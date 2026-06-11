from datetime import date

from backend.core.fee_control_constants import (
    FIXED_CLASS_KEYS,
    canonical_class_for_student_class,
    is_passed_out_class,
    normalize_class_name,
)
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.repositories.class_fee_repository import ClassFeeRepository


class ClassFeeService:
    def __init__(self, session):
        self.session = session
        self.repo = ClassFeeRepository(session)
        self._year_repo = AcademicYearRepository(session)

    @staticmethod
    def fixed_class_keys():
        return list(FIXED_CLASS_KEYS)

    def resolve_academic_year_id(self, academic_year_id: int | None = None) -> int:
        if academic_year_id is not None:
            year = self._year_repo.get(int(academic_year_id))
            if year is None:
                raise ValueError("Academic year not found.")
            return int(year.id)
        current = self._year_repo.get_current()
        if current is None:
            current = self._year_repo.ensure_bootstrap_year()
        return int(current.id)

    def is_year_tariff_editable(self, academic_year_id: int, as_of: date | None = None) -> bool:
        year = self._year_repo.get(int(academic_year_id))
        if year is None:
            return False
        return year.end_date >= (as_of or date.today())

    def list_years_for_fee_control(self):
        return self._year_repo.list_all()

    def display_amount_for_class(self, class_key: str, academic_year_id: int | None = None) -> float:
        year_id = self.resolve_academic_year_id(academic_year_id)
        stored = self.repo.get_stored_amount(class_key, year_id)
        if stored is not None:
            return float(stored)
        avg = self.repo.average_school_fees_for_class(class_key)
        if avg is not None:
            return float(avg)
        return 20000.0

    def apply_class_school_fee(
        self, class_key: str, new_amount: float, academic_year_id: int | None = None
    ) -> int:
        year_id = self.resolve_academic_year_id(academic_year_id)
        if not self.is_year_tariff_editable(year_id):
            raise ValueError("Cannot edit class fees for an academic year that has ended.")
        return self.repo.apply_class_school_fee(class_key, new_amount, year_id)

    def count_students_in_class(self, class_key: str) -> int:
        return len(self.repo.students_in_fixed_class(class_key))

    def copy_tariffs_to_new_year(self, new_year_id: int) -> int:
        year = self._year_repo.get(int(new_year_id))
        if year is None:
            raise ValueError("Academic year not found.")
        prior_years = self._year_repo.years_before(year)
        if prior_years:
            source = prior_years[-1]
            return self.repo.copy_tariffs_from_year(source.id, year.id)
        count = 0
        for class_key in FIXED_CLASS_KEYS:
            amount = self.repo.average_school_fees_for_class(class_key) or 20000.0
            self.repo.upsert_stored_amount(class_key, year.id, float(amount))
            count += 1
        self.session.flush()
        return count

    def school_fees_for_class_name(
        self, class_name: str, academic_year_id: int | None = None
    ) -> float:
        """Tariff for a class: stored value for the year, else class average, else default."""
        if is_passed_out_class(class_name):
            return 0.0
        key = canonical_class_for_student_class(class_name)
        if key is None:
            return 20000.0
        year_id = self.resolve_academic_year_id(academic_year_id)
        stored = self.repo.get_stored_amount(key, year_id)
        if stored is not None:
            return float(stored)
        avg = self.repo.average_school_fees_for_class(key)
        if avg is not None:
            return float(avg)
        return 20000.0

    def school_fees_for_student_update(self, student, new_class_name: str) -> float:
        """Keep existing school_fees if class unchanged (case-insensitive); otherwise resolve from class."""
        if normalize_class_name(getattr(student, "class_name", None)) == normalize_class_name(new_class_name):
            return float(getattr(student, "school_fees", 0) or 0.0)
        return self.school_fees_for_class_name(new_class_name)
