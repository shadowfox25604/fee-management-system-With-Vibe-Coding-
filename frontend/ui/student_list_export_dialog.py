"""Export filter dialog for Student List."""

from __future__ import annotations

import calendar
from datetime import date, datetime

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from backend.core.fee_control_constants import FIXED_CLASS_KEYS, FIXED_SECTION_KEYS, PASSED_OUT_CLASS_KEY
from backend.reports.student_list_excel_export import STUDENT_LIST_EXPORT_COLUMNS
from backend.services.student_service import StudentService
from frontend.ui import theme
from frontend.ui.student_filter_combo import StudentFilterComboBox
from frontend.ui.table_style import fee_action_button_width, style_fee_action_button


class StudentListExportDialog(QDialog):
    _DIALOG_WIDTH = 580
    _DIALOG_MIN_HEIGHT = 360
    _DIALOG_PREFERRED_HEIGHT = 640

    def __init__(
        self,
        student_service: StudentService,
        *,
        search: str = "",
        search_basis: str = "Name",
        student_id: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._search = (search or "").strip()
        self._search_basis = (search_basis or "Name").strip()
        self._class_count = len(FIXED_CLASS_KEYS) + 1
        self._section_count = len(FIXED_SECTION_KEYS)
        self.setWindowTitle("Export student list")
        self.setMinimumWidth(self._DIALOG_WIDTH)
        self.setMinimumHeight(self._DIALOG_MIN_HEIGHT)
        theme.apply_dialog_theme(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 20, 16)
        root.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(14)

        hint = QLabel(
            "Combine filters as needed. Choose a joined month or a joined date range (not both). "
            "Pick all classes or selected classes from the checklist. Optionally filter by section, "
            "status, or one student."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "hint")
        layout.addWidget(hint)

        min_date, max_date = student_service.student_join_date_bounds()
        if min_date and max_date:
            bounds_hint = QLabel(
                f"Student records span {min_date.day:02d}/{min_date.month:02d}/{min_date.year} "
                f"to {max_date.day:02d}/{max_date.month:02d}/{max_date.year}."
            )
            bounds_hint.setWordWrap(True)
            bounds_hint.setProperty("role", "muted")
            layout.addWidget(bounds_hint)

        if self._search:
            search_hint = QLabel(
                f'Table search also applied ({self._search_basis}): "{self._search}"'
            )
            search_hint.setProperty("role", "muted")
            layout.addWidget(search_hint)

        self._month_cb = QCheckBox("Filter by joined month")
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

        self._range_cb = QCheckBox("Filter by joined date range")
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
        self._class_list.setMinimumHeight(96)
        self._class_list.setMaximumHeight(120)
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
        layout.addWidget(class_group)

        section_group = QGroupBox("Sections to include")
        section_lay = QVBoxLayout(section_group)
        section_lay.setSpacing(10)

        section_mode_row = QHBoxLayout()
        self._section_all = QRadioButton("All sections")
        self._section_pick = QRadioButton("Selected sections")
        self._section_all.setChecked(True)
        self._section_mode = QButtonGroup(self)
        self._section_mode.addButton(self._section_all)
        self._section_mode.addButton(self._section_pick)
        section_mode_row.addWidget(self._section_all)
        section_mode_row.addWidget(self._section_pick)
        section_mode_row.addStretch(1)
        section_lay.addLayout(section_mode_row)

        self._section_search = QLineEdit()
        self._section_search.setPlaceholderText("Search sections…")
        self._section_search.setMinimumHeight(36)
        section_lay.addWidget(self._section_search)

        self._section_list = QListWidget()
        self._section_list.setMinimumHeight(88)
        self._section_list.setMaximumHeight(112)
        theme.refresh_list_widget(self._section_list)
        for section_key in FIXED_SECTION_KEYS:
            item = QListWidgetItem(section_key)
            item.setData(Qt.ItemDataRole.UserRole, section_key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._section_list.addItem(item)
        section_lay.addWidget(self._section_list)

        section_actions = QHBoxLayout()
        self._section_select_all_btn = QPushButton("Select all")
        self._section_clear_all_btn = QPushButton("Clear all")
        style_fee_action_button(
            self._section_select_all_btn,
            width=fee_action_button_width(self._section_select_all_btn, min_width=92),
        )
        style_fee_action_button(
            self._section_clear_all_btn,
            width=fee_action_button_width(self._section_clear_all_btn, min_width=92),
        )
        section_actions.addWidget(self._section_select_all_btn)
        section_actions.addWidget(self._section_clear_all_btn)
        section_actions.addStretch(1)
        self._section_summary = QLabel()
        self._section_summary.setProperty("role", "muted")
        section_actions.addWidget(self._section_summary)
        section_lay.addLayout(section_actions)
        layout.addWidget(section_group)

        status_group = QGroupBox("Status")
        status_lay = QHBoxLayout(status_group)
        self._status_all = QRadioButton("All students")
        self._status_active = QRadioButton("Active only")
        self._status_inactive = QRadioButton("Inactive only")
        self._status_all.setChecked(True)
        self._status_mode = QButtonGroup(self)
        self._status_mode.addButton(self._status_all)
        self._status_mode.addButton(self._status_active)
        self._status_mode.addButton(self._status_inactive)
        status_lay.addWidget(self._status_all)
        status_lay.addWidget(self._status_active)
        status_lay.addWidget(self._status_inactive)
        status_lay.addStretch(1)
        layout.addWidget(status_group)

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

        columns_group = QGroupBox("Columns to export")
        columns_lay = QVBoxLayout(columns_group)
        columns_lay.setSpacing(10)

        columns_hint = QLabel("Choose which fields appear in the Excel file.")
        columns_hint.setWordWrap(True)
        columns_hint.setProperty("role", "muted")
        columns_lay.addWidget(columns_hint)

        columns_host = QWidget()
        columns_grid = QGridLayout(columns_host)
        columns_grid.setContentsMargins(4, 4, 4, 4)
        columns_grid.setHorizontalSpacing(16)
        columns_grid.setVerticalSpacing(8)
        self._column_checks: dict[str, QCheckBox] = {}
        for index, column in enumerate(STUDENT_LIST_EXPORT_COLUMNS):
            key = str(column["key"])
            checkbox = QCheckBox(str(column["header"]))
            checkbox.setChecked(True)
            checkbox.toggled.connect(lambda _: self._update_column_summary())
            self._column_checks[key] = checkbox
            row = index // 2
            col = index % 2
            columns_grid.addWidget(checkbox, row, col)
        columns_lay.addWidget(columns_host)

        column_actions = QHBoxLayout()
        self._column_select_all_btn = QPushButton("Select all")
        self._column_clear_all_btn = QPushButton("Clear all")
        style_fee_action_button(
            self._column_select_all_btn,
            width=fee_action_button_width(self._column_select_all_btn, min_width=92),
        )
        style_fee_action_button(
            self._column_clear_all_btn,
            width=fee_action_button_width(self._column_clear_all_btn, min_width=92),
        )
        column_actions.addWidget(self._column_select_all_btn)
        column_actions.addWidget(self._column_clear_all_btn)
        column_actions.addStretch(1)
        self._column_summary = QLabel()
        self._column_summary.setProperty("role", "muted")
        column_actions.addWidget(self._column_summary)
        columns_lay.addLayout(column_actions)
        layout.addWidget(columns_group)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        actions = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        export_btn = actions.button(QDialogButtonBox.StandardButton.Ok)
        if export_btn is not None:
            export_btn.setText("Export")
        actions.accepted.connect(self._on_accept)
        actions.rejected.connect(self.reject)
        root.addWidget(actions)

        self._constrain_dialog_size()

        self._month_cb.toggled.connect(self._on_month_toggled)
        self._range_cb.toggled.connect(self._on_range_toggled)
        self._class_mode.buttonClicked.connect(self._on_class_mode_changed)
        self._section_mode.buttonClicked.connect(self._on_section_mode_changed)
        self._class_search.textChanged.connect(self._filter_class_list)
        self._section_search.textChanged.connect(self._filter_section_list)
        self._class_list.itemChanged.connect(lambda _: self._update_class_summary())
        self._section_list.itemChanged.connect(lambda _: self._update_section_summary())
        self._class_select_all_btn.clicked.connect(lambda: self._set_visible_class_checks(True))
        self._class_clear_all_btn.clicked.connect(lambda: self._set_visible_class_checks(False))
        self._section_select_all_btn.clicked.connect(lambda: self._set_visible_section_checks(True))
        self._section_clear_all_btn.clicked.connect(lambda: self._set_visible_section_checks(False))
        self._column_select_all_btn.clicked.connect(lambda: self._set_all_column_checks(True))
        self._column_clear_all_btn.clicked.connect(lambda: self._set_all_column_checks(False))
        self._student_cb.toggled.connect(lambda _: self._sync_fields())
        self._sync_fields()
        self._update_class_summary()
        self._update_section_summary()
        self._update_column_summary()

    def _constrain_dialog_size(self) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        margin = 48
        if screen is not None:
            available = screen.availableGeometry()
            max_w = max(self._DIALOG_WIDTH, available.width() - margin)
            max_h = max(self._DIALOG_MIN_HEIGHT, available.height() - margin)
        elif self.parent() is not None:
            parent_geo = self.parent().frameGeometry()
            max_w = max(self._DIALOG_WIDTH, parent_geo.width() - margin)
            max_h = max(self._DIALOG_MIN_HEIGHT, parent_geo.height() - margin)
        else:
            max_w = self._DIALOG_WIDTH
            max_h = self._DIALOG_PREFERRED_HEIGHT

        self.setMaximumSize(max_w, max_h)
        target_h = min(self._DIALOG_PREFERRED_HEIGHT, max_h)
        self.resize(self._DIALOG_WIDTH, target_h)

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

    def _on_section_mode_changed(self) -> None:
        if self._section_pick.isChecked():
            self._set_all_section_checks(False)
        self._sync_fields()

    def _sync_fields(self) -> None:
        self._month.setEnabled(self._month_cb.isChecked())
        self._year.setEnabled(self._month_cb.isChecked())
        self._from_date.setEnabled(self._range_cb.isChecked())
        self._to_date.setEnabled(self._range_cb.isChecked())
        pick_classes = self._class_pick.isChecked()
        for widget in (
            self._class_search,
            self._class_list,
            self._class_select_all_btn,
            self._class_clear_all_btn,
        ):
            widget.setEnabled(pick_classes)
        pick_sections = self._section_pick.isChecked()
        for widget in (
            self._section_search,
            self._section_list,
            self._section_select_all_btn,
            self._section_clear_all_btn,
        ):
            widget.setEnabled(pick_sections)
        self._student_combo.setEnabled(self._student_cb.isChecked())

    def _filter_class_list(self) -> None:
        needle = self._class_search.text().strip().lower()
        for row in range(self._class_list.count()):
            item = self._class_list.item(row)
            if item is None:
                continue
            item.setHidden(bool(needle) and needle not in item.text().lower())
        self._update_class_summary()

    def _filter_section_list(self) -> None:
        needle = self._section_search.text().strip().lower()
        for row in range(self._section_list.count()):
            item = self._section_list.item(row)
            if item is None:
                continue
            item.setHidden(bool(needle) and needle not in item.text().lower())
        self._update_section_summary()

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

    def _set_all_section_checks(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self._section_list.blockSignals(True)
        for row in range(self._section_list.count()):
            item = self._section_list.item(row)
            if item is not None:
                item.setCheckState(state)
        self._section_list.blockSignals(False)
        self._update_section_summary()

    def _set_visible_section_checks(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self._section_list.blockSignals(True)
        for row in range(self._section_list.count()):
            item = self._section_list.item(row)
            if item is None or item.isHidden():
                continue
            item.setCheckState(state)
        self._section_list.blockSignals(False)
        self._update_section_summary()

    def _selected_class_keys(self) -> list[str]:
        keys: list[str] = []
        for row in range(self._class_list.count()):
            item = self._class_list.item(row)
            if item is None:
                continue
            if item.checkState() == Qt.CheckState.Checked:
                keys.append(str(item.data(Qt.ItemDataRole.UserRole) or item.text()))
        return keys

    def _selected_section_keys(self) -> list[str]:
        keys: list[str] = []
        for row in range(self._section_list.count()):
            item = self._section_list.item(row)
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

    def _update_section_summary(self) -> None:
        selected = len(self._selected_section_keys())
        if self._section_all.isChecked():
            self._section_summary.setText(f"All {self._section_count} sections")
            return
        self._section_summary.setText(f"{selected} of {self._section_count} selected")

    def _selected_column_keys(self) -> list[str]:
        return [
            key
            for key, checkbox in self._column_checks.items()
            if checkbox.isChecked()
        ]

    def _set_all_column_checks(self, checked: bool) -> None:
        for checkbox in self._column_checks.values():
            checkbox.setChecked(checked)
        self._update_column_summary()

    def _update_column_summary(self) -> None:
        selected = len(self._selected_column_keys())
        total = len(self._column_checks)
        self._column_summary.setText(f"{selected} of {total} columns selected")

    def _on_accept(self) -> None:
        try:
            self.payload()
        except ValueError as exc:
            theme.message_warning(self, "Invalid export filter", str(exc))
            return
        self.accept()

    def payload(self) -> dict:
        if self._month_cb.isChecked() and self._range_cb.isChecked():
            raise ValueError("Choose either a joined month or a joined date range, not both.")

        filters: dict = {}
        if self._search:
            filters["search"] = self._search
            filters["search_basis"] = self._search_basis
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
        if self._section_pick.isChecked():
            sections = self._selected_section_keys()
            if not sections:
                raise ValueError("Select at least one section to export.")
            if len(sections) < self._section_count:
                filters["sections"] = sections
        if self._status_active.isChecked():
            filters["status"] = "active"
        elif self._status_inactive.isChecked():
            filters["status"] = "inactive"
        if self._student_cb.isChecked():
            student_id = self._student_combo.selected_student_id()
            if not student_id:
                raise ValueError("Select a student from the list (search by name or ID).")
            filters["student_id"] = student_id
        columns = self._selected_export_columns()
        if not columns:
            raise ValueError("Select at least one column to export.")
        filters["columns"] = columns
        return filters

    def _selected_export_columns(self) -> list[str]:
        selected = set(self._selected_column_keys())
        return [
            str(column["key"])
            for column in STUDENT_LIST_EXPORT_COLUMNS
            if str(column["key"]) in selected
        ]

    def _export_timestamp_label(self) -> str:
        now = datetime.now()
        return now.strftime("%d-%m-%Y-%H-%M-%S")

    def suggested_filename(self) -> str:
        parts = ["student-list"]
        if self._month_cb.isChecked():
            year, mon = int(self._year.value()), int(self._month.currentIndex() + 1)
            parts.append(f"joined-{year}-{mon:02d}")
        elif self._range_cb.isChecked():
            qf = self._from_date.date()
            qt = self._to_date.date()
            parts.append(
                f"joined-{qf.day():02d}-{qf.month():02d}-{qf.year()}-"
                f"{qt.day():02d}-{qt.month():02d}-{qt.year()}"
            )
        if self._class_pick.isChecked():
            labels = self._selected_class_keys()
            if len(labels) == 1:
                parts.append(labels[0])
            elif 1 < len(labels) <= 3:
                parts.append("-".join(labels))
            elif len(labels) > 3:
                parts.append(f"{len(labels)}-classes")
        if self._section_pick.isChecked():
            labels = self._selected_section_keys()
            if len(labels) == 1:
                parts.append(f"sec-{labels[0]}")
            elif len(labels) > 1:
                parts.append(f"{len(labels)}-sections")
        if self._status_active.isChecked():
            parts.append("active")
        elif self._status_inactive.isChecked():
            parts.append("inactive")
        if self._student_cb.isChecked():
            sid = self._student_combo.selected_student_id()
            if sid:
                parts.append(sid)
        parts.append(self._export_timestamp_label())
        return "-".join(parts) + ".xlsx"
