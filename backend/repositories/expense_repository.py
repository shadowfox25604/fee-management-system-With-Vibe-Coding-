from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from backend.models import Expense, FacultySalary


class ExpenseRepository:
    def __init__(self, session):
        self.session = session

    def upsert_faculty_salary(
        self,
        faculty_name: str,
        role: str,
        monthly_salary: float,
        default_working_days: int = 26,
        *,
        is_active: bool = True,
    ) -> FacultySalary:
        name = faculty_name.strip()
        row = self.session.scalars(
            select(FacultySalary)
            .where(func.lower(FacultySalary.faculty_name) == name.lower())
            .limit(1)
        ).first()
        if row is None:
            row = FacultySalary(
                faculty_name=name,
                role=role.strip(),
                monthly_salary=float(monthly_salary),
                default_working_days=int(default_working_days),
                is_active=bool(is_active),
            )
            self.session.add(row)
        else:
            row.role = role.strip()
            row.monthly_salary = float(monthly_salary)
            row.default_working_days = int(default_working_days)
            row.is_active = bool(is_active)
        self.session.commit()
        self.session.refresh(row)
        return row

    def get_faculty_salary(self, faculty_id: int) -> FacultySalary | None:
        return self.session.get(FacultySalary, int(faculty_id))

    def list_faculty_salaries(self, *, active_only: bool = False) -> list[FacultySalary]:
        stmt = select(FacultySalary)
        if active_only:
            stmt = stmt.where(FacultySalary.is_active.is_(True))
        stmt = stmt.order_by(FacultySalary.faculty_name.asc())
        return list(self.session.scalars(stmt).all())

    def create_salary_expense(
        self,
        *,
        person_name: str,
        amount: float,
        expense_date: date,
        month_label: str,
        attendance_days: float,
        working_days: float,
        base_amount: float,
        description: str = "",
        notes: str = "",
    ) -> Expense:
        row = Expense(
            expense_type="salary",
            category="Salary",
            person_name=person_name.strip(),
            description=description.strip(),
            amount=float(amount),
            expense_date=expense_date,
            month_label=month_label.strip(),
            attendance_days=float(attendance_days),
            working_days=float(working_days),
            base_amount=float(base_amount),
            notes=notes.strip(),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def create_other_expense(
        self,
        *,
        category: str,
        amount: float,
        expense_date: date,
        description: str = "",
        notes: str = "",
    ) -> Expense:
        row = Expense(
            expense_type="other",
            category=category.strip(),
            amount=float(amount),
            expense_date=expense_date,
            description=description.strip(),
            notes=notes.strip(),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def list_salary_expenses(self, *, limit: int = 500) -> list[Expense]:
        stmt = (
            select(Expense)
            .where(Expense.expense_type == "salary")
            .order_by(Expense.expense_date.desc(), Expense.id.desc())
            .limit(int(limit))
        )
        return list(self.session.scalars(stmt).all())

    def list_other_expenses(self, *, limit: int = 500) -> list[Expense]:
        stmt = (
            select(Expense)
            .where(Expense.expense_type == "other")
            .order_by(Expense.expense_date.desc(), Expense.id.desc())
            .limit(int(limit))
        )
        return list(self.session.scalars(stmt).all())

    def sum_salary_expenses(self, month_label: str | None = None) -> float:
        stmt = select(func.coalesce(func.sum(Expense.amount), 0.0)).where(
            Expense.expense_type == "salary"
        )
        if month_label:
            stmt = stmt.where(Expense.month_label == month_label.strip())
        return float(self.session.scalar(stmt) or 0.0)

    def sum_other_expenses(self) -> float:
        return float(
            self.session.scalar(
                select(func.coalesce(func.sum(Expense.amount), 0.0)).where(
                    Expense.expense_type == "other"
                )
            )
            or 0.0
        )

    def grouped_other_expense_totals(self) -> dict[str, float]:
        rows = self.session.execute(
            select(Expense.category, func.coalesce(func.sum(Expense.amount), 0.0))
            .where(Expense.expense_type == "other")
            .group_by(Expense.category)
            .order_by(Expense.category.asc())
        ).all()
        return {str(category): float(total or 0.0) for category, total in rows}
