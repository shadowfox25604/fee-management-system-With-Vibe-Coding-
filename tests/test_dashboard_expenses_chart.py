from datetime import date, datetime, timedelta

import pytest

from backend.services.expense_service import ExpenseService
from backend.services.misc_expense_service import MiscExpenseService


def test_daily_misc_expenses_chart_groups_by_entry_date(db_session):
    misc = MiscExpenseService(db_session)
    expense = misc.add_new_expense("Rent", date(2026, 5, 6))
    misc.add_entry(expense.id, "May rent", 30000.0, entry_date=date(2026, 5, 10))
    misc.add_entry(expense.id, "Extra", 5000.0, entry_date=date(2026, 5, 10))

    daily = misc.daily_misc_chart_for_month(2026, 5)
    assert daily["amounts"][9] == pytest.approx(35000.0, abs=0.01)
    assert sum(daily["amounts"]) == pytest.approx(35000.0, abs=0.01)


def test_daily_salary_expenses_chart_keeps_payout_and_reversal_dates(db_session):
    svc = ExpenseService(db_session)
    faculty = svc.assign_faculty_salary("Ravi Kumar", 30000.0, default_working_days=25)
    pay_day = date.today() - timedelta(days=1)
    entry = svc.record_salary_from_attendance(
        faculty.id,
        attendance_days=20,
        working_days=25,
        month_label=pay_day.strftime("%Y-%m"),
        expense_date=pay_day,
    )
    svc.undo_salary_payment(entry.reference_no)
    row = svc.repo.session.get(type(entry), entry.id)
    assert row is not None
    row.reverted_at = datetime.combine(date.today(), datetime.min.time())
    svc.repo.session.commit()

    daily = svc.daily_salary_chart_for_month(date.today().year, date.today().month)
    paid_idx = pay_day.day - 1
    rev_idx = date.today().day - 1
    assert daily["amounts"][paid_idx] == pytest.approx(float(entry.amount), abs=0.01)
    assert daily["reverted_amounts"][rev_idx] == pytest.approx(float(entry.amount), abs=0.01)


def test_merge_daily_charts_combines_salary_and_misc(db_session):
    expense_svc = ExpenseService(db_session)
    misc_svc = MiscExpenseService(db_session)
    faculty = expense_svc.assign_faculty_salary("Ravi Kumar", 30000.0, default_working_days=25)
    pay_day = date(2026, 5, 12)
    expense_svc.record_salary_from_attendance(
        faculty.id,
        attendance_days=20,
        working_days=25,
        month_label="2026-05",
        expense_date=pay_day,
    )
    misc_expense = misc_svc.add_new_expense("Stationary", date(2026, 5, 6))
    misc_svc.add_entry(misc_expense.id, "Forms", 1000.0, entry_date=pay_day)

    merged = ExpenseService.merge_daily_charts(
        expense_svc.daily_salary_chart_for_month(2026, 5),
        misc_svc.daily_misc_chart_for_month(2026, 5),
    )
    assert merged["amounts"][11] == pytest.approx(24000.0 + 1000.0, abs=0.01)
