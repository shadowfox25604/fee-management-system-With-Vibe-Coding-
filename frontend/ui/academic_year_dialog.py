from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
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
        self.resize(760, 420)
        theme.apply_dialog_theme(self)
        layout = QVBoxLayout(self)
        hint = QLabel(
            "Academic years are set automatically by the system. "
            "Each year runs from 31 May through 1 June of the following calendar year "
            "(for example, 2025-2026 is 31 May 2025 - 1 June 2026). "
            "Use “Add next year” to create the next sequential year with the correct dates and label. "
            "The year that contains today’s date is the current year for new fees and payments. "
            "Adding a new forward year promotes every active student one class (e.g. Nursery→LKG→UKG→1→2→…→10→Passed Out). "
            "Pending fees for the new year become: existing pending + previous current-year school due + previous current-year van due. "
            "Class 10 students are marked Passed Out and set to inactive."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "muted")
        layout.addWidget(hint)
        self._current_lbl = QLabel()
        layout.addWidget(self._current_lbl)
        self._next_lbl = QLabel()
        self._next_lbl.setProperty("role", "hint")
        self._next_lbl.setWordWrap(True)
        layout.addWidget(self._next_lbl)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Academic year", "Start", "End"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        configure_data_table(self.table)
        layout.addWidget(self.table, 1)
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add next year")
        del_btn = QPushButton("Delete year")
        self._add_btn.clicked.connect(self._on_add)
        del_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self._add_btn)
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
        try:
            next_start, next_end, next_label = self.service.next_academic_year_bounds()
            if any(y.start_date == next_start and y.end_date == next_end for y in years):
                self._next_lbl.setText("Next academic year is already in the list.")
                self._add_btn.setEnabled(False)
            else:
                self._next_lbl.setText(
                    f"Next year to add: {next_label} "
                    f"({format_academic_year_range(next_start, next_end)})"
                )
                self._add_btn.setEnabled(True)
        except Exception:
            self._next_lbl.setText("")
            self._add_btn.setEnabled(True)

        self.table.setRowCount(len(years))
        from backend.core.academic_year_dates import format_academic_year_date_display

        for i, y in enumerate(years):
            self.table.setItem(i, 0, QTableWidgetItem(y.label or ""))
            self.table.setItem(i, 1, QTableWidgetItem(format_academic_year_date_display(y.start_date)))
            self.table.setItem(i, 2, QTableWidgetItem(format_academic_year_date_display(y.end_date)))
            self.table.item(i, 0).setData(Qt.UserRole, int(y.id))

    def _selected_year_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.UserRole)) if item else None

    def _on_add(self):
        try:
            self.service.create_next_year(
                class_fee_service=self.class_fee_service,
                village_fee_service=self.village_fee_service,
            )
            self.session.expire_all()
            self._reload()
        except AcademicYearProvisionError as e:
            self.session.expire_all()
            self._reload()
            theme.message_warning(
                self,
                "Year saved — setup incomplete",
                f"Academic year “{e.year.label}” was saved and will remain after restart, "
                f"but fee rows for some students could not be created:\n\n{e}",
            )
        except Exception as e:
            self.session.rollback()
            theme.message_critical(self, "Could not add year", str(e))

    def _on_delete(self):
        yid = self._selected_year_id()
        if yid is None:
            theme.message_information(self, "Select a year", "Select an academic year row to delete.")
            return
        year = self.service.repo.get(yid)
        if year is None:
            return
        ok = theme.message_question(
            self,
            "Delete academic year",
            f"Delete {year.label} ({format_academic_year_range(year.start_date, year.end_date)})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_year(yid)
            self._reload()
        except Exception as e:
            self.session.rollback()
            theme.message_critical(self, "Could not delete year", str(e))
