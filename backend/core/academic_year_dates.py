"""Academic year date helpers — automatic May 31 → 1 June ranges."""

from datetime import date

from backend.core.payment_date_format import parse_payment_date_dmY


def format_academic_year_date_display(d: date) -> str:
    """e.g. 31 May 2025"""
    return f"{d.day} {d.strftime('%B')} {d.year}"


def format_academic_year_range(start: date, end: date) -> str:
    return f"{format_academic_year_date_display(start)} - {format_academic_year_date_display(end)}"


def parse_academic_year_date(s: str) -> date:
    return parse_payment_date_dmY(s)


def is_standard_academic_year_bounds(start: date, end: date) -> bool:
    return (
        start.month == 5
        and start.day == 31
        and end.month == 6
        and end.day == 1
        and end.year == start.year + 1
    )


def academic_year_bounds_for_start_year(start_year: int) -> tuple[date, date]:
    """2025-2026 → 31 May 2025 through 1 June 2026."""
    return date(int(start_year), 5, 31), date(int(start_year) + 1, 6, 1)


def academic_year_start_year_for_date(d: date) -> int:
    """Calendar year that begins the academic year containing *d*."""
    y = d.year
    if d < date(y, 5, 31):
        return y - 1
    if d.month == 6 and d.day > 1:
        return y
    if d.month > 6:
        return y
    if d.month == 5 and d.day >= 31:
        return y
    if d.month == 6 and d.day <= 1:
        return y - 1
    return y - 1


def auto_label_for_range(start: date, end: date) -> str:
    """Label e.g. 2025-2026 for standard May 31 → 1 June ranges."""
    if is_standard_academic_year_bounds(start, end):
        return f"{start.year}-{end.year}"
    if end.year == start.year:
        return str(start.year)
    return format_academic_year_range(start, end)


def academic_year_short_label(start: date, end: date) -> str:
    """Compact label for dropdowns, e.g. 2025-2026."""
    return auto_label_for_range(start, end)


def default_academic_year_bounds(as_of: date | None = None) -> tuple[date, date]:
    d = as_of or date.today()
    start_year = academic_year_start_year_for_date(d)
    return academic_year_bounds_for_start_year(start_year)
