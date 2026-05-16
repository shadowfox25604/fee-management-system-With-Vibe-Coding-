"""Cascade-delete helpers so integration tests leave the app's SQLite DB clean."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import FeePlan, Invoice, Payment, PaymentAllocation, Student


def delete_student_and_related(session: Session, student_pk: int | None) -> None:
    """Remove one student row and payments, allocations, invoices, fee plans. No-op if pk is None or missing."""
    if student_pk is None:
        return
    exists = session.scalar(select(Student.id).where(Student.id == student_pk))
    if exists is None:
        return
    pay_ids = list(session.scalars(select(Payment.id).where(Payment.student_id_fk == student_pk)).all())
    if pay_ids:
        session.execute(delete(PaymentAllocation).where(PaymentAllocation.payment_id.in_(pay_ids)))
    session.execute(delete(Payment).where(Payment.student_id_fk == student_pk))
    session.execute(delete(Invoice).where(Invoice.student_id_fk == student_pk))
    session.execute(delete(FeePlan).where(FeePlan.student_id_fk == student_pk))
    session.execute(delete(Student).where(Student.id == student_pk))
    session.commit()


def cleanup_test_students(session: Session, student_pks: list[int | None]) -> None:
    """Rollback dangling txns, then remove students newest-first (safest if tests ever relate)."""
    try:
        session.rollback()
    except Exception:
        pass
    for pk in reversed(student_pks):
        delete_student_and_related(session, pk)
