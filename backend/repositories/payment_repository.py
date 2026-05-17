from datetime import date

from sqlalchemy import func, not_, or_, select

from backend.core.fee_heads import van_fee_head_filter, van_fee_head_name_match
from backend.core.payment_reference import allocate_unique_payment_reference
from backend.models import AcademicYear, FeeHead, Invoice, Payment, Student
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.services.fee_balance_service import FeeBalanceService

_van_fee_head_filter = van_fee_head_filter
_van_fee_head_name_match = van_fee_head_name_match


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
        """Sum of split-payment school discounts recorded on Payment.discount_amount per student."""
        if not student_ids:
            return {}
        rows = self.session.execute(
            select(Payment.student_id_fk, func.coalesce(func.sum(Payment.discount_amount), 0.0))
            .where(Payment.student_id_fk.in_(student_ids))
            .group_by(Payment.student_id_fk)
        ).all()
        return {int(r[0]): float(r[1] or 0.0) for r in rows}

    def get_students_school_fee_summary(self, student_ids):
        return self._balance.get_students_school_fee_summary(student_ids)

    def get_students_van_fee_summary(self, student_ids):
        return self._balance.get_students_van_fee_summary(student_ids)

    def get_student_due_breakdown(self, student_id_fk):
        """Display/payment caps: max(tariff remaining, open invoice balance) per bucket."""
        sid = int(student_id_fk)
        return self.get_students_due_breakdown([sid]).get(
            sid, {"van_due": 0.0, "fee_due": 0.0, "total": 0.0}
        )

    def get_student_invoice_bucket_outstanding(self, student_id_fk):
        """Unpaid invoice totals split by van/transport fee heads vs all other heads (what split payments can clear)."""
        m = self.get_students_invoice_bucket_outstanding([int(student_id_fk)])
        return m.get(int(student_id_fk), {"van": 0.0, "school": 0.0, "total": 0.0})

    def get_students_invoice_bucket_outstanding(self, student_ids):
        """Batch: open balance per student for transport vs school invoice buckets."""
        if not student_ids:
            return {}
        rows = self.session.execute(
            select(Invoice.student_id_fk, Invoice.amount_due, Invoice.amount_paid, FeeHead.head_name)
            .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
            .where(Invoice.student_id_fk.in_(student_ids))
        ).all()
        acc = {int(sid): {"van": 0.0, "school": 0.0} for sid in student_ids}
        for student_id_fk, amount_due, amount_paid, head_name in rows:
            sid = int(student_id_fk)
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
    ):
        d = payment_date or date.today()
        if d > date.today():
            raise ValueError("Payment date cannot be in the future")
        payment = Payment(
            student_id_fk=student.id,
            payment_date=d,
            amount=amount,
            mode=mode,
            reference_no=self.new_payment_reference(),
            operator_name=operator_name,
        )
        self.session.add(payment)
        rem = amount
        invoices = self.session.scalars(
            select(Invoice)
            .outerjoin(AcademicYear, AcademicYear.id == Invoice.academic_year_id)
            .where(Invoice.student_id_fk == student.id)
            .order_by(*self._invoice_year_order())
        ).all()
        for inv in invoices:
            if rem <= 0:
                break
            bal = inv.amount_due - inv.amount_paid
            if bal <= 0:
                continue
            alloc = min(rem, bal)
            inv.amount_paid += alloc
            rem -= alloc
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
        due = self.get_student_due_breakdown(student.id)
        if due["total"] <= 0:
            raise ValueError("No outstanding amount for this student")
        eps = 1e-6
        if discount_amount > school_amount + eps:
            raise ValueError("Discount cannot exceed school fee payment amount")
        school_cap = float(
            due.get("school_payable", due.get("school_pending", 0.0) + due.get("school_current", 0.0))
        )
        if school_amount + discount_amount > school_cap + eps:
            raise ValueError("School fee payment plus discount exceeds school fees due (pending + current year)")
        van_cap = float(due.get("van_payable", due.get("van_pending", 0.0) + due.get("van_current", 0.0)))
        if van_amount > van_cap + eps:
            raise ValueError("Van fee payment exceeds van fees due (pending + current year)")
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
    ):
        """Apply school payments only to non-van invoices and van payments only to van/transport invoices (due date order)."""
        van_amount, school_amount, discount_amount, d = self.validate_split_payment_inputs(
            student, van_amount, school_amount, discount_amount, payment_date
        )
        total = van_amount + school_amount
        payment_total = total + discount_amount
        school_allocate = school_amount + discount_amount
        self._ensure_split_payment_invoice_capacity(student, van_amount, school_allocate, d)
        payment = Payment(
            student_id_fk=student.id,
            payment_date=d,
            amount=payment_total,
            discount_amount=discount_amount,
            mode=mode,
            reference_no=self.new_payment_reference(),
            operator_name=operator_name,
        )
        self.session.add(payment)

        def _allocate(amount: float, invoices):
            rem = amount
            for inv in invoices:
                if rem <= 0:
                    break
                bal = inv.amount_due - inv.amount_paid
                if bal <= 0:
                    continue
                alloc = min(rem, bal)
                inv.amount_paid += alloc
                rem -= alloc
            return rem

        van_invoices = self.session.scalars(
            select(Invoice)
            .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
            .outerjoin(AcademicYear, AcademicYear.id == Invoice.academic_year_id)
            .where(Invoice.student_id_fk == student.id, _van_fee_head_filter())
            .order_by(*self._invoice_year_order())
        ).all()
        school_invoices = self.session.scalars(
            select(Invoice)
            .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
            .outerjoin(AcademicYear, AcademicYear.id == Invoice.academic_year_id)
            .where(Invoice.student_id_fk == student.id, not_(_van_fee_head_filter()))
            .order_by(*self._invoice_year_order())
        ).all()
        rem_v = _allocate(van_amount, van_invoices)
        rem_s = _allocate(school_allocate, school_invoices)
        eps = 1e-6
        if rem_v > eps or rem_s > eps:
            self.session.rollback()
            raise ValueError("Could not allocate payment to invoices; check fee heads and invoice balances")
        self.session.commit()
        self.session.refresh(payment)
        return payment

    def list_recent_payments_with_students(self, limit: int = 2000, search: str | None = None):
        """Newest first: reference, student, amounts, mode, operator. Optional case-insensitive search substring."""
        stmt = select(Payment, Student).join(Student, Student.id == Payment.student_id_fk)
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
        out = []
        for p, s in self.session.execute(stmt).all():
            out.append(
                {
                    "payment_date": p.payment_date,
                    "reference_no": p.reference_no or "",
                    "student_roll": s.student_id or "",
                    "student_name": s.full_name or "",
                    "amount": float(p.amount or 0.0),
                    "discount": float(p.discount_amount or 0.0),
                    "mode": p.mode or "",
                    "operator": p.operator_name or "",
                }
            )
        return out
