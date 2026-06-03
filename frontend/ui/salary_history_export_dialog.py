"""Export filter dialog for Salary History."""

from __future__ import annotations

import calendar
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from backend.services.expense_service import ExpenseService
from frontend.ui import theme
from frontend.ui.table_style import fee_action_button_width, style_fee_action_button


class SalaryHistoryExportDialog(QDialog):
    _DIALOG_WIDTH = 580
    _DIALOG_HEIGHT = 620

    def __init__(
        self,
        expense_service: ExpenseService,
        *,
        search: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._search = (search or "").strip()
        faculty_names = expense_service.list_salary_export_faculty_names()
        self._faculty_count = len(faculty_names)
        self.setWindowTitle("Export salary history")
        self.setMinimumSize(self._DIALOG_WIDTH, self._DIALOG_HEIGHT)
        self.resize(self._DIALOG_WIDTH, self._DIALOG_HEIGHT)
        theme.apply_dialog_theme(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)

        hint = QLabel(
            "Combine filters as needed. Choose a specific month or a date range (not both). "
            "Pick all faculty, one faculty member, or any group from the checklist."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "hint")
        layout.addWidget(hint)

        min_date, max_date = expense_service.salary_expense_date_bounds()
        if min_date and max_date:
            bounds_hint = QLabel(
                f"Recorded salary payouts span {min_date.day:02d}/{min_date.month:02d}/{min_date.year} "
                f"to {max_date.day:02d}/{max_date.month:02d}/{max_date.year}."
            )
            bounds_hint.setWordWrap(True)
            bounds_hint.setProperty("role", "muted")
            layout.addWidget(bounds_hint)

        if self._search:
            search_hint = QLabel(f'Table search also applied: "{self._search}"')
            search_hint.setProperty("role", "muted")
            layout.addWidget(search_hint)

        self._month_cb = QCheckBox("Filter by specific month")
        layout.addWidget(self._month_cb)

        month_row = QHBoxLayout()
        month_row.setSpacing(12)
        month_row.setContentsMargins(24, 0, 0, 0)
        self._month = QComboBox()
        self._month.addItems(
            [
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ]
        )
        self._month.setMinimumHeight(40)
        today = date.today()
        self._month.setCurrentIndex(today.month - 1)
        self._year = QSpinBox()
        self._year.setRange(2000, 2100)
        self._year.setValue(today.year)
        self._year.setMinimumHeight(40)
        month_row.addWidget(QLabel("Month"))
        month_row.addWidget(self._month, 1)
        month_row.addWidget(QLabel("Year"))
        month_row.addWidget(self._year)
        layout.addLayout(month_row)

        self._range_cb = QCheckBox("Filter by date range")
        layout.addWidget(self._range_cb)

        range_row = QHBoxLayout()
        range_row.setSpacing(12)
        range_row.setContentsMargins(24, 0, 0, 0)
        month_start = date(today.year, today.month, 1)
        month_last_day = calendar.monthrange(today.year, today.month)[1]
        month_end = date(today.year, today.month, month_last_day)
        self._from_date = QDateEdit(QDate(month_start.year, month_start.month, month_start.day))
        self._from_date.setCalendarPopup(True)
        self._from_date.setDisplayFormat("dd/MM/yyyy")
        self._from_date.setMinimumHeight(40)
        self._to_date = QDateEdit(QDate(month_end.year, month_end.month, month_end.day))
        self._to_date.setCalendarPopup(True)
        self._to_date.setDisplayFormat("dd/MM/yyyy")
        self._to_date.setMinimumHeight(40)
        range_row.addWidget(QLabel("From"))
        range_row.addWidget(self._from_date, 1)
        range_row.addWidget(QLabel("To"))
        range_row.addWidget(self._to_date, 1)
        layout.addLayout(range_row)

        faculty_group = QGroupBox("Faculty to include")
        faculty_lay = QVBoxLayout(faculty_group)
        faculty_lay.setSpacing(10)

        faculty_mode_row = QHBoxLayout()
        self._faculty_all = QRadioButton("All faculty")
        self._faculty_pick = QRadioButton("Selected faculty")
        self._faculty_all.setChecked(True)
        self._faculty_mode = QButtonGroup(self)
        self._faculty_mode.addButton(self._faculty_all)
        self._faculty_mode.addButton(self._faculty_pick)
        faculty_mode_row.addWidget(self._faculty_all)
        faculty_mode_row.addWidget(self._faculty_pick)
        faculty_mode_row.addStretch(1)
        faculty_lay.addLayout(faculty_mode_row)

        self._faculty_search = QLineEdit()
        self._faculty_search.setPlaceholderText("Search faculty…")
        self._faculty_search.setMinimumHeight(36)
        faculty_lay.addWidget(self._faculty_search)

        self._faculty_list = QListWidget()
        self._faculty_list.setMinimumHeight(140)
        theme.refresh_list_widget(self._faculty_list)
        for faculty_name in faculty_names:
            item = QListWidgetItem(faculty_name)
            item.setData(Qt.ItemDataRole.UserRole, faculty_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._faculty_list.addItem(item)
        faculty_lay.addWidget(self._faculty_list)

        faculty_actions = QHBoxLayout()
        self._faculty_select_all_btn = QPushButton("Select all")
        self._faculty_clear_all_btn = QPushButton("Clear all")
        style_fee_action_button(
            self._faculty_select_all_btn,
            width=fee_action_button_width(self._faculty_select_all_btn, min_width=92),
        )
        style_fee_action_button(
            self._faculty_clear_all_btn,
            width=fee_action_button_width(self._faculty_clear_all_btn, min_width=92),
        )
        faculty_actions.addWidget(self._faculty_select_all_btn)
        faculty_actions.addWidget(self._faculty_clear_all_btn)
        faculty_actions.addStretch(1)
        self._faculty_summary = QLabel()
        self._faculty_summary.setProperty("role", "muted")
        faculty_actions.addWidget(self._faculty_summary)
        faculty_lay.addLayout(faculty_actions)

        if self._faculty_count == 0:
            empty = QLabel("No faculty recorded yet.")
            empty.setProperty("role", "hint")
            faculty_lay.addWidget(empty)
            self._faculty_pick.setEnabled(False)

        layout.addWidget(faculty_group, 1)

        actions = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        export_btn = actions.button(QDialogButtonBox.StandardButton.Ok)
        if export_btn is not None:
            export_btn.setText("Export")
        actions.accepted.connect(self._on_accept)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)

        self._month_cb.toggled.connect(self._on_month_toggled)
        self._range_cb.toggled.connect(self._on_range_toggled)
        self._faculty_mode.buttonClicked.connect(self._on_faculty_mode_changed)
        self._faculty_search.textChanged.connect(self._filter_faculty_list)
        self._faculty_list.itemChanged.connect(lambda _: self._update_faculty_summary())
        self._faculty_select_all_btn.clicked.connect(lambda: self._set_visible_faculty_checks(True))
        self._faculty_clear_all_btn.clicked.connect(lambda: self._set_visible_faculty_checks(False))
        self._sync_fields()
        self._update_faculty_summary()

    def _on_month_toggled(self, checked: bool) -> None:
        if checked:
            self._range_cb.blockSignals(True)
            self._range_cb.setChecked(False)
            self._range_cb.blockSignals(False)
        self._sync_fields()

    def _on_range_toggled(self, checked: bool) -> None:
        if checked:
            self._month_cb.blockSignals(True)
            self._month_cb.setChecked(False)
            self._month_cb.blockSignals(False)
        self._sync_fields()

    def _on_faculty_mode_changed(self) -> None:
        if self._faculty_pick.isChecked():
            self._set_all_faculty_checks(False)
        self._sync_fields()

    def _sync_fields(self) -> None:
        self._month.setEnabled(self._month_cb.isChecked())
        self._year.setEnabled(self._month_cb.isChecked())
        self._from_date.setEnabled(self._range_cb.isChecked())
        self._to_date.setEnabled(self._range_cb.isChecked())
        pick_on = self._faculty_pick.isChecked() and self._faculty_count > 0
        for widget in (
            self._faculty_search,
            self._faculty_list,
            self._faculty_select_all_btn,
            self._faculty_clear_all_btn,
        ):
            widget.setEnabled(pick_on)

    def _filter_faculty_list(self) -> None:
        needle = self._faculty_search.text().strip().lower()
        for row in range(self._faculty_list.count()):
            item = self._faculty_list.item(row)
            if item is None:
                continue
            item.setHidden(bool(needle) and needle not in item.text().lower())
        self._update_faculty_summary()

    def _set_all_faculty_checks(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self._faculty_list.blockSignals(True)
        for row in range(self._faculty_list.count()):
            item = self._faculty_list.item(row)
            if item is not None:
                item.setCheckState(state)
        self._faculty_list.blockSignals(False)
        self._update_faculty_summary()

    def _set_visible_faculty_checks(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self._faculty_list.blockSignals(True)
        for row in range(self._faculty_list.count()):
            item = self._faculty_list.item(row)
            if item is None or item.isHidden():
                continue
            item.setCheckState(state)
        self._faculty_list.blockSignals(False)
        self._update_faculty_summary()

    def _selected_faculty_names(self) -> list[str]:
        names: list[str] = []
        for row in range(self._faculty_list.count()):
            item = self._faculty_list.item(row)
            if item is None:
                continue
            if item.checkState() == Qt.CheckState.Checked:
                names.append(str(item.data(Qt.ItemDataRole.UserRole) or item.text()))
        return names

    def _update_faculty_summary(self) -> None:
        selected = len(self._selected_faculty_names())
        if self._faculty_all.isChecked() or self._faculty_count == 0:
            self._faculty_summary.setText(f"All {self._faculty_count} faculty")
            return
        self._faculty_summary.setText(f"{selected} of {self._faculty_count} selected")

    def _on_accept(self) -> None:
        try:
            self.payload()
        except ValueError as exc:
            theme.message_warning(self, "Invalid export filter", str(exc))
            return
        self.accept()

    def payload(self) -> dict:
        if self._month_cb.isChecked() and self._range_cb.isChecked():
            raise ValueError("Choose either a specific month or a date range, not both.")

        filters: dict = {"include_reverted": True}
        if self._search:
            filters["search"] = self._search
        if self._month_cb.isChecked():
            filters["month"] = (int(self._year.value()), int(self._month.currentIndex() + 1))
        elif self._range_cb.isChecked():
            qf = self._from_date.date()
            qt = self._to_date.date()
            date_from = date(qf.year(), qf.month(), qf.day())
            date_to = date(qt.year(), qt.month(), qt.day())
            if date_from > date_to:
                raise ValueError("Start date must be on or before end date.")
            filters["date_from"] = date_from
            filters["date_to"] = date_to
        if self._faculty_pick.isChecked():
            faculty_names = self._selected_faculty_names()
            if not faculty_names:
                raise ValueError("Select at least one faculty member to export.")
            if len(faculty_names) < self._faculty_count:
                filters["faculty_names"] = faculty_names
        return filters

    def suggested_filename(self) -> str:
        parts = ["salary-history"]
        if self._month_cb.isChecked():
            year, mon = int(self._year.value()), int(self._month.currentIndex() + 1)
            parts.append(f"{year}-{mon:02d}")
        elif self._range_cb.isChecked():
            qf = self._from_date.date()
            qt = self._to_date.date()
            parts.append(
                f"{qf.year()}{qf.month():02d}{qf.day():02d}-"
                f"{qt.year()}{qt.month():02d}{qt.day():02d}"
            )
        if self._faculty_pick.isChecked():
            labels = self._selected_faculty_names()
            if len(labels) == 1:
                parts.append(labels[0].replace(" ", "-"))
            elif 1 < len(labels) <= 2:
                parts.append("-".join(label.replace(" ", "-") for label in labels))
            elif len(labels) > 2:
                parts.append(f"{len(labels)}-faculty")
        if len(parts) == 1:
            return "salary-history.xlsx"
        return "-".join(parts) + ".xlsx"
