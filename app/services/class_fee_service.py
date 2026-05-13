from app.core.fee_control_constants import (
    FIXED_CLASS_KEYS,
    canonical_class_for_student_class,
    normalize_class_name,
)
from app.repositories.class_fee_repository import ClassFeeRepository


class ClassFeeService:
    def __init__(self, session):
        self.repo = ClassFeeRepository(session)

    @staticmethod
    def fixed_class_keys():
        return list(FIXED_CLASS_KEYS)

    def display_amount_for_class(self, class_key: str) -> float:
        stored = self.repo.get_stored_amount(class_key)
        if stored is not None:
            return float(stored)
        avg = self.repo.average_school_fees_for_class(class_key)
        if avg is not None:
            return float(avg)
        return 20000.0

    def apply_class_school_fee(self, class_key: str, new_amount: float) -> int:
        return self.repo.apply_class_school_fee(class_key, new_amount)

    def count_students_in_class(self, class_key: str) -> int:
        return len(self.repo.students_in_fixed_class(class_key))

    def school_fees_for_class_name(self, class_name: str) -> float:
        """Tariff for new students: Fee Control stored value, else class average, else default."""
        key = canonical_class_for_student_class(class_name)
        if key is None:
            return 20000.0
        stored = self.repo.get_stored_amount(key)
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
