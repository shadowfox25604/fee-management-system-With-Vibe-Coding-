"""Payment date as DD/MM/YYYY (day first, then month, then year).

The desktop UI uses slashes (dd/MM/yyyy) in the date picker, which matches this convention.
"""

from datetime import date, datetime


def format_payment_date_dmY(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def parse_payment_date_dmY(s: str) -> date:
    raw = (s or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("Date of payment is required. Use DD/MM/YYYY, for example 12/05/2026.")
    try:
        return datetime.strptime(raw, "%d/%m/%Y").date()
    except ValueError as e:
        raise ValueError(
            "Date of payment must be in DD/MM/YYYY format (day/month/year), for example 12/05/2026 or 12\\05\\2026."
        ) from e
