"""Miscellaneous school expenses — expense groups and line entries."""

from __future__ import annotations

import calendar
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from backend.services.misc_expense_service import MiscExpenseService
from frontend.ui import theme
from frontend.ui.edudash_widgets import CardTitleBar, SurfaceCard, wrap_page
from frontend.ui.pagination import PaginationBar, slice_page
from frontend.ui.school_branding import breadcrumb_trail
from frontend.ui.table_style import (
    configure_scrollable_data_table,
    fee_action_button_width,
    style_fee_action_button,
    table_item,
)

_EDIT_COLUMN_WIDTH = 132
_STATUS_COLUMN_WIDTH = 120
_DELETE_COLUMN_WIDTH = 160


class _ExpenseDialog(QDialog):
    _DIALOG_WIDTH = 560
    _DIALOG_HEIGHT = 320

    def __init__(
        self,
        *,
        title: str,
        head: str = "",
        expense_date: date | None = None,
        expense_particulars: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(self._DIALOG_WIDTH, self._DIALOG_HEIGHT)
        self.resize(self._DIALOG_WIDTH, self._DIALOG_HEIGHT)
        theme.apply_dialog_theme(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)
        form = QFormLayout()
        form.setSpacing(14)
        self._head = QLineEdit((head or "").strip())
        self._head.setPlaceholderText("e.g. Rent, Stationary, Donation")
        self._head.setMinimumHeight(40)
        self._date = QDateEdit(QDate.currentDate())
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("dd/MM/yyyy")
        self._date.setMinimumHeight(40)
        if expense_date is not None:
            self._date.setDate(QDate(expense_date.year, expense_date.month, expense_date.day))
        self._particulars = QLineEdit((expense_particulars or "").strip())
        self._particulars.setPlaceholderText("Optional particulars")
        self._particulars.setMinimumHeight(40)
        form.addRow("Head", self._head)
        form.addRow("Date", self._date)
        form.addRow("Particulars", self._particulars)
        layout.addLayout(form)
        layout.addStretch(1)
        actions = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        actions.accepted.connect(self.accept)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)

    def payload(self) -> dict:
        qd = self._date.date()
        return {
            "head": (self._head.text() or "").strip(),
            "expense_date": date(qd.year(), qd.month(), qd.day()),
            "notes": (self._particulars.text() or "").strip(),
        }


class _EntryDialog(QDialog):
    _DIALOG_WIDTH = 560
    _DIALOG_HEIGHT = 300

    def __init__(
        self,
        service: MiscExpenseService,
        *,
        title: str,
        expense_id: int | None = None,
        particular: str = "",
        amount: str = "",
        entry_date: date | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(self._DIALOG_WIDTH, self._DIALOG_HEIGHT)
        self.resize(self._DIALOG_WIDTH, self._DIALOG_HEIGHT)
        theme.apply_dialog_theme(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)
        form = QFormLayout()
        form.setSpacing(14)
        self._expense = QComboBox()
        self._expense.setMinimumHeight(40)
        for expense in service.list_expenses():
            self._expense.addItem(str(expense.head or "").strip(), int(expense.id))
        if expense_id is not None:
            idx = self._expense.findData(int(expense_id))
            if idx >= 0:
                self._expense.setCurrentIndex(idx)
        self._particular = QLineEdit((particular or "").strip())
        self._particular.setPlaceholderText("Description of the item or payment")
        self._particular.setMinimumHeight(40)
        self._amount = QLineEdit((amount or "").strip())
        self._amount.setPlaceholderText("Amount in ₹")
        self._amount.setMinimumHeight(40)
        self._date = QDateEdit(QDate.currentDate())
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("dd/MM/yyyy")
        self._date.setMinimumHeight(40)
        if entry_date is not None:
            self._date.setDate(QDate(entry_date.year, entry_date.month, entry_date.day))
        form.addRow("Expense", self._expense)
        form.addRow("Date", self._date)
        form.addRow("Particular", self._particular)
        form.addRow("Amount (₹)", self._amount)
        layout.addLayout(form)
        layout.addStretch(1)
        actions = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        actions.accepted.connect(self.accept)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)

    def payload(self) -> dict:
        qd = self._date.date()
        return {
            "expense_id": int(self._expense.currentData()),
            "entry_date": date(qd.year(), qd.month(), qd.day()),
            "particular": (self._particular.text() or "").strip(),
            "amount": float((self._amount.text() or "").strip() or 0.0),
        }


class _ExportFilterDialog(QDialog):
    _DIALOG_WIDTH = 580
    _DIALOG_HEIGHT = 620

    def __init__(self, service: MiscExpenseService, parent=None):
        super().__init__(parent)
        self._expense_count = 0
        self.setWindowTitle("Export expenses")
        self.setMinimumSize(self._DIALOG_WIDTH, self._DIALOG_HEIGHT)
        self.resize(self._DIALOG_WIDTH, self._DIALOG_HEIGHT)
        theme.apply_dialog_theme(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)

        hint = QLabel(
            "Combine date filters with expense selection. Choose a specific month or a date range "
            "(not both). Pick all expenses, one expense, or any group from the checklist."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "hint")
        layout.addWidget(hint)

        min_date, max_date = service.entry_date_bounds()
        if min_date and max_date:
            bounds_hint = QLabel(
                f"Recorded entries span {min_date.day:02d}/{min_date.month:02d}/{min_date.year} "
                f"to {max_date.day:02d}/{max_date.month:02d}/{max_date.year}."
            )
            bounds_hint.setWordWrap(True)
            bounds_hint.setProperty("role", "muted")
            layout.addWidget(bounds_hint)

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

        expense_group = QGroupBox("Expenses to include")
        expense_lay = QVBoxLayout(expense_group)
        expense_lay.setSpacing(10)

        mode_row = QHBoxLayout()
        self._expense_all = QRadioButton("All expenses")
        self._expense_pick = QRadioButton("Selected expenses")
        self._expense_all.setChecked(True)
        self._expense_mode = QButtonGroup(self)
        self._expense_mode.addButton(self._expense_all)
        self._expense_mode.addButton(self._expense_pick)
        mode_row.addWidget(self._expense_all)
        mode_row.addWidget(self._expense_pick)
        mode_row.addStretch(1)
        expense_lay.addLayout(mode_row)

        self._expense_search = QLineEdit()
        self._expense_search.setPlaceholderText("Search expenses…")
        self._expense_search.setMinimumHeight(36)
        expense_lay.addWidget(self._expense_search)

        self._expense_list = QListWidget()
        self._expense_list.setMinimumHeight(160)
        theme.refresh_list_widget(self._expense_list)
        for expense in service.list_expenses():
            head = str(expense.head or "").strip()
            item = QListWidgetItem(head)
            item.setData(Qt.ItemDataRole.UserRole, int(expense.id))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._expense_list.addItem(item)
        self._expense_count = self._expense_list.count()
        expense_lay.addWidget(self._expense_list)

        picker_actions = QHBoxLayout()
        self._select_all_btn = QPushButton("Select all")
        self._clear_all_btn = QPushButton("Clear all")
        style_fee_action_button(
            self._select_all_btn,
            width=fee_action_button_width(self._select_all_btn, min_width=92),
        )
        style_fee_action_button(
            self._clear_all_btn,
            width=fee_action_button_width(self._clear_all_btn, min_width=92),
        )
        picker_actions.addWidget(self._select_all_btn)
        picker_actions.addWidget(self._clear_all_btn)
        picker_actions.addStretch(1)
        self._expense_summary = QLabel()
        self._expense_summary.setProperty("role", "muted")
        picker_actions.addWidget(self._expense_summary)
        expense_lay.addLayout(picker_actions)

        if self._expense_count == 0:
            empty = QLabel("No expenses recorded yet.")
            empty.setProperty("role", "hint")
            expense_lay.addWidget(empty)
            self._expense_pick.setEnabled(False)

        layout.addWidget(expense_group, 1)

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
        self._expense_mode.buttonClicked.connect(self._on_expense_mode_changed)
        self._expense_search.textChanged.connect(self._filter_expense_list)
        self._expense_list.itemChanged.connect(lambda _: self._update_expense_summary())
        self._select_all_btn.clicked.connect(lambda: self._set_visible_expense_checks(True))
        self._clear_all_btn.clicked.connect(lambda: self._set_visible_expense_checks(False))
        self._sync_fields()
        self._update_expense_summary()

    def _on_expense_mode_changed(self) -> None:
        if self._expense_pick.isChecked():
            self._set_all_expense_checks(False)
        self._sync_fields()

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

    def _sync_fields(self) -> None:
        month_on = self._month_cb.isChecked()
        range_on = self._range_cb.isChecked()
        pick_on = self._expense_pick.isChecked() and self._expense_count > 0
        self._month.setEnabled(month_on)
        self._year.setEnabled(month_on)
        self._from_date.setEnabled(range_on)
        self._to_date.setEnabled(range_on)
        for widget in (
            self._expense_search,
            self._expense_list,
            self._select_all_btn,
            self._clear_all_btn,
        ):
            widget.setEnabled(pick_on)

    def _filter_expense_list(self) -> None:
        needle = self._expense_search.text().strip().lower()
        for row in range(self._expense_list.count()):
            item = self._expense_list.item(row)
            if item is None:
                continue
            item.setHidden(bool(needle) and needle not in item.text().lower())
        self._update_expense_summary()

    def _set_all_expense_checks(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self._expense_list.blockSignals(True)
        for row in range(self._expense_list.count()):
            item = self._expense_list.item(row)
            if item is not None:
                item.setCheckState(state)
        self._expense_list.blockSignals(False)
        self._update_expense_summary()

    def _set_visible_expense_checks(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self._expense_list.blockSignals(True)
        for row in range(self._expense_list.count()):
            item = self._expense_list.item(row)
            if item is None or item.isHidden():
                continue
            item.setCheckState(state)
        self._expense_list.blockSignals(False)
        self._update_expense_summary()

    def _selected_expense_ids(self) -> list[int]:
        ids: list[int] = []
        for row in range(self._expense_list.count()):
            item = self._expense_list.item(row)
            if item is None:
                continue
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return ids

    def _update_expense_summary(self) -> None:
        total = self._expense_count
        selected = len(self._selected_expense_ids())
        if total == 0:
            self._expense_summary.setText("No expenses available")
            return
        if self._expense_all.isChecked():
            self._expense_summary.setText(f"All {total} expenses")
            return
        self._expense_summary.setText(f"{selected} of {total} selected")

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

        filters: dict = {}
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

        if self._expense_pick.isChecked():
            expense_ids = self._selected_expense_ids()
            if not expense_ids:
                raise ValueError("Select at least one expense to export.")
            if len(expense_ids) < self._expense_count:
                filters["expense_ids"] = expense_ids

        return filters

    def _selected_expense_labels(self) -> list[str]:
        labels: list[str] = []
        for row in range(self._expense_list.count()):
            item = self._expense_list.item(row)
            if item is None:
                continue
            if item.checkState() == Qt.CheckState.Checked:
                labels.append(item.text())
        return labels

    def suggested_filename(self) -> str:
        parts = ["miscellaneous-expenses"]
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
        if self._expense_pick.isChecked():
            labels = self._selected_expense_labels()
            if len(labels) == 1:
                safe = "".join(
                    ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in labels[0]
                )
                parts.append(safe or "expense")
            elif 1 < len(labels) <= 3:
                chunk = "-".join(
                    "".join(ch if ch.isalnum() else "-" for ch in label)[:12]
                    for label in labels
                )
                parts.append(chunk or "selected")
            elif len(labels) > 3:
                parts.append(f"{len(labels)}-expenses")
        if len(parts) == 1:
            return "miscellaneous-expenses.xlsx"
        return "-".join(parts) + ".xlsx"


class MiscExpensesPage(QWidget):
    PAGE_SIZE = 50

    def __init__(self, service: MiscExpenseService, parent=None, *, on_data_changed=None):
        super().__init__(parent)
        self._service = service
        self._on_data_changed = on_data_changed
        self._page = 0
        self._cache: list[dict] = []

        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(12)

        hint = QLabel(
            "Record non-salary school expenses. Each expense has a head (e.g. Rent, Donation), "
            "a date, and one or more line entries. Export produces the colour-coded Excel ledger format."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "hint")
        body_lay.addWidget(hint)

        toolbar = QHBoxLayout()
        self._add_new_expense_btn = QPushButton("Add New Expense")
        self._add_entry_btn = QPushButton("Add Entry")
        self._export_btn = QPushButton("Export Excel")
        self._refresh_btn = QPushButton("Refresh")
        for btn in (
            self._add_new_expense_btn,
            self._add_entry_btn,
            self._export_btn,
            self._refresh_btn,
        ):
            style_fee_action_button(btn)
            toolbar.addWidget(btn)
        toolbar.addWidget(QLabel("Filter"))
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Head, particular, particulars…")
        toolbar.addWidget(self._filter, 1)
        body_lay.addLayout(toolbar)

        self._totals_label = QLabel("Total recorded: ₹0.00")
        self._totals_label.setProperty("role", "muted")
        body_lay.addWidget(self._totals_label)

        card = SurfaceCard()
        card.body.addWidget(CardTitleBar("Expense entry history"))
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["Date", "Head", "Particular", "Amount (₹)", "Status", "Edit", "Delete"]
        )
        configure_scrollable_data_table(self._table)
        self._table.setProperty("table_variant", "scrollable")
        card.body.addWidget(self._table, 1)
        card.setMinimumHeight(0)
        body_lay.addWidget(card, 1)

        self._pagination = PaginationBar(
            lambda: self._change_page(-1),
            lambda: self._change_page(1),
            green_style=True,
        )
        body_lay.addWidget(self._pagination)

        self._wrapped = wrap_page(
            "Miscellaneous",
            breadcrumb_trail("Expenses", "Miscellaneous"),
            body,
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._wrapped)

        self._add_new_expense_btn.clicked.connect(self._on_add_new_expense)
        self._add_entry_btn.clicked.connect(self._on_add_entry)
        self._export_btn.clicked.connect(self._on_export_excel)
        self._refresh_btn.clicked.connect(lambda: self.reload(reset_page=True))
        self._filter.textChanged.connect(lambda _: self.reload(reset_page=True))
        self.reload(reset_page=True)

    def _notify_data_changed(self) -> None:
        if self._on_data_changed is not None:
            self._on_data_changed()

    def refresh_theme(self) -> None:
        for btn in (
            self._add_new_expense_btn,
            self._add_entry_btn,
            self._export_btn,
            self._refresh_btn,
        ):
            style_fee_action_button(btn, width=btn.width() if btn.width() > 0 else None)
        self._pagination.refresh_theme()

    def reload(self, *, reset_page: bool = False) -> None:
        if reset_page:
            self._page = 0
        self._cache = self._service.list_entry_history(
            limit=50000,
            search=self._filter.text(),
        )
        total = self._service.total_spent()
        self._totals_label.setText(f"Total recorded: ₹{total:,.2f}")
        self._render_page()

    def _change_page(self, delta: int) -> None:
        self._page = max(0, self._page + int(delta))
        self._render_page()

    def _render_page(self) -> None:
        rows = slice_page(self._cache, self._page, page_size=self.PAGE_SIZE)
        tbl = self._table
        tbl.setRowCount(len(rows))
        tokens = theme.current_tokens()
        for i, row in enumerate(rows):
            d = row.get("expense_date")
            date_text = f"{d.day:02d}/{d.month:02d}/{d.year}" if d else ""
            is_reverted = bool(row.get("is_reverted", False))
            status = str(row.get("status") or ("Expense reverted" if is_reverted else "Recorded"))
            tbl.setItem(i, 0, table_item(date_text))
            tbl.setItem(i, 1, table_item(str(row.get("head") or "")))
            tbl.setItem(i, 2, table_item(str(row.get("particular") or "")))
            amount_item = table_item(f"{float(row.get('amount') or 0.0):,.2f}")
            status_item = table_item(status)
            if is_reverted:
                amount_item.setForeground(QColor(tokens.text_muted))
                status_item.setForeground(QColor(tokens.text_muted))
            tbl.setItem(i, 3, amount_item)
            tbl.setItem(i, 4, status_item)
            entry_id = int(row.get("entry_id") or 0)
            edit_btn = QPushButton("Edit")
            style_fee_action_button(
                edit_btn,
                width=fee_action_button_width(edit_btn, min_width=76),
            )
            if is_reverted:
                edit_btn.setEnabled(False)
            else:
                edit_btn.clicked.connect(lambda _=False, eid=entry_id: self._on_edit_entry(eid))
            tbl.setCellWidget(i, 5, edit_btn)
            delete_btn = QPushButton("Delete")
            style_fee_action_button(
                delete_btn,
                width=fee_action_button_width(delete_btn, min_width=92),
            )
            if is_reverted:
                delete_btn.setEnabled(False)
            else:
                delete_btn.clicked.connect(lambda _=False, eid=entry_id: self._on_delete_entry(eid))
            tbl.setCellWidget(i, 6, delete_btn)
        for col in range(5):
            tbl.resizeColumnToContents(col)
        tbl.resizeColumnsToContents()
        header = tbl.horizontalHeader()
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        tbl.setColumnWidth(5, max(tbl.columnWidth(5), _EDIT_COLUMN_WIDTH))
        tbl.setColumnWidth(6, max(tbl.columnWidth(6), _DELETE_COLUMN_WIDTH))
        tbl.setColumnWidth(4, max(tbl.columnWidth(4), _STATUS_COLUMN_WIDTH))
        fitted = getattr(tbl, "_fitted_column_widths", None)
        if fitted is None:
            fitted = [tbl.columnWidth(c) for c in range(tbl.columnCount())]
        while len(fitted) < tbl.columnCount():
            fitted.append(72)
        fitted[4] = tbl.columnWidth(4)
        fitted[5] = tbl.columnWidth(5)
        fitted[6] = tbl.columnWidth(6)
        tbl._fitted_column_widths = fitted
        self._pagination.update_state(self._page, len(self._cache), page_size=self.PAGE_SIZE)

    def _window(self) -> QWidget:
        return self.window()

    def _on_add_new_expense(self) -> None:
        dialog = _ExpenseDialog(title="Add new expense", parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        payload = dialog.payload()
        try:
            self._service.add_new_expense(
                payload["head"],
                payload["expense_date"],
                notes=payload["notes"],
            )
        except ValueError as exc:
            theme.message_warning(self._window(), "Invalid expense", str(exc))
            return
        except Exception as exc:
            theme.message_critical(self._window(), "Save failed", str(exc))
            return
        theme.message_information(self._window(), "Saved", "New expense added.")
        self.reload(reset_page=True)
        self._notify_data_changed()

    def _on_add_entry(self) -> None:
        if not self._service.list_expenses():
            theme.message_warning(
                self._window(),
                "No expenses",
                "Add a new expense before recording entries.",
            )
            return
        dialog = _EntryDialog(self._service, title="Add entry", parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        payload = dialog.payload()
        try:
            self._service.add_entry(
                payload["expense_id"],
                payload["particular"],
                payload["amount"],
                entry_date=payload["entry_date"],
            )
        except ValueError as exc:
            theme.message_warning(self._window(), "Invalid entry", str(exc))
            return
        except Exception as exc:
            theme.message_critical(self._window(), "Save failed", str(exc))
            return
        theme.message_information(self._window(), "Saved", "Expense entry saved.")
        self.reload(reset_page=False)
        self._notify_data_changed()

    def _on_edit_entry(self, entry_id: int) -> None:
        entry = self._service.repo.get_entry(entry_id)
        if entry is None:
            theme.message_warning(self._window(), "Not found", "This entry no longer exists.")
            self.reload(reset_page=False)
            return
        dialog = _EntryDialog(
            self._service,
            title="Edit entry",
            expense_id=int(entry.expense_id),
            particular=entry.particular,
            amount=f"{float(entry.amount or 0.0):.2f}",
            entry_date=entry.entry_date,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        payload = dialog.payload()
        try:
            if int(payload["expense_id"]) != int(entry.expense_id):
                self._service.delete_entry(entry_id)
                self._service.add_entry(
                    payload["expense_id"],
                    payload["particular"],
                    payload["amount"],
                    entry_date=payload["entry_date"],
                )
            else:
                self._service.update_entry(
                    entry_id,
                    particular=payload["particular"],
                    amount=payload["amount"],
                    entry_date=payload["entry_date"],
                )
        except ValueError as exc:
            theme.message_warning(self._window(), "Invalid entry", str(exc))
            return
        except Exception as exc:
            theme.message_critical(self._window(), "Save failed", str(exc))
            return
        self.reload(reset_page=False)
        self._notify_data_changed()

    def _on_delete_entry(self, entry_id: int) -> None:
        reply = theme.message_question(
            self._window(),
            "Confirm delete entry",
            "Delete this expense entry?\n\n"
            "The row will stay in history with status “Expense reverted”.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete_entry(entry_id)
        except ValueError as exc:
            theme.message_warning(self._window(), "Delete failed", str(exc))
            return
        except Exception as exc:
            theme.message_critical(self._window(), "Delete failed", str(exc))
            return
        theme.message_information(
            self._window(),
            "Expense reverted",
            "The expense entry has been reverted and marked as “Expense reverted”.",
        )
        self.reload(reset_page=False)
        self._notify_data_changed()

    def _on_export_excel(self) -> None:
        dialog = _ExportFilterDialog(self._service, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            filters = dialog.payload()
        except ValueError as exc:
            theme.message_warning(self._window(), "Invalid export filter", str(exc))
            return

        match_count = self._service.count_export_rows(**filters)
        if match_count == 0:
            min_date, max_date = self._service.entry_date_bounds()
            span = ""
            if min_date and max_date:
                span = (
                    f"\n\nRecorded entries span "
                    f"{min_date.day:02d}/{min_date.month:02d}/{min_date.year} to "
                    f"{max_date.day:02d}/{max_date.month:02d}/{max_date.year}."
                )
            theme.message_warning(
                self._window(),
                "No matching entries",
                "No expense entries match the selected filters." + span,
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self._window(),
            "Export miscellaneous expenses",
            dialog.suggested_filename(),
            "Excel files (*.xlsx)",
        )
        if not path:
            return
        try:
            self._service.export_excel(path, **filters)
        except Exception as exc:
            theme.message_critical(self._window(), "Export failed", str(exc))
            return
        theme.message_information(self._window(), "Exported", f"Excel report saved to {path}")
