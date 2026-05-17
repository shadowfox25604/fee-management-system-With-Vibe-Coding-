from backend.core.fee_control_constants import (
    FIXED_VILLAGE_KEYS,
    canonical_village_for_student_village,
    normalize_village_name,
)
from backend.repositories.village_van_fee_repository import VillageVanFeeRepository


class VillageVanFeeService:
    def __init__(self, session):
        self.repo = VillageVanFeeRepository(session)

    @staticmethod
    def fixed_village_keys():
        return list(FIXED_VILLAGE_KEYS)

    def list_village_keys_for_fee_control(self) -> list[str]:
        return self.repo.list_village_keys_for_fee_control()

    def resolve_village_key(self, village: str | None) -> str | None:
        """Match student village text to a fee-control village key (built-in or custom)."""
        k = canonical_village_for_student_village(village)
        if k is not None:
            return k
        n = normalize_village_name(village)
        if not n:
            return None
        for key in self.list_village_keys_for_fee_control():
            if normalize_village_name(key) == n:
                return key
        return None

    def register_new_village(self, village_name: str, initial_fee: float) -> str:
        """Create or overwrite a custom village tariff row. Returns the stored village key."""
        name = (village_name or "").strip()
        if not name:
            raise ValueError("Village name is required.")
        if len(name) > 80:
            raise ValueError("Village name is too long (max 80 characters).")
        fee = float(initial_fee)
        if fee < 0:
            raise ValueError("Van fee cannot be negative.")
        n = normalize_village_name(name)
        for existing in self.list_village_keys_for_fee_control():
            if normalize_village_name(existing) == n:
                raise ValueError(f"A village matching “{existing}” already exists.")
        self.repo.upsert_stored_amount(name, fee)
        self.repo.session.commit()
        return name

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

    def count_students_on_van_transport_in_village(self, village_key: str) -> int:
        """Students in the village who use school van (excludes own-transport)."""
        return sum(
            1
            for st in self.repo.students_in_fixed_village(village_key)
            if (getattr(st, "transport_mode", None) or "van") != "own"
        )

    def van_fees_for_village_name(self, village: str) -> float:
        """Tariff for new students: Fee Control stored value, else village average, else default."""
        key = self.resolve_village_key(village)
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
