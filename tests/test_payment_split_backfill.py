from datetime import date

import pytest
from sqlalchemy import func, select

from backend.models import FeeHead, Payment, Student
from backend.repositories.payment_repository import PaymentRepository, infer_payment_split_amounts


def test_infer_payment_split_legacy_lump_sum():
    school, van = infer_payment_split_amounts(10000.0, 0.0)
    assert school == pytest.approx(10000.0)
    assert van == pytest.approx(0.0)


def test_infer_payment_split_with_discount():
    school, van = infer_payment_split_amounts(4000.0, 1000.0)
    assert school == pytest.approx(3000.0)
    assert van == pytest.approx(0.0)


def test_infer_payment_split_from_allocations():
    school, van = infer_payment_split_amounts(
        4000.0,
        1000.0,
        school_allocated=0.0,
        van_allocated=4000.0,
    )
    assert school == pytest.approx(0.0)
    assert van == pytest.approx(3000.0)


def test_backfill_legacy_payment_splits(db_session):
    st = Student(
        student_id="BF001",
        full_name="Backfill Student",
        class_name="1",
        section="A",
        phone="9000000099",
        guardian_name="Parent",
        school_fees=10000.0,
        van_fees=0.0,
    )
    db_session.add(st)
    db_session.commit()

    payment = Payment(
        student_id_fk=st.student_id,
        payment_date=date.today(),
        amount=5000.0,
        school_amount=0.0,
        van_amount=0.0,
        discount_amount=500.0,
        mode="cash",
        reference_no="BACKFILLTEST01",
        operator_name="tester",
        is_reverted=False,
    )
    db_session.add(payment)
    db_session.commit()

    repo = PaymentRepository(db_session)
    updated = repo.backfill_legacy_payment_splits()
    assert updated >= 1
    db_session.refresh(payment)
    assert payment.school_amount == pytest.approx(4500.0)
    assert payment.van_amount == pytest.approx(0.0)

    rows = repo.list_recent_payments_with_students(search="BF001", include_reverted=True)
    row = next(r for r in rows if r["reference_no"] == "BACKFILLTEST01")
    assert row["school_amount"] == pytest.approx(4500.0)
    assert row["van_amount"] == pytest.approx(0.0)
