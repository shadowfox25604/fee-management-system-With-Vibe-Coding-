from __future__ import annotations

from datetime import date
from pathlib import Path

import xlsxwriter


class MiscIncomeExcelExporter:
    """Export miscellaneous expenses in the school's colour-coded ledger format."""

    _HEADER_BG = "#ED7D31"
    _DATE_BG = "#BDD7EE"
    _EXPENSE_BG = "#F8CBAD"
    _PARTICULARS_BG = "#E2EFDA"
    _AMOUNT_BG = "#C6EFCE"
    _GROUP_TOTAL_BG = "#FFE699"
    _GRAND_TOTAL_BG = "#44546A"

    @classmethod
    def export(cls, rows: list[dict], output_path: Path) -> None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        workbook = xlsxwriter.Workbook(str(output_path))
        try:
            sheet = workbook.add_worksheet("Expenses")
            sheet.set_column("A:A", 14)
            sheet.set_column("B:B", 18)
            sheet.set_column("C:C", 34)
            sheet.set_column("D:D", 12)
            sheet.set_column("E:E", 14)

            header_fmt = workbook.add_format(
                {
                    "bold": True,
                    "font_color": "#FFFFFF",
                    "bg_color": cls._HEADER_BG,
                    "align": "center",
                    "valign": "vcenter",
                    "border": 1,
                }
            )
            date_fmt = workbook.add_format(
                {"bg_color": cls._DATE_BG, "align": "right", "valign": "vcenter", "border": 1}
            )
            expense_fmt = workbook.add_format(
                {"bg_color": cls._EXPENSE_BG, "align": "left", "valign": "vcenter", "border": 1}
            )
            particulars_fmt = workbook.add_format(
                {"bg_color": cls._PARTICULARS_BG, "align": "left", "valign": "vcenter", "border": 1}
            )
            amount_fmt = workbook.add_format(
                {
                    "bg_color": cls._AMOUNT_BG,
                    "align": "right",
                    "valign": "vcenter",
                    "border": 1,
                    "num_format": "#,##0",
                }
            )
            group_total_fmt = workbook.add_format(
                {
                    "bold": True,
                    "bg_color": cls._GROUP_TOTAL_BG,
                    "align": "right",
                    "valign": "vcenter",
                    "border": 1,
                    "num_format": "#,##0",
                }
            )

            grand_total_label_fmt = workbook.add_format(
                {
                    "bold": True,
                    "font_color": "#FFFFFF",
                    "font_size": 12,
                    "bg_color": cls._GRAND_TOTAL_BG,
                    "align": "right",
                    "valign": "vcenter",
                    "border": 1,
                }
            )
            grand_total_amount_fmt = workbook.add_format(
                {
                    "bold": True,
                    "font_color": "#FFFFFF",
                    "font_size": 12,
                    "bg_color": cls._GRAND_TOTAL_BG,
                    "align": "right",
                    "valign": "vcenter",
                    "border": 1,
                    "num_format": "#,##0",
                }
            )
            grand_total_blank_fmt = workbook.add_format(
                {"bg_color": cls._GRAND_TOTAL_BG, "border": 1}
            )

            headers = ["Date", "Expense", "Particulars", "Amount", "Total"]
            for col, label in enumerate(headers):
                sheet.write(0, col, label, header_fmt)
            sheet.freeze_panes(1, 0)

            group_totals = cls._group_totals(rows)
            row_group_totals = cls._row_group_totals(rows, group_totals)
            grand_total = 0.0

            for row_idx, row in enumerate(rows, start=1):
                income_date = row.get("income_date")
                if isinstance(income_date, date):
                    sheet.write(row_idx, 0, cls._format_date(income_date), date_fmt)
                else:
                    sheet.write(row_idx, 0, "", date_fmt)

                sheet.write(row_idx, 1, str(row.get("head") or ""), expense_fmt)
                sheet.write(row_idx, 2, str(row.get("particular") or ""), particulars_fmt)
                amount = float(row.get("amount") or 0.0)
                sheet.write(row_idx, 3, amount, amount_fmt)
                grand_total += amount
                sheet.write(row_idx, 4, row_group_totals[row_idx - 1], group_total_fmt)

            total_row = len(rows) + 1
            if rows:
                sheet.merge_range(
                    total_row,
                    0,
                    total_row,
                    2,
                    "",
                    grand_total_blank_fmt,
                )
                sheet.write(total_row, 3, "Grand Total", grand_total_label_fmt)
                sheet.write(total_row, 4, grand_total, grand_total_amount_fmt)
                sheet.autofilter(0, 0, total_row, len(headers) - 1)
            else:
                sheet.autofilter(0, 0, 0, len(headers) - 1)
        finally:
            workbook.close()

    @staticmethod
    def _group_totals(rows: list[dict]) -> dict[int, float]:
        """Map each group's first row index to the sum of amounts in that group."""
        totals: dict[int, float] = {}
        if not rows:
            return totals
        start = 0
        group_sum = 0.0
        for idx, row in enumerate(rows):
            group_sum += float(row.get("amount") or 0.0)
            next_starts_group = idx + 1 >= len(rows) or bool(rows[idx + 1].get("show_head"))
            if next_starts_group:
                totals[start] = group_sum
                start = idx + 1
                group_sum = 0.0
        return totals

    @staticmethod
    def _row_group_totals(rows: list[dict], group_totals: dict[int, float]) -> list[float]:
        """Repeat each group's subtotal on every row in that group."""
        if not rows:
            return []
        out: list[float] = []
        group_start = 0
        for idx, row in enumerate(rows):
            if idx > 0 and bool(row.get("show_head", True)):
                group_start = idx
            out.append(group_totals.get(group_start, float(row.get("amount") or 0.0)))
        return out

    @staticmethod
    def _format_date(value: date) -> str:
        return f"{value.day}/{value.month}/{value.year}"
