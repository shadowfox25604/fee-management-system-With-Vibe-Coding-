"""Academic year date helpers — DD/MM/YYYY display and parsing."""

from datetime import date, datetime

from backend.core.payment_date_format import format_payment_date_dmY, parse_payment_date_dmY


def format_academic_year_range(start: date, end: date) -> str:
    return f"{format_payment_date_dmY(start)} – {format_payment_date_dmY(end)}"


def parse_academic_year_date(s: str) -> date:
    return parse_payment_date_dmY(s)


def auto_label_for_range(start: date, end: date) -> str:
    """Short label e.g. 2025-26 from May 2025 – Apr 2026."""
    if end.year == start.year:
        return str(start.year)
    if end.year == start.year + 1 and end.month <= 4:
        return f"{start.year}-{str(end.year)[-2:]}"
    return format_academic_year_range(start, end)
