from datetime import date

from backend.core.academic_year_dates import (
    academic_year_bounds_for_start_year,
    academic_year_short_label,
    auto_label_for_range,
    default_academic_year_bounds,
    format_academic_year_range,
)
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.repositories.student_repository import StudentRepository
from backend.repositories.student_year_fee_repository import StudentYearFeeRepository
from backend.services.academic_year_errors import AcademicYearProvisionError
from backend.services.class_fee_service import ClassFeeService
from backend.services.fee_rollover_service import FeeRolloverService
from backend.services.village_van_fee_service import VillageVanFeeService


class AcademicYearService:
    def __init__(self, session):
        self.session = session
        self.repo = AcademicYearRepository(session)
        self.year_fee_repo = StudentYearFeeRepository(session)

    def list_years(self):
        return self.repo.list_all()

    def get(self, year_id: int):
        return self.repo.get(year_id)

    def get_current(self, as_of: date | None = None):
        return self.repo.get_current(as_of)

    def format_year_display(self, year) -> str:
        if year is None:
            return "—"
        return f"{year.label} ({format_academic_year_range(year.start_date, year.end_date)})"

    def format_year_short_label(self, year) -> str:
        """Compact label for filters and dropdowns, e.g. 2025-2026."""
        if year is None:
            return "—"
        label = (year.label or "").strip()
        if label and "/" not in label and "–" not in label and "-" in label:
            return label
        return academic_year_short_label(year.start_date, year.end_date)

    def next_academic_year_bounds(self) -> tuple[date, date, str]:
        years = self.repo.list_all()
        if not years:
            start, end = default_academic_year_bounds(date.today())
        else:
            next_start_year = years[-1].start_date.year + 1
            start, end = academic_year_bounds_for_start_year(next_start_year)
        label = auto_label_for_range(start, end)
        return start, end, label

    def create_next_year(
        self,
        *,
        class_fee_service: ClassFeeService | None = None,
        village_fee_service: VillageVanFeeService | None = None,
        provision_students: bool = True,
    ):
        start, end, label = self.next_academic_year_bounds()
        return self.create_year(
            start,
            end,
            label,
            class_fee_service=class_fee_service,
            village_fee_service=village_fee_service,
            provision_students=provision_students,
        )

    def create_year(
        self,
        start: date,
        end: date,
        label: str | None = None,
        *,
        class_fee_service: ClassFeeService | None = None,
        village_fee_service: VillageVanFeeService | None = None,
        provision_students: bool = True,
    ):
        year = self.repo.create(start, end, label)
        # Commit the year first so it survives app restarts even if provisioning fails.
        self.session.commit()
        self.session.refresh(year)
        if class_fee_service is not None:
            try:
                class_fee_service.copy_tariffs_to_new_year(year.id)
                self.session.commit()
            except Exception as exc:
                self.session.rollback()
                raise AcademicYearProvisionError(year, exc) from exc
        if provision_students and class_fee_service and village_fee_service:
            try:
                rollover = FeeRolloverService(self.session)
                if self._should_promote_classes(year):
                    StudentRepository(self.session).promote_all_student_classes(
                        lambda cn: class_fee_service.school_fees_for_class_name(cn, year.id)
                    )
                # Snapshot: new pending = existing pending + current school due + current van due.
                rolled_by_student = rollover.compute_rollover_snapshot(year)
                self._provision_students(year, class_fee_service, village_fee_service)
                if rolled_by_student:
                    rollover.apply_opening_pending(year, rolled_by_student)
                self.session.commit()
            except Exception as exc:
                self.session.rollback()
                raise AcademicYearProvisionError(year, exc) from exc
        return year

    def _should_promote_classes(self, new_year) -> bool:
        """Promote when adding a new forward academic year (not the first, not back-dated)."""
        years = self.repo.list_all()
        prior = [y for y in years if y.id != new_year.id]
        if not prior:
            return False
        latest_start = max(y.start_date for y in prior)
        return new_year.start_date >= latest_start

    def update_year(self, year_id: int, start: date, end: date, label: str | None = None):
        year = self.repo.get(year_id)
        if year is None:
            raise ValueError("Academic year not found.")
        self.repo.update(year, start, end, label)
        self.session.commit()
        self.session.refresh(year)
        return year

    def delete_year(self, year_id: int):
        from sqlalchemy import delete, func, select

        from backend.models import Invoice, StudentAcademicYearFee

        year = self.repo.get(year_id)
        if year is None:
            raise ValueError("Academic year not found.")
        inv_count = self.session.scalar(
            select(func.count(Invoice.id)).where(Invoice.academic_year_id == year.id)
        ) or 0
        if inv_count:
            raise ValueError(
                "Cannot delete this academic year: invoices are linked to it. "
                "Reassign or remove those invoices first."
            )
        self.session.execute(
            delete(StudentAcademicYearFee).where(StudentAcademicYearFee.academic_year_id == year.id)
        )
        self.repo.delete(year)
        self.session.commit()

    def _provision_students(self, year, class_fee_service, village_fee_service):
        def school_for_class(class_name):
            return class_fee_service.school_fees_for_class_name(class_name, year.id)

        def van_for_village(village):
            return village_fee_service.van_fees_for_village_name(village or "")

        self.year_fee_repo.provision_all_students_for_year(
            year.id, school_for_class, van_for_village
        )

    def is_year_editable(self, year, as_of: date | None = None) -> bool:
        if year is None:
            return False
        return year.end_date >= (as_of or date.today())
