"""Display formatting for salary month labels stored as YYYY-MM."""

from datetime import date


def format_month_label_display(month_label: str) -> str:
    """Convert YYYY-MM (e.g. 2026-05) to a readable label (e.g. May 2026)."""
    text = (month_label or "").strip()
    if not text:
        return ""
    if len(text) == 7 and text[4] == "-":
        year_text, month_text = text[:4], text[5:]
        if year_text.isdigit() and month_text.isdigit():
            month_num = int(month_text)
            if 1 <= month_num <= 12:
                return date(int(year_text), month_num, 1).strftime("%B %Y")
    return text
