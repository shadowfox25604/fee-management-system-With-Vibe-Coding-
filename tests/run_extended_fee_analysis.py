"""Extended multi-run fee rollover and payment analysis report."""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base
from backend.core.schema_migrations import apply_sqlite_column_migrations, apply_sqlite_data_migrations
from backend.core.fee_due_display import rollover_pending_from_due
from backend.models import Student, entities  # noqa: F401
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.repositories.payment_repository import PaymentRepository
from backend.repositories.student_year_fee_repository import StudentYearFeeRepository
from backend.services.academic_year_service import AcademicYearService
from backend.services.class_fee_service import ClassFeeService
from backend.services.fee_balance_service import FeeBalanceService
from backend.services.village_van_fee_service import VillageVanFeeService
from tests.test_rollover_analysis_scenarios import _fee_heads, _run_rollover_scenarios


def _fresh_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    return sessionmaker(bind=engine)()


def run_triple_rollover_chain(session) -> bool:
    for row in AcademicYearRepository(session).list_all():
        session.delete(row)
    session.commit()

    ay = AcademicYearRepository(session)
    y1 = ay.create(date(2020, 5, 17), date(2021, 4, 18), "2020-21")
    y2 = ay.create(date(2021, 5, 17), date(2022, 4, 18), "2021-22")
    y3 = ay.create(date(2022, 5, 17), date(2023, 4, 18), "2022-23")
    session.commit()
    _fee_heads(session)
    sy = StudentYearFeeRepository(session)
    balance = FeeBalanceService(session)
    ay_svc = AcademicYearService(session)
    class_svc = ClassFeeService(session)
    village_svc = VillageVanFeeService(session)

    profiles = [
        ("CHAIN-A", 500, 200, 3000, 400, 4000, 500),
        ("CHAIN-B", 0, 0, 0, 0, 8000, 1200),
        ("CHAIN-C", 1500, 600, 2500, 800, 6000, 900),
    ]
    students = []
    for label, s_old, v_old, s_mid, v_mid, s_cur, v_cur in profiles:
        st = Student(
            student_id=label,
            full_name=label,
            class_name="4",
            section="A",
            phone=f"9{abs(hash(label)) % 10**9:09d}",
            guardian_name="G",
            school_fees=s_cur,
            van_fees=v_cur,
        )
        st.created_at = datetime(2020, 6, 1)
        session.add(st)
        session.commit()
        sy.get_or_create(st, y1.id, school_fees=s_old, van_fees=v_old)
        sy.get_or_create(st, y2.id, school_fees=s_mid, van_fees=v_mid)
        sy.get_or_create(st, y3.id, school_fees=s_cur, van_fees=v_cur)
        session.commit()
        students.append((label, st))

    ok = True
    print("\nRUN 3 — Triple consecutive rollovers (3 students, 2 year increments each):")
    print(
        f"{'Student':<10} {'Stage':<8} {'Pending':>10} {'SchDue':>10} "
        f"{'VanDue':>10} {'Expected':>10} {'Result':>6}"
    )

    before_y4_map = {}
    for label, st in students:
        before_y4_map[label] = balance.get_students_due_breakdown(
            [st.student_id], as_of=y3.end_date
        )[st.student_id]

    ay_svc.create_year(
        date(2023, 5, 17), date(2024, 4, 18), "2023-24",
        class_fee_service=class_svc, village_fee_service=village_svc,
    )
    session.commit()
    y4 = ay.list_all()[-1]

    for label, st in students:
        before_y4 = before_y4_map[label]
        after_y4 = balance.get_students_due_breakdown([st.student_id], as_of=y4.start_date)[st.student_id]
        exp_y4 = rollover_pending_from_due(before_y4)
        m4 = abs(float(after_y4["pending_fees"]) - exp_y4) < 0.02
        ok &= m4
        print(
            f"{label:<10} {'Y3->Y4':<8} {after_y4['pending_fees']:>10.2f} "
            f"{after_y4['fee_due']:>10.2f} {after_y4['van_due']:>10.2f} "
            f"{exp_y4:>10.2f} {'OK' if m4 else 'FAIL':>6}"
        )

    before_y5_map = {}
    for label, st in students:
        before_y5_map[label] = balance.get_students_due_breakdown(
            [st.student_id], as_of=y4.end_date
        )[st.student_id]

    ay_svc.create_year(
        date(2024, 5, 17), date(2025, 4, 18), "2024-25",
        class_fee_service=class_svc, village_fee_service=village_svc,
    )
    session.commit()
    y5 = ay.list_all()[-1]

    for label, st in students:
        before_y5_src = before_y5_map[label]
        after_y5 = balance.get_students_due_breakdown([st.student_id], as_of=y5.start_date)[st.student_id]
        exp_y5 = rollover_pending_from_due(before_y5_src)
        m5 = abs(float(after_y5["pending_fees"]) - exp_y5) < 0.02
        ok &= m5
        print(
            f"{label:<10} {'Y4->Y5':<8} {after_y5['pending_fees']:>10.2f} "
            f"{after_y5['fee_due']:>10.2f} {after_y5['van_due']:>10.2f} "
            f"{exp_y5:>10.2f} {'OK' if m5 else 'FAIL':>6}"
        )
    print(f"Triple rollover chain: {'ALL OK' if ok else 'FAILURES DETECTED'}")
    return ok


def payment_after_rollover(session, results) -> None:
    pay_repo = PaymentRepository(session)
    balance = FeeBalanceService(session)
    y_new = AcademicYearRepository(session).list_all()[-1]

    print("\nPAYMENT AFTER ROLLOVER — Rs 500 school payment debits combined pending first:")
    print(
        f"{'Scenario':<22} {'PendingBefore':>14} {'Paid':>8} "
        f"{'PendingAfter':>13} {'SchDueAfter':>12} {'VanDueAfter':>12}"
    )
    for r in results:
        if r.expected_rolled < 0.02:
            continue
        st = session.scalars(select(Student).where(Student.student_id == r.student_id)).first()
        before = balance.get_students_due_breakdown([st.student_id])[st.student_id]
        pay_amt = min(500.0, float(before["pending_fees"]))
        if pay_amt <= 0:
            continue
        pay_repo.create_split_payment(st, 0.0, pay_amt, "cash", "analysis", 0.0, y_new.start_date)
        after = balance.get_students_due_breakdown([st.student_id])[st.student_id]
        print(
            f"{r.name:<22} {before['pending_fees']:>14.2f} {pay_amt:>8.2f} "
            f"{after['pending_fees']:>13.2f} {after['fee_due']:>12.2f} {after['van_due']:>12.2f}"
        )


def main() -> int:
    print("=" * 100)
    print("EXTENDED FEE ANALYSIS — MULTIPLE RUNS, STUDENTS, AND ACADEMIC YEARS")
    print("=" * 100)

    session = _fresh_session()
    try:
        r1 = _run_rollover_scenarios(session)
        print(f"\nRUN 1 — 6-student rollover suite: {sum(1 for r in r1 if r.passed)}/{len(r1)} passed")
        payment_after_rollover(session, r1)
    finally:
        session.close()

    session = _fresh_session()
    try:
        r2 = _run_rollover_scenarios(session)
        print(f"\nRUN 2 — repeat identical suite: {sum(1 for r in r2 if r.passed)}/{len(r2)} passed")
    finally:
        session.close()

    session = _fresh_session()
    try:
        chain_ok = run_triple_rollover_chain(session)
    finally:
        session.close()

    session = _fresh_session()
    try:
        results = _run_rollover_scenarios(session)
        print("\n" + "=" * 100)
        print("MASTER SUMMARY — 6 SCENARIOS × VARIABLE PENDING / CURRENT SCHOOL / CURRENT VAN")
        print("=" * 100)
        print(
            f"{'Scenario':<22} {'OldPen':>9} {'CurSch':>9} {'CurVan':>9} "
            f"{'Rolled':>10} {'Opening':>10} {'NewPen':>10} {'NewSch':>9} {'NewVan':>9} {'OK':>4}"
        )
        print("-" * 100)
        for r in results:
            print(
                f"{r.name:<22} {r.before_pending:>9.2f} {r.before_school:>9.2f} {r.before_van:>9.2f} "
                f"{r.expected_rolled:>10.2f} {r.opening_stored:>10.2f} {r.after_pending:>10.2f} "
                f"{r.after_school:>9.2f} {r.after_van:>9.2f} {'Y' if r.passed else 'N':>4}"
            )
        all_ok = all(r.passed for r in results) and chain_ok
    finally:
        session.close()

    print("\n" + "=" * 100)
    if all_ok:
        print("OVERALL: ALL RUNS PASSED — rollover formula verified across multiple iterations.")
    else:
        print("OVERALL: FAILURES DETECTED — review scenarios marked FAIL.")
    print("=" * 100)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
