"""Add New Faculty — required fields only."""

from __future__ import annotations

import calendar
from datetime import date

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from frontend.ui import theme
from frontend.ui.edudash_widgets import FormField, FormGrid, wrap_page
from frontend.ui.school_branding import breadcrumb_trail
from frontend.ui.table_style import style_fee_action_button


class AddFacultyPage(QWidget):
    """Faculty form styled like Add New Student."""

    def __init__(self, parent=None):
        super().__init__(parent)

        body = QWidget()
        body.setObjectName("addFacultyBody")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(20)

        grid = FormGrid(columns=3)
        self.faculty_name = QLineEdit()
        self.faculty_type = QComboBox()
        self.faculty_type.addItem("Teaching", "Teaching")
        self.faculty_type.addItem("Non Teaching", "Non Teaching")
        self.role = QLineEdit()
        self.monthly_salary = QLineEdit()
        self.default_working_days = QLineEdit()
        self.status = QComboBox()
        self.status.addItem("active", True)
        self.status.addItem("inactive", False)

        grid.add_field(FormField("Faculty Name", self.faculty_name, required=True))
        grid.add_field(FormField("Category", self.faculty_type, required=True))
        grid.add_field(FormField("Role / Designation", self.role, required=True))
        grid.add_field(FormField("Monthly Salary", self.monthly_salary, required=True))
        grid.add_field(FormField("Default Working Days", self.default_working_days, required=True))
        grid.add_field(FormField("Status", self.status, required=True))
        body_lay.addWidget(grid)

        self._salary_hint = QLabel(
            "Default working days are auto-set from the current month (total days minus Sundays). "
            "Salary payout is calculated from attendance in Salary tab."
        )
        self._salary_hint.setWordWrap(True)
        self._salary_hint.setProperty("role", "hint")
        self._type_hint = QLabel(
            "Choose Teaching or Non Teaching so faculty records stay clean and easy to filter."
        )
        self._type_hint.setWordWrap(True)
        self._type_hint.setProperty("role", "hint")
        body_lay.addWidget(self._salary_hint)
        body_lay.addWidget(self._type_hint)

        submit_row = QHBoxLayout()
        self.submit_btn = QPushButton("Add Faculty")
        style_fee_action_button(self.submit_btn)
        submit_row.addStretch(1)
        submit_row.addWidget(self.submit_btn)
        body_lay.addLayout(submit_row)
        body_lay.addStretch(1)

        self._wrapped = wrap_page(
            "Add New Faculty",
            breadcrumb_trail("Expenses", "Add Faculty"),
            body,
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._wrapped)
        self.sync_default_working_days_current_month()

    @staticmethod
    def _default_working_days_for_month(year: int, month: int) -> int:
        days_in_month = calendar.monthrange(year, month)[1]
        sunday_count = sum(
            1
            for day_num in range(1, days_in_month + 1)
            if date(year, month, day_num).weekday() == 6
        )
        return max(1, days_in_month - sunday_count)

    def sync_default_working_days_current_month(self) -> None:
        today = date.today()
        self.default_working_days.setText(
            str(self._default_working_days_for_month(today.year, today.month))
        )

    def form_validation_errors(self) -> list[str]:
        errors: list[str] = []
        if not self.faculty_name.text().strip():
            errors.append("Please fill in Faculty Name.")
        if not self.faculty_type.currentText().strip():
            errors.append("Please select Category.")
        if not self.role.text().strip():
            errors.append("Please fill in Role / Designation.")

        salary_text = self.monthly_salary.text().strip()
        if not salary_text:
            errors.append("Please fill in Monthly Salary.")
        else:
            try:
                if float(salary_text) <= 0:
                    errors.append("Monthly Salary must be greater than zero.")
            except ValueError:
                errors.append("Monthly Salary must be a valid number.")

        days_text = self.default_working_days.text().strip()
        if not days_text:
            errors.append("Please fill in Default Working Days.")
        else:
            try:
                if int(float(days_text)) <= 0:
                    errors.append("Default Working Days must be greater than zero.")
            except ValueError:
                errors.append("Default Working Days must be a valid number.")
        return errors

    def refresh_theme(self) -> None:
        body = self.findChild(QWidget, "addFacultyBody")
        if body is not None:
            body.setStyleSheet("background: transparent;")
        style_fee_action_button(self.submit_btn)
        theme.refresh_widget_tree(self._wrapped)
