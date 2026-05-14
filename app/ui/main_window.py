from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.exc import IntegrityError
from app.core.fee_control_constants import (
    FIXED_CLASS_KEYS,
    FIXED_SECTION_KEYS,
    FIXED_VILLAGE_KEYS,
    canonical_village_for_student_village,
)
from app.models import Student
from app.reports.excel_export import ExcelExporter
from app.reports.payment_receipt_pdf import render_payment_receipt
from app.reports.pdf_export import PdfExporter
from app.services.backup_service import BackupService
from app.services.class_fee_service import ClassFeeService
from app.services.village_van_fee_service import VillageVanFeeService
from app.services.payment_service import PaymentService
from app.services.report_service import ReportService
from app.services.student_service import StudentService


@dataclass
class PaymentLikePane:
    search_by: QComboBox
    student_search: QLineEdit
    student_results: QListWidget
    hint: QLabel


class MainWindow(QMainWindow):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.student_service = StudentService(session)
        self.payment_service = PaymentService(session)
        self.report_service = ReportService(session)
        self.backup_service = BackupService()
        self.class_fee_service = ClassFeeService(session)
        self.village_van_fee_service = VillageVanFeeService(session)
        self.selected_student = None
        self._payment_panes: dict[str, PaymentLikePane] = {}
        self.setWindowTitle("Offline Fee Management")
        self.resize(1100, 700)
        tabs = QTabWidget()
        tabs.addTab(self._build_search_tab(), "Student Search")
        tabs.addTab(self._build_student_details_tab(), "Student Details")
        tabs.addTab(self._build_payment_tab(), "Collect Payment")
        tabs.addTab(self._build_add_student_tab(), "Add Student")
        tabs.addTab(self._build_reports_tab(), "Reports")
        tabs.addTab(self._build_backup_tab(), "Backup")
        self._fee_control_tab_index = tabs.addTab(self._build_fee_control_tab(), "Fee Control")
        self._payment_history_tab_index = tabs.addTab(self._build_payment_history_tab(), "Payment History")
        tabs.currentChanged.connect(self._on_main_tab_changed)
        self.setCentralWidget(tabs)
        self.perform_search()
    def _build_search_tab(self):
        w=QWidget(); layout=QVBoxLayout(w); row=QHBoxLayout()
        self.search_by=QComboBox(); self.search_by.addItems(["Roll Number","Name"]); self.search_by.setCurrentIndex(1); self.search_by.currentIndexChanged.connect(self.on_student_search_basis_changed)
        self.search_input=QLineEdit(); self.search_input.textChanged.connect(lambda _: self.perform_search())
        self.sort_by=QComboBox(); self.sort_by.addItems(["PK","Student ID","Name","Class","Section","Phone","Guardian Name","Village","Status","Van Fees","Van Fees Paid","Van Fees Due","School Fees","School Fees Paid","Discount","School Fees Due","Total Fees","Total Fees Due"]); self.sort_by.currentIndexChanged.connect(self.perform_search)
        self.sort_order=QComboBox(); self.sort_order.addItems(["Ascending","Descending"]); self.sort_order.currentIndexChanged.connect(self.perform_search)
        btn=QPushButton("Search"); btn.clicked.connect(self.perform_search)
        row.addWidget(self.search_by); row.addWidget(self.search_input); row.addWidget(self.sort_by); row.addWidget(self.sort_order); row.addWidget(btn)
        self.student_table=QTableWidget(0,18); self.student_table.setHorizontalHeaderLabels(["PK","Student ID","Name","Class","Section","Phone","Guardian Name","Village","Status","Van Fees","Van Fees Paid","Van Fees Due","School Fees","School Fees Paid","Discount","School Fees Due","Total Fees","Total Fees Due"])
        self.student_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.student_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.student_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.student_table.cellClicked.connect(self.on_student_selected)
        self.student_info=QLabel("Select a student to view details.")
        self.on_student_search_basis_changed()
        layout.addLayout(row); layout.addWidget(self.student_table); layout.addWidget(self.student_info)
        return w
    def _build_student_details_tab(self):
        w = self._create_payment_like_tab("details")
        return w

    def _build_payment_tab(self):
        w = self._create_payment_like_tab("payment")
        return w

    def _create_payment_like_tab(self, pane_id: str):
        w = QWidget()
        layout = QFormLayout(w)
        search_row = QHBoxLayout()
        search_by = QComboBox()
        search_by.addItems(["Roll Number", "Name", "Phone", "Village", "Class-Section", "Status", "Guardian Name"])
        search_by.setCurrentIndex(1)
        search_by.currentIndexChanged.connect(lambda _=None, p=pane_id: self._on_payment_search_basis_changed(p))
        student_search = QLineEdit()
        student_search.textChanged.connect(lambda t, p=pane_id: self._on_payment_student_filter_changed(p, t))
        search_row.addWidget(search_by)
        search_row.addWidget(student_search)
        student_results = QListWidget()
        student_results.itemClicked.connect(lambda item, p=pane_id: self._on_payment_student_selected(p, item))
        student_results.itemDoubleClicked.connect(lambda item, p=pane_id: self._on_payment_student_double_clicked(p, item))
        hint = QLabel(
            "Double-click a student to edit their profile."
            if pane_id == "details"
            else "Double-click a student to open payment collection."
        )
        layout.addRow("Find Student", search_row)
        layout.addRow("Matching Students", student_results)
        layout.addRow(hint)
        self._payment_panes[pane_id] = PaymentLikePane(
            search_by=search_by,
            student_search=student_search,
            student_results=student_results,
            hint=hint,
        )
        self._load_payment_student_options()
        self._on_payment_search_basis_changed(pane_id)
        return w
    def _build_add_student_tab(self):
        w=QWidget(); layout=QFormLayout(w)
        self.add_student_id=QLineEdit(); self.add_student_name=QLineEdit()
        self.add_student_class = QComboBox()
        self.add_student_class.addItems(list(FIXED_CLASS_KEYS))
        self.add_student_class.setCurrentIndex(3)
        self.add_student_section = QComboBox()
        self.add_student_section.addItems(list(FIXED_SECTION_KEYS))
        self.add_student_phone = QLineEdit()
        self.add_student_village = QComboBox()
        self.add_student_village.addItems(list(FIXED_VILLAGE_KEYS))
        self.add_student_guardian = QLineEdit()
        self.add_student_status = QComboBox()
        self.add_student_status.addItems(["active", "inactive"])
        school_fee_hint = QLabel(
            "School fees are set automatically from the student’s class (see Fee Control tab). "
            "Classes outside the fixed list use the default amount until you set them in Fee Control. "
            "Class and section are picked from lists to avoid typing mistakes."
        )
        school_fee_hint.setWordWrap(True)
        school_fee_hint.setStyleSheet("color: #888;")
        van_fee_hint = QLabel(
            "Van fees are set automatically from the student’s village (see Fee Control tab). "
            "Only the listed villages are available."
        )
        van_fee_hint.setWordWrap(True)
        van_fee_hint.setStyleSheet("color: #888;")
        b = QPushButton("Add Student")
        b.clicked.connect(self.add_student)
        layout.addRow("Student ID", self.add_student_id)
        layout.addRow("Name", self.add_student_name)
        layout.addRow("Class", self.add_student_class)
        layout.addRow("Section", self.add_student_section)
        layout.addRow("Phone", self.add_student_phone)
        layout.addRow("Village", self.add_student_village)
        layout.addRow("Guardian Name", self.add_student_guardian)
        layout.addRow(van_fee_hint)
        layout.addRow(school_fee_hint)
        layout.addRow("Status", self.add_student_status)
        layout.addRow(b)
        return w
    def _build_reports_tab(self):
        w=QWidget(); layout=QVBoxLayout(w); row=QHBoxLayout()
        self.report_student_input=QLineEdit(); self.report_student_input.setPlaceholderText("Student ID / Name")
        self.report_class=QComboBox(); self.report_class.addItem("All Classes", None)
        self.report_section=QComboBox(); self.report_section.addItem("All Sections", None)
        self._load_report_filter_values()
        a=QPushButton("Load Defaulters"); a.clicked.connect(self.load_defaulters)
        b=QPushButton("Export Excel"); b.clicked.connect(self.export_excel)
        c=QPushButton("Export PDF"); c.clicked.connect(self.export_pdf)
        row.addWidget(self.report_student_input); row.addWidget(self.report_class); row.addWidget(self.report_section); row.addWidget(a); row.addWidget(b); row.addWidget(c)
        self.report_table=QTableWidget(0,5); self.report_table.setHorizontalHeaderLabels(["Student ID","Name","Class","Section","Outstanding"])
        layout.addLayout(row); layout.addWidget(self.report_table); return w
    def _load_report_filter_values(self):
        values = self.report_service.get_report_filter_values()
        self.report_class.clear(); self.report_class.addItem("All Classes", None)
        self.report_section.clear(); self.report_section.addItem("All Sections", None)
        for c in values.get("classes", []):
            self.report_class.addItem(str(c), str(c))
        for s in values.get("sections", []):
            self.report_section.addItem(str(s), str(s))
    def _build_backup_tab(self):
        w=QWidget(); layout=QVBoxLayout(w)
        a=QPushButton("Create Backup"); a.clicked.connect(self.create_backup)
        b=QPushButton("Restore Backup"); b.clicked.connect(self.restore_backup)
        self.backup_status=QLabel("No backup action performed yet.")
        layout.addWidget(a); layout.addWidget(b); layout.addWidget(self.backup_status); return w

    def _build_fee_control_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        school_lbl = QLabel(
            "School fees: set the tariff for each class (fixed list). Class names on students are matched "
            "case-insensitively. Apply updates all matching students’ school fees, adjusts tuition invoice "
            "amounts only, and does not change van fees or transport invoices."
        )
        school_lbl.setWordWrap(True)
        van_lbl = QLabel(
            "Van fees: set the tariff for each village (fixed list). Village on students is matched "
            "case-insensitively. Apply updates all matching students’ van fees, adjusts transport/van invoice "
            "amounts only, and does not change tuition invoices."
        )
        van_lbl.setWordWrap(True)
        confirm_lbl = QLabel("A confirmation is required before saving each row.")
        confirm_lbl.setWordWrap(True)
        layout.addWidget(school_lbl)
        layout.addWidget(van_lbl)
        layout.addWidget(confirm_lbl)

        tables_row = QHBoxLayout()
        self._fee_control_amount_edits = {}
        tbl_school = QTableWidget(len(FIXED_CLASS_KEYS), 3)
        tbl_school.setHorizontalHeaderLabels(["Class", "School fee (₹)", ""])
        tbl_school.verticalHeader().setVisible(False)
        for row, class_key in enumerate(FIXED_CLASS_KEYS):
            tbl_school.setItem(row, 0, QTableWidgetItem(class_key))
            amount_edit = QLineEdit()
            amount_edit.setPlaceholderText("20000")
            self._fee_control_amount_edits[class_key] = amount_edit
            tbl_school.setCellWidget(row, 1, amount_edit)
            apply_btn = QPushButton("Apply…")
            apply_btn.clicked.connect(lambda _=False, ck=class_key: self._on_fee_control_apply_clicked(ck))
            tbl_school.setCellWidget(row, 2, apply_btn)
        tbl_school.resizeColumnsToContents()

        self._van_fee_control_amount_edits = {}
        tbl_van = QTableWidget(len(FIXED_VILLAGE_KEYS), 3)
        tbl_van.setHorizontalHeaderLabels(["Village", "Van fee (₹)", ""])
        tbl_van.verticalHeader().setVisible(False)
        for row, village_key in enumerate(FIXED_VILLAGE_KEYS):
            tbl_van.setItem(row, 0, QTableWidgetItem(village_key))
            v_edit = QLineEdit()
            v_edit.setPlaceholderText("0")
            self._van_fee_control_amount_edits[village_key] = v_edit
            tbl_van.setCellWidget(row, 1, v_edit)
            v_apply = QPushButton("Apply…")
            v_apply.clicked.connect(lambda _=False, vk=village_key: self._on_van_fee_control_apply_clicked(vk))
            tbl_van.setCellWidget(row, 2, v_apply)
        tbl_van.resizeColumnsToContents()

        tables_row.addWidget(tbl_school, 1)
        tables_row.addWidget(tbl_van, 1)
        layout.addLayout(tables_row)
        self._fee_control_table = tbl_school
        self._van_fee_control_table = tbl_van
        self._refresh_fee_control_amounts()
        self._refresh_van_fee_control_amounts()
        return w

    def _on_main_tab_changed(self, index: int):
        if index == getattr(self, "_fee_control_tab_index", -1):
            self._refresh_fee_control_amounts()
            self._refresh_van_fee_control_amounts()
        if index == getattr(self, "_payment_history_tab_index", -1):
            self._refresh_payment_history_table()

    def _build_payment_history_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        hint = QLabel(
            "Recorded payments (newest first). Each payment has a 12-character reference (letters A-Z and digits 0-9). "
            "Use the filter to search by reference, student ID, or name. Collected (₹) is school + van + discount for that payment; discount applies to school fee due only."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555;")
        row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_payment_history_table)
        row.addWidget(refresh_btn)
        row.addWidget(QLabel("Filter:"))
        self._payment_history_filter = QLineEdit()
        self._payment_history_filter.setPlaceholderText("Reference, student ID, or name...")
        self._payment_history_filter.textChanged.connect(lambda _: self._refresh_payment_history_table())
        row.addWidget(self._payment_history_filter, 1)
        self._payment_history_table = QTableWidget(0, 8)
        self._payment_history_table.setHorizontalHeaderLabels(
            ["Date", "Reference", "Student ID", "Name", "Total (₹)", "Discount (₹)", "Mode", "Operator"]
        )
        self._payment_history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._payment_history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._payment_history_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(hint)
        layout.addLayout(row)
        layout.addWidget(self._payment_history_table)
        return w

    def _refresh_payment_history_table(self):
        if not hasattr(self, "_payment_history_table"):
            return
        search = self._payment_history_filter.text() if hasattr(self, "_payment_history_filter") else ""
        rows = self.payment_service.list_payment_history(limit=5000, search=search)
        tbl = self._payment_history_table
        tbl.setRowCount(len(rows))
        for i, r in enumerate(rows):
            d = r["payment_date"]
            date_s = f"{d.day:02d}/{d.month:02d}/{d.year}" if d else ""
            tbl.setItem(i, 0, QTableWidgetItem(date_s))
            tbl.setItem(i, 1, QTableWidgetItem(str(r["reference_no"])))
            tbl.setItem(i, 2, QTableWidgetItem(str(r["student_roll"])))
            tbl.setItem(i, 3, QTableWidgetItem(str(r["student_name"])))
            tbl.setItem(i, 4, QTableWidgetItem(f"{float(r['amount']):.2f}"))
            tbl.setItem(i, 5, QTableWidgetItem(f"{float(r['discount']):.2f}"))
            tbl.setItem(i, 6, QTableWidgetItem(str(r["mode"])))
            tbl.setItem(i, 7, QTableWidgetItem(str(r["operator"])))
        tbl.resizeColumnsToContents()

    def _refresh_fee_control_amounts(self):
        if not hasattr(self, "_fee_control_amount_edits"):
            return
        for class_key, edit in self._fee_control_amount_edits.items():
            amt = self.class_fee_service.display_amount_for_class(class_key)
            edit.setText(f"{amt:.2f}")

    def _refresh_van_fee_control_amounts(self):
        if not hasattr(self, "_van_fee_control_amount_edits"):
            return
        for village_key, edit in self._van_fee_control_amount_edits.items():
            amt = self.village_van_fee_service.display_amount_for_village(village_key)
            edit.setText(f"{amt:.2f}")

    def _on_fee_control_apply_clicked(self, class_key: str):
        edit = self._fee_control_amount_edits.get(class_key)
        if edit is None:
            return
        raw = (edit.text() or "").strip()
        try:
            new_amt = float(raw) if raw else 0.0
        except ValueError:
            QMessageBox.warning(self, "Invalid amount", "Enter a valid number for the school fee.")
            return
        if new_amt < 0:
            QMessageBox.warning(self, "Invalid amount", "School fee cannot be negative.")
            return
        n = self.class_fee_service.count_students_in_class(class_key)
        reply = QMessageBox.question(
            self,
            "Confirm class fee update",
            f"Set school fee for class “{class_key}” to {new_amt:.2f}?\n\n"
            f"This will update {n} student(s) whose class matches (case-insensitive), set each student’s "
            f"school_fees to this amount, scale tuition (non-transport) invoice amount_due values, and store "
            f"this amount for the class. Van fees and transport invoices will not be changed.\n\n"
            f"Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            updated = self.class_fee_service.apply_class_school_fee(class_key, new_amt)
            QMessageBox.information(
                self,
                "Fee updated",
                f"Class “{class_key}” school fee saved. {updated} student(s) updated.",
            )
            self._refresh_fee_control_amounts()
            self.perform_search()
            self._load_report_filter_values()
            self._load_payment_student_options()
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Fee update failed", str(e))

    def _on_van_fee_control_apply_clicked(self, village_key: str):
        edit = self._van_fee_control_amount_edits.get(village_key)
        if edit is None:
            return
        raw = (edit.text() or "").strip()
        try:
            new_amt = float(raw) if raw else 0.0
        except ValueError:
            QMessageBox.warning(self, "Invalid amount", "Enter a valid number for the van fee.")
            return
        if new_amt < 0:
            QMessageBox.warning(self, "Invalid amount", "Van fee cannot be negative.")
            return
        n = self.village_van_fee_service.count_students_in_village(village_key)
        reply = QMessageBox.question(
            self,
            "Confirm village van fee update",
            f"Set van fee for village “{village_key}” to {new_amt:.2f}?\n\n"
            f"This will update {n} student(s) whose village matches (case-insensitive), set each student’s "
            f"van_fees to this amount, scale transport/van invoice amount_due values, and store "
            f"this amount for the village. Tuition invoices will not be changed.\n\n"
            f"Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            updated = self.village_van_fee_service.apply_village_van_fee(village_key, new_amt)
            QMessageBox.information(
                self,
                "Fee updated",
                f"Village “{village_key}” van fee saved. {updated} student(s) updated.",
            )
            self._refresh_van_fee_control_amounts()
            self.perform_search()
            self._load_report_filter_values()
            self._load_payment_student_options()
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Van fee update failed", str(e))

    def _load_payment_student_options(self):
        self._all_payment_students = self.student_service.list_students()
        for pid in list(self._payment_panes.keys()):
            pane = self._payment_panes[pid]
            self._populate_payment_student_options(pane.student_search.text(), pane_id=pid)

    def _populate_payment_student_options(self, filter_text=None, pane_id=None):
        pane_ids = [pane_id] if pane_id else list(self._payment_panes.keys())
        for pid in pane_ids:
            pane = self._payment_panes[pid]
            if pane_id is not None:
                ft = filter_text if filter_text is not None else pane.student_search.text()
            else:
                ft = pane.student_search.text()
            q = (ft or "").strip().lower()
            current_student_id = self.selected_student.id if self.selected_student else None
            pane.student_results.blockSignals(True)
            pane.student_results.clear()
            criteria = pane.search_by.currentText()
            students = self._all_payment_students
            selected_item = None
            for s in students:
                if q:
                    if criteria == "Roll Number" and q not in str(s.student_id or "").lower():
                        continue
                    if criteria == "Name" and q not in str(s.full_name or "").lower():
                        continue
                    if criteria == "Phone" and q not in str(s.phone or "").lower():
                        continue
                    if criteria == "Village" and q not in str(getattr(s, "village", None) or "").lower():
                        continue
                    if criteria == "Class-Section":
                        class_section = f"{s.class_name}-{s.section}".lower()
                        if q not in class_section:
                            continue
                    if criteria == "Status" and q not in str(s.status or "").lower():
                        continue
                    if criteria == "Guardian Name" and q not in str(s.guardian_name or "").lower():
                        continue
                item = QListWidgetItem(f"{s.student_id} - {s.full_name} | Class {s.class_name}-{s.section} | {s.phone}")
                item.setData(Qt.UserRole, s.id)
                pane.student_results.addItem(item)
                if current_student_id and s.id == current_student_id:
                    selected_item = item
            if selected_item:
                pane.student_results.setCurrentItem(selected_item)
            pane.student_results.blockSignals(False)

    def _on_payment_student_filter_changed(self, pane_id, text):
        self._populate_payment_student_options(text, pane_id=pane_id)

    def _on_payment_search_basis_changed(self, pane_id, _=None):
        pane = self._payment_panes[pane_id]
        basis = pane.search_by.currentText()
        placeholder_map = {
            "Roll Number": "Enter student roll number",
            "Name": "Enter student name",
            "Phone": "Enter student phone",
            "Village": "Enter village name",
            "Class-Section": "Enter class-section (example: I-A or 10-B)",
            "Status": "Enter student status",
            "Guardian Name": "Enter guardian name",
        }
        pane.student_search.setPlaceholderText(placeholder_map.get(basis, ""))
        self._on_payment_student_filter_changed(pane_id, pane.student_search.text())

    def _on_payment_student_selected(self, pane_id, item):
        student_id = item.data(Qt.UserRole) if item else None
        if not student_id:
            self.selected_student = None
            return
        s = self.session.get(Student, int(student_id))
        if not s:
            return
        self.selected_student = s

    def _on_payment_student_double_clicked(self, pane_id, item):
        if not item:
            return
        self._on_payment_student_selected(pane_id, item)
        if self.selected_student:
            # Collect Payment: student profile is view-only; Student Details tab: full edit + Save
            student_fields_editable = pane_id != "payment"
            self._open_payment_student_editor(self.selected_student, student_fields_editable=student_fields_editable)

    def _open_payment_student_editor(self, student, student_fields_editable: bool = True):
        show_payment_ui = not student_fields_editable
        dialog = QDialog(self)
        dialog.setWindowTitle("Collect Payment" if show_payment_ui else "Student Details")
        dialog.resize(760, 480 if student_fields_editable else 640)
        layout = QVBoxLayout(dialog)
        heading = QLabel(f"{student.full_name} ({student.student_id})")
        heading.setStyleSheet("font-size: 16px; font-weight: 600;")
        if student_fields_editable:
            sub_heading = QLabel("Edit student details below, then click Save.")
        else:
            sub_heading = QLabel("Student information is shown for reference. Enter payment details below.")
        sub_heading.setStyleSheet("color: #555;")
        layout.addWidget(heading)
        layout.addWidget(sub_heading)

        details_box = QGroupBox("Student Information")
        details_layout = QFormLayout(details_box)
        lbl_pk = QLabel(str(student.id))
        lbl_created = QLabel(str(student.created_at or "-"))

        edit_student_id = edit_name = edit_class = edit_section = edit_phone = edit_guardian = None
        edit_village = None
        lbl_school_fees_editable = None
        lbl_van_fees_editable = None
        edit_status = None
        lbl_van_fees = None
        lbl_school_fees = None
        ro_student_id = ro_name = ro_class = ro_section = ro_phone = ro_village = ro_guardian = ro_status = None

        if student_fields_editable:
            edit_student_id = QLineEdit(str(student.student_id or ""))
            edit_name = QLineEdit(str(student.full_name or ""))
            edit_class = QLineEdit(str(student.class_name or ""))
            edit_section = QLineEdit(str(student.section or ""))
            edit_phone = QLineEdit(str(student.phone or ""))
            edit_village = QComboBox()
            edit_village.addItems(list(FIXED_VILLAGE_KEYS))
            key = canonical_village_for_student_village(getattr(student, "village", None))
            if key:
                vidx = edit_village.findText(key, Qt.MatchFixedString)
                if vidx >= 0:
                    edit_village.setCurrentIndex(vidx)
            edit_guardian = QLineEdit(str(student.guardian_name or ""))
            lbl_van_fees_editable = QLabel(f"{float(getattr(student, 'van_fees', 0) or 0):.2f}")
            lbl_van_fees_editable.setToolTip("Van fee tariff is managed under Fee Control (by village).")
            lbl_school_fees_editable = QLabel(f"{float(getattr(student, 'school_fees', 0) or 0):.2f}")
            lbl_school_fees_editable.setToolTip("School fee tariff is managed under Fee Control (by class).")
            edit_status = QComboBox()
            edit_status.addItems(["active", "inactive"])
            current_status = str(student.status or "active").lower()
            status_index = edit_status.findText(current_status, Qt.MatchFixedString)
            if status_index >= 0:
                edit_status.setCurrentIndex(status_index)
            details_layout.addRow("PK", lbl_pk)
            details_layout.addRow("Created At", lbl_created)
            details_layout.addRow("Student ID", edit_student_id)
            details_layout.addRow("Name", edit_name)
            details_layout.addRow("Class", edit_class)
            details_layout.addRow("Section", edit_section)
            details_layout.addRow("Phone", edit_phone)
            details_layout.addRow("Village", edit_village)
            details_layout.addRow("Guardian Name", edit_guardian)
            details_layout.addRow("Van Fees (read-only)", lbl_van_fees_editable)
            details_layout.addRow("School Fees (read-only)", lbl_school_fees_editable)
            details_layout.addRow("Status", edit_status)
        else:
            ro_student_id = QLabel(str(student.student_id or "-"))
            ro_name = QLabel(str(student.full_name or "-"))
            ro_class = QLabel(str(student.class_name or "-"))
            ro_section = QLabel(str(student.section or "-"))
            ro_phone = QLabel(str(student.phone or "-"))
            ro_village = QLabel(str(getattr(student, "village", None) or "-"))
            ro_guardian = QLabel(str(student.guardian_name or "-"))
            ro_status = QLabel(str(student.status or "-"))
            lbl_van_fees = QLabel(f"{float(getattr(student, 'van_fees', 0) or 0):.2f}")
            lbl_school_fees = QLabel(f"{float(getattr(student, 'school_fees', 0) or 0):.2f}")
            details_layout.addRow("PK", lbl_pk)
            details_layout.addRow("Created At", lbl_created)
            details_layout.addRow("Student ID", ro_student_id)
            details_layout.addRow("Name", ro_name)
            details_layout.addRow("Class", ro_class)
            details_layout.addRow("Section", ro_section)
            details_layout.addRow("Phone", ro_phone)
            details_layout.addRow("Village", ro_village)
            details_layout.addRow("Guardian Name", ro_guardian)
            details_layout.addRow("Van Fees", lbl_van_fees)
            details_layout.addRow("School Fees", lbl_school_fees)
            details_layout.addRow("Status", ro_status)
        layout.addWidget(details_box)

        popup_out_van = popup_out_school = popup_out_total = None
        popup_school_pay = popup_van_pay = popup_discount = popup_payment_date = popup_mode = None
        if show_payment_ui:
            payment_box = QGroupBox("Payment Details")
            payment_layout = QFormLayout(payment_box)
            due_init = self.payment_service.get_student_due_breakdown(student.id)
            popup_out_van = QLabel(f"{due_init['van_due']:.2f}")
            popup_out_school = QLabel(f"{due_init['fee_due']:.2f}")
            popup_out_total = QLabel(f"{due_init['total']:.2f}")
            popup_school_pay = QLineEdit()
            popup_school_pay.setPlaceholderText("0.00")
            popup_van_pay = QLineEdit()
            popup_van_pay.setPlaceholderText("0.00")
            popup_discount = QLineEdit()
            popup_discount.setPlaceholderText("0.00")
            popup_payment_date = QDateEdit(QDate.currentDate())
            popup_payment_date.setCalendarPopup(True)
            popup_payment_date.setDisplayFormat("dd/MM/yyyy")
            popup_payment_date.setMaximumDate(QDate.currentDate())
            popup_mode = QLineEdit("cash")
            payment_layout.addRow("Van fees due", popup_out_van)
            payment_layout.addRow("Fee due", popup_out_school)
            payment_layout.addRow("Total fees due", popup_out_total)
            payment_layout.addRow("School fee payment", popup_school_pay)
            payment_layout.addRow("Van fee payment", popup_van_pay)
            payment_layout.addRow("Discount", popup_discount)
            payment_layout.addRow("Date of payment", popup_payment_date)
            payment_layout.addRow("Mode", popup_mode)
            layout.addWidget(payment_box)

        collect_btn = None
        print_receipt_btn = None
        if show_payment_ui:
            collect_btn = QPushButton("Collect Payment")
            print_receipt_btn = QPushButton("Print Receipt")
            close_pay_btn = QPushButton("Close")
            pay_row = QHBoxLayout()
            pay_row.addStretch(1)
            pay_row.addWidget(collect_btn)
            pay_row.addWidget(print_receipt_btn)
            pay_row.addWidget(close_pay_btn)
            pay_footer = QWidget()
            pay_footer.setLayout(pay_row)
            layout.addWidget(pay_footer)
            close_pay_btn.clicked.connect(dialog.reject)
        else:
            buttons = QDialogButtonBox(
                QDialogButtonBox.Save | QDialogButtonBox.Close
                if student_fields_editable
                else QDialogButtonBox.Close
            )
            layout.addWidget(buttons)
            buttons.rejected.connect(dialog.reject)

        def _refresh_read_only_student_widgets(s):
            if not student_fields_editable and s is not None:
                heading.setText(f"{s.full_name} ({s.student_id})")
                ro_student_id.setText(str(s.student_id or "-"))
                ro_name.setText(str(s.full_name or "-"))
                ro_class.setText(str(s.class_name or "-"))
                ro_section.setText(str(s.section or "-"))
                ro_phone.setText(str(s.phone or "-"))
                ro_village.setText(str(getattr(s, "village", None) or "-"))
                ro_guardian.setText(str(s.guardian_name or "-"))
                ro_status.setText(str(s.status or "-"))
                if lbl_van_fees is not None:
                    lbl_van_fees.setText(f"{float(getattr(s, 'van_fees', 0) or 0):.2f}")
                if lbl_school_fees is not None:
                    lbl_school_fees.setText(f"{float(getattr(s, 'school_fees', 0) or 0):.2f}")
                if popup_out_van is not None and popup_out_school is not None and popup_out_total is not None:
                    d = self.payment_service.get_student_due_breakdown(s.id)
                    popup_out_van.setText(f"{d['van_due']:.2f}")
                    popup_out_school.setText(f"{d['fee_due']:.2f}")
                    popup_out_total.setText(f"{d['total']:.2f}")
                lbl_pk.setText(str(s.id))
                lbl_created.setText(str(s.created_at or "-"))

        def on_save():
            try:
                updated = self.student_service.update_student(
                    student,
                    edit_student_id.text(),
                    edit_name.text(),
                    edit_class.text(),
                    edit_section.text(),
                    edit_phone.text(),
                    edit_village.currentText(),
                    edit_guardian.text(),
                    edit_status.currentText(),
                    village_fee_service=self.village_van_fee_service,
                    class_fee_service=self.class_fee_service,
                )
                self.selected_student = updated
                self._load_payment_student_options()
                self.perform_search()
                self._load_report_filter_values()
                QMessageBox.information(self, "Student updated", f"Student {updated.full_name} ({updated.student_id}) updated successfully.")
                heading.setText(f"{updated.full_name} ({updated.student_id})")
                lbl_van_fees_editable.setText(f"{float(updated.van_fees):.2f}")
                if lbl_school_fees_editable is not None:
                    lbl_school_fees_editable.setText(f"{float(updated.school_fees):.2f}")
                if popup_out_van is not None and popup_out_school is not None and popup_out_total is not None:
                    d = self.payment_service.get_student_due_breakdown(updated.id)
                    popup_out_van.setText(f"{d['van_due']:.2f}")
                    popup_out_school.setText(f"{d['fee_due']:.2f}")
                    popup_out_total.setText(f"{d['total']:.2f}")
            except IntegrityError:
                self.session.rollback()
                QMessageBox.warning(dialog, "Duplicate value", "Student ID or phone already exists. Please use unique values.")
            except Exception as e:
                self.session.rollback()
                QMessageBox.critical(dialog, "Update error", str(e))

        def _parse_split_payment_form():
            school_txt = (popup_school_pay.text() or "").strip()
            van_txt = (popup_van_pay.text() or "").strip()
            disc_txt = (popup_discount.text() or "").strip()
            school_amt = float(school_txt) if school_txt else 0.0
            van_amt = float(van_txt) if van_txt else 0.0
            disc_amt = float(disc_txt) if disc_txt else 0.0
            qd = popup_payment_date.date()
            pay_date = date(qd.year(), qd.month(), qd.day())
            return school_amt, van_amt, disc_amt, pay_date

        def _finalize_after_payment_saved():
            self.session.refresh(student)
            d = self.payment_service.get_student_due_breakdown(student.id)
            popup_out_van.setText(f"{d['van_due']:.2f}")
            popup_out_school.setText(f"{d['fee_due']:.2f}")
            popup_out_total.setText(f"{d['total']:.2f}")
            _refresh_read_only_student_widgets(student)
            popup_school_pay.clear()
            popup_van_pay.clear()
            popup_discount.clear()
            popup_payment_date.setDate(QDate.currentDate())
            self.perform_search()
            self._load_payment_student_options()
            self._refresh_payment_history_table()

        def on_collect_payment():
            try:
                school_amt, van_amt, disc_amt, pay_date = _parse_split_payment_form()
                payment = self.payment_service.collect_split_payment(
                    student,
                    van_amt,
                    school_amt,
                    popup_mode.text() or "cash",
                    "desktop_user",
                    disc_amt,
                    pay_date,
                )
                QMessageBox.information(dialog, "Payment saved", f"Reference: {payment.reference_no}")
                _finalize_after_payment_saved()
            except Exception as e:
                QMessageBox.critical(dialog, "Payment error", str(e))

        def on_print_receipt():
            try:
                school_amt, van_amt, disc_amt, pay_date = _parse_split_payment_form()
                payment = self.payment_service.collect_split_payment(
                    student,
                    van_amt,
                    school_amt,
                    popup_mode.text() or "cash",
                    "desktop_user",
                    disc_amt,
                    pay_date,
                )
            except Exception as e:
                QMessageBox.critical(dialog, "Payment error", str(e))
                return

            due_after = self.payment_service.get_student_due_breakdown(student.id)
            total_fees_due = float(due_after.get("total", 0.0) or 0.0)

            default_name = f"Receipt_{student.student_id}_{payment.reference_no}.pdf"
            path, _ = QFileDialog.getSaveFileName(
                dialog, "Save receipt", str(Path.home() / default_name), "PDF (*.pdf)"
            )
            pdf_note = ""
            if path:
                if not str(path).lower().endswith(".pdf"):
                    path = f"{path}.pdf"
                try:
                    render_payment_receipt(
                        Path(path),
                        student_name=student.full_name or "",
                        roll_number=str(student.student_id or ""),
                        class_name=str(student.class_name or ""),
                        section=str(student.section or ""),
                        guardian_name=str(student.guardian_name or ""),
                        school_fees_paid=school_amt,
                        van_fees_paid=van_amt,
                        discount=disc_amt,
                        total_fees_due=total_fees_due,
                        receipt_no=payment.reference_no,
                        generated_at=datetime.now(),
                    )
                    pdf_note = f"\n\nReceipt saved to:\n{path}"
                except Exception as e:
                    QMessageBox.warning(
                        dialog,
                        "Receipt file error",
                        f"Payment was saved (Reference: {payment.reference_no}) but the PDF could not be written:\n{e}",
                    )
                    _finalize_after_payment_saved()
                    return
            else:
                pdf_note = "\n\nNo PDF was saved (save dialog cancelled)."

            QMessageBox.information(
                dialog,
                "Payment saved",
                f"Reference: {payment.reference_no}{pdf_note}",
            )
            _finalize_after_payment_saved()

        if not show_payment_ui and student_fields_editable:
            buttons.accepted.connect(on_save)
        if collect_btn is not None:
            collect_btn.clicked.connect(on_collect_payment)
        if print_receipt_btn is not None:
            print_receipt_btn.clicked.connect(on_print_receipt)
        dialog.exec()
    def _class_sort_value(self, class_name):
        cls = str(class_name or "").strip()
        if cls.isdigit():
            return (0, int(cls))
        return (1, cls.lower())
    def on_student_search_basis_changed(self, _=None):
        basis = self.search_by.currentText() if hasattr(self, "search_by") else "Name"
        if basis == "Roll Number":
            self.search_input.setPlaceholderText("Enter student roll number")
        else:
            self.search_input.setPlaceholderText("Enter student name")
        self.perform_search()
    def perform_search(self):
        search_text = (self.search_input.text() or "").strip()
        search_basis = self.search_by.currentText() if hasattr(self, "search_by") else "Name"
        if search_text:
            students = self.student_service.list_students()
            q = search_text.lower()
            if search_basis == "Roll Number":
                students = [s for s in students if q in str(s.student_id or "").lower()]
            else:
                students = [s for s in students if q in str(s.full_name or "").lower()]
        else:
            students=self.student_service.search_students("")
        summaries = self.payment_service.get_students_school_fee_summary([s.id for s in students])
        van_summaries = self.payment_service.get_students_van_fee_summary([s.id for s in students])
        due_map = self.payment_service.get_students_due_breakdown([s.id for s in students])
        discount_map = self.payment_service.get_students_cumulative_payment_discount([s.id for s in students])
        sort_field = self.sort_by.currentText()
        reverse_sort = self.sort_order.currentIndex() == 1
        def sort_key(student):
            summary = summaries.get(student.id, {"fee_paid": 0.0, "fee_due": 0.0, "total_fees": 0.0})
            van_s = van_summaries.get(student.id, {"van_paid": 0.0, "van_due": 0.0})
            due = due_map.get(student.id, {"van_due": 0.0, "fee_due": 0.0, "total": 0.0})
            disc = float(discount_map.get(student.id, 0.0) or 0.0)
            if sort_field == "PK":
                return student.id
            if sort_field == "Student ID":
                return (student.student_id or "").lower()
            if sort_field == "Name":
                return (student.full_name or "").lower()
            if sort_field == "Class":
                return self._class_sort_value(student.class_name)
            if sort_field == "Section":
                return (student.section or "").lower()
            if sort_field == "Phone":
                return (student.phone or "").lower()
            if sort_field == "Guardian Name":
                return (getattr(student, "guardian_name", None) or "").lower()
            if sort_field == "Village":
                return (getattr(student, "village", None) or "").lower()
            if sort_field == "Status":
                return (student.status or "").lower()
            if sort_field == "Van Fees":
                return float(getattr(student, "van_fees", 0) or 0)
            if sort_field == "Van Fees Paid":
                return float(van_s["van_paid"])
            if sort_field == "Van Fees Due":
                return float(due["van_due"])
            if sort_field == "School Fees":
                return float(getattr(student, "school_fees", 0) or 0)
            if sort_field == "School Fees Paid":
                return float(summary["fee_paid"])
            if sort_field == "Discount":
                return disc
            if sort_field == "School Fees Due":
                return float(due["fee_due"])
            if sort_field == "Total Fees":
                return float(summary["total_fees"])
            if sort_field == "Total Fees Due":
                return float(due["total"])
            return student.id
        students.sort(key=sort_key, reverse=reverse_sort)
        self.student_table.setRowCount(len(students))
        for i,s in enumerate(students):
            summary = summaries.get(s.id, {"fee_paid": 0.0, "fee_due": 0.0, "total_fees": 0.0})
            van_s = van_summaries.get(s.id, {"van_paid": 0.0, "van_due": 0.0})
            due = due_map.get(s.id, {"van_due": 0.0, "fee_due": 0.0, "total": 0.0})
            disc = float(discount_map.get(s.id, 0.0) or 0.0)
            v_text = str(getattr(s, "village", None) or "")
            g_text = str(getattr(s, "guardian_name", None) or "")
            self.student_table.setItem(i, 0, QTableWidgetItem(str(s.id)))
            self.student_table.setItem(i, 1, QTableWidgetItem(s.student_id))
            self.student_table.setItem(i, 2, QTableWidgetItem(s.full_name))
            self.student_table.setItem(i, 3, QTableWidgetItem(str(s.class_name)))
            self.student_table.setItem(i, 4, QTableWidgetItem(str(s.section)))
            self.student_table.setItem(i, 5, QTableWidgetItem(s.phone))
            self.student_table.setItem(i, 6, QTableWidgetItem(g_text))
            self.student_table.setItem(i, 7, QTableWidgetItem(v_text))
            self.student_table.setItem(i, 8, QTableWidgetItem(s.status))
            self.student_table.setItem(i, 9, QTableWidgetItem(f"{float(getattr(s, 'van_fees', 0) or 0):.2f}"))
            self.student_table.setItem(i, 10, QTableWidgetItem(f"{van_s['van_paid']:.2f}"))
            self.student_table.setItem(i, 11, QTableWidgetItem(f"{due['van_due']:.2f}"))
            self.student_table.setItem(i, 12, QTableWidgetItem(f"{float(getattr(s, 'school_fees', 0) or 0):.2f}"))
            self.student_table.setItem(i, 13, QTableWidgetItem(f"{summary['fee_paid']:.2f}"))
            self.student_table.setItem(i, 14, QTableWidgetItem(f"{disc:.2f}"))
            self.student_table.setItem(i, 15, QTableWidgetItem(f"{due['fee_due']:.2f}"))
            self.student_table.setItem(i, 16, QTableWidgetItem(f"{summary['total_fees']:.2f}"))
            self.student_table.setItem(i, 17, QTableWidgetItem(f"{due['total']:.2f}"))
    def on_student_selected(self,row,_):
        item=self.student_table.item(row,0)
        if not item: return
        s=self.session.get(Student,int(item.text()))
        if not s: return
        self.selected_student=s; self.student_info.setText(f"Selected: {s.full_name} ({s.student_id}) — Van: {float(getattr(s, 'van_fees', 0) or 0):.2f}, School: {float(getattr(s, 'school_fees', 0) or 0):.2f}")
        self._populate_payment_student_options()
    def add_student(self):
        try:
            st = self.student_service.create_student(
                self.add_student_id.text(),
                self.add_student_name.text(),
                self.add_student_class.currentText(),
                self.add_student_section.currentText(),
                self.add_student_phone.text(),
                self.add_student_village.currentText(),
                self.add_student_guardian.text(),
                self.add_student_status.currentText(),
                village_fee_service=self.village_van_fee_service,
                class_fee_service=self.class_fee_service,
            )
            self.add_student_id.clear()
            self.add_student_name.clear()
            self.add_student_class.setCurrentIndex(3)
            self.add_student_section.setCurrentIndex(0)
            self.add_student_phone.clear()
            self.add_student_village.setCurrentIndex(0)
            self.add_student_guardian.clear()
            self.add_student_status.setCurrentIndex(0)
            self._load_report_filter_values()
            self._load_payment_student_options()
            self.perform_search()
            QMessageBox.information(self, "Student added", f"Student {st.full_name} ({st.student_id}) added successfully.")
        except IntegrityError:
            self.session.rollback()
            QMessageBox.warning(self, "Duplicate value", "Student ID or phone already exists. Please use unique values.")
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Add student error", str(e))
    def load_defaulters(self):
        selected_class = self.report_class.currentData()
        selected_section = self.report_section.currentData()
        rows=self.report_service.get_defaulters(student_query=self.report_student_input.text(), class_name=selected_class, section=selected_section); self.report_table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            self.report_table.setItem(i,0,QTableWidgetItem(str(r.student_id))); self.report_table.setItem(i,1,QTableWidgetItem(str(r.full_name))); self.report_table.setItem(i,2,QTableWidgetItem(str(r.class_name))); self.report_table.setItem(i,3,QTableWidgetItem(str(r.section))); self.report_table.setItem(i,4,QTableWidgetItem(f"{float(r.outstanding):.2f}"))
    def _rows(self):
        out=[]
        for i in range(self.report_table.rowCount()): out.append({"student_id":self.report_table.item(i,0).text(),"name":self.report_table.item(i,1).text(),"class":self.report_table.item(i,2).text(),"section":self.report_table.item(i,3).text(),"outstanding":self.report_table.item(i,4).text()})
        return out
    def export_excel(self):
        p,_=QFileDialog.getSaveFileName(self,"Save Excel","defaulters.xlsx","Excel Files (*.xlsx)")
        if not p: return
        ExcelExporter.export_rows(self._rows(), Path(p)); QMessageBox.information(self,"Exported",f"Excel report saved to {p}")
    def export_pdf(self):
        p,_=QFileDialog.getSaveFileName(self,"Save PDF","defaulters.pdf","PDF Files (*.pdf)")
        if not p: return
        rows=self._rows(); table=[[r["student_id"],r["name"],r["class"],r["section"],r["outstanding"]] for r in rows]
        PdfExporter.export_simple_table("Defaulter Report",["Student ID","Name","Class","Section","Outstanding"],table,Path(p)); QMessageBox.information(self,"Exported",f"PDF report saved to {p}")
    def create_backup(self):
        p=self.backup_service.create_backup(); self.backup_status.setText(f"Backup created: {p}")
    def restore_backup(self):
        p,_=QFileDialog.getOpenFileName(self,"Choose backup","","DB Files (*.db *.sqlite *.sqlite3)")
        if not p: return
        self.backup_service.restore_backup(Path(p)); self.backup_status.setText(f"Backup restored from: {p}")
