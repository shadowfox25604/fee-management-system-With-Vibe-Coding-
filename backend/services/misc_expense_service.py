from __future__ import annotations

from datetime import date
from pathlib import Path

from backend.repositories.misc_expense_repository import MiscExpenseRepository


class MiscExpenseService:
    def __init__(self, session):
        self.repo = MiscExpenseRepository(session)

    def add_new_expense(
        self,
        head: str,
        expense_date: date,
        *,
        notes: str = "",
    ):
        return self.repo.create_new_expense(
            head=head,
            expense_date=expense_date,
            notes=notes,
        )

    def list_expenses(self):
        return self.repo.list_expenses()

    def update_expense(
        self,
        expense_id: int,
        *,
        head: str,
        expense_date: date,
        notes: str = "",
    ):
        return self.repo.update_expense(
            expense_id,
            head=head,
            expense_date=expense_date,
            notes=notes,
        )

    def delete_expense(self, expense_id: int) -> None:
        self.repo.delete_expense(expense_id)

    def add_entry(
        self,
        expense_id: int,
        particular: str,
        amount: float,
        *,
        entry_date: date | None = None,
    ):
        return self.repo.create_entry(
            expense_id=expense_id,
            particular=particular,
            amount=amount,
            entry_date=entry_date,
        )

    def update_entry(self, entry_id: int, *, particular: str, amount: float):
        return self.repo.update_entry(entry_id, particular=particular, amount=amount)

    def delete_entry(self, entry_id: int) -> None:
        self.repo.delete_entry(entry_id)

    def list_entry_history(self, *, limit: int = 50000, search: str | None = None):
        return self.repo.list_entry_history(limit=limit, search=search)

    def total_spent(self) -> float:
        return self.repo.sum_all_entries()

    def entry_date_bounds(self) -> tuple[date | None, date | None]:
        return self.repo.entry_date_bounds()

    def daily_misc_chart_for_month(self, year: int, month: int) -> dict:
        return self.repo.daily_misc_expenses_for_month(year, month)

    def count_export_rows(
        self,
        *,
        month: tuple[int, int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        expense_id: int | None = None,
        expense_ids: list[int] | None = None,
    ) -> int:
        return len(
            self.repo.list_export_rows(
                month=month,
                date_from=date_from,
                date_to=date_to,
                expense_id=expense_id,
                expense_ids=expense_ids,
            )
        )

    @staticmethod
    def expense_display_name(expense) -> str:
        return MiscExpenseRepository.format_expense_display_name(expense)

    def export_excel(
        self,
        output_path: Path,
        *,
        month: tuple[int, int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        expense_id: int | None = None,
        expense_ids: list[int] | None = None,
    ) -> Path:
        from backend.reports.misc_expense_excel_export import MiscExpenseExcelExporter

        rows = self.repo.list_export_rows(
            month=month,
            date_from=date_from,
            date_to=date_to,
            expense_id=expense_id,
            expense_ids=expense_ids,
        )
        MiscExpenseExcelExporter.export(rows, output_path)
        return output_path
