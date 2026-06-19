"""Tests for Delete Member backend and policy."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import func, select

from backend.core.member_delete_policy import student_delete_requires_extended_warnings
from backend.models import (
    Expense,
    FacultyAttendance,
    FacultySalary,
    FeeHead,
    Invoice,
    Payment,
    Student,
    StudentAcademicYearFee,
    entities,  # noqa: F401
)
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.services.expense_service import ExpenseService
from backend.services.student_service import StudentService


def _fee_heads(session):
    t = session.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "tuition")).first()
    if t is None:
        t = FeeHead(head_name="Tuition", frequency="monthly", default_amount=2000.0)
        session.add(t)
    session.flush()
    return t


def test_student_delete_requires_extended_warnings():
    active = Student(student_id="A1", full_name="Active", class_name="5", section="A", phone="9000000001")
    inactive = Student(
        student_id="I1", full_name="Inactive", class_name="5", section="A", phone="9000000002", status="inactive"
    )
    assert student_delete_requires_extended_warnings(active, 0.0) is True
    assert student_delete_requires_extended_warnings(inactive, 100.0) is True
    assert student_delete_requires_extended_warnings(inactive, 0.0) is False


def test_delete_student_cascade(db_session):
    _fee_heads(db_session)
    ay = AcademicYearRepository(db_session).ensure_bootstrap_year()
    sid = f"DEL{uuid.uuid4().hex[:6].upper()}"
    st = Student(
        student_id=sid,
        full_name="Delete Me",
        class_name="5",
        section="A",
        phone=f"9{uuid.uuid4().int % 10**9:09d}",
        guardian_name="G",
        status="inactive",
    )
    db_session.add(st)
    db_session.flush()
    fh = _fee_heads(db_session)
    db_session.add(
        StudentAcademicYearFee(
            student_id_fk=sid,
            academic_year_id=ay.id,
            school_fees=5000.0,
            van_fees=0.0,
        )
    )
    db_session.add(
        Invoice(
            student_id_fk=sid,
            academic_year_id=ay.id,
            fee_head_id=fh.id,
            period_label="2026",
            due_date=date.today(),
            amount_due=1000.0,
            amount_paid=0.0,
        )
    )
    db_session.add(
        Payment(
            student_id_fk=sid,
            payment_date=date.today(),
            amount=100.0,
            school_amount=100.0,
            van_amount=0.0,
            discount_amount=0.0,
            mode="cash",
            reference_no=f"REF{uuid.uuid4().hex[:8].upper()}",
        )
    )
    db_session.commit()

    name = StudentService(db_session).delete_student(sid)
    assert name == "Delete Me"
    assert db_session.get(Student, sid) is None
    assert db_session.scalars(select(Invoice).where(Invoice.student_id_fk == sid)).first() is None
    assert db_session.scalars(select(Payment).where(Payment.student_id_fk == sid)).first() is None
    assert db_session.scalars(
        select(StudentAcademicYearFee).where(StudentAcademicYearFee.student_id_fk == sid)
    ).first() is None


def test_delete_student_not_found(db_session):
    with pytest.raises(ValueError, match="not found"):
        StudentService(db_session).delete_student("MISSING999")


def test_purge_faculty_by_employee_id(db_session):
    fac = FacultySalary(
        employee_id=f"FAC{uuid.uuid4().hex[:4].upper()}",
        faculty_name=f"Faculty {uuid.uuid4().hex[:4]}",
        faculty_type="Teaching",
        monthly_salary=15000.0,
        is_active=True,
    )
    db_session.add(fac)
    db_session.flush()
    db_session.add(
        FacultyAttendance(
            faculty_id_fk=int(fac.id),
            month_label="2026-06",
            attendance_days=20.0,
            working_days=26.0,
        )
    )
    db_session.add(
        Expense(
            expense_type="salary",
            category="Salary",
            person_name=fac.faculty_name,
            amount=15000.0,
            expense_date=date.today(),
        )
    )
    db_session.commit()
    eid = fac.employee_id

    result = ExpenseService(db_session).purge_faculty_by_employee_id(eid)
    assert result["faculty_deleted"] == 1
    assert result["attendance_deleted"] == 1
    assert result["salary_expenses_deleted"] == 1
    assert db_session.scalars(
        select(FacultySalary).where(FacultySalary.employee_id == eid)
    ).first() is None
