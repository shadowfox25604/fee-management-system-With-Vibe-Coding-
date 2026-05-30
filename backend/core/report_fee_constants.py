"""Fee status filters for the Reports tab."""

from backend.core.fee_due_display import pending_fees as combined_pending_fees

FEE_FILTER_PENDING_DUE = "pending_due"
FEE_FILTER_CURRENT_YEAR = "current_year_due"
FEE_FILTER_PAID = "paid"

REPORT_FEE_FILTER_LABELS: dict[str, str] = {
    FEE_FILTER_PENDING_DUE: "Pending fees due",
    FEE_FILTER_CURRENT_YEAR: "Fees due (current year)",
    FEE_FILTER_PAID: "Fees paid",
}

REPORT_FEE_FILTER_ORDER: tuple[str, ...] = (
    FEE_FILTER_PENDING_DUE,
    FEE_FILTER_CURRENT_YEAR,
    FEE_FILTER_PAID,
)

_EPS = 0.01


def current_year_total(due: dict) -> float:
    fee_due = float(due.get("fee_due", 0) or 0)
    van_due = float(due.get("van_due", 0) or 0)
    return fee_due + van_due


def has_pending_fees_due(due: dict) -> bool:
    """Prior-year balances still outstanding (current-year balance ignored for inclusion)."""
    return combined_pending_fees(due) > _EPS


def has_current_year_fees_due(due: dict) -> bool:
    """Pending fees cleared; current academic year still has balance."""
    return combined_pending_fees(due) <= _EPS and current_year_total(due) > _EPS


def is_fully_paid(due: dict) -> bool:
    """No pending fees and no current-year fees remaining."""
    return combined_pending_fees(due) <= _EPS and current_year_total(due) <= _EPS


def matches_fee_filter(due: dict, fee_status: str) -> bool:
    if fee_status == FEE_FILTER_PENDING_DUE:
        return has_pending_fees_due(due)
    if fee_status == FEE_FILTER_CURRENT_YEAR:
        return has_current_year_fees_due(due)
    if fee_status == FEE_FILTER_PAID:
        return is_fully_paid(due)
    return False


def amount_for_fee_filter(due: dict, fee_status: str) -> float:
    if fee_status == FEE_FILTER_PENDING_DUE:
        return combined_pending_fees(due)
    if fee_status == FEE_FILTER_CURRENT_YEAR:
        return current_year_total(due)
    return 0.0


def report_amount_column_label(fee_status: str | None) -> str:
    if not fee_status:
        return "Total due"
    if fee_status == FEE_FILTER_PENDING_DUE:
        return "Pending fees due"
    if fee_status == FEE_FILTER_CURRENT_YEAR:
        return "Due (current year)"
    if fee_status == FEE_FILTER_PAID:
        return "Status"
    return "Amount"
