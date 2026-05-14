from app.core.fee_control_constants import (
    FIXED_VILLAGE_KEYS,
    canonical_village_for_student_village,
    normalize_village_name,
)
from app.repositories.village_van_fee_repository import VillageVanFeeRepository


class VillageVanFeeService:
    def __init__(self, session):
        self.repo = VillageVanFeeRepository(session)

    @staticmethod
    def fixed_village_keys():
        return list(FIXED_VILLAGE_KEYS)

    def display_amount_for_village(self, village_key: str) -> float:
        stored = self.repo.get_stored_amount(village_key)
        if stored is not None:
            return float(stored)
        avg = self.repo.average_van_fees_for_village(village_key)
        if avg is not None:
            return float(avg)
        return 0.0

    def apply_village_van_fee(self, village_key: str, new_amount: float) -> int:
        return self.repo.apply_village_van_fee(village_key, new_amount)

    def count_students_in_village(self, village_key: str) -> int:
        return len(self.repo.students_in_fixed_village(village_key))

    def van_fees_for_village_name(self, village: str) -> float:
        """Tariff for new students: Fee Control stored value, else village average, else default."""
        key = canonical_village_for_student_village(village)
        if key is None:
            return 0.0
        stored = self.repo.get_stored_amount(key)
        if stored is not None:
            return float(stored)
        avg = self.repo.average_van_fees_for_village(key)
        if avg is not None:
            return float(avg)
        return 0.0

    def van_fees_for_student_update(self, student, new_village: str) -> float:
        """Keep existing van_fees if village unchanged (case-insensitive); otherwise resolve from village."""
        old = getattr(student, "village", None) or ""
        if normalize_village_name(old) == normalize_village_name(new_village):
            return float(getattr(student, "van_fees", 0) or 0.0)
        return self.van_fees_for_village_name(new_village)
