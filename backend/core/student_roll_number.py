"""Structured student roll numbers: {N|O}{YYYY}{SSSS}."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import func, select

from backend.core.academic_year_dates import academic_year_start_year_for_date
from backend.models import Student
from backend.repositories.academic_year_repository import AcademicYearRepository

FORMATTED_ROLL_PATTERN = re.compile(r"^([NO])(\d{4})(\d{4})$", re.IGNORECASE)
MAX_SEQUENCE = 9999


@dataclass(frozen=True)
class RollParts:
    prefix: str
    entry_year: int
    sequence: int

    @property
    def is_old(self) -> bool:
        return self.prefix.upper() == "O"

    def compose(self) -> str:
        return compose_roll_number(
            is_old=self.is_old,
            entry_year=self.entry_year,
            sequence=self.sequence,
        )


def prefix_for_mode(*, is_old: bool) -> str:
    return "O" if is_old else "N"


def compose_roll_number(*, is_old: bool, entry_year: int, sequence: int) -> str:
    year = int(entry_year)
    seq = int(sequence)
    if year < 1000 or year > 9999:
        raise ValueError("Entry year must be a 4-digit year.")
    if seq < 1 or seq > MAX_SEQUENCE:
        raise ValueError(f"Sequence must be between 1 and {MAX_SEQUENCE}.")
    return f"{prefix_for_mode(is_old=is_old)}{year}{seq:04d}"


def parse_roll_number(student_id: str) -> RollParts | None:
    text = (student_id or "").strip().upper()
    match = FORMATTED_ROLL_PATTERN.match(text)
    if match is None:
        return None
    prefix, year_text, seq_text = match.groups()
    return RollParts(prefix=prefix.upper(), entry_year=int(year_text), sequence=int(seq_text))


def entry_year_from_session(session) -> int:
    year_repo = AcademicYearRepository(session)
    current = year_repo.get_current()
    if current is None:
        years = year_repo.list_all()
        if not years:
            raise ValueError("No current academic year is configured.")
        current = years[-1]
    return academic_year_start_year_for_date(current.start_date)


def suggest_next_sequence(session, entry_year: int) -> int:
    year = int(entry_year)
    max_seq = 0
    for student_id in session.scalars(select(Student.student_id)).all():
        parts = parse_roll_number(str(student_id or ""))
        if parts is None:
            continue
        if parts.entry_year != year:
            continue
        max_seq = max(max_seq, parts.sequence)
    return max_seq + 1 if max_seq > 0 else 1


def suggest_next_roll_number(session, *, is_old: bool) -> str:
    entry_year = entry_year_from_session(session)
    sequence = suggest_next_sequence(session, entry_year)
    return compose_roll_number(is_old=is_old, entry_year=entry_year, sequence=sequence)


def _student_id_exists(session, student_id: str, *, exclude_student_id: str | None = None) -> bool:
    sid = (student_id or "").strip()
    stmt = select(Student.student_id).where(func.lower(Student.student_id) == sid.lower())
    if exclude_student_id is not None:
        stmt = stmt.where(func.lower(Student.student_id) != exclude_student_id.lower())
    return session.scalar(stmt.limit(1)) is not None


def validate_roll_number_for_create(session, student_id: str, *, is_old: bool) -> str:
    parts = parse_roll_number(student_id)
    if parts is None:
        raise ValueError("Roll number must match format N/O + 4-digit year + 4-digit sequence (e.g. N20250001).")
    expected_prefix = prefix_for_mode(is_old=is_old)
    if parts.prefix.upper() != expected_prefix:
        mode_label = "Old" if is_old else "New"
        raise ValueError(f"Roll number must start with {expected_prefix} for a {mode_label} student.")
    entry_year = entry_year_from_session(session)
    if parts.entry_year != entry_year:
        raise ValueError(
            f"Roll number year must be {entry_year} (current academic year entry year)."
        )
    normalized = parts.compose()
    if _student_id_exists(session, normalized):
        raise ValueError("Student ID already exists.")
    return normalized


def validate_roll_number_suffix_change(old_id: str, new_id: str) -> str:
    old_parts = parse_roll_number(old_id)
    new_parts = parse_roll_number(new_id)
    if old_parts is None or new_parts is None:
        raise ValueError("Roll number must match format N/O + 4-digit year + 4-digit sequence.")
    if old_parts.prefix != new_parts.prefix or old_parts.entry_year != new_parts.entry_year:
        raise ValueError("Only the last 4 digits of the roll number may be changed.")
    if old_parts.sequence == new_parts.sequence:
        return old_parts.compose()
    return new_parts.compose()
