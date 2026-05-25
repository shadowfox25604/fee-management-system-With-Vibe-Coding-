from datetime import date

import pytest
from sqlalchemy import select

from backend.models import Expense, FacultySalary
from backend.services.expense_service import ExpenseService


def test_assign_faculty_salary_upserts_existing_name(db_session):
    svc = ExpenseService(db_session)
    first = svc.assign_faculty_salary(
        "Anita Devi",
        25000.0,
        role="Science",
        default_working_days=26,
    )
    second = svc.assign_faculty_salary(
        "anita devi",
        28000.0,
        role="Senior Science",
        default_working_days=24,
    )

    assert first.id == second.id
    assert float(second.monthly_salary) == 28000.0
    assert int(second.default_working_days) == 24
    rows = db_session.scalars(select(FacultySalary)).all()
    assert len(rows) == 1


def test_record_salary_from_attendance_creates_salary_expense(db_session):
    svc = ExpenseService(db_session)
    faculty = svc.assign_faculty_salary(
        "Ravi Kumar",
        30000.0,
        role="English",
        default_working_days=25,
    )

    entry = svc.record_salary_from_attendance(
        faculty.id,
        attendance_days=20,
        working_days=25,
        month_label="2026-05",
        expense_date=date(2026, 5, 31),
        notes="May salary payout",
    )

    assert entry.expense_type == "salary"
    assert entry.person_name == "Ravi Kumar"
    assert float(entry.base_amount) == 30000.0
    assert float(entry.amount) == 24000.0
    assert svc.salary_total("2026-05") == pytest.approx(24000.0, abs=0.01)


def test_other_expense_totals_grouped_by_category(db_session):
    svc = ExpenseService(db_session)
    svc.add_other_expense("Rent", 10000.0, expense_date=date(2026, 5, 2), description="Building rent")
    svc.add_other_expense("Donation", 1500.0, expense_date=date(2026, 5, 4), notes="Local event support")
    svc.add_other_expense("Stationary", 500.0, expense_date=date(2026, 5, 6), description="Registers")

    totals = svc.other_totals()
    assert totals["total"] == pytest.approx(12000.0, abs=0.01)
    assert totals["by_category"]["Rent"] == pytest.approx(10000.0, abs=0.01)
    assert totals["by_category"]["Donation"] == pytest.approx(1500.0, abs=0.01)
    assert totals["by_category"]["Stationary"] == pytest.approx(500.0, abs=0.01)
    rows = db_session.scalars(select(Expense).where(Expense.expense_type == "other")).all()
    assert len(rows) == 3


def test_salary_calc_rejects_attendance_above_working_days(db_session):
    svc = ExpenseService(db_session)
    with pytest.raises(ValueError, match="greater than working days"):
        svc.calculate_salary_amount(30000.0, attendance_days=28, working_days=26)
