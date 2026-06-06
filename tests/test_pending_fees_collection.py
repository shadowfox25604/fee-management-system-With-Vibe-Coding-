"""Pending fees: combined prior-year balance and pending-first payment allocation."""

import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import func, select

from backend.models import FeeHead, Invoice, Student, entities  # noqa: F401
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.repositories.payment_repository import PaymentRepository
from backend.repositories.student_year_fee_repository import StudentYearFeeRepository
from backend.services.fee_balance_service import FeeBalanceService


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


def test_pending_fees_equals_school_plus_van_from_prior_years(db_session):
    _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    for row in ay_repo.list_all():
        db_session.delete(row)
    db_session.commit()
    y_prev = ay_repo.create(date(2023, 5, 17), date(2024, 4, 18), "2023-24")
    y_cur = ay_repo.create(date(2025, 5, 17), date(2026, 4, 18), "2025-26")
    db_session.commit()

    st = Student(
        student_id=f"PF{uuid.uuid4().hex[:4].upper()}",
        full_name="Pending Sum",
        class_name="3",
        section="A",
        phone=f"7{uuid.uuid4().int % 10**9:09d}",
        guardian_name="G",
        van_fees=600.0,
        school_fees=4000.0,
    )
    db_session.add(st)
    db_session.commit()
    _set_joining_date(st, date(2023, 6, 1))
    sy = StudentYearFeeRepository(db_session)
    sy.get_or_create(st, y_prev.id, school_fees=3000.0, van_fees=500.0)
    sy.get_or_create(st, y_cur.id, school_fees=4000.0, van_fees=600.0)
    db_session.commit()

    due = FeeBalanceService(db_session).get_students_due_breakdown([st.student_id])[st.student_id]
    assert due["pending_fees"] == pytest.approx(
        due["school_pending"] + due["van_pending"], abs=0.01
    )
    assert due["pending_fees"] == pytest.approx(3500.0, abs=0.01)


def test_school_payment_debits_combined_pending_before_current_year(db_session):
    _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    for row in ay_repo.list_all():
        db_session.delete(row)
    db_session.commit()
    y_prev = ay_repo.create(date(2023, 5, 17), date(2024, 4, 18), "2023-24")
    y_cur = ay_repo.create(date(2025, 5, 17), date(2026, 4, 18), "2025-26")
    db_session.commit()

    st = Student(
        student_id=f"PS{uuid.uuid4().hex[:4].upper()}",
        full_name="School Pending First",
        class_name="4",
        section="B",
        phone=f"6{uuid.uuid4().int % 10**9:09d}",
        guardian_name="G",
        van_fees=1000.0,
        school_fees=5000.0,
    )
    db_session.add(st)
    db_session.commit()
    _set_joining_date(st, date(2023, 6, 1))
    sy = StudentYearFeeRepository(db_session)
    sy.get_or_create(st, y_prev.id, school_fees=2000.0, van_fees=800.0)
    sy.get_or_create(st, y_cur.id, school_fees=5000.0, van_fees=1000.0)
    db_session.commit()

    balance = FeeBalanceService(db_session)
    pay_repo = PaymentRepository(db_session)
    before = balance.get_students_due_breakdown([st.student_id])[st.student_id]
    assert before["pending_fees"] == pytest.approx(2800.0, abs=0.01)

    pay_repo.create_split_payment(st, 0.0, 2800.0, "cash", "test", 0.0, date(2025, 6, 1))
    after = balance.get_students_due_breakdown([st.student_id])[st.student_id]
    assert after["pending_fees"] == pytest.approx(0.0, abs=0.01)
    assert after["fee_due"] == pytest.approx(5000.0, abs=0.01)
    assert after["van_due"] == pytest.approx(1000.0, abs=0.01)


def test_van_payment_debits_combined_pending_before_current_year(db_session):
    _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    for row in ay_repo.list_all():
        db_session.delete(row)
    db_session.commit()
    y_prev = ay_repo.create(date(2023, 5, 17), date(2024, 4, 18), "2023-24")
    y_cur = ay_repo.create(date(2025, 5, 17), date(2026, 4, 18), "2025-26")
    db_session.commit()

    st = Student(
        student_id=f"PV{uuid.uuid4().hex[:4].upper()}",
        full_name="Van Pending First",
        class_name="4",
        section="B",
        phone=f"5{uuid.uuid4().int % 10**9:09d}",
        guardian_name="G",
        van_fees=1000.0,
        school_fees=5000.0,
    )
    db_session.add(st)
    db_session.commit()
    _set_joining_date(st, date(2023, 6, 1))
    sy = StudentYearFeeRepository(db_session)
    sy.get_or_create(st, y_prev.id, school_fees=1500.0, van_fees=500.0)
    sy.get_or_create(st, y_cur.id, school_fees=5000.0, van_fees=1000.0)
    db_session.commit()

    balance = FeeBalanceService(db_session)
    pay_repo = PaymentRepository(db_session)
    before = balance.get_students_due_breakdown([st.student_id])[st.student_id]
    assert before["pending_fees"] == pytest.approx(2000.0, abs=0.01)

    pay_repo.create_split_payment(st, 2000.0, 0.0, "cash", "test", 0.0, date(2025, 6, 1))
    after = balance.get_students_due_breakdown([st.student_id])[st.student_id]
    assert after["pending_fees"] == pytest.approx(0.0, abs=0.01)
    assert after["fee_due"] == pytest.approx(5000.0, abs=0.01)
    assert after["van_due"] == pytest.approx(1000.0, abs=0.01)
