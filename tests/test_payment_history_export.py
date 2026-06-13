from datetime import date, timedelta

import pytest

from backend.models import Student
from backend.services.academic_year_service import AcademicYearService
from backend.services.payment_service import PaymentService


def _seed_student(session, *, student_id: str = "S001", class_name: str = "1") -> Student:
    student = Student(
        student_id=student_id,
        full_name="Test Student",
        class_name=class_name,
        section="A",
        phone="9000000001",
        guardian_name="Parent",
        school_fees=20000.0,
        van_fees=0.0,
    )
    session.add(student)
    session.commit()
    session.refresh(student)
    return student


def test_payment_history_filter_by_month(db_session):
    svc = PaymentService(db_session)
    student = _seed_student(db_session)
    pay_b = date.today() - timedelta(days=60)
    pay_a = date.today() - timedelta(days=10)
    svc.repo.create_payment(student, 1000.0, "cash", "admin", payment_date=pay_b)
    svc.repo.create_payment(student, 500.0, "cash", "admin", payment_date=pay_a)

    older_rows = svc.list_payment_history(
        month=(pay_b.year, pay_b.month),
        include_reverted=True,
    )
    assert len(older_rows) == 1
    assert older_rows[0]["amount"] == pytest.approx(1000.0, abs=0.01)


def test_payment_history_filter_by_class(db_session):
    svc = PaymentService(db_session)
    s1 = _seed_student(db_session, student_id="S001", class_name="1")
    s2 = _seed_student(db_session, student_id="S002", class_name="2")
    svc.repo.create_payment(s1, 1000.0, "cash", "admin", payment_date=date.today() - timedelta(days=3))
    svc.repo.create_payment(s2, 800.0, "cash", "admin", payment_date=date.today() - timedelta(days=2))

    rows = svc.list_payment_history(class_name="1", include_reverted=True)
    assert len(rows) == 1
    assert rows[0]["student_roll"] == "S001"


def test_payment_history_filter_by_multiple_classes(db_session):
    svc = PaymentService(db_session)
    s1 = _seed_student(db_session, student_id="S001", class_name="1")
    s2 = _seed_student(db_session, student_id="S002", class_name="2")
    s3 = _seed_student(db_session, student_id="S003", class_name="LKG")
    pay_day = date.today() - timedelta(days=2)
    svc.repo.create_payment(s1, 1000.0, "cash", "admin", payment_date=pay_day)
    svc.repo.create_payment(s2, 800.0, "cash", "admin", payment_date=pay_day)
    svc.repo.create_payment(s3, 500.0, "cash", "admin", payment_date=pay_day)

    rows = svc.list_payment_history(class_names=["1", "2"], include_reverted=True)
    assert len(rows) == 2
    rolls = {row["student_roll"] for row in rows}
    assert rolls == {"S001", "S002"}


def test_payment_history_filter_by_academic_year(db_session):
    svc = PaymentService(db_session)
    year_svc = AcademicYearService(db_session)
    year = year_svc.repo.ensure_bootstrap_year()
    student = _seed_student(db_session)
    svc.repo.create_payment(student, 1200.0, "cash", "admin", payment_date=year.start_date)

    rows = svc.list_payment_history(academic_year_id=year.id, include_reverted=True)
    assert len(rows) == 1


def test_payment_history_filter_by_student(db_session):
    svc = PaymentService(db_session)
    s1 = _seed_student(db_session, student_id="S001", class_name="1")
    s2 = _seed_student(db_session, student_id="S002", class_name="2")
    pay_day = date.today() - timedelta(days=1)
    svc.repo.create_payment(s1, 1000.0, "cash", "admin", payment_date=pay_day)
    svc.repo.create_payment(s2, 800.0, "cash", "admin", payment_date=pay_day)

    rows = svc.list_payment_history(student_id="S001", include_reverted=True)
    assert len(rows) == 1
    assert rows[0]["student_roll"] == "S001"


def test_payment_history_export_excel(tmp_path, db_session):
    svc = PaymentService(db_session)
    student = _seed_student(db_session)
    pay_day = date.today() - timedelta(days=1)
    svc.repo.create_payment(student, 1500.0, "cash", "admin", payment_date=pay_day)

    out = tmp_path / "payments.xlsx"
    svc.export_excel(out, include_reverted=True)
    assert out.exists()
    assert out.stat().st_size > 0


def test_academic_year_short_label():
    from backend.core.academic_year_dates import academic_year_short_label

    assert academic_year_short_label(date(2025, 5, 31), date(2026, 6, 1)) == "2025-2026"
    assert academic_year_short_label(date(2026, 6, 1), date(2027, 6, 4)) == "1 June 2026 - 4 June 2027"
