from datetime import date

import pytest
from sqlalchemy import select

from backend.models import Expense, FacultyAttendance, FacultySalary
from backend.services.expense_service import ExpenseService


def test_assign_faculty_salary_upserts_existing_name(db_session):
    svc = ExpenseService(db_session)
    first = svc.assign_faculty_salary(
        "Anita Devi",
        25000.0,
        faculty_type="Teaching",
        role="Science",
        default_working_days=26,
    )
    second = svc.assign_faculty_salary(
        "anita devi",
        28000.0,
        faculty_type="non-teaching",
        role="Senior Science",
        default_working_days=24,
    )

    assert first.id == second.id
    assert float(second.monthly_salary) == 28000.0
    assert int(second.default_working_days) == 24
    assert str(second.faculty_type) == "Non Teaching"
    rows = db_session.scalars(select(FacultySalary)).all()
    assert len(rows) == 1


def test_faculty_lists_can_filter_by_type(db_session):
    svc = ExpenseService(db_session)
    svc.assign_faculty_salary("Rahul Das", 26000.0, faculty_type="Teaching", role="Math")
    svc.assign_faculty_salary("Nisha Paul", 22000.0, faculty_type="Non Teaching", role="Admin")

    teaching = svc.list_faculty_salaries(faculty_type="Teaching")
    non_teaching = svc.list_faculty_salaries(faculty_type="Non Teaching")

    assert len(teaching) == 1
    assert teaching[0].faculty_name == "Rahul Das"
    assert len(non_teaching) == 1
    assert non_teaching[0].faculty_name == "Nisha Paul"


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


def test_mark_attendance_persists_for_month(db_session):
    svc = ExpenseService(db_session)
    faculty = svc.assign_faculty_salary(
        "Nirmala",
        31000.0,
        role="Office",
        default_working_days=26,
    )
    payload = svc.save_faculty_attendance(
        faculty.id,
        year=2026,
        month=5,
        marked_days=[1, 2, 2, 31, 99],
    )

    assert payload["month_label"] == "2026-05"
    assert payload["checked_days"] == 3
    assert payload["sunday_days"] == 5
    assert payload["attendance_days"] == pytest.approx(8.0, abs=0.01)
    stored = svc.get_saved_faculty_attendance(faculty.id, year=2026, month=5)
    assert stored["marked_days"] == [1, 2, 31]
    rows = db_session.scalars(select(FacultyAttendance)).all()
    assert len(rows) == 1


def test_salary_from_marked_attendance_is_calculated_not_saved(db_session):
    svc = ExpenseService(db_session)
    faculty = svc.assign_faculty_salary(
        "Prakash",
        31000.0,
        role="Teacher",
        default_working_days=26,
    )
    svc.save_faculty_attendance(
        faculty.id,
        year=2026,
        month=5,
        marked_days=[1, 2, 4, 5, 6],
    )
    before_count = len(db_session.scalars(select(Expense).where(Expense.expense_type == "salary")).all())

    payload = svc.get_saved_faculty_attendance(
        faculty.id,
        year=2026,
        month=5,
    )
    calc = svc.calculate_salary_for_faculty(
        faculty.id,
        attendance_days=float(payload["attendance_days"]),
        working_days=float(payload["working_days"]),
    )

    assert payload["checked_days"] == 5
    assert payload["sunday_days"] == 5
    assert payload["attendance_days"] == pytest.approx(10.0, abs=0.01)
    assert payload["working_days"] == pytest.approx(31.0, abs=0.01)
    assert calc["payable_amount"] == pytest.approx(10000.0, abs=0.01)
    after_count = len(db_session.scalars(select(Expense).where(Expense.expense_type == "salary")).all())
    assert after_count == before_count
