import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import func, or_, select

from backend.core.database import Base
import backend.core.database as db
from backend.core.schema_migrations import (
    apply_sqlite_column_migrations,
    apply_sqlite_data_migrations,
)
from backend.models import ClassSchoolFee, FeeHead, Invoice, Payment, Student, entities  # noqa: F401
from backend.repositories.class_fee_repository import ClassFeeRepository
from backend.core.payment_reference import REF_LEN, is_compact_payment_reference
from backend.repositories.payment_repository import PaymentRepository
def test_class_name_matches_query_exact_not_substring():
    from backend.core.fee_control_constants import (
        class_name_matches_query,
        class_section_matches_query,
    )

    assert class_name_matches_query("1", "1")
    assert not class_name_matches_query("10", "1")
    assert not class_name_matches_query("11", "1")
    assert class_name_matches_query("10", "10")
    assert class_name_matches_query("LKG", "lkg")

    assert class_section_matches_query("1", "A", "1")
    assert not class_section_matches_query("10", "A", "1")
    assert class_section_matches_query("10", "B", "10-b")
    assert not class_section_matches_query("10", "A", "10-b")


def test_schema_and_student_creation():
    Base.metadata.create_all(bind=db.engine)
    apply_sqlite_column_migrations(db.engine)
    apply_sqlite_data_migrations(db.engine)
    s=db.SessionLocal()
    try:
        sid = f"TST{uuid.uuid4().hex[:8].upper()}"
        st=Student(student_id=sid, full_name="Test User", class_name="8", section="A", phone=f"9{uuid.uuid4().int % 10**9:09d}", guardian_name="Guardian")
        s.add(st); s.commit(); assert st.student_id is not None
        assert float(st.van_fees) == 0.0
        assert float(st.school_fees) == 20000.0
        assert getattr(st, "village", None) == ""
        assert (getattr(st, "transport_mode", None) or "van") == "van"
    finally:
        s.close()


def test_create_student_own_transport_zeros_van_fee():
    Base.metadata.create_all(bind=db.engine)
    apply_sqlite_column_migrations(db.engine)
    apply_sqlite_data_migrations(db.engine)
    s = db.SessionLocal()
    try:
        from backend.repositories.village_van_fee_repository import VillageVanFeeRepository
        from backend.services.student_service import StudentService
        from backend.services.village_van_fee_service import VillageVanFeeService

        VillageVanFeeRepository(s).upsert_stored_amount("Nagaram", 4500.0)
        s.commit()

        ss = StudentService(s)
        vfs = VillageVanFeeService(s)
        sid = f"OWN{uuid.uuid4().hex[:8].upper()}"
        st = ss.create_student(
            sid,
            "Own Transport Test",
            "5",
            "A",
            f"8{uuid.uuid4().int % 10**9:09d}",
            village="Nagaram",
            guardian_name="G Name",
            gender="Male",
            father_name="G Name",
            status="active",
            transport_mode="own",
            village_fee_service=vfs,
            class_fee_service=None,
        )
        assert st.transport_mode == "own"
        assert float(st.van_fees) == 0.0

        sid2 = f"VAN{uuid.uuid4().hex[:8].upper()}"
        st2 = ss.create_student(
            sid2,
            "Van Transport Test",
            "5",
            "A",
            f"7{uuid.uuid4().int % 10**9:09d}",
            village="Nagaram",
            guardian_name="G Name",
            gender="Male",
            father_name="G Name",
            status="active",
            transport_mode="van",
            village_fee_service=vfs,
            class_fee_service=None,
        )
        assert st2.transport_mode == "van"
        assert float(st2.van_fees) == 4500.0
    finally:
        s.close()


def test_split_payment_top_up_when_invoices_smaller_than_tariff():
    """Tariff-based due can exceed open invoice lines; split pay must still allocate (payment-sized top-up)."""
    Base.metadata.create_all(bind=db.engine)
    apply_sqlite_column_migrations(db.engine)
    apply_sqlite_data_migrations(db.engine)
    s = db.SessionLocal()
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
                student_id_fk=st.student_id,
                fee_head_id=tr.id,
                period_label="2026-01",
                due_date=d,
                amount_due=500.0,
                amount_paid=0.0,
            )
        )
        s.add(
            Invoice(
                student_id_fk=st.student_id,
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
            select(Invoice).where(
                Invoice.student_id_fk == st.student_id,
                or_(
                    Invoice.period_label.like("Collect top-up%"),
                    Invoice.period_label.like("Tariff sync%"),
                ),
            )
        ).all()
        assert len(top_ups) >= 1

        payments = s.scalars(select(Payment).where(Payment.student_id_fk == st.student_id)).all()
        assert len(payments) == 1
        assert payments[0].reference_no
        assert is_compact_payment_reference(payments[0].reference_no)
        assert len(payments[0].reference_no.strip()) == REF_LEN
    finally:
        s.close()


def test_split_payment_with_discount_records_total_amount():
    Base.metadata.create_all(bind=db.engine)
    apply_sqlite_column_migrations(db.engine)
    apply_sqlite_data_migrations(db.engine)
    s = db.SessionLocal()
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
                student_id_fk=st.student_id,
                fee_head_id=tr.id,
                period_label="2026-01",
                due_date=d,
                amount_due=2000.0,
                amount_paid=0.0,
            )
        )
        s.add(
            Invoice(
                student_id_fk=st.student_id,
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
        assert float(pay.amount) == 3500.0
        due_after = repo.get_student_due_breakdown(st.student_id)
        assert due_after["fee_due"] == 8500.0  # tariff school due minus cash + discount applied to school
        assert due_after["school_payable"] == 8000.0  # payable reduced by cash + cumulative discount
        assert due_after["van_due"] == 3000.0
        assert due_after["total"] == 11000.0
    finally:
        s.close()


def test_split_payment_school_fully_covered_by_discount_stores_sum_in_payment_amount():
    """School + van + discount is stored on Payment.amount; invoices still allocate school and van lines."""
    Base.metadata.create_all(bind=db.engine)
    apply_sqlite_column_migrations(db.engine)
    apply_sqlite_data_migrations(db.engine)
    s = db.SessionLocal()
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

        sid = f"Z0{uuid.uuid4().hex[:8].upper()}"
        st = Student(
            student_id=sid,
            full_name="Zero Net Discount Test",
            class_name="3",
            section="A",
            phone=f"4{uuid.uuid4().int % 10**9:09d}",
            guardian_name="G",
            van_fees=0.0,
            school_fees=20000.0,
        )
        s.add(st)
        s.commit()
        s.refresh(st)

        d = date(2026, 7, 1)
        s.add(
            Invoice(
                student_id_fk=st.student_id,
                fee_head_id=t.id,
                period_label="2026-01",
                due_date=d,
                amount_due=20000.0,
                amount_paid=0.0,
            )
        )
        s.commit()

        repo = PaymentRepository(s)
        pay = repo.create_split_payment(
            st,
            van_amount=0.0,
            school_amount=1000.0,
            mode="cash",
            operator_name="test",
            discount_amount=1000.0,
        )
        assert float(pay.discount_amount) == 1000.0
        assert float(pay.amount) == 2000.0
        inv = s.scalars(select(Invoice).where(Invoice.student_id_fk == st.student_id)).first()
        assert float(inv.amount_paid) == 2000.0
    finally:
        s.close()


def test_orphan_discount_on_non_school_allocation_does_not_reduce_school_payable():
    """Discount stored on a payment must be credited to school invoices to reduce school payable."""
    Base.metadata.create_all(bind=db.engine)
    apply_sqlite_column_migrations(db.engine)
    apply_sqlite_data_migrations(db.engine)
    s = db.SessionLocal()
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

        sid = f"OD{uuid.uuid4().hex[:8].upper()}"
        st = Student(
            student_id=sid,
            full_name="Orphan Discount Test",
            class_name="7",
            section="B",
            phone=f"7{uuid.uuid4().int % 10**9:09d}",
            guardian_name="G",
            van_fees=5272.73,
            school_fees=20000.0,
        )
        s.add(st)
        s.commit()
        s.refresh(st)

        from backend.repositories.academic_year_repository import AcademicYearRepository
        from backend.repositories.student_year_fee_repository import StudentYearFeeRepository

        ay_repo = AcademicYearRepository(s)
        for row in ay_repo.list_all():
            s.delete(row)
        s.commit()
        y_cur = ay_repo.create(date(2026, 5, 16), date(2027, 5, 31), "2026-27")
        s.commit()
        StudentYearFeeRepository(s).get_or_create(st, y_cur.id, school_fees=20000.0, van_fees=5272.73)
        s.commit()

        pay_day = date(2026, 5, 19)
        van_inv = Invoice(
            student_id_fk=st.student_id,
            academic_year_id=y_cur.id,
            fee_head_id=tr.id,
            period_label="van",
            due_date=pay_day,
            amount_due=5272.73,
            amount_paid=0.0,
        )
        school_inv = Invoice(
            student_id_fk=st.student_id,
            academic_year_id=y_cur.id,
            fee_head_id=t.id,
            period_label="school",
            due_date=pay_day,
            amount_due=20000.0,
            amount_paid=0.0,
        )
        s.add(van_inv)
        s.add(school_inv)
        s.commit()
        s.refresh(van_inv)

        repo = PaymentRepository(s)
        payment = Payment(
            student_id_fk=st.student_id,
            payment_date=pay_day,
            amount=4000.0,
            school_amount=0.0,
            van_amount=0.0,
            discount_amount=1000.0,
            mode="cash",
            reference_no=repo.new_payment_reference(),
            operator_name="test",
            is_reverted=False,
        )
        s.add(payment)
        s.flush()
        repo._allocate_to_invoices(int(payment.id), 4000.0, [van_inv])
        s.commit()

        due = repo.get_student_due_breakdown(st.student_id)
        assert repo.get_students_cumulative_payment_discount([st.student_id]).get(st.student_id, 0.0) == 0.0
        assert due["school_payable"] == pytest.approx(20000.0, abs=0.01)
        assert due["van_payable"] == pytest.approx(1272.73, abs=0.01)
    finally:
        s.close()


def test_school_payment_can_clear_pending_van_before_current_school():
    """School fee payment applies to all pending dues first, then current-year school fees."""
    Base.metadata.create_all(bind=db.engine)
    apply_sqlite_column_migrations(db.engine)
    apply_sqlite_data_migrations(db.engine)
    s = db.SessionLocal()
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

        from backend.repositories.academic_year_repository import AcademicYearRepository

        ay_repo = AcademicYearRepository(s)
        for row in ay_repo.list_all():
            s.delete(row)
        s.commit()
        y_prev = ay_repo.create(date(2025, 5, 17), date(2026, 5, 15), "2025-26")
        y_cur = ay_repo.create(date(2026, 6, 1), date(2027, 6, 4), "2026-27")
        s.commit()

        sid = f"SC{uuid.uuid4().hex[:8].upper()}"
        st = Student(
            student_id=sid,
            full_name="Pending First School Pay",
            class_name="7",
            section="B",
            phone=f"8{uuid.uuid4().int % 10**9:09d}",
            guardian_name="G",
            van_fees=5272.73,
            school_fees=20000.0,
            created_at=datetime(2025, 8, 1),
        )
        s.add(st)
        s.commit()
        s.refresh(st)

        from backend.repositories.student_year_fee_repository import StudentYearFeeRepository

        sy = StudentYearFeeRepository(s)
        sy.get_or_create(st, y_prev.id, school_fees=0.0, van_fees=5272.73)
        sy.get_or_create(st, y_cur.id, school_fees=20000.0, van_fees=5272.73)
        s.commit()

        pay_day = date(2026, 6, 3)
        s.add(
            Invoice(
                student_id_fk=st.student_id,
                academic_year_id=y_prev.id,
                fee_head_id=tr.id,
                period_label="prev van",
                due_date=pay_day,
                amount_due=5272.73,
                amount_paid=4000.0,
            )
        )
        s.add(
            Invoice(
                student_id_fk=st.student_id,
                academic_year_id=y_cur.id,
                fee_head_id=t.id,
                period_label="cur school",
                due_date=pay_day,
                amount_due=20000.0,
                amount_paid=2545.73,
            )
        )
        s.add(
            Invoice(
                student_id_fk=st.student_id,
                academic_year_id=y_cur.id,
                fee_head_id=tr.id,
                period_label="cur van",
                due_date=pay_day,
                amount_due=5272.73,
                amount_paid=0.0,
            )
        )
        s.commit()

        repo = PaymentRepository(s)
        due = repo.get_student_due_breakdown(st.student_id)
        assert due["school_payable"] == pytest.approx(18727.0, abs=0.01)
        repo.validate_split_payment_inputs(st, 0.0, 18000.0, 0.0, pay_day)
        pay = repo.create_split_payment(st, 0.0, 18000.0, "cash", "test", 0.0, pay_day)
        assert float(pay.school_amount) == pytest.approx(18000.0, abs=0.01)
        after = repo.get_student_due_breakdown(st.student_id)
        assert after["pending_fees"] == pytest.approx(0.0, abs=0.01)
        assert after["fee_due"] == pytest.approx(727.0, abs=0.02)
    finally:
        s.close()


def test_split_payment_stores_explicit_payment_date():
    Base.metadata.create_all(bind=db.engine)
    apply_sqlite_column_migrations(db.engine)
    apply_sqlite_data_migrations(db.engine)
    s = db.SessionLocal()
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
                student_id_fk=st.student_id,
                fee_head_id=tr.id,
                period_label="2026-01",
                due_date=d_inv,
                amount_due=500.0,
                amount_paid=0.0,
            )
        )
        s.add(
            Invoice(
                student_id_fk=st.student_id,
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
        assert float(pay.amount) == 300.0
        assert float(pay.discount_amount) == 0.0
    finally:
        s.close()


def test_split_payment_rejects_future_payment_date():
    Base.metadata.create_all(bind=db.engine)
    apply_sqlite_column_migrations(db.engine)
    apply_sqlite_data_migrations(db.engine)
    s = db.SessionLocal()
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
                student_id_fk=st.student_id,
                fee_head_id=tr.id,
                period_label="2026-01",
                due_date=d_inv,
                amount_due=500.0,
                amount_paid=0.0,
            )
        )
        s.add(
            Invoice(
                student_id_fk=st.student_id,
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
    Base.metadata.create_all(bind=db.engine)
    apply_sqlite_column_migrations(db.engine)
    apply_sqlite_data_migrations(db.engine)
    s = db.SessionLocal()
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
        # Current-year due is tariff minus paid; invoice open balance does not inflate display.
        s.add(
            Invoice(
                student_id_fk=st.student_id,
                fee_head_id=t.id,
                period_label="inv1",
                due_date=d,
                amount_due=6000.0,
                amount_paid=0.0,
            )
        )
        s.add(
            Invoice(
                student_id_fk=st.student_id,
                fee_head_id=tr.id,
                period_label="v1",
                due_date=d,
                amount_due=200.0,
                amount_paid=0.0,
            )
        )
        s.commit()

        repo = PaymentRepository(s)
        due = repo.get_student_due_breakdown(st.student_id)
        assert due["fee_due"] == 5000.0
        assert due["van_due"] == 1000.0
    finally:
        s.close()


def test_parse_payment_date_accepts_slash_or_backslash():
    from backend.core.payment_date_format import parse_payment_date_dmY

    assert parse_payment_date_dmY("10/02/2026") == date(2026, 2, 10)
    assert parse_payment_date_dmY("10\\02\\2026") == date(2026, 2, 10)


def test_class_fee_apply_updates_students_scales_tuition_leaves_transport_invoices():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.core.database import Base

    mem = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=mem)
    apply_sqlite_column_migrations(mem)
    apply_sqlite_data_migrations(mem)
    MemSession = sessionmaker(bind=mem, autoflush=False, autocommit=False)
    s = MemSession()
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

        sid = f"CF{uuid.uuid4().hex[:8].upper()}"
        st = Student(
            student_id=sid,
            full_name="Class Fee Test",
            class_name="5",
            section="A",
            phone=f"3{uuid.uuid4().int % 10**9:09d}",
            guardian_name="G",
            van_fees=3000.0,
            school_fees=20000.0,
        )
        s.add(st)
        s.commit()
        s.refresh(st)

        d = date(2026, 4, 1)
        inv_s = Invoice(
            student_id_fk=st.student_id,
            fee_head_id=t.id,
            period_label="2026-01",
            due_date=d,
            amount_due=10000.0,
            amount_paid=0.0,
        )
        inv_v = Invoice(
            student_id_fk=st.student_id,
            fee_head_id=tr.id,
            period_label="2026-01",
            due_date=d,
            amount_due=500.0,
            amount_paid=0.0,
        )
        s.add(inv_s)
        s.add(inv_v)
        s.commit()

        from backend.models import AcademicYear, StudentAcademicYearFee
        from backend.repositories.academic_year_repository import AcademicYearRepository

        ay_repo = AcademicYearRepository(s)
        year = ay_repo.ensure_bootstrap_year()
        s.add(
            StudentAcademicYearFee(
                student_id_fk=st.student_id,
                academic_year_id=year.id,
                school_fees=20000.0,
                van_fees=3000.0,
            )
        )
        inv_s.academic_year_id = year.id
        s.commit()

        cfr = ClassFeeRepository(s)
        n = cfr.apply_class_school_fee("5", 25000.0, year.id)
        assert n == 1

        st2 = s.get(Student, st.student_id)
        assert float(st2.school_fees) == 25000.0
        assert float(st2.van_fees) == 3000.0

        s.refresh(inv_s)
        s.refresh(inv_v)
        assert float(inv_s.amount_due) == 12500.0
        assert float(inv_v.amount_due) == 500.0

        row = s.get(ClassSchoolFee, ("5", year.id))
        assert row is not None
        assert float(row.amount) == 25000.0

        pay_repo = PaymentRepository(s)
        due = pay_repo.get_student_due_breakdown(st.student_id)
        assert due["van_due"] == 3000.0
    finally:
        s.close()


def test_village_van_fee_apply_updates_students_scales_transport_leaves_tuition_invoices():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.core.database import Base
    from backend.models import VillageVanFee
    from backend.repositories.village_van_fee_repository import VillageVanFeeRepository

    mem = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=mem)
    apply_sqlite_column_migrations(mem)
    apply_sqlite_data_migrations(mem)
    MemSession = sessionmaker(bind=mem, autoflush=False, autocommit=False)
    s = MemSession()
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

        sid = f"VF{uuid.uuid4().hex[:8].upper()}"
        st = Student(
            student_id=sid,
            full_name="Village Van Fee Test",
            class_name="5",
            section="A",
            phone=f"2{uuid.uuid4().int % 10**9:09d}",
            guardian_name="G",
            village="Nagaram",
            van_fees=3000.0,
            school_fees=20000.0,
        )
        s.add(st)
        s.commit()
        s.refresh(st)

        d = date(2026, 4, 1)
        inv_s = Invoice(
            student_id_fk=st.student_id,
            fee_head_id=t.id,
            period_label="2026-01",
            due_date=d,
            amount_due=10000.0,
            amount_paid=0.0,
        )
        inv_v = Invoice(
            student_id_fk=st.student_id,
            fee_head_id=tr.id,
            period_label="2026-01",
            due_date=d,
            amount_due=500.0,
            amount_paid=0.0,
        )
        s.add(inv_s)
        s.add(inv_v)
        s.commit()

        vfr = VillageVanFeeRepository(s)
        n = vfr.apply_village_van_fee("Nagaram", 4500.0)
        assert n == 1

        st2 = s.get(Student, st.student_id)
        assert float(st2.van_fees) == 4500.0
        assert float(st2.school_fees) == 20000.0

        s.refresh(inv_s)
        s.refresh(inv_v)
        assert float(inv_s.amount_due) == 10000.0
        assert float(inv_v.amount_due) == 750.0

        row = s.get(VillageVanFee, "Nagaram")
        assert row is not None
        assert float(row.amount) == 4500.0

        pay_repo = PaymentRepository(s)
        due = pay_repo.get_student_due_breakdown(st.student_id)
        assert due["fee_due"] == 20000.0
    finally:
        s.close()


def test_payment_receipt_pdf_writes_valid_pdf(tmp_path):
    from datetime import datetime

    from backend.reports.payment_receipt_pdf import render_payment_receipt

    out = tmp_path / "receipt.pdf"
    render_payment_receipt(
        out,
        student_name="Receipt Student",
        roll_number="STU9999",
        class_name="6",
        section="A",
        guardian_name="Parent Name",
        school_fees_paid=1000.0,
        van_fees_paid=500.0,
        discount=100.0,
        receipt_no="ABCD12345678",
        generated_at=datetime(2026, 5, 14, 14, 30, 0),
    )
    assert out.is_file()
    data = out.read_bytes()
    assert data[:4] == b"%PDF"
    assert len(data) > 2000


def test_create_split_rejects_discount_greater_than_school_amount():
    Base.metadata.create_all(bind=db.engine)
    apply_sqlite_column_migrations(db.engine)
    apply_sqlite_data_migrations(db.engine)
    s = db.SessionLocal()
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

        sid = f"DC{uuid.uuid4().hex[:8].upper()}"
        st = Student(
            student_id=sid,
            full_name="Discount Cap Test",
            class_name="2",
            section="A",
            phone=f"1{uuid.uuid4().int % 10**9:09d}",
            guardian_name="G",
            van_fees=1000.0,
            school_fees=5000.0,
        )
        s.add(st)
        s.commit()
        s.refresh(st)

        d = date(2026, 9, 1)
        s.add(
            Invoice(
                student_id_fk=st.student_id,
                fee_head_id=t.id,
                period_label="2026-01",
                due_date=d,
                amount_due=5000.0,
                amount_paid=0.0,
            )
        )
        s.add(
            Invoice(
                student_id_fk=st.student_id,
                fee_head_id=tr.id,
                period_label="2026-01",
                due_date=d,
                amount_due=500.0,
                amount_paid=0.0,
            )
        )
        s.commit()

        repo = PaymentRepository(s)
        with pytest.raises(ValueError, match="Discount cannot exceed"):
            repo.create_split_payment(
                st,
                van_amount=0.0,
                school_amount=100.0,
                mode="cash",
                operator_name="test",
                discount_amount=150.0,
            )
    finally:
        s.close()


def test_payment_service_collect_split_delegates_to_repo():
    from backend.services.payment_service import PaymentService

    Base.metadata.create_all(bind=db.engine)
    apply_sqlite_column_migrations(db.engine)
    apply_sqlite_data_migrations(db.engine)
    s = db.SessionLocal()
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

        sid = f"PS{uuid.uuid4().hex[:8].upper()}"
        st = Student(
            student_id=sid,
            full_name="Service Split Test",
            class_name="7",
            section="C",
            phone=f"0{uuid.uuid4().int % 10**9:09d}",
            guardian_name="G",
            van_fees=500.0,
            school_fees=3000.0,
        )
        s.add(st)
        s.commit()
        s.refresh(st)

        d_inv = date(2026, 10, 1)
        s.add(
            Invoice(
                student_id_fk=st.student_id,
                fee_head_id=t.id,
                period_label="2026-01",
                due_date=d_inv,
                amount_due=3000.0,
                amount_paid=0.0,
            )
        )
        s.add(
            Invoice(
                student_id_fk=st.student_id,
                fee_head_id=tr.id,
                period_label="2026-01",
                due_date=d_inv,
                amount_due=500.0,
                amount_paid=0.0,
            )
        )
        s.commit()

        pay_day = date(2026, 1, 15)
        svc = PaymentService(s)
        pay = svc.collect_split_payment(
            st,
            van_amount=100.0,
            school_amount=200.0,
            mode="card",
            operator_name="svc_op",
            discount_amount=50.0,
            payment_date=pay_day,
        )
        assert float(pay.amount) == 350.0
        assert pay.mode == "card"
        assert pay.operator_name == "svc_op"
    finally:
        s.close()


def test_dashboard_period_stats_match_sql():
  """Dashboard tiles use SQL aggregates (not limited payment list scans)."""
  Base.metadata.create_all(bind=db.engine)
  apply_sqlite_column_migrations(db.engine)
  apply_sqlite_data_migrations(db.engine)
  s = db.SessionLocal()
  try:
    from backend.services.payment_service import PaymentService
    from backend.services.student_service import StudentService

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    active, inactive = StudentService(s).count_active_inactive()
    period = PaymentService(s).dashboard_period_stats(week_start, today)

    active_db = s.scalar(
      select(func.count()).select_from(Student).where(func.lower(Student.status) == "active")
    ) or 0
    inactive_db = s.scalar(
      select(func.count()).select_from(Student).where(func.lower(Student.status) != "active")
    ) or 0
    collected_db = float(
      s.scalar(
        select(func.coalesce(func.sum(Payment.amount - Payment.discount_amount), 0.0)).where(
          Payment.payment_date >= week_start,
          Payment.payment_date <= today,
          or_(Payment.is_reverted.is_(False), Payment.is_reverted.is_(None)),
        )
      )
      or 0.0
    )
    week_count_db = s.scalar(
      select(func.count())
      .select_from(Payment)
      .where(Payment.payment_date >= week_start, Payment.payment_date <= today)
    ) or 0
    today_count_db = s.scalar(
      select(func.count()).select_from(Payment).where(Payment.payment_date == today)
    ) or 0

    assert active == active_db
    assert inactive == inactive_db
    assert period["collected_week"] == collected_db
    assert period["payments_week"] == week_count_db
    assert period["payments_today"] == today_count_db
  finally:
    s.close()


def test_daily_cash_collected_for_month_excludes_discount():
  Base.metadata.create_all(bind=db.engine)
  apply_sqlite_column_migrations(db.engine)
  apply_sqlite_data_migrations(db.engine)
  s = db.SessionLocal()
  try:
    from backend.services.payment_service import PaymentService

    sid = f"CHT{uuid.uuid4().hex[:8].upper()}"
    st = Student(
      student_id=sid,
      full_name="Chart Student",
      class_name="5",
      section="A",
      phone=f"6{uuid.uuid4().int % 10**9:09d}",
      guardian_name="Guardian",
    )
    s.add(st)
    s.commit()
    pay_day = date(2026, 5, 15)
    s.add(
      Payment(
        student_id_fk=st.student_id,
        payment_date=pay_day,
        amount=350.0,
        discount_amount=50.0,
        mode="cash",
        reference_no=PaymentRepository(s).new_payment_reference(),
      )
    )
    s.commit()
    daily = PaymentService(s).daily_cash_collected_for_month(2026, 5)
    assert daily["days_in_month"] == 31
    assert daily["amounts"][14] == 300.0
    assert daily["amounts"][0] == 0.0
  finally:
    s.close()
