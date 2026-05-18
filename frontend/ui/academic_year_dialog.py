from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from backend.core.academic_year_dates import format_academic_year_range
from backend.services.academic_year_errors import AcademicYearProvisionError
from backend.services.academic_year_service import AcademicYearService
from frontend.ui import theme
from frontend.ui.table_style import configure_data_table


class AcademicYearDialog(QDialog):
    def __init__(self, session, class_fee_service, village_fee_service, parent=None):
        super().__init__(parent)
        self.session = session
        self.service = AcademicYearService(session)
        self.class_fee_service = class_fee_service
        self.village_fee_service = village_fee_service
        self.setWindowTitle("Manage academic years")
        self.resize(720, 420)
        theme.apply_dialog_theme(self)
        layout = QVBoxLayout(self)
        hint = QLabel(
            "Each academic year is a date range (DD/MM/YYYY). Ranges must not overlap. "
            "The year that contains today’s date is the current year for new fees and payments. "
            "Adding a year creates fee records for all students using class and village tariffs."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "muted")
        layout.addWidget(hint)
        self._current_lbl = QLabel()
        layout.addWidget(self._current_lbl)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Label", "Start", "End"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        configure_data_table(self.table)
        layout.addWidget(self.table, 1)
        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add year…")
        edit_btn = QPushButton("Edit year…")
        del_btn = QPushButton("Delete year")
        add_btn.clicked.connect(self._on_add)
        edit_btn.clicked.connect(self._on_edit)
        del_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._reload()

    def _reload(self):
        current = self.service.get_current()
        self._current_lbl.setText(
            f"Current academic year: {self.service.format_year_display(current)}"
            if current
            else "Current academic year: none (today is not inside any defined range)"
        )
        years = self.service.list_years()
        self.table.setRowCount(len(years))
        from backend.core.payment_date_format import format_payment_date_dmY

        for i, y in enumerate(years):
            self.table.setItem(i, 0, QTableWidgetItem(y.label or ""))
            self.table.setItem(i, 1, QTableWidgetItem(format_payment_date_dmY(y.start_date)))
            self.table.setItem(i, 2, QTableWidgetItem(format_payment_date_dmY(y.end_date)))
            self.table.item(i, 0).setData(Qt.UserRole, int(y.id))

    def _selected_year_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.UserRole)) if item else None

    def _year_form_dialog(self, title: str, start: date | None = None, end: date | None = None, label: str = ""):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        theme.apply_dialog_theme(dlg)
        form = QFormLayout(dlg)
        label_edit = QLineEdit(label)
        label_edit.setPlaceholderText("Optional, e.g. 2025-26")
        start_edit = QDateEdit(QDate.currentDate())
        start_edit.setCalendarPopup(True)
        start_edit.setDisplayFormat("dd/MM/yyyy")
        end_edit = QDateEdit(QDate.currentDate())
        end_edit.setCalendarPopup(True)
        end_edit.setDisplayFormat("dd/MM/yyyy")
        if start:
            start_edit.setDate(QDate(start.year, start.month, start.day))
        if end:
            end_edit.setDate(QDate(end.year, end.month, end.day))
        form.addRow("Label", label_edit)
        form.addRow("Start date", start_edit)
        form.addRow("End date", end_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        q1, q2 = start_edit.date(), end_edit.date()
        return label_edit.text().strip(), date(q1.year(), q1.month(), q1.day()), date(q2.year(), q2.month(), q2.day())

    def _on_add(self):
        data = self._year_form_dialog("Add academic year")
        if not data:
            return
        label, start, end = data
        try:
            self.service.create_year(
                start,
                end,
                label or None,
                class_fee_service=self.class_fee_service,
                village_fee_service=self.village_fee_service,
            )
            self.session.expire_all()
            self._reload()
        except AcademicYearProvisionError as e:
            self.session.expire_all()
            self._reload()
            QMessageBox.warning(
                self,
                "Year saved — setup incomplete",
                f"Academic year “{e.year.label}” was saved and will remain after restart, "
                f"but fee rows for some students could not be created:\n\n{e}",
            )
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Could not add year", str(e))

    def _on_edit(self):
        yid = self._selected_year_id()
        if yid is None:
            QMessageBox.information(self, "Select a year", "Select an academic year row to edit.")
            return
        year = self.service.repo.get(yid)
        if year is None:
            return
        data = self._year_form_dialog("Edit academic year", year.start_date, year.end_date, year.label)
        if not data:
            return
        label, start, end = data
        try:
            self.service.update_year(yid, start, end, label or None)
            self._reload()
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Could not update year", str(e))

    def _on_delete(self):
        yid = self._selected_year_id()
        if yid is None:
            QMessageBox.information(self, "Select a year", "Select an academic year row to delete.")
            return
        year = self.service.repo.get(yid)
        if year is None:
            return
        ok = QMessageBox.question(
            self,
            "Delete academic year",
            f"Delete {year.label} ({format_academic_year_range(year.start_date, year.end_date)})?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ok != QMessageBox.Yes:
            return
        try:
            self.service.delete_year(yid)
            self._reload()
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Could not delete year", str(e))
