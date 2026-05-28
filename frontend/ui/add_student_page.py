"""Add New Student form — mandatory fields marked with *."""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable

from PySide6.QtWidgets import (
    QComboBox,
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
from frontend.ui.phone_input import configure_phone_line_edit, normalize_phone_text, phone_validation_message
from frontend.ui.table_style import style_fee_action_button


class AddStudentPage(QWidget):
    """Form fields wired by MainWindow.add_student."""

    def __init__(self, populate_village: Callable[[QComboBox], None], parent=None):
        super().__init__(parent)

        body = QWidget()
        body.setObjectName("addStudentBody")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(20)

        required_hint = QLabel("Fields marked with * are required.")
        required_hint.setProperty("role", "hint")
        required_hint.setWordWrap(True)
        body_lay.addWidget(required_hint)

        grid = FormGrid(columns=3)
        self.student_id = QLineEdit()
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
        self.date_of_birth = QLineEdit()
        self.date_of_birth.setPlaceholderText("DD/MM/YYYY")
        self.caste = QLineEdit()
        self.aadhaar = QLineEdit()
        self.village = QComboBox()
        populate_village(self.village)
        self.transport = QComboBox()
        self.transport.addItem("Van transport", "van")
        self.transport.addItem("Own transport", "own")
        self.status = QComboBox()
        self.status.addItems(["active", "inactive"])

        grid.add_field(FormField("Roll Number", self.student_id, required=True))
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
        body_lay.addWidget(grid)

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
            "Add New Student",
            breadcrumb_trail("Student", "Add New Student"),
            body,
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._wrapped)

    @staticmethod
    def _optional_date_of_birth(text: str) -> date | None:
        raw = (text or "").strip()
        if not raw:
            return None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        return None

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
            "date_of_birth": self._optional_date_of_birth(self.date_of_birth.text()),
            "caste": self.caste.text().strip(),
            "aadhaar": aadhaar,
            "status": status_text or "active",
        }

    def form_validation_errors(self) -> list[str]:
        """Validation popup messages for mandatory fields only."""
        errors: list[str] = []
        if not self.student_id.text().strip():
            errors.append("Please fill in Roll Number.")
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
        return errors

    def missing_required_fields(self) -> list[str]:
        """Backward-compatible helper; prefer form_validation_errors()."""
        return self.form_validation_errors()

    def refresh_theme(self) -> None:
        body = self.findChild(QWidget, "addStudentBody")
        if body is not None:
            body.setStyleSheet("background: transparent;")
        style_fee_action_button(self.submit_btn)
        theme.refresh_widget_tree(self._wrapped)
