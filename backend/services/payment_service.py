from datetime import date
from pathlib import Path

from backend.repositories.payment_repository import PaymentRepository


class PaymentService:
    def __init__(self, session):
        self.repo = PaymentRepository(session)

    def get_balance(self, student_id_fk):
        return self.repo.get_student_balance(student_id_fk)

    def get_student_due_breakdown(self, student_id_fk):
        return self.repo.get_student_due_breakdown(student_id_fk)

    def get_student_yearly_breakdown(self, student):
        return self.repo.get_student_yearly_breakdown(student)

    def get_students_due_breakdown(self, student_ids):
        return self.repo.get_students_due_breakdown(student_ids)

    def get_students_school_fee_summary(self, student_ids):
        return self.repo.get_students_school_fee_summary(student_ids)

    def get_students_van_fee_summary(self, student_ids):
        return self.repo.get_students_van_fee_summary(student_ids)

    def get_students_cumulative_payment_discount(self, student_ids):
        return self.repo.get_students_cumulative_payment_discount(student_ids)

    def collect_payment(self, student, amount, mode="cash", operator_name="admin", payment_date: date | None = None):
        if amount <= 0:
            raise ValueError("Payment amount must be positive")
        bal = self.repo.get_student_balance(student.student_id)
        if bal <= 0:
            raise ValueError("No outstanding amount for this student")
        if amount > bal:
            raise ValueError("Payment exceeds outstanding balance")
        return self.repo.create_payment(student, amount, mode, operator_name, payment_date)

    def collect_split_payment(
        self,
        student,
        van_amount=0.0,
        school_amount=0.0,
        mode="cash",
        operator_name="admin",
        discount_amount=0.0,
        payment_date: date | None = None,
    ):
        va = float(van_amount or 0.0)
        sa = float(school_amount or 0.0)
        disc = float(discount_amount or 0.0)
        if va < 0 or sa < 0:
            raise ValueError("Payment amounts cannot be negative")
        if va + sa <= 0:
            raise ValueError("At least one payment amount must be positive")
        due = self.repo.get_student_due_breakdown(student.student_id)
        if due["total"] <= 0:
            raise ValueError("No outstanding amount for this student")
        return self.repo.create_split_payment(student, va, sa, mode, operator_name, disc, payment_date)

    def list_payment_history(
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
    ):
        return self.repo.list_recent_payments_with_students(
            limit,
            search=search,
            include_reverted=include_reverted,
            month=month,
            date_from=date_from,
            date_to=date_to,
            class_name=class_name,
            class_names=class_names,
            academic_year_id=academic_year_id,
        )

    def payment_date_bounds(self) -> tuple[date | None, date | None]:
        return self.repo.payment_date_bounds()

    def count_export_rows(
        self,
        *,
        search: str | None = None,
        include_reverted: bool = True,
        month: tuple[int, int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        class_name: str | None = None,
        class_names: list[str] | None = None,
        academic_year_id: int | None = None,
    ) -> int:
        return len(
            self.repo.list_recent_payments_with_students(
                50000,
                search=search,
                include_reverted=include_reverted,
                month=month,
                date_from=date_from,
                date_to=date_to,
                class_name=class_name,
                class_names=class_names,
                academic_year_id=academic_year_id,
            )
        )

    def export_excel(
        self,
        output_path: Path,
        *,
        search: str | None = None,
        include_reverted: bool = True,
        month: tuple[int, int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        class_name: str | None = None,
        class_names: list[str] | None = None,
        academic_year_id: int | None = None,
    ) -> Path:
        from backend.reports.payment_history_excel_export import PaymentHistoryExcelExporter

        rows = self.repo.list_recent_payments_with_students(
            50000,
            search=search,
            include_reverted=include_reverted,
            month=month,
            date_from=date_from,
            date_to=date_to,
            class_name=class_name,
            class_names=class_names,
            academic_year_id=academic_year_id,
        )
        PaymentHistoryExcelExporter.export(rows, output_path)
        return output_path

    def undo_payment(self, reference_no: str):
        return self.repo.undo_payment(reference_no)

    def dashboard_period_stats(self, week_start: date, today: date) -> dict:
        return self.repo.dashboard_period_stats(week_start, today)

    def daily_cash_collected_for_month(self, year: int, month: int) -> dict:
        return self.repo.daily_cash_collected_for_month(year, month)
