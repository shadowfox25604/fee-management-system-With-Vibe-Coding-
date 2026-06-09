from __future__ import annotations

import calendar
from datetime import date

from datetime import date
from pathlib import Path

from backend.repositories.expense_repository import ExpenseRepository


class ExpenseService:
    def __init__(self, session):
        self.repo = ExpenseRepository(session)

    @staticmethod
    def normalize_faculty_type(faculty_type: str | None) -> str:
        text = (faculty_type or "").strip().lower()
        if text in ("teaching", "teacher", "academic"):
            return "Teaching"
        if text in ("non teaching", "non-teaching", "nonteaching", "admin", "support"):
            return "Non Teaching"
        return "Teaching"

    def assign_faculty_salary(
        self,
        faculty_name: str,
        monthly_salary: float,
        *,
        faculty_type: str = "Teaching",
        role: str = "",
        default_working_days: int = 26,
        is_active: bool = True,
    ):
        name = (faculty_name or "").strip()
        if not name:
            raise ValueError("Faculty name is required.")
        salary = float(monthly_salary or 0.0)
        if salary <= 0:
            raise ValueError("Monthly salary must be greater than zero.")
        working_days = int(default_working_days or 0)
        if working_days <= 0:
            raise ValueError("Working days must be greater than zero.")
        return self.repo.upsert_faculty_salary(
            name,
            self.normalize_faculty_type(faculty_type),
            role or "",
            salary,
            working_days,
            is_active=bool(is_active),
        )

    def list_faculty_salaries(
        self,
        *,
        active_only: bool = False,
        faculty_type: str | None = None,
        search: str | None = None,
    ):
        return self.repo.list_faculty_salaries(
            active_only=active_only,
            faculty_type=self.normalize_faculty_type(faculty_type)
            if faculty_type and faculty_type.lower() != "all"
            else faculty_type,
            search=search,
        )

    def update_faculty_profile(
        self,
        faculty_id: int,
        *,
        faculty_name: str,
        faculty_type: str,
        role: str,
        monthly_salary: float,
        default_working_days: int,
        is_active: bool,
    ):
        name = (faculty_name or "").strip()
        if not name:
            raise ValueError("Faculty name is required.")
        salary = float(monthly_salary or 0.0)
        if salary <= 0:
            raise ValueError("Monthly salary must be greater than zero.")
        working_days = int(float(default_working_days or 0))
        if working_days <= 0:
            raise ValueError("Working days must be greater than zero.")
        row = self.repo.update_faculty_profile(
            int(faculty_id),
            faculty_name=name,
            faculty_type=self.normalize_faculty_type(faculty_type),
            role=(role or "").strip(),
            monthly_salary=salary,
            default_working_days=working_days,
            is_active=bool(is_active),
        )
        if row is None:
            raise ValueError("Selected faculty does not exist.")
        return row

    @staticmethod
    def calculate_salary_amount(
        monthly_salary: float,
        attendance_days: float,
        working_days: float,
    ) -> float:
        monthly = float(monthly_salary or 0.0)
        attendance = float(attendance_days or 0.0)
        days = float(working_days or 0.0)
        if monthly <= 0:
            raise ValueError("Monthly salary must be greater than zero.")
        if days <= 0:
            raise ValueError("Working days must be greater than zero.")
        if attendance < 0:
            raise ValueError("Attendance days cannot be negative.")
        if attendance > days:
            raise ValueError("Attendance days cannot be greater than working days.")
        return round((monthly * attendance) / days, 2)

    def calculate_salary_for_faculty(
        self,
        faculty_id: int,
        attendance_days: float,
        *,
        working_days: float | None = None,
    ) -> dict:
        faculty = self.repo.get_faculty_salary(int(faculty_id))
        if faculty is None:
            raise ValueError("Selected faculty does not exist.")
        days = float(working_days if working_days is not None else faculty.default_working_days)
        payable = self.calculate_salary_amount(
            float(faculty.monthly_salary),
            float(attendance_days),
            days,
        )
        return {
            "faculty": faculty,
            "attendance_days": float(attendance_days),
            "working_days": days,
            "monthly_salary": float(faculty.monthly_salary),
            "payable_amount": payable,
        }

    @staticmethod
    def _month_label(year: int, month: int) -> str:
        year_num = int(year)
        month_num = int(month)
        if month_num < 1 or month_num > 12:
            raise ValueError("Month must be between 1 and 12.")
        return f"{year_num:04d}-{month_num:02d}"

    @staticmethod
    def _normalized_marked_days(marked_days: list[int], *, days_in_month: int) -> list[int]:
        out: list[int] = []
        for raw in marked_days or []:
            try:
                day_num = int(raw)
            except (TypeError, ValueError):
                continue
            if 1 <= day_num <= int(days_in_month):
                out.append(day_num)
        return sorted(set(out))

    @staticmethod
    def _sunday_count(year: int, month: int) -> int:
        days_in_month = calendar.monthrange(int(year), int(month))[1]
        return sum(
            1
            for day_num in range(1, days_in_month + 1)
            if date(int(year), int(month), day_num).weekday() == 6
        )

    def save_faculty_attendance(
        self,
        faculty_id: int,
        *,
        year: int,
        month: int,
        marked_days: list[int],
    ) -> dict:
        faculty = self.repo.get_faculty_salary(int(faculty_id))
        if faculty is None:
            raise ValueError("Selected faculty does not exist.")
        year_num = int(year)
        month_num = int(month)
        month_text = self._month_label(year_num, month_num)
        days_in_month = calendar.monthrange(year_num, month_num)[1]
        normalized_days = self._normalized_marked_days(marked_days, days_in_month=days_in_month)
        sunday_days = self._sunday_count(year_num, month_num)
        checked_days = len(normalized_days)
        attendance_days = float(checked_days + sunday_days)
        row = self.repo.upsert_faculty_attendance(
            faculty_id=int(faculty_id),
            month_label=month_text,
            marked_days=normalized_days,
            checked_days=checked_days,
            sunday_days=sunday_days,
            attendance_days=attendance_days,
            working_days=float(days_in_month),
        )
        return {
            "faculty": faculty,
            "attendance": row,
            "marked_days": normalized_days,
            "month_label": month_text,
            "checked_days": checked_days,
            "sunday_days": sunday_days,
            "attendance_days": attendance_days,
            "working_days": float(days_in_month),
        }

    def get_saved_faculty_attendance(
        self,
        faculty_id: int,
        *,
        year: int,
        month: int,
    ) -> dict:
        faculty = self.repo.get_faculty_salary(int(faculty_id))
        if faculty is None:
            raise ValueError("Selected faculty does not exist.")
        year_num = int(year)
        month_num = int(month)
        month_text = self._month_label(year_num, month_num)
        days_in_month = calendar.monthrange(year_num, month_num)[1]
        sunday_days = self._sunday_count(year_num, month_num)
        row = self.repo.get_faculty_attendance(int(faculty_id), month_text)
        if row is None:
            return {
                "faculty": faculty,
                "attendance": None,
                "marked_days": [],
                "month_label": month_text,
                "checked_days": 0,
                "sunday_days": sunday_days,
                "attendance_days": float(sunday_days),
                "working_days": float(days_in_month),
            }
        marked_days = self.repo.parse_attendance_days(getattr(row, "marked_days_csv", ""))
        checked_days = int(getattr(row, "checked_days", len(marked_days)) or 0)
        attendance_days = float(getattr(row, "attendance_days", checked_days + sunday_days) or 0.0)
        return {
            "faculty": faculty,
            "attendance": row,
            "marked_days": marked_days,
            "month_label": month_text,
            "checked_days": checked_days,
            "sunday_days": int(getattr(row, "sunday_days", sunday_days) or sunday_days),
            "attendance_days": attendance_days,
            "working_days": float(getattr(row, "working_days", days_in_month) or days_in_month),
        }

    def record_salary_from_attendance(
        self,
        faculty_id: int,
        attendance_days: float,
        *,
        working_days: float | None = None,
        month_label: str = "",
        expense_date: date | None = None,
        notes: str = "",
        operator_name: str = "",
    ):
        calc = self.calculate_salary_for_faculty(
            faculty_id,
            attendance_days,
            working_days=working_days,
        )
        faculty = calc["faculty"]
        exp_date = expense_date or date.today()
        month_text = (month_label or "").strip() or exp_date.strftime("%Y-%m")
        description = f"Salary for {month_text}"
        return self.repo.create_salary_expense(
            person_name=str(faculty.faculty_name or ""),
            amount=float(calc["payable_amount"]),
            expense_date=exp_date,
            month_label=month_text,
            attendance_days=float(calc["attendance_days"]),
            working_days=float(calc["working_days"]),
            base_amount=float(calc["monthly_salary"]),
            description=description,
            notes=notes or "",
            operator_name=operator_name or "",
            faculty_type=str(faculty.faculty_type or ""),
        )

    def list_salary_expenses(self, *, limit: int = 500, include_reverted: bool = False):
        return self.repo.list_salary_expenses(limit=limit, include_reverted=include_reverted)

    def list_salary_history(
        self,
        limit: int = 5000,
        search: str | None = None,
        *,
        include_reverted: bool = True,
        month: tuple[int, int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        faculty_names: list[str] | None = None,
    ):
        return self.repo.list_salary_history(
            limit=limit,
            search=search,
            include_reverted=include_reverted,
            month=month,
            date_from=date_from,
            date_to=date_to,
            faculty_names=faculty_names,
        )

    def salary_expense_date_bounds(self) -> tuple[date | None, date | None]:
        return self.repo.salary_expense_date_bounds()

    def list_salary_export_faculty_names(self) -> list[str]:
        return self.repo.list_salary_export_faculty_names()

    def count_salary_export_rows(
        self,
        *,
        search: str | None = None,
        include_reverted: bool = True,
        month: tuple[int, int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        faculty_names: list[str] | None = None,
    ) -> int:
        return len(
            self.repo.list_salary_history(
                50000,
                search=search,
                include_reverted=include_reverted,
                month=month,
                date_from=date_from,
                date_to=date_to,
                faculty_names=faculty_names,
            )
        )

    def export_salary_history_excel(
        self,
        output_path: Path,
        *,
        search: str | None = None,
        include_reverted: bool = True,
        month: tuple[int, int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        faculty_names: list[str] | None = None,
    ) -> Path:
        from backend.reports.salary_history_excel_export import SalaryHistoryExcelExporter

        rows = self.repo.list_salary_history(
            50000,
            search=search,
            include_reverted=include_reverted,
            month=month,
            date_from=date_from,
            date_to=date_to,
            faculty_names=faculty_names,
        )
        SalaryHistoryExcelExporter.export(rows, Path(output_path))
        return Path(output_path)

    def undo_salary_payment(self, reference_no: str):
        return self.repo.undo_salary_expense(reference_no)

    def faculty_salary_overview(self, faculty_id: int, *, history_limit: int = 100) -> dict:
        faculty = self.repo.get_faculty_salary(int(faculty_id))
        if faculty is None:
            raise ValueError("Selected faculty does not exist.")
        history = self.repo.list_salary_expenses_for_faculty(faculty.faculty_name, limit=history_limit)
        total_paid = self.repo.sum_salary_expenses_for_faculty(faculty.faculty_name)
        return {
            "faculty": faculty,
            "history": history,
            "total_paid": float(total_paid),
        }

    def salary_total(self, month_label: str | None = None) -> float:
        return self.repo.sum_salary_expenses(month_label=month_label)

    def daily_salary_chart_for_month(self, year: int, month: int) -> dict:
        return self.repo.daily_salary_expenses_for_month(year, month)

    def dashboard_expense_pie_for_month(
        self,
        year: int,
        month: int,
        *,
        misc_expense_service,
    ) -> dict:
        """Pie-chart breakdown: salary plus each miscellaneous expense head for the month."""
        year_num = int(year)
        month_num = int(month)
        if month_num < 1 or month_num > 12:
            raise ValueError("Month must be between 1 and 12.")
        salary_total = float(self.repo.sum_salary_expenses_for_calendar_month(year_num, month_num))
        slices: list[dict] = []
        if salary_total > 1e-6:
            slices.append({"label": "Salary", "amount": round(salary_total, 2)})
        for head, amount in misc_expense_service.expenses_by_head_for_month(year_num, month_num):
            slices.append({"label": str(head), "amount": round(float(amount), 2)})
        total = round(sum(float(s["amount"]) for s in slices), 2)
        month_label = date(year_num, month_num, 1).strftime("%B %Y")
        return {
            "year": year_num,
            "month": month_num,
            "month_label": month_label,
            "total": total,
            "slices": slices,
        }

    @staticmethod
    def merge_daily_charts(*parts: dict) -> dict:
        if not parts:
            return {
                "amounts": [],
                "reverted_amounts": [],
                "month_label": "",
            }
        base = parts[0]
        day_count = len(base.get("amounts") or [])
        amounts = [0.0] * day_count
        reverted_amounts = [0.0] * day_count
        for part in parts:
            part_amounts = list(part.get("amounts") or [])
            part_reverted = list(part.get("reverted_amounts") or [])
            if len(part_amounts) > day_count:
                extra = len(part_amounts) - day_count
                amounts.extend([0.0] * extra)
                reverted_amounts.extend([0.0] * extra)
                day_count = len(part_amounts)
            while len(part_reverted) < day_count:
                part_reverted.append(0.0)
            for idx in range(day_count):
                if idx < len(part_amounts):
                    amounts[idx] += float(part_amounts[idx] or 0.0)
                if idx < len(part_reverted):
                    reverted_amounts[idx] += float(part_reverted[idx] or 0.0)
        return {
            "year": base.get("year"),
            "month": base.get("month"),
            "days_in_month": base.get("days_in_month", day_count),
            "amounts": amounts,
            "reverted_amounts": reverted_amounts,
            "month_label": base.get("month_label", ""),
        }

    def purge_faculty_by_name(self, faculty_name: str) -> dict[str, int]:
        """Delete faculty (if present), attendance, and salary history rows for this name."""
        return self.repo.purge_faculty_by_name(faculty_name)
