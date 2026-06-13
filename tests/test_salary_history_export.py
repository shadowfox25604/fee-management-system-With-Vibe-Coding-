from datetime import date

import pytest

from backend.services.expense_service import ExpenseService


def _seed_faculty(svc: ExpenseService, name: str, *, salary: float = 30000.0, employee_id: str | None = None):
    return svc.assign_faculty_salary(
        name,
        salary,
        employee_id=employee_id or svc.suggest_next_faculty_employee_id(),
        role="Teacher",
        default_working_days=25,
    )


def test_salary_history_filter_by_month(db_session):
    svc = ExpenseService(db_session)
    f1 = _seed_faculty(svc, "Ravi Kumar")
    f2 = _seed_faculty(svc, "Priya Singh")
    svc.record_salary_from_attendance(
        f1.id,
        attendance_days=20,
        working_days=25,
        month_label="2026-04",
        expense_date=date(2026, 4, 30),
    )
    svc.record_salary_from_attendance(
        f2.id,
        attendance_days=20,
        working_days=25,
        month_label="2026-05",
        expense_date=date(2026, 5, 31),
    )

    rows = svc.list_salary_history(month=(2026, 4), include_reverted=True)
    assert len(rows) == 1
    assert rows[0]["faculty_name"] == "Ravi Kumar"


def test_salary_history_filter_by_date_range(db_session):
    svc = ExpenseService(db_session)
    f1 = _seed_faculty(svc, "Ravi Kumar")
    f2 = _seed_faculty(svc, "Priya Singh")
    svc.record_salary_from_attendance(
        f1.id,
        attendance_days=20,
        working_days=25,
        month_label="2026-04",
        expense_date=date(2026, 4, 10),
    )
    svc.record_salary_from_attendance(
        f2.id,
        attendance_days=20,
        working_days=25,
        month_label="2026-05",
        expense_date=date(2026, 5, 10),
    )

    rows = svc.list_salary_history(
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 30),
        include_reverted=True,
    )
    assert len(rows) == 1
    assert rows[0]["faculty_name"] == "Ravi Kumar"


def test_salary_history_filter_by_faculty_names(db_session):
    svc = ExpenseService(db_session)
    f1 = _seed_faculty(svc, "Ravi Kumar")
    f2 = _seed_faculty(svc, "Priya Singh")
    pay_day = date(2026, 5, 15)
    svc.record_salary_from_attendance(
        f1.id,
        attendance_days=20,
        working_days=25,
        month_label="2026-05",
        expense_date=pay_day,
    )
    svc.record_salary_from_attendance(
        f2.id,
        attendance_days=20,
        working_days=25,
        month_label="2026-05",
        expense_date=pay_day,
    )

    rows = svc.list_salary_history(
        faculty_names=["Ravi Kumar"],
        include_reverted=True,
    )
    assert len(rows) == 1
    assert rows[0]["faculty_name"] == "Ravi Kumar"


def test_salary_history_export_excel(tmp_path, db_session):
    svc = ExpenseService(db_session)
    faculty = _seed_faculty(svc, "Ravi Kumar")
    svc.record_salary_from_attendance(
        faculty.id,
        attendance_days=20,
        working_days=25,
        month_label="2026-05",
        expense_date=date(2026, 5, 31),
    )

    out = tmp_path / "salary-history.xlsx"
    svc.export_salary_history_excel(out, include_reverted=True)
    assert out.exists()
    assert out.stat().st_size > 0


def test_list_salary_export_faculty_names(db_session):
    svc = ExpenseService(db_session)
    f1 = _seed_faculty(svc, "Ravi Kumar")
    _seed_faculty(svc, "Priya Singh")
    svc.record_salary_from_attendance(
        f1.id,
        attendance_days=20,
        working_days=25,
        month_label="2026-05",
        expense_date=date(2026, 5, 31),
    )

    names = svc.list_salary_export_faculty_names()
    assert "Ravi Kumar" in names
    assert "Priya Singh" in names
