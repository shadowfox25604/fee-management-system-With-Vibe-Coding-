"""Per-academic-year village van fee tariffs."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from backend.models import AcademicYear, Student
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.repositories.student_year_fee_repository import StudentYearFeeRepository
from backend.services.academic_year_service import AcademicYearService
from backend.services.class_fee_service import ClassFeeService
from backend.services.village_van_fee_service import VillageVanFeeService

from tests.academic_year_helpers import clear_all_academic_years


def _seed_year(db_session, start: date, end: date, label: str) -> AcademicYear:
    clear_all_academic_years(db_session)
    repo = AcademicYearRepository(db_session)
    year = repo.create(start, end, label)
    db_session.commit()
    return year


def test_village_fees_independent_per_academic_year(db_session):
    van_svc = VillageVanFeeService(db_session)
    y1 = _seed_year(db_session, date(2026, 5, 17), date(2027, 4, 18), "2026-27")
    repo = AcademicYearRepository(db_session)
    y2 = repo.create(date(2027, 5, 17), date(2028, 4, 18), "2027-28")
    db_session.commit()

    van_svc.repo.upsert_stored_amount("Nagaram", y1.id, 500.0)
    van_svc.repo.upsert_stored_amount("Nagaram", y2.id, 700.0)
    db_session.commit()

    assert van_svc.display_amount_for_village("Nagaram", y1.id) == pytest.approx(500.0)
    assert van_svc.display_amount_for_village("Nagaram", y2.id) == pytest.approx(700.0)
    assert van_svc.van_fees_for_village_name("Nagaram", y1.id) == pytest.approx(500.0)
    assert van_svc.van_fees_for_village_name("Nagaram", y2.id) == pytest.approx(700.0)


def test_apply_updates_village_year_row_not_other_years(db_session):
    van_svc = VillageVanFeeService(db_session)
    y1 = _seed_year(db_session, date(2027, 5, 17), date(2028, 4, 18), "2027-28")
    repo = AcademicYearRepository(db_session)
    y2 = repo.create(date(2028, 5, 17), date(2029, 4, 18), "2028-29")
    db_session.commit()

    van_svc.repo.upsert_stored_amount("Nagaram", y1.id, 500.0)
    van_svc.repo.upsert_stored_amount("Nagaram", y2.id, 700.0)
    db_session.commit()

    st = Student(
        student_id=f"VV-{uuid.uuid4().hex[:8]}",
        full_name="Village Year Student",
        class_name="5",
        section="A",
        phone="9876500002",
        guardian_name="G",
        village="Nagaram",
        school_fees=20000.0,
        van_fees=700.0,
        transport_mode="van",
    )
    db_session.add(st)
    db_session.commit()

    sy = StudentYearFeeRepository(db_session)
    sy.get_or_create(st, y1.id, school_fees=20000.0, van_fees=500.0)
    sy.get_or_create(st, y2.id, school_fees=20000.0, van_fees=700.0)
    db_session.commit()

    van_svc.apply_village_van_fee("Nagaram", 550.0, y1.id)

    row1 = sy.get(st.student_id, y1.id)
    row2 = sy.get(st.student_id, y2.id)
    assert row1 is not None and row1.van_fees == pytest.approx(550.0)
    assert row2 is not None and row2.van_fees == pytest.approx(700.0)


def test_new_year_copies_previous_village_tariffs(db_session):
    class_svc = ClassFeeService(db_session)
    van_svc = VillageVanFeeService(db_session)
    y1 = _seed_year(db_session, date(2026, 5, 17), date(2027, 4, 18), "2026-27")
    van_svc.repo.upsert_stored_amount("Nagaram", y1.id, 650.0)
    van_svc.repo.upsert_stored_amount("Ramapuram", y1.id, 800.0)
    db_session.commit()

    ay_svc = AcademicYearService(db_session)
    y2 = ay_svc.create_year(
        date(2027, 5, 17),
        date(2028, 4, 18),
        "2027-28",
        class_fee_service=class_svc,
        village_fee_service=van_svc,
        provision_students=False,
    )
    db_session.commit()

    assert van_svc.display_amount_for_village("Nagaram", y2.id) == pytest.approx(650.0)
    assert van_svc.display_amount_for_village("Ramapuram", y2.id) == pytest.approx(800.0)


def test_mid_year_class_change_copied_on_next_year(db_session):
    """Changes in the current year are the source for the next year's class tariffs."""
    class_svc = ClassFeeService(db_session)
    van_svc = VillageVanFeeService(db_session)
    y1 = _seed_year(db_session, date(2026, 5, 17), date(2027, 4, 18), "2026-27")
    class_svc.repo.upsert_stored_amount("5", y1.id, 20000.0)
    van_svc.repo.upsert_stored_amount("Nagaram", y1.id, 500.0)
    db_session.commit()

    class_svc.apply_class_school_fee("5", 22500.0, y1.id)
    van_svc.apply_village_van_fee("Nagaram", 575.0, y1.id)

    ay_svc = AcademicYearService(db_session)
    y2 = ay_svc.create_year(
        date(2027, 5, 17),
        date(2028, 4, 18),
        "2027-28",
        class_fee_service=class_svc,
        village_fee_service=van_svc,
        provision_students=False,
    )
    db_session.commit()

    assert class_svc.display_amount_for_class("5", y2.id) == pytest.approx(22500.0)
    assert van_svc.display_amount_for_village("Nagaram", y2.id) == pytest.approx(575.0)


def test_ended_year_village_tariffs_not_editable(db_session):
    van_svc = VillageVanFeeService(db_session)
    y1 = _seed_year(db_session, date(2023, 5, 17), date(2024, 4, 18), "2023-24")
    van_svc.repo.upsert_stored_amount("Nagaram", y1.id, 500.0)
    db_session.commit()

    assert van_svc.is_year_tariff_editable(y1.id, as_of=date(2026, 6, 1)) is False
    with pytest.raises(ValueError, match="ended"):
        van_svc.apply_village_van_fee("Nagaram", 600.0, y1.id)


def test_apply_village_van_fee_after_fee_head_bootstrap(db_session, isolated_test_database):
    """Apply creates transport invoices once default fee heads are bootstrapped."""
    from sqlalchemy import delete, func, select

    from backend.core.fee_head_bootstrap import ensure_default_fee_heads
    from backend.models import FeeHead, Invoice
    from backend.repositories.village_van_fee_repository import VillageVanFeeRepository

    db_session.execute(delete(FeeHead))
    db_session.commit()
    assert db_session.scalars(select(FeeHead)).first() is None

    today = date.today()
    start_year = today.year if today.month >= 5 else today.year - 1
    y_cur = _seed_year(
        db_session,
        date(start_year, 5, 17),
        date(start_year + 1, 4, 18),
        f"{start_year}-{start_year + 1}",
    )

    st = Student(
        student_id=f"VH-{uuid.uuid4().hex[:8]}",
        full_name="Van Head Bootstrap",
        class_name="5",
        section="A",
        phone=f"9{uuid.uuid4().int % 10**9:09d}",
        guardian_name="G",
        village="Nagaram",
        school_fees=20000.0,
        van_fees=0.0,
        transport_mode="van",
    )
    db_session.add(st)
    db_session.commit()

    ensure_default_fee_heads(isolated_test_database)

    transport = db_session.scalars(
        select(FeeHead).where(func.lower(FeeHead.head_name) == "transport").limit(1)
    ).first()
    assert transport is not None

    n = VillageVanFeeRepository(db_session).apply_village_van_fee("Nagaram", 20000.0, y_cur.id)
    assert n == 1

    db_session.refresh(st)
    assert float(st.van_fees) == pytest.approx(20000.0)

    inv = db_session.scalars(
        select(Invoice).where(
            Invoice.student_id_fk == st.student_id,
            Invoice.fee_head_id == transport.id,
        )
    ).first()
    assert inv is not None
    assert float(inv.amount_due) == pytest.approx(20000.0)
