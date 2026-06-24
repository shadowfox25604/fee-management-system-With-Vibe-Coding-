from datetime import date

from sqlalchemy import func, or_, select

from backend.core.fee_control_constants import FIXED_VILLAGE_KEYS, normalize_village_name
from backend.models import AcademicYear, FeeHead, Invoice, Student, VillageVanFee
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.repositories.student_year_fee_repository import StudentYearFeeRepository


def _van_fee_head_filter():
    hn = func.lower(FeeHead.head_name)
    return or_(
        hn == "transport",
        hn == "van",
        hn == "van fee",
        hn == "van fees",
        hn == "bus",
        hn == "conveyance",
    )


class VillageVanFeeRepository:
    def __init__(self, session):
        self.session = session

    def _year_row(self, village_key: str, academic_year_id: int) -> VillageVanFee | None:
        return self.session.get(VillageVanFee, (village_key, int(academic_year_id)))

    def get_stored_amount(self, village_key: str, academic_year_id: int) -> float | None:
        row = self._year_row(village_key, academic_year_id)
        if row is None:
            return None
        return float(row.amount)

    def upsert_stored_amount(self, village_key: str, academic_year_id: int, amount: float) -> None:
        row = self._year_row(village_key, academic_year_id)
        if row is None:
            self.session.add(
                VillageVanFee(
                    village_key=village_key,
                    academic_year_id=int(academic_year_id),
                    amount=float(amount),
                )
            )
        else:
            row.amount = float(amount)

    def copy_tariffs_from_year(self, from_year_id: int, to_year_id: int) -> int:
        rows = self.session.scalars(
            select(VillageVanFee).where(VillageVanFee.academic_year_id == int(from_year_id))
        ).all()
        count = 0
        for row in rows:
            self.upsert_stored_amount(row.village_key, to_year_id, float(row.amount))
            count += 1
        if count == 0:
            return 0
        self.session.flush()
        return count

    def average_van_fees_for_village(self, village_key: str) -> float | None:
        n = normalize_village_name(village_key)
        rows = self.session.execute(
            select(Student.van_fees).where(
                func.lower(func.trim(Student.village)) == n,
                Student.transport_mode != "own",
            )
        ).all()
        if not rows:
            return None
        vals = [float(r[0] or 0.0) for r in rows]
        return sum(vals) / len(vals)

    def students_in_fixed_village(self, village_key: str) -> list[Student]:
        n = normalize_village_name(village_key)
        return list(
            self.session.scalars(
                select(Student).where(func.lower(func.trim(Student.village)) == n)
            ).all()
        )

    def _first_van_fee_head(self) -> FeeHead | None:
        t = self.session.scalars(
            select(FeeHead).where(func.lower(FeeHead.head_name) == "transport").limit(1)
        ).first()
        if t:
            return t
        return self.session.scalars(
            select(FeeHead).where(_van_fee_head_filter()).order_by(FeeHead.id.asc()).limit(1)
        ).first()

    def _van_invoice_filter(self, academic_year_id: int | None, *, include_untagged: bool):
        if academic_year_id is None:
            return True
        if include_untagged:
            return or_(
                Invoice.academic_year_id == int(academic_year_id),
                Invoice.academic_year_id.is_(None),
            )
        return Invoice.academic_year_id == int(academic_year_id)

    def _van_invoices_ordered(
        self,
        student_id: str,
        academic_year_id: int | None = None,
        *,
        include_untagged: bool = False,
    ) -> list[Invoice]:
        stmt = (
            select(Invoice)
            .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
            .where(Invoice.student_id_fk == student_id, _van_fee_head_filter())
            .order_by(Invoice.due_date.asc(), Invoice.id.asc())
        )
        if academic_year_id is not None:
            stmt = stmt.where(
                self._van_invoice_filter(academic_year_id, include_untagged=include_untagged)
            )
        return list(self.session.scalars(stmt).all())

    def _total_van_paid(
        self,
        student_id: str,
        academic_year_id: int | None = None,
        *,
        include_untagged: bool = False,
    ) -> float:
        invs = self._van_invoices_ordered(
            student_id, academic_year_id, include_untagged=include_untagged
        )
        return sum(float(i.amount_paid or 0.0) for i in invs)

    def _adjust_van_invoices(
        self,
        student: Student,
        old_tariff: float,
        new_tariff: float,
        academic_year_id: int | None = None,
        *,
        include_untagged: bool = False,
    ) -> None:
        eps = 1e-6
        invs = self._van_invoices_ordered(
            student.student_id, academic_year_id, include_untagged=include_untagged
        )
        total_paid = sum(float(i.amount_paid or 0.0) for i in invs)
        if new_tariff + eps < total_paid:
            raise ValueError(
                f"Student {student.student_id}: new van fee {new_tariff:.2f} is below amount already "
                f"allocated to transport/van invoices ({total_paid:.2f})."
            )

        if not invs:
            if new_tariff <= eps:
                return
            fh = self._first_van_fee_head()
            if fh is None:
                raise ValueError(
                    "No Transport (or other van) fee head found; add a Transport fee head before applying village van fees."
                )
            year_id = academic_year_id
            if year_id is None:
                current = AcademicYearRepository(self.session).get_current()
                year_id = current.id if current else None
            self.session.add(
                Invoice(
                    student_id_fk=student.student_id,
                    academic_year_id=year_id,
                    fee_head_id=fh.id,
                    period_label=f"Van tariff {date.today().isoformat()}",
                    due_date=date.today(),
                    amount_due=float(new_tariff),
                    amount_paid=0.0,
                )
            )
            self.session.flush()
            return

        old_tariff = float(old_tariff or 0.0)
        sum_due = sum(float(i.amount_due or 0.0) for i in invs)
        if old_tariff > eps:
            k = new_tariff / old_tariff
        elif sum_due > eps:
            k = new_tariff / sum_due
        else:
            k = 1.0 if new_tariff <= eps else new_tariff / max(total_paid, eps)

        for inv in invs:
            paid = float(inv.amount_paid or 0.0)
            new_d = max(paid, round(float(inv.amount_due or 0.0) * k, 2))
            inv.amount_due = new_d

        self.session.flush()

    def list_village_keys_in_database(self, academic_year_id: int | None = None) -> list[str]:
        stmt = select(VillageVanFee.village_key).order_by(VillageVanFee.village_key)
        if academic_year_id is not None:
            stmt = stmt.where(VillageVanFee.academic_year_id == int(academic_year_id))
        rows = self.session.scalars(stmt).all()
        return [str(r) for r in rows if r]

    def list_village_keys_for_fee_control(self, academic_year_id: int | None = None) -> list[str]:
        """Built-in villages first (fixed order), then any extra keys for the academic year (A–Z)."""
        fixed_set = set(FIXED_VILLAGE_KEYS)
        fixed_order = list(FIXED_VILLAGE_KEYS)
        extra = sorted(
            (k for k in self.list_village_keys_in_database(academic_year_id) if k not in fixed_set),
            key=lambda x: str(x).lower(),
        )
        return fixed_order + extra

    def apply_village_van_fee(
        self, village_key: str, new_amount: float, academic_year_id: int
    ) -> int:
        vk = (village_key or "").strip()
        if not vk:
            raise ValueError("Village name is required.")
        if len(vk) > 80:
            raise ValueError("Village name is too long (max 80 characters).")
        new_amount = float(new_amount)
        if new_amount < 0:
            raise ValueError("Van fee amount cannot be negative.")

        year = self.session.get(AcademicYear, int(academic_year_id))
        if year is None:
            raise ValueError("Academic year not found.")
        if year.end_date < date.today():
            raise ValueError("Cannot edit village van fees for an academic year that has ended.")

        current = AcademicYearRepository(self.session).get_current()
        is_current_year = current is not None and int(current.id) == int(academic_year_id)

        students = self.students_in_fixed_village(vk)
        van_students = [st for st in students if (getattr(st, "transport_mode", None) or "van") != "own"]
        for st in van_students:
            paid = self._total_van_paid(
                st.student_id,
                academic_year_id,
                include_untagged=is_current_year,
            )
            if new_amount + 1e-6 < paid:
                raise ValueError(
                    f"Student {st.student_id} ({st.full_name}): new van fee {new_amount:.2f} is below transport "
                    f"invoice payments ({paid:.2f}). Lower collected amounts or raise the village van fee."
                )

        year_fee_repo = StudentYearFeeRepository(self.session)
        for st in van_students:
            year_row = year_fee_repo.get(st.student_id, academic_year_id)
            if year_row is None:
                year_row = year_fee_repo.get_or_create(
                    st,
                    academic_year_id,
                    school_fees=float(st.school_fees or 0.0),
                    van_fees=float(st.van_fees or 0.0),
                )
            old_tariff = float(year_row.van_fees or 0.0)
            invs = self._van_invoices_ordered(
                st.student_id, academic_year_id, include_untagged=is_current_year
            )
            if is_current_year or invs:
                self._adjust_van_invoices(
                    st,
                    old_tariff,
                    new_amount,
                    academic_year_id,
                    include_untagged=is_current_year,
                )
            year_row.van_fees = new_amount
            if is_current_year:
                st.van_fees = new_amount

        self.upsert_stored_amount(vk, academic_year_id, new_amount)
        self.session.commit()
        return len(van_students)
