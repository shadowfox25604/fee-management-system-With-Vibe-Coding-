import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.core.database import Base, SessionLocal, engine
from app.core.schema_migrations import (
    apply_sqlite_column_migrations,
    apply_sqlite_data_migrations,
)
from app.models import FeeHead, Invoice, Payment, Student, entities  # noqa: F401
from app.repositories.payment_repository import PaymentRepository


def test_schema_and_student_creation():
    Base.metadata.create_all(bind=engine)
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    s=SessionLocal()
    try:
        sid = f"TST{uuid.uuid4().hex[:8].upper()}"
        st=Student(student_id=sid, full_name="Test User", class_name="8", section="A", phone=f"9{uuid.uuid4().int % 10**9:09d}", guardian_name="Guardian")
        s.add(st); s.commit(); assert st.id is not None
        assert float(st.van_fees) == 0.0
        assert float(st.school_fees) == 20000.0
        assert getattr(st, "village", None) == ""
    finally:
        s.close()


def test_split_payment_top_up_when_invoices_smaller_than_tariff():
    """Tariff-based due can exceed open invoice lines; split pay must still allocate (payment-sized top-up)."""
    Base.metadata.create_all(bind=engine)
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    s = SessionLocal()
    try:
        t = s.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "tuition")).first()
        tr = s.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "transport")).first()
        if t is None:
            t = FeeHead(head_name="Tuition", frequency="monthly", default_amount=2000.0)
            s.add(t)
        if tr is None:
            tr = FeeHead(head_name="Transport", frequency="monthly", default_amount=500.0)
            s.add(tr)
        s.flush()

        sid = f"SP{uuid.uuid4().hex[:8].upper()}"
        st = Student(
            student_id=sid,
            full_name="Split Pay Test",
            class_name="5",
            section="A",
            phone=f"8{uuid.uuid4().int % 10**9:09d}",
            guardian_name="G",
            van_fees=7000.0,
            school_fees=20000.0,
        )
        s.add(st)
        s.commit()
        s.refresh(st)

        d = date(2026, 6, 15)
        s.add(
            Invoice(
                student_id_fk=st.id,
                fee_head_id=tr.id,
                period_label="2026-01",
                due_date=d,
                amount_due=500.0,
                amount_paid=0.0,
            )
        )
        s.add(
            Invoice(
                student_id_fk=st.id,
                fee_head_id=t.id,
                period_label="2026-01",
                due_date=d,
                amount_due=1000.0,
                amount_paid=0.0,
            )
        )
        s.commit()

        repo = PaymentRepository(s)
        pay = repo.create_split_payment(st, van_amount=4000.0, school_amount=5000.0, mode="cash", operator_name="test")
        assert float(pay.amount) == 9000.0
        assert float(pay.discount_amount) == 0.0

        top_ups = s.scalars(
            select(Invoice).where(Invoice.student_id_fk == st.id, Invoice.period_label.like("Collect top-up%"))
        ).all()
        assert len(top_ups) >= 1

        payments = s.scalars(select(Payment).where(Payment.student_id_fk == st.id)).all()
        assert len(payments) == 1
    finally:
        s.close()


def test_split_payment_with_discount_records_net_amount():
    Base.metadata.create_all(bind=engine)
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    s = SessionLocal()
    try:
        t = s.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "tuition")).first()
        tr = s.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "transport")).first()
        if t is None:
            t = FeeHead(head_name="Tuition", frequency="monthly", default_amount=2000.0)
            s.add(t)
        if tr is None:
            tr = FeeHead(head_name="Transport", frequency="monthly", default_amount=500.0)
            s.add(tr)
        s.flush()

        sid = f"SD{uuid.uuid4().hex[:8].upper()}"
        st = Student(
            student_id=sid,
            full_name="Discount Pay Test",
            class_name="4",
            section="C",
            phone=f"6{uuid.uuid4().int % 10**9:09d}",
            guardian_name="G",
            van_fees=5000.0,
            school_fees=10000.0,
        )
        s.add(st)
        s.commit()
        s.refresh(st)

        d = date(2026, 7, 1)
        s.add(
            Invoice(
                student_id_fk=st.id,
                fee_head_id=tr.id,
                period_label="2026-01",
                due_date=d,
                amount_due=2000.0,
                amount_paid=0.0,
            )
        )
        s.add(
            Invoice(
                student_id_fk=st.id,
                fee_head_id=t.id,
                period_label="2026-01",
                due_date=d,
                amount_due=3000.0,
                amount_paid=0.0,
            )
        )
        s.commit()

        repo = PaymentRepository(s)
        pay = repo.create_split_payment(
            st,
            van_amount=1000.0,
            school_amount=2000.0,
            mode="cash",
            operator_name="test",
            discount_amount=500.0,
        )
        assert float(pay.discount_amount) == 500.0
        assert float(pay.amount) == 2500.0
        due_after = repo.get_student_due_breakdown(st.id)
        assert due_after["fee_due"] == 7500.0
        assert due_after["van_due"] == 4000.0
        assert due_after["total"] == 11500.0
    finally:
        s.close()


def test_split_payment_stores_explicit_payment_date():
    Base.metadata.create_all(bind=engine)
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    s = SessionLocal()
    try:
        t = s.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "tuition")).first()
        tr = s.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "transport")).first()
        if t is None:
            t = FeeHead(head_name="Tuition", frequency="monthly", default_amount=2000.0)
            s.add(t)
        if tr is None:
            tr = FeeHead(head_name="Transport", frequency="monthly", default_amount=500.0)
            s.add(tr)
        s.flush()

        sid = f"PD{uuid.uuid4().hex[:8].upper()}"
        st = Student(
            student_id=sid,
            full_name="Payment Date Test",
            class_name="1",
            section="A",
            phone=f"5{uuid.uuid4().int % 10**9:09d}",
            guardian_name="G",
            van_fees=2000.0,
            school_fees=5000.0,
        )
        s.add(st)
        s.commit()
        s.refresh(st)

        d_inv = date(2026, 3, 1)
        s.add(
            Invoice(
                student_id_fk=st.id,
                fee_head_id=tr.id,
                period_label="2026-01",
                due_date=d_inv,
                amount_due=500.0,
                amount_paid=0.0,
            )
        )
        s.add(
            Invoice(
                student_id_fk=st.id,
                fee_head_id=t.id,
                period_label="2026-01",
                due_date=d_inv,
                amount_due=1000.0,
                amount_paid=0.0,
            )
        )
        s.commit()

        pay_day = date(2026, 2, 10)
        repo = PaymentRepository(s)
        pay = repo.create_split_payment(
            st,
            van_amount=100.0,
            school_amount=200.0,
            mode="cash",
            operator_name="test",
            payment_date=pay_day,
        )
        assert pay.payment_date == pay_day
    finally:
        s.close()


def test_split_payment_rejects_future_payment_date():
    Base.metadata.create_all(bind=engine)
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    s = SessionLocal()
    try:
        t = s.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "tuition")).first()
        tr = s.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "transport")).first()
        if t is None:
            t = FeeHead(head_name="Tuition", frequency="monthly", default_amount=2000.0)
            s.add(t)
        if tr is None:
            tr = FeeHead(head_name="Transport", frequency="monthly", default_amount=500.0)
            s.add(tr)
        s.flush()

        sid = f"PF{uuid.uuid4().hex[:8].upper()}"
        st = Student(
            student_id=sid,
            full_name="Future Date Test",
            class_name="2",
            section="B",
            phone=f"4{uuid.uuid4().int % 10**9:09d}",
            guardian_name="G",
            van_fees=2000.0,
            school_fees=5000.0,
        )
        s.add(st)
        s.commit()
        s.refresh(st)

        d_inv = date(2026, 3, 1)
        s.add(
            Invoice(
                student_id_fk=st.id,
                fee_head_id=tr.id,
                period_label="2026-01",
                due_date=d_inv,
                amount_due=500.0,
                amount_paid=0.0,
            )
        )
        s.add(
            Invoice(
                student_id_fk=st.id,
                fee_head_id=t.id,
                period_label="2026-01",
                due_date=d_inv,
                amount_due=1000.0,
                amount_paid=0.0,
            )
        )
        s.commit()

        repo = PaymentRepository(s)
        future = date.today() + timedelta(days=2)
        with pytest.raises(ValueError, match="future"):
            repo.create_split_payment(
                st,
                van_amount=100.0,
                school_amount=200.0,
                mode="cash",
                operator_name="test",
                payment_date=future,
            )
    finally:
        s.close()


def test_due_breakdown_is_max_of_tariff_and_invoice_open_balance():
    """Displayed due must not stay stuck at tariff when invoices show more (or less) open balance."""
    Base.metadata.create_all(bind=engine)
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    s = SessionLocal()
    try:
        t = s.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "tuition")).first()
        tr = s.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "transport")).first()
        if t is None:
            t = FeeHead(head_name="Tuition", frequency="monthly", default_amount=2000.0)
            s.add(t)
        if tr is None:
            tr = FeeHead(head_name="Transport", frequency="monthly", default_amount=500.0)
            s.add(tr)
        s.flush()

        sid = f"DD{uuid.uuid4().hex[:8].upper()}"
        st = Student(
            student_id=sid,
            full_name="Due Merge Test",
            class_name="3",
            section="B",
            phone=f"7{uuid.uuid4().int % 10**9:09d}",
            guardian_name="G",
            van_fees=1000.0,
            school_fees=5000.0,
        )
        s.add(st)
        s.commit()
        s.refresh(st)

        d = date(2026, 8, 1)
        # Tariff school fee_due = 5000, but invoices only 6000 open -> display should use 6000
        s.add(
            Invoice(
                student_id_fk=st.id,
                fee_head_id=t.id,
                period_label="inv1",
                due_date=d,
                amount_due=6000.0,
                amount_paid=0.0,
            )
        )
        s.add(
            Invoice(
                student_id_fk=st.id,
                fee_head_id=tr.id,
                period_label="v1",
                due_date=d,
                amount_due=200.0,
                amount_paid=0.0,
            )
        )
        s.commit()

        repo = PaymentRepository(s)
        due = repo.get_student_due_breakdown(st.id)
        assert due["fee_due"] == 6000.0
        assert due["van_due"] == 1000.0  # max(1000 tariff remainder, 200 invoice open)
    finally:
        s.close()


def test_parse_payment_date_accepts_slash_or_backslash():
    from app.core.payment_date_format import parse_payment_date_dmY

    assert parse_payment_date_dmY("10/02/2026") == date(2026, 2, 10)
    assert parse_payment_date_dmY("10\\02\\2026") == date(2026, 2, 10)
