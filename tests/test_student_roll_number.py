"""Tests for structured student roll numbers."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import func, select

from backend.core.student_roll_number import (
    compose_roll_number,
    entry_year_from_session,
    parse_roll_number,
    validate_roll_number_suffix_change,
)
from backend.models import FeeHead, Payment
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.repositories.class_fee_repository import ClassFeeRepository
from backend.repositories.village_van_fee_repository import VillageVanFeeRepository
from backend.services.class_fee_service import ClassFeeService
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


def _bootstrap_year(session):
    _fee_heads(session)
    ay_repo = AcademicYearRepository(session)
    clear_all_academic_years(session)
    ay = ay_repo.create(date(2025, 5, 31), date(2026, 6, 1), "2025-2026")
    session.commit()
    return ay


def _phone() -> str:
    return f"9{uuid.uuid4().int % 10**9:09d}"


def _student_kwargs(**overrides):
    base = {
        "class_name": "5",
        "section": "A",
        "phone": _phone(),
        "village": "Nagaram",
        "guardian_name": "G",
        "gender": "Male",
        "father_name": "G",
        "transport_mode": "own",
        "class_fee_service": None,
        "village_fee_service": None,
    }
    base.update(overrides)
    return base


def test_compose_and_parse_roll_number():
    roll = compose_roll_number(is_old=False, entry_year=2025, sequence=1)
    assert roll == "N20250001"
    parts = parse_roll_number(roll)
    assert parts is not None
    assert parts.prefix == "N"
    assert parts.entry_year == 2025
    assert parts.sequence == 1
    assert parse_roll_number("LEGACY123") is None


def test_suggest_shared_sequence_across_new_and_old(db_session):
    _bootstrap_year(db_session)
    ss = StudentService(db_session)
    assert ss.suggest_next_roll_number(is_old=False) == "N20250001"

    ss.create_student(
        "N20250001",
        "First",
        **_student_kwargs(),
        is_old_student=False,
    )
    assert ss.suggest_next_roll_number(is_old=True) == "O20250002"


def test_reject_wrong_prefix_for_mode(db_session):
    _bootstrap_year(db_session)
    ss = StudentService(db_session)
    entry_year = entry_year_from_session(db_session)
    bad_roll = compose_roll_number(is_old=False, entry_year=entry_year, sequence=99)
    with pytest.raises(ValueError, match="must start with O"):
        ss.create_student(
            bad_roll,
            "Wrong Prefix",
            **_student_kwargs(),
            is_old_student=True,
        )


def test_reject_wrong_entry_year(db_session):
    _bootstrap_year(db_session)
    ss = StudentService(db_session)
    with pytest.raises(ValueError, match="Roll number year must be"):
        ss.create_student(
            "N20240001",
            "Wrong Year",
            **_student_kwargs(),
            is_old_student=False,
        )


def test_admin_override_last_four_digits_on_create(db_session):
    ay = _bootstrap_year(db_session)
    ClassFeeRepository(db_session).upsert_stored_amount("5", ay.id, 6000.0)
    db_session.commit()

    ss = StudentService(db_session)
    entry_year = entry_year_from_session(db_session)
    custom_roll = compose_roll_number(is_old=False, entry_year=entry_year, sequence=50)
    st = ss.create_student(
        custom_roll,
        "Custom Sequence",
        **_student_kwargs(),
        is_old_student=False,
    )
    assert st.student_id == custom_roll


def test_duplicate_roll_number_rejected(db_session):
    _bootstrap_year(db_session)
    ss = StudentService(db_session)
    ss.create_student(
        "N20250001",
        "First",
        **_student_kwargs(),
        is_old_student=False,
    )
    with pytest.raises(ValueError, match="already exists"):
        ss.create_student(
            "N20250001",
            "Duplicate",
            **_student_kwargs(phone=_phone()),
            is_old_student=False,
        )


def test_suffix_only_edit_renames_student_with_payment(db_session):
    ay = _bootstrap_year(db_session)
    ClassFeeRepository(db_session).upsert_stored_amount("5", ay.id, 6000.0)
    VillageVanFeeRepository(db_session).upsert_stored_amount("Nagaram", ay.id, 1000.0)
    db_session.commit()

    ss = StudentService(db_session)
    st = ss.create_student(
        "N20250001",
        "Pay Student",
        **_student_kwargs(
            transport_mode="van",
            village_fee_service=VillageVanFeeService(db_session),
            class_fee_service=ClassFeeService(db_session),
        ),
        is_old_student=False,
    )
    db_session.add(
        Payment(
            student_id_fk=st.student_id,
            payment_date=date.today(),
            amount=100.0,
            school_amount=100.0,
            van_amount=0.0,
            mode="cash",
            reference_no="REF0001",
            operator_name="Admin",
        )
    )
    db_session.commit()

    updated = ss.update_student(
        st,
        "N20250050",
        st.full_name,
        st.class_name,
        st.section,
        st.phone,
        village=st.village,
        guardian_name=st.guardian_name,
        status=st.status,
        transport_mode=st.transport_mode,
        gender=st.gender,
        father_name=st.father_name,
    )
    assert updated.student_id == "N20250050"
    payment = db_session.scalars(select(Payment)).first()
    assert payment is not None
    assert payment.student_id_fk == "N20250050"


def test_validate_roll_number_suffix_change_rejects_prefix_change():
    with pytest.raises(ValueError, match="Only the last 4 digits"):
        validate_roll_number_suffix_change("N20250001", "O20250001")
