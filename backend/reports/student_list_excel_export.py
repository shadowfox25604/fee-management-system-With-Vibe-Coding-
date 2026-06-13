from __future__ import annotations

from pathlib import Path

import xlsxwriter

STUDENT_LIST_EXPORT_COLUMNS: tuple[dict, ...] = (
    {"key": "student_id", "header": "Student ID", "money": False, "width": 12},
    {"key": "full_name", "header": "Name", "money": False, "width": 24},
    {"key": "gender", "header": "Gender", "money": False, "width": 10},
    {"key": "father_name", "header": "Father Name", "money": False, "width": 18},
    {"key": "mother_name", "header": "Mother Name", "money": False, "width": 18},
    {"key": "class_name", "header": "Class", "money": False, "width": 10},
    {"key": "section", "header": "Section", "money": False, "width": 10},
    {"key": "mobile_number_1", "header": "Mobile Number 1", "money": False, "width": 14},
    {"key": "mobile_number_2", "header": "Mobile Number 2", "money": False, "width": 14},
    {"key": "date_of_birth", "header": "Date of Birth", "money": False, "width": 12},
    {"key": "caste", "header": "Caste", "money": False, "width": 12},
    {"key": "aadhaar", "header": "Aadhaar", "money": False, "width": 16},
    {"key": "village", "header": "Village", "money": False, "width": 16},
    {"key": "status", "header": "Status", "money": False, "width": 10},
    {"key": "van_fees", "header": "Van Fees", "money": True, "width": 14},
    {"key": "van_paid", "header": "Van Paid", "money": True, "width": 14},
    {"key": "van_due", "header": "Van Due (current)", "money": True, "width": 14},
    {"key": "school_fees", "header": "School Fees", "money": True, "width": 14},
    {"key": "school_paid", "header": "School Paid", "money": True, "width": 14},
    {"key": "discount", "header": "Discount", "money": True, "width": 14},
    {"key": "pending_fees", "header": "Pending fees", "money": True, "width": 14},
    {"key": "school_due", "header": "School Due (current)", "money": True, "width": 14},
    {"key": "school_payable", "header": "School Payable (total)", "money": True, "width": 14},
    {"key": "total_due", "header": "Total Due", "money": True, "width": 14},
)

STUDENT_LIST_EXPORT_COLUMN_KEYS: tuple[str, ...] = tuple(
    column["key"] for column in STUDENT_LIST_EXPORT_COLUMNS
)


class StudentListExcelExporter:
    """Export student list rows to a formatted Excel workbook."""

    _HEADER_BG = "#1ABC9C"
    _GRAND_TOTAL_BG = "#44546A"

    @classmethod
    def _column_defs(cls, columns: list[str] | None) -> list[dict]:
        if not columns:
            return list(STUDENT_LIST_EXPORT_COLUMNS)
        by_key = {column["key"]: column for column in STUDENT_LIST_EXPORT_COLUMNS}
        resolved: list[dict] = []
        for key in columns:
            column = by_key.get(key)
            if column is not None:
                resolved.append(column)
        return resolved

    @classmethod
    def export(
        cls,
        rows: list[dict],
        output_path: Path,
        *,
        columns: list[str] | None = None,
    ) -> None:
        column_defs = cls._column_defs(columns)
        if not column_defs:
            raise ValueError("Select at least one column to export.")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        workbook = xlsxwriter.Workbook(str(output_path))
        try:
            sheet = workbook.add_worksheet("Student List")
            for col_idx, column in enumerate(column_defs):
                width = int(column.get("width") or 12)
                sheet.set_column(col_idx, col_idx, width)

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

            for col_idx, column in enumerate(column_defs):
                sheet.write(0, col_idx, str(column["header"]), header_fmt)
            sheet.freeze_panes(1, 0)

            money_keys = [column["key"] for column in column_defs if column["money"]]
            totals = {key: 0.0 for key in money_keys}
            for row_idx, row in enumerate(rows, start=1):
                for col_idx, column in enumerate(column_defs):
                    key = str(column["key"])
                    if column["money"]:
                        value = float(row.get(key) or 0.0)
                        totals[key] = totals.get(key, 0.0) + value
                        sheet.write(row_idx, col_idx, value, money_fmt)
                    else:
                        sheet.write(row_idx, col_idx, str(row.get(key) or ""), text_fmt)

            last_col = len(column_defs) - 1
            if rows and money_keys:
                total_row = len(rows) + 1
                first_money_idx = next(
                    i for i, column in enumerate(column_defs) if column["money"]
                )
                label_col = max(0, first_money_idx - 1)
                for col_idx, column in enumerate(column_defs):
                    if col_idx == label_col:
                        sheet.write(total_row, col_idx, "Grand Total", total_label_fmt)
                    elif column["money"]:
                        sheet.write(
                            total_row,
                            col_idx,
                            totals[str(column["key"])],
                            total_money_fmt,
                        )
                    else:
                        sheet.write(total_row, col_idx, "", total_blank_fmt)
                sheet.autofilter(0, 0, total_row, last_col)
            elif rows:
                sheet.autofilter(0, 0, len(rows), last_col)
            else:
                sheet.autofilter(0, 0, 0, last_col)
        finally:
            workbook.close()
