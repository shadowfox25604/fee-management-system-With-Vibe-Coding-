"""Year-aware fee due calculations (pending vs current academic year)."""

from datetime import date, datetime

from sqlalchemy import func, not_, select

from backend.models import AcademicYear, FeeHead, Invoice, Student
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.core.fee_heads import van_fee_head_name_match
from backend.core.student_enrollment import student_skips_academic_year_fee_provisioning
from backend.repositories.student_year_fee_repository import StudentYearFeeRepository


def _empty_due() -> dict:
    return {
        "pending_fees": 0.0,
        "opening_pending_fees": 0.0,
        "van_pending": 0.0,
        "van_current": 0.0,
        "van_due": 0.0,
        "school_pending": 0.0,
        "school_current": 0.0,
        "fee_due": 0.0,
        "fee_tariff_due": 0.0,
        "total": 0.0,
        "current_year_label": "",
    }


class FeeBalanceService:
    def __init__(self, session):
        self.session = session
        self.year_repo = AcademicYearRepository(session)
        self.year_fee_repo = StudentYearFeeRepository(session)

    def get_current_academic_year(self) -> AcademicYear | None:
        return self.year_repo.get_current()

    @staticmethod
    def _student_joining_date(student: Student) -> date:
        created = getattr(student, "created_at", None)
        if created is None:
            return date.today()
        if isinstance(created, datetime):
            return created.date()
        if isinstance(created, date):
            return created
        return date.today()

    def _tariffs_for_enrolled_year(
        self, student: Student, yr: AcademicYear, joining_date: date
    ) -> tuple[float, float]:
        """Tariff for a year the student was enrolled in; 0 if no fee row and not joining/current year."""
        row = self.year_fee_repo.get(student.student_id, yr.id)
        if row is not None:
            return float(row.school_fees or 0.0), float(row.van_fees or 0.0)
        if student_skips_academic_year_fee_provisioning(student):
            return 0.0, 0.0
        join_year = self.year_repo.get_for_date(joining_date)
        if join_year is not None and join_year.id == yr.id:
            return float(student.school_fees or 0.0), float(student.van_fees or 0.0)
        current = self.year_repo.get_current()
        if current is not None and current.id == yr.id:
            return float(student.school_fees or 0.0), float(student.van_fees or 0.0)
        return 0.0, 0.0

    def _normalize_year_id(self, year_id, current: AcademicYear | None, fallback_year_id: int | None) -> int:
        if year_id is not None:
            return int(year_id)
        if current is not None:
            return int(current.id)
        if fallback_year_id is not None:
            return int(fallback_year_id)
        return 0

    def _paid_by_year_bucket(
        self, student_ids: list[str], current: AcademicYear | None, fallback_year_id: int | None
    ) -> dict[str, dict[int, dict[str, float]]]:
        """student_id -> year_id -> {school, van} paid sums."""
        if not student_ids:
            return {}
        rows = self.session.execute(
            select(
                Invoice.student_id_fk,
                Invoice.academic_year_id,
                Invoice.amount_paid,
                FeeHead.head_name,
            )
            .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
            .where(Invoice.student_id_fk.in_(student_ids))
        ).all()
        acc: dict[str, dict[int, dict[str, float]]] = {}
        for sid in student_ids:
            acc[str(sid)] = {}
        for student_id_fk, year_id, amount_paid, head_name in rows:
            sid = str(student_id_fk)
            yid = self._normalize_year_id(year_id, current, fallback_year_id)
            if sid not in acc:
                acc[sid] = {}
            bucket = acc[sid].setdefault(yid, {"school": 0.0, "van": 0.0})
            amt = float(amount_paid or 0.0)
            if van_fee_head_name_match(head_name):
                bucket["van"] += amt
            else:
                bucket["school"] += amt
        return acc

    def _invoice_open_by_year_bucket(
        self, student_ids: list[str], current: AcademicYear | None, fallback_year_id: int | None
    ) -> dict[str, dict[int, dict[str, float]]]:
        if not student_ids:
            return {}
        rows = self.session.execute(
            select(
                Invoice.student_id_fk,
                Invoice.academic_year_id,
                Invoice.amount_due,
                Invoice.amount_paid,
                FeeHead.head_name,
            )
            .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
            .where(Invoice.student_id_fk.in_(student_ids))
        ).all()
        acc: dict[str, dict[int, dict[str, float]]] = {}
        for sid in student_ids:
            acc[str(sid)] = {}
        for student_id_fk, year_id, amount_due, amount_paid, head_name in rows:
            sid = str(student_id_fk)
            yid = self._normalize_year_id(year_id, current, fallback_year_id)
            bal = float(amount_due or 0.0) - float(amount_paid or 0.0)
            if bal <= 0:
                continue
            bucket = acc[sid].setdefault(yid, {"school": 0.0, "van": 0.0})
            if van_fee_head_name_match(head_name):
                bucket["van"] += bal
            else:
                bucket["school"] += bal
        return acc

    def _year_maps_for_student(self, student: Student):
        self.year_repo.ensure_bootstrap_year()
        years = self.year_repo.list_all()
        current = self.year_repo.get_current()
        fallback_id = years[-1].id if years else None
        paid_map = self._paid_by_year_bucket([student.student_id], current, fallback_id).get(student.student_id, {})
        inv_map = self._invoice_open_by_year_bucket([student.student_id], current, fallback_id).get(student.student_id, {})
        return years, paid_map, inv_map

    @staticmethod
    def _bucket_year_due(
        tariff: float, paid: float, invoice_open: float
    ) -> tuple[float, float]:
        """Return (year_due, invoice_capacity_gap). gap = extra invoice amount_due needed to cover tariff debt."""
        tariff_due = max(0.0, float(tariff) - float(paid))
        year_due = max(tariff_due, float(invoice_open))
        gap = max(0.0, year_due - float(invoice_open))
        return year_due, gap

    def sync_tariff_invoices_for_student(
        self,
        student: Student,
        anchor_date: date,
        *,
        school_fee_head,
        van_fee_head,
    ) -> None:
        """Ensure each academic year has invoice lines covering tariff debt (oldest years first on payment)."""
        years, paid_map, inv_map = self._year_maps_for_student(student)
        joining_date = self._student_joining_date(student)
        eps = 1e-6
        for yr in years:
            if yr.end_date < joining_date:
                continue
            yid = yr.id
            school_tariff, van_tariff = self._tariffs_for_enrolled_year(student, yr, joining_date)
            paid_y = paid_map.get(yid, {"school": 0.0, "van": 0.0})
            inv_y = inv_map.get(yid, {"school": 0.0, "van": 0.0})
            _, school_gap = self._bucket_year_due(school_tariff, paid_y["school"], inv_y["school"])
            _, van_gap = self._bucket_year_due(van_tariff, paid_y["van"], inv_y["van"])
            if van_gap > eps and van_fee_head is not None:
                self.session.add(
                    Invoice(
                        student_id_fk=student.student_id,
                        academic_year_id=yid,
                        fee_head_id=van_fee_head.id,
                        period_label=f"Tariff sync van {yr.label} {anchor_date.isoformat()}",
                        due_date=anchor_date,
                        amount_due=round(van_gap, 2),
                        amount_paid=0.0,
                    )
                )
            if school_gap > eps and school_fee_head is not None:
                self.session.add(
                    Invoice(
                        student_id_fk=student.student_id,
                        academic_year_id=yid,
                        fee_head_id=school_fee_head.id,
                        period_label=f"Tariff sync school {yr.label} {anchor_date.isoformat()}",
                        due_date=anchor_date,
                        amount_due=round(school_gap, 2),
                        amount_paid=0.0,
                    )
                )
        self.session.flush()

    def get_students_due_breakdown(
        self,
        student_ids: list[str],
        discount_by_id: dict[str, float] | None = None,
        *,
        as_of: date | None = None,
    ) -> dict:
        if not student_ids:
            return {}
        self.year_repo.ensure_bootstrap_year()
        current = self.year_repo.get_current(as_of)
        years = self.year_repo.list_all()
        if not years:
            return {str(sid): _empty_due() for sid in student_ids}

        students = {
            str(s.student_id): s
            for s in self.session.scalars(select(Student).where(Student.student_id.in_(student_ids))).all()
        }
        fallback_id = years[-1].id if years else None
        current_id = current.id if current else fallback_id
        paid_map = self._paid_by_year_bucket(student_ids, current, fallback_id)
        inv_map = self._invoice_open_by_year_bucket(student_ids, current, fallback_id)
        current_label = current.label if current else years[-1].label

        out = {}
        for sid in student_ids:
            i = str(sid)
            st = students.get(i)
            if st is None:
                out[i] = _empty_due()
                continue
            joining_date = self._student_joining_date(st)
            van_pending = school_pending = van_current = school_current = 0.0
            for yr in years:
                if yr.end_date < joining_date:
                    continue
                yid = yr.id
                school_tariff, van_tariff = self._tariffs_for_enrolled_year(st, yr, joining_date)
                paid_y = paid_map.get(i, {}).get(yid, {"school": 0.0, "van": 0.0})
                school_year_due = max(0.0, float(school_tariff) - float(paid_y["school"]))
                van_year_due = max(0.0, float(van_tariff) - float(paid_y["van"]))
                if yid == current_id:
                    van_current = van_year_due
                    school_current = school_year_due
                else:
                    van_pending += van_year_due
                    school_pending += school_year_due

            disc = float((discount_by_id or {}).get(i, 0.0) or 0.0)
            fee_due = max(0.0, float(school_current))
            van_due = max(0.0, float(van_current))
            # Pending fees = unpaid school + van from all years before the current year.
            # After academic-year rollover this equals:
            #   old pending + old current-year school due + old current-year van due
            prior_unpaid = school_pending + van_pending
            current_row = self.year_fee_repo.get(i, current_id)
            opening = float(current_row.opening_pending_fees or 0) if current_row else 0.0
            pending_fees_total = max(0.0, prior_unpaid)
            # School payments clear combined pending first, then current-year school.
            school_payable = max(0.0, pending_fees_total + school_current - disc)
            # Prior-year van is part of combined pending; van payments apply to current-year van only.
            van_payable = max(0.0, van_current)
            total_payable = max(0.0, pending_fees_total + school_current + van_current - disc)
            out[i] = {
                "pending_fees": pending_fees_total,
                "opening_pending_fees": opening,
                "van_pending": van_pending,
                "van_current": van_current,
                "van_due": van_due,
                "school_pending": school_pending,
                "school_current": school_current,
                "fee_due": fee_due,
                "fee_tariff_due": school_current,
                "school_payable": school_payable,
                "van_payable": van_payable,
                "total": total_payable,
                "current_year_label": current_label,
            }
        return out

    def get_student_yearly_breakdown(self, student: Student) -> list[dict]:
        """Per enrolled academic year: tariffs, paid amounts, and remaining due."""
        self.year_repo.ensure_bootstrap_year()
        current = self.year_repo.get_current()
        years = self.year_repo.list_all()
        if not years:
            return []
        fallback_id = years[-1].id if years else None
        current_id = current.id if current else fallback_id
        sid = str(student.student_id)
        paid_map = self._paid_by_year_bucket([sid], current, fallback_id).get(sid, {})
        joining_date = self._student_joining_date(student)
        rows = []
        for yr in years:
            if yr.end_date < joining_date:
                continue
            yid = yr.id
            school_tariff, van_tariff = self._tariffs_for_enrolled_year(student, yr, joining_date)
            paid_y = paid_map.get(yid, {"school": 0.0, "van": 0.0})
            school_due = max(0.0, float(school_tariff) - float(paid_y["school"]))
            van_due = max(0.0, float(van_tariff) - float(paid_y["van"]))
            rows.append(
                {
                    "year_id": yid,
                    "label": yr.label or "",
                    "is_current": yid == current_id,
                    "school_tariff": school_tariff,
                    "school_paid": paid_y["school"],
                    "school_due": school_due,
                    "van_tariff": van_tariff,
                    "van_paid": paid_y["van"],
                    "van_due": van_due,
                }
            )
        return rows

    def get_students_school_fee_summary(self, student_ids: list[str]) -> dict:
        """Totals for search table: current-year tariff and all-years school paid."""
        if not student_ids:
            return {}
        current = self.year_repo.get_current()
        discount_by_id = self._discount_map(student_ids)
        years = self.year_repo.list_all()
        fallback_id = years[-1].id if years else None
        paid_map = self._paid_by_year_bucket(student_ids, current, fallback_id)
        students = {
            str(s.student_id): s
            for s in self.session.scalars(select(Student).where(Student.student_id.in_(student_ids))).all()
        }
        out = {}
        for sid in student_ids:
            i = str(sid)
            st = students.get(i)
            if st is None:
                continue
            school_tariff = float(st.school_fees or 0.0)
            van_tariff = float(st.van_fees or 0.0)
            if current:
                school_tariff, van_tariff = self.year_fee_repo.tariffs_for_student_year(st, current.id)
            fee_paid = sum(b["school"] for b in paid_map.get(i, {}).values())
            total_fees = school_tariff + van_tariff
            disc = float(discount_by_id.get(i, 0.0) or 0.0)
            fee_tariff_due = max(0.0, school_tariff - fee_paid)
            out[i] = {
                "total_fees": total_fees,
                "fee_paid": fee_paid,
                "fee_tariff_due": fee_tariff_due,
                "fee_due": max(0.0, fee_tariff_due - disc),
            }
        return out

    def get_students_van_fee_summary(self, student_ids: list[str]) -> dict:
        if not student_ids:
            return {}
        current = self.year_repo.get_current()
        years = self.year_repo.list_all()
        fallback_id = years[-1].id if years else None
        paid_map = self._paid_by_year_bucket(student_ids, current, fallback_id)
        students = {
            str(s.student_id): s
            for s in self.session.scalars(select(Student).where(Student.student_id.in_(student_ids))).all()
        }
        out = {}
        for sid in student_ids:
            i = str(sid)
            st = students.get(i)
            if st is None:
                continue
            van_tariff = float(st.van_fees or 0.0)
            if current:
                _, van_tariff = self.year_fee_repo.tariffs_for_student_year(st, current.id)
            van_paid = sum(b["van"] for b in paid_map.get(i, {}).values())
            out[i] = {"van_paid": van_paid, "van_due": van_tariff - van_paid}
        return out

    def _discount_map(self, student_ids: list[str]) -> dict[str, float]:
        from backend.models import Payment

        if not student_ids:
            return {}
        rows = self.session.execute(
            select(Payment.student_id_fk, func.coalesce(func.sum(Payment.discount_amount), 0.0))
            .where(Payment.student_id_fk.in_(student_ids))
            .group_by(Payment.student_id_fk)
        ).all()
        return {str(r[0]): float(r[1] or 0.0) for r in rows}
