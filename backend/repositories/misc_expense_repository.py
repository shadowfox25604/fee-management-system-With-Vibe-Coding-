from __future__ import annotations

import calendar
from datetime import date, datetime

from sqlalchemy import func, or_, select

from backend.models import MiscExpense, MiscExpenseEntry


class MiscExpenseRepository:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def _not_reverted_filter():
        return or_(MiscExpenseEntry.is_reverted.is_(False), MiscExpenseEntry.is_reverted.is_(None))

    @staticmethod
    def _entry_history_row(entry: MiscExpenseEntry, expense: MiscExpense) -> dict:
        reverted = bool(getattr(entry, "is_reverted", False))
        return {
            "entry_id": entry.id,
            "expense_id": expense.id,
            "head": expense.head or "",
            "expense_date": entry.entry_date,
            "particular": entry.particular,
            "amount": float(entry.amount or 0.0),
            "is_reverted": reverted,
            "status": "Expense reverted" if reverted else "Recorded",
        }

    @staticmethod
    def _normalize_head(head: str) -> str:
        text = (head or "").strip()
        if not text:
            raise ValueError("Expense head is required.")
        return text

    @staticmethod
    def format_expense_display_name(expense: MiscExpense) -> str:
        d = expense.expense_date
        date_text = f"{d.day:02d}/{d.month:02d}/{d.year}" if d else ""
        parts = [str(expense.head or "").strip(), date_text]
        notes = (expense.notes or "").strip()
        if notes:
            parts.append(notes)
        return " · ".join(part for part in parts if part)

    def _find_expense_by_head(
        self,
        head: str,
        *,
        exclude_id: int | None = None,
    ) -> MiscExpense | None:
        head_key = head.strip().lower()
        for row in self.session.scalars(select(MiscExpense)).all():
            if exclude_id is not None and int(row.id) == int(exclude_id):
                continue
            if (row.head or "").strip().lower() == head_key:
                return row
        return None

    def create_new_expense(
        self,
        *,
        head: str,
        expense_date: date,
        notes: str = "",
    ) -> MiscExpense:
        clean_head = self._normalize_head(head)
        clean_notes = (notes or "").strip()
        if self._find_expense_by_head(clean_head) is not None:
            raise ValueError(
                f'An expense named "{clean_head}" already exists. '
                "Add entries to that expense instead."
            )
        row = MiscExpense(
            head=clean_head,
            expense_date=expense_date,
            notes=clean_notes,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def get_expense(self, expense_id: int) -> MiscExpense | None:
        return self.session.get(MiscExpense, int(expense_id))

    def list_expenses(self) -> list[MiscExpense]:
        stmt = select(MiscExpense).order_by(
            MiscExpense.expense_date.desc(),
            MiscExpense.head.asc(),
            MiscExpense.id.desc(),
        )
        return list(self.session.scalars(stmt).all())

    def update_expense(
        self,
        expense_id: int,
        *,
        head: str,
        expense_date: date,
        notes: str = "",
    ) -> MiscExpense:
        row = self.get_expense(expense_id)
        if row is None:
            raise ValueError("Expense not found.")
        clean_head = self._normalize_head(head)
        clean_notes = (notes or "").strip()
        if self._find_expense_by_head(clean_head, exclude_id=int(expense_id)) is not None:
            raise ValueError(
                f'An expense named "{clean_head}" already exists. '
                "Add entries to that expense instead."
            )
        row.head = clean_head
        row.expense_date = expense_date
        row.notes = clean_notes
        self.session.commit()
        self.session.refresh(row)
        return row

    def delete_expense(self, expense_id: int) -> None:
        row = self.get_expense(expense_id)
        if row is None:
            raise ValueError("Expense not found.")
        self.session.delete(row)
        self.session.commit()

    def create_entry(
        self,
        *,
        expense_id: int,
        particular: str,
        amount: float,
        entry_date: date | None = None,
    ) -> MiscExpenseEntry:
        expense = self.get_expense(expense_id)
        if expense is None:
            raise ValueError("Expense not found.")
        text = (particular or "").strip()
        if not text:
            raise ValueError("Particular is required.")
        value = float(amount or 0.0)
        if value <= 0:
            raise ValueError("Amount must be greater than zero.")
        row = MiscExpenseEntry(
            expense_id=int(expense_id),
            entry_date=entry_date or date.today(),
            particular=text,
            amount=value,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def get_entry(self, entry_id: int) -> MiscExpenseEntry | None:
        return self.session.get(MiscExpenseEntry, int(entry_id))

    def update_entry(
        self,
        entry_id: int,
        *,
        particular: str,
        amount: float,
        entry_date: date | None = None,
    ) -> MiscExpenseEntry:
        row = self.get_entry(entry_id)
        if row is None:
            raise ValueError("Entry not found.")
        if bool(getattr(row, "is_reverted", False)):
            raise ValueError("Cannot edit a reverted expense entry.")
        text = (particular or "").strip()
        if not text:
            raise ValueError("Particular is required.")
        value = float(amount or 0.0)
        if value <= 0:
            raise ValueError("Amount must be greater than zero.")
        row.particular = text
        row.amount = value
        if entry_date is not None:
            row.entry_date = entry_date
        self.session.commit()
        self.session.refresh(row)
        return row

    def delete_entry(self, entry_id: int) -> None:
        row = self.get_entry(entry_id)
        if row is None:
            raise ValueError("Entry not found.")
        if bool(getattr(row, "is_reverted", False)):
            raise ValueError("This expense entry is already reverted.")
        row.is_reverted = True
        row.reverted_at = datetime.now()
        self.session.commit()

    def list_entry_history(
        self,
        *,
        limit: int = 50000,
        search: str | None = None,
    ) -> list[dict]:
        stmt = (
            select(MiscExpenseEntry, MiscExpense)
            .join(MiscExpense, MiscExpenseEntry.expense_id == MiscExpense.id)
        )
        needle = (search or "").strip().lower()
        if needle:
            pat = f"%{needle}%"
            stmt = stmt.where(
                or_(
                    func.lower(MiscExpense.head).like(pat),
                    func.lower(MiscExpense.notes).like(pat),
                    func.lower(MiscExpenseEntry.particular).like(pat),
                )
            )
        stmt = stmt.order_by(
            MiscExpenseEntry.id.desc(),
        ).limit(int(limit))
        return [
            self._entry_history_row(entry, expense)
            for entry, expense in self.session.execute(stmt).all()
        ]

    def list_export_rows(
        self,
        *,
        month: tuple[int, int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        expense_id: int | None = None,
        expense_ids: list[int] | None = None,
    ) -> list[dict]:
        stmt = select(MiscExpenseEntry, MiscExpense).join(
            MiscExpense, MiscExpenseEntry.expense_id == MiscExpense.id
        ).where(self._not_reverted_filter())
        if month is not None:
            year, mon = month
            start = date(int(year), int(mon), 1)
            last_day = calendar.monthrange(int(year), int(mon))[1]
            end = date(int(year), int(mon), last_day)
            stmt = stmt.where(
                MiscExpenseEntry.entry_date >= start,
                MiscExpenseEntry.entry_date <= end,
            )
        else:
            if date_from is not None:
                stmt = stmt.where(MiscExpenseEntry.entry_date >= date_from)
            if date_to is not None:
                stmt = stmt.where(MiscExpenseEntry.entry_date <= date_to)
        if expense_ids:
            ids = [int(value) for value in expense_ids]
            if ids:
                stmt = stmt.where(MiscExpenseEntry.expense_id.in_(ids))
        elif expense_id is not None:
            stmt = stmt.where(MiscExpenseEntry.expense_id == int(expense_id))
        stmt = stmt.order_by(
            MiscExpenseEntry.entry_date.asc(),
            MiscExpense.head.asc(),
            MiscExpenseEntry.id.asc(),
        )
        rows: list[dict] = []
        prev_date: date | None = None
        prev_head: str | None = None
        for entry, expense in self.session.execute(stmt).all():
            entry_date = entry.entry_date
            head = expense.head or ""
            show_date = entry_date != prev_date
            show_head = show_date or head != prev_head
            rows.append(
                {
                    "expense_date": entry_date,
                    "head": head,
                    "particular": entry.particular,
                    "amount": float(entry.amount or 0.0),
                    "show_date": show_date,
                    "show_head": show_head,
                }
            )
            prev_date = entry_date
            prev_head = head
        return rows

    def daily_misc_expenses_for_month(self, year: int, month: int) -> dict:
        """Per-day miscellaneous expense totals by entry date."""
        last_day = calendar.monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, last_day)
        rows = self.session.execute(
            select(MiscExpenseEntry.entry_date, func.sum(MiscExpenseEntry.amount))
            .where(
                MiscExpenseEntry.entry_date >= start,
                MiscExpenseEntry.entry_date <= end,
                self._not_reverted_filter(),
            )
            .group_by(MiscExpenseEntry.entry_date)
        ).all()
        by_day: dict[int, float] = {}
        for entry_date, total in rows:
            if isinstance(entry_date, date):
                by_day[int(entry_date.day)] = float(total or 0.0)
        amounts = [by_day.get(day, 0.0) for day in range(1, last_day + 1)]
        month_label = date(year, month, 1).strftime("%B %Y")
        return {
            "year": year,
            "month": month,
            "days_in_month": last_day,
            "amounts": amounts,
            "reverted_amounts": [0.0] * last_day,
            "month_label": month_label,
        }

    def misc_expenses_by_head_for_month(self, year: int, month: int) -> list[tuple[str, float]]:
        """Miscellaneous expense totals grouped by expense head for a calendar month."""
        last_day = calendar.monthrange(int(year), int(month))[1]
        start = date(int(year), int(month), 1)
        end = date(int(year), int(month), last_day)
        rows = self.session.execute(
            select(MiscExpense.head, func.coalesce(func.sum(MiscExpenseEntry.amount), 0.0))
            .join(MiscExpenseEntry, MiscExpenseEntry.expense_id == MiscExpense.id)
            .where(
                MiscExpenseEntry.entry_date >= start,
                MiscExpenseEntry.entry_date <= end,
                self._not_reverted_filter(),
            )
            .group_by(MiscExpense.head)
            .order_by(func.sum(MiscExpenseEntry.amount).desc())
        ).all()
        out: list[tuple[str, float]] = []
        for head, total in rows:
            amount = float(total or 0.0)
            if amount <= 1e-6:
                continue
            label = str(head or "").strip() or "Miscellaneous"
            out.append((label, amount))
        return out

    def entry_date_bounds(self) -> tuple[date | None, date | None]:
        min_date, max_date = self.session.execute(
            select(
                func.min(MiscExpenseEntry.entry_date),
                func.max(MiscExpenseEntry.entry_date),
            )
        ).one()
        return min_date, max_date

    def sum_all_entries(self) -> float:
        return float(
            self.session.scalar(
                select(func.coalesce(func.sum(MiscExpenseEntry.amount), 0.0)).where(
                    self._not_reverted_filter()
                )
            )
            or 0.0
        )
