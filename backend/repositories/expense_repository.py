from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from backend.models import Expense, FacultyAttendance, FacultySalary


class ExpenseRepository:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def _normalize_month_label(month_label: str) -> str:
        text = (month_label or "").strip()
        if len(text) != 7 or text[4] != "-":
            raise ValueError("Month label must be in YYYY-MM format.")
        year_text = text[:4]
        month_text = text[5:]
        if not year_text.isdigit() or not month_text.isdigit():
            raise ValueError("Month label must be in YYYY-MM format.")
        month_num = int(month_text)
        if month_num < 1 or month_num > 12:
            raise ValueError("Month label month must be between 01 and 12.")
        return f"{int(year_text):04d}-{month_num:02d}"

    @staticmethod
    def serialize_attendance_days(marked_days: list[int]) -> str:
        normalized = sorted({int(day) for day in (marked_days or []) if int(day) > 0})
        return ",".join(str(day) for day in normalized)

    @staticmethod
    def parse_attendance_days(marked_days_csv: str | None) -> list[int]:
        text = (marked_days_csv or "").strip()
        if not text:
            return []
        out: list[int] = []
        for token in text.split(","):
            value = token.strip()
            if not value:
                continue
            try:
                day_num = int(value)
            except ValueError:
                continue
            if day_num > 0:
                out.append(day_num)
        return sorted(set(out))

    @staticmethod
    def _normalize_faculty_type(value: str | None) -> str:
        text = (value or "").strip().lower()
        if text in ("teaching", "teacher", "academic"):
            return "Teaching"
        if text in ("non teaching", "non-teaching", "nonteaching", "admin", "support"):
            return "Non Teaching"
        return "Teaching"

    def upsert_faculty_salary(
        self,
        faculty_name: str,
        faculty_type: str,
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
                faculty_type=self._normalize_faculty_type(faculty_type),
                role=role.strip(),
                monthly_salary=float(monthly_salary),
                default_working_days=int(default_working_days),
                is_active=bool(is_active),
            )
            self.session.add(row)
        else:
            row.faculty_type = self._normalize_faculty_type(faculty_type)
            row.role = role.strip()
            row.monthly_salary = float(monthly_salary)
            row.default_working_days = int(default_working_days)
            row.is_active = bool(is_active)
        self.session.commit()
        self.session.refresh(row)
        return row

    def upsert_faculty_attendance(
        self,
        *,
        faculty_id: int,
        month_label: str,
        marked_days: list[int],
        checked_days: int,
        sunday_days: int,
        attendance_days: float,
        working_days: float,
    ) -> FacultyAttendance:
        faculty_id_num = int(faculty_id)
        month_text = self._normalize_month_label(month_label)
        stored_days = self.serialize_attendance_days(marked_days)
        row = self.session.scalars(
            select(FacultyAttendance)
            .where(
                FacultyAttendance.faculty_id_fk == faculty_id_num,
                FacultyAttendance.month_label == month_text,
            )
            .limit(1)
        ).first()
        if row is None:
            row = FacultyAttendance(
                faculty_id_fk=faculty_id_num,
                month_label=month_text,
                marked_days_csv=stored_days,
                checked_days=int(checked_days),
                sunday_days=int(sunday_days),
                attendance_days=float(attendance_days),
                working_days=float(working_days),
            )
            self.session.add(row)
        else:
            row.marked_days_csv = stored_days
            row.checked_days = int(checked_days)
            row.sunday_days = int(sunday_days)
            row.attendance_days = float(attendance_days)
            row.working_days = float(working_days)
        self.session.commit()
        self.session.refresh(row)
        return row

    def get_faculty_attendance(self, faculty_id: int, month_label: str) -> FacultyAttendance | None:
        return self.session.scalars(
            select(FacultyAttendance)
            .where(
                FacultyAttendance.faculty_id_fk == int(faculty_id),
                FacultyAttendance.month_label == self._normalize_month_label(month_label),
            )
            .limit(1)
        ).first()

    def get_faculty_salary(self, faculty_id: int) -> FacultySalary | None:
        return self.session.get(FacultySalary, int(faculty_id))

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
    ) -> FacultySalary | None:
        row = self.session.get(FacultySalary, int(faculty_id))
        if row is None:
            return None
        new_name = (faculty_name or "").strip()
        if not new_name:
            raise ValueError("Faculty name is required.")
        existing = self.session.scalars(
            select(FacultySalary)
            .where(
                func.lower(FacultySalary.faculty_name) == new_name.lower(),
                FacultySalary.id != int(faculty_id),
            )
            .limit(1)
        ).first()
        if existing is not None:
            raise ValueError("Another faculty with this name already exists.")

        old_name = str(row.faculty_name or "").strip()
        row.faculty_name = new_name
        row.faculty_type = self._normalize_faculty_type(faculty_type)
        row.role = (role or "").strip()
        row.monthly_salary = float(monthly_salary)
        row.default_working_days = int(default_working_days)
        row.is_active = bool(is_active)

        if old_name and old_name.lower() != new_name.lower():
            salary_rows = self.session.scalars(
                select(Expense).where(
                    Expense.expense_type == "salary",
                    func.lower(Expense.person_name) == old_name.lower(),
                )
            ).all()
            for salary_row in salary_rows:
                salary_row.person_name = new_name

        self.session.commit()
        self.session.refresh(row)
        return row

    def list_faculty_salaries(
        self,
        *,
        active_only: bool = False,
        faculty_type: str | None = None,
        search: str | None = None,
    ) -> list[FacultySalary]:
        stmt = select(FacultySalary)
        if active_only:
            stmt = stmt.where(FacultySalary.is_active.is_(True))
        if faculty_type and faculty_type.lower() != "all":
            stmt = stmt.where(FacultySalary.faculty_type == self._normalize_faculty_type(faculty_type))
        needle = (search or "").strip().lower()
        if needle:
            pat = f"%{needle}%"
            stmt = stmt.where(
                func.lower(FacultySalary.faculty_name).like(pat)
                | func.lower(FacultySalary.role).like(pat)
            )
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
        person_text = person_name.strip()
        month_text = month_label.strip()
        existing_rows = self.session.scalars(
            select(Expense)
            .where(
                Expense.expense_type == "salary",
                func.lower(Expense.person_name) == person_text.lower(),
                Expense.month_label == month_text,
            )
            .order_by(Expense.id.desc())
        ).all()
        if existing_rows:
            # Keep one row and overwrite it with latest salary payload.
            row = existing_rows[0]
            row.category = "Salary"
            row.person_name = person_text
            row.description = description.strip()
            row.amount = float(amount)
            row.expense_date = expense_date
            row.month_label = month_text
            row.attendance_days = float(attendance_days)
            row.working_days = float(working_days)
            row.base_amount = float(base_amount)
            row.notes = notes.strip()
            for duplicate in existing_rows[1:]:
                self.session.delete(duplicate)
        else:
            row = Expense(
                expense_type="salary",
                category="Salary",
                person_name=person_text,
                description=description.strip(),
                amount=float(amount),
                expense_date=expense_date,
                month_label=month_text,
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

    def list_salary_expenses_for_faculty(self, faculty_name: str, *, limit: int = 500) -> list[Expense]:
        name = (faculty_name or "").strip()
        if not name:
            return []
        stmt = (
            select(Expense)
            .where(
                Expense.expense_type == "salary",
                func.lower(Expense.person_name) == name.lower(),
            )
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

    def sum_salary_expenses_for_faculty(self, faculty_name: str) -> float:
        name = (faculty_name or "").strip()
        if not name:
            return 0.0
        return float(
            self.session.scalar(
                select(func.coalesce(func.sum(Expense.amount), 0.0)).where(
                    Expense.expense_type == "salary",
                    func.lower(Expense.person_name) == name.lower(),
                )
            )
            or 0.0
        )

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
