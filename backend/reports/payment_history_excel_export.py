from __future__ import annotations

from datetime import date
from pathlib import Path

import xlsxwriter


class PaymentHistoryExcelExporter:
    """Export payment history rows to a formatted Excel workbook."""

    _HEADER_BG = "#1ABC9C"
    _GRAND_TOTAL_BG = "#44546A"

    @classmethod
    def export(cls, rows: list[dict], output_path: Path) -> None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        headers = [
            "Date",
            "Reference",
            "Student ID",
            "Name",
            "Class",
            "Section",
            "Total (₹)",
            "Discount (₹)",
            "Mode",
            "Operator",
            "Status",
        ]

        workbook = xlsxwriter.Workbook(str(output_path))
        try:
            sheet = workbook.add_worksheet("Payment History")
            sheet.set_column("A:A", 12)
            sheet.set_column("B:B", 14)
            sheet.set_column("C:C", 12)
            sheet.set_column("D:D", 24)
            sheet.set_column("E:E", 10)
            sheet.set_column("F:F", 10)
            sheet.set_column("G:H", 12)
            sheet.set_column("I:I", 12)
            sheet.set_column("J:J", 14)
            sheet.set_column("K:K", 16)

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
            text_fmt = workbook.add_format({"border": 1, "valign": "vcenter"})
            money_fmt = workbook.add_format(
                {"border": 1, "align": "right", "valign": "vcenter", "num_format": "#,##0.00"}
            )
            total_label_fmt = workbook.add_format(
                {
                    "bold": True,
                    "font_color": "#FFFFFF",
                    "bg_color": cls._GRAND_TOTAL_BG,
                    "align": "right",
                    "valign": "vcenter",
                    "border": 1,
                }
            )
            total_money_fmt = workbook.add_format(
                {
                    "bold": True,
                    "font_color": "#FFFFFF",
                    "bg_color": cls._GRAND_TOTAL_BG,
                    "align": "right",
                    "valign": "vcenter",
                    "border": 1,
                    "num_format": "#,##0.00",
                }
            )
            total_blank_fmt = workbook.add_format({"bg_color": cls._GRAND_TOTAL_BG, "border": 1})

            for col, label in enumerate(headers):
                sheet.write(0, col, label, header_fmt)
            sheet.freeze_panes(1, 0)

            total_amount = 0.0
            total_discount = 0.0
            for row_idx, row in enumerate(rows, start=1):
                payment_date = row.get("payment_date")
                date_text = cls._format_date(payment_date) if isinstance(payment_date, date) else ""
                amount = float(row.get("amount") or 0.0)
                discount = float(row.get("discount") or 0.0)
                total_amount += amount
                total_discount += discount

                sheet.write(row_idx, 0, date_text, text_fmt)
                sheet.write(row_idx, 1, str(row.get("reference_no") or ""), text_fmt)
                sheet.write(row_idx, 2, str(row.get("student_roll") or ""), text_fmt)
                sheet.write(row_idx, 3, str(row.get("student_name") or ""), text_fmt)
                sheet.write(row_idx, 4, str(row.get("class_name") or ""), text_fmt)
                sheet.write(row_idx, 5, str(row.get("section") or ""), text_fmt)
                sheet.write(row_idx, 6, amount, money_fmt)
                sheet.write(row_idx, 7, discount, money_fmt)
                sheet.write(row_idx, 8, str(row.get("mode") or ""), text_fmt)
                sheet.write(row_idx, 9, str(row.get("operator") or ""), text_fmt)
                sheet.write(row_idx, 10, str(row.get("status") or "Paid"), text_fmt)

            if rows:
                total_row = len(rows) + 1
                for col in range(5):
                    sheet.write(total_row, col, "", total_blank_fmt)
                sheet.write(total_row, 5, "Grand Total", total_label_fmt)
                sheet.write(total_row, 6, total_amount, total_money_fmt)
                sheet.write(total_row, 7, total_discount, total_money_fmt)
                for col in range(8, len(headers)):
                    sheet.write(total_row, col, "", total_blank_fmt)
                sheet.autofilter(0, 0, total_row, len(headers) - 1)
            else:
                sheet.autofilter(0, 0, 0, len(headers) - 1)
        finally:
            workbook.close()

    @staticmethod
    def _format_date(value: date) -> str:
        return f"{value.day:02d}/{value.month:02d}/{value.year}"
