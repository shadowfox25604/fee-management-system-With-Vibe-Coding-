from __future__ import annotations

import calendar
from datetime import date, datetime

from sqlalchemy import func, or_, select

from backend.core.app_roles import format_operator_display
from backend.models import MiscIncome, MiscIncomeEntry


class MiscIncomeRepository:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def _not_reverted_filter():
        return or_(MiscIncomeEntry.is_reverted.is_(False), MiscIncomeEntry.is_reverted.is_(None))

    @staticmethod
    def _entry_history_row(entry: MiscIncomeEntry, expense: MiscIncome) -> dict:
        reverted = bool(getattr(entry, "is_reverted", False))
        return {
            "entry_id": entry.id,
            "income_id": expense.id,
            "head": expense.head or "",
            "income_date": entry.entry_date,
            "particular": entry.particular,
            "amount": float(entry.amount or 0.0),
            "is_reverted": reverted,
            "status": "Income reverted" if reverted else "Recorded",
            "operator": format_operator_display(getattr(entry, "operator_name", "") or ""),
        }

    @staticmethod
    def _normalize_head(head: str) -> str:
        text = (head or "").strip()
        if not text:
            raise ValueError("Income head is required.")
        return text

    @staticmethod
    def format_income_display_name(expense: MiscIncome) -> str:
        d = expense.income_date
        date_text = f"{d.day:02d}/{d.month:02d}/{d.year}" if d else ""
        parts = [str(expense.head or "").strip(), date_text]
        notes = (expense.notes or "").strip()
        if notes:
            parts.append(notes)
        return " · ".join(part for part in parts if part)

    def _find_income_by_head(
        self,
        head: str,
        *,
        exclude_id: int | None = None,
    ) -> MiscIncome | None:
        head_key = head.strip().lower()
        for row in self.session.scalars(select(MiscIncome)).all():
            if exclude_id is not None and int(row.id) == int(exclude_id):
                continue
            if (row.head or "").strip().lower() == head_key:
                return row
        return None

    def create_new_income(
        self,
        *,
        head: str,
        income_date: date,
        notes: str = "",
    ) -> MiscIncome:
        clean_head = self._normalize_head(head)
        clean_notes = (notes or "").strip()
        if self._find_income_by_head(clean_head) is not None:
            raise ValueError(
                f'An income source named "{clean_head}" already exists. '
                "Add entries to that income source instead."
            )
        row = MiscIncome(
            head=clean_head,
            income_date=income_date,
            notes=clean_notes,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def get_income(self, income_id: int) -> MiscIncome | None:
        return self.session.get(MiscIncome, int(income_id))

    def list_incomes(self) -> list[MiscIncome]:
        stmt = select(MiscIncome).order_by(
            MiscIncome.income_date.desc(),
            MiscIncome.head.asc(),
            MiscIncome.id.desc(),
        )
        return list(self.session.scalars(stmt).all())

    def update_income(
        self,
        income_id: int,
        *,
        head: str,
        income_date: date,
        notes: str = "",
    ) -> MiscIncome:
        row = self.get_income(income_id)
        if row is None:
            raise ValueError("Income not found.")
        clean_head = self._normalize_head(head)
        clean_notes = (notes or "").strip()
        if self._find_income_by_head(clean_head, exclude_id=int(income_id)) is not None:
            raise ValueError(
                f'An income source named "{clean_head}" already exists. '
                "Add entries to that income source instead."
            )
        row.head = clean_head
        row.income_date = income_date
        row.notes = clean_notes
        self.session.commit()
        self.session.refresh(row)
        return row

    def delete_income(self, income_id: int) -> None:
        row = self.get_income(income_id)
        if row is None:
            raise ValueError("Income not found.")
        self.session.delete(row)
        self.session.commit()

    def create_entry(
        self,
        *,
        income_id: int,
        particular: str,
        amount: float,
        entry_date: date | None = None,
        operator_name: str = "",
    ) -> MiscIncomeEntry:
        expense = self.get_income(income_id)
        if expense is None:
            raise ValueError("Income not found.")
        text = (particular or "").strip()
        if not text:
            raise ValueError("Particular is required.")
        value = float(amount or 0.0)
        if value <= 0:
            raise ValueError("Amount must be greater than zero.")
        row = MiscIncomeEntry(
            income_id=int(income_id),
            entry_date=entry_date or date.today(),
            particular=text,
            amount=value,
            operator_name=(operator_name or "").strip(),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def get_entry(self, entry_id: int) -> MiscIncomeEntry | None:
        return self.session.get(MiscIncomeEntry, int(entry_id))

    def update_entry(
        self,
        entry_id: int,
        *,
        particular: str,
        amount: float,
        entry_date: date | None = None,
    ) -> MiscIncomeEntry:
        row = self.get_entry(entry_id)
        if row is None:
            raise ValueError("Entry not found.")
        if bool(getattr(row, "is_reverted", False)):
            raise ValueError("Cannot edit a reverted income entry.")
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
            raise ValueError("This income entry is already reverted.")
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
            select(MiscIncomeEntry, MiscIncome)
            .join(MiscIncome, MiscIncomeEntry.income_id == MiscIncome.id)
        )
        needle = (search or "").strip().lower()
        if needle:
            pat = f"%{needle}%"
            stmt = stmt.where(
                or_(
                    func.lower(MiscIncome.head).like(pat),
                    func.lower(MiscIncome.notes).like(pat),
                    func.lower(MiscIncomeEntry.particular).like(pat),
                )
            )
        stmt = stmt.order_by(
            MiscIncomeEntry.id.desc(),
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
        income_id: int | None = None,
        income_ids: list[int] | None = None,
    ) -> list[dict]:
        stmt = select(MiscIncomeEntry, MiscIncome).join(
            MiscIncome, MiscIncomeEntry.income_id == MiscIncome.id
        ).where(self._not_reverted_filter())
        if month is not None:
            year, mon = month
            start = date(int(year), int(mon), 1)
            last_day = calendar.monthrange(int(year), int(mon))[1]
            end = date(int(year), int(mon), last_day)
            stmt = stmt.where(
                MiscIncomeEntry.entry_date >= start,
                MiscIncomeEntry.entry_date <= end,
            )
        else:
            if date_from is not None:
                stmt = stmt.where(MiscIncomeEntry.entry_date >= date_from)
            if date_to is not None:
                stmt = stmt.where(MiscIncomeEntry.entry_date <= date_to)
        if income_ids:
            ids = [int(value) for value in income_ids]
            if ids:
                stmt = stmt.where(MiscIncomeEntry.income_id.in_(ids))
        elif income_id is not None:
            stmt = stmt.where(MiscIncomeEntry.income_id == int(income_id))
        stmt = stmt.order_by(
            MiscIncomeEntry.entry_date.asc(),
            MiscIncome.head.asc(),
            MiscIncomeEntry.id.asc(),
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
                    "income_date": entry_date,
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

    def daily_income_for_month(self, year: int, month: int) -> dict:
        """Per-day miscellaneous expense totals by entry date."""
        last_day = calendar.monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, last_day)
        rows = self.session.execute(
            select(MiscIncomeEntry.entry_date, func.sum(MiscIncomeEntry.amount))
            .where(
                MiscIncomeEntry.entry_date >= start,
                MiscIncomeEntry.entry_date <= end,
                self._not_reverted_filter(),
            )
            .group_by(MiscIncomeEntry.entry_date)
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

    def income_by_head_for_month(self, year: int, month: int) -> list[tuple[str, float]]:
        """Miscellaneous expense totals grouped by expense head for a calendar month."""
        last_day = calendar.monthrange(int(year), int(month))[1]
        start = date(int(year), int(month), 1)
        end = date(int(year), int(month), last_day)
        rows = self.session.execute(
            select(MiscIncome.head, func.coalesce(func.sum(MiscIncomeEntry.amount), 0.0))
            .join(MiscIncomeEntry, MiscIncomeEntry.income_id == MiscIncome.id)
            .where(
                MiscIncomeEntry.entry_date >= start,
                MiscIncomeEntry.entry_date <= end,
                self._not_reverted_filter(),
            )
            .group_by(MiscIncome.head)
            .order_by(func.sum(MiscIncomeEntry.amount).desc())
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
                func.min(MiscIncomeEntry.entry_date),
                func.max(MiscIncomeEntry.entry_date),
            )
        ).one()
        return min_date, max_date

    def sum_all_entries(self) -> float:
        return float(
            self.session.scalar(
                select(func.coalesce(func.sum(MiscIncomeEntry.amount), 0.0)).where(
                    self._not_reverted_filter()
                )
            )
            or 0.0
        )
