"""Add New Student — required fields only."""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from backend.core.fee_control_constants import FIXED_CLASS_KEYS, FIXED_SECTION_KEYS
from frontend.ui.edudash_widgets import FormField, FormGrid, SectionBlock, wrap_page
from frontend.ui.school_branding import breadcrumb_trail
from frontend.ui import theme
from frontend.ui.theme import style_primary


class AddStudentPage(QWidget):
    """Form fields wired by MainWindow.add_student."""

    def __init__(self, populate_village: Callable[[QComboBox], None], parent=None):
        super().__init__(parent)

        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(20)

        self._section = SectionBlock("Student details")
        grid = FormGrid(columns=3)
        self.student_id = QLineEdit()
        self.full_name = QLineEdit()
        self.student_class = QComboBox()
        self.student_class.addItems(list(FIXED_CLASS_KEYS))
        self.student_class.setCurrentIndex(3)
        self.section = QComboBox()
        self.section.addItems(list(FIXED_SECTION_KEYS))
        self.phone = QLineEdit()
        self.village = QComboBox()
        populate_village(self.village)
        self.transport = QComboBox()
        self.transport.addItem("Van transport", "van")
        self.transport.addItem("Own transport", "own")
        self.guardian_name = QLineEdit()
        self.status = QComboBox()
        self.status.addItems(["active", "inactive"])

        grid.add_field(FormField("Student ID", self.student_id, required=True))
        grid.add_field(FormField("Name", self.full_name, required=True))
        grid.add_field(FormField("Class", self.student_class, required=True))
        grid.add_field(FormField("Section", self.section, required=True))
        grid.add_field(FormField("Phone", self.phone))
        grid.add_field(FormField("Village", self.village))
        grid.add_field(FormField("Transport", self.transport))
        grid.add_field(FormField("Guardian Name", self.guardian_name))
        grid.add_field(FormField("Status", self.status))
        self._section.form_layout.addWidget(grid)

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
        self._section.form_layout.addWidget(self._van_hint)
        self._section.form_layout.addWidget(self._school_hint)
        body_lay.addWidget(self._section)

        submit_row = QHBoxLayout()
        self.submit_btn = QPushButton("Add Student")
        style_primary(self.submit_btn)
        submit_row.addStretch(1)
        submit_row.addWidget(self.submit_btn)
        body_lay.addLayout(submit_row)
        body_lay.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(body)

        self._wrapped = wrap_page(
            "Add New Student",
            breadcrumb_trail("Student", "Add New Student"),
            scroll,
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._wrapped)

    def refresh_theme(self) -> None:
        self._section.refresh_theme()
        style_primary(self.submit_btn)
        theme.refresh_widget_tree(self._wrapped)
