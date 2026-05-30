"""Display helpers for student fee due breakdowns."""


def pending_fees(due: dict | None) -> float:
    """Combined prior-year school + van balance (pending fees)."""
    if not due:
        return 0.0
    if "pending_fees" in due:
        return float(due.get("pending_fees") or 0)
    return float(due.get("school_pending", 0) or 0) + float(due.get("van_pending", 0) or 0)
