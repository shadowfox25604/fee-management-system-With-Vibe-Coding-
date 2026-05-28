"""Cascade-delete helpers so tests never leave rows in the production database."""

from __future__ import annotations

import re

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from backend.models import FeePlan, Invoice, Payment, PaymentAllocation, Student, StudentAcademicYearFee

# Roll numbers created by tests/test_core.py and tests/test_academic_years.py
_TEST_ROLL_PREFIXES = (
    "TST",
    "OWN",
    "VAN",
    "SP",
    "SD",
    "Z0",
    "PD",
    "PF",
    "DD",
    "CF",
    "VF",
    "DC",
    "PS",
    "AY",
    "TP",
)

_TEST_FULL_NAMES = frozenset(
    {
        "Test User",
        "Own Transport Test",
        "Van Transport Test",
        "Split Pay Test",
        "Discount Pay Test",
        "Zero Net Discount Test",
        "Payment Date Test",
        "Future Date Test",
        "Due Merge Test",
        "Class Fee Test",
        "Village Van Fee Test",
        "Discount Cap Test",
        "Service Split Test",
        "Year Order",
        "Due Split",
        "Tariff Pending",
    }
)

_TEST_ROLL_RE = re.compile(
    r"^(" + "|".join(_TEST_ROLL_PREFIXES) + r")[A-Z0-9]{2,}$",
    re.IGNORECASE,
)


def is_test_student_roll(student_id: str | None) -> bool:
    sid = (student_id or "").strip().upper()
    if not sid:
        return False
    return bool(_TEST_ROLL_RE.match(sid))


def is_test_student_record(student: Student) -> bool:
    if (student.full_name or "").strip() in _TEST_FULL_NAMES:
        return True
    return is_test_student_roll(student.student_id)


def delete_student_and_related(session: Session, student_pk: str | None) -> None:
    """Remove one student row and payments, allocations, invoices, fee plans, year fees."""
    if student_pk is None:
        return
    exists = session.scalar(select(Student.student_id).where(Student.student_id == student_pk))
    if exists is None:
        return
    pay_ids = list(session.scalars(select(Payment.id).where(Payment.student_id_fk == student_pk)).all())
    if pay_ids:
        session.execute(delete(PaymentAllocation).where(PaymentAllocation.payment_id.in_(pay_ids)))
    session.execute(delete(Payment).where(Payment.student_id_fk == student_pk))
    session.execute(delete(Invoice).where(Invoice.student_id_fk == student_pk))
    session.execute(delete(FeePlan).where(FeePlan.student_id_fk == student_pk))
    session.execute(delete(StudentAcademicYearFee).where(StudentAcademicYearFee.student_id_fk == student_pk))
    session.execute(delete(Student).where(Student.student_id == student_pk))
    session.commit()


def cleanup_test_students(session: Session, student_pks: list[str | None]) -> None:
    """Rollback dangling txns, then remove students newest-first."""
    try:
        session.rollback()
    except Exception:
        pass
    for pk in reversed(student_pks):
        delete_student_and_related(session, pk)


def find_test_student_ids(session: Session) -> list[str]:
    rows = session.scalars(select(Student)).all()
    return [str(s.student_id) for s in rows if is_test_student_record(s)]


def remove_all_test_students(session: Session) -> int:
    """Delete every student that matches pytest roll/name patterns. Returns count removed."""
    ids = find_test_student_ids(session)
    for pk in ids:
        delete_student_and_related(session, pk)
    return len(ids)
