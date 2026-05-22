"""Shared phone number input helpers (digits only, fixed length)."""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QLineEdit

PHONE_DIGIT_COUNT = 10


def normalize_phone_text(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())[:PHONE_DIGIT_COUNT]


def phone_validation_message(phone: str) -> str | None:
    value = (phone or "").strip()
    if not value:
        return "Please fill in Phone."
    if not value.isdigit() or len(value) != PHONE_DIGIT_COUNT:
        return "Phone must be exactly 10 digits."
    return None


def _sanitize_phone_line_edit(line_edit: QLineEdit, text: str) -> None:
    digits = normalize_phone_text(text)
    if digits == text:
        return
    cursor = line_edit.cursorPosition()
    removed_before = sum(1 for ch in text[:cursor] if not ch.isdigit())
    overflow = max(0, len("".join(ch for ch in text if ch.isdigit())) - PHONE_DIGIT_COUNT)
    line_edit.blockSignals(True)
    line_edit.setText(digits)
    line_edit.setCursorPosition(max(0, cursor - removed_before - overflow))
    line_edit.blockSignals(False)


def configure_phone_line_edit(line_edit: QLineEdit) -> None:
    """Restrict a QLineEdit to up to 10 numeric digits."""
    line_edit.setMaxLength(PHONE_DIGIT_COUNT)
    line_edit.setValidator(
        QRegularExpressionValidator(
            QRegularExpression(rf"[0-9]{{0,{PHONE_DIGIT_COUNT}}}"),
            line_edit,
        )
    )
    line_edit.textChanged.connect(lambda text: _sanitize_phone_line_edit(line_edit, text))
