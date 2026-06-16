import calendar
from datetime import date, datetime

from sqlalchemy import func, not_, or_, select

from backend.core.fee_due_display import pending_fees as combined_pending_fees
from backend.core.fee_heads import van_fee_head_filter, van_fee_head_name_match
from backend.core.payment_reference import allocate_unique_payment_reference
from backend.models import AcademicYear, FeeHead, Invoice, Payment, PaymentAllocation, Student
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.services.fee_balance_service import FeeBalanceService

_van_fee_head_filter = van_fee_head_filter
_van_fee_head_name_match = van_fee_head_name_match


def infer_payment_split_amounts(
    amount: float,
    discount_amount: float = 0.0,
    *,
    school_allocated: float = 0.0,
    van_allocated: float = 0.0,
) -> tuple[float, float]:
    """Derive school/van cash columns for legacy rows that only stored the total amount."""
    total = float(amount or 0.0)
    discount = float(discount_amount or 0.0)
    cash = max(0.0, total - discount)
    school_alloc = float(school_allocated or 0.0)
    van_alloc = float(van_allocated or 0.0)
    eps = 1e-6

    if van_alloc <= eps and school_alloc <= eps:
        return cash, 0.0

    school_cash_equiv = max(0.0, school_alloc - discount)
    van_cash = max(0.0, van_alloc)
    parts_sum = school_cash_equiv + van_cash
    if parts_sum <= eps:
        return cash, 0.0
    if van_cash <= eps:
        return min(cash, school_cash_equiv if school_cash_equiv > eps else cash), 0.0
    if school_cash_equiv <= eps:
        return 0.0, min(cash, van_cash)

    van_amount = min(cash, cash * (van_cash / parts_sum))
    school_amount = cash - van_amount
    return round(school_amount, 2), round(van_amount, 2)


class PaymentRepository:
    def __init__(self, session):
        self.session = session
        self._balance = FeeBalanceService(session)
        self._year_repo = AcademicYearRepository(session)

    def _invoice_year_order(self):
        return (
            func.coalesce(AcademicYear.start_date, date(1900, 1, 1)),
            Invoice.due_date,
            Invoice.id,
        )

    def _current_academic_year_id(self) -> int | None:
        y = self._year_repo.get_current()
        return y.id if y else None

    @staticmethod
    def _sort_invoices_chronologically(invoices) -> list:
        return sorted(
            invoices,
            key=lambda inv: (
                int(getattr(inv, "academic_year_id", 0) or 0),
                getattr(inv, "due_date", None) or date.min,
                int(getattr(inv, "id", 0) or 0),
            ),
        )

    def _pending_invoice_order(self, school_invoices, van_invoices) -> list:
        """All prior-year invoices (school + van), oldest first."""
        current_id = self._current_academic_year_id()
        pending: list = []
        for inv in list(school_invoices) + list(van_invoices):
            if current_id is None or int(getattr(inv, "academic_year_id", 0) or 0) != int(current_id):
                pending.append(inv)
        return self._sort_invoices_chronologically(pending)

    def _current_school_invoice_order(self, school_invoices) -> list:
        current_id = self._current_academic_year_id()
        current = [
            inv
            for inv in school_invoices
            if current_id is not None
            and int(getattr(inv, "academic_year_id", 0) or 0) == int(current_id)
        ]
        return self._sort_invoices_chronologically(current)

    def _current_van_invoice_order(self, van_invoices) -> list:
        current_id = self._current_academic_year_id()
        current = [
            inv
            for inv in van_invoices
            if current_id is not None
            and int(getattr(inv, "academic_year_id", 0) or 0) == int(current_id)
        ]
        return self._sort_invoices_chronologically(current)

    def _school_payment_invoice_order(self, school_invoices, van_invoices) -> list:
        """Pending-year invoices (school + van) first, then current-year school invoices."""
        current_id = self._current_academic_year_id()
        pending: list = []
        current_school: list = []
        for inv in school_invoices:
            if current_id is not None and int(getattr(inv, "academic_year_id", 0) or 0) == int(current_id):
                current_school.append(inv)
            else:
                pending.append(inv)
        for inv in van_invoices:
            if current_id is None or int(getattr(inv, "academic_year_id", 0) or 0) != int(current_id):
                pending.append(inv)
        return self._sort_invoices_chronologically(pending) + self._sort_invoices_chronologically(
            current_school
        )

    def _van_payment_invoice_order(self, van_invoices) -> list:
        """Pending-year van invoices first, then current-year van invoices."""
        current_id = self._current_academic_year_id()
        pending: list = []
        current: list = []
        for inv in van_invoices:
            if current_id is not None and int(getattr(inv, "academic_year_id", 0) or 0) == int(current_id):
                current.append(inv)
            else:
                pending.append(inv)
        return self._sort_invoices_chronologically(pending) + self._sort_invoices_chronologically(current)

    @staticmethod
    def _not_reverted_filter():
        return or_(Payment.is_reverted.is_(False), Payment.is_reverted.is_(None))

    def new_payment_reference(self) -> str:
        def _exists(cand: str) -> bool:
            n = self.session.scalar(select(func.count(Payment.id)).where(Payment.reference_no == cand)) or 0
            return n > 0

        return allocate_unique_payment_reference(_exists)

    def get_student_balance(self, student_id_fk):
        due = self.session.scalar(select(func.coalesce(func.sum(Invoice.amount_due), 0)).where(Invoice.student_id_fk == student_id_fk)) or 0
        paid = self.session.scalar(select(func.coalesce(func.sum(Invoice.amount_paid), 0)).where(Invoice.student_id_fk == student_id_fk)) or 0
        return float(due - paid)

    def get_students_cumulative_payment_discount(self, student_ids):
        """Sum school discounts that were actually allocated to school (non-van) invoices."""
        if not student_ids:
            return {}
        payments = self.session.execute(
            select(
                Payment.id,
                Payment.student_id_fk,
                Payment.discount_amount,
            ).where(Payment.student_id_fk.in_(student_ids), self._not_reverted_filter())
        ).all()
        if not payments:
            return {}
        payment_ids = [int(row[0]) for row in payments]
        school_alloc_rows = self.session.execute(
            select(
                PaymentAllocation.payment_id,
                func.coalesce(func.sum(PaymentAllocation.allocated_amount), 0.0),
            )
            .join(Invoice, Invoice.id == PaymentAllocation.invoice_id)
            .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
            .where(
                PaymentAllocation.payment_id.in_(payment_ids),
                not_(_van_fee_head_filter()),
            )
            .group_by(PaymentAllocation.payment_id)
        ).all()
        school_alloc_by_payment = {int(pid): float(total or 0.0) for pid, total in school_alloc_rows}
        credited: dict[str, float] = {}
        for payment_id, student_id_fk, discount_amount in payments:
            discount = float(discount_amount or 0.0)
            if discount <= 0:
                continue
            school_alloc = float(school_alloc_by_payment.get(int(payment_id), 0.0))
            if school_alloc <= 0:
                continue
            credited[str(student_id_fk)] = credited.get(str(student_id_fk), 0.0) + min(
                discount, school_alloc
            )
        return credited

    def _allocate_to_invoices(self, payment_id: int, amount: float, invoices) -> float:
        rem = float(amount or 0.0)
        for inv in invoices:
            if rem <= 0:
                break
            bal = float(inv.amount_due or 0.0) - float(inv.amount_paid or 0.0)
            if bal <= 0:
                continue
            alloc = min(rem, bal)
            inv.amount_paid += alloc
            self.session.add(
                PaymentAllocation(
                    payment_id=int(payment_id),
                    invoice_id=int(inv.id),
                    allocated_amount=float(alloc),
                )
            )
            rem -= alloc
        return rem

    def _allocate_split_payment(
        self,
        payment_id: int,
        van_amount: float,
        school_amount: float,
        discount_amount: float,
        school_invoices,
        van_invoices,
    ) -> tuple[float, float]:
        """
        Allocate a split payment across invoices.

        - Combined pending (prior-year school + prior-year van) is cleared by school
          cash + discount only, oldest invoices first.
        - Van cash clears current-year van invoices only (never pending).
        - School cash + discount then clears current-year school invoices.
        """
        eps = 1e-6
        current_id = self._current_academic_year_id()
        years = self._year_repo.list_all()
        fallback_id = int(years[-1].id) if years else None
        current_id_effective = int(current_id) if current_id is not None else fallback_id

        school_budget = float(school_amount or 0.0) + float(discount_amount or 0.0)
        van_budget = float(van_amount or 0.0)

        def _inv_year_int(inv) -> int:
            # Match fee_balance_service: NULL academic_year_id counts as current year.
            y = getattr(inv, "academic_year_id", None)
            if y is not None:
                return int(y)
            if current_id_effective is not None:
                return int(current_id_effective)
            return 0

        pending_invoices: list = []
        current_school: list = []
        current_van: list = []

        for inv in list(school_invoices):
            inv_y = _inv_year_int(inv)
            if current_id_effective is not None and inv_y == current_id_effective:
                current_school.append(inv)
            else:
                pending_invoices.append(inv)

        for inv in list(van_invoices):
            inv_y = _inv_year_int(inv)
            if current_id_effective is not None and inv_y == current_id_effective:
                current_van.append(inv)
            else:
                pending_invoices.append(inv)

        pending_invoices = self._sort_invoices_chronologically(pending_invoices)
        current_school = self._sort_invoices_chronologically(current_school)
        current_van = self._sort_invoices_chronologically(current_van)

        # Allocate all pending invoices from school budget only (combined pending bucket).
        for inv in pending_invoices:
            if school_budget <= eps:
                break
            bal = float(inv.amount_due or 0.0) - float(inv.amount_paid or 0.0)
            if bal <= eps:
                continue
            alloc = min(bal, school_budget)
            if alloc <= eps:
                continue
            inv.amount_paid += alloc
            self.session.add(
                PaymentAllocation(
                    payment_id=int(payment_id),
                    invoice_id=int(inv.id),
                    allocated_amount=float(alloc),
                )
            )
            school_budget -= float(alloc)

        # Allocate remaining school budget to current-year school; van budget to current van.
        school_budget = self._allocate_to_invoices(payment_id, school_budget, current_school)
        van_budget = self._allocate_to_invoices(payment_id, van_budget, current_van)

        # Remaining budgets should be ~0 when validation caps are correct.
        if abs(school_budget) <= eps:
            school_budget = 0.0
        if abs(van_budget) <= eps:
            van_budget = 0.0

        return float(school_budget), float(van_budget)

    def get_students_school_fee_summary(self, student_ids):
        return self._balance.get_students_school_fee_summary(student_ids)

    def get_students_van_fee_summary(self, student_ids):
        return self._balance.get_students_van_fee_summary(student_ids)

    def get_student_due_breakdown(self, student_id_fk):
        """Display/payment caps: max(tariff remaining, open invoice balance) per bucket."""
        sid = str(student_id_fk)
        return self.get_students_due_breakdown([sid]).get(
            sid, {"van_due": 0.0, "fee_due": 0.0, "total": 0.0}
        )

    def get_student_yearly_breakdown(self, student: Student) -> list[dict]:
        return self._balance.get_student_yearly_breakdown(student)

    def get_student_invoice_bucket_outstanding(self, student_id_fk):
        """Unpaid invoice totals split by van/transport fee heads vs all other heads (what split payments can clear)."""
        sid = str(student_id_fk)
        m = self.get_students_invoice_bucket_outstanding([sid])
        return m.get(sid, {"van": 0.0, "school": 0.0, "total": 0.0})

    def get_students_invoice_bucket_outstanding(self, student_ids):
        """Batch: open balance per student for transport vs school invoice buckets."""
        if not student_ids:
            return {}
        rows = self.session.execute(
            select(Invoice.student_id_fk, Invoice.amount_due, Invoice.amount_paid, FeeHead.head_name)
            .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
            .where(Invoice.student_id_fk.in_(student_ids))
        ).all()
        acc = {str(sid): {"van": 0.0, "school": 0.0} for sid in student_ids}
        for student_id_fk, amount_due, amount_paid, head_name in rows:
            sid = str(student_id_fk)
            if sid not in acc:
                continue
            bal = float(amount_due or 0.0) - float(amount_paid or 0.0)
            if bal <= 0:
                continue
            if _van_fee_head_name_match(head_name):
                acc[sid]["van"] += bal
            else:
                acc[sid]["school"] += bal
        for sid in acc:
            acc[sid]["total"] = acc[sid]["van"] + acc[sid]["school"]
        return acc

    def get_students_due_breakdown(self, student_ids):
        if not student_ids:
            return {}
        discount_by_id = self.get_students_cumulative_payment_discount(student_ids)
        return self._balance.get_students_due_breakdown(student_ids, discount_by_id)

    def _first_transport_fee_head(self):
        return self.session.scalars(select(FeeHead).where(_van_fee_head_filter()).limit(1)).first()

    def _first_school_fee_head(self):
        t = self.session.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "tuition").limit(1)).first()
        if t:
            return t
        for h in self.session.scalars(select(FeeHead).order_by(FeeHead.id)).all():
            if not _van_fee_head_name_match(h.head_name):
                return h
        return None

    def _sync_invoices_if_possible(
        self, student: Student, van_amount: float, school_amount: float, invoice_anchor_date: date
    ) -> None:
        """Create tariff invoice lines when fee heads exist (best-effort for legacy payments)."""
        van_fh = self._first_transport_fee_head()
        school_fh = self._first_school_fee_head()
        if van_fh is None and school_fh is None:
            return
        self._balance.sync_tariff_invoices_for_student(
            student,
            invoice_anchor_date,
            school_fee_head=school_fh,
            van_fee_head=van_fh,
        )

    def _ensure_split_payment_invoice_capacity(
        self, student: Student, van_amount: float, school_amount: float, invoice_anchor_date: date
    ):
        """Create per-year invoice lines so payments can clear pending (older) years before the current year."""
        van_fh = self._first_transport_fee_head()
        school_fh = self._first_school_fee_head()
        if float(van_amount or 0.0) > 1e-6 and van_fh is None:
            raise ValueError(
                "Cannot record van payments: add a fee head named Transport (or Van / Bus), then try again."
            )
        if float(school_amount or 0.0) > 1e-6 and school_fh is None:
            raise ValueError(
                "Cannot record school payments: add a Tuition fee head (or another non-transport fee head), "
                "then try again."
            )
        self._balance.sync_tariff_invoices_for_student(
            student,
            invoice_anchor_date,
            school_fee_head=school_fh,
            van_fee_head=van_fh,
        )

    def create_payment(
        self,
        student: Student,
        amount: float,
        mode: str,
        operator_name: str,
        payment_date: date | None = None,
        remark: str = "",
    ):
        d = payment_date or date.today()
        if d > date.today():
            raise ValueError("Payment date cannot be in the future")
        amt = float(amount or 0.0)
        self._sync_invoices_if_possible(student, 0.0, amt, d)
        payment = Payment(
            student_id_fk=student.student_id,
            payment_date=d,
            amount=amount,
            school_amount=amount,
            van_amount=0.0,
            mode=mode,
            reference_no=self.new_payment_reference(),
            operator_name=operator_name,
            remark=(remark or "").strip(),
            is_reverted=False,
        )
        self.session.add(payment)
        self.session.flush()
        rem = float(amount or 0.0)
        van_invoices = self.session.scalars(
            select(Invoice)
            .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
            .outerjoin(AcademicYear, AcademicYear.id == Invoice.academic_year_id)
            .where(Invoice.student_id_fk == student.student_id, _van_fee_head_filter())
            .order_by(*self._invoice_year_order())
        ).all()
        school_invoices = self.session.scalars(
            select(Invoice)
            .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
            .outerjoin(AcademicYear, AcademicYear.id == Invoice.academic_year_id)
            .where(Invoice.student_id_fk == student.student_id, not_(_van_fee_head_filter()))
            .order_by(*self._invoice_year_order())
        ).all()
        rem_s, rem_v = self._allocate_split_payment(
            payment.id, 0.0, amt, 0.0, school_invoices, van_invoices
        )
        rem = rem_s + rem_v
        self.session.commit()
        self.session.refresh(payment)
        return payment

    def validate_split_payment_inputs(
        self,
        student: Student,
        van_amount: float,
        school_amount: float,
        discount_amount: float,
        payment_date: date | None,
    ) -> tuple[float, float, float, date]:
        """Same business rules as split collection (without mutating invoices or payments)."""
        van_amount = float(van_amount or 0.0)
        school_amount = float(school_amount or 0.0)
        discount_amount = float(discount_amount or 0.0)
        d = payment_date or date.today()
        if van_amount < 0 or school_amount < 0:
            raise ValueError("Payment amounts cannot be negative")
        if d > date.today():
            raise ValueError("Payment date cannot be in the future")
        total = van_amount + school_amount
        if total <= 0:
            raise ValueError("At least one payment amount must be positive")
        if discount_amount < 0:
            raise ValueError("Discount cannot be negative")
        due = self.get_student_due_breakdown(student.student_id)
        if due["total"] <= 0:
            raise ValueError("No outstanding amount for this student")
        eps = 1e-6
        if discount_amount > school_amount + eps:
            raise ValueError("Discount cannot exceed school fee payment amount")
        pending_total = combined_pending_fees(due)
        school_current = float(due.get("school_current", due.get("fee_due", 0.0)) or 0.0)
        van_current = float(due.get("van_due", due.get("van_current", 0.0)) or 0.0)
        school_cap = float(due.get("school_payable", 0.0))
        if school_cap <= 0:
            school_cap = max(0.0, pending_total + school_current)
        if school_amount + discount_amount > school_cap + eps:
            raise ValueError("School fee payment plus discount exceeds school fees due (pending + current year)")
        van_cap = float(due.get("van_payable", 0.0))
        if van_cap <= 0:
            van_cap = max(0.0, van_current)
        if van_amount > van_cap + eps:
            raise ValueError("Van fee payment exceeds current-year van fees due")
        max_total = max(0.0, school_cap + van_current)
        if van_amount + school_amount + discount_amount > max_total + eps:
            raise ValueError("Total payment exceeds outstanding fees (pending + current year)")
        return van_amount, school_amount, discount_amount, d

    def create_split_payment(
        self,
        student: Student,
        van_amount: float,
        school_amount: float,
        mode: str,
        operator_name: str,
        discount_amount: float = 0.0,
        payment_date: date | None = None,
        remark: str = "",
    ):
        """School payments clear combined pending first; van payments clear van dues only."""
        van_amount, school_amount, discount_amount, d = self.validate_split_payment_inputs(
            student, van_amount, school_amount, discount_amount, payment_date
        )
        total = van_amount + school_amount
        payment_total = total + discount_amount
        school_allocate = school_amount + discount_amount
        self._ensure_split_payment_invoice_capacity(student, van_amount, school_allocate, d)
        payment = Payment(
            student_id_fk=student.student_id,
            payment_date=d,
            amount=payment_total,
            school_amount=school_amount,
            van_amount=van_amount,
            discount_amount=discount_amount,
            mode=mode,
            reference_no=self.new_payment_reference(),
            operator_name=operator_name,
            remark=(remark or "").strip(),
            is_reverted=False,
        )
        self.session.add(payment)
        self.session.flush()

        van_invoices = self.session.scalars(
            select(Invoice)
            .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
            .outerjoin(AcademicYear, AcademicYear.id == Invoice.academic_year_id)
            .where(Invoice.student_id_fk == student.student_id, _van_fee_head_filter())
            .order_by(*self._invoice_year_order())
        ).all()
        school_invoices = self.session.scalars(
            select(Invoice)
            .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
            .outerjoin(AcademicYear, AcademicYear.id == Invoice.academic_year_id)
            .where(Invoice.student_id_fk == student.student_id, not_(_van_fee_head_filter()))
            .order_by(*self._invoice_year_order())
        ).all()
        rem_s, rem_v = self._allocate_split_payment(
            payment.id, van_amount, school_amount, discount_amount, school_invoices, van_invoices
        )
        eps = 1e-6
        if rem_v > eps or rem_s > eps:
            self.session.rollback()
            raise ValueError("Could not allocate payment to invoices; check fee heads and invoice balances")
        self.session.commit()
        self.session.refresh(payment)
        return payment

    def _student_school_invoices(self, student_id: str) -> list[Invoice]:
        return list(
            self.session.scalars(
                select(Invoice)
                .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
                .outerjoin(AcademicYear, AcademicYear.id == Invoice.academic_year_id)
                .where(Invoice.student_id_fk == str(student_id), not_(_van_fee_head_filter()))
                .order_by(*self._invoice_year_order())
            ).all()
        )

    def _student_van_invoices(self, student_id: str) -> list[Invoice]:
        return list(
            self.session.scalars(
                select(Invoice)
                .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
                .outerjoin(AcademicYear, AcademicYear.id == Invoice.academic_year_id)
                .where(Invoice.student_id_fk == str(student_id), _van_fee_head_filter())
                .order_by(*self._invoice_year_order())
            ).all()
        )

    def _student_all_invoices(self, student_id: str) -> list[Invoice]:
        return list(
            self.session.scalars(
                select(Invoice)
                .outerjoin(AcademicYear, AcademicYear.id == Invoice.academic_year_id)
                .where(Invoice.student_id_fk == str(student_id))
                .order_by(*self._invoice_year_order())
            ).all()
        )

    def _rebuild_student_allocations(self, student_id: str) -> None:
        student_id = str(student_id)
        for inv in self._student_all_invoices(student_id):
            inv.amount_paid = 0.0

        existing_allocs = self.session.scalars(
            select(PaymentAllocation)
            .join(Payment, Payment.id == PaymentAllocation.payment_id)
            .where(Payment.student_id_fk == student_id)
        ).all()
        for alloc in existing_allocs:
            self.session.delete(alloc)
        self.session.flush()

        payments = self.session.scalars(
            select(Payment)
            .where(Payment.student_id_fk == student_id, self._not_reverted_filter())
            .order_by(Payment.payment_date.asc(), Payment.id.asc())
        ).all()

        eps = 1e-6
        school_invoices = self._student_school_invoices(student_id)
        van_invoices = self._student_van_invoices(student_id)
        for payment in payments:
            school_amount = float(getattr(payment, "school_amount", 0.0) or 0.0)
            van_amount = float(getattr(payment, "van_amount", 0.0) or 0.0)
            discount_amount = float(payment.discount_amount or 0.0)
            if school_amount > eps or van_amount > eps:
                rem_s, rem_v = self._allocate_split_payment(
                    payment.id,
                    van_amount,
                    school_amount,
                    discount_amount,
                    school_invoices,
                    van_invoices,
                )
            else:
                rem_s, rem_v = self._allocate_split_payment(
                    payment.id,
                    0.0,
                    float(payment.amount or 0.0),
                    0.0,
                    school_invoices,
                    van_invoices,
                )
            rem_total = rem_s + rem_v
            if rem_total > eps:
                self._allocate_to_invoices(payment.id, rem_total, self._student_all_invoices(student_id))

    def undo_payment(self, reference_no: str) -> Payment:
        ref = (reference_no or "").strip()
        if not ref:
            raise ValueError("Payment reference is required.")
        payment = self.session.scalars(
            select(Payment).where(Payment.reference_no == ref).limit(1)
        ).first()
        if payment is None:
            raise ValueError("Payment not found.")
        if bool(getattr(payment, "is_reverted", False)):
            raise ValueError("This payment is already reverted.")

        payment.is_reverted = True
        payment.reverted_at = datetime.now()
        self._rebuild_student_allocations(str(payment.student_id_fk))
        self.session.commit()
        self.session.refresh(payment)
        return payment

    @staticmethod
    def _coerce_payment_date(value) -> date | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                return None
        return None

    def daily_cash_collected_for_month(self, year: int, month: int) -> dict:
        """Per-day chart data: live collections and reversals both keyed to payment date."""
        last_day = calendar.monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, last_day)
        cash = Payment.amount - Payment.discount_amount
        live_filter = self._not_reverted_filter()
        collected_rows = self.session.execute(
            select(Payment.payment_date, func.sum(cash))
            .where(
                Payment.payment_date >= start,
                Payment.payment_date <= end,
                live_filter,
            )
            .group_by(Payment.payment_date)
        ).all()
        reverted_rows = self.session.execute(
            select(Payment.payment_date, func.sum(cash))
            .where(
                Payment.is_reverted.is_(True),
                Payment.payment_date >= start,
                Payment.payment_date <= end,
            )
            .group_by(Payment.payment_date)
        ).all()
        collected_by_day: dict[int, float] = {}
        reverted_by_day: dict[int, float] = {}
        for pd, total in collected_rows:
            coerced = self._coerce_payment_date(pd)
            if coerced is not None:
                collected_by_day[int(coerced.day)] = float(total or 0.0)
        for rd, total in reverted_rows:
            coerced = self._coerce_payment_date(rd)
            if coerced is not None:
                reverted_by_day[int(coerced.day)] = float(total or 0.0)
        amounts = [collected_by_day.get(day, 0.0) for day in range(1, last_day + 1)]
        reverted_amounts = [reverted_by_day.get(day, 0.0) for day in range(1, last_day + 1)]
        month_label = date(year, month, 1).strftime("%B %Y")
        return {
            "year": year,
            "month": month,
            "days_in_month": last_day,
            "amounts": amounts,
            "reverted_amounts": reverted_amounts,
            "month_label": month_label,
        }

    def dashboard_period_stats(self, week_start: date, today: date) -> dict:
        """Aggregated payment metrics for the dashboard week tile."""
        cash_collected = Payment.amount - Payment.discount_amount
        live_filter = self._not_reverted_filter()
        collected_week = float(
            self.session.scalar(
                select(func.coalesce(func.sum(cash_collected), 0.0)).where(
                    Payment.payment_date >= week_start,
                    Payment.payment_date <= today,
                    live_filter,
                )
            )
            or 0.0
        )
        payments_week = int(
            self.session.scalar(
                select(func.count())
                .select_from(Payment)
                .where(
                    Payment.payment_date >= week_start,
                    Payment.payment_date <= today,
                    live_filter,
                )
            )
            or 0
        )
        payments_today = int(
            self.session.scalar(
                select(func.count())
                .select_from(Payment)
                .where(Payment.payment_date == today, live_filter)
            )
            or 0
        )
        return {
            "collected_week": collected_week,
            "payments_week": payments_week,
            "payments_today": payments_today,
        }

    def list_recent_payments_with_students(
        self,
        limit: int = 2000,
        search: str | None = None,
        *,
        include_reverted: bool = False,
        month: tuple[int, int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        class_name: str | None = None,
        class_names: list[str] | None = None,
        academic_year_id: int | None = None,
        student_id: str | None = None,
    ):
        """Newest first: reference, student, amounts, mode, operator. Optional filters for export."""
        stmt = select(Payment, Student).join(Student, Student.student_id == Payment.student_id_fk)
        if not include_reverted:
            stmt = stmt.where(self._not_reverted_filter())
        if month is not None:
            year, mon = month
            start = date(int(year), int(mon), 1)
            last_day = calendar.monthrange(int(year), int(mon))[1]
            end = date(int(year), int(mon), last_day)
            stmt = stmt.where(Payment.payment_date >= start, Payment.payment_date <= end)
        else:
            if date_from is not None:
                stmt = stmt.where(Payment.payment_date >= date_from)
            if date_to is not None:
                stmt = stmt.where(Payment.payment_date <= date_to)
        if class_names:
            student_ids = self._student_ids_for_classes(class_names)
            if not student_ids:
                return []
            stmt = stmt.where(Payment.student_id_fk.in_(student_ids))
        elif class_name:
            student_ids = self._student_ids_for_class(class_name)
            if not student_ids:
                return []
            stmt = stmt.where(Payment.student_id_fk.in_(student_ids))
        if academic_year_id is not None:
            year = self._year_repo.get(int(academic_year_id))
            if year is None:
                return []
            stmt = stmt.where(
                Payment.payment_date >= year.start_date,
                Payment.payment_date <= year.end_date,
            )
        if student_id is not None and str(student_id).strip():
            stmt = stmt.where(Payment.student_id_fk == str(student_id).strip())
        needle = (search or "").strip()
        if needle:
            pat = f"%{needle.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Payment.reference_no).like(pat),
                    func.lower(Student.student_id).like(pat),
                    func.lower(Student.full_name).like(pat),
                )
            )
        stmt = stmt.order_by(Payment.payment_date.desc(), Payment.id.desc()).limit(limit)
        rows = self.session.execute(stmt).all()
        eps = 1e-6
        legacy_ids = [
            int(p.id)
            for p, _s in rows
            if abs(float(getattr(p, "school_amount", 0.0) or 0.0)) <= eps
            and abs(float(getattr(p, "van_amount", 0.0) or 0.0)) <= eps
        ]
        alloc_map = self._allocation_splits_for_payments(legacy_ids)
        return [
            self._payment_history_row(p, s, alloc_map.get(int(p.id)))
            for p, s in rows
        ]

    def _allocation_splits_for_payments(
        self, payment_ids: list[int]
    ) -> dict[int, tuple[float, float]]:
        if not payment_ids:
            return {}
        school_totals: dict[int, float] = {}
        van_totals: dict[int, float] = {}
        stmt = (
            select(
                PaymentAllocation.payment_id,
                PaymentAllocation.allocated_amount,
                FeeHead.head_name,
            )
            .join(Invoice, Invoice.id == PaymentAllocation.invoice_id)
            .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
            .where(PaymentAllocation.payment_id.in_(payment_ids))
        )
        for payment_id, allocated_amount, head_name in self.session.execute(stmt).all():
            pid = int(payment_id)
            amt = float(allocated_amount or 0.0)
            if _van_fee_head_name_match(head_name or ""):
                van_totals[pid] = van_totals.get(pid, 0.0) + amt
            else:
                school_totals[pid] = school_totals.get(pid, 0.0) + amt
        return {
            pid: (school_totals.get(pid, 0.0), van_totals.get(pid, 0.0)) for pid in payment_ids
        }

    @staticmethod
    def _payment_history_row(
        p: Payment,
        s: Student,
        allocation_split: tuple[float, float] | None = None,
    ) -> dict:
        school_amount = float(getattr(p, "school_amount", 0.0) or 0.0)
        van_amount = float(getattr(p, "van_amount", 0.0) or 0.0)
        eps = 1e-6
        if school_amount <= eps and van_amount <= eps:
            school_alloc, van_alloc = allocation_split or (0.0, 0.0)
            school_amount, van_amount = infer_payment_split_amounts(
                float(p.amount or 0.0),
                float(p.discount_amount or 0.0),
                school_allocated=school_alloc,
                van_allocated=van_alloc,
            )
        return {
            "payment_date": p.payment_date,
            "reference_no": p.reference_no or "",
            "student_roll": s.student_id or "",
            "student_name": s.full_name or "",
            "class_name": s.class_name or "",
            "section": s.section or "",
            "father_name": getattr(s, "father_name", None) or "",
            "mother_name": getattr(s, "mother_name", None) or "",
            "guardian_name": getattr(s, "father_name", None) or s.guardian_name or "",
            "amount": float(p.amount or 0.0),
            "school_amount": school_amount,
            "van_amount": van_amount,
            "discount": float(p.discount_amount or 0.0),
            "mode": p.mode or "",
            "operator": p.operator_name or "",
            "remark": (getattr(p, "remark", None) or "").strip(),
            "is_reverted": bool(getattr(p, "is_reverted", False)),
            "status": "Payment reverted" if bool(getattr(p, "is_reverted", False)) else "Paid",
        }

    def backfill_legacy_payment_splits(self) -> int:
        """Persist school/van columns on payments created before split columns existed."""
        eps = 1e-6
        payments = self.session.scalars(
            select(Payment).where(
                func.abs(Payment.school_amount) <= eps,
                func.abs(Payment.van_amount) <= eps,
                Payment.amount > eps,
            )
        ).all()
        if not payments:
            return 0
        alloc_map = self._allocation_splits_for_payments([int(p.id) for p in payments])
        updated = 0
        for payment in payments:
            school_alloc, van_alloc = alloc_map.get(int(payment.id), (0.0, 0.0))
            school_amount, van_amount = infer_payment_split_amounts(
                float(payment.amount or 0.0),
                float(payment.discount_amount or 0.0),
                school_allocated=school_alloc,
                van_allocated=van_alloc,
            )
            payment.school_amount = school_amount
            payment.van_amount = van_amount
            updated += 1
        if updated:
            self.session.commit()
        return updated

    def _student_ids_for_class(self, class_key: str) -> list[str]:
        from backend.core.fee_control_constants import PASSED_OUT_CLASS_KEY, normalize_class_name
        from backend.repositories.class_fee_repository import ClassFeeRepository

        key = (class_key or "").strip()
        if not key:
            return []
        if normalize_class_name(key) == normalize_class_name(PASSED_OUT_CLASS_KEY):
            rows = self.session.scalars(
                select(Student.student_id).where(
                    func.lower(func.trim(Student.class_name))
                    == normalize_class_name(PASSED_OUT_CLASS_KEY)
                )
            ).all()
            return [str(value) for value in rows]
        return [student.student_id for student in ClassFeeRepository(self.session).students_in_fixed_class(key)]

    def _student_ids_for_classes(self, class_keys: list[str]) -> list[str]:
        ids: list[str] = []
        seen: set[str] = set()
        for key in class_keys:
            for student_id in self._student_ids_for_class(key):
                if student_id not in seen:
                    seen.add(student_id)
                    ids.append(student_id)
        return ids

    def payment_date_bounds(self) -> tuple[date | None, date | None]:
        row = self.session.execute(
            select(func.min(Payment.payment_date), func.max(Payment.payment_date))
        ).one()
        return row[0], row[1]
