from datetime import date

import pytest

from backend.models import Expense
from backend.services.expense_service import ExpenseService


def test_undo_salary_payment_reverts_and_keeps_history(db_session):
    svc = ExpenseService(db_session)
    faculty = svc.assign_faculty_salary(
        "Undo Faculty",
        26000.0,
        employee_id="Fac1",
        role="Math",
        default_working_days=26,
    )
    entry = svc.record_salary_from_attendance(
        faculty.id,
        attendance_days=20,
        working_days=26,
        month_label="2026-06",
        expense_date=date(2026, 6, 15),
        notes="June payout",
    )
    ref = entry.reference_no
    assert ref
    assert svc.salary_total("2026-06") == pytest.approx(float(entry.amount), abs=0.01)

    reverted = svc.undo_salary_payment(ref)
    assert bool(reverted.is_reverted) is True
    assert svc.salary_total("2026-06") == pytest.approx(0.0, abs=0.01)

    history_all = svc.list_salary_history(limit=100, include_reverted=True)
    row = next(h for h in history_all if h["reference_no"] == ref)
    assert row["status"] == "Salary reverted"
    assert row["is_reverted"] is True

    history_live = svc.list_salary_history(limit=100, include_reverted=False)
    assert ref not in {h["reference_no"] for h in history_live}


def test_undo_salary_payment_cannot_run_twice(db_session):
    svc = ExpenseService(db_session)
    faculty = svc.assign_faculty_salary(
        "Undo Twice",
        24000.0,
        employee_id="Fac1",
        default_working_days=26,
    )
    entry = svc.record_salary_from_attendance(
        faculty.id,
        attendance_days=26,
        working_days=26,
        month_label="2026-07",
        expense_date=date(2026, 7, 1),
    )
    svc.undo_salary_payment(entry.reference_no)
    with pytest.raises(ValueError, match="already reverted"):
        svc.undo_salary_payment(entry.reference_no)
