from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtGui import QColor, QIcon
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
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.exc import IntegrityError
from backend.core.config import DB_PATH
from backend.core.fee_control_constants import (
    FIXED_CLASS_KEYS,
    FIXED_SECTION_KEYS,
    canonical_class_for_student_class,
)
from backend.models import Student
from backend.services.academic_year_service import AcademicYearService
from backend.services.backup_service import BackupService
from backend.services.class_fee_service import ClassFeeService
from backend.services.village_van_fee_service import VillageVanFeeService
from backend.services.payment_service import PaymentService
from backend.services.report_service import ReportService
from backend.services.student_service import StudentService
from frontend.ui.academic_year_dialog import AcademicYearDialog
from frontend.ui.add_student_page import AddStudentPage
from frontend.ui.app_shell import AppShell
from frontend.ui.school_branding import (
    breadcrumb_trail,
    load_logo_pixmap,
    resolve_logo_path,
    school_window_title,
)
from frontend.ui.edudash_widgets import SurfaceCard, wrap_page
from frontend.ui.home_page import HomePageTab
from frontend.ui.pagination import PAGE_SIZE, PaginationBar, page_count, slice_page
from frontend.ui.student_details_tab import StudentDetailsTab
from frontend.ui.table_style import (
    apply_button_cell,
    configure_data_table,
    configure_fee_editor_table,
    refresh_tables_in,
    style_fee_action_button,
    table_item,
)
from frontend.ui import theme
from frontend.ui.theme import style_primary as style_primary_button


_SEARCH_TABLE_HEADERS = [
    "PK",
    "Student ID",
    "Name",
    "Class",
    "Section",
    "Phone",
    "Guardian Name",
    "Village",
    "Status",
    "Van Fees",
    "Van Paid",
    "Van Pending",
    "Van Due (current)",
    "School Fees",
    "School Paid",
    "Discount",
    "School Pending",
    "School Due (current)",
    "School Payable (total)",
    "Total Due",
]
# Column index for header-click sorting (Student Search tab).
_SEARCH_SORTABLE_COLUMNS: dict[str, int] = {
    "Student ID": 1,
    "Name": 2,
    "Class": 3,
    "Village": 7,
}


@dataclass
class PaymentLikePane:
    search_by: QComboBox
    student_search: QLineEdit
    student_results: QListWidget
    hint: QLabel
    pagination: PaginationBar | None = None
    page_index: int = 0
    filtered_ids: list | None = None

    def __post_init__(self):
        if self.filtered_ids is None:
            self.filtered_ids = []


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
        self.academic_year_service = AcademicYearService(session)
        self.selected_student = None
        self._payment_panes: dict[str, PaymentLikePane] = {}
        self._search_page = 0
        self._search_cache: list = []
        self._search_fee_maps: dict = {}
        self._search_fee_maps_complete = False
        self._search_sort_column = "Student ID"
        self._search_sort_ascending = True
        self._report_page = 0
        self._report_defaulter_rows: list = []
        self._payment_history_page = 0
        self._payment_history_cache: list = []
        self._all_payment_students = None
        self._details_page_index = 0
        self._details_filtered_ids: list[int] = []
        self._details_due_map: dict = {}
        self._student_details_tab: StudentDetailsTab | None = None
        self.setWindowTitle(school_window_title())
        logo_path = resolve_logo_path()
        if logo_path is not None:
            self.setWindowIcon(QIcon(str(logo_path)))
        self.resize(1360, 860)
        self._shell = AppShell()
        self._tab_names = [
            "Home Page",
            "Student Search",
            "Student Details",
            "Collect Payment",
            "Add Student",
            "Reports",
            "Backup",
            "Fee Control",
            "Payment History",
        ]
        builders = [
            self._build_home_tab,
            self._build_search_tab,
            self._build_student_details_tab,
            self._build_payment_tab,
            self._build_add_student_tab,
            self._build_reports_tab,
            self._build_backup_tab,
            self._build_fee_control_tab,
            self._build_payment_history_tab,
        ]
        for key, builder in zip(self._tab_names, builders):
            idx = self._shell.register_page(key, builder())
            if key == "Home Page":
                self._home_tab_index = idx
            if key == "Fee Control":
                self._fee_control_tab_index = idx
            if key == "Payment History":
                self._payment_history_tab_index = idx
        self._shell.page_changed.connect(self._on_main_tab_changed)
        self._global_search = self._shell.search_field()
        self._global_search.returnPressed.connect(self._on_global_search)
        self._global_search.textChanged.connect(self._on_global_search_changed)
        theme.ThemeManager.instance().theme_changed.connect(self._on_theme_changed)
        self.setCentralWidget(self._shell)
        self._shell._fab.clicked.connect(lambda: self._shell.go("Fee Control"))
        self._shell.go("Home Page")
        self.perform_search(reset_page=True)
    def _build_home_tab(self) -> HomePageTab:
        self._home_page = HomePageTab(
            on_navigate=self._navigate_to_tab,
            on_refresh=self._home_page_snapshot,
            on_chart_data=self._home_page_chart_data,
            on_manage_academic_years=self._on_manage_academic_years_clicked,
            parent=self,
        )
        return self._home_page

    def _home_page_chart_data(self, year: int, month: int) -> dict:
        """Daily collected amounts for a calendar month (from payments table)."""
        return self.payment_service.daily_cash_collected_for_month(year, month)

    def _refresh_dashboard(self, chart_date: date | None = None) -> None:
        """Reload dashboard metrics, chart, and payment list from the database."""
        self.session.expire_all()

        def _do_reload() -> None:
            home = getattr(self, "_home_page", None)
            if home is not None:
                home.reload(chart_date=chart_date)

        # Defer until after the payment dialog closes so the chart repaints reliably.
        QTimer.singleShot(0, _do_reload)

    def _navigate_to_tab(self, tab_name: str) -> None:
        aliases = {"Student List": "Student Search", "Add New Student": "Add Student"}
        self._shell.go(aliases.get(tab_name, tab_name))

    def _on_theme_changed(self, _mode: str) -> None:
        self._shell.refresh_theme()
        refresh_tables_in(self)
        theme.refresh_widget_tree(self._shell)
        home = getattr(self, "_home_page", None)
        if home is not None:
            home.refresh_theme()
            home.reload()
        self._refresh_student_views_theme()

    def _refresh_student_views_theme(self) -> None:
        add_page = getattr(self, "_add_student_page", None)
        if add_page is not None:
            add_page.refresh_theme()
        details = getattr(self, "_student_details_tab", None)
        if details is not None:
            details.refresh_theme()
        if hasattr(self, "student_table"):
            configure_data_table(self.student_table)
        add_village = getattr(self, "_add_village_btn", None)
        if add_village is not None:
            style_fee_action_button(add_village)
        for pane in self._payment_panes.values():
            theme.refresh_list_widget(pane.student_results)
        for btn in self.findChildren(QPushButton):
            variant = btn.property("variant")
            if variant in ("primary", "teal-outline", "icon"):
                theme.polish(btn, str(variant))

    def _current_tab_name(self) -> str:
        idx = self._shell.current_index()
        if 0 <= idx < len(self._tab_names):
            return self._tab_names[idx]
        return ""

    def _on_global_search_changed(self, text: str) -> None:
        self._route_global_search((text or "").strip(), live=True)

    def _on_global_search(self) -> None:
        self._route_global_search((self._global_search.text() or "").strip(), live=False)

    def _route_global_search(self, text: str, *, live: bool) -> None:
        tab_name = self._current_tab_name()
        if tab_name in ("Home Page", "Add Student"):
            return
        if tab_name == "Collect Payment":
            self._apply_search_to_payment_pane(text)
            return
        if tab_name == "Student Details":
            self._apply_search_to_details_tab(text)
            return
        if tab_name == "Payment History":
            self._apply_search_to_payment_history(text)
            return
        if tab_name == "Student Search":
            self._apply_search_to_student_search(text)
            return
        # Other tabs: jump to student search when user submits non-empty query
        if text and not live:
            self._navigate_to_tab("Student Search")
            self._apply_search_to_student_search(text)

    def _apply_search_to_student_search(self, text: str) -> None:
        if not hasattr(self, "search_by"):
            return
        if text:
            idx = self.search_by.findText("Name")
            if idx >= 0:
                self.search_by.setCurrentIndex(idx)
        if hasattr(self, "search_input"):
            self.search_input.blockSignals(True)
            try:
                self.search_input.setText(text)
            finally:
                self.search_input.blockSignals(False)
            self.perform_search(reset_page=True)

    def _apply_search_to_payment_pane(self, text: str) -> None:
        pane = self._payment_panes.get("payment")
        if pane is None:
            return
        if text:
            idx = pane.search_by.findText("Name")
            if idx >= 0:
                pane.search_by.setCurrentIndex(idx)
        pane.student_search.blockSignals(True)
        try:
            pane.student_search.setText(text)
        finally:
            pane.student_search.blockSignals(False)
        self._refresh_payment_pane("payment", reset_page=True)

    def _apply_search_to_details_tab(self, text: str) -> None:
        tab = self._student_details_tab
        if tab is None:
            return
        if text:
            idx = tab.search_by.findText("Name")
            if idx >= 0:
                tab.search_by.setCurrentIndex(idx)
        tab.student_search.blockSignals(True)
        try:
            tab.student_search.setText(text)
        finally:
            tab.student_search.blockSignals(False)
        self._refresh_details_tab(reset_page=True)

    def _apply_search_to_payment_history(self, text: str) -> None:
        if not hasattr(self, "_payment_history_filter"):
            return
        self._payment_history_filter.blockSignals(True)
        try:
            self._payment_history_filter.setText(text)
        finally:
            self._payment_history_filter.blockSignals(False)
        self._refresh_payment_history_table(reset_page=True)

    @staticmethod
    def _payment_record_date(value) -> date | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return None

    def _home_page_snapshot(self) -> dict:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        active, inactive = self.student_service.count_active_inactive()
        total_students = active + inactive
        current = self.academic_year_service.get_current()
        years = self.academic_year_service.list_years()
        if current:
            year_text = self.academic_year_service.format_year_display(current)
        else:
            year_text = "None (today is not inside any defined academic year range)"
        period = self.payment_service.dashboard_period_stats(week_start, today)
        collected_week = float(period["collected_week"])
        payments_week = int(period["payments_week"])
        payments_today = int(period["payments_today"])
        payments = self.payment_service.list_payment_history(limit=500)
        collected = sum(float(p.get("amount", 0) or 0) for p in payments)
        recent = []
        for p in payments[:12]:
            d = p.get("payment_date")
            date_s = d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d or "")
            name = str(p.get("student_name") or "")
            recent.append({
                "initial": name[:1] if name else "P",
                "name": name,
                "amount": float(p.get("amount", 0) or 0),
                "mode": str(p.get("mode") or ""),
                "date": date_s,
            })
        daily_revenue = self.payment_service.daily_cash_collected_for_month(today.year, today.month)
        week_range = (
            f"{week_start.strftime('%d %b')} – {today.strftime('%d %b %Y')}"
            if week_start != today
            else today.strftime("%d %b %Y")
        )
        return {
            "today": today,
            "current_academic_year": year_text,
            "academic_years_count": len(years),
            "students_active": active,
            "students_inactive": inactive,
            "students_total": total_students,
            "collected_week": collected_week,
            "collected_week_display": f"{collected_week:,.0f}",
            "payments_week": payments_week,
            "payments_today": payments_today,
            "week_range": week_range,
            "collected_display": f"{collected:,.0f}",
            "payments_count": len(payments),
            "database_path": str(DB_PATH),
            "revenue_chart": {
                "amounts": daily_revenue["amounts"],
                "month_label": daily_revenue["month_label"],
            },
            "recent_payments": recent,
        }

    def _build_search_tab(self):
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        search_refresh_btn = QPushButton("Refresh")
        search_refresh_btn.clicked.connect(self._on_student_search_refresh_clicked)
        toolbar.addWidget(search_refresh_btn)
        toolbar.addWidget(QLabel("Search by"))
        self.search_by = QComboBox()
        self.search_by.addItems(["Roll Number", "Name", "Village", "Class"])
        self.search_by.setCurrentIndex(1)
        self.search_by.currentIndexChanged.connect(self.on_student_search_basis_changed)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter students…")
        self.search_input.textChanged.connect(lambda _: self.perform_search(reset_page=True))
        toolbar.addWidget(self.search_by)
        toolbar.addWidget(self.search_input, 1)
        layout.addLayout(toolbar)

        table_card = SurfaceCard()
        self.student_table = QTableWidget(0, len(_SEARCH_TABLE_HEADERS))
        self.student_table.setHorizontalHeaderLabels(list(_SEARCH_TABLE_HEADERS))
        configure_data_table(self.student_table)
        self.student_table.cellClicked.connect(self.on_student_selected)
        search_header = self.student_table.horizontalHeader()
        search_header.setSectionsClickable(True)
        search_header.setSortIndicatorShown(True)
        search_header.sectionClicked.connect(self._on_search_table_header_clicked)
        self._update_search_sort_indicator()
        table_card.body.addWidget(self.student_table, 1)
        layout.addWidget(table_card, 1)

        self.student_info = QLabel("Select a student to view fee summary.")
        self.student_info.setProperty("role", "muted")
        self.student_info.setWordWrap(True)
        layout.addWidget(self.student_info)
        self._search_pagination = PaginationBar(
            lambda: self._search_change_page(-1),
            lambda: self._search_change_page(1),
        )
        layout.addWidget(self._search_pagination)
        return wrap_page(
            "Student List",
            breadcrumb_trail("Student", "Student List"),
            body,
        )
    def _build_student_details_tab(self) -> QWidget:
        tab = StudentDetailsTab()
        self._student_details_tab = tab
        self._details_pagination = PaginationBar(
            lambda: self._details_change_page(-1),
            lambda: self._details_change_page(1),
        )
        tab.pagination_layout.addStretch(1)
        tab.pagination_layout.addWidget(self._details_pagination.status_label)
        tab.pagination_layout.addWidget(self._details_pagination.prev_btn)
        tab.pagination_layout.addWidget(self._details_pagination.next_btn)

        tab.refresh_btn.clicked.connect(self._on_details_refresh_clicked)
        tab.student_search.textChanged.connect(lambda _: self._refresh_details_tab(reset_page=True))
        tab.search_by.currentIndexChanged.connect(self._on_details_search_basis_changed)
        tab.filter_active_only.toggled.connect(lambda _: self._refresh_details_tab(reset_page=True))
        tab.filter_outstanding_only.toggled.connect(lambda _: self._refresh_details_tab(reset_page=True))
        tab.student_results.itemClicked.connect(self._on_details_student_clicked)
        tab.student_results.itemDoubleClicked.connect(self._on_details_edit_clicked)
        tab.btn_edit.clicked.connect(self._on_details_edit_clicked)
        tab.btn_collect.clicked.connect(self._on_details_collect_payment_clicked)
        self._on_details_search_basis_changed()
        return wrap_page(
            "Student Details",
            breadcrumb_trail("Student", "Student Details"),
            tab,
        )

    def _build_payment_tab(self):
        body = self._create_payment_like_tab("payment")
        return wrap_page(
            "Collect Payment",
            breadcrumb_trail("Fees Collection", "Collect Payment"),
            body,
        )

    def _create_payment_like_tab(self, pane_id: str):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(lambda _=False, p=pane_id: self._on_payment_pane_refresh_clicked(p))
        toolbar.addWidget(refresh_btn)
        toolbar.addWidget(QLabel("Search by"))
        search_by = QComboBox()
        search_by.addItems(["Roll Number", "Name", "Phone", "Village", "Class-Section", "Status", "Guardian Name"])
        search_by.setCurrentIndex(1)
        search_by.currentIndexChanged.connect(lambda _=None, p=pane_id: self._on_payment_search_basis_changed(p))
        student_search = QLineEdit()
        student_search.textChanged.connect(
            lambda t, p=pane_id: self._refresh_payment_pane(p, reset_page=True)
        )
        toolbar.addWidget(search_by)
        toolbar.addWidget(student_search, 1)
        outer.addLayout(toolbar)

        list_card = SurfaceCard()
        student_results = QListWidget()
        theme.refresh_list_widget(student_results)
        student_results.itemClicked.connect(lambda item, p=pane_id: self._on_payment_student_selected(p, item))
        student_results.itemDoubleClicked.connect(
            lambda item, p=pane_id: self._on_payment_student_double_clicked(p, item)
        )
        hint = QLabel("Double-click a student to open payment collection.")
        hint.setProperty("role", "hint")
        list_card.body.addWidget(student_results, 1)
        list_card.body.addWidget(hint)
        outer.addWidget(list_card, 1)

        pagination = PaginationBar(
            lambda _checked=False, p=pane_id: self._payment_change_page(p, -1),
            lambda _checked=False, p=pane_id: self._payment_change_page(p, 1),
        )
        outer.addWidget(pagination)
        self._payment_panes[pane_id] = PaymentLikePane(
            search_by=search_by,
            student_search=student_search,
            student_results=student_results,
            hint=hint,
            pagination=pagination,
        )
        student_search.setPlaceholderText("Enter student name")
        return w
    def _build_add_student_tab(self):
        page = AddStudentPage(self._populate_village_combo, parent=self)
        self._add_student_page = page
        self.add_student_id = page.student_id
        self.add_student_name = page.full_name
        self.add_student_class = page.student_class
        self.add_student_section = page.section
        self.add_student_phone = page.phone
        self.add_student_village = page.village
        self.add_student_transport = page.transport
        self.add_student_guardian = page.guardian_name
        self.add_student_status = page.status
        page.submit_btn.clicked.connect(self.add_student)
        return page

    def _populate_village_combo(self, combo: QComboBox) -> None:
        combo.clear()
        for k in self.village_van_fee_service.list_village_keys_for_fee_control():
            combo.addItem(k)

    def _populate_class_combo(self, combo: QComboBox) -> None:
        combo.clear()
        combo.addItems(list(FIXED_CLASS_KEYS))

    def _populate_section_combo(self, combo: QComboBox) -> None:
        combo.clear()
        combo.addItems(list(FIXED_SECTION_KEYS))

    @staticmethod
    def _canonical_section_for_combo(section: str | None) -> str | None:
        s = (section or "").strip().upper()
        return s if s in FIXED_SECTION_KEYS else None

    @staticmethod
    def _select_combo_value(combo: QComboBox, value: str | None, *, canonical=None) -> None:
        """Select combo item; optional canonical() maps legacy text to a list key."""
        raw = (value or "").strip()
        if not raw:
            return
        pick = canonical(raw) if canonical else None
        if pick:
            idx = combo.findText(pick, Qt.MatchFixedString)
            if idx >= 0:
                combo.setCurrentIndex(idx)
                return
        if combo.findText(raw, Qt.MatchFixedString) < 0:
            combo.addItem(raw)
        idx = combo.findText(raw, Qt.MatchFixedString)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _build_reports_tab(self):
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        toolbar = QHBoxLayout()
        self.report_student_input = QLineEdit()
        self.report_student_input.setPlaceholderText("Student ID or name")
        self.report_class = QComboBox()
        self.report_class.addItem("All Classes", None)
        self.report_section = QComboBox()
        self.report_section.addItem("All Sections", None)
        self._load_report_filter_values()
        a = QPushButton("Load defaulters")
        style_primary_button(a)
        a.clicked.connect(lambda: self.load_defaulters(reset_page=True))
        b = QPushButton("Export Excel")
        b.clicked.connect(self.export_excel)
        c = QPushButton("Export PDF")
        c.clicked.connect(self.export_pdf)
        toolbar.addWidget(self.report_student_input, 1)
        toolbar.addWidget(self.report_class)
        toolbar.addWidget(self.report_section)
        toolbar.addWidget(a)
        toolbar.addWidget(b)
        toolbar.addWidget(c)
        layout.addLayout(toolbar)
        card = SurfaceCard()
        self.report_table = QTableWidget(0, 5)
        self.report_table.setHorizontalHeaderLabels(
            ["Student ID", "Name", "Class", "Section", "Outstanding"]
        )
        configure_data_table(self.report_table)
        card.body.addWidget(self.report_table, 1)
        layout.addWidget(card, 1)
        self._report_pagination = PaginationBar(
            lambda: self._report_change_page(-1),
            lambda: self._report_change_page(1),
        )
        layout.addWidget(self._report_pagination)
        return wrap_page("Reports", breadcrumb_trail("Reports"), body)
    def _load_report_filter_values(self):
        values = self.report_service.get_report_filter_values()
        self.report_class.clear(); self.report_class.addItem("All Classes", None)
        self.report_section.clear(); self.report_section.addItem("All Sections", None)
        for c in values.get("classes", []):
            self.report_class.addItem(str(c), str(c))
        for s in values.get("sections", []):
            self.report_section.addItem(str(s), str(s))
    def _build_backup_tab(self):
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        card = SurfaceCard()
        hint = QLabel("Safeguard your local database before major changes or device migration.")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        card.body.addWidget(hint)
        row = QHBoxLayout()
        a = QPushButton("Create backup")
        style_primary_button(a)
        a.clicked.connect(self.create_backup)
        b = QPushButton("Restore backup")
        b.clicked.connect(self.restore_backup)
        row.addWidget(a)
        row.addWidget(b)
        row.addStretch(1)
        card.body.addLayout(row)
        self.backup_status = QLabel("No backup action performed yet.")
        self.backup_status.setProperty("role", "muted")
        self.backup_status.setWordWrap(True)
        card.body.addWidget(self.backup_status)
        layout.addWidget(card)
        layout.addStretch(1)
        return wrap_page("Backup", breadcrumb_trail("Backup"), body)

    def _build_fee_control_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        intro = SurfaceCard()
        school_lbl = QLabel(
            "School fees: set the tariff for each class (fixed list). Apply updates matching students’ school fees "
            "and tuition invoices only."
        )
        school_lbl.setWordWrap(True)
        school_lbl.setProperty("role", "muted")
        van_lbl = QLabel(
            "Van fees: set tariffs per village. Use “Add village” for new villages. Own-transport students are skipped."
        )
        van_lbl.setWordWrap(True)
        van_lbl.setProperty("role", "muted")
        confirm_lbl = QLabel("A confirmation is required before saving each row.")
        confirm_lbl.setProperty("role", "hint")
        intro.body.addWidget(school_lbl)
        intro.body.addWidget(van_lbl)
        intro.body.addWidget(confirm_lbl)
        academic_years_row = QHBoxLayout()
        manage_years_btn = QPushButton("Manage academic years")
        style_primary_button(manage_years_btn)
        manage_years_btn.setToolTip("Add or edit academic year date ranges (DD/MM/YYYY).")
        manage_years_btn.clicked.connect(self._on_manage_academic_years_clicked)
        academic_years_row.addWidget(manage_years_btn)
        academic_years_row.addStretch(1)
        intro.body.addLayout(academic_years_row)
        layout.addWidget(intro)

        tables_row = QHBoxLayout()
        tables_row.setSpacing(16)
        self._fee_control_amount_edits = {}
        tbl_school = QTableWidget(len(FIXED_CLASS_KEYS), 3)
        tbl_school.setHorizontalHeaderLabels(["Class", "School fee (₹)", "Action"])
        configure_fee_editor_table(tbl_school)
        for row, class_key in enumerate(FIXED_CLASS_KEYS):
            class_item = table_item(class_key)
            tbl_school.setItem(row, 0, class_item)
            amount_edit = QLineEdit()
            amount_edit.setPlaceholderText("20000")
            self._fee_control_amount_edits[class_key] = amount_edit
            tbl_school.setCellWidget(row, 1, amount_edit)
            tbl_school.setCellWidget(
                row,
                2,
                apply_button_cell(lambda _=False, ck=class_key: self._on_fee_control_apply_clicked(ck)),
            )

        self._van_fee_control_panel = QWidget()
        van_panel_layout = QVBoxLayout(self._van_fee_control_panel)
        self._van_fee_control_table = self._create_van_fee_control_table()
        van_panel_layout.addWidget(self._van_fee_control_table)
        self._add_village_btn = QPushButton("Add village")
        style_fee_action_button(self._add_village_btn)
        self._add_village_btn.clicked.connect(self._on_add_village_fee_clicked)
        add_village_row = QHBoxLayout()
        add_village_row.addStretch(1)
        add_village_row.addWidget(self._add_village_btn)
        van_panel_layout.addLayout(add_village_row)

        school_card = SurfaceCard()
        school_title = QLabel("School fees by class")
        school_title.setProperty("role", "section-title")
        school_card.body.addWidget(school_title)
        school_card.body.addWidget(tbl_school, 1)
        van_card = SurfaceCard()
        van_title = QLabel("Van fees by village")
        van_title.setProperty("role", "section-title")
        van_card.body.addWidget(van_title)
        van_card.body.addWidget(self._van_fee_control_panel, 1)
        tables_row.addWidget(school_card, 1)
        tables_row.addWidget(van_card, 1)
        layout.addLayout(tables_row, 1)
        self._fee_control_table = tbl_school
        self._refresh_fee_control_amounts()
        self._refresh_van_fee_control_amounts()
        return wrap_page("Fee Control", breadcrumb_trail("Fee Control"), w)

    def _on_manage_academic_years_clicked(self) -> None:
        dlg = AcademicYearDialog(
            self.session,
            self.class_fee_service,
            self.village_van_fee_service,
            parent=self,
        )
        dlg.exec()
        self.perform_search(reset_page=False)
        self._invalidate_payment_student_cache()

    @staticmethod
    def _format_fee_due_lines(due: dict) -> str:
        return (
            f"Van pending: {due.get('van_pending', 0):.2f} | Van due (current): {due.get('van_due', 0):.2f} — "
            f"School pending: {due.get('school_pending', 0):.2f} | School due (current): {due.get('fee_due', 0):.2f} | "
            f"Total payable: {due.get('total', 0):.2f}"
        )

    def _create_van_fee_control_table(self) -> QTableWidget:
        self._van_fee_control_amount_edits = {}
        keys = self.village_van_fee_service.list_village_keys_for_fee_control()
        tbl = QTableWidget(len(keys), 3)
        tbl.setHorizontalHeaderLabels(["Village", "Van fee (₹)", "Action"])
        configure_fee_editor_table(tbl)
        for row, village_key in enumerate(keys):
            tbl.setItem(row, 0, table_item(village_key))
            v_edit = QLineEdit()
            v_edit.setPlaceholderText("0")
            self._van_fee_control_amount_edits[village_key] = v_edit
            tbl.setCellWidget(row, 1, v_edit)
            tbl.setCellWidget(
                row,
                2,
                apply_button_cell(lambda _=False, vk=village_key: self._on_van_fee_control_apply_clicked(vk)),
            )
        return tbl

    def _rebuild_van_fee_control_table(self) -> None:
        panel = getattr(self, "_van_fee_control_panel", None)
        if panel is None:
            return
        lay = panel.layout()
        if lay is None or lay.count() < 1:
            return
        old_tbl = lay.itemAt(0).widget()
        new_tbl = self._create_van_fee_control_table()
        lay.replaceWidget(old_tbl, new_tbl)
        old_tbl.deleteLater()
        self._van_fee_control_table = new_tbl
        self._refresh_van_fee_control_amounts()

    def _on_add_village_fee_clicked(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Add village")
        theme.apply_dialog_theme(dlg)
        form = QFormLayout(dlg)
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Village name")
        fee_edit = QLineEdit()
        fee_edit.setPlaceholderText("0.00")
        form.addRow("Village name", name_edit)
        form.addRow("Van fee (₹)", fee_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted:
            return
        raw_fee = (fee_edit.text() or "").strip()
        try:
            fee = float(raw_fee) if raw_fee else 0.0
        except ValueError:
            QMessageBox.warning(self, "Invalid amount", "Enter a valid number for the van fee.")
            return
        try:
            stored = self.village_van_fee_service.register_new_village(name_edit.text(), fee)
        except Exception as e:
            QMessageBox.critical(self, "Add village failed", str(e))
            return
        self._rebuild_van_fee_control_table()
        self._populate_village_combo(self.add_student_village)
        QMessageBox.information(
            self,
            "Village added",
            f"Village “{stored}” was added with van fee {fee:.2f}.",
        )

    def _on_main_tab_changed(self, index: int):
        if index == getattr(self, "_home_tab_index", -1):
            home = getattr(self, "_home_page", None)
            if home is not None:
                home.reload()
        tab_name = self._tab_names[index] if 0 <= index < len(self._tab_names) else ""
        if tab_name == "Add Student":
            self._populate_village_combo(self.add_student_village)
        if index == getattr(self, "_fee_control_tab_index", -1):
            self._refresh_fee_control_amounts()
            self._refresh_van_fee_control_amounts()
        if index == getattr(self, "_payment_history_tab_index", -1):
            self._refresh_payment_history_table(reset_page=False)
        if tab_name == "Student Details":
            self._refresh_details_tab(reset_page=False)
        if tab_name == "Collect Payment":
            self._ensure_payment_students_loaded()
            self._refresh_payment_pane("payment", reset_page=False)
        self._update_global_search_placeholder(tab_name)

    def _update_global_search_placeholder(self, tab_name: str) -> None:
        placeholders = {
            "Collect Payment": "Search students by name, roll number, phone…",
            "Student Search": "Search students by name, roll, village, class…",
            "Student Details": "Find a student by name, roll number, phone…",
            "Payment History": "Filter by reference, student ID, or name…",
        }
        self._shell.set_search_placeholder(placeholders.get(tab_name, "Search"))

    def _build_payment_history_tab(self):
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(
            "Recorded payments (newest first). Filter by reference, student ID, or name. "
            "Collected (₹) is school + van + discount; discount applies to school fees only."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "hint")
        layout.addWidget(hint)
        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._on_payment_history_refresh_clicked)
        toolbar.addWidget(refresh_btn)
        toolbar.addWidget(QLabel("Filter"))
        self._payment_history_filter = QLineEdit()
        self._payment_history_filter.setPlaceholderText("Reference, student ID, or name…")
        self._payment_history_filter.textChanged.connect(
            lambda _: self._refresh_payment_history_table(reset_page=True)
        )
        toolbar.addWidget(self._payment_history_filter, 1)
        layout.addLayout(toolbar)
        card = SurfaceCard()
        self._payment_history_table = QTableWidget(0, 8)
        self._payment_history_table.setHorizontalHeaderLabels(
            ["Date", "Reference", "Student ID", "Name", "Total (₹)", "Discount (₹)", "Mode", "Operator"]
        )
        configure_data_table(self._payment_history_table)
        card.body.addWidget(self._payment_history_table, 1)
        layout.addWidget(card, 1)
        self._payment_history_pagination = PaginationBar(
            lambda: self._payment_history_change_page(-1),
            lambda: self._payment_history_change_page(1),
        )
        layout.addWidget(self._payment_history_pagination)
        return wrap_page(
            "Payment History",
            breadcrumb_trail("Fees Collection", "Payment History"),
            body,
        )

    def _on_payment_history_refresh_clicked(self):
        """Clear filter, reset to page 1, and reload all payment history."""
        if hasattr(self, "_payment_history_filter"):
            self._payment_history_filter.blockSignals(True)
            try:
                self._payment_history_filter.clear()
            finally:
                self._payment_history_filter.blockSignals(False)
        self._refresh_payment_history_table(reset_page=True)

    def _refresh_payment_history_table(self, reset_page: bool = False):
        if not hasattr(self, "_payment_history_table"):
            return
        if reset_page:
            self._payment_history_page = 0
        search = self._payment_history_filter.text() if hasattr(self, "_payment_history_filter") else ""
        self._payment_history_cache = self.payment_service.list_payment_history(limit=50000, search=search)
        self._render_payment_history_page()

    def _render_payment_history_page(self):
        if not hasattr(self, "_payment_history_table"):
            return
        rows = slice_page(self._payment_history_cache, self._payment_history_page)
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
        if hasattr(self, "_payment_history_pagination"):
            self._payment_history_pagination.update_state(
                self._payment_history_page, len(self._payment_history_cache)
            )

    def _payment_history_change_page(self, delta: int):
        new_page = self._payment_history_page + delta
        if new_page < 0 or new_page >= page_count(len(self._payment_history_cache)):
            return
        self._payment_history_page = new_page
        self._render_payment_history_page()

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
            self.perform_search(reset_page=True)
            self._load_report_filter_values()
            self._invalidate_payment_student_cache()
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
        n = self.village_van_fee_service.count_students_on_van_transport_in_village(village_key)
        reply = QMessageBox.question(
            self,
            "Confirm village van fee update",
            f"Set van fee for village “{village_key}” to {new_amt:.2f}?\n\n"
            f"This will update {n} student(s) on van transport whose village matches (case-insensitive); "
            f"students on own transport are skipped. Each updated student’s van_fees will be set to this amount, "
            f"transport/van invoice amount_due values will be scaled, and this amount will be stored for the village. "
            f"Tuition invoices will not be changed.\n\n"
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
            self.perform_search(reset_page=True)
            self._load_report_filter_values()
            self._invalidate_payment_student_cache()
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Van fee update failed", str(e))

    def _ensure_payment_students_loaded(self):
        if self._all_payment_students is None:
            self._all_payment_students = self.student_service.list_students()

    def _invalidate_payment_student_cache(self):
        self._all_payment_students = None
        for pid in list(self._payment_panes.keys()):
            self._refresh_payment_pane(pid, reset_page=True)
        self._refresh_details_tab(reset_page=True)

    def _on_details_search_basis_changed(self, _=None) -> None:
        tab = self._student_details_tab
        if tab is None:
            return
        basis = tab.search_by.currentText()
        placeholder_map = {
            "Roll Number": "Enter student roll number",
            "Name": "Enter student name",
            "Phone": "Enter student phone",
            "Village": "Enter village name",
            "Class-Section": "Enter class-section (example: I-A or 10-B)",
            "Status": "Enter student status",
            "Guardian Name": "Enter guardian name",
        }
        tab.student_search.setPlaceholderText(placeholder_map.get(basis, ""))
        self._refresh_details_tab(reset_page=True)

    def _on_details_refresh_clicked(self) -> None:
        tab = self._student_details_tab
        if tab is None:
            return
        tab.student_search.blockSignals(True)
        try:
            tab.student_search.clear()
        finally:
            tab.student_search.blockSignals(False)
        tab.filter_active_only.setChecked(False)
        tab.filter_outstanding_only.setChecked(False)
        self.selected_student = None
        tab.student_results.clear()
        tab.clear_detail()
        self._refresh_details_tab(reset_page=True)

    def _rebuild_details_filtered_ids(self) -> None:
        self._ensure_payment_students_loaded()
        tab = self._student_details_tab
        if tab is None:
            return
        q = (tab.student_search.text() or "").strip().lower()
        criteria = tab.search_by.currentText()
        active_only = tab.filter_active_only.isChecked()
        outstanding_only = tab.filter_outstanding_only.isChecked()

        candidates = [
            s
            for s in self._all_payment_students
            if self._payment_student_matches(s, criteria, q)
            and (not active_only or str(s.status or "").lower() == "active")
        ]
        candidate_ids = [s.id for s in candidates]
        due_map = (
            self.payment_service.get_students_due_breakdown(candidate_ids)
            if candidate_ids
            else {}
        )
        if outstanding_only:
            candidates = [s for s in candidates if float(due_map.get(s.id, {}).get("total", 0) or 0) > 0.01]
        self._details_filtered_ids = [s.id for s in candidates]
        self._details_due_map = due_map

    def _refresh_details_tab(self, reset_page: bool = False) -> None:
        tab = self._student_details_tab
        if tab is None:
            return
        if reset_page:
            self._details_page_index = 0
        self._rebuild_details_filtered_ids()
        self._render_details_list()
        if self.selected_student and self.selected_student.id in self._details_filtered_ids:
            self._show_details_for_student(self.selected_student)
        elif not tab.student_results.currentItem():
            tab.clear_detail()

    def _render_details_list(self) -> None:
        tab = self._student_details_tab
        if tab is None:
            return
        ids = slice_page(self._details_filtered_ids, self._details_page_index)
        self._ensure_payment_students_loaded()
        by_id = {s.id: s for s in self._all_payment_students}
        due_map = getattr(self, "_details_due_map", {})
        current_id = self.selected_student.id if self.selected_student else None
        tab.match_count_label.setText(f"{len(self._details_filtered_ids)} students match")
        tab.student_results.blockSignals(True)
        tab.student_results.clear()
        selected_item = None
        for sid in ids:
            s = by_id.get(sid)
            if not s:
                continue
            due = due_map.get(sid, {})
            total = float(due.get("total", 0) or 0)
            status = str(s.status or "active")
            due_tag = "Paid up" if total <= 0.01 else f"Due ₹{total:.2f}"
            line = (
                f"{s.student_id} - {s.full_name} | Class {s.class_name}-{s.section} | "
                f"{status} | {due_tag}"
            )
            item = QListWidgetItem(line)
            item.setData(Qt.UserRole, s.id)
            if total > 0.01:
                item.setForeground(Qt.GlobalColor.darkRed)
            tab.student_results.addItem(item)
            if current_id and s.id == current_id:
                selected_item = item
        if selected_item:
            tab.student_results.setCurrentItem(selected_item)
        tab.student_results.blockSignals(False)
        self._details_pagination.update_state(self._details_page_index, len(self._details_filtered_ids))

    def _details_change_page(self, delta: int) -> None:
        new_page = self._details_page_index + delta
        if new_page < 0 or new_page >= page_count(len(self._details_filtered_ids)):
            return
        self._details_page_index = new_page
        self._render_details_list()

    def _on_details_student_clicked(self, item: QListWidgetItem) -> None:
        if not item:
            return
        student_id = item.data(Qt.UserRole)
        if not student_id:
            return
        s = self.session.get(Student, int(student_id))
        if not s:
            return
        self.selected_student = s
        self._show_details_for_student(s)

    def _show_details_for_student(self, student: Student) -> None:
        tab = self._student_details_tab
        if tab is None:
            return
        due = self.payment_service.get_student_due_breakdown(student.id)
        yearly = self.payment_service.get_student_yearly_breakdown(student)
        roll = str(student.student_id or "")
        payments = [
            p
            for p in self.payment_service.list_payment_history(limit=5000)
            if str(p.get("student_roll") or "") == roll
        ][:10]
        tab.show_detail(
            {
                "student": student,
                "due": due,
                "yearly": yearly,
                "payments": payments,
            }
        )

    def _on_details_edit_clicked(self, _item=None) -> None:
        if not self.selected_student:
            item = self._student_details_tab.student_results.currentItem() if self._student_details_tab else None
            if item:
                self._on_details_student_clicked(item)
        if self.selected_student:
            self._open_payment_student_editor(self.selected_student, student_fields_editable=True)
            self.session.refresh(self.selected_student)
            self._invalidate_payment_student_cache()
            if self.selected_student:
                self._show_details_for_student(self.selected_student)

    def _on_details_collect_payment_clicked(self) -> None:
        if not self.selected_student:
            item = self._student_details_tab.student_results.currentItem() if self._student_details_tab else None
            if item:
                self._on_details_student_clicked(item)
        if not self.selected_student:
            return
        student = self.selected_student
        self._navigate_to_tab("Collect Payment")
        pane = self._payment_panes.get("payment")
        if pane is None:
            return
        pane.search_by.blockSignals(True)
        pane.student_search.blockSignals(True)
        try:
            idx = pane.search_by.findText("Roll Number", Qt.MatchFixedString)
            if idx >= 0:
                pane.search_by.setCurrentIndex(idx)
            pane.student_search.setText(str(student.student_id or ""))
        finally:
            pane.search_by.blockSignals(False)
            pane.student_search.blockSignals(False)
        self._refresh_payment_pane("payment", reset_page=True)
        for i in range(pane.student_results.count()):
            item = pane.student_results.item(i)
            if item and item.data(Qt.UserRole) == student.id:
                pane.student_results.setCurrentItem(item)
                break

    def _payment_student_matches(self, student, criteria: str, q: str) -> bool:
        if not q:
            return True
        if criteria == "Roll Number":
            return q in str(student.student_id or "").lower()
        if criteria == "Name":
            return q in str(student.full_name or "").lower()
        if criteria == "Phone":
            return q in str(student.phone or "").lower()
        if criteria == "Village":
            return q in str(getattr(student, "village", None) or "").lower()
        if criteria == "Class-Section":
            return q in f"{student.class_name}-{student.section}".lower()
        if criteria == "Status":
            return q in str(student.status or "").lower()
        if criteria == "Guardian Name":
            return q in str(student.guardian_name or "").lower()
        return True

    def _rebuild_payment_filtered_ids(self, pane_id: str) -> None:
        self._ensure_payment_students_loaded()
        pane = self._payment_panes[pane_id]
        q = (pane.student_search.text() or "").strip().lower()
        criteria = pane.search_by.currentText()
        pane.filtered_ids = [
            s.id
            for s in self._all_payment_students
            if self._payment_student_matches(s, criteria, q)
        ]

    def _on_payment_pane_refresh_clicked(self, pane_id: str) -> None:
        """Clear find-student search, reset list to page 1, reload all students."""
        if pane_id not in self._payment_panes:
            return
        pane = self._payment_panes[pane_id]
        pane.student_search.blockSignals(True)
        try:
            pane.student_search.clear()
        finally:
            pane.student_search.blockSignals(False)
        pane.student_results.clear()
        self.selected_student = None
        self._refresh_payment_pane(pane_id, reset_page=True)

    def _refresh_payment_pane(self, pane_id: str, reset_page: bool = False) -> None:
        if pane_id not in self._payment_panes:
            return
        pane = self._payment_panes[pane_id]
        if reset_page:
            pane.page_index = 0
        self._rebuild_payment_filtered_ids(pane_id)
        self._render_payment_pane(pane_id)

    def _render_payment_pane(self, pane_id: str) -> None:
        pane = self._payment_panes[pane_id]
        ids = slice_page(pane.filtered_ids, pane.page_index)
        self._ensure_payment_students_loaded()
        by_id = {s.id: s for s in self._all_payment_students}
        current_student_id = self.selected_student.id if self.selected_student else None
        pane.student_results.blockSignals(True)
        pane.student_results.clear()
        selected_item = None
        for sid in ids:
            s = by_id.get(sid)
            if not s:
                continue
            item = QListWidgetItem(
                f"{s.student_id} - {s.full_name} | Class {s.class_name}-{s.section} | {s.phone}"
            )
            item.setData(Qt.UserRole, s.id)
            pane.student_results.addItem(item)
            if current_student_id and s.id == current_student_id:
                selected_item = item
        if selected_item:
            pane.student_results.setCurrentItem(selected_item)
        pane.student_results.blockSignals(False)
        if pane.pagination is not None:
            pane.pagination.update_state(pane.page_index, len(pane.filtered_ids))

    def _payment_change_page(self, pane_id: str, delta: int) -> None:
        pane = self._payment_panes[pane_id]
        new_page = pane.page_index + delta
        if new_page < 0 or new_page >= page_count(len(pane.filtered_ids)):
            return
        pane.page_index = new_page
        self._render_payment_pane(pane_id)

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
        self._refresh_payment_pane(pane_id, reset_page=True)

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

    def _preview_student_van_fee(self, student, village: str, transport_mode: str) -> float:
        """Tariff shown in the editor; matches update_student fee resolution on save."""
        tm = (transport_mode or "van").strip().lower()
        if tm == "own":
            return 0.0
        old_tm = (getattr(student, "transport_mode", None) or "van").strip().lower()
        if old_tm == "own":
            return float(self.village_van_fee_service.van_fees_for_village_name(village))
        return float(self.village_van_fee_service.van_fees_for_student_update(student, village))

    def _preview_student_school_fee(self, student, class_name: str) -> float:
        return float(self.class_fee_service.school_fees_for_student_update(student, class_name))

    def _open_payment_student_editor(self, student, student_fields_editable: bool = True):
        show_payment_ui = not student_fields_editable
        dialog = QDialog(self)
        dialog.setWindowTitle("Collect Payment" if show_payment_ui else "Student Details")
        dialog.resize(760, 480 if student_fields_editable else 720)
        theme.apply_dialog_theme(dialog)
        layout = QVBoxLayout(dialog)
        heading = QLabel(f"{student.full_name} ({student.student_id})")
        heading.setProperty("role", "page-title")
        if student_fields_editable:
            sub_heading = QLabel("Edit student details below, then click Save.")
        else:
            sub_heading = QLabel("Student information is shown for reference. Enter payment details below.")
        sub_heading.setProperty("role", "muted")
        layout.addWidget(heading)
        layout.addWidget(sub_heading)

        details_box = QGroupBox("Student Information")
        details_layout = QFormLayout(details_box)
        lbl_pk = QLabel(str(student.id))
        lbl_created = QLabel(str(student.created_at or "-"))

        edit_student_id = edit_name = edit_class = edit_section = edit_phone = edit_guardian = None
        edit_village = edit_transport = None
        lbl_school_fees_editable = None
        lbl_van_fees_editable = None
        edit_status = None
        lbl_van_fees = None
        lbl_school_fees = None
        ro_student_id = ro_name = ro_class = ro_section = ro_phone = ro_village = ro_transport = ro_guardian = ro_status = None

        if student_fields_editable:
            edit_student_id = QLineEdit(str(student.student_id or ""))
            edit_name = QLineEdit(str(student.full_name or ""))
            edit_class = QComboBox()
            self._populate_class_combo(edit_class)
            self._select_combo_value(
                edit_class, getattr(student, "class_name", None), canonical=canonical_class_for_student_class
            )
            edit_section = QComboBox()
            self._populate_section_combo(edit_section)
            self._select_combo_value(
                edit_section,
                getattr(student, "section", None),
                canonical=self._canonical_section_for_combo,
            )
            edit_phone = QLineEdit(str(student.phone or ""))
            edit_village = QComboBox()
            self._populate_village_combo(edit_village)
            key = self.village_van_fee_service.resolve_village_key(getattr(student, "village", None))
            raw = (getattr(student, "village", None) or "").strip()
            if key:
                vidx = edit_village.findText(key, Qt.MatchFixedString)
                if vidx >= 0:
                    edit_village.setCurrentIndex(vidx)
            elif raw:
                if edit_village.findText(raw) < 0:
                    edit_village.addItem(raw)
                vidx = edit_village.findText(raw, Qt.MatchFixedString)
                if vidx >= 0:
                    edit_village.setCurrentIndex(vidx)
            edit_transport = QComboBox()
            edit_transport.addItem("Van transport", "van")
            edit_transport.addItem("Own transport", "own")
            tm = (getattr(student, "transport_mode", None) or "van").strip().lower()
            edit_transport.setCurrentIndex(1 if tm == "own" else 0)
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
            details_layout.addRow("Transport", edit_transport)
            details_layout.addRow("Guardian Name", edit_guardian)
            details_layout.addRow("Van Fees (read-only)", lbl_van_fees_editable)
            details_layout.addRow("School Fees (read-only)", lbl_school_fees_editable)
            details_layout.addRow("Status", edit_status)

            def _refresh_editable_fee_preview() -> None:
                village = edit_village.currentText()
                transport = edit_transport.currentData() or "van"
                class_name = edit_class.currentText()
                lbl_van_fees_editable.setText(
                    f"{self._preview_student_van_fee(student, village, transport):.2f}"
                )
                lbl_school_fees_editable.setText(
                    f"{self._preview_student_school_fee(student, class_name):.2f}"
                )

            edit_village.currentIndexChanged.connect(lambda _=None: _refresh_editable_fee_preview())
            edit_transport.currentIndexChanged.connect(lambda _=None: _refresh_editable_fee_preview())
            edit_class.currentIndexChanged.connect(lambda _=None: _refresh_editable_fee_preview())
        else:
            ro_student_id = QLabel(str(student.student_id or "-"))
            ro_name = QLabel(str(student.full_name or "-"))
            ro_class = QLabel(str(student.class_name or "-"))
            ro_section = QLabel(str(student.section or "-"))
            ro_phone = QLabel(str(student.phone or "-"))
            ro_village = QLabel(str(getattr(student, "village", None) or "-"))
            tm_ro = (getattr(student, "transport_mode", None) or "van").strip().lower()
            ro_transport = QLabel("Own transport" if tm_ro == "own" else "Van transport")
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
            details_layout.addRow("Transport", ro_transport)
            details_layout.addRow("Guardian Name", ro_guardian)
            details_layout.addRow("Van Fees", lbl_van_fees)
            details_layout.addRow("School Fees", lbl_school_fees)
            details_layout.addRow("Status", ro_status)
        layout.addWidget(details_box)

        def _format_joining_date(st) -> str:
            created = getattr(st, "created_at", None)
            if created is None:
                return "—"
            if isinstance(created, datetime):
                return created.strftime("%d/%m/%Y")
            return str(created)

        fees_box = QGroupBox("Fee balance (pending + current year)")
        fees_layout = QFormLayout(fees_box)
        due_init = self.payment_service.get_student_due_breakdown(student.id)
        joining_lbl = QLabel(_format_joining_date(student))
        year_lbl = QLabel(due_init.get("current_year_label") or "—")
        school_pending_lbl = QLabel(f"{due_init.get('school_pending', 0):.2f}")
        van_pending_lbl = QLabel(f"{due_init.get('van_pending', 0):.2f}")
        school_current_lbl = QLabel(f"{due_init.get('fee_due', 0):.2f}")
        van_current_lbl = QLabel(f"{due_init.get('van_due', 0):.2f}")
        school_payable_lbl = QLabel(f"{due_init.get('school_payable', due_init.get('fee_due', 0)):.2f}")
        van_payable_lbl = QLabel(f"{due_init.get('van_payable', due_init.get('van_due', 0)):.2f}")
        total_payable_lbl = QLabel(f"{due_init.get('total', 0):.2f}")
        fees_layout.addRow("Student joining date", joining_lbl)
        fees_layout.addRow("Academic year", year_lbl)
        fees_layout.addRow("Pending school fees", school_pending_lbl)
        fees_layout.addRow("Pending van fees", van_pending_lbl)
        fees_layout.addRow("School fees due (current year)", school_current_lbl)
        fees_layout.addRow("Van fees due (current year)", van_current_lbl)
        fees_layout.addRow("Payable school fees", school_payable_lbl)
        fees_layout.addRow("Payable van fees", van_payable_lbl)
        fees_layout.addRow("Total payable amount", total_payable_lbl)
        layout.addWidget(fees_box)

        pay_school_pending_lbl = pay_van_pending_lbl = None
        pay_school_current_lbl = pay_van_current_lbl = None
        popup_school_pay = popup_van_pay = popup_discount = popup_payment_date = popup_mode = None

        def _apply_due_breakdown(d: dict, st=None) -> None:
            school_pending_lbl.setText(f"{d.get('school_pending', 0):.2f}")
            van_pending_lbl.setText(f"{d.get('van_pending', 0):.2f}")
            school_current_lbl.setText(f"{d.get('fee_due', 0):.2f}")
            van_current_lbl.setText(f"{d.get('van_due', 0):.2f}")
            school_payable_lbl.setText(f"{d.get('school_payable', 0):.2f}")
            van_payable_lbl.setText(f"{d.get('van_payable', 0):.2f}")
            total_payable_lbl.setText(f"{d.get('total', 0):.2f}")
            year_lbl.setText(d.get("current_year_label") or "—")
            if st is not None:
                joining_lbl.setText(_format_joining_date(st))
            if pay_school_pending_lbl is not None:
                pay_school_pending_lbl.setText(f"{d.get('school_pending', 0):.2f}")
                pay_van_pending_lbl.setText(f"{d.get('van_pending', 0):.2f}")
                pay_school_current_lbl.setText(f"{d.get('fee_due', 0):.2f}")
                pay_van_current_lbl.setText(f"{d.get('van_due', 0):.2f}")

        if show_payment_ui:
            payment_box = QGroupBox("Payment Details")
            payment_layout = QFormLayout(payment_box)
            pay_school_pending_lbl = QLabel(f"{due_init.get('school_pending', 0):.2f}")
            pay_van_pending_lbl = QLabel(f"{due_init.get('van_pending', 0):.2f}")
            pay_school_current_lbl = QLabel(f"{due_init.get('fee_due', 0):.2f}")
            pay_van_current_lbl = QLabel(f"{due_init.get('van_due', 0):.2f}")
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
            payment_layout.addRow("Pending school fees", pay_school_pending_lbl)
            payment_layout.addRow("Pending van fees", pay_van_pending_lbl)
            payment_layout.addRow("School fees due (current year)", pay_school_current_lbl)
            payment_layout.addRow("Van fees due (current year)", pay_van_current_lbl)
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
            style_primary_button(collect_btn)
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
                if ro_transport is not None:
                    tm2 = (getattr(s, "transport_mode", None) or "van").strip().lower()
                    ro_transport.setText("Own transport" if tm2 == "own" else "Van transport")
                ro_guardian.setText(str(s.guardian_name or "-"))
                ro_status.setText(str(s.status or "-"))
                if lbl_van_fees is not None:
                    lbl_van_fees.setText(f"{float(getattr(s, 'van_fees', 0) or 0):.2f}")
                if lbl_school_fees is not None:
                    lbl_school_fees.setText(f"{float(getattr(s, 'school_fees', 0) or 0):.2f}")
                d = self.payment_service.get_student_due_breakdown(s.id)
                _apply_due_breakdown(d, s)
                lbl_pk.setText(str(s.id))
                lbl_created.setText(str(s.created_at or "-"))

        def on_save():
            try:
                updated = self.student_service.update_student(
                    student,
                    edit_student_id.text(),
                    edit_name.text(),
                    edit_class.currentText(),
                    edit_section.currentText(),
                    edit_phone.text(),
                    edit_village.currentText(),
                    edit_guardian.text(),
                    edit_status.currentText(),
                    transport_mode=edit_transport.currentData() or "van",
                    village_fee_service=self.village_van_fee_service,
                    class_fee_service=self.class_fee_service,
                )
                self.selected_student = updated
                self._invalidate_payment_student_cache()
                self.perform_search(reset_page=True)
                self._load_report_filter_values()
                QMessageBox.information(self, "Student updated", f"Student {updated.full_name} ({updated.student_id}) updated successfully.")
                heading.setText(f"{updated.full_name} ({updated.student_id})")
                lbl_van_fees_editable.setText(f"{float(updated.van_fees):.2f}")
                if lbl_school_fees_editable is not None:
                    lbl_school_fees_editable.setText(f"{float(updated.school_fees):.2f}")
                d = self.payment_service.get_student_due_breakdown(updated.id)
                _apply_due_breakdown(d, updated)
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

        def _finalize_after_payment_saved(pay_date: date | None = None):
            self.session.refresh(student)
            d = self.payment_service.get_student_due_breakdown(student.id)
            _apply_due_breakdown(d, student)
            _refresh_read_only_student_widgets(student)
            popup_school_pay.clear()
            popup_van_pay.clear()
            popup_discount.clear()
            popup_payment_date.setDate(QDate.currentDate())
            self.perform_search(reset_page=False)
            self._invalidate_payment_student_cache()
            self._refresh_payment_history_table(reset_page=False)
            self._refresh_dashboard(chart_date=pay_date)

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
                _finalize_after_payment_saved(pay_date)
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

            default_name = f"Receipt_{student.student_id}_{payment.reference_no}.pdf"
            path, _ = QFileDialog.getSaveFileName(
                dialog, "Save receipt", str(Path.home() / default_name), "PDF (*.pdf)"
            )
            pdf_note = ""
            if path:
                if not str(path).lower().endswith(".pdf"):
                    path = f"{path}.pdf"
                try:
                    from backend.reports.payment_receipt_pdf import render_payment_receipt

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
                    _finalize_after_payment_saved(pay_date)
                    return
            else:
                pdf_note = "\n\nNo PDF was saved (save dialog cancelled)."

            QMessageBox.information(
                dialog,
                "Payment saved",
                f"Reference: {payment.reference_no}{pdf_note}",
            )
            _finalize_after_payment_saved(pay_date)

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

    def _on_search_table_header_clicked(self, logical_index: int) -> None:
        sort_name = next(
            (name for name, col in _SEARCH_SORTABLE_COLUMNS.items() if col == logical_index),
            None,
        )
        if sort_name is None:
            return
        if sort_name == self._search_sort_column:
            self._search_sort_ascending = not self._search_sort_ascending
        else:
            self._search_sort_column = sort_name
            self._search_sort_ascending = True
        self._update_search_sort_indicator()
        self.perform_search(reset_page=True)

    def _update_search_sort_indicator(self) -> None:
        header = self.student_table.horizontalHeader()
        col = _SEARCH_SORTABLE_COLUMNS.get(self._search_sort_column, 1)
        order = Qt.SortOrder.AscendingOrder if self._search_sort_ascending else Qt.SortOrder.DescendingOrder
        header.setSortIndicator(col, order)

    def _search_sort_key(self, student):
        sort_field = self._search_sort_column
        if sort_field == "Student ID":
            return (student.student_id or "").lower()
        if sort_field == "Name":
            return (student.full_name or "").lower()
        if sort_field == "Class":
            return self._class_sort_value(student.class_name)
        if sort_field == "Village":
            return (getattr(student, "village", None) or "").lower()
        return (student.student_id or "").lower()

    def _on_student_search_refresh_clicked(self):
        """Clear search text, reset to page 1, and reload the full student list."""
        if hasattr(self, "search_input"):
            self.search_input.blockSignals(True)
            try:
                self.search_input.clear()
            finally:
                self.search_input.blockSignals(False)
        if hasattr(self, "student_info"):
            self.student_info.setText("Select a student to view details.")
        self.selected_student = None
        self.perform_search(reset_page=True)

    def on_student_search_basis_changed(self, _=None):
        basis = self.search_by.currentText() if hasattr(self, "search_by") else "Name"
        placeholders = {
            "Roll Number": "Enter student roll number",
            "Name": "Enter student name",
            "Village": "Enter village name",
            "Class": "Enter class",
        }
        self.search_input.setPlaceholderText(placeholders.get(basis, "Enter search text"))
        self.perform_search(reset_page=True)

    def _student_matches_search_basis(self, student, basis: str, q: str) -> bool:
        if basis == "Roll Number":
            return q in str(student.student_id or "").lower()
        if basis == "Village":
            return q in str(getattr(student, "village", None) or "").lower()
        if basis == "Class":
            return q in str(student.class_name or "").lower()
        return q in str(student.full_name or "").lower()

    def _collect_filtered_students(self):
        search_text = (self.search_input.text() or "").strip()
        search_basis = self.search_by.currentText() if hasattr(self, "search_by") else "Name"
        if search_text:
            students = self.student_service.list_students()
            q = search_text.lower()
            return [s for s in students if self._student_matches_search_basis(s, search_basis, q)]
        return self.student_service.search_students("")

    def _fee_maps_for_ids(self, student_ids: list[int]) -> dict:
        if not student_ids:
            return {
                "summaries": {},
                "van_summaries": {},
                "due_map": {},
                "discount_map": {},
            }
        return {
            "summaries": self.payment_service.get_students_school_fee_summary(student_ids),
            "van_summaries": self.payment_service.get_students_van_fee_summary(student_ids),
            "due_map": self.payment_service.get_students_due_breakdown(student_ids),
            "discount_map": self.payment_service.get_students_cumulative_payment_discount(student_ids),
        }

    def _rebuild_search_cache(self) -> None:
        students = self._collect_filtered_students()
        students.sort(key=self._search_sort_key, reverse=not self._search_sort_ascending)
        self._search_cache = students
        self._search_fee_maps = {
            "summaries": {},
            "van_summaries": {},
            "due_map": {},
            "discount_map": {},
        }
        self._search_fee_maps_complete = False

    def _render_search_page(self) -> None:
        if self._search_page >= page_count(len(self._search_cache)):
            self._search_page = max(0, page_count(len(self._search_cache)) - 1)
        students = slice_page(self._search_cache, self._search_page)
        if getattr(self, "_search_fee_maps_complete", False):
            summaries = self._search_fee_maps.get("summaries", {})
            van_summaries = self._search_fee_maps.get("van_summaries", {})
            due_map = self._search_fee_maps.get("due_map", {})
            discount_map = self._search_fee_maps.get("discount_map", {})
        else:
            page_maps = self._fee_maps_for_ids([s.id for s in students])
            summaries = page_maps["summaries"]
            van_summaries = page_maps["van_summaries"]
            due_map = page_maps["due_map"]
            discount_map = page_maps["discount_map"]
        self.student_table.setRowCount(len(students))
        for i, s in enumerate(students):
            summary = summaries.get(s.id, {"fee_paid": 0.0, "fee_due": 0.0, "total_fees": 0.0})
            van_s = van_summaries.get(s.id, {"van_paid": 0.0, "van_due": 0.0})
            due = due_map.get(
                s.id,
                {
                    "van_due": 0.0,
                    "fee_due": 0.0,
                    "total": 0.0,
                    "van_pending": 0.0,
                    "van_current": 0.0,
                    "school_pending": 0.0,
                    "school_current": 0.0,
                },
            )
            disc = float(discount_map.get(s.id, 0.0) or 0.0)
            v_text = str(getattr(s, "village", None) or "")
            g_text = str(getattr(s, "guardian_name", None) or "")
            row_cells = [
                str(s.id),
                s.student_id,
                s.full_name,
                str(s.class_name),
                str(s.section),
                s.phone,
                g_text,
                v_text,
                s.status,
                f"{float(getattr(s, 'van_fees', 0) or 0):.2f}",
                f"{van_s['van_paid']:.2f}",
                f"{due.get('van_pending', 0):.2f}",
                f"{due['van_due']:.2f}",
                f"{float(getattr(s, 'school_fees', 0) or 0):.2f}",
                f"{summary['fee_paid']:.2f}",
                f"{disc:.2f}",
                f"{due.get('school_pending', 0):.2f}",
                f"{due['fee_due']:.2f}",
                f"{due.get('school_payable', due.get('school_pending', 0) + due['fee_due']):.2f}",
                f"{due['total']:.2f}",
            ]
            for col, text in enumerate(row_cells):
                self.student_table.setItem(
                    i, col, table_item(text, bold=(col in (1, 2)))
                )
            total_due = float(due.get("total", 0) or 0)
            if total_due > 0.01:
                due_item = self.student_table.item(i, 19)
                if due_item:
                    due_item.setForeground(QColor(theme.current_tokens().danger))
        if hasattr(self, "_search_pagination"):
            self._search_pagination.update_state(self._search_page, len(self._search_cache))

    def _search_change_page(self, delta: int) -> None:
        new_page = self._search_page + delta
        if new_page < 0 or new_page >= page_count(len(self._search_cache)):
            return
        self._search_page = new_page
        self._render_search_page()

    def perform_search(self, reset_page: bool = False):
        if reset_page:
            self._search_page = 0
        self._rebuild_search_cache()
        self._render_search_page()
    def on_student_selected(self,row,_):
        item=self.student_table.item(row,0)
        if not item: return
        s=self.session.get(Student,int(item.text()))
        if not s: return
        self.selected_student = s
        d = self.payment_service.get_student_due_breakdown(s.id)
        self.student_info.setText(
            f"Selected: {s.full_name} ({s.student_id}) — {self._format_fee_due_lines(d)}"
        )
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
                transport_mode=self.add_student_transport.currentData() or "van",
                village_fee_service=self.village_van_fee_service,
                class_fee_service=self.class_fee_service,
            )
            self.add_student_id.clear()
            self.add_student_name.clear()
            self.add_student_class.setCurrentIndex(3)
            self.add_student_section.setCurrentIndex(0)
            self.add_student_phone.clear()
            self.add_student_village.setCurrentIndex(0)
            self.add_student_transport.setCurrentIndex(0)
            self.add_student_guardian.clear()
            self.add_student_status.setCurrentIndex(0)
            self._load_report_filter_values()
            self._invalidate_payment_student_cache()
            self.perform_search(reset_page=True)
            QMessageBox.information(self, "Student added", f"Student {st.full_name} ({st.student_id}) added successfully.")
        except IntegrityError:
            self.session.rollback()
            QMessageBox.warning(self, "Duplicate value", "Student ID or phone already exists. Please use unique values.")
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Add student error", str(e))
    def load_defaulters(self, reset_page: bool = True):
        selected_class = self.report_class.currentData()
        selected_section = self.report_section.currentData()
        self._report_defaulter_rows = self.report_service.get_defaulters(
            student_query=self.report_student_input.text(),
            class_name=selected_class,
            section=selected_section,
        )
        if reset_page:
            self._report_page = 0
        self._render_report_page()

    def _render_report_page(self):
        rows = slice_page(self._report_defaulter_rows, self._report_page)
        self.report_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.report_table.setItem(i, 0, QTableWidgetItem(str(r.student_id)))
            self.report_table.setItem(i, 1, QTableWidgetItem(str(r.full_name)))
            self.report_table.setItem(i, 2, QTableWidgetItem(str(r.class_name)))
            self.report_table.setItem(i, 3, QTableWidgetItem(str(r.section)))
            self.report_table.setItem(i, 4, QTableWidgetItem(f"{float(r.outstanding):.2f}"))
        if hasattr(self, "_report_pagination"):
            self._report_pagination.update_state(self._report_page, len(self._report_defaulter_rows))

    def _report_change_page(self, delta: int):
        new_page = self._report_page + delta
        if new_page < 0 or new_page >= page_count(len(self._report_defaulter_rows)):
            return
        self._report_page = new_page
        self._render_report_page()

    def _rows(self):
        out = []
        for r in self._report_defaulter_rows:
            out.append(
                {
                    "student_id": str(r.student_id),
                    "name": str(r.full_name),
                    "class": str(r.class_name),
                    "section": str(r.section),
                    "outstanding": f"{float(r.outstanding):.2f}",
                }
            )
        return out

    def export_excel(self):
        p, _ = QFileDialog.getSaveFileName(self, "Save Excel", "defaulters.xlsx", "Excel Files (*.xlsx)")
        if not p:
            return
        from backend.reports.excel_export import ExcelExporter

        ExcelExporter.export_rows(self._rows(), Path(p))
        QMessageBox.information(self, "Exported", f"Excel report saved to {p}")

    def export_pdf(self):
        p, _ = QFileDialog.getSaveFileName(self, "Save PDF", "defaulters.pdf", "PDF Files (*.pdf)")
        if not p:
            return
        from backend.reports.pdf_export import PdfExporter

        rows = self._rows()
        table = [[r["student_id"], r["name"], r["class"], r["section"], r["outstanding"]] for r in rows]
        PdfExporter.export_simple_table(
            "Defaulter Report",
            ["Student ID", "Name", "Class", "Section", "Outstanding"],
            table,
            Path(p),
        )
        QMessageBox.information(self, "Exported", f"PDF report saved to {p}")
    def create_backup(self):
        p=self.backup_service.create_backup(); self.backup_status.setText(f"Backup created: {p}")
    def restore_backup(self):
        p,_=QFileDialog.getOpenFileName(self,"Choose backup","","DB Files (*.db *.sqlite *.sqlite3)")
        if not p: return
        self.backup_service.restore_backup(Path(p)); self.backup_status.setText(f"Backup restored from: {p}")
