from __future__ import annotations

from datetime import date
from pathlib import Path

from backend.repositories.misc_income_repository import MiscIncomeRepository


class MiscIncomeService:
    def __init__(self, session):
        self.repo = MiscIncomeRepository(session)

    def add_new_income(
        self,
        head: str,
        income_date: date,
        *,
        notes: str = "",
    ):
        return self.repo.create_new_income(
            head=head,
            income_date=income_date,
            notes=notes,
        )

    def list_incomes(self):
        return self.repo.list_incomes()

    def update_income(
        self,
        income_id: int,
        *,
        head: str,
        income_date: date,
        notes: str = "",
    ):
        return self.repo.update_income(
            income_id,
            head=head,
            income_date=income_date,
            notes=notes,
        )

    def delete_income(self, income_id: int) -> None:
        self.repo.delete_income(income_id)

    def add_entry(
        self,
        income_id: int,
        particular: str,
        amount: float,
        *,
        entry_date: date | None = None,
    ):
        return self.repo.create_entry(
            income_id=income_id,
            particular=particular,
            amount=amount,
            entry_date=entry_date,
        )

    def update_entry(
        self,
        entry_id: int,
        *,
        particular: str,
        amount: float,
        entry_date: date | None = None,
    ):
        return self.repo.update_entry(
            entry_id,
            particular=particular,
            amount=amount,
            entry_date=entry_date,
        )

    def delete_entry(self, entry_id: int) -> None:
        self.repo.delete_entry(entry_id)

    def list_entry_history(self, *, limit: int = 50000, search: str | None = None):
        return self.repo.list_entry_history(limit=limit, search=search)

    def total_received(self) -> float:
        return self.repo.sum_all_entries()

    def entry_date_bounds(self) -> tuple[date | None, date | None]:
        return self.repo.entry_date_bounds()

    def daily_income_chart_for_month(self, year: int, month: int) -> dict:
        return self.repo.daily_income_for_month(year, month)

    def income_by_head_for_month(self, year: int, month: int) -> list[tuple[str, float]]:
        return self.repo.income_by_head_for_month(year, month)

    def dashboard_income_pie_for_month(self, year: int, month: int) -> dict:
        year_num = int(year)
        month_num = int(month)
        if month_num < 1 or month_num > 12:
            raise ValueError("Month must be between 1 and 12.")
        slices: list[dict] = []
        for head, amount in self.income_by_head_for_month(year_num, month_num):
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

    def count_export_rows(
        self,
        *,
        month: tuple[int, int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        income_id: int | None = None,
        income_ids: list[int] | None = None,
    ) -> int:
        return len(
            self.repo.list_export_rows(
                month=month,
                date_from=date_from,
                date_to=date_to,
                income_id=income_id,
                income_ids=income_ids,
            )
        )

    @staticmethod
    def income_display_name(income) -> str:
        return MiscIncomeRepository.format_income_display_name(income)

    def export_excel(
        self,
        output_path: Path,
        *,
        month: tuple[int, int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        income_id: int | None = None,
        income_ids: list[int] | None = None,
    ) -> Path:
        from backend.reports.misc_income_excel_export import MiscIncomeExcelExporter

        rows = self.repo.list_export_rows(
            month=month,
            date_from=date_from,
            date_to=date_to,
            income_id=income_id,
            income_ids=income_ids,
        )
        MiscIncomeExcelExporter.export(rows, output_path)
        return output_path
