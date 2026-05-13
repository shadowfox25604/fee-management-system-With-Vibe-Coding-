from datetime import date

from sqlalchemy import func, not_, or_, select

from app.models import FeeHead, Invoice, Payment, Student


def _van_fee_head_filter():
    """Fee heads that count as van / transport for paid & due columns."""
    hn = func.lower(FeeHead.head_name)
    return or_(
        hn == "transport",
        hn == "van",
        hn == "van fee",
        hn == "van fees",
        hn == "bus",
        hn == "conveyance",
    )


def _van_fee_head_name_match(head_name: str) -> bool:
    hn = (head_name or "").strip().lower()
    return hn in ("transport", "van", "van fee", "van fees", "bus", "conveyance")


class PaymentRepository:
    def __init__(self, session):
        self.session = session

    def next_receipt_no(self):
        c = self.session.scalar(select(func.count(Payment.id))) or 0
        return f"RCPT-{c+1:06d}"

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
        """School bucket: fee_paid on non-transport invoices; fee_tariff_due = max(0, school_fees - fee_paid);
        fee_due = max(0, fee_tariff_due - cumulative split-payment discounts)."""
        if not student_ids:
            return {}
        discount_by_id = self.get_students_cumulative_payment_discount(student_ids)
        van_school_by_id = {
            int(r[0]): (float(r[1] or 0.0), float(r[2] or 0.0))
            for r in self.session.execute(
                select(Student.id, Student.van_fees, Student.school_fees).where(Student.id.in_(student_ids))
            ).all()
        }
        stmt_school_paid = (
            select(
                Invoice.student_id_fk,
                func.coalesce(func.sum(Invoice.amount_paid), 0.0).label("fee_paid"),
            )
            .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
            .where(
                Invoice.student_id_fk.in_(student_ids),
                not_(_van_fee_head_filter()),
            )
            .group_by(Invoice.student_id_fk)
        )
        paid_by_id = {int(r[0]): float(r[1] or 0.0) for r in self.session.execute(stmt_school_paid).all()}
        out = {}
        for sid in student_ids:
            i = int(sid)
            van, school = van_school_by_id.get(i, (0.0, 0.0))
            total = float(van) + float(school)
            paid = float(paid_by_id.get(i, 0.0) or 0.0)
            disc = float(discount_by_id.get(i, 0.0) or 0.0)
            fee_tariff_due = max(0.0, float(school) - paid)
            fee_due = max(0.0, fee_tariff_due - disc)
            out[i] = {
                "total_fees": total,
                "fee_paid": paid,
                "fee_tariff_due": fee_tariff_due,
                "fee_due": fee_due,
            }
        return out

    def get_students_van_fee_summary(self, student_ids):
        """Van bucket: van_paid on transport/van invoices; van_due = van_fees - van_paid (UI caps at 0)."""
        if not student_ids:
            return {}
        tariff_by_id = {
            int(r[0]): float(r[1] or 0.0)
            for r in self.session.execute(
                select(Student.id, Student.van_fees).where(Student.id.in_(student_ids))
            ).all()
        }
        stmt = (
            select(
                Invoice.student_id_fk,
                func.coalesce(func.sum(Invoice.amount_paid), 0.0).label("van_paid"),
            )
            .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
            .where(
                Invoice.student_id_fk.in_(student_ids),
                _van_fee_head_filter(),
            )
            .group_by(Invoice.student_id_fk)
        )
        paid_by_id = {
            int(r[0]): float(r[1] or 0.0) for r in self.session.execute(stmt).all()
        }
        out = {}
        for sid in student_ids:
            tariff = float(tariff_by_id.get(int(sid), 0.0) or 0.0)
            paid = float(paid_by_id.get(int(sid), 0.0) or 0.0)
            out[int(sid)] = {
                "van_paid": paid,
                "van_due": tariff - paid,
            }
        return out

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
        """Per student: van_due = max(tariff, open van invoices). School: max(tariff_due, open school invoices)
        minus cumulative split-payment discounts (applied to school fees only)."""
        if not student_ids:
            return {}
        inv_map = self.get_students_invoice_bucket_outstanding(student_ids)
        fee_map = self.get_students_school_fee_summary(student_ids)
        van_map = self.get_students_van_fee_summary(student_ids)
        discount_by_id = self.get_students_cumulative_payment_discount(student_ids)
        out = {}
        for sid in student_ids:
            i = int(sid)
            inv = inv_map.get(i, {"van": 0.0, "school": 0.0})
            fee = fee_map.get(i, {"fee_due": 0.0, "fee_tariff_due": 0.0})
            van = van_map.get(i, {"van_due": 0.0})
            disc = float(discount_by_id.get(i, 0.0) or 0.0)
            v_tariff = max(0.0, float(van.get("van_due", 0.0) or 0.0))
            f_tariff_raw = max(0.0, float(fee.get("fee_tariff_due", fee.get("fee_due", 0.0)) or 0.0))
            v_due = max(v_tariff, float(inv.get("van", 0.0) or 0.0))
            f_pre = max(f_tariff_raw, float(inv.get("school", 0.0) or 0.0))
            f_due = max(0.0, f_pre - disc)
            out[i] = {"van_due": v_due, "fee_due": f_due, "total": v_due + f_due}
        return out

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
        """Add invoice lines so open balances can absorb this payment (tariff vs invoice mismatch)."""
        d0 = invoice_anchor_date
        eps = 1e-6
        inv = self.get_student_invoice_bucket_outstanding(student.id)
        van_gap = max(0.0, round(float(van_amount or 0.0) - inv["van"], 2))
        if van_gap > eps:
            fh = self._first_transport_fee_head()
            if fh is None:
                raise ValueError(
                    "Cannot record van payments: add a fee head named Transport (or Van / Bus), then try again."
                )
            self.session.add(
                Invoice(
                    student_id_fk=student.id,
                    fee_head_id=fh.id,
                    period_label=f"Collect top-up van {d0.isoformat()}",
                    due_date=d0,
                    amount_due=van_gap,
                    amount_paid=0.0,
                )
            )
            self.session.flush()
        inv = self.get_student_invoice_bucket_outstanding(student.id)
        school_gap = max(0.0, round(float(school_amount or 0.0) - inv["school"], 2))
        if school_gap > eps:
            fh = self._first_school_fee_head()
            if fh is None:
                raise ValueError(
                    "Cannot record school payments: add a Tuition fee head (or another non-transport fee head), "
                    "then try again."
                )
            self.session.add(
                Invoice(
                    student_id_fk=student.id,
                    fee_head_id=fh.id,
                    period_label=f"Collect top-up school {d0.isoformat()}",
                    due_date=d0,
                    amount_due=school_gap,
                    amount_paid=0.0,
                )
            )
        self.session.flush()

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
            receipt_no=self.next_receipt_no(),
            operator_name=operator_name,
        )
        self.session.add(payment)
        rem = amount
        invoices = self.session.scalars(select(Invoice).where(Invoice.student_id_fk == student.id).order_by(Invoice.due_date.asc())).all()
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
        van_amount = float(van_amount or 0.0)
        school_amount = float(school_amount or 0.0)
        discount_amount = float(discount_amount or 0.0)
        d = payment_date or date.today()
        if d > date.today():
            raise ValueError("Payment date cannot be in the future")
        total = van_amount + school_amount
        if total <= 0:
            raise ValueError("At least one payment amount must be positive")
        if discount_amount < 0:
            raise ValueError("Discount cannot be negative")
        due = self.get_student_due_breakdown(student.id)
        eps = 1e-6
        if discount_amount > school_amount + eps:
            raise ValueError("Discount cannot exceed school fee payment amount")
        if school_amount + discount_amount > due["fee_due"] + eps:
            raise ValueError("School fee payment plus discount exceeds school fees due")
        net_collected = total - discount_amount
        if net_collected <= eps:
            raise ValueError("Amount collected after discount must be positive")
        if van_amount > due["van_due"] + eps:
            raise ValueError("Van fee payment exceeds van fees due")
        self._ensure_split_payment_invoice_capacity(student, van_amount, school_amount, d)
        payment = Payment(
            student_id_fk=student.id,
            payment_date=d,
            amount=net_collected,
            discount_amount=discount_amount,
            mode=mode,
            receipt_no=self.next_receipt_no(),
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
            .where(Invoice.student_id_fk == student.id, _van_fee_head_filter())
            .order_by(Invoice.due_date.asc())
        ).all()
        school_invoices = self.session.scalars(
            select(Invoice)
            .join(FeeHead, FeeHead.id == Invoice.fee_head_id)
            .where(Invoice.student_id_fk == student.id, not_(_van_fee_head_filter()))
            .order_by(Invoice.due_date.asc())
        ).all()
        rem_v = _allocate(van_amount, van_invoices)
        rem_s = _allocate(school_amount, school_invoices)
        if rem_v > eps or rem_s > eps:
            self.session.rollback()
            raise ValueError("Could not allocate payment to invoices; check fee heads and invoice balances")
        self.session.commit()
        self.session.refresh(payment)
        return payment
