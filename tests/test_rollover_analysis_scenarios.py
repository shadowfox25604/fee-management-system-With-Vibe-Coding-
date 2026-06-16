"""
Multi-student / multi-year rollover analysis scenarios.
Run: python -m pytest tests/test_rollover_analysis_scenarios.py -v -s
Or:  python tests/run_rollover_analysis.py
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime

import pytest
from sqlalchemy import func, select

from backend.models import FeeHead, Student, entities  # noqa: F401
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.repositories.payment_repository import PaymentRepository
from backend.repositories.student_year_fee_repository import StudentYearFeeRepository
from backend.services.academic_year_service import AcademicYearService
from backend.services.class_fee_service import ClassFeeService
from backend.services.fee_balance_service import FeeBalanceService
from backend.services.village_van_fee_service import VillageVanFeeService
from tests.academic_year_helpers import clear_all_academic_years


def _set_joining_date(student: Student, d: date) -> None:
    student.created_at = datetime(d.year, d.month, d.day, 10, 0, 0)


def _fee_heads(session):
    t = session.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "tuition")).first()
    tr = session.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "transport")).first()
    if t is None:
        t = FeeHead(head_name="Tuition", frequency="monthly", default_amount=2000.0)
        session.add(t)
    if tr is None:
        tr = FeeHead(head_name="Transport", frequency="monthly", default_amount=500.0)
        session.add(tr)
    session.flush()
    return t, tr


@dataclass
class ScenarioResult:
    name: str
    student_id: str
    before_pending: float
    before_school: float
    before_van: float
    expected_rolled: float
    opening_stored: float
    after_pending: float
    after_school: float
    after_van: float
    new_year_school_tariff: float
    new_year_van_tariff: float
    passed: bool
    notes: str


def _build_base_years(ay_repo, db_session):
    clear_all_academic_years(db_session)
    y_old = ay_repo.create(date(2022, 5, 17), date(2023, 4, 18), "2022-23")
    y_prev = ay_repo.create(date(2023, 5, 17), date(2024, 4, 18), "2023-24")
    y_cur = ay_repo.create(date(2024, 5, 17), date(2025, 4, 18), "2024-25")
    db_session.commit()
    return y_old, y_prev, y_cur


def _run_rollover_scenarios(db_session) -> list[ScenarioResult]:
    _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    y_old, y_prev, y_cur = _build_base_years(ay_repo, db_session)
    sy = StudentYearFeeRepository(db_session)
    balance = FeeBalanceService(db_session)
    snapshot_date = y_cur.end_date

    specs = [
        {
            "name": "A_only_old_pending",
            "school_old": 1500.0,
            "van_old": 400.0,
            "school_prev": 0.0,
            "van_prev": 0.0,
            "school_cur": 5000.0,
            "van_cur": 800.0,
            "paid_prev_school": 0.0,
            "paid_prev_van": 0.0,
            "paid_cur_school": 5000.0,
            "paid_cur_van": 800.0,
        },
        {
            "name": "B_only_current_unpaid",
            "school_old": 0.0,
            "van_old": 0.0,
            "school_prev": 0.0,
            "van_prev": 0.0,
            "school_cur": 6000.0,
            "van_cur": 1000.0,
            "paid_prev_school": 0.0,
            "paid_prev_van": 0.0,
            "paid_cur_school": 0.0,
            "paid_cur_van": 0.0,
        },
        {
            "name": "C_pending_plus_current",
            "school_old": 2000.0,
            "van_old": 500.0,
            "school_prev": 3000.0,
            "van_prev": 700.0,
            "school_cur": 8000.0,
            "van_cur": 1200.0,
            "paid_prev_school": 1000.0,
            "paid_prev_van": 200.0,
            "paid_cur_school": 2000.0,
            "paid_cur_van": 300.0,
        },
        {
            "name": "D_fully_paid",
            "school_old": 1000.0,
            "van_old": 200.0,
            "school_prev": 2000.0,
            "van_prev": 300.0,
            "school_cur": 5000.0,
            "van_cur": 600.0,
            "paid_prev_school": 1000.0,
            "paid_prev_van": 200.0,
            "paid_cur_school": 5000.0,
            "paid_cur_van": 600.0,
        },
        {
            "name": "E_van_pending_only",
            "school_old": 0.0,
            "van_old": 0.0,
            "school_prev": 0.0,
            "van_prev": 1272.73,
            "school_cur": 17454.27,
            "van_cur": 5272.73,
            "paid_prev_school": 0.0,
            "paid_prev_van": 4000.0,
            "paid_cur_school": 2545.73,
            "paid_cur_van": 0.0,
        },
        {
            "name": "F_school_pending_heavy",
            "school_old": 5000.0,
            "van_old": 0.0,
            "school_prev": 4000.0,
            "van_prev": 0.0,
            "school_cur": 10000.0,
            "van_cur": 0.0,
            "paid_prev_school": 0.0,
            "paid_prev_van": 0.0,
            "paid_cur_school": 3000.0,
            "paid_cur_van": 0.0,
        },
    ]

    students = []
    for spec in specs:
        sid = f"T{spec['name'][:1]}{uuid.uuid4().hex[:6].upper()}"
        st = Student(
            student_id=sid,
            full_name=f"Test {spec['name']}",
            class_name="5",
            section="A",
            phone=f"9{uuid.uuid4().int % 10**9:09d}",
            guardian_name="G",
            van_fees=spec["van_cur"],
            school_fees=spec["school_cur"],
        )
        db_session.add(st)
        db_session.commit()
        _set_joining_date(st, date(2022, 6, 1))
        sy.get_or_create(st, y_old.id, school_fees=spec["school_old"], van_fees=spec["van_old"])
        sy.get_or_create(st, y_prev.id, school_fees=spec["school_prev"], van_fees=spec["van_prev"])
        row_cur = sy.get_or_create(st, y_cur.id, school_fees=spec["school_cur"], van_fees=spec["van_cur"])
        db_session.commit()
        spec["_student"] = st
        spec["_row_cur"] = row_cur
        students.append(spec)

    t, tr = _fee_heads(db_session)

    for spec in students:
        st = spec["_student"]
        if spec["paid_prev_van"] > 0:
            _make_invoice(db_session, st, y_prev.id, tr.id, spec["van_prev"], spec["paid_prev_van"])
        if spec["paid_cur_school"] > 0:
            _make_invoice(db_session, st, y_cur.id, t.id, spec["school_cur"], spec["paid_cur_school"])
        if spec["paid_cur_van"] > 0:
            _make_invoice(db_session, st, y_cur.id, tr.id, spec["van_cur"], spec["paid_cur_van"])
    db_session.commit()

    before_map = {}
    for spec in students:
        st = spec["_student"]
        due = balance.get_students_due_breakdown([st.student_id], as_of=snapshot_date)[st.student_id]
        before_map[st.student_id] = due

    class_svc = ClassFeeService(db_session)
    village_svc = VillageVanFeeService(db_session)
    AcademicYearService(db_session).create_year(
        date(2025, 5, 17),
        date(2026, 4, 18),
        "2025-26",
        class_fee_service=class_svc,
        village_fee_service=village_svc,
    )
    db_session.commit()
    y_new = ay_repo.list_all()[-1]

    results = []
    for spec in students:
        st = spec["_student"]
        before = before_map[st.student_id]
        bp = float(before["pending_fees"])
        bs = float(before["fee_due"])
        bv = float(before["van_due"])
        expected = bp + bs + bv
        new_row = sy.get(st.student_id, y_new.id)
        opening = float(new_row.opening_pending_fees or 0) if new_row else 0.0
        after = balance.get_students_due_breakdown([st.student_id], as_of=y_new.start_date)[st.student_id]
        ap = float(after["pending_fees"])
        asn = float(after["fee_due"])
        avn = float(after["van_due"])
        ns = float(new_row.school_fees or 0) if new_row else 0.0
        nv = float(new_row.van_fees or 0) if new_row else 0.0

        ok_opening = abs(opening - expected) < 0.02
        ok_pending = abs(ap - expected) < 0.02
        ok_school = abs(asn - ns) < 0.02
        ok_van = abs(avn - nv) < 0.02
        passed = ok_opening and ok_pending and ok_school and ok_van
        notes = []
        if not ok_opening:
            notes.append(f"opening mismatch got {opening:.2f} expected {expected:.2f}")
        if not ok_pending:
            notes.append(f"pending mismatch got {ap:.2f} expected {expected:.2f}")
        if not ok_school:
            notes.append(f"school due mismatch got {asn:.2f} expected {ns:.2f}")
        if not ok_van:
            notes.append(f"van due mismatch got {avn:.2f} expected {nv:.2f}")

        results.append(
            ScenarioResult(
                name=spec["name"],
                student_id=st.student_id,
                before_pending=bp,
                before_school=bs,
                before_van=bv,
                expected_rolled=expected,
                opening_stored=opening,
                after_pending=ap,
                after_school=asn,
                after_van=avn,
                new_year_school_tariff=ns,
                new_year_van_tariff=nv,
                passed=passed,
                notes="; ".join(notes) if notes else "OK",
            )
        )
    return results


def _make_invoice(session, student, year_id, fee_head_id, amount_due, amount_paid):
    from backend.models import Invoice

    inv = Invoice(
        student_id_fk=student.student_id,
        academic_year_id=year_id,
        fee_head_id=fee_head_id,
        period_label="test",
        due_date=date(2025, 3, 1),
        amount_due=amount_due,
        amount_paid=amount_paid,
    )
    session.add(inv)
    session.flush()
    return inv


def test_all_rollover_scenarios_pass(db_session):
    results = _run_rollover_scenarios(db_session)
    failed = [r for r in results if not r.passed]
    assert not failed, failed


def test_payment_after_rollover_clears_pending_first(db_session):
    _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    y_old, y_prev, y_cur = _build_base_years(ay_repo, db_session)
    st = Student(
        student_id=f"PAY{uuid.uuid4().hex[:4].upper()}",
        full_name="Payment After Rollover",
        class_name="6",
        section="B",
        phone=f"8{uuid.uuid4().int % 10**9:09d}",
        guardian_name="G",
        van_fees=1000.0,
        school_fees=7000.0,
    )
    db_session.add(st)
    db_session.commit()
    _set_joining_date(st, date(2022, 6, 1))
    sy = StudentYearFeeRepository(db_session)
    sy.get_or_create(st, y_prev.id, school_fees=2000.0, van_fees=500.0)
    sy.get_or_create(st, y_cur.id, school_fees=7000.0, van_fees=1000.0)
    db_session.commit()

    AcademicYearService(db_session).create_year(
        date(2025, 5, 17),
        date(2026, 4, 18),
        "2025-26",
        class_fee_service=ClassFeeService(db_session),
        village_fee_service=VillageVanFeeService(db_session),
    )
    db_session.commit()

    balance = FeeBalanceService(db_session)
    pay_repo = PaymentRepository(db_session)
    y_new = ay_repo.list_all()[-1]
    before = balance.get_students_due_breakdown([st.student_id], as_of=y_new.start_date)[st.student_id]
    pending_before = float(before["pending_fees"])
    pay_repo.create_split_payment(st, 0.0, pending_before, "cash", "test", 0.0, y_new.start_date)
    after = balance.get_students_due_breakdown([st.student_id], as_of=y_new.start_date)[st.student_id]
    assert after["pending_fees"] == pytest.approx(0.0, abs=0.02)
    assert after["fee_due"] == pytest.approx(float(before["fee_due"]), abs=0.02)


import pytest  # noqa: E402 — used in test above
