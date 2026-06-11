"""Shared date-of-birth QDateEdit helpers."""

from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDateEdit

DOB_MIN_DATE = QDate(1900, 1, 1)
DOB_EMPTY_SENTINEL_DATE = DOB_MIN_DATE


def qdate_from_value(value: date | datetime | None) -> QDate | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return QDate(value.year, value.month, value.day)
    return None


def configure_date_of_birth_edit(
    date_edit: QDateEdit,
    *,
    initial: date | datetime | None = None,
    allow_empty: bool = False,
    minimum_height: int | None = None,
) -> bool:
    """Configure a QDateEdit for date-of-birth entry. Returns whether the field starts empty."""
    date_edit.setCalendarPopup(True)
    date_edit.setDisplayFormat("dd/MM/yyyy")
    date_edit.setMinimumDate(DOB_MIN_DATE)
    date_edit.setMaximumDate(QDate.currentDate())
    date_edit.setCorrectionMode(QDateEdit.CorrectionMode.CorrectToPreviousValue)
    if minimum_height is not None:
        date_edit.setMinimumHeight(minimum_height)
    if allow_empty:
        date_edit.setSpecialValueText("—")
    date_edit.editingFinished.connect(lambda: enforce_date_of_birth_bounds(date_edit))

    initially_empty = False
    qd = qdate_from_value(initial)
    if qd is not None and qd.isValid():
        date_edit.setDate(qd)
    elif allow_empty:
        date_edit.setDate(DOB_EMPTY_SENTINEL_DATE)
        initially_empty = True
    else:
        date_edit.setDate(QDate.currentDate())
    return initially_empty


def enforce_date_of_birth_bounds(date_edit: QDateEdit) -> None:
    today = QDate.currentDate()
    qd = date_edit.date()
    if qd > today:
        date_edit.setDate(today)


def date_of_birth_validation_message(date_edit: QDateEdit) -> str | None:
    enforce_date_of_birth_bounds(date_edit)
    if date_edit.date() > QDate.currentDate():
        return "Date of Birth cannot be in the future."
    return None


def read_date_of_birth_value(
    date_edit: QDateEdit,
    *,
    initially_empty: bool = False,
) -> date | None:
    enforce_date_of_birth_bounds(date_edit)
    qd = date_edit.date()
    if not qd.isValid():
        return None
    if initially_empty and qd == DOB_EMPTY_SENTINEL_DATE:
        return None
    return date(qd.year(), qd.month(), qd.day())
