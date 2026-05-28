from __future__ import annotations

import calendar
from datetime import date

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
        )

    def list_salary_expenses(self, *, limit: int = 500):
        return self.repo.list_salary_expenses(limit=limit)

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

    def add_other_expense(
        self,
        category: str,
        amount: float,
        *,
        expense_date: date | None = None,
        description: str = "",
        notes: str = "",
    ):
        cat = (category or "").strip()
        if not cat:
            raise ValueError("Expense category is required.")
        value = float(amount or 0.0)
        if value <= 0:
            raise ValueError("Expense amount must be greater than zero.")
        return self.repo.create_other_expense(
            category=cat,
            amount=value,
            expense_date=expense_date or date.today(),
            description=description or "",
            notes=notes or "",
        )

    def list_other_expenses(self, *, limit: int = 500):
        return self.repo.list_other_expenses(limit=limit)

    def salary_total(self, month_label: str | None = None) -> float:
        return self.repo.sum_salary_expenses(month_label=month_label)

    def other_totals(self) -> dict:
        by_category = self.repo.grouped_other_expense_totals()
        return {
            "total": self.repo.sum_other_expenses(),
            "by_category": by_category,
        }
