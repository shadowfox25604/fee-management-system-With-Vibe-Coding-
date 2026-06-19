"""Rules and copy for deleting students from the admin UI."""

from __future__ import annotations

from backend.core.fee_control_constants import is_passed_out_class
from backend.core.fee_due_display import pending_fees
from backend.core.student_enrollment import student_is_inactive
from backend.models import Student


def student_delete_requires_extended_warnings(student: Student, pending_amount: float | None = None) -> bool:
    """True when active status or any pending fees require a two-step delete flow."""
    pending = float(pending_amount if pending_amount is not None else 0.0)
    if pending > 0:
        return True
    status = (getattr(student, "status", None) or "active").strip().lower()
    return status == "active"


def student_delete_summary_lines(student: Student, due: dict | None) -> list[str]:
    """Human-readable bullets for delete confirmation dialogs."""
    due = due or {}
    pending = pending_fees(due)
    total = float(due.get("total") or 0.0)
    status = (getattr(student, "status", None) or "active").strip().title() or "Active"
    lines = [
        f"Roll number: {getattr(student, 'student_id', '')}",
        f"Name: {getattr(student, 'full_name', '')}",
        f"Class: {getattr(student, 'class_name', '')}-{getattr(student, 'section', '')}",
        f"Status: {status}",
    ]
    if is_passed_out_class(getattr(student, "class_name", None)):
        lines.append("Passed out: Yes")
    if pending > 0:
        lines.append(f"Pending fees: ₹{pending:,.2f}")
    if total > 0:
        lines.append(f"Total amount due: ₹{total:,.2f}")
    lines.extend(
        [
            "",
            "Deleting will permanently remove:",
            "• Payment and invoice history",
            "• Academic year fee records",
            "• All fee plans for this student",
        ]
    )
    if student_is_inactive(student) and pending <= 0:
        lines.append("")
        lines.append("This student is inactive with no pending fees.")
    return lines
