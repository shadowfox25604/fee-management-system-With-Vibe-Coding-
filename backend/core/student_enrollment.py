"""Enrollment helpers: inactive / passed-out students and academic-year fee rules."""

from backend.core.fee_control_constants import is_passed_out_class
from backend.models import Student


def student_is_inactive_status(status: str | None) -> bool:
    """True when status is inactive (left school / not enrolled for year increment)."""
    return (status or "").strip().lower() == "inactive"


def student_is_inactive(student: Student) -> bool:
    return student_is_inactive_status(getattr(student, "status", None))


def student_skips_academic_year_fee_provisioning(student: Student) -> bool:
    """Inactive or passed-out students must not receive new year fees on increment."""
    return is_passed_out_class(getattr(student, "class_name", None)) or student_is_inactive(student)
