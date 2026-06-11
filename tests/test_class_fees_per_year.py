"""Per-academic-year class school fee tariffs."""

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


def _seed_year(db_session, start: date, end: date, label: str) -> AcademicYear:
    repo = AcademicYearRepository(db_session)
    for row in repo.list_all():
        db_session.delete(row)
    db_session.commit()
    year = repo.create(start, end, label)
    db_session.commit()
    return year


def test_class_fees_independent_per_academic_year(db_session):
    class_svc = ClassFeeService(db_session)
    y1 = _seed_year(db_session, date(2026, 5, 17), date(2027, 4, 18), "2026-27")
    repo = AcademicYearRepository(db_session)
    y2 = repo.create(date(2027, 5, 17), date(2028, 4, 18), "2027-28")
    db_session.commit()

    class_svc.repo.upsert_stored_amount("5", y1.id, 20000.0)
    class_svc.repo.upsert_stored_amount("5", y2.id, 30000.0)
    db_session.commit()

    assert class_svc.display_amount_for_class("5", y1.id) == pytest.approx(20000.0)
    assert class_svc.display_amount_for_class("5", y2.id) == pytest.approx(30000.0)
    assert class_svc.school_fees_for_class_name("5", y1.id) == pytest.approx(20000.0)
    assert class_svc.school_fees_for_class_name("5", y2.id) == pytest.approx(30000.0)


def test_apply_updates_year_row_not_other_years(db_session):
    class_svc = ClassFeeService(db_session)
    y1 = _seed_year(db_session, date(2027, 5, 17), date(2028, 4, 18), "2027-28")
    repo = AcademicYearRepository(db_session)
    y2 = repo.create(date(2028, 5, 17), date(2029, 4, 18), "2028-29")
    db_session.commit()

    class_svc.repo.upsert_stored_amount("5", y1.id, 20000.0)
    class_svc.repo.upsert_stored_amount("5", y2.id, 30000.0)
    db_session.commit()

    st = Student(
        student_id=f"YF-{uuid.uuid4().hex[:8]}",
        full_name="Year Fee Student",
        class_name="5",
        section="A",
        phone="9876500001",
        guardian_name="G",
        school_fees=30000.0,
        van_fees=0.0,
    )
    db_session.add(st)
    db_session.commit()

    sy = StudentYearFeeRepository(db_session)
    sy.get_or_create(st, y1.id, school_fees=20000.0, van_fees=0.0)
    sy.get_or_create(st, y2.id, school_fees=30000.0, van_fees=0.0)
    db_session.commit()

    class_svc.apply_class_school_fee("5", 22000.0, y1.id)

    row1 = sy.get(st.student_id, y1.id)
    row2 = sy.get(st.student_id, y2.id)
    assert row1 is not None and row1.school_fees == pytest.approx(22000.0)
    assert row2 is not None and row2.school_fees == pytest.approx(30000.0)


def test_new_year_copies_previous_class_tariffs(db_session):
    class_svc = ClassFeeService(db_session)
    village_svc = VillageVanFeeService(db_session)
    y1 = _seed_year(db_session, date(2026, 5, 17), date(2027, 4, 18), "2026-27")
    class_svc.repo.upsert_stored_amount("5", y1.id, 21500.0)
    class_svc.repo.upsert_stored_amount("6", y1.id, 22500.0)
    db_session.commit()

    ay_svc = AcademicYearService(db_session)
    y2 = ay_svc.create_year(
        date(2027, 5, 17),
        date(2028, 4, 18),
        "2027-28",
        class_fee_service=class_svc,
        village_fee_service=village_svc,
        provision_students=False,
    )
    db_session.commit()

    assert class_svc.display_amount_for_class("5", y2.id) == pytest.approx(21500.0)
    assert class_svc.display_amount_for_class("6", y2.id) == pytest.approx(22500.0)


def test_ended_year_tariffs_not_editable(db_session):
    class_svc = ClassFeeService(db_session)
    y1 = _seed_year(db_session, date(2023, 5, 17), date(2024, 4, 18), "2023-24")
    class_svc.repo.upsert_stored_amount("5", y1.id, 20000.0)
    db_session.commit()

    assert class_svc.is_year_tariff_editable(y1.id, as_of=date(2026, 6, 1)) is False
    with pytest.raises(ValueError, match="ended"):
        class_svc.apply_class_school_fee("5", 21000.0, y1.id)
