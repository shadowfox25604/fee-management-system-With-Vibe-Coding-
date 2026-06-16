"""Academic year rollover consolidates prior pending + current-year dues into pending fees."""

import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import func, select

from backend.models import FeeHead, Student, entities  # noqa: F401
from backend.core.fee_due_display import rollover_pending_from_due
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


def test_new_year_rollover_combines_pending_and_current_dues(db_session):
    _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)

    y_old = ay_repo.create(date(2022, 5, 17), date(2023, 4, 18), "2022-23")
    y_prev = ay_repo.create(date(2023, 5, 17), date(2024, 4, 18), "2023-24")
    y_cur = ay_repo.create(date(2024, 5, 17), date(2025, 4, 18), "2024-25")
    db_session.commit()

    st = Student(
        student_id=f"RO{uuid.uuid4().hex[:4].upper()}",
        full_name="Rollover Student",
        class_name="5",
        section="A",
        phone=f"7{uuid.uuid4().int % 10**9:09d}",
        guardian_name="G",
        van_fees=1000.0,
        school_fees=6000.0,
    )
    db_session.add(st)
    db_session.commit()
    _set_joining_date(st, date(2022, 6, 1))

    sy = StudentYearFeeRepository(db_session)
    sy.get_or_create(st, y_old.id, school_fees=0.0, van_fees=0.0)
    sy.get_or_create(st, y_prev.id, school_fees=2000.0, van_fees=500.0)
    sy.get_or_create(st, y_cur.id, school_fees=6000.0, van_fees=1000.0)
    db_session.commit()

    balance = FeeBalanceService(db_session)
    before = balance.get_students_due_breakdown(
        [st.student_id], as_of=y_cur.end_date
    )[st.student_id]
    expected_rolled = rollover_pending_from_due(before)
    assert before["pending_fees"] == pytest.approx(2500.0, abs=0.01)
    assert before["fee_due"] == pytest.approx(6000.0, abs=0.01)
    assert before["van_due"] == pytest.approx(1000.0, abs=0.01)
    assert expected_rolled == pytest.approx(9500.0, abs=0.01)

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

    new_year = ay_repo.list_all()[-1]
    new_row = sy.get(st.student_id, new_year.id)
    assert new_row is not None
    assert float(new_row.opening_pending_fees) == pytest.approx(expected_rolled, abs=0.01)

    after = balance.get_students_due_breakdown(
        [st.student_id], as_of=new_year.start_date
    )[st.student_id]
    assert after["pending_fees"] == pytest.approx(expected_rolled, abs=0.01)
    assert after["fee_due"] == pytest.approx(float(new_row.school_fees or 0), abs=0.01)
    assert after["van_due"] == pytest.approx(float(new_row.van_fees or 0), abs=0.01)
    assert after["school_current"] == pytest.approx(float(new_row.school_fees or 0), abs=0.01)
    assert after["van_current"] == pytest.approx(float(new_row.van_fees or 0), abs=0.01)


def test_rollover_pending_decreases_when_prior_balance_paid(db_session):
    _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)

    y_prev = ay_repo.create(date(2023, 5, 17), date(2024, 4, 18), "2023-24")
    y_cur = ay_repo.create(date(2024, 5, 17), date(2025, 4, 18), "2024-25")
    db_session.commit()

    st = Student(
        student_id=f"RP{uuid.uuid4().hex[:4].upper()}",
        full_name="Rollover Paydown",
        class_name="6",
        section="A",
        phone=f"6{uuid.uuid4().int % 10**9:09d}",
        guardian_name="G",
        van_fees=800.0,
        school_fees=5000.0,
    )
    db_session.add(st)
    db_session.commit()
    _set_joining_date(st, date(2023, 6, 1))

    sy = StudentYearFeeRepository(db_session)
    sy.get_or_create(st, y_prev.id, school_fees=1000.0, van_fees=200.0)
    sy.get_or_create(st, y_cur.id, school_fees=5000.0, van_fees=800.0)
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
    db_session.commit()

    balance = FeeBalanceService(db_session)
    pay_repo = PaymentRepository(db_session)
    after_roll = balance.get_students_due_breakdown([st.student_id])[st.student_id]
    assert after_roll["pending_fees"] == pytest.approx(7000.0, abs=0.01)

    pay_repo.create_split_payment(st, 0.0, 2000.0, "cash", "test", 0.0, date(2025, 6, 1))
    after_pay = balance.get_students_due_breakdown([st.student_id])[st.student_id]
    assert after_pay["pending_fees"] == pytest.approx(5000.0, abs=0.01)
    assert after_pay["fee_due"] == pytest.approx(float(sy.get(st.student_id, ay_repo.list_all()[-1].id).school_fees), abs=0.01)
