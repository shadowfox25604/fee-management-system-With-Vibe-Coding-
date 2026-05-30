import uuid
from datetime import date, datetime

from sqlalchemy import func, select

from backend.core.report_fee_constants import (
    FEE_FILTER_CURRENT_YEAR,
    FEE_FILTER_PAID,
    FEE_FILTER_PENDING_DUE,
    has_current_year_fees_due,
    has_pending_fees_due,
    is_fully_paid,
)
from backend.models import FeeHead, Student
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.repositories.payment_repository import PaymentRepository
from backend.repositories.student_year_fee_repository import StudentYearFeeRepository
from backend.services.fee_balance_service import FeeBalanceService
from backend.services.report_service import ReportService


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


def _student(db_session, *, sid: str, name: str, cls: str = "5", section: str = "A"):
    st = Student(
        student_id=sid,
        full_name=name,
        class_name=cls,
        section=section,
        phone=f"9{uuid.uuid4().int % 10**9:09d}",
        guardian_name="G",
        van_fees=1000.0,
        school_fees=5000.0,
    )
    db_session.add(st)
    db_session.commit()
    return st


def test_report_fee_filters_by_class_section(db_session):
    _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    for row in ay_repo.list_all():
        db_session.delete(row)
    db_session.commit()
    y1 = ay_repo.create(date(2024, 5, 17), date(2025, 4, 18), "2024-25")
    y2 = ay_repo.create(date(2025, 5, 17), date(2026, 4, 18), "2025-26")
    db_session.commit()

    pending_st = _student(db_session, sid=f"RP{uuid.uuid4().hex[:4].upper()}", name="Pending Only")
    current_st = _student(db_session, sid=f"RC{uuid.uuid4().hex[:4].upper()}", name="Current Only")
    paid_st = _student(db_session, sid=f"RD{uuid.uuid4().hex[:4].upper()}", name="Fully Paid")
    both_st = _student(db_session, sid=f"RB{uuid.uuid4().hex[:4].upper()}", name="Both Due")
    other_section = _student(
        db_session,
        sid=f"RX{uuid.uuid4().hex[:4].upper()}",
        name="Other Section",
        section="B",
    )
    for st in (pending_st, current_st, paid_st, both_st, other_section):
        _set_joining_date(st, date(2024, 6, 1))

    sy = StudentYearFeeRepository(db_session)
    for st in (pending_st, current_st, paid_st, both_st, other_section):
        sy.get_or_create(st, y1.id, school_fees=5000.0, van_fees=1000.0)
        sy.get_or_create(st, y2.id, school_fees=5000.0, van_fees=1000.0)
    db_session.commit()

    pay_repo = PaymentRepository(db_session)
    pay_repo.create_split_payment(current_st, 1000.0, 5000.0, "cash", "test", 0.0, date(2025, 6, 1))
    pay_repo.create_split_payment(paid_st, 2000.0, 10000.0, "cash", "test", 0.0, date(2025, 6, 1))
    db_session.commit()

    balance = FeeBalanceService(db_session)
    pending_due = balance.get_students_due_breakdown([pending_st.student_id])[pending_st.student_id]
    current_due = balance.get_students_due_breakdown([current_st.student_id])[current_st.student_id]
    paid_due = balance.get_students_due_breakdown([paid_st.student_id])[paid_st.student_id]
    both_due = balance.get_students_due_breakdown([both_st.student_id])[both_st.student_id]

    assert has_pending_fees_due(pending_due)
    assert not has_current_year_fees_due(pending_due)
    assert has_current_year_fees_due(current_due)
    assert not has_pending_fees_due(current_due)
    assert is_fully_paid(paid_due)
    assert has_pending_fees_due(both_due)

    svc = ReportService(db_session)
    pending_rows = svc.get_fee_report_rows(
        FEE_FILTER_PENDING_DUE, class_name="5", section="A"
    )
    pending_ids = {r.student_id for r in pending_rows}
    assert pending_st.student_id in pending_ids
    assert both_st.student_id in pending_ids
    assert current_st.student_id not in pending_ids
    assert other_section.student_id not in pending_ids

    current_rows = svc.get_fee_report_rows(
        FEE_FILTER_CURRENT_YEAR, class_name="5", section="A"
    )
    current_ids = {r.student_id for r in current_rows}
    assert current_st.student_id in current_ids
    assert pending_st.student_id not in current_ids
    assert both_st.student_id not in current_ids
    assert paid_st.student_id not in current_ids

    paid_rows = svc.get_fee_report_rows(FEE_FILTER_PAID, class_name="5", section="A")
    assert paid_st.student_id in {r.student_id for r in paid_rows}
    assert pending_st.student_id not in {r.student_id for r in paid_rows}


def test_report_loads_all_students_without_filters(db_session):
    _student(db_session, sid=f"RA{uuid.uuid4().hex[:4].upper()}", name="Alpha", cls="3", section="A")
    _student(db_session, sid=f"RB{uuid.uuid4().hex[:4].upper()}", name="Beta", cls="4", section="B")
    rows = ReportService(db_session).get_fee_report_rows()
    assert len(rows) >= 2
    assert {r.full_name for r in rows} >= {"Alpha", "Beta"}
