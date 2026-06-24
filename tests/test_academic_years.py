import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import func, select

import backend.core.database as db
from backend.models import FeeHead, Invoice, Student, entities  # noqa: F401
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.repositories.payment_repository import PaymentRepository
from backend.repositories.student_year_fee_repository import StudentYearFeeRepository
from backend.services.academic_year_service import AcademicYearService
from backend.services.fee_balance_service import FeeBalanceService
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


def test_standard_academic_year_bounds_and_labels():
    from backend.core.academic_year_dates import (
        academic_year_bounds_for_start_year,
        academic_year_start_year_for_date,
        auto_label_for_range,
        default_academic_year_bounds,
        format_academic_year_range,
    )

    start, end = academic_year_bounds_for_start_year(2025)
    assert start == date(2025, 5, 31)
    assert end == date(2026, 6, 1)
    assert auto_label_for_range(start, end) == "2025-2026"
    assert format_academic_year_range(start, end) == "31 May 2025 - 1 June 2026"

    assert academic_year_start_year_for_date(date(2026, 3, 10)) == 2025
    assert academic_year_start_year_for_date(date(2026, 6, 12)) == 2026
    cur_start, cur_end = default_academic_year_bounds(date(2026, 6, 12))
    assert cur_start == date(2026, 5, 31)
    assert cur_end == date(2027, 6, 1)


def test_create_next_academic_year_uses_standard_bounds(db_session):
    clear_all_academic_years(db_session)

    svc = AcademicYearService(db_session)
    expected_start, expected_end, expected_label = svc.next_academic_year_bounds()
    first = svc.create_next_year(provision_students=False)
    assert first.label == expected_label
    assert first.start_date == expected_start
    assert first.end_date == expected_end

    second = svc.create_next_year(provision_students=False)
    assert second.start_date.year == first.start_date.year + 1
    assert second.end_date.year == first.end_date.year + 1
    assert second.label == f"{second.start_date.year}-{second.end_date.year}"


def test_academic_year_persists_after_new_session(db_session):
    """Year must be on disk before student provisioning finishes (survives app restart)."""
    from backend.services.academic_year_service import AcademicYearService

    clear_all_academic_years(db_session)

    svc = AcademicYearService(db_session)
    y = svc.create_year(
        date(2024, 5, 17),
        date(2025, 4, 18),
        "2024-25",
        provision_students=False,
    )
    assert y.id is not None
    db_session.close()

    s2 = db.SessionLocal()
    try:
        labels = [r.label for r in AcademicYearRepository(s2).list_all()]
        assert "2024-25" in labels
    finally:
        s2.close()


def test_academic_year_overlap_rejected(db_session):
    repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)
    repo.create(date(2025, 5, 17), date(2026, 4, 18), "2025-26")
    db_session.commit()
    with pytest.raises(ValueError, match="overlap"):
        repo.create(date(2026, 1, 1), date(2026, 12, 31), "bad")


def test_payment_applies_to_pending_year_first(db_session):
    t, tr = _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)
    y1 = ay_repo.create(date(2024, 5, 17), date(2025, 4, 18), "2024-25")
    y2 = ay_repo.create(date(2025, 5, 17), date(2026, 4, 18), "2025-26")
    db_session.commit()

    sid = f"AY{uuid.uuid4().hex[:6].upper()}"
    st = Student(
        student_id=sid,
        full_name="Year Order",
        class_name="5",
        section="A",
        phone=f"9{uuid.uuid4().int % 10**9:09d}",
        guardian_name="G",
        van_fees=1000.0,
        school_fees=5000.0,
    )
    db_session.add(st)
    db_session.commit()
    _set_joining_date(st, date(2024, 6, 1))
    sy = StudentYearFeeRepository(db_session)
    sy.get_or_create(st, y1.id, school_fees=5000.0, van_fees=1000.0)
    sy.get_or_create(st, y2.id, school_fees=5000.0, van_fees=1000.0)
    db_session.commit()

    db_session.add(
        Invoice(
            student_id_fk=st.student_id,
            academic_year_id=y1.id,
            fee_head_id=t.id,
            period_label="y1",
            due_date=date(2025, 3, 1),
            amount_due=5000.0,
            amount_paid=0.0,
        )
    )
    db_session.add(
        Invoice(
            student_id_fk=st.student_id,
            academic_year_id=y2.id,
            fee_head_id=t.id,
            period_label="y2",
            due_date=date(2026, 1, 1),
            amount_due=5000.0,
            amount_paid=0.0,
        )
    )
    db_session.commit()

    balance = FeeBalanceService(db_session)
    due = balance.get_students_due_breakdown([st.student_id], {st.student_id: 0.0})[st.student_id]
    assert due["school_pending"] >= 5000.0 - 1e-6
    assert due["school_current"] >= 5000.0 - 1e-6

    pay_repo = PaymentRepository(db_session)
    pay_repo.create_split_payment(st, 0.0, 2000.0, "cash", "test", 0.0, date(2025, 6, 1))
    inv_old = db_session.scalars(
        select(Invoice).where(Invoice.student_id_fk == st.student_id, Invoice.academic_year_id == y1.id)
    ).first()
    inv_new = db_session.scalars(
        select(Invoice).where(Invoice.student_id_fk == st.student_id, Invoice.academic_year_id == y2.id)
    ).first()
    assert float(inv_old.amount_paid) == 2000.0
    assert float(inv_new.amount_paid) == 0.0


def test_tariff_only_pending_cleared_before_current_year(db_session):
    """Prior-year debt with no invoices: payment must reduce school_pending before school_current."""
    t, _tr = _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)
    y_old = ay_repo.create(date(2023, 5, 17), date(2024, 4, 18), "2023-24")
    y_cur = ay_repo.create(date(2025, 5, 17), date(2026, 4, 18), "2025-26")
    db_session.commit()

    st = Student(
        student_id=f"TP{uuid.uuid4().hex[:4].upper()}",
        full_name="Tariff Pending",
        class_name="2",
        section="B",
        phone=f"5{uuid.uuid4().int % 10**9:09d}",
        guardian_name="G",
        van_fees=0.0,
        school_fees=10000.0,
    )
    db_session.add(st)
    db_session.commit()
    _set_joining_date(st, date(2023, 6, 1))
    sy = StudentYearFeeRepository(db_session)
    sy.get_or_create(st, y_old.id, school_fees=8000.0, van_fees=0.0)
    sy.get_or_create(st, y_cur.id, school_fees=10000.0, van_fees=0.0)
    db_session.commit()
    # Only current year has an invoice (legacy-style data).
    db_session.add(
        Invoice(
            student_id_fk=st.student_id,
            academic_year_id=y_cur.id,
            fee_head_id=t.id,
            period_label="cur-only",
            due_date=date(2026, 1, 1),
            amount_due=10000.0,
            amount_paid=0.0,
        )
    )
    db_session.commit()

    balance = FeeBalanceService(db_session)
    pay_repo = PaymentRepository(db_session)
    before = balance.get_students_due_breakdown([st.student_id], {st.student_id: 0.0})[st.student_id]
    assert before["school_pending"] == pytest.approx(8000.0, abs=0.02)
    assert before["school_current"] == pytest.approx(10000.0, abs=0.02)

    pay_repo.create_split_payment(st, 0.0, 5000.0, "cash", "test", 0.0, date(2025, 6, 1))
    after = balance.get_students_due_breakdown([st.student_id], {st.student_id: 0.0})[st.student_id]
    assert after["school_pending"] == pytest.approx(3000.0, abs=0.02)
    assert after["school_current"] == pytest.approx(10000.0, abs=0.02)


def test_due_breakdown_splits_pending_and_current(db_session):
    t, tr = _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)
    y_prev = ay_repo.create(date(2023, 5, 17), date(2024, 4, 18), "2023-24")
    y_cur = ay_repo.create(date(2025, 5, 17), date(2026, 4, 18), "2025-26")
    db_session.commit()

    st = Student(
        student_id=f"AY2{uuid.uuid4().hex[:4].upper()}",
        full_name="Due Split",
        class_name="3",
        section="B",
        phone=f"8{uuid.uuid4().int % 10**9:09d}",
        guardian_name="G",
        van_fees=500.0,
        school_fees=3000.0,
    )
    db_session.add(st)
    db_session.commit()
    _set_joining_date(st, date(2023, 6, 1))
    sy = StudentYearFeeRepository(db_session)
    sy.get_or_create(st, y_prev.id, school_fees=3000.0, van_fees=500.0)
    sy.get_or_create(st, y_cur.id, school_fees=4000.0, van_fees=600.0)
    db_session.commit()

    balance = FeeBalanceService(db_session)
    due = balance.get_students_due_breakdown([st.student_id], {st.student_id: 0.0})[st.student_id]
    assert due["school_pending"] == pytest.approx(3000.0, abs=0.01)
    assert due["school_current"] == pytest.approx(4000.0, abs=0.01)
    assert due["van_pending"] == pytest.approx(500.0, abs=0.01)
    assert due["van_current"] == pytest.approx(600.0, abs=0.01)
    assert due["pending_fees"] == pytest.approx(
        due["school_pending"] + due["van_pending"], abs=0.01
    )


def test_new_student_has_no_pending_from_older_years(db_session):
    """Student joining in the current year must not inherit tariffs from prior academic years."""
    _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)
    ay_repo.create(date(2024, 5, 17), date(2025, 4, 18), "2024-25")
    ay_repo.create(date(2025, 5, 17), date(2026, 4, 18), "2025-26")
    y_cur = ay_repo.create(date(2026, 5, 17), date(2027, 4, 18), "2026-27")
    db_session.commit()

    st = Student(
        student_id=f"NEW{uuid.uuid4().hex[:4].upper()}",
        full_name="GOUTHAM",
        class_name="2",
        section="B",
        phone=f"9{uuid.uuid4().int % 10**9:09d}",
        guardian_name="Guardian",
        van_fees=4500.0,
        school_fees=19870.18,
    )
    db_session.add(st)
    db_session.commit()
    StudentYearFeeRepository(db_session).sync_student_to_current_year(st)
    db_session.commit()

    due = FeeBalanceService(db_session).get_students_due_breakdown([st.student_id], {st.student_id: 0.0})[st.student_id]
    assert due["school_pending"] == pytest.approx(0.0, abs=0.01)
    assert due["van_pending"] == pytest.approx(0.0, abs=0.01)
    assert due["fee_due"] == pytest.approx(19870.18, abs=0.01)
    assert due["van_due"] == pytest.approx(4500.0, abs=0.01)
    assert due["school_payable"] == pytest.approx(19870.18, abs=0.01)
    assert due["van_payable"] == pytest.approx(4500.0, abs=0.01)
    assert due["total"] == pytest.approx(24370.18, abs=0.01)


def test_school_payment_clears_pending_before_current_year(db_session):
    t, _tr = _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)
    y_old = ay_repo.create(date(2023, 5, 17), date(2024, 4, 18), "2023-24")
    y_cur = ay_repo.create(date(2025, 5, 17), date(2026, 4, 18), "2025-26")
    db_session.commit()

    st = Student(
        student_id=f"SP{uuid.uuid4().hex[:4].upper()}",
        full_name="School Pay Order",
        class_name="4",
        section="A",
        phone=f"7{uuid.uuid4().int % 10**9:09d}",
        guardian_name="G",
        van_fees=0.0,
        school_fees=6000.0,
    )
    db_session.add(st)
    db_session.commit()
    _set_joining_date(st, date(2023, 6, 1))
    sy = StudentYearFeeRepository(db_session)
    sy.get_or_create(st, y_old.id, school_fees=2000.0, van_fees=0.0)
    sy.get_or_create(st, y_cur.id, school_fees=6000.0, van_fees=0.0)
    db_session.commit()

    balance = FeeBalanceService(db_session)
    pay_repo = PaymentRepository(db_session)
    before = balance.get_students_due_breakdown([st.student_id], {st.student_id: 0.0})[st.student_id]
    assert before["school_pending"] == pytest.approx(2000.0, abs=0.02)
    assert before["fee_due"] == pytest.approx(6000.0, abs=0.02)

    pay_repo.create_split_payment(st, 0.0, 2500.0, "cash", "test", 0.0, date(2025, 6, 1))
    after = balance.get_students_due_breakdown([st.student_id], {st.student_id: 0.0})[st.student_id]
    assert after["school_pending"] == pytest.approx(0.0, abs=0.02)
    assert after["fee_due"] == pytest.approx(5500.0, abs=0.02)


def test_van_payment_only_clears_current_year_not_pending(db_session):
    """Prior-year van is in combined pending; van payment clears current-year van only."""
    _t, tr = _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)
    y_old = ay_repo.create(date(2023, 5, 17), date(2024, 4, 18), "2023-24")
    y_cur = ay_repo.create(date(2025, 5, 17), date(2026, 4, 18), "2025-26")
    db_session.commit()

    st = Student(
        student_id=f"VP{uuid.uuid4().hex[:4].upper()}",
        full_name="Van Pay Order",
        class_name="4",
        section="A",
        phone=f"6{uuid.uuid4().int % 10**9:09d}",
        guardian_name="G",
        van_fees=800.0,
        school_fees=0.0,
    )
    db_session.add(st)
    db_session.commit()
    _set_joining_date(st, date(2023, 6, 1))
    sy = StudentYearFeeRepository(db_session)
    sy.get_or_create(st, y_old.id, school_fees=0.0, van_fees=300.0)
    sy.get_or_create(st, y_cur.id, school_fees=0.0, van_fees=800.0)
    db_session.commit()

    balance = FeeBalanceService(db_session)
    pay_repo = PaymentRepository(db_session)
    before = balance.get_students_due_breakdown([st.student_id], {st.student_id: 0.0})[st.student_id]
    assert before["van_pending"] == pytest.approx(300.0, abs=0.02)
    assert before["van_due"] == pytest.approx(800.0, abs=0.02)

    pay_repo.create_split_payment(st, 500.0, 0.0, "cash", "test", 0.0, date(2025, 6, 1))
    after = balance.get_students_due_breakdown([st.student_id], {st.student_id: 0.0})[st.student_id]
    assert after["pending_fees"] == pytest.approx(300.0, abs=0.02)
    assert after["van_pending"] == pytest.approx(300.0, abs=0.02)
    assert after["van_due"] == pytest.approx(300.0, abs=0.02)


def test_van_payment_does_not_clear_pending_only_current_van(db_session):
    """Van payment must not reduce combined pending; only current-year van due."""
    t, tr = _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)
    y_old = ay_repo.create(date(2023, 5, 17), date(2024, 4, 18), "2023-24")
    y_cur = ay_repo.create(date(2025, 5, 17), date(2026, 4, 18), "2025-26")
    db_session.commit()

    st = Student(
        student_id=f"VC{uuid.uuid4().hex[:4].upper()}",
        full_name="Van Clears Combined Pending",
        class_name="4",
        section="A",
        phone=f"4{uuid.uuid4().int % 10**9:09d}",
        guardian_name="G",
        van_fees=1000.0,
        school_fees=2000.0,
    )
    db_session.add(st)
    db_session.commit()
    _set_joining_date(st, date(2023, 6, 1))
    sy = StudentYearFeeRepository(db_session)
    sy.get_or_create(st, y_old.id, school_fees=1500.0, van_fees=500.0)
    sy.get_or_create(st, y_cur.id, school_fees=2000.0, van_fees=1000.0)
    db_session.commit()

    balance = FeeBalanceService(db_session)
    pay_repo = PaymentRepository(db_session)
    before = balance.get_students_due_breakdown([st.student_id], {st.student_id: 0.0})[st.student_id]
    assert before["pending_fees"] == pytest.approx(2000.0, abs=0.02)
    assert before["school_pending"] == pytest.approx(1500.0, abs=0.02)
    assert before["van_pending"] == pytest.approx(500.0, abs=0.02)
    assert before["van_payable"] == pytest.approx(1000.0, abs=0.02)

    pay_repo.create_split_payment(st, 1000.0, 0.0, "cash", "test", 0.0, date(2025, 6, 1))
    after = balance.get_students_due_breakdown([st.student_id], {st.student_id: 0.0})[st.student_id]
    assert after["pending_fees"] == pytest.approx(2000.0, abs=0.02)
    assert after["school_pending"] == pytest.approx(1500.0, abs=0.02)
    assert after["van_pending"] == pytest.approx(500.0, abs=0.02)
    assert after["fee_due"] == pytest.approx(2000.0, abs=0.02)
    assert after["van_due"] == pytest.approx(0.0, abs=0.02)


def test_next_class_key_progression():
    from backend.core.fee_control_constants import (
        FIXED_CLASS_KEYS,
        PASSED_OUT_CLASS_KEY,
        next_class_key,
    )

    assert next_class_key("LKG") == "UKG"
    assert next_class_key("lkg") == "UKG"
    assert next_class_key("UKG") == "1"
    assert next_class_key("6") == "7"
    assert next_class_key("9") == "10"
    assert next_class_key("10") == PASSED_OUT_CLASS_KEY
    assert next_class_key(PASSED_OUT_CLASS_KEY) is None
    assert next_class_key("passed out") is None
    assert next_class_key("11") is None
    assert next_class_key("Nursery") == "LKG"
    assert next_class_key("unknown") is None

    for idx, key in enumerate(FIXED_CLASS_KEYS[:-1]):
        assert next_class_key(key) == FIXED_CLASS_KEYS[idx + 1]
    assert next_class_key(FIXED_CLASS_KEYS[-1]) == PASSED_OUT_CLASS_KEY


def test_create_year_promotes_students(db_session):
    from backend.core.fee_control_constants import FIXED_CLASS_KEYS, next_class_key
    from backend.services.class_fee_service import ClassFeeService
    from backend.services.village_van_fee_service import VillageVanFeeService

    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)

    ay_repo.create(date(2024, 5, 17), date(2025, 4, 18), "2024-25")
    db_session.commit()
    class_svc = ClassFeeService(db_session)
    year_2024 = ay_repo.list_all()[0]
    for class_key in FIXED_CLASS_KEYS:
        class_svc.repo.upsert_stored_amount(class_key, year_2024.id, 20000.0)
    db_session.commit()

    st = Student(
        student_id=f"PROMO-{uuid.uuid4().hex[:8]}",
        full_name="Promo Student",
        class_name="LKG",
        section="A",
        phone="9876543210",
        guardian_name="G",
        status="active",
        school_fees=10000.0,
        van_fees=500.0,
    )
    db_session.add(st)
    db_session.commit()

    village_svc = VillageVanFeeService(db_session)
    ay_svc = AcademicYearService(db_session)
    ay_svc.create_year(
        date(2025, 5, 17),
        date(2026, 4, 18),
        "2025-26",
        class_fee_service=class_svc,
        village_fee_service=village_svc,
    )
    db_session.refresh(st)

    assert st.class_name == next_class_key("LKG")
    new_year = ay_repo.list_all()[-1]
    year_row = StudentYearFeeRepository(db_session).get(st.student_id, new_year.id)
    assert year_row is not None
    assert year_row.school_fees == pytest.approx(
        class_svc.school_fees_for_class_name("UKG", new_year.id), abs=0.01
    )


def test_create_year_promotes_nursery_to_lkg(db_session):
    from backend.core.fee_control_constants import FIXED_CLASS_KEYS, next_class_key
    from backend.services.class_fee_service import ClassFeeService
    from backend.services.village_van_fee_service import VillageVanFeeService

    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)

    ay_repo.create(date(2024, 5, 17), date(2025, 4, 18), "2024-25")
    db_session.commit()
    class_svc = ClassFeeService(db_session)
    year_2024 = ay_repo.list_all()[0]
    for class_key in FIXED_CLASS_KEYS:
        class_svc.repo.upsert_stored_amount(class_key, year_2024.id, 20000.0)
    db_session.commit()

    st = Student(
        student_id=f"NURS-{uuid.uuid4().hex[:8]}",
        full_name="Nursery Student",
        class_name="Nursery",
        section="A",
        phone="9876543213",
        guardian_name="G",
        status="active",
        school_fees=10000.0,
        van_fees=500.0,
    )
    db_session.add(st)
    db_session.commit()

    village_svc = VillageVanFeeService(db_session)
    ay_svc = AcademicYearService(db_session)
    ay_svc.create_year(
        date(2025, 5, 17),
        date(2026, 4, 18),
        "2025-26",
        class_fee_service=class_svc,
        village_fee_service=village_svc,
    )
    db_session.refresh(st)

    assert st.class_name == next_class_key("Nursery")
    new_year = ay_repo.list_all()[-1]
    year_row = StudentYearFeeRepository(db_session).get(st.student_id, new_year.id)
    assert year_row is not None
    assert year_row.school_fees == pytest.approx(
        class_svc.school_fees_for_class_name("LKG", new_year.id), abs=0.01
    )


def test_create_year_passes_out_class_10_students(db_session):
    from backend.core.fee_control_constants import FIXED_CLASS_KEYS, PASSED_OUT_CLASS_KEY
    from backend.services.class_fee_service import ClassFeeService
    from backend.services.village_van_fee_service import VillageVanFeeService

    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)

    ay_repo.create(date(2024, 5, 17), date(2025, 4, 18), "2024-25")
    db_session.commit()
    class_svc = ClassFeeService(db_session)
    year_2024 = ay_repo.list_all()[0]
    for class_key in FIXED_CLASS_KEYS:
        class_svc.repo.upsert_stored_amount(class_key, year_2024.id, 20000.0)
    db_session.commit()

    st = Student(
        student_id=f"PASS-{uuid.uuid4().hex[:8]}",
        full_name="Class Ten Graduate",
        class_name="10",
        section="A",
        phone="9876543211",
        guardian_name="G",
        status="active",
        school_fees=25000.0,
        van_fees=1200.0,
    )
    db_session.add(st)
    db_session.commit()

    village_svc = VillageVanFeeService(db_session)
    ay_svc = AcademicYearService(db_session)
    ay_svc.create_year(
        date(2025, 5, 17),
        date(2026, 4, 18),
        "2025-26",
        class_fee_service=class_svc,
        village_fee_service=village_svc,
    )
    db_session.refresh(st)

    assert st.class_name == PASSED_OUT_CLASS_KEY
    assert (st.status or "").lower() == "inactive"
    assert st.school_fees == pytest.approx(0.0, abs=0.01)
    assert st.van_fees == pytest.approx(0.0, abs=0.01)
    year_row = StudentYearFeeRepository(db_session).get(st.student_id, ay_repo.list_all()[-1].id)
    assert year_row is None


def test_create_year_skips_inactive_students(db_session):
    from backend.core.fee_control_constants import FIXED_CLASS_KEYS
    from backend.services.class_fee_service import ClassFeeService
    from backend.services.village_van_fee_service import VillageVanFeeService

    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)

    ay_repo.create(date(2024, 5, 17), date(2025, 4, 18), "2024-25")
    db_session.commit()
    class_svc = ClassFeeService(db_session)
    year_2024 = ay_repo.list_all()[0]
    for class_key in FIXED_CLASS_KEYS:
        class_svc.repo.upsert_stored_amount(class_key, year_2024.id, 20000.0)
    db_session.commit()

    st = Student(
        student_id=f"DROP-{uuid.uuid4().hex[:8]}",
        full_name="Left School Student",
        class_name="6",
        section="B",
        phone="9876543212",
        guardian_name="G",
        status="inactive",
        school_fees=15000.0,
        van_fees=800.0,
    )
    db_session.add(st)
    db_session.commit()
    sy = StudentYearFeeRepository(db_session)
    sy.get_or_create(
        st, ay_repo.list_all()[0].id, school_fees=15000.0, van_fees=800.0, allow_inactive=True
    )
    db_session.commit()

    village_svc = VillageVanFeeService(db_session)
    ay_svc = AcademicYearService(db_session)
    ay_svc.create_year(
        date(2025, 5, 17),
        date(2026, 4, 18),
        "2025-26",
        class_fee_service=class_svc,
        village_fee_service=village_svc,
    )
    db_session.refresh(st)

    assert st.class_name == "6"
    assert (st.status or "").lower() == "inactive"
    new_year_id = ay_repo.list_all()[-1].id
    assert sy.get(st.student_id, new_year_id) is None
    old_year_row = sy.get(st.student_id, ay_repo.list_all()[0].id)
    assert old_year_row is not None
    assert old_year_row.school_fees == pytest.approx(15000.0, abs=0.01)


def test_inactive_student_no_phantom_current_year_due_after_increment(db_session):
    """Inactive leavers must not accrue current-year due from profile fees when no year row exists."""
    from backend.services.class_fee_service import ClassFeeService
    from backend.services.fee_balance_service import FeeBalanceService
    from backend.services.village_van_fee_service import VillageVanFeeService

    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)

    y1 = ay_repo.create(date(2024, 5, 17), date(2025, 4, 18), "2024-25")
    db_session.commit()

    st = Student(
        student_id=f"PHANTOM-{uuid.uuid4().hex[:8]}",
        full_name="Inactive With Old Due",
        class_name="7",
        section="A",
        phone="9876543213",
        guardian_name="G",
        status="inactive",
        school_fees=20000.0,
        van_fees=1000.0,
    )
    db_session.add(st)
    db_session.commit()
    _set_joining_date(st, date(2024, 6, 1))
    sy = StudentYearFeeRepository(db_session)
    sy.get_or_create(st, y1.id, school_fees=10000.0, van_fees=500.0, allow_inactive=True)
    db_session.commit()

    class_svc = ClassFeeService(db_session)
    village_svc = VillageVanFeeService(db_session)
    AcademicYearService(db_session).create_year(
        date(2025, 5, 17),
        date(2026, 4, 18),
        "2025-26",
        class_fee_service=class_svc,
        village_fee_service=village_svc,
    )
    db_session.refresh(st)

    assert sy.get(st.student_id, ay_repo.list_all()[-1].id) is None
    due = FeeBalanceService(db_session).get_students_due_breakdown([st.student_id])[st.student_id]
    assert due["school_current"] == pytest.approx(0.0, abs=0.01)
    assert due["van_current"] == pytest.approx(0.0, abs=0.01)
    assert due["fee_due"] == pytest.approx(0.0, abs=0.01)
    assert due["school_pending"] == pytest.approx(10000.0, abs=0.01)
    assert due["van_pending"] == pytest.approx(500.0, abs=0.01)
