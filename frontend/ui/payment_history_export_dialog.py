"""Export filter dialog for Payment History."""

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

from backend.core.fee_control_constants import FIXED_CLASS_KEYS, PASSED_OUT_CLASS_KEY
from backend.services.academic_year_service import AcademicYearService
from backend.services.payment_service import PaymentService
from backend.services.student_service import StudentService
from frontend.ui import theme
from frontend.ui.student_filter_combo import StudentFilterComboBox
from frontend.ui.table_style import fee_action_button_width, style_fee_action_button


class PaymentHistoryExportDialog(QDialog):
    _DIALOG_WIDTH = 580
    _DIALOG_HEIGHT = 720

    def __init__(
        self,
        payment_service: PaymentService,
        academic_year_service: AcademicYearService,
        student_service: StudentService,
        *,
        search: str = "",
        student_id: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._search = (search or "").strip()
        self._class_count = len(FIXED_CLASS_KEYS) + 1
        self.setWindowTitle("Export payment history")
        self.setMinimumSize(self._DIALOG_WIDTH, self._DIALOG_HEIGHT)
        self.resize(self._DIALOG_WIDTH, self._DIALOG_HEIGHT)
        theme.apply_dialog_theme(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)

        hint = QLabel(
            "Combine filters as needed. Choose a specific month or a date range (not both). "
            "Pick all classes, one class, or any group from the checklist. Optionally filter to one student."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "hint")
        layout.addWidget(hint)

        min_date, max_date = payment_service.payment_date_bounds()
        if min_date and max_date:
            bounds_hint = QLabel(
                f"Recorded payments span {min_date.day:02d}/{min_date.month:02d}/{min_date.year} "
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

        class_group = QGroupBox("Classes to include")
        class_lay = QVBoxLayout(class_group)
        class_lay.setSpacing(10)

        class_mode_row = QHBoxLayout()
        self._class_all = QRadioButton("All classes")
        self._class_pick = QRadioButton("Selected classes")
        self._class_all.setChecked(True)
        self._class_mode = QButtonGroup(self)
        self._class_mode.addButton(self._class_all)
        self._class_mode.addButton(self._class_pick)
        class_mode_row.addWidget(self._class_all)
        class_mode_row.addWidget(self._class_pick)
        class_mode_row.addStretch(1)
        class_lay.addLayout(class_mode_row)

        self._class_search = QLineEdit()
        self._class_search.setPlaceholderText("Search classes…")
        self._class_search.setMinimumHeight(36)
        class_lay.addWidget(self._class_search)

        self._class_list = QListWidget()
        self._class_list.setMinimumHeight(140)
        theme.refresh_list_widget(self._class_list)
        for class_key in (*FIXED_CLASS_KEYS, PASSED_OUT_CLASS_KEY):
            item = QListWidgetItem(class_key)
            item.setData(Qt.ItemDataRole.UserRole, class_key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._class_list.addItem(item)
        class_lay.addWidget(self._class_list)

        class_actions = QHBoxLayout()
        self._class_select_all_btn = QPushButton("Select all")
        self._class_clear_all_btn = QPushButton("Clear all")
        style_fee_action_button(
            self._class_select_all_btn,
            width=fee_action_button_width(self._class_select_all_btn, min_width=92),
        )
        style_fee_action_button(
            self._class_clear_all_btn,
            width=fee_action_button_width(self._class_clear_all_btn, min_width=92),
        )
        class_actions.addWidget(self._class_select_all_btn)
        class_actions.addWidget(self._class_clear_all_btn)
        class_actions.addStretch(1)
        self._class_summary = QLabel()
        self._class_summary.setProperty("role", "muted")
        class_actions.addWidget(self._class_summary)
        class_lay.addLayout(class_actions)
        layout.addWidget(class_group, 1)

        student_group = QGroupBox("Filter by student")
        student_lay = QVBoxLayout(student_group)
        student_lay.setSpacing(10)
        self._student_cb = QCheckBox("Only this student")
        student_lay.addWidget(self._student_cb)
        self._student_combo = StudentFilterComboBox(student_service, parent=self)
        student_lay.addWidget(self._student_combo)
        if student_id:
            idx = self._student_combo.findData(student_id)
            if idx >= 0:
                self._student_combo.setCurrentIndex(idx)
                self._student_cb.setChecked(True)
        layout.addWidget(student_group)

        self._year_cb = QCheckBox("Filter by academic year")
        layout.addWidget(self._year_cb)

        year_row = QHBoxLayout()
        year_row.setContentsMargins(24, 0, 0, 0)
        self._academic_year = QComboBox()
        self._academic_year.setMinimumHeight(40)
        current_year = academic_year_service.get_current()
        for year in academic_year_service.list_years():
            self._academic_year.addItem(
                academic_year_service.format_year_short_label(year),
                int(year.id),
            )
        if current_year is not None:
            idx = self._academic_year.findData(int(current_year.id))
            if idx >= 0:
                self._academic_year.setCurrentIndex(idx)
        year_row.addWidget(self._academic_year, 1)
        layout.addLayout(year_row)

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
        self._class_mode.buttonClicked.connect(self._on_class_mode_changed)
        self._class_search.textChanged.connect(self._filter_class_list)
        self._class_list.itemChanged.connect(lambda _: self._update_class_summary())
        self._class_select_all_btn.clicked.connect(lambda: self._set_visible_class_checks(True))
        self._class_clear_all_btn.clicked.connect(lambda: self._set_visible_class_checks(False))
        self._year_cb.toggled.connect(lambda _: self._sync_fields())
        self._student_cb.toggled.connect(lambda _: self._sync_fields())
        self._sync_fields()
        self._update_class_summary()

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

    def _on_class_mode_changed(self) -> None:
        if self._class_pick.isChecked():
            self._set_all_class_checks(False)
        self._sync_fields()

    def _sync_fields(self) -> None:
        self._month.setEnabled(self._month_cb.isChecked())
        self._year.setEnabled(self._month_cb.isChecked())
        self._from_date.setEnabled(self._range_cb.isChecked())
        self._to_date.setEnabled(self._range_cb.isChecked())
        self._academic_year.setEnabled(self._year_cb.isChecked())
        pick_on = self._class_pick.isChecked()
        for widget in (
            self._class_search,
            self._class_list,
            self._class_select_all_btn,
            self._class_clear_all_btn,
        ):
            widget.setEnabled(pick_on)
        self._student_combo.setEnabled(self._student_cb.isChecked())

    def _filter_class_list(self) -> None:
        needle = self._class_search.text().strip().lower()
        for row in range(self._class_list.count()):
            item = self._class_list.item(row)
            if item is None:
                continue
            item.setHidden(bool(needle) and needle not in item.text().lower())
        self._update_class_summary()

    def _set_all_class_checks(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self._class_list.blockSignals(True)
        for row in range(self._class_list.count()):
            item = self._class_list.item(row)
            if item is not None:
                item.setCheckState(state)
        self._class_list.blockSignals(False)
        self._update_class_summary()

    def _set_visible_class_checks(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self._class_list.blockSignals(True)
        for row in range(self._class_list.count()):
            item = self._class_list.item(row)
            if item is None or item.isHidden():
                continue
            item.setCheckState(state)
        self._class_list.blockSignals(False)
        self._update_class_summary()

    def _selected_class_keys(self) -> list[str]:
        keys: list[str] = []
        for row in range(self._class_list.count()):
            item = self._class_list.item(row)
            if item is None:
                continue
            if item.checkState() == Qt.CheckState.Checked:
                keys.append(str(item.data(Qt.ItemDataRole.UserRole) or item.text()))
        return keys

    def _update_class_summary(self) -> None:
        selected = len(self._selected_class_keys())
        if self._class_all.isChecked():
            self._class_summary.setText(f"All {self._class_count} classes")
            return
        self._class_summary.setText(f"{selected} of {self._class_count} selected")

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
        if self._class_pick.isChecked():
            class_names = self._selected_class_keys()
            if not class_names:
                raise ValueError("Select at least one class to export.")
            if len(class_names) < self._class_count:
                filters["class_names"] = class_names
        if self._student_cb.isChecked():
            student_id = self._student_combo.selected_student_id()
            if not student_id:
                raise ValueError("Select a student from the list (search by name or ID).")
            filters["student_id"] = student_id
        if self._year_cb.isChecked():
            year_id = self._academic_year.currentData()
            if year_id is None:
                raise ValueError("Select an academic year to export.")
            filters["academic_year_id"] = int(year_id)
        return filters

    def suggested_filename(self) -> str:
        parts = ["payment-history"]
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
        if self._class_pick.isChecked():
            labels = self._selected_class_keys()
            if len(labels) == 1:
                parts.append(labels[0])
            elif 1 < len(labels) <= 3:
                parts.append("-".join(labels))
            elif len(labels) > 3:
                parts.append(f"{len(labels)}-classes")
        if self._student_cb.isChecked():
            sid = self._student_combo.selected_student_id()
            if sid:
                parts.append(sid)
        if self._year_cb.isChecked():
            parts.append(str(self._academic_year.currentText() or "year"))
        if len(parts) == 1:
            return "payment-history.xlsx"
        return "-".join(parts) + ".xlsx"
