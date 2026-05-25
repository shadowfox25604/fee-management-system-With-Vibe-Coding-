from __future__ import annotations

from datetime import date

from backend.repositories.expense_repository import ExpenseRepository


class ExpenseService:
    def __init__(self, session):
        self.repo = ExpenseRepository(session)

    def assign_faculty_salary(
        self,
        faculty_name: str,
        monthly_salary: float,
        *,
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
            role or "",
            salary,
            working_days,
            is_active=bool(is_active),
        )

    def list_faculty_salaries(self, *, active_only: bool = False):
        return self.repo.list_faculty_salaries(active_only=active_only)

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
