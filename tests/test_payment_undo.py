from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import func, select

from backend.models import FeeHead, Invoice, Payment, Student
from backend.repositories.payment_repository import PaymentRepository
from backend.services.payment_service import PaymentService


def _fee_heads(session):
    tuition = session.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "tuition")).first()
    transport = session.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "transport")).first()
    if tuition is None:
        tuition = FeeHead(head_name="Tuition", frequency="monthly", default_amount=2000.0)
        session.add(tuition)
    if transport is None:
        transport = FeeHead(head_name="Transport", frequency="monthly", default_amount=500.0)
        session.add(transport)
    session.flush()
    return tuition, transport


def test_undo_payment_reverts_due_and_marks_history(db_session):
    pay_day = date.today() - timedelta(days=1)
    tuition, transport = _fee_heads(db_session)
    st = Student(
        student_id="UNDO001",
        full_name="Undo Student",
        class_name="6",
        section="A",
        phone="9000000001",
        guardian_name="Parent",
        van_fees=1000.0,
        school_fees=5000.0,
    )
    db_session.add(st)
    db_session.commit()
    db_session.refresh(st)

    db_session.add(
        Invoice(
            student_id_fk=st.student_id,
            fee_head_id=tuition.id,
            period_label="2026-01",
                due_date=pay_day,
            amount_due=5000.0,
            amount_paid=0.0,
        )
    )
    db_session.add(
        Invoice(
            student_id_fk=st.student_id,
            fee_head_id=transport.id,
            period_label="2026-01",
                due_date=pay_day,
            amount_due=1000.0,
            amount_paid=0.0,
        )
    )
    db_session.commit()

    repo = PaymentRepository(db_session)
    svc = PaymentService(db_session)
    pay = repo.create_split_payment(
        st,
        van_amount=200.0,
        school_amount=300.0,
        mode="cash",
        operator_name="tester",
        discount_amount=50.0,
            payment_date=pay_day,
    )

    due_after_payment = repo.get_student_due_breakdown(st.student_id)
    assert due_after_payment["total"] == pytest.approx(5400.0, abs=0.01)

    reverted = svc.undo_payment(pay.reference_no)
    assert bool(reverted.is_reverted) is True

    due_after_undo = repo.get_student_due_breakdown(st.student_id)
    assert due_after_undo["total"] == pytest.approx(6000.0, abs=0.01)
    assert due_after_undo["school_payable"] == pytest.approx(5000.0, abs=0.01)
    assert due_after_undo["van_payable"] == pytest.approx(1000.0, abs=0.01)

    history_all = svc.list_payment_history(limit=100, include_reverted=True)
    row = next((r for r in history_all if r.get("reference_no") == pay.reference_no), None)
    assert row is not None
    assert row["status"] == "Payment reverted"
    assert row["is_reverted"] is True

    history_live = svc.list_payment_history(limit=100, include_reverted=False)
    assert all(r.get("reference_no") != pay.reference_no for r in history_live)

    payment_row = db_session.scalars(select(Payment).where(Payment.reference_no == pay.reference_no)).first()
    assert payment_row is not None
    assert bool(payment_row.is_reverted) is True


def test_undo_payment_cannot_run_twice(db_session):
    pay_day = date.today() - timedelta(days=1)
    tuition, _transport = _fee_heads(db_session)
    st = Student(
        student_id="UNDO002",
        full_name="Undo Twice Student",
        class_name="5",
        section="A",
        phone="9000000002",
        guardian_name="Parent",
        van_fees=0.0,
        school_fees=2000.0,
    )
    db_session.add(st)
    db_session.commit()
    db_session.refresh(st)

    db_session.add(
        Invoice(
            student_id_fk=st.student_id,
            fee_head_id=tuition.id,
            period_label="2026-01",
                due_date=pay_day,
            amount_due=2000.0,
            amount_paid=0.0,
        )
    )
    db_session.commit()

    repo = PaymentRepository(db_session)
    pay = repo.create_split_payment(
        st,
        van_amount=0.0,
        school_amount=500.0,
        mode="cash",
        operator_name="tester",
        discount_amount=0.0,
            payment_date=pay_day,
    )
    repo.undo_payment(pay.reference_no)
    with pytest.raises(ValueError, match="already reverted"):
        repo.undo_payment(pay.reference_no)


def test_daily_chart_shows_reversion_on_original_payment_date(db_session):
    pay_day = date.today() - timedelta(days=1)
    tuition, _transport = _fee_heads(db_session)
    st = Student(
        student_id="UNDO003",
        full_name="Undo Chart Student",
        class_name="4",
        section="B",
        phone="9000000003",
        guardian_name="Parent",
        van_fees=0.0,
        school_fees=3000.0,
    )
    db_session.add(st)
    db_session.commit()
    db_session.refresh(st)

    db_session.add(
        Invoice(
            student_id_fk=st.student_id,
            fee_head_id=tuition.id,
            period_label="2026-01",
            due_date=pay_day,
            amount_due=3000.0,
            amount_paid=0.0,
        )
    )
    db_session.commit()

    repo = PaymentRepository(db_session)
    pay = repo.create_split_payment(
        st,
        van_amount=0.0,
        school_amount=500.0,
        mode="cash",
        operator_name="tester",
        discount_amount=100.0,
        payment_date=pay_day,
    )
    reverted = repo.undo_payment(pay.reference_no)
    assert reverted.reverted_at is not None

    # Reversion happens today, but the chart should attribute it to the payment date.
    payment_row = db_session.scalars(select(Payment).where(Payment.reference_no == pay.reference_no)).first()
    assert payment_row is not None
    payment_row.reverted_at = datetime.combine(date.today(), datetime.min.time())
    db_session.commit()

    daily = repo.daily_cash_collected_for_month(date.today().year, date.today().month)
    collected = daily["amounts"]
    reverted_amounts = daily["reverted_amounts"]
    assert len(collected) == len(reverted_amounts)

    pay_idx = pay_day.day - 1
    rev_idx = date.today().day - 1
    assert collected[pay_idx] == pytest.approx(0.0, abs=0.01)
    assert reverted_amounts[pay_idx] == pytest.approx(500.0, abs=0.01)
    assert collected[pay_idx] + reverted_amounts[pay_idx] == pytest.approx(500.0, abs=0.01)
    if rev_idx != pay_idx:
        assert reverted_amounts[rev_idx] == pytest.approx(0.0, abs=0.01)
        assert collected[rev_idx] == pytest.approx(0.0, abs=0.01)


def test_dashboard_collected_week_ignores_reversions_for_prior_week_payments(db_session):
    """Reverting an older payment this week must not reduce Amount Collected This Week."""
    tuition, _transport = _fee_heads(db_session)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    prior_week_day = week_start - timedelta(days=1)

    st = Student(
        student_id="WEEK001",
        full_name="Week Stats Student",
        class_name="5",
        section="A",
        phone="9000000010",
        guardian_name="Parent",
        van_fees=0.0,
        school_fees=5000.0,
    )
    db_session.add(st)
    db_session.commit()
    db_session.refresh(st)

    db_session.add(
        Invoice(
            student_id_fk=st.student_id,
            fee_head_id=tuition.id,
            period_label="2026-01",
            due_date=prior_week_day,
            amount_due=5000.0,
            amount_paid=0.0,
        )
    )
    db_session.commit()

    repo = PaymentRepository(db_session)
    pay = repo.create_split_payment(
        st,
        van_amount=0.0,
        school_amount=5000.0,
        mode="cash",
        operator_name="tester",
        discount_amount=0.0,
        payment_date=prior_week_day,
    )
    repo.undo_payment(pay.reference_no)

    payment_row = db_session.scalars(select(Payment).where(Payment.reference_no == pay.reference_no)).first()
    assert payment_row is not None
    payment_row.reverted_at = datetime.combine(today, datetime.min.time())
    db_session.commit()

    period = PaymentService(db_session).dashboard_period_stats(week_start, today)
    assert period["collected_week"] == pytest.approx(0.0, abs=0.01)
