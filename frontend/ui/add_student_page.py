"""Add New Student form — mandatory fields marked with *."""

from __future__ import annotations

from datetime import date
from typing import Callable

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.core.fee_control_constants import FIXED_CLASS_KEYS, FIXED_SECTION_KEYS
from frontend.ui.edudash_widgets import FormField, FormGrid, wrap_page
from frontend.ui.school_branding import breadcrumb_trail
from frontend.ui import theme
from frontend.ui.date_input import (
    configure_date_of_birth_edit,
    date_of_birth_validation_message,
    read_date_of_birth_value,
)
from frontend.ui.phone_input import configure_phone_line_edit, normalize_phone_text, phone_validation_message
from frontend.ui.segment_toggle import LOGIN_SEGMENT_WIDTH, SegmentToggle
from frontend.ui.table_style import style_fee_action_button

_OLD_STUDENT_INDEX = 1


class AddStudentPage(QWidget):
    """Form fields wired by MainWindow.add_student."""

    def __init__(self, populate_village: Callable[[QComboBox], None], parent=None):
        super().__init__(parent)

        body = QWidget()
        body.setObjectName("addStudentBody")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(20)

        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)
        self._mode_toggle = SegmentToggle(
            ("New Student", "Old Student"),
            width=LOGIN_SEGMENT_WIDTH,
        )
        self._mode_toggle.selection_changed.connect(self._on_student_mode_changed)
        toggle_row.addWidget(self._mode_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        toggle_row.addStretch(1)
        body_lay.addLayout(toggle_row)
        body_lay.addSpacing(4)

        self._roll_hint = QLabel(
            "Format: N/O + entry year + sequence (e.g. N20250001). "
            "Sequence is suggested; you may change the last 4 digits."
        )
        self._roll_hint.setWordWrap(True)
        self._roll_hint.setProperty("role", "hint")
        body_lay.addWidget(self._roll_hint)

        self._pending_hint = QLabel(
            "Enter total arrears from before the current academic year (combined school and van pending)."
        )
        self._pending_hint.setWordWrap(True)
        self._pending_hint.setProperty("role", "hint")
        self._pending_hint.hide()
        body_lay.addWidget(self._pending_hint)

        required_hint = QLabel("Fields marked with * are required.")
        required_hint.setProperty("role", "hint")
        required_hint.setWordWrap(True)
        body_lay.addWidget(required_hint)

        grid = FormGrid(columns=3)
        roll_row = QWidget()
        roll_layout = QHBoxLayout(roll_row)
        roll_layout.setContentsMargins(0, 0, 0, 0)
        roll_layout.setSpacing(8)
        self.roll_prefix = QLabel("N2025")
        self.roll_prefix.setProperty("role", "muted")
        self.roll_suffix = QLineEdit()
        self.roll_suffix.setMaxLength(4)
        self.roll_suffix.setPlaceholderText("0001")
        self.roll_suffix.setFixedWidth(72)
        roll_layout.addWidget(self.roll_prefix)
        roll_layout.addWidget(self.roll_suffix, 1)
        self.student_id = self.roll_suffix
        self.full_name = QLineEdit()
        self.student_class = QComboBox()
        self.student_class.addItems(list(FIXED_CLASS_KEYS))
        self.student_class.setCurrentIndex(FIXED_CLASS_KEYS.index("1"))
        self.section = QComboBox()
        self.section.addItems(list(FIXED_SECTION_KEYS))
        self.gender = QComboBox()
        self.gender.addItems(["Male", "Female", "Other"])
        self.father_name = QLineEdit()
        self.mother_name = QLineEdit()
        self.mobile_number_1 = QLineEdit()
        configure_phone_line_edit(self.mobile_number_1)
        self.mobile_number_2 = QLineEdit()
        configure_phone_line_edit(self.mobile_number_2)
        self.date_of_birth = QDateEdit()
        configure_date_of_birth_edit(self.date_of_birth, minimum_height=40)
        self.caste = QLineEdit()
        self.aadhaar = QLineEdit()
        self.village = QComboBox()
        populate_village(self.village)
        self.transport = QComboBox()
        self.transport.addItem("Van transport", "van")
        self.transport.addItem("Own transport", "own")
        self.status = QComboBox()
        self.status.addItems(["active", "inactive"])
        self.pending_fees = QLineEdit()
        self.pending_fees.setPlaceholderText("0.00")

        grid.add_field(FormField("Roll Number", roll_row, required=True))
        grid.add_field(FormField("Name", self.full_name, required=True))
        grid.add_field(FormField("Gender", self.gender, required=True))
        grid.add_field(FormField("Father Name", self.father_name, required=True))
        grid.add_field(FormField("Mother Name", self.mother_name))
        grid.add_field(FormField("Class", self.student_class, required=True))
        grid.add_field(FormField("Section", self.section, required=True))
        grid.add_field(FormField("Mobile Number 1", self.mobile_number_1, required=True))
        grid.add_field(FormField("Mobile Number 2", self.mobile_number_2))
        grid.add_field(FormField("Date of Birth", self.date_of_birth))
        grid.add_field(FormField("Caste", self.caste))
        grid.add_field(FormField("Aadhaar", self.aadhaar))
        grid.add_field(FormField("Village", self.village, required=True))
        grid.add_field(FormField("Transport", self.transport, required=True))
        grid.add_field(FormField("Status", self.status))
        self._pending_fees_field = FormField("Pending Fees", self.pending_fees, required=True)
        grid.add_field(self._pending_fees_field)
        body_lay.addWidget(grid)

        self._pending_fees_field.setVisible(False)

        self._van_hint = QLabel(
            "Choose Van transport to apply the village van fee from Fee Control, or Own transport "
            "to set van fees to zero (village is still stored for your records)."
        )
        self._van_hint.setWordWrap(True)
        self._van_hint.setProperty("role", "hint")
        self._school_hint = QLabel(
            "School fees are set automatically from the student’s class (see Fee Control tab). "
            "Class and section are picked from lists to avoid typing mistakes."
        )
        self._school_hint.setWordWrap(True)
        self._school_hint.setProperty("role", "hint")
        body_lay.addWidget(self._van_hint)
        body_lay.addWidget(self._school_hint)

        submit_row = QHBoxLayout()
        self.submit_btn = QPushButton("Add Student")
        style_fee_action_button(self.submit_btn)
        submit_row.addStretch(1)
        submit_row.addWidget(self.submit_btn)
        body_lay.addLayout(submit_row)
        body_lay.addStretch(1)

        self._wrapped = wrap_page(
            "Add Student",
            breadcrumb_trail("Admin Control", "Add Student"),
            body,
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._wrapped)

    def _on_student_mode_changed(self, _label: str) -> None:
        old_mode = self.is_old_student_mode()
        self._pending_hint.setVisible(old_mode)
        self._pending_fees_field.setVisible(old_mode)
        if not old_mode:
            self.pending_fees.clear()
        self.roll_refresh_requested.emit()

    roll_refresh_requested = Signal()

    def sync_suggested_roll_number(self, roll_number: str, *, force: bool = False) -> None:
        roll = (roll_number or "").strip().upper()
        if len(roll) >= 5:
            self.roll_prefix.setText(roll[:-4])
        if force or not (self.roll_suffix.text() or "").strip():
            self.roll_suffix.setText(roll[-4:] if len(roll) >= 4 else "")

    def composed_roll_number(self) -> str:
        prefix = (self.roll_prefix.text() or "").strip().upper()
        suffix = (self.roll_suffix.text() or "").strip()
        if suffix.isdigit():
            suffix = f"{int(suffix):04d}"
        return f"{prefix}{suffix}"

    def clear_roll_suffix(self) -> None:
        self.roll_suffix.clear()

    def is_old_student_mode(self) -> bool:
        return self._mode_toggle.selected_index() == _OLD_STUDENT_INDEX

    def pending_fees_value(self) -> float | None:
        if not self.is_old_student_mode():
            return None
        text = self.pending_fees.text().strip()
        if not text:
            return None
        try:
            value = float(text)
        except ValueError:
            return None
        if value < 0:
            return None
        return value

    def reset_student_mode(self) -> None:
        self._mode_toggle.set_selected_index(0, animate=False)
        self.pending_fees.clear()
        self._pending_hint.hide()
        self._pending_fees_field.setVisible(False)
        self.roll_refresh_requested.emit()

    def roll_suffix_validation_error(self) -> str | None:
        text = (self.roll_suffix.text() or "").strip()
        if not text:
            return "Please fill in Roll Number sequence (last 4 digits)."
        if not text.isdigit():
            return "Roll Number sequence must contain digits only."
        value = int(text)
        if value < 1 or value > 9999:
            return "Roll Number sequence must be between 0001 and 9999."
        return None

    def date_of_birth_value(self) -> date:
        return read_date_of_birth_value(self.date_of_birth) or date.today()

    def reset_date_of_birth(self) -> None:
        self.date_of_birth.setDate(QDate.currentDate())

    def optional_fields_for_submit(self) -> dict:
        """Sanitize optional fields; invalid optional input is ignored (no popup)."""
        mobile_2 = normalize_phone_text(self.mobile_number_2.text().strip())
        if mobile_2 and phone_validation_message(mobile_2):
            mobile_2 = ""
        aadhaar = normalize_phone_text(self.aadhaar.text().strip())
        if aadhaar and len(aadhaar) != 12:
            aadhaar = ""
        status_text = self.status.currentText().strip()
        return {
            "mother_name": self.mother_name.text().strip(),
            "mobile_number_2": mobile_2,
            "date_of_birth": self.date_of_birth_value(),
            "caste": self.caste.text().strip(),
            "aadhaar": aadhaar,
            "status": status_text or "active",
        }

    def form_validation_errors(self) -> list[str]:
        """Validation popup messages for mandatory fields only."""
        errors: list[str] = []
        roll_error = self.roll_suffix_validation_error()
        if roll_error:
            errors.append(roll_error)
        if not self.full_name.text().strip():
            errors.append("Please fill in Name.")
        if not self.gender.currentText().strip():
            errors.append("Please fill in Gender.")
        if not self.father_name.text().strip():
            errors.append("Please fill in Father Name.")
        if not self.student_class.currentText().strip():
            errors.append("Please fill in Class.")
        if not self.section.currentText().strip():
            errors.append("Please fill in Section.")
        mobile_1 = self.mobile_number_1.text().strip()
        if not mobile_1:
            errors.append("Please fill in Mobile Number 1.")
        elif not mobile_1.isdigit() or len(mobile_1) != 10:
            errors.append("Mobile Number 1 must be exactly 10 digits.")
        if not self.village.currentText().strip():
            errors.append("Please fill in Village.")
        if not self.transport.currentText().strip():
            errors.append("Please fill in Transport.")
        dob_error = date_of_birth_validation_message(self.date_of_birth)
        if dob_error:
            errors.append(dob_error)
        if self.is_old_student_mode():
            pending_text = self.pending_fees.text().strip()
            if not pending_text:
                errors.append("Please fill in Pending Fees for an old student.")
            else:
                try:
                    pending_value = float(pending_text)
                except ValueError:
                    errors.append("Pending Fees must be a valid number.")
                else:
                    if pending_value < 0:
                        errors.append("Pending Fees cannot be negative.")
        return errors

    def missing_required_fields(self) -> list[str]:
        """Backward-compatible helper; prefer form_validation_errors()."""
        return self.form_validation_errors()

    def refresh_theme(self) -> None:
        body = self.findChild(QWidget, "addStudentBody")
        if body is not None:
            body.setStyleSheet("background: transparent;")
        self._mode_toggle.refresh_theme()
        style_fee_action_button(self.submit_btn)
        theme.refresh_widget_tree(self._wrapped)
