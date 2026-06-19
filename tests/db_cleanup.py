"""Cascade-delete helpers so tests never leave rows in the production database."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Student

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
    from backend.repositories.student_repository import StudentRepository

    repo = StudentRepository(session)
    if repo.get_by_id(str(student_pk)) is None:
        return
    repo.delete_student_cascade(str(student_pk))


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
