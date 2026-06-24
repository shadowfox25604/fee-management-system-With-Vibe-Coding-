from datetime import date

from backend.core.fee_control_constants import (
    FIXED_VILLAGE_KEYS,
    canonical_village_for_student_village,
    normalize_village_name,
)
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.repositories.village_van_fee_repository import VillageVanFeeRepository


class VillageVanFeeService:
    def __init__(self, session):
        self.session = session
        self.repo = VillageVanFeeRepository(session)
        self._year_repo = AcademicYearRepository(session)

    @staticmethod
    def fixed_village_keys():
        return list(FIXED_VILLAGE_KEYS)

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

    def list_village_keys_for_fee_control(self, academic_year_id: int | None = None) -> list[str]:
        year_id = self.resolve_academic_year_id(academic_year_id) if academic_year_id is not None else None
        if year_id is None:
            current = self._year_repo.get_current()
            year_id = int(current.id) if current else None
        return self.repo.list_village_keys_for_fee_control(year_id)

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

    def register_new_village(
        self,
        village_name: str,
        initial_fee: float,
        academic_year_id: int | None = None,
    ) -> str:
        """Create or overwrite a custom village tariff row for the academic year."""
        name = (village_name or "").strip()
        if not name:
            raise ValueError("Village name is required.")
        if len(name) > 80:
            raise ValueError("Village name is too long (max 80 characters).")
        fee = float(initial_fee)
        if fee < 0:
            raise ValueError("Van fee cannot be negative.")
        year_id = self.resolve_academic_year_id(academic_year_id)
        if not self.is_year_tariff_editable(year_id):
            raise ValueError("Cannot add villages for an academic year that has ended.")
        n = normalize_village_name(name)
        for existing in self.list_village_keys_for_fee_control(year_id):
            if normalize_village_name(existing) == n:
                raise ValueError(f"A village matching “{existing}” already exists.")
        self.repo.upsert_stored_amount(name, year_id, fee)
        self.repo.session.commit()
        return name

    def display_amount_for_village(
        self, village_key: str, academic_year_id: int | None = None
    ) -> float:
        year_id = self.resolve_academic_year_id(academic_year_id)
        stored = self.repo.get_stored_amount(village_key, year_id)
        if stored is not None:
            return float(stored)
        avg = self.repo.average_van_fees_for_village(village_key)
        if avg is not None:
            return float(avg)
        return 0.0

    def apply_village_van_fee(
        self, village_key: str, new_amount: float, academic_year_id: int | None = None
    ) -> int:
        year_id = self.resolve_academic_year_id(academic_year_id)
        if not self.is_year_tariff_editable(year_id):
            raise ValueError("Cannot edit village van fees for an academic year that has ended.")
        return self.repo.apply_village_van_fee(village_key, new_amount, year_id)

    def count_students_in_village(self, village_key: str) -> int:
        return len(self.repo.students_in_fixed_village(village_key))

    def count_students_on_van_transport_in_village(self, village_key: str) -> int:
        """Students in the village who use school van (excludes own-transport)."""
        return sum(
            1
            for st in self.repo.students_in_fixed_village(village_key)
            if (getattr(st, "transport_mode", None) or "van") != "own"
        )

    def copy_tariffs_to_new_year(self, new_year_id: int) -> int:
        year = self._year_repo.get(int(new_year_id))
        if year is None:
            raise ValueError("Academic year not found.")
        prior_years = self._year_repo.years_before(year)
        if prior_years:
            source = prior_years[-1]
            return self.repo.copy_tariffs_from_year(source.id, year.id)
        count = 0
        for village_key in FIXED_VILLAGE_KEYS:
            avg = self.repo.average_van_fees_for_village(village_key)
            if avg is not None:
                self.repo.upsert_stored_amount(village_key, year.id, float(avg))
                count += 1
        self.session.flush()
        return count

    def van_fees_for_village_name(
        self, village: str, academic_year_id: int | None = None
    ) -> float:
        """Tariff for new students: stored value for the year, else village average, else 0."""
        key = self.resolve_village_key(village)
        if key is None:
            return 0.0
        year_id = self.resolve_academic_year_id(academic_year_id)
        stored = self.repo.get_stored_amount(key, year_id)
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
