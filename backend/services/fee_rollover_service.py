"""Consolidate prior balances into opening pending when a new academic year is added."""

from sqlalchemy import select

from backend.core.fee_due_display import rollover_pending_from_due
from backend.models import AcademicYear, Student
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.repositories.student_year_fee_repository import StudentYearFeeRepository
from backend.services.fee_balance_service import FeeBalanceService


class FeeRolloverService:
    def __init__(self, session):
        self.session = session
        self.year_repo = AcademicYearRepository(session)
        self.year_fee_repo = StudentYearFeeRepository(session)

    def compute_rollover_snapshot(self, new_year: AcademicYear) -> dict[str, float]:
        """Return per-student rolled pending before the new year fee rows exist.

        rolled = existing pending fees + current-year school due + current-year van due
        """
        previous = self._previous_year_for_rollover(new_year)
        if previous is None:
            return {}
        snapshot_date = previous.end_date
        balance = FeeBalanceService(self.session)
        out: dict[str, float] = {}
        for st in self.session.scalars(select(Student)).all():
            due = balance.get_students_due_breakdown(
                [st.student_id], as_of=snapshot_date
            ).get(st.student_id)
            if not due:
                continue
            rolled = rollover_pending_from_due(due)
            if rolled > 1e-6:
                out[str(st.student_id)] = round(rolled, 2)
        return out

    def apply_opening_pending(self, new_year: AcademicYear, rolled_by_student: dict[str, float]) -> int:
        if not rolled_by_student:
            return 0
        updated = 0
        for student_id, rolled in rolled_by_student.items():
            row = self.year_fee_repo.get(student_id, new_year.id)
            if row is None:
                continue
            row.opening_pending_fees = float(rolled)
            self.session.add(row)
            updated += 1
        if updated:
            self.session.flush()
        return updated

    def apply_new_year_rollover(self, new_year: AcademicYear) -> int:
        """Legacy entry: snapshot and apply in one call (prefer compute + apply after provision)."""
        rolled = self.compute_rollover_snapshot(new_year)
        return self.apply_opening_pending(new_year, rolled)

    def _previous_year_for_rollover(self, new_year: AcademicYear) -> AcademicYear | None:
        candidates = [
            y
            for y in self.year_repo.list_all()
            if y.id != new_year.id and y.end_date < new_year.start_date
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda y: y.end_date)
