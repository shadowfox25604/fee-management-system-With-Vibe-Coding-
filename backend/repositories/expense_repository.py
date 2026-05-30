from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, or_, select

from backend.core.salary_reference import allocate_unique_salary_reference
from backend.models import Expense, FacultyAttendance, FacultySalary


class ExpenseRepository:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def _salary_not_reverted_filter():
        return or_(Expense.is_reverted.is_(False), Expense.is_reverted.is_(None))

    def lookup_faculty_type(self, person_name: str) -> str:
        name = (person_name or "").strip()
        if not name:
            return ""
        row = self.session.scalars(
            select(FacultySalary.faculty_type)
            .where(func.lower(func.trim(FacultySalary.faculty_name)) == name.lower())
            .limit(1)
        ).first()
        return self._normalize_faculty_type(row) if row else ""

    def new_salary_reference(self) -> str:
        def exists(cand: str) -> bool:
            hit = self.session.scalar(
                select(func.count(Expense.id)).where(Expense.reference_no == cand)
            )
            return int(hit or 0) > 0

        return allocate_unique_salary_reference(exists)

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
                salary_row.faculty_type = self._normalize_faculty_type(row.faculty_type)

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
        operator_name: str = "",
        faculty_type: str = "",
    ) -> Expense:
        person_text = person_name.strip()
        month_text = month_label.strip()
        category_text = self._normalize_faculty_type(faculty_type) or self.lookup_faculty_type(person_text)
        row = Expense(
            expense_type="salary",
            category="Salary",
            person_name=person_text,
            faculty_type=category_text,
            description=description.strip(),
            amount=float(amount),
            expense_date=expense_date,
            month_label=month_text,
            attendance_days=float(attendance_days),
            working_days=float(working_days),
            base_amount=float(base_amount),
            notes=notes.strip(),
            reference_no=self.new_salary_reference(),
            operator_name=(operator_name or "").strip(),
            is_reverted=False,
            reverted_at=None,
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

    def list_salary_expenses(
        self, *, limit: int = 500, include_reverted: bool = False
    ) -> list[Expense]:
        stmt = select(Expense).where(Expense.expense_type == "salary")
        if not include_reverted:
            stmt = stmt.where(self._salary_not_reverted_filter())
        stmt = stmt.order_by(Expense.expense_date.desc(), Expense.id.desc()).limit(int(limit))
        return list(self.session.scalars(stmt).all())

    def list_salary_expenses_for_faculty(
        self,
        faculty_name: str,
        *,
        limit: int = 500,
        include_reverted: bool = True,
    ) -> list[Expense]:
        name = (faculty_name or "").strip()
        if not name:
            return []
        stmt = select(Expense).where(
            Expense.expense_type == "salary",
            func.lower(Expense.person_name) == name.lower(),
        )
        if not include_reverted:
            stmt = stmt.where(self._salary_not_reverted_filter())
        stmt = stmt.order_by(Expense.expense_date.desc(), Expense.id.desc()).limit(int(limit))
        return list(self.session.scalars(stmt).all())

    def list_salary_history(
        self,
        limit: int = 5000,
        search: str | None = None,
        *,
        include_reverted: bool = True,
    ) -> list[dict]:
        stmt = (
            select(Expense, FacultySalary)
            .outerjoin(
                FacultySalary,
                func.lower(FacultySalary.faculty_name) == func.lower(Expense.person_name),
            )
            .where(Expense.expense_type == "salary")
        )
        if not include_reverted:
            stmt = stmt.where(self._salary_not_reverted_filter())
        needle = (search or "").strip()
        if needle:
            pat = f"%{needle.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Expense.reference_no).like(pat),
                    func.lower(Expense.person_name).like(pat),
                    func.lower(Expense.month_label).like(pat),
                    func.lower(FacultySalary.role).like(pat),
                    func.lower(Expense.notes).like(pat),
                )
            )
        stmt = stmt.order_by(Expense.expense_date.desc(), Expense.id.desc()).limit(int(limit))
        out: list[dict] = []
        for exp, faculty in self.session.execute(stmt).all():
            reverted = bool(getattr(exp, "is_reverted", False))
            stored_type = (getattr(exp, "faculty_type", None) or "").strip()
            if not stored_type and faculty is not None:
                stored_type = str(getattr(faculty, "faculty_type", None) or "").strip()
            if not stored_type:
                stored_type = self.lookup_faculty_type(exp.person_name or "")
            out.append(
                {
                    "expense_id": exp.id,
                    "expense_date": exp.expense_date,
                    "reference_no": exp.reference_no or "",
                    "faculty_name": exp.person_name or "",
                    "faculty_type": stored_type or "—",
                    "role": getattr(faculty, "role", "") or "",
                    "month_label": exp.month_label or "",
                    "attendance_days": float(exp.attendance_days or 0.0),
                    "working_days": float(exp.working_days or 0.0),
                    "base_amount": float(exp.base_amount or 0.0),
                    "amount": float(exp.amount or 0.0),
                    "notes": exp.notes or "",
                    "operator": getattr(exp, "operator_name", "") or "",
                    "is_reverted": reverted,
                    "status": "Salary reverted" if reverted else "Paid",
                }
            )
        return out

    def undo_salary_expense(self, reference_no: str) -> Expense:
        ref = (reference_no or "").strip()
        if not ref:
            raise ValueError("Salary reference is required.")
        row = self.session.scalars(
            select(Expense).where(
                Expense.expense_type == "salary",
                Expense.reference_no == ref,
            ).limit(1)
        ).first()
        if row is None:
            raise ValueError("Salary payment not found.")
        if bool(getattr(row, "is_reverted", False)):
            raise ValueError("This salary payment is already reverted.")
        row.is_reverted = True
        row.reverted_at = datetime.now()
        self.session.commit()
        self.session.refresh(row)
        return row

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
            Expense.expense_type == "salary",
            self._salary_not_reverted_filter(),
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
                    self._salary_not_reverted_filter(),
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

    def purge_faculty_by_name(self, faculty_name: str) -> dict[str, int]:
        """Remove faculty profile, attendance, and all salary payouts for this name."""
        needle = (faculty_name or "").strip().lower()
        if not needle:
            raise ValueError("Faculty name is required.")
        faculty = self.session.scalars(
            select(FacultySalary)
            .where(func.lower(func.trim(FacultySalary.faculty_name)) == needle)
            .limit(1)
        ).first()
        attendance_deleted = 0
        faculty_deleted = 0
        if faculty is not None:
            attendance_rows = list(
                self.session.scalars(
                    select(FacultyAttendance).where(
                        FacultyAttendance.faculty_id_fk == int(faculty.id)
                    )
                ).all()
            )
            for row in attendance_rows:
                self.session.delete(row)
            attendance_deleted = len(attendance_rows)
            self.session.delete(faculty)
            faculty_deleted = 1
        expense_rows = list(
            self.session.scalars(
                select(Expense).where(
                    Expense.expense_type == "salary",
                    func.lower(func.trim(Expense.person_name)) == needle,
                )
            ).all()
        )
        for row in expense_rows:
            self.session.delete(row)
        self.session.commit()
        return {
            "faculty_deleted": faculty_deleted,
            "attendance_deleted": attendance_deleted,
            "salary_expenses_deleted": len(expense_rows),
        }
