"""Display helpers for student fee due breakdowns."""


def pending_fees(due: dict | None) -> float:
    """Combined prior-year school + van balance (pending fees)."""
    if not due:
        return 0.0
    if "pending_fees" in due:
        return float(due.get("pending_fees") or 0)
    return float(due.get("school_pending", 0) or 0) + float(due.get("van_pending", 0) or 0)


def combine_rollover_pending_fees(
    existing_pending: float,
    current_school_due: float,
    current_van_due: float,
) -> float:
    """New pending fees when an academic year rolls forward.

    new pending = existing pending + current-year school due + current-year van due
    """
    return max(
        0.0,
        float(existing_pending or 0.0)
        + float(current_school_due or 0.0)
        + float(current_van_due or 0.0),
    )


def rollover_pending_from_due(due: dict | None) -> float:
    """Compute consolidated pending from a pre-rollover due breakdown."""
    if not due:
        return 0.0
    return combine_rollover_pending_fees(
        pending_fees(due),
        float(due.get("fee_due", due.get("school_current", 0)) or 0.0),
        float(due.get("van_due", due.get("van_current", 0)) or 0.0),
    )
