"""Tests for importing old students with initial pending fees."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import func, select

from backend.models import FeeHead
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.repositories.class_fee_repository import ClassFeeRepository
from backend.repositories.village_van_fee_repository import VillageVanFeeRepository
from backend.services.class_fee_service import ClassFeeService
from backend.services.fee_balance_service import FeeBalanceService
from backend.services.student_service import StudentService
from backend.services.village_van_fee_service import VillageVanFeeService
from tests.academic_year_helpers import clear_all_academic_years


def _fee_heads(session):
    t = session.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "tuition")).first()
    tr = session.scalars(select(FeeHead).where(func.lower(FeeHead.head_name) == "transport")).first()
    if t is None:
        t = FeeHead(head_name="Tuition", frequency="monthly", default_amount=2000.0)
        session.add(t)
    if tr is None:
        tr = FeeHead(head_name="Transport", frequency="monthly", default_amount=500.0)
        session.add(tr)
    session.flush()
    return t, tr


def _next_roll(ss: StudentService, *, is_old: bool = False) -> str:
    return ss.suggest_next_roll_number(is_old=is_old)


def test_siblings_can_share_mobile_number(db_session):
    _fee_heads(db_session)
    AcademicYearRepository(db_session).ensure_bootstrap_year()
    db_session.commit()

    shared_phone = f"9{uuid.uuid4().int % 10**9:09d}"
    ss = StudentService(db_session)

    first = ss.create_student(
        _next_roll(ss, is_old=False),
        "Older Sibling",
        "5",
        "A",
        shared_phone,
        village="Nagaram",
        guardian_name="Parent",
        gender="Male",
        father_name="Parent",
        transport_mode="own",
        is_old_student=False,
    )
    second = ss.create_student(
        _next_roll(ss, is_old=False),
        "Younger Sibling",
        "3",
        "B",
        shared_phone,
        village="Nagaram",
        guardian_name="Parent",
        gender="Female",
        father_name="Parent",
        transport_mode="own",
        is_old_student=False,
    )
    assert first.mobile_number_1 == shared_phone
    assert second.mobile_number_1 == shared_phone


def test_new_student_has_zero_pending_fees(db_session):
    _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    ay = ay_repo.ensure_bootstrap_year()
    ClassFeeRepository(db_session).upsert_stored_amount("5", ay.id, 6000.0)
    VillageVanFeeRepository(db_session).upsert_stored_amount("Nagaram", ay.id, 1000.0)
    db_session.commit()

    ss = StudentService(db_session)
    phone = f"9{uuid.uuid4().int % 10**9:09d}"
    st = ss.create_student(
        _next_roll(ss, is_old=False),
        "New Student",
        "5",
        "A",
        phone,
        village="Nagaram",
        guardian_name="G",
        gender="Male",
        father_name="G",
        transport_mode="van",
        village_fee_service=VillageVanFeeService(db_session),
        class_fee_service=ClassFeeService(db_session),
        is_old_student=False,
    )
    due = FeeBalanceService(db_session).get_students_due_breakdown([st.student_id])[st.student_id]
    assert float(due["pending_fees"]) == pytest.approx(0.0, abs=0.01)
    assert float(due["fee_due"]) == pytest.approx(6000.0, abs=0.01)
    assert float(due["van_due"]) == pytest.approx(1000.0, abs=0.01)


def test_old_student_seeds_pending_fees(db_session):
    _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)

    y_prev = ay_repo.create(date(2023, 5, 17), date(2024, 4, 18), "2023-24")
    y_cur = ay_repo.create(date(2024, 5, 17), date(2025, 4, 18), "2024-25")
    ClassFeeRepository(db_session).upsert_stored_amount("5", y_cur.id, 6000.0)
    VillageVanFeeRepository(db_session).upsert_stored_amount("Nagaram", y_cur.id, 1000.0)
    db_session.commit()

    ss = StudentService(db_session)
    phone = f"8{uuid.uuid4().int % 10**9:09d}"
    st = ss.create_student(
        _next_roll(ss, is_old=True),
        "Imported Old Student",
        "5",
        "A",
        phone,
        village="Nagaram",
        guardian_name="G",
        gender="Male",
        father_name="G",
        transport_mode="van",
        village_fee_service=VillageVanFeeService(db_session),
        class_fee_service=ClassFeeService(db_session),
        initial_pending_fees=15000.0,
        is_old_student=True,
    )
    due = FeeBalanceService(db_session).get_students_due_breakdown([st.student_id])[st.student_id]
    assert float(due["pending_fees"]) == pytest.approx(15000.0, abs=0.01)
    assert float(due["fee_due"]) == pytest.approx(6000.0, abs=0.01)
    assert float(due["van_due"]) == pytest.approx(1000.0, abs=0.01)


def test_old_student_with_zero_pending_skips_prior_year_seed(db_session):
    _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    ay = ay_repo.ensure_bootstrap_year()
    ClassFeeRepository(db_session).upsert_stored_amount("5", ay.id, 6000.0)
    db_session.commit()

    ss = StudentService(db_session)
    phone = f"7{uuid.uuid4().int % 10**9:09d}"
    st = ss.create_student(
        _next_roll(ss, is_old=True),
        "Zero Pending Old",
        "5",
        "A",
        phone,
        village="Nagaram",
        guardian_name="G",
        gender="Male",
        father_name="G",
        transport_mode="own",
        village_fee_service=VillageVanFeeService(db_session),
        class_fee_service=ClassFeeService(db_session),
        initial_pending_fees=0.0,
        is_old_student=True,
    )
    due = FeeBalanceService(db_session).get_students_due_breakdown([st.student_id])[st.student_id]
    assert float(due["pending_fees"]) == pytest.approx(0.0, abs=0.01)


def test_negative_pending_fees_raises(db_session):
    _fee_heads(db_session)
    AcademicYearRepository(db_session).ensure_bootstrap_year()
    db_session.commit()

    ss = StudentService(db_session)
    phone = f"6{uuid.uuid4().int % 10**9:09d}"
    with pytest.raises(ValueError, match="Pending fees cannot be negative"):
        ss.create_student(
            _next_roll(ss, is_old=True),
            "Bad Pending",
            "5",
            "A",
            phone,
            village="Nagaram",
            guardian_name="G",
            gender="Male",
            father_name="G",
            initial_pending_fees=-100.0,
            is_old_student=True,
        )


def test_old_student_auto_creates_prior_year_when_missing(db_session):
    _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)
    y_cur = ay_repo.create(date(2024, 5, 17), date(2025, 4, 18), "2024-25")
    ClassFeeRepository(db_session).upsert_stored_amount("5", y_cur.id, 5000.0)
    db_session.commit()
    assert len(ay_repo.list_all()) == 1

    ss = StudentService(db_session)
    phone = f"5{uuid.uuid4().int % 10**9:09d}"
    st = ss.create_student(
        _next_roll(ss, is_old=True),
        "Auto Prior Year",
        "5",
        "A",
        phone,
        village="Nagaram",
        guardian_name="G",
        gender="Male",
        father_name="G",
        transport_mode="own",
        class_fee_service=ClassFeeService(db_session),
        initial_pending_fees=8000.0,
        is_old_student=True,
    )
    years = ay_repo.list_all()
    assert len(years) == 2

    due = FeeBalanceService(db_session).get_students_due_breakdown([st.student_id])[st.student_id]
    assert float(due["pending_fees"]) == pytest.approx(8000.0, abs=0.01)


def test_old_student_uses_existing_prior_year_with_standard_bounds(db_session):
    """Adjacent May/June years: prior end is not strictly before current start."""
    _fee_heads(db_session)
    ay_repo = AcademicYearRepository(db_session)
    clear_all_academic_years(db_session)

    y_prev = ay_repo.create(date(2025, 5, 31), date(2026, 6, 1), "2025-2026")
    y_cur = ay_repo.create(date(2026, 5, 31), date(2027, 6, 1), "2026-2027")
    ClassFeeRepository(db_session).upsert_stored_amount("3", y_cur.id, 5000.0)
    db_session.commit()
    assert len(ay_repo.list_all()) == 2

    ss = StudentService(db_session)
    phone = f"4{uuid.uuid4().int % 10**9:09d}"
    st = ss.create_student(
        _next_roll(ss, is_old=True),
        "Adjacent Year Old",
        "3",
        "B",
        phone,
        village="Nagaram",
        guardian_name="G",
        gender="Female",
        father_name="G",
        transport_mode="own",
        class_fee_service=ClassFeeService(db_session),
        initial_pending_fees=90000.0,
        is_old_student=True,
    )
    assert len(ay_repo.list_all()) == 2

    due = FeeBalanceService(db_session).get_students_due_breakdown([st.student_id])[st.student_id]
    assert float(due["pending_fees"]) == pytest.approx(90000.0, abs=0.01)
    assert ay_repo.get_predecessor(y_cur) is not None
    assert ay_repo.get_predecessor(y_cur).id == y_prev.id
