import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from PySide6.QtCore import QDate, QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QCalendarWidget,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGraphicsOpacityEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QHeaderView,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
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
    class_section_matches_query,
)
from backend.models import Student
from backend.services.academic_year_service import AcademicYearService
from backend.services.backup_service import BackupService
from backend.services.class_fee_service import ClassFeeService
from backend.services.village_van_fee_service import VillageVanFeeService
from backend.services.expense_service import ExpenseService
from backend.services.payment_service import PaymentService
from backend.core.fee_due_display import pending_fees
from backend.core.student_search_match import SEARCH_PLACEHOLDERS, student_matches_search
from backend.core.report_fee_constants import (
    FEE_FILTER_CURRENT_YEAR,
    FEE_FILTER_PAID,
    FEE_FILTER_PENDING_DUE,
    REPORT_FEE_FILTER_LABELS,
    REPORT_FEE_FILTER_ORDER,
    report_amount_column_label,
)
from backend.services.report_service import ReportService
from backend.services.student_service import StudentService
from frontend.ui.academic_year_dialog import AcademicYearDialog
from frontend.ui.add_faculty_page import AddFacultyPage
from frontend.ui.add_student_page import AddStudentPage
from frontend.ui.app_shell import AppShell
from frontend.ui.school_branding import (
    breadcrumb_trail,
    load_logo_pixmap,
    resolve_logo_path,
    school_window_title,
)
from frontend.ui.edudash_widgets import CardTitleBar, GradientProfileCard, SurfaceCard, wrap_page
from frontend.ui.home_page import HomePageTab
from frontend.ui.pagination import PAGE_SIZE, PaginationBar, page_count, slice_page
from frontend.ui.student_details_tab import StudentDetailsTab
from frontend.ui.table_style import (
    apply_button_cell,
    configure_data_table,
    configure_fee_editor_table,
    configure_scrollable_data_table,
    clear_data_table_selection,
    fee_action_button_width,
    fit_table_columns_to_contents,
    refresh_tables_in,
    style_fee_action_button,
    table_item,
)
from frontend.ui import theme
from frontend.ui.phone_input import configure_phone_line_edit, normalize_phone_text, phone_validation_message


_SEARCH_TABLE_HEADERS = [
    "Student ID",
    "Name",
    "Gender",
    "Father Name",
    "Mother Name",
    "Class",
    "Section",
    "Mobile Number 1",
    "Mobile Number 2",
    "Date of Birth",
    "Caste",
    "Aadhaar",
    "Village",
    "Status",
    "Van Fees",
    "Van Paid",
    "Van Due (current)",
    "School Fees",
    "School Paid",
    "Discount",
    "Pending fees",
    "School Due (current)",
    "School Payable (total)",
    "Total Due",
]
# Column index for header-click sorting (Student Search tab).
_SEARCH_SORTABLE_COLUMNS: dict[str, int] = {
    "Student ID": 0,
    "Name": 1,
    "Class": 5,
    "Village": 12,
}


@dataclass
class PaymentLikePane:
    refresh_btn: QPushButton | None
    search_by: QComboBox
    student_search: QLineEdit
    student_results: QListWidget
    hint: QLabel
    count_label: QLabel | None = None
    preview_heading: QLabel | None = None
    preview_outstanding: QLabel | None = None
    profile_card: GradientProfileCard | None = None
    fee_labels: dict[str, QLabel] | None = None
    yearly_table: QTableWidget | None = None
    payments_table: QTableWidget | None = None
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
        self.expense_service = ExpenseService(session)
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
        self._report_fee_status: str | None = None
        self._payment_history_page = 0
        self._payment_history_cache: list = []
        self._salary_assignments_page = 0
        self._salary_assignments_cache: list = []
        self._salary_assignments_page_size = 15
        self._salary_selected_faculty_id: int | None = None
        self._salary_clear_selection_on_next_render = False
        self._salary_control_page = 0
        self._salary_control_cache: list = []
        self._salary_control_page_size = 15
        self._salary_control_selected_faculty_id: int | None = None
        self._salary_history_tab_page = 0
        self._salary_history_tab_cache: list = []
        self._all_payment_students = None
        self._details_page_index = 0
        self._details_filtered_ids: list[str] = []
        self._details_due_map: dict = {}
        self._student_details_tab: StudentDetailsTab | None = None
        self._ui_animations: list[QPropertyAnimation] = []
        self._student_search_timer = QTimer(self)
        self._student_search_timer.setSingleShot(True)
        self._student_search_timer.setInterval(200)
        self._report_search_timer = QTimer(self)
        self._report_search_timer.setSingleShot(True)
        self._report_search_timer.setInterval(200)
        self._report_search_timer.timeout.connect(
            lambda: self.load_defaulters(reset_page=True)
        )
        self._student_search_timer.timeout.connect(
            lambda: self.perform_search(reset_page=True)
        )
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
            "Payment History",
            "Salary",
            "Salary Control",
            "Salary History",
            "Other",
            "Add Faculty",
            "Add Student",
            "Reports",
            "Backup",
            "Fee Control",
        ]
        builders = [
            self._build_home_tab,
            self._build_search_tab,
            self._build_student_details_tab,
            self._build_payment_tab,
            self._build_payment_history_tab,
            self._build_salary_tab,
            self._build_salary_control_tab,
            self._build_salary_history_tab,
            self._build_other_expense_tab,
            self._build_add_faculty_tab,
            self._build_add_student_tab,
            self._build_reports_tab,
            self._build_backup_tab,
            self._build_fee_control_tab,
        ]
        for key, builder in zip(self._tab_names, builders):
            idx = self._shell.register_page(key, builder())
            if key == "Home Page":
                self._home_tab_index = idx
            if key == "Fee Control":
                self._fee_control_tab_index = idx
            if key == "Payment History":
                self._payment_history_tab_index = idx
            if key == "Salary":
                self._salary_tab_index = idx
            if key == "Salary Control":
                self._salary_control_tab_index = idx
            if key == "Salary History":
                self._salary_history_tab_index = idx
            if key == "Other":
                self._other_expense_tab_index = idx
            if key == "Add Faculty":
                self._add_faculty_tab_index = idx
        self._shell.page_changed.connect(self._on_main_tab_changed)
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
        add_faculty_page = getattr(self, "_add_faculty_page", None)
        if add_faculty_page is not None:
            add_faculty_page.refresh_theme()
        details = getattr(self, "_student_details_tab", None)
        if details is not None:
            details.refresh_theme()
        add_village = getattr(self, "_add_village_btn", None)
        if add_village is not None:
            style_fee_action_button(add_village)
        for pagination in self._all_pagination_bars():
            pagination.refresh_theme()
        for btn in (
            getattr(self, "_load_defaulters_btn", None),
            getattr(self, "_export_excel_btn", None),
            getattr(self, "_export_pdf_btn", None),
            getattr(self, "_create_backup_btn", None),
            getattr(self, "_restore_backup_btn", None),
            getattr(self, "_manage_years_btn", None),
            getattr(self, "_salary_refresh_btn", None),
            getattr(self, "_salary_open_window_btn", None),
            getattr(self, "_salary_control_refresh_btn", None),
            getattr(self, "_salary_control_edit_salary_btn", None),
            getattr(self, "_salary_control_edit_profile_btn", None),
            getattr(self, "_add_faculty_submit_btn", None),
            getattr(self, "_other_add_btn", None),
        ):
            if btn is not None:
                style_fee_action_button(btn, width=btn.width() if btn.width() > 0 else None)
        self._refresh_salary_list_style()
        for pane_id in self._payment_panes:
            self._refresh_payment_pane_visuals(pane_id)
        for btn in self.findChildren(QPushButton):
            variant = btn.property("variant")
            if variant in ("primary", "teal-outline", "icon"):
                theme.polish(btn, str(variant))

    def _animate_widget_fade(self, widget: QWidget | None, *, start: float = 0.82, duration: int = 180) -> None:
        if widget is None:
            return
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        effect.setOpacity(start)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(duration)
        anim.setStartValue(start)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _cleanup(a=anim) -> None:
            if a in self._ui_animations:
                self._ui_animations.remove(a)

        anim.finished.connect(_cleanup)
        self._ui_animations.append(anim)
        anim.start()

    @staticmethod
    def _stretch_table_columns(table: QTableWidget | None) -> None:
        if table is None:
            return
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        for col in range(table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)

    def _refresh_payment_pane_visuals(self, pane_id: str) -> None:
        pane = self._payment_panes.get(pane_id)
        if pane is None:
            return
        t = theme.current_tokens()
        if pane.refresh_btn is not None:
            style_fee_action_button(
                pane.refresh_btn,
                width=fee_action_button_width(pane.refresh_btn, min_width=88),
            )
        pane.student_results.setSpacing(4)
        pane.student_results.setStyleSheet(
            f"""
            QListWidget {{
                background: {t.bg_surface};
                color: {t.text_primary};
                border: 1px solid {t.border};
                border-radius: 12px;
                padding: 6px;
                outline: none;
            }}
            QListWidget::item {{
                color: {t.text_primary};
                border: 1px solid transparent;
                border-radius: 8px;
                margin: 2px;
                padding: 10px 12px;
            }}
            QListWidget::item:hover {{
                background: {t.bg_hover};
                border-color: {t.border_light};
            }}
            QListWidget::item:selected {{
                background: {t.primary_soft};
                border-color: {t.primary_light};
                color: {t.text_primary};
            }}
            """
        )
        if pane.count_label is not None:
            pane.count_label.setStyleSheet(
                f"color: {t.text_secondary}; font-size: 12px; font-weight: 600; background: transparent;"
            )
        if pane.preview_heading is not None:
            pane.preview_heading.setStyleSheet(
                f"color: {t.text_primary}; font-size: 30px; font-weight: 700; background: transparent;"
            )
        if pane.preview_outstanding is not None:
            pane.preview_outstanding.setStyleSheet(
                f"color: {t.text_secondary}; font-size: 13px; font-weight: 600; background: transparent;"
            )
        if pane.yearly_table is not None:
            configure_data_table(pane.yearly_table)
            self._stretch_table_columns(pane.yearly_table)
        if pane.payments_table is not None:
            configure_data_table(pane.payments_table)
            self._stretch_table_columns(pane.payments_table)
        for bar in self.findChildren(CardTitleBar):
            bar.refresh_theme()

    def _style_payment_preview_total(self, pane: PaymentLikePane, total_due: float) -> None:
        labels = pane.fee_labels or {}
        total_lbl = labels.get("total")
        if total_lbl is None:
            return
        t = theme.current_tokens()
        if total_due > 0.01:
            total_lbl.setStyleSheet(
                f"color: {t.danger}; font-weight: 700; background: transparent;"
            )
        else:
            total_lbl.setStyleSheet(
                f"color: {t.success}; font-weight: 700; background: transparent;"
            )

    def _set_payment_preview_idle(self, pane: PaymentLikePane) -> None:
        if pane.preview_heading is not None:
            pane.preview_heading.setText("No student selected")
        if pane.preview_outstanding is not None:
            pane.preview_outstanding.setText("Outstanding total: ₹0.00")
            pane.preview_outstanding.setStyleSheet(
                f"color: {theme.current_tokens().text_secondary}; font-size: 13px; font-weight: 600; background: transparent;"
            )
        if pane.profile_card is not None:
            pane.profile_card.set_student("No student selected", "—", "—")
        labels = pane.fee_labels or {}
        for key in (
            "academic_year",
            "pending_fees",
            "school_due",
            "van_due",
            "school_payable",
            "van_payable",
            "total",
        ):
            lbl = labels.get(key)
            if lbl is not None:
                lbl.setText("—")
        self._style_payment_preview_total(pane, 0.0)
        if pane.yearly_table is not None:
            pane.yearly_table.setRowCount(0)
        if pane.payments_table is not None:
            pane.payments_table.setRowCount(0)

    def _set_payment_preview_student(self, pane: PaymentLikePane, student: Student, due: dict | None = None) -> None:
        d = due or self.payment_service.get_student_due_breakdown(student.student_id)
        total_due = float(d.get("total", 0) or 0)
        class_name = str(getattr(student, "class_name", None) or "—")
        section = str(getattr(student, "section", None) or "").strip()
        class_section = f"{class_name}-{section}" if section else class_name

        if pane.preview_heading is not None:
            pane.preview_heading.setText(str(getattr(student, "full_name", None) or "Student"))
        if pane.preview_outstanding is not None:
            pane.preview_outstanding.setText(f"Outstanding total: ₹{total_due:.2f}")
            t = theme.current_tokens()
            if total_due > 0.01:
                pane.preview_outstanding.setStyleSheet(
                    f"color: {t.danger}; font-size: 13px; font-weight: 700; background: transparent;"
                )
            else:
                pane.preview_outstanding.setStyleSheet(
                    f"color: {t.success}; font-size: 13px; font-weight: 700; background: transparent;"
                )
        if pane.profile_card is not None:
            pane.profile_card.set_student(
                str(getattr(student, "full_name", None) or "—"),
                class_section,
                str(getattr(student, "student_id", None) or "—"),
            )

        labels = pane.fee_labels or {}
        mappings = {
            "academic_year": str(d.get("current_year_label") or "—"),
            "pending_fees": f"{pending_fees(d):.2f}",
            "school_due": f"{float(d.get('fee_due', 0) or 0):.2f}",
            "van_due": f"{float(d.get('van_due', 0) or 0):.2f}",
            "school_payable": f"{float(d.get('school_payable', 0) or 0):.2f}",
            "van_payable": f"{float(d.get('van_payable', 0) or 0):.2f}",
            "total": f"{total_due:.2f}",
        }
        for key, value in mappings.items():
            lbl = labels.get(key)
            if lbl is not None:
                lbl.setText(value)
        self._style_payment_preview_total(pane, total_due)

        if pane.yearly_table is not None:
            pane.yearly_table.setRowCount(0)
            yearly = self.payment_service.get_student_yearly_breakdown(student)
            for row, yr in enumerate(yearly or []):
                pane.yearly_table.insertRow(row)
                label = yr.get("label") or ""
                if yr.get("is_current"):
                    label = f"{label} (current)"
                cells = [
                    label,
                    f"{float(yr.get('school_tariff', 0) or 0):.2f}",
                    f"{float(yr.get('school_paid', 0) or 0):.2f}",
                    f"{float(yr.get('school_due', 0) or 0):.2f}",
                    f"{float(yr.get('van_tariff', 0) or 0):.2f}",
                    f"{float(yr.get('van_paid', 0) or 0):.2f}",
                    f"{float(yr.get('van_due', 0) or 0):.2f}",
                ]
                for col, text in enumerate(cells):
                    item = table_item(text)
                    if col in (3, 6) and float(text) > 0.01:
                        item.setForeground(QColor(theme.current_tokens().danger))
                    pane.yearly_table.setItem(row, col, item)
            self._stretch_table_columns(pane.yearly_table)
        if pane.payments_table is not None:
            pane.payments_table.setRowCount(0)
            roll = str(getattr(student, "student_id", None) or "")
            payments = [
                p
                for p in self.payment_service.list_payment_history(limit=5000)
                if str(p.get("student_roll") or "") == roll
            ][:14]
            for row, p in enumerate(payments):
                pane.payments_table.insertRow(row)
                pd = p.get("payment_date")
                pd_str = pd.strftime("%d/%m/%Y") if hasattr(pd, "strftime") else str(pd or "")
                values = [
                    pd_str,
                    str(p.get("reference_no") or ""),
                    f"{float(p.get('amount', 0) or 0):.2f}",
                    f"{float(p.get('discount', 0) or 0):.2f}",
                    str(p.get("mode") or ""),
                ]
                for col, text in enumerate(values):
                    pane.payments_table.setItem(row, col, table_item(text))
            self._stretch_table_columns(pane.payments_table)
        self._animate_widget_fade(pane.profile_card, start=0.86, duration=180)

    def _all_pagination_bars(self) -> list[PaginationBar]:
        bars: list[PaginationBar] = []
        for attr in (
            "_search_pagination",
            "_details_pagination",
            "_payment_history_pagination",
            "_salary_assignments_pagination",
        ):
            bar = getattr(self, attr, None)
            if bar is not None:
                bars.append(bar)
        for pane in self._payment_panes.values():
            if pane.pagination is not None and pane.pagination.green_style:
                bars.append(pane.pagination)
        return bars

    def _schedule_student_search(self) -> None:
        self._student_search_timer.start()

    def _run_student_search_now(self, *, reset_page: bool = True) -> None:
        self._student_search_timer.stop()
        self.perform_search(reset_page=reset_page)

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
                "reverted_amounts": daily_revenue.get("reverted_amounts", []),
                "month_label": daily_revenue["month_label"],
            },
            "recent_payments": recent,
        }

    def _build_search_tab(self):
        body = QWidget()
        body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.setMinimumHeight(0)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        search_refresh_btn = QPushButton("Refresh")
        search_refresh_btn.clicked.connect(self._on_student_search_refresh_clicked)
        toolbar.addWidget(search_refresh_btn)
        toolbar.addWidget(QLabel("Search by"))
        self.search_by = QComboBox()
        self.search_by.addItems(
            [
                "Roll Number",
                "Name",
                "Gender",
                "Father Name",
                "Mother Name",
                "Mobile Number 1",
                "Mobile Number 2",
                "Aadhaar",
                "Village",
                "Class",
                "Caste",
            ]
        )
        self.search_by.setCurrentIndex(1)
        self.search_by.currentIndexChanged.connect(self.on_student_search_basis_changed)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter students…")
        self.search_input.textChanged.connect(lambda _: self._schedule_student_search())
        toolbar.addWidget(self.search_by)
        toolbar.addWidget(self.search_input, 1)
        layout.addLayout(toolbar)

        table_card = SurfaceCard()
        table_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table_card.setMinimumHeight(0)
        self.student_table = QTableWidget(0, len(_SEARCH_TABLE_HEADERS))
        self.student_table.setHorizontalHeaderLabels(list(_SEARCH_TABLE_HEADERS))
        configure_scrollable_data_table(self.student_table)
        self.student_table.setProperty("table_variant", "scrollable")
        self.student_table.cellClicked.connect(self.on_student_selected)
        search_header = self.student_table.horizontalHeader()
        search_header.setSectionsClickable(True)
        search_header.setSortIndicatorShown(True)
        search_header.sectionClicked.connect(self._on_search_table_header_clicked)
        self._update_search_sort_indicator()
        table_card.body.addWidget(self.student_table, 1)
        layout.addWidget(table_card, 1)

        footer = QWidget()
        footer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        footer_lay = QVBoxLayout(footer)
        footer_lay.setContentsMargins(0, 4, 0, 0)
        footer_lay.setSpacing(8)
        self.student_info = QLabel("Select a student to view fee summary.")
        self.student_info.setProperty("role", "muted")
        self.student_info.setWordWrap(True)
        footer_lay.addWidget(self.student_info)
        self._search_pagination = PaginationBar(
            lambda: self._search_change_page(-1),
            lambda: self._search_change_page(1),
            green_style=True,
        )
        footer_lay.addWidget(self._search_pagination)
        layout.addWidget(footer)
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
            green_style=True,
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
        root = QHBoxLayout(w)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        left_host = QWidget()
        left_lay = QVBoxLayout(left_host)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(12)

        list_card = SurfaceCard()
        list_title = QLabel("Find student")
        list_title.setProperty("role", "section-title")
        list_hint = QLabel("Search students and double-click any row to open payment collection.")
        list_hint.setProperty("role", "muted")
        list_hint.setWordWrap(True)
        list_card.body.addWidget(list_title)
        list_card.body.addWidget(list_hint)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        refresh_btn = QPushButton("Refresh")
        style_fee_action_button(refresh_btn, width=fee_action_button_width(refresh_btn, min_width=88))
        refresh_btn.clicked.connect(lambda _=False, p=pane_id: self._on_payment_pane_refresh_clicked(p))
        toolbar.addWidget(refresh_btn)
        toolbar.addWidget(QLabel("Search by"))
        search_by = QComboBox()
        search_by.addItems(
            [
                "Roll Number",
                "Name",
                "Mobile Number 1",
                "Mobile Number 2",
                "Village",
                "Class-Section",
                "Status",
                "Father Name",
                "Mother Name",
                "Aadhaar",
            ]
        )
        search_by.setCurrentIndex(1)
        search_by.currentIndexChanged.connect(lambda _=None, p=pane_id: self._on_payment_search_basis_changed(p))
        student_search = QLineEdit()
        student_search.setClearButtonEnabled(True)
        student_search.textChanged.connect(
            lambda t, p=pane_id: self._refresh_payment_pane(p, reset_page=True)
        )
        toolbar.addWidget(search_by)
        toolbar.addWidget(student_search, 1)
        list_card.body.addLayout(toolbar)

        count_label = QLabel("0 students found")
        count_label.setProperty("role", "muted")
        list_card.body.addWidget(count_label)

        student_results = QListWidget()
        student_results.itemClicked.connect(lambda item, p=pane_id: self._on_payment_student_selected(p, item))
        student_results.itemDoubleClicked.connect(
            lambda item, p=pane_id: self._on_payment_student_double_clicked(p, item)
        )
        hint = QLabel("Tip: the selected student summary appears on the right.")
        hint.setProperty("role", "hint")
        list_card.body.addWidget(student_results, 1)
        list_card.body.addWidget(hint)
        left_lay.addWidget(list_card, 1)

        pagination = PaginationBar(
            lambda _checked=False, p=pane_id: self._payment_change_page(p, -1),
            lambda _checked=False, p=pane_id: self._payment_change_page(p, 1),
            green_style=True,
        )
        left_lay.addWidget(pagination)
        root.addWidget(left_host, 5)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        right_host = QWidget()
        right_lay = QVBoxLayout(right_host)
        right_lay.setContentsMargins(0, 0, 0, 4)
        right_lay.setSpacing(14)

        preview_heading = QLabel("No student selected")
        preview_heading.setProperty("role", "section-title")
        preview_outstanding = QLabel("Outstanding total: ₹0.00")
        preview_outstanding.setProperty("role", "muted")
        right_lay.addWidget(preview_heading)
        right_lay.addWidget(preview_outstanding)

        profile_card = GradientProfileCard("—", "—", "—", show_action=False)
        profile_card.setMinimumHeight(260)
        right_lay.addWidget(profile_card)

        fees_card = SurfaceCard()
        fees_card.body.addWidget(CardTitleBar("Fee snapshot"))
        fees_form = QFormLayout()
        fees_form.setHorizontalSpacing(16)
        fees_form.setVerticalSpacing(8)
        fee_labels = {
            "academic_year": QLabel("—"),
            "pending_fees": QLabel("—"),
            "school_due": QLabel("—"),
            "van_due": QLabel("—"),
            "school_payable": QLabel("—"),
            "van_payable": QLabel("—"),
            "total": QLabel("—"),
        }
        fees_form.addRow("Academic year", fee_labels["academic_year"])
        fees_form.addRow("Pending fees", fee_labels["pending_fees"])
        fees_form.addRow("School due (year)", fee_labels["school_due"])
        fees_form.addRow("Van due (year)", fee_labels["van_due"])
        fees_form.addRow("Payable school", fee_labels["school_payable"])
        fees_form.addRow("Payable van", fee_labels["van_payable"])
        fees_form.addRow("Total payable", fee_labels["total"])
        fees_card.body.addLayout(fees_form)
        right_lay.addWidget(fees_card)

        year_card = SurfaceCard()
        year_card.body.addWidget(CardTitleBar("Fees by academic year"))
        yearly_table = QTableWidget(0, 7)
        yearly_table.setHorizontalHeaderLabels(
            ["Year", "School tariff", "School paid", "School due", "Van tariff", "Van paid", "Van due"]
        )
        yearly_table.setMinimumHeight(220)
        configure_data_table(yearly_table)
        year_card.body.addWidget(yearly_table)
        right_lay.addWidget(year_card)

        pay_card = SurfaceCard()
        pay_card.body.addWidget(CardTitleBar("Recent payments"))
        payments_table = QTableWidget(0, 5)
        payments_table.setHorizontalHeaderLabels(
            ["Date", "Reference", "Amount (₹)", "Discount (₹)", "Mode"]
        )
        payments_table.setMinimumHeight(280)
        configure_data_table(payments_table)
        pay_card.body.addWidget(payments_table)
        right_lay.addWidget(pay_card)

        right_scroll.setWidget(right_host)
        root.addWidget(right_scroll, 6)

        self._payment_panes[pane_id] = PaymentLikePane(
            refresh_btn=refresh_btn,
            search_by=search_by,
            student_search=student_search,
            student_results=student_results,
            hint=hint,
            count_label=count_label,
            preview_heading=preview_heading,
            preview_outstanding=preview_outstanding,
            profile_card=profile_card,
            fee_labels=fee_labels,
            yearly_table=yearly_table,
            payments_table=payments_table,
            pagination=pagination,
        )
        student_search.setPlaceholderText("Enter student name")
        self._refresh_payment_pane_visuals(pane_id)
        self._set_payment_preview_idle(self._payment_panes[pane_id])
        return w
    def _build_add_faculty_tab(self):
        page = AddFacultyPage(parent=self)
        self._add_faculty_page = page
        self.add_faculty_name = page.faculty_name
        self.add_faculty_type = page.faculty_type
        self.add_faculty_role = page.role
        self.add_faculty_monthly_salary = page.monthly_salary
        self.add_faculty_default_working_days = page.default_working_days
        self.add_faculty_status = page.status
        self._add_faculty_submit_btn = page.submit_btn
        page.submit_btn.clicked.connect(self.add_faculty)
        return page

    def _build_add_student_tab(self):
        page = AddStudentPage(self._populate_village_combo, parent=self)
        self._add_student_page = page
        self.add_student_id = page.student_id
        self.add_student_name = page.full_name
        self.add_student_gender = page.gender
        self.add_student_father_name = page.father_name
        self.add_student_mother_name = page.mother_name
        self.add_student_class = page.student_class
        self.add_student_section = page.section
        self.add_student_mobile_number_1 = page.mobile_number_1
        self.add_student_mobile_number_2 = page.mobile_number_2
        self.add_student_date_of_birth = page.date_of_birth
        self.add_student_caste = page.caste
        self.add_student_aadhaar = page.aadhaar
        self.add_student_village = page.village
        self.add_student_transport = page.transport
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
    def _gender_display(value: str | None) -> str:
        text = (value or "").strip()
        lower = text.lower()
        if lower in ("male", "boy"):
            return "Male"
        if lower in ("female", "girl"):
            return "Female"
        return text.title() if text else ""

    @staticmethod
    def _gender_for_combo(value: str | None) -> str:
        shown = MainWindow._gender_display(value)
        return shown if shown in ("Male", "Female", "Other") else "Male"

    @staticmethod
    def _default_working_days_for_month(year: int, month: int) -> int:
        days_in_month = calendar.monthrange(year, month)[1]
        sunday_count = sum(
            1
            for day_num in range(1, days_in_month + 1)
            if date(year, month, day_num).weekday() == 6
        )
        return max(1, days_in_month - sunday_count)

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

    def _refresh_salary_list_style(self) -> None:
        t = theme.current_tokens()
        list_widget = getattr(self, "_salary_faculty_list", None)
        if list_widget is not None:
            list_widget.setStyleSheet(
                f"""
                QListWidget {{
                    background: {t.bg_surface};
                    color: {t.text_primary};
                    border: 1px solid {t.border};
                    border-radius: 12px;
                    padding: 6px;
                    outline: none;
                }}
                QListWidget::item {{
                    color: {t.text_primary};
                    border: 1px solid transparent;
                    border-radius: 8px;
                    margin: 2px;
                    padding: 10px 12px;
                }}
                QListWidget::item:hover {{
                    background: {t.bg_hover};
                    border-color: {t.border_light};
                }}
                QListWidget::item:selected {{
                    background: {t.primary_soft};
                    border-color: {t.primary_light};
                    color: {t.text_primary};
                }}
                """
            )
        for card in self.findChildren(QWidget):
            if card.objectName() == "salaryStatCard":
                card.setStyleSheet(
                    f"QWidget#salaryStatCard {{ background: {t.bg_surface}; border: 1px solid {t.border}; border-radius: 12px; }}"
                )

    def _create_salary_stat_card(self, title: str) -> tuple[QWidget, QLabel]:
        card = QWidget()
        card.setObjectName("salaryStatCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)
        title_lbl = QLabel(title)
        title_lbl.setProperty("role", "muted")
        value_lbl = QLabel("—")
        value_lbl.setProperty("role", "section-title")
        lay.addWidget(title_lbl)
        lay.addWidget(value_lbl)
        t = theme.current_tokens()
        card.setStyleSheet(
            f"QWidget#salaryStatCard {{ background: {t.bg_surface}; border: 1px solid {t.border}; border-radius: 12px; }}"
        )
        return card, value_lbl

    def _style_salary_status_badge(self, status_text: str) -> None:
        badge = getattr(self, "_salary_lbl_status", None)
        if badge is None:
            return
        t = theme.current_tokens()
        status_value = (status_text or "").strip().lower()
        if status_value == "active":
            bg = t.primary_soft
            fg = t.success
        elif status_value == "inactive":
            bg = t.bg_section_header
            fg = t.text_secondary
        else:
            bg = t.bg_section_header
            fg = t.text_primary
        badge.setText(status_text or "—")
        badge.setStyleSheet(
            f"background: {bg}; color: {fg}; padding: 4px 10px; border-radius: 10px; font-weight: 700;"
        )

    def _clear_salary_detail_panel(self) -> None:
        if hasattr(self, "_salary_profile_card"):
            self._salary_profile_card.set_student("No faculty selected", "—", "—")
        if hasattr(self, "_salary_detail_heading"):
            self._salary_detail_heading.setText("No faculty selected")
        if hasattr(self, "_salary_detail_hint"):
            self._salary_detail_hint.setText("Select a faculty member from the left panel to view details.")
        for attr in (
            "_salary_lbl_name",
            "_salary_lbl_type",
            "_salary_lbl_role",
            "_salary_lbl_monthly",
            "_salary_lbl_working",
            "_salary_lbl_created",
            "_salary_attendance_month_value",
            "_salary_attendance_checked_value",
            "_salary_attendance_sunday_value",
            "_salary_attendance_total_value",
            "_salary_attendance_working_value",
            "_salary_stat_total_paid",
            "_salary_stat_entries",
            "_salary_stat_last_paid",
            "_salary_stat_month",
        ):
            lbl = getattr(self, attr, None)
            if lbl is not None:
                lbl.setText("—")
        self._style_salary_status_badge("—")
        if hasattr(self, "_salary_total_label"):
            self._salary_total_label.setText("Total paid: ₹0.00")
        table = getattr(self, "_salary_history_table", None)
        if table is not None:
            table.setRowCount(0)
        open_btn = getattr(self, "_salary_open_window_btn", None)
        if open_btn is not None:
            open_btn.setEnabled(False)

    def _build_reports_tab(self):
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        toolbar = QHBoxLayout()
        self.report_search_by = QComboBox()
        self.report_search_by.addItems(["Roll Number", "Name", "Village"])
        self.report_search_by.setCurrentIndex(1)
        self.report_search_by.currentIndexChanged.connect(self._on_report_search_basis_changed)
        self.report_student_input = QLineEdit()
        self.report_student_input.setPlaceholderText("Enter student name")
        self.report_student_input.textChanged.connect(lambda _: self._schedule_report_search())
        self.report_class = QComboBox()
        self.report_class.addItem("All Classes", None)
        self.report_section = QComboBox()
        self.report_section.addItem("All Sections", None)
        self.report_fee_filter = QComboBox()
        self.report_fee_filter.addItem("All students", None)
        for key in REPORT_FEE_FILTER_ORDER:
            self.report_fee_filter.addItem(REPORT_FEE_FILTER_LABELS[key], key)
        self._load_report_filter_values()
        report_refresh_btn = QPushButton("Refresh")
        style_fee_action_button(report_refresh_btn)
        report_refresh_btn.clicked.connect(self._on_report_refresh_clicked)
        a = QPushButton("Load report")
        style_fee_action_button(a)
        a.clicked.connect(lambda: self.load_defaulters(reset_page=True))
        b = QPushButton("Export Excel")
        style_fee_action_button(b)
        b.clicked.connect(self.export_excel)
        c = QPushButton("Export PDF")
        style_fee_action_button(c)
        c.clicked.connect(self.export_pdf)
        self._load_defaulters_btn = a
        self._export_excel_btn = b
        self._export_pdf_btn = c
        self._report_refresh_btn = report_refresh_btn
        toolbar.addWidget(report_refresh_btn)
        toolbar.addWidget(QLabel("Search by"))
        toolbar.addWidget(self.report_search_by)
        toolbar.addWidget(self.report_student_input, 1)
        toolbar.addWidget(self.report_class)
        toolbar.addWidget(self.report_section)
        toolbar.addWidget(self.report_fee_filter)
        toolbar.addWidget(a)
        toolbar.addWidget(b)
        toolbar.addWidget(c)
        layout.addLayout(toolbar)
        card = SurfaceCard()
        self.report_table = QTableWidget(0, 5)
        self.report_table.setHorizontalHeaderLabels(
            ["Student ID", "Name", "Class", "Section", "Total due"]
        )
        configure_scrollable_data_table(self.report_table)
        self.report_table.setProperty("table_variant", "scrollable")
        card.body.addWidget(self.report_table, 1)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card.setMinimumHeight(0)
        layout.addWidget(card, 1)
        self._report_pagination = PaginationBar(
            lambda: self._report_change_page(-1),
            lambda: self._report_change_page(1),
        )
        layout.addWidget(self._report_pagination)
        return wrap_page("Reports", breadcrumb_trail("Reports"), body)
    def _load_report_filter_values(self):
        values = self.report_service.get_report_filter_values()
        self.report_class.blockSignals(True)
        self.report_section.blockSignals(True)
        try:
            self.report_class.clear()
            self.report_class.addItem("All Classes", None)
            self.report_section.clear()
            self.report_section.addItem("All Sections", None)
            for c in values.get("classes", []):
                self.report_class.addItem(str(c), str(c))
            for s in values.get("sections", []):
                self.report_section.addItem(str(s), str(s))
        finally:
            self.report_class.blockSignals(False)
            self.report_section.blockSignals(False)

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
        style_fee_action_button(a)
        a.clicked.connect(self.create_backup)
        b = QPushButton("Restore backup")
        style_fee_action_button(b)
        b.clicked.connect(self.restore_backup)
        self._create_backup_btn = a
        self._restore_backup_btn = b
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
        style_fee_action_button(manage_years_btn)
        self._manage_years_btn = manage_years_btn
        manage_years_btn.setToolTip(
            "Add or edit academic year date ranges (DD/MM/YYYY). "
            "Adding a new forward year promotes active students one class (Class 10→Passed Out). "
            "Inactive students are skipped; old pending fees remain."
        )
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
            f"Pending fees: {pending_fees(due):.2f} | "
            f"School due (current): {due.get('fee_due', 0):.2f} | "
            f"Van due (current): {due.get('van_due', 0):.2f} | "
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
            theme.message_warning(self, "Invalid amount", "Enter a valid number for the van fee.")
            return
        try:
            stored = self.village_van_fee_service.register_new_village(name_edit.text(), fee)
        except Exception as e:
            theme.message_critical(self, "Add village failed", str(e))
            return
        self._rebuild_van_fee_control_table()
        self._populate_village_combo(self.add_student_village)
        theme.message_information(
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
        if index == getattr(self, "_add_faculty_tab_index", -1):
            page = getattr(self, "_add_faculty_page", None)
            if page is not None:
                has_user_input = any(
                    [
                        bool((page.faculty_name.text() or "").strip()),
                        bool((page.role.text() or "").strip()),
                        bool((page.monthly_salary.text() or "").strip()),
                    ]
                )
                if not has_user_input:
                    page.sync_default_working_days_current_month()
        if index == getattr(self, "_fee_control_tab_index", -1):
            self._refresh_fee_control_amounts()
            self._refresh_van_fee_control_amounts()
        if index == getattr(self, "_payment_history_tab_index", -1):
            self._refresh_payment_history_table(reset_page=False)
            if hasattr(self, "_payment_history_pagination"):
                self._payment_history_pagination.refresh_theme()
        if index == getattr(self, "_salary_tab_index", -1):
            self._refresh_salary_faculty_options()
            self._refresh_salary_assignments_table()
            self._refresh_salary_history_table()
        if index == getattr(self, "_salary_control_tab_index", -1):
            self._refresh_salary_control_assignments_table(reset_page=False)
            self._refresh_salary_control_history_table()
        if index == getattr(self, "_salary_history_tab_index", -1):
            self._refresh_salary_history_tab_table(reset_page=False)
            if hasattr(self, "_salary_history_tab_pagination"):
                self._salary_history_tab_pagination.refresh_theme()
        if index == getattr(self, "_other_expense_tab_index", -1):
            self._refresh_other_expense_table()
        if tab_name == "Student Details":
            self._refresh_details_tab(reset_page=False)
        if tab_name == "Collect Payment":
            self._ensure_payment_students_loaded()
            self._refresh_payment_pane("payment", reset_page=False)

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
        self._payment_history_table = QTableWidget(0, 11)
        self._payment_history_table.setHorizontalHeaderLabels(
            [
                "Date",
                "Reference",
                "Student ID",
                "Name",
                "Total (₹)",
                "Discount (₹)",
                "Mode",
                "Operator",
                "Status",
                "Print Receipt",
                "Undo Payment",
            ]
        )
        configure_scrollable_data_table(self._payment_history_table)
        self._payment_history_table.setProperty("table_variant", "scrollable")
        card.body.addWidget(self._payment_history_table, 1)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card.setMinimumHeight(0)
        layout.addWidget(card, 1)
        self._payment_history_pagination = PaginationBar(
            lambda: self._payment_history_change_page(-1),
            lambda: self._payment_history_change_page(1),
            green_style=True,
        )
        self._payment_history_pagination.refresh_theme()
        layout.addWidget(self._payment_history_pagination)
        return wrap_page(
            "Payment History",
            breadcrumb_trail("Fees Collection", "Payment History"),
            body,
        )

    def _build_salary_history_tab(self):
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(
            "Recorded faculty salary payouts (newest first). Filter by reference, faculty name, "
            "month, role, or notes. Undo removes the payout from salary totals while keeping the row in history."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "hint")
        layout.addWidget(hint)
        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        style_fee_action_button(refresh_btn)
        refresh_btn.clicked.connect(self._on_salary_history_tab_refresh_clicked)
        toolbar.addWidget(refresh_btn)
        toolbar.addWidget(QLabel("Filter"))
        self._salary_history_tab_filter = QLineEdit()
        self._salary_history_tab_filter.setPlaceholderText("Reference, faculty, month, role, notes…")
        self._salary_history_tab_filter.textChanged.connect(
            lambda _: self._refresh_salary_history_tab_table(reset_page=True)
        )
        toolbar.addWidget(self._salary_history_tab_filter, 1)
        layout.addLayout(toolbar)
        card = SurfaceCard()
        self._salary_history_tab_table = QTableWidget(0, 11)
        self._salary_history_tab_table.setHorizontalHeaderLabels(
            [
                "Date",
                "Reference",
                "Faculty",
                "Type",
                "Month",
                "Attendance/Days",
                "Base (₹)",
                "Paid (₹)",
                "Notes",
                "Status",
                "Undo",
            ]
        )
        configure_scrollable_data_table(self._salary_history_tab_table)
        self._salary_history_tab_table.setProperty("table_variant", "scrollable")
        card.body.addWidget(self._salary_history_tab_table, 1)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card.setMinimumHeight(0)
        layout.addWidget(card, 1)
        self._salary_history_tab_pagination = PaginationBar(
            lambda: self._salary_history_tab_change_page(-1),
            lambda: self._salary_history_tab_change_page(1),
            green_style=True,
        )
        self._salary_history_tab_pagination.refresh_theme()
        layout.addWidget(self._salary_history_tab_pagination)
        return wrap_page(
            "Salary History",
            breadcrumb_trail("Expenses", "Salary History"),
            body,
        )

    def _on_salary_history_tab_refresh_clicked(self) -> None:
        if hasattr(self, "_salary_history_tab_filter"):
            self._salary_history_tab_filter.blockSignals(True)
            try:
                self._salary_history_tab_filter.clear()
            finally:
                self._salary_history_tab_filter.blockSignals(False)
        clear_data_table_selection(getattr(self, "_salary_history_tab_table", None))
        self._refresh_salary_history_tab_table(reset_page=True)

    def _refresh_salary_history_tab_table(self, reset_page: bool = False) -> None:
        if not hasattr(self, "_salary_history_tab_table"):
            return
        if reset_page:
            self._salary_history_tab_page = 0
        search = (
            self._salary_history_tab_filter.text()
            if hasattr(self, "_salary_history_tab_filter")
            else ""
        )
        self._salary_history_tab_cache = self.expense_service.list_salary_history(
            limit=50000,
            search=search,
            include_reverted=True,
        )
        self._render_salary_history_tab_page()

    def _render_salary_history_tab_page(self) -> None:
        if not hasattr(self, "_salary_history_tab_table"):
            return
        rows = slice_page(self._salary_history_tab_cache, self._salary_history_tab_page)
        tbl = self._salary_history_tab_table
        tbl.setRowCount(len(rows))
        for i, r in enumerate(rows):
            d = r.get("expense_date")
            date_s = f"{d.day:02d}/{d.month:02d}/{d.year}" if d else ""
            attendance = float(r.get("attendance_days", 0) or 0)
            working = float(r.get("working_days", 0) or 0)
            tbl.setItem(i, 0, QTableWidgetItem(date_s))
            tbl.setItem(i, 1, QTableWidgetItem(str(r.get("reference_no") or "")))
            tbl.setItem(i, 2, QTableWidgetItem(str(r.get("faculty_name") or "")))
            tbl.setItem(i, 3, QTableWidgetItem(str(r.get("faculty_type") or "")))
            tbl.setItem(i, 4, QTableWidgetItem(str(r.get("month_label") or "")))
            tbl.setItem(i, 5, QTableWidgetItem(f"{attendance:.1f}/{working:.1f}"))
            tbl.setItem(i, 6, QTableWidgetItem(f"{float(r.get('base_amount', 0) or 0):.2f}"))
            tbl.setItem(i, 7, QTableWidgetItem(f"{float(r.get('amount', 0) or 0):.2f}"))
            tbl.setItem(i, 8, QTableWidgetItem(str(r.get("notes") or "")))
            tbl.setItem(i, 9, QTableWidgetItem(str(r.get("status") or "Paid")))
            undo_btn = QPushButton("Undo")
            style_fee_action_button(undo_btn, width=fee_action_button_width(undo_btn, min_width=92))
            if bool(r.get("is_reverted", False)):
                undo_btn.setText("Reverted")
                undo_btn.setEnabled(False)
            else:
                undo_btn.clicked.connect(
                    lambda _=False, payment_row=dict(r): self._on_salary_history_tab_undo(payment_row)
                )
            tbl.setCellWidget(i, 10, undo_btn)
        tbl.resizeColumnsToContents()
        tbl.setColumnWidth(10, max(tbl.columnWidth(10), 116))
        if hasattr(self, "_salary_history_tab_pagination"):
            self._salary_history_tab_pagination.update_state(
                self._salary_history_tab_page, len(self._salary_history_tab_cache)
            )

    def _on_salary_history_tab_undo(self, payment_row: dict) -> None:
        if bool(payment_row.get("is_reverted", False)):
            theme.message_information(self, "Already reverted", "This salary payment is already reverted.")
            return
        reference_no = str(payment_row.get("reference_no") or "")
        if not reference_no:
            theme.message_warning(self, "Missing reference", "Cannot undo salary payment without a reference.")
            return
        reply = theme.message_question(
            self,
            "Confirm undo salary",
            f"Undo salary reference “{reference_no}” for {payment_row.get('faculty_name', '')}?\n\n"
            "This removes the payout from salary totals and marks the row as “Salary reverted”.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.expense_service.undo_salary_payment(reference_no)
        except Exception as e:
            self.session.rollback()
            theme.message_critical(self, "Undo salary failed", str(e))
            return
        self._refresh_salary_history_tab_table(reset_page=False)
        self._refresh_salary_history_table()
        self._refresh_salary_control_history_table()
        self._refresh_dashboard()
        theme.message_information(
            self,
            "Salary reverted",
            f"Salary {reference_no} has been reverted and marked as “Salary reverted”.",
        )

    def _salary_history_tab_change_page(self, delta: int) -> None:
        new_page = self._salary_history_tab_page + delta
        if new_page < 0 or new_page >= page_count(len(self._salary_history_tab_cache)):
            return
        self._salary_history_tab_page = new_page
        self._render_salary_history_tab_page()

    def _build_salary_tab(self):
        body = QWidget()
        root = QHBoxLayout(body)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        left = SurfaceCard()
        left.setMinimumWidth(460)
        left.setMaximumWidth(560)
        left.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        ll = left.body
        ll.setSpacing(14)

        title = QLabel("Find faculty")
        title.setProperty("role", "section-title")
        title_hint = QLabel("Search and pick a faculty profile to view salary details and attendance snapshot.")
        title_hint.setProperty("role", "muted")
        title_hint.setWordWrap(True)
        ll.addWidget(title)
        ll.addWidget(title_hint)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        self._salary_total_faculty_label = QLabel("Total faculty: 0")
        self._salary_teaching_label = QLabel("Teaching: 0")
        self._salary_non_teaching_label = QLabel("Non Teaching: 0")
        for badge in (
            self._salary_total_faculty_label,
            self._salary_teaching_label,
            self._salary_non_teaching_label,
        ):
            badge.setProperty("role", "muted")
            badge_row.addWidget(badge)
        badge_row.addStretch(1)
        ll.addLayout(badge_row)

        tool = QHBoxLayout()
        tool.setSpacing(8)
        self._salary_refresh_btn = QPushButton("Refresh")
        style_fee_action_button(self._salary_refresh_btn)
        self._salary_refresh_btn.clicked.connect(self._on_salary_assignments_refresh_clicked)
        tool.addWidget(self._salary_refresh_btn)
        tool.addWidget(QLabel("Search by"))
        self._salary_search_by = QComboBox()
        self._salary_search_by.addItem("Name", "name")
        self._salary_search_by.addItem("Role / Designation", "role")
        self._salary_search_by.currentIndexChanged.connect(self._on_salary_assignments_filter_changed)
        tool.addWidget(self._salary_search_by, 1)
        ll.addLayout(tool)

        self._salary_filter_search = QLineEdit()
        self._salary_filter_search.setPlaceholderText("Enter faculty name")
        self._salary_filter_search.setClearButtonEnabled(True)
        self._salary_filter_search.textChanged.connect(self._on_salary_assignments_filter_changed)
        ll.addWidget(self._salary_filter_search)

        meta_row = QHBoxLayout()
        self._salary_match_count_label = QLabel("0 faculty match")
        self._salary_match_count_label.setProperty("role", "muted")
        self._salary_selection_hint = QLabel("Select a faculty from the list")
        self._salary_selection_hint.setProperty("role", "hint")
        meta_row.addWidget(self._salary_match_count_label)
        meta_row.addStretch(1)
        meta_row.addWidget(self._salary_selection_hint)
        ll.addLayout(meta_row)

        type_filter_row = QHBoxLayout()
        type_filter_row.setSpacing(14)
        type_filter_row.addWidget(QLabel("Category"))
        self._salary_filter_type_group = QButtonGroup(self)
        self._salary_filter_type_all = QRadioButton("All")
        self._salary_filter_type_non_teaching = QRadioButton("Non Teaching")
        self._salary_filter_type_teaching = QRadioButton("Teaching")
        self._salary_filter_type_group.addButton(self._salary_filter_type_all, 0)
        self._salary_filter_type_group.addButton(self._salary_filter_type_non_teaching, 1)
        self._salary_filter_type_group.addButton(self._salary_filter_type_teaching, 2)
        self._salary_filter_type_all.setChecked(True)
        for radio in (
            self._salary_filter_type_all,
            self._salary_filter_type_non_teaching,
            self._salary_filter_type_teaching,
        ):
            radio.toggled.connect(self._on_salary_assignments_filter_changed)
            type_filter_row.addWidget(radio)
        type_filter_row.addStretch(1)
        ll.addLayout(type_filter_row)

        self._salary_faculty_list = QListWidget()
        self._salary_faculty_list.setSpacing(4)
        self._salary_faculty_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._salary_faculty_list.itemSelectionChanged.connect(self._on_salary_assignment_selected)
        ll.addWidget(self._salary_faculty_list, 1)

        self._salary_assignments_pagination = PaginationBar(
            lambda: self._salary_assignments_change_page(-1),
            lambda: self._salary_assignments_change_page(1),
            green_style=True,
        )
        self._salary_assignments_pagination.refresh_theme()
        ll.addWidget(self._salary_assignments_pagination)
        root.addWidget(left, 6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._salary_detail_body = QWidget()
        self._salary_detail_body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        dl = QVBoxLayout(self._salary_detail_body)
        dl.setContentsMargins(0, 0, 0, 4)
        dl.setSpacing(16)

        self._salary_detail_heading = QLabel("No faculty selected")
        self._salary_detail_heading.setProperty("role", "section-title")
        self._salary_detail_hint = QLabel("Select a faculty member from the left panel to view details.")
        self._salary_detail_hint.setProperty("role", "muted")
        self._salary_detail_hint.setWordWrap(True)
        dl.addWidget(self._salary_detail_heading)
        dl.addWidget(self._salary_detail_hint)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)
        self._salary_profile_card = GradientProfileCard("—", "—", "—", show_action=False)
        self._salary_profile_card.setFixedWidth(306)
        top_row.addWidget(self._salary_profile_card)

        overview_card = SurfaceCard()
        overview_card.body.addWidget(CardTitleBar("Faculty overview"))
        overview_form = QFormLayout()
        overview_form.setHorizontalSpacing(16)
        overview_form.setVerticalSpacing(8)
        self._salary_lbl_name = QLabel("—")
        self._salary_lbl_type = QLabel("—")
        self._salary_lbl_role = QLabel("—")
        self._salary_lbl_monthly = QLabel("—")
        self._salary_lbl_working = QLabel("—")
        self._salary_lbl_status = QLabel("—")
        self._salary_lbl_created = QLabel("—")
        self._salary_lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._salary_lbl_status.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._salary_lbl_status.setMinimumWidth(84)
        self._salary_lbl_status.setMaximumWidth(124)
        overview_form.addRow("Faculty name", self._salary_lbl_name)
        overview_form.addRow("Category", self._salary_lbl_type)
        overview_form.addRow("Role", self._salary_lbl_role)
        overview_form.addRow("Monthly salary", self._salary_lbl_monthly)
        overview_form.addRow("Working days", self._salary_lbl_working)
        overview_form.addRow("Status", self._salary_lbl_status)
        overview_form.addRow("Created at", self._salary_lbl_created)
        overview_card.body.addLayout(overview_form)
        top_row.addWidget(overview_card, 1)
        top_row.setStretch(0, 4)
        top_row.setStretch(1, 6)
        dl.addLayout(top_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self._salary_open_window_btn = QPushButton("Salary Window")
        style_fee_action_button(self._salary_open_window_btn)
        self._salary_open_window_btn.clicked.connect(self._on_salary_open_faculty_window_clicked)
        action_row.addWidget(self._salary_open_window_btn)
        action_row.addStretch(1)
        dl.addLayout(action_row)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        card_total, self._salary_stat_total_paid = self._create_salary_stat_card("Total paid")
        card_entries, self._salary_stat_entries = self._create_salary_stat_card("Salary entries")
        card_last, self._salary_stat_last_paid = self._create_salary_stat_card("Last salary date")
        card_month, self._salary_stat_month = self._create_salary_stat_card("Attendance month")
        stats_row.addWidget(card_total, 1)
        stats_row.addWidget(card_entries, 1)
        stats_row.addWidget(card_last, 1)
        stats_row.addWidget(card_month, 1)
        dl.addLayout(stats_row)

        middle_row = QHBoxLayout()
        middle_row.setSpacing(14)

        attendance_card = SurfaceCard()
        attendance_card.body.addWidget(CardTitleBar("Attendance snapshot"))
        attendance_form = QFormLayout()
        attendance_form.setHorizontalSpacing(16)
        attendance_form.setVerticalSpacing(8)
        self._salary_snapshot_month_edit = QDateEdit(QDate.currentDate())
        self._salary_snapshot_month_edit.setCalendarPopup(True)
        self._salary_snapshot_month_edit.setDisplayFormat("MMMM yyyy")
        self._salary_snapshot_month_edit.setDate(
            QDate(QDate.currentDate().year(), QDate.currentDate().month(), 1)
        )
        self._salary_snapshot_month_edit.dateChanged.connect(self._on_salary_snapshot_month_changed)
        self._salary_attendance_month_value = QLabel("—")
        self._salary_attendance_checked_value = QLabel("—")
        self._salary_attendance_sunday_value = QLabel("—")
        self._salary_attendance_total_value = QLabel("—")
        self._salary_attendance_working_value = QLabel("—")
        attendance_form.addRow("Snapshot month", self._salary_snapshot_month_edit)
        attendance_form.addRow("Month label", self._salary_attendance_month_value)
        attendance_form.addRow("Days present", self._salary_attendance_checked_value)
        attendance_form.addRow("Additional days", self._salary_attendance_sunday_value)
        attendance_form.addRow("Attendance used", self._salary_attendance_total_value)
        attendance_form.addRow("Total working days", self._salary_attendance_working_value)
        attendance_card.body.addLayout(attendance_form)
        attendance_hint = QLabel(
            "Attendance values are entered in Faculty Window (working days and present days). "
            "Salary calculation happens there and is not saved from this page."
        )
        attendance_hint.setProperty("role", "hint")
        attendance_hint.setWordWrap(True)
        attendance_card.body.addWidget(attendance_hint)
        middle_row.addWidget(attendance_card, 1)
        dl.addLayout(middle_row)

        history_card = SurfaceCard()
        history_card.body.addWidget(CardTitleBar("Salary history (selected faculty)"))
        self._salary_total_label = QLabel("Total paid: ₹0.00")
        self._salary_total_label.setProperty("role", "muted")
        history_card.body.addWidget(self._salary_total_label)
        self._salary_history_table = QTableWidget(0, 8)
        self._salary_history_table.setHorizontalHeaderLabels(
            [
                "Date",
                "Reference",
                "Month",
                "Attendance/Days",
                "Base Salary (₹)",
                "Paid (₹)",
                "Status",
                "Notes",
            ]
        )
        configure_scrollable_data_table(self._salary_history_table)
        self._salary_history_table.setProperty("table_variant", "scrollable")
        self._salary_history_table.horizontalHeader().setSectionResizeMode(
            7, QHeaderView.ResizeMode.Stretch
        )
        history_card.body.addWidget(self._salary_history_table, 1)
        dl.addWidget(history_card, 1)

        scroll.setWidget(self._salary_detail_body)
        root.addWidget(scroll, 7)

        self._refresh_salary_list_style()
        self._refresh_salary_assignments_table(reset_page=True)
        self._clear_salary_detail_panel()
        return wrap_page(
            "Salary",
            breadcrumb_trail("Expenses", "Salary"),
            body,
        )

    def _build_salary_control_tab(self):
        body = QWidget()
        root = QHBoxLayout(body)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        left = SurfaceCard()
        left.setMinimumWidth(460)
        left.setMaximumWidth(560)
        left.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        ll = left.body
        ll.setSpacing(14)

        title = QLabel("Find faculty")
        title.setProperty("role", "section-title")
        hint = QLabel("Pick a faculty profile and edit salary or profile details.")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        ll.addWidget(title)
        ll.addWidget(hint)

        tool = QHBoxLayout()
        tool.setSpacing(8)
        self._salary_control_refresh_btn = QPushButton("Refresh")
        style_fee_action_button(self._salary_control_refresh_btn)
        self._salary_control_refresh_btn.clicked.connect(self._on_salary_control_refresh_clicked)
        tool.addWidget(self._salary_control_refresh_btn)
        tool.addWidget(QLabel("Search by"))
        self._salary_control_search_by = QComboBox()
        self._salary_control_search_by.addItem("Name", "name")
        self._salary_control_search_by.addItem("Role / Designation", "role")
        self._salary_control_search_by.currentIndexChanged.connect(
            lambda _: self._refresh_salary_control_assignments_table(reset_page=True)
        )
        tool.addWidget(self._salary_control_search_by, 1)
        ll.addLayout(tool)

        self._salary_control_filter_search = QLineEdit()
        self._salary_control_filter_search.setPlaceholderText("Enter faculty name")
        self._salary_control_filter_search.setClearButtonEnabled(True)
        self._salary_control_filter_search.textChanged.connect(
            lambda _: self._refresh_salary_control_assignments_table(reset_page=True)
        )
        ll.addWidget(self._salary_control_filter_search)

        meta_row = QHBoxLayout()
        self._salary_control_match_count_label = QLabel("0 faculty match")
        self._salary_control_match_count_label.setProperty("role", "muted")
        self._salary_control_selection_hint = QLabel("Select a faculty from the list")
        self._salary_control_selection_hint.setProperty("role", "hint")
        meta_row.addWidget(self._salary_control_match_count_label)
        meta_row.addStretch(1)
        meta_row.addWidget(self._salary_control_selection_hint)
        ll.addLayout(meta_row)

        type_filter_row = QHBoxLayout()
        type_filter_row.setSpacing(14)
        type_filter_row.addWidget(QLabel("Category"))
        self._salary_control_filter_type_group = QButtonGroup(self)
        self._salary_control_filter_type_all = QRadioButton("All")
        self._salary_control_filter_type_non_teaching = QRadioButton("Non Teaching")
        self._salary_control_filter_type_teaching = QRadioButton("Teaching")
        self._salary_control_filter_type_group.addButton(self._salary_control_filter_type_all, 0)
        self._salary_control_filter_type_group.addButton(self._salary_control_filter_type_non_teaching, 1)
        self._salary_control_filter_type_group.addButton(self._salary_control_filter_type_teaching, 2)
        self._salary_control_filter_type_all.setChecked(True)
        for radio in (
            self._salary_control_filter_type_all,
            self._salary_control_filter_type_non_teaching,
            self._salary_control_filter_type_teaching,
        ):
            radio.toggled.connect(lambda _=False: self._refresh_salary_control_assignments_table(reset_page=True))
            type_filter_row.addWidget(radio)
        type_filter_row.addStretch(1)
        ll.addLayout(type_filter_row)

        self._salary_control_faculty_list = QListWidget()
        self._salary_control_faculty_list.setSpacing(4)
        self._salary_control_faculty_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._salary_control_faculty_list.itemSelectionChanged.connect(self._on_salary_control_assignment_selected)
        ll.addWidget(self._salary_control_faculty_list, 1)

        self._salary_control_pagination = PaginationBar(
            lambda: self._salary_control_change_page(-1),
            lambda: self._salary_control_change_page(1),
            green_style=True,
        )
        self._salary_control_pagination.refresh_theme()
        ll.addWidget(self._salary_control_pagination)
        root.addWidget(left, 6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._salary_control_detail_body = QWidget()
        self._salary_control_detail_body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        dl = QVBoxLayout(self._salary_control_detail_body)
        dl.setContentsMargins(0, 0, 0, 4)
        dl.setSpacing(16)

        self._salary_control_detail_heading = QLabel("No faculty selected")
        self._salary_control_detail_heading.setProperty("role", "section-title")
        self._salary_control_detail_hint = QLabel("Select a faculty member from the left panel to view and edit.")
        self._salary_control_detail_hint.setProperty("role", "muted")
        self._salary_control_detail_hint.setWordWrap(True)
        dl.addWidget(self._salary_control_detail_heading)
        dl.addWidget(self._salary_control_detail_hint)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)
        self._salary_control_profile_card = GradientProfileCard("—", "—", "—", show_action=False)
        self._salary_control_profile_card.setFixedWidth(306)
        top_row.addWidget(self._salary_control_profile_card)

        overview_card = SurfaceCard()
        overview_card.body.addWidget(CardTitleBar("Faculty overview"))
        overview_form = QFormLayout()
        overview_form.setHorizontalSpacing(16)
        overview_form.setVerticalSpacing(8)
        self._salary_control_lbl_name = QLabel("—")
        self._salary_control_lbl_type = QLabel("—")
        self._salary_control_lbl_role = QLabel("—")
        self._salary_control_lbl_monthly = QLabel("—")
        self._salary_control_lbl_working = QLabel("—")
        self._salary_control_lbl_status = QLabel("—")
        self._salary_control_lbl_created = QLabel("—")
        self._salary_control_lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._salary_control_lbl_status.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._salary_control_lbl_status.setMinimumWidth(84)
        self._salary_control_lbl_status.setMaximumWidth(124)
        overview_form.addRow("Faculty name", self._salary_control_lbl_name)
        overview_form.addRow("Category", self._salary_control_lbl_type)
        overview_form.addRow("Role", self._salary_control_lbl_role)
        overview_form.addRow("Monthly salary", self._salary_control_lbl_monthly)
        overview_form.addRow("Working days", self._salary_control_lbl_working)
        overview_form.addRow("Status", self._salary_control_lbl_status)
        overview_form.addRow("Created at", self._salary_control_lbl_created)
        overview_card.body.addLayout(overview_form)
        top_row.addWidget(overview_card, 1)
        top_row.setStretch(0, 4)
        top_row.setStretch(1, 6)
        dl.addLayout(top_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self._salary_control_edit_salary_btn = QPushButton("Edit Salary")
        style_fee_action_button(self._salary_control_edit_salary_btn)
        self._salary_control_edit_salary_btn.clicked.connect(self._on_salary_control_edit_salary_clicked)
        action_row.addWidget(self._salary_control_edit_salary_btn)
        self._salary_control_edit_profile_btn = QPushButton("Edit Profile")
        style_fee_action_button(self._salary_control_edit_profile_btn)
        self._salary_control_edit_profile_btn.clicked.connect(self._on_salary_control_edit_profile_clicked)
        action_row.addWidget(self._salary_control_edit_profile_btn)
        action_row.addStretch(1)
        dl.addLayout(action_row)

        history_card = SurfaceCard()
        history_card.body.addWidget(CardTitleBar("Salary history (selected faculty)"))
        self._salary_control_total_label = QLabel("Total paid: ₹0.00")
        self._salary_control_total_label.setProperty("role", "muted")
        history_card.body.addWidget(self._salary_control_total_label)
        self._salary_control_history_table = QTableWidget(0, 5)
        self._salary_control_history_table.setHorizontalHeaderLabels(
            ["Date", "Month", "Attendance/Days", "Paid (₹)", "Notes"]
        )
        configure_scrollable_data_table(self._salary_control_history_table)
        self._salary_control_history_table.setProperty("table_variant", "scrollable")
        self._salary_control_history_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        history_card.body.addWidget(self._salary_control_history_table, 1)
        dl.addWidget(history_card, 1)

        scroll.setWidget(self._salary_control_detail_body)
        root.addWidget(scroll, 7)

        self._refresh_salary_control_assignments_table(reset_page=True)
        self._clear_salary_control_detail_panel()
        return wrap_page(
            "Salary Control",
            breadcrumb_trail("Expenses", "Salary Control"),
            body,
        )

    def _style_salary_control_status_badge(self, status_text: str) -> None:
        badge = getattr(self, "_salary_control_lbl_status", None)
        if badge is None:
            return
        t = theme.current_tokens()
        status_value = (status_text or "").strip().lower()
        if status_value == "active":
            bg = t.primary_soft
            fg = t.success
        elif status_value == "inactive":
            bg = t.bg_section_header
            fg = t.text_secondary
        else:
            bg = t.bg_section_header
            fg = t.text_primary
        badge.setText(status_text or "—")
        badge.setStyleSheet(
            f"background: {bg}; color: {fg}; padding: 4px 10px; border-radius: 10px; font-weight: 700;"
        )

    def _clear_salary_control_detail_panel(self) -> None:
        if hasattr(self, "_salary_control_profile_card"):
            self._salary_control_profile_card.set_student("No faculty selected", "—", "—")
        if hasattr(self, "_salary_control_detail_heading"):
            self._salary_control_detail_heading.setText("No faculty selected")
        if hasattr(self, "_salary_control_detail_hint"):
            self._salary_control_detail_hint.setText(
                "Select a faculty member from the left panel to view and edit."
            )
        for attr in (
            "_salary_control_lbl_name",
            "_salary_control_lbl_type",
            "_salary_control_lbl_role",
            "_salary_control_lbl_monthly",
            "_salary_control_lbl_working",
            "_salary_control_lbl_created",
        ):
            lbl = getattr(self, attr, None)
            if lbl is not None:
                lbl.setText("—")
        self._style_salary_control_status_badge("—")
        if hasattr(self, "_salary_control_total_label"):
            self._salary_control_total_label.setText("Total paid: ₹0.00")
        table = getattr(self, "_salary_control_history_table", None)
        if table is not None:
            table.setRowCount(0)
        edit_salary_btn = getattr(self, "_salary_control_edit_salary_btn", None)
        if edit_salary_btn is not None:
            edit_salary_btn.setEnabled(False)
        edit_profile_btn = getattr(self, "_salary_control_edit_profile_btn", None)
        if edit_profile_btn is not None:
            edit_profile_btn.setEnabled(False)

    def _on_salary_control_refresh_clicked(self) -> None:
        self._salary_control_selected_faculty_id = None
        self._clear_salary_control_detail_panel()
        if hasattr(self, "_salary_control_filter_search"):
            self._salary_control_filter_search.blockSignals(True)
            self._salary_control_filter_search.clear()
            self._salary_control_filter_search.blockSignals(False)
        if hasattr(self, "_salary_control_filter_type_all"):
            self._salary_control_filter_type_all.blockSignals(True)
            self._salary_control_filter_type_all.setChecked(True)
            self._salary_control_filter_type_all.blockSignals(False)
        if hasattr(self, "_salary_control_search_by"):
            self._salary_control_search_by.blockSignals(True)
            self._salary_control_search_by.setCurrentIndex(0)
            self._salary_control_search_by.blockSignals(False)
        self.session.expire_all()
        self._refresh_salary_control_assignments_table(reset_page=True)

    def _refresh_salary_control_assignments_table(self, *, reset_page: bool = False) -> None:
        if not hasattr(self, "_salary_control_faculty_list"):
            return
        if reset_page:
            self._salary_control_page = 0
        type_filter = None
        if self._salary_control_filter_type_teaching.isChecked():
            type_filter = "Teaching"
        elif self._salary_control_filter_type_non_teaching.isChecked():
            type_filter = "Non Teaching"
        search_text = (self._salary_control_filter_search.text() or "").strip()
        search_mode = self._salary_control_search_by.currentData()
        rows = self.expense_service.list_faculty_salaries(
            active_only=False,
            faculty_type=type_filter,
            search=None,
        )
        if search_text:
            needle = search_text.lower()
            if str(search_mode or "name").lower() == "role":
                rows = [r for r in rows if needle in str(getattr(r, "role", "") or "").lower()]
            else:
                rows = [r for r in rows if needle in str(getattr(r, "faculty_name", "") or "").lower()]
        self._salary_control_cache = list(rows or [])
        count = len(self._salary_control_cache)
        self._salary_control_match_count_label.setText(f"{count} faculty match")
        self._salary_control_selection_hint.setText(
            "Select a faculty from the list" if count else "No faculty match the filters."
        )
        all_ids = {int(getattr(r, "id", 0)) for r in self.expense_service.list_faculty_salaries(active_only=False)}
        if self._salary_control_selected_faculty_id is not None and self._salary_control_selected_faculty_id not in all_ids:
            self._salary_control_selected_faculty_id = None
        pages = page_count(len(self._salary_control_cache), self._salary_control_page_size)
        if self._salary_control_page >= pages:
            self._salary_control_page = max(0, pages - 1)
        self._render_salary_control_assignments_page()

    def _render_salary_control_assignments_page(self) -> None:
        if not hasattr(self, "_salary_control_faculty_list"):
            return
        list_widget = self._salary_control_faculty_list
        rows = slice_page(
            self._salary_control_cache,
            self._salary_control_page,
            self._salary_control_page_size,
        )
        selected_row = -1
        list_widget.blockSignals(True)
        list_widget.clear()
        for i, row in enumerate(rows):
            status = "Active" if bool(getattr(row, "is_active", True)) else "Inactive"
            item = QListWidgetItem(
                f"{str(row.faculty_name or '')} ({str(getattr(row, 'faculty_type', '') or 'Teaching')})\n"
                f"{str(row.role or 'Role not set')} | Monthly ₹{float(row.monthly_salary or 0):,.2f} "
                f"| Working {int(row.default_working_days or 0)} | {status}"
            )
            item.setData(Qt.UserRole, int(row.id))
            list_widget.addItem(item)
            if int(getattr(row, "id", 0) or 0) == int(self._salary_control_selected_faculty_id or 0):
                selected_row = i
        list_widget.blockSignals(False)
        if list_widget.count() > 0:
            if selected_row < 0:
                selected_row = 0
            list_widget.setCurrentRow(selected_row)
            current = list_widget.currentItem()
            if current is not None:
                selected_id = current.data(Qt.UserRole)
                self._salary_control_selected_faculty_id = int(selected_id) if selected_id is not None else None
                self._on_salary_control_faculty_changed()
        else:
            self._salary_control_selected_faculty_id = None
            self._clear_salary_control_detail_panel()
        self._animate_widget_fade(list_widget, start=0.78, duration=150)
        self._salary_control_pagination.update_state(
            self._salary_control_page,
            len(self._salary_control_cache),
            self._salary_control_page_size,
        )

    def _salary_control_change_page(self, delta: int) -> None:
        new_page = self._salary_control_page + int(delta)
        if new_page < 0 or new_page >= page_count(
            len(self._salary_control_cache),
            self._salary_control_page_size,
        ):
            return
        self._salary_control_page = new_page
        self._render_salary_control_assignments_page()

    def _on_salary_control_assignment_selected(self) -> None:
        if not hasattr(self, "_salary_control_faculty_list"):
            return
        current = self._salary_control_faculty_list.currentItem()
        if current is None:
            return
        faculty_id = current.data(Qt.UserRole)
        if faculty_id is None:
            return
        selected_id = int(faculty_id)
        if self._salary_control_selected_faculty_id != selected_id:
            self._salary_control_selected_faculty_id = selected_id
            self._on_salary_control_faculty_changed()

    def _on_salary_control_faculty_changed(self, _=None) -> None:
        faculty_id = self._salary_control_selected_faculty_id
        if faculty_id is None:
            self._clear_salary_control_detail_panel()
            return
        faculty = self.expense_service.repo.get_faculty_salary(int(faculty_id))
        if faculty is None:
            self._salary_control_selected_faculty_id = None
            self._clear_salary_control_detail_panel()
            return
        self._salary_control_detail_heading.setText(f"{faculty.faculty_name} ({faculty.faculty_type})")
        self._salary_control_detail_hint.setText("Edit salary and faculty profile details from this tab.")
        self._salary_control_profile_card.set_student(
            str(faculty.faculty_name or "—"),
            str(faculty.faculty_type or "—"),
            str(faculty.role or "—"),
        )
        self._salary_control_lbl_name.setText(str(faculty.faculty_name or "—"))
        self._salary_control_lbl_type.setText(str(faculty.faculty_type or "—"))
        self._salary_control_lbl_role.setText(str(faculty.role or "—"))
        self._salary_control_lbl_monthly.setText(f"₹{float(faculty.monthly_salary or 0.0):,.2f}")
        self._salary_control_lbl_working.setText(str(int(faculty.default_working_days or 0)))
        self._salary_control_lbl_created.setText(str(getattr(faculty, "created_at", "—") or "—"))
        self._style_salary_control_status_badge(
            "Active" if bool(getattr(faculty, "is_active", True)) else "Inactive"
        )
        self._salary_control_edit_salary_btn.setEnabled(True)
        self._salary_control_edit_profile_btn.setEnabled(True)
        self._refresh_salary_control_history_table()
        self._animate_widget_fade(getattr(self, "_salary_control_detail_body", None), start=0.82, duration=190)

    def _refresh_salary_control_history_table(self) -> None:
        if not hasattr(self, "_salary_control_history_table"):
            return
        faculty_id = self._salary_control_selected_faculty_id
        table = self._salary_control_history_table
        if faculty_id is None:
            table.setRowCount(0)
            self._salary_control_total_label.setText("Total paid: ₹0.00")
            return
        try:
            overview = self.expense_service.faculty_salary_overview(int(faculty_id), history_limit=1000)
        except Exception:
            table.setRowCount(0)
            self._salary_control_total_label.setText("Total paid: ₹0.00")
            return
        faculty = overview["faculty"]
        rows = overview["history"]
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            d = row.expense_date
            d_text = d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d or "")
            attendance = float(getattr(row, "attendance_days", 0) or 0)
            working = float(getattr(row, "working_days", 0) or 0)
            values = [
                d_text,
                str(row.month_label or ""),
                f"{attendance:.1f}/{working:.1f}",
                f"{float(row.amount or 0):.2f}",
                str(row.notes or ""),
            ]
            for col, value in enumerate(values):
                table.setItem(i, col, table_item(value))
        fit_table_columns_to_contents(table)
        self._salary_control_total_label.setText(
            f"Total paid to {faculty.faculty_name}: ₹{float(overview.get('total_paid', 0.0)):.2f}"
        )

    def _on_salary_control_edit_salary_clicked(self) -> None:
        faculty_id = self._salary_control_selected_faculty_id
        if faculty_id is None:
            theme.message_warning(self, "Missing faculty", "Select a faculty member first.")
            return
        self._open_faculty_profile_editor_dialog(
            int(faculty_id),
            salary_only=True,
            on_success=self._on_salary_control_update_success,
        )

    def _on_salary_control_edit_profile_clicked(self) -> None:
        faculty_id = self._salary_control_selected_faculty_id
        if faculty_id is None:
            theme.message_warning(self, "Missing faculty", "Select a faculty member first.")
            return
        self._open_faculty_profile_editor_dialog(
            int(faculty_id),
            salary_only=False,
            on_success=self._on_salary_control_update_success,
        )

    def _on_salary_control_update_success(self, updated_id: int) -> None:
        self._salary_control_selected_faculty_id = int(updated_id)
        self._refresh_salary_control_assignments_table(reset_page=False)
        self._on_salary_control_faculty_changed()
        # Keep Salary tab views in sync after profile updates.
        self._salary_selected_faculty_id = int(updated_id)
        self._refresh_salary_assignments_table(reset_page=False)
        self._on_salary_faculty_changed()
        self._refresh_salary_history_table()

    def _on_salary_faculty_changed(self, _=None) -> None:
        faculty_id = self._salary_selected_faculty_id
        if faculty_id is None:
            self._clear_salary_detail_panel()
            return
        faculty = self.expense_service.repo.get_faculty_salary(int(faculty_id))
        if faculty is None:
            self._salary_selected_faculty_id = None
            self._clear_salary_detail_panel()
            return
        self._salary_detail_heading.setText(f"{faculty.faculty_name} ({faculty.faculty_type})")
        self._salary_detail_hint.setText("Faculty profile, attendance snapshot, and salary history overview.")
        self._salary_profile_card.set_student(
            str(faculty.faculty_name or "—"),
            str(faculty.faculty_type or "—"),
            str(faculty.role or "—"),
        )
        self._salary_lbl_name.setText(str(faculty.faculty_name or "—"))
        self._salary_lbl_type.setText(str(faculty.faculty_type or "—"))
        self._salary_lbl_role.setText(str(faculty.role or "—"))
        self._salary_lbl_monthly.setText(f"₹{float(faculty.monthly_salary or 0.0):,.2f}")
        self._salary_lbl_working.setText(str(int(faculty.default_working_days or 0)))
        self._salary_lbl_created.setText(str(getattr(faculty, "created_at", "—") or "—"))
        self._style_salary_status_badge(
            "Active" if bool(getattr(faculty, "is_active", True)) else "Inactive"
        )
        self._salary_open_window_btn.setEnabled(True)
        self._refresh_salary_attendance_snapshot()
        self._refresh_salary_history_table()
        self._animate_widget_fade(getattr(self, "_salary_detail_body", None), start=0.82, duration=190)

    def _refresh_salary_faculty_options(self) -> None:
        if not hasattr(self, "_salary_faculty_list"):
            return
        self._refresh_salary_assignments_table(reset_page=False)

    def _on_salary_assignments_refresh_clicked(self) -> None:
        # Force a visible right-panel refresh cycle.
        self._salary_clear_selection_on_next_render = True
        self._salary_selected_faculty_id = None
        self._clear_salary_detail_panel()
        self._animate_widget_fade(getattr(self, "_salary_detail_body", None), start=0.72, duration=120)
        if hasattr(self, "_salary_filter_search"):
            self._salary_filter_search.blockSignals(True)
            self._salary_filter_search.clear()
            self._salary_filter_search.blockSignals(False)
        if hasattr(self, "_salary_filter_type_all"):
            self._salary_filter_type_all.blockSignals(True)
            self._salary_filter_type_all.setChecked(True)
            self._salary_filter_type_all.blockSignals(False)
        if hasattr(self, "_salary_search_by"):
            self._salary_search_by.blockSignals(True)
            self._salary_search_by.setCurrentIndex(0)
            self._salary_search_by.blockSignals(False)
        if hasattr(self, "_salary_snapshot_month_edit"):
            today_qdate = QDate.currentDate()
            first_of_month = QDate(today_qdate.year(), today_qdate.month(), 1)
            self._salary_snapshot_month_edit.blockSignals(True)
            self._salary_snapshot_month_edit.setDate(first_of_month)
            self._salary_snapshot_month_edit.blockSignals(False)
        # Force re-read of selected faculty + history/attendance from DB.
        self.session.expire_all()
        self._refresh_salary_assignments_table(reset_page=True)

    def _on_salary_assignments_filter_changed(self, _=None) -> None:
        self._refresh_salary_assignments_table(reset_page=True)

    def _refresh_salary_assignments_table(self, _=None, *, reset_page: bool = False) -> None:
        if not hasattr(self, "_salary_faculty_list"):
            return
        if reset_page:
            self._salary_assignments_page = 0
        type_filter = None
        if hasattr(self, "_salary_filter_type_teaching") and self._salary_filter_type_teaching.isChecked():
            type_filter = "Teaching"
        elif hasattr(self, "_salary_filter_type_non_teaching") and self._salary_filter_type_non_teaching.isChecked():
            type_filter = "Non Teaching"
        search_text = (self._salary_filter_search.text() or "").strip() if hasattr(
            self, "_salary_filter_search"
        ) else ""
        search_mode = self._salary_search_by.currentData() if hasattr(self, "_salary_search_by") else "name"
        rows = self.expense_service.list_faculty_salaries(
            active_only=False,
            faculty_type=type_filter,
            search=None,
        )
        if search_text:
            needle = search_text.lower()
            if str(search_mode or "name").lower() == "role":
                rows = [r for r in rows if needle in str(getattr(r, "role", "") or "").lower()]
            else:
                rows = [r for r in rows if needle in str(getattr(r, "faculty_name", "") or "").lower()]
        self._salary_assignments_cache = list(rows or [])
        if hasattr(self, "_salary_match_count_label"):
            count = len(self._salary_assignments_cache)
            self._salary_match_count_label.setText(f"{count} faculty match")
        if hasattr(self, "_salary_selection_hint"):
            self._salary_selection_hint.setText(
                "Select a faculty from the list" if self._salary_assignments_cache else "No faculty match the filters."
            )

        all_rows = self.expense_service.list_faculty_salaries(active_only=False)
        all_ids = {int(getattr(r, "id", 0)) for r in all_rows}
        if self._salary_selected_faculty_id is not None and self._salary_selected_faculty_id not in all_ids:
            self._salary_selected_faculty_id = None

        pages = page_count(len(self._salary_assignments_cache), self._salary_assignments_page_size)
        if self._salary_assignments_page >= pages:
            self._salary_assignments_page = max(0, pages - 1)
        self._render_salary_assignments_page()

        teaching = sum(1 for r in all_rows if str(getattr(r, "faculty_type", "")).lower() == "teaching")
        non_teaching = len(all_rows) - teaching
        if hasattr(self, "_salary_total_faculty_label"):
            self._salary_total_faculty_label.setText(f"Total faculty: {len(all_rows)}")
            self._salary_teaching_label.setText(f"Teaching: {teaching}")
            self._salary_non_teaching_label.setText(f"Non Teaching: {non_teaching}")

    def _render_salary_assignments_page(self) -> None:
        if not hasattr(self, "_salary_faculty_list"):
            return
        list_widget = self._salary_faculty_list
        rows = slice_page(
            self._salary_assignments_cache,
            self._salary_assignments_page,
            self._salary_assignments_page_size,
        )
        selected_row = -1
        list_widget.blockSignals(True)
        list_widget.clear()
        for i, row in enumerate(rows):
            status = "Active" if bool(getattr(row, "is_active", True)) else "Inactive"
            item = QListWidgetItem(
                f"{str(row.faculty_name or '')} ({str(getattr(row, 'faculty_type', '') or 'Teaching')})\n"
                f"{str(row.role or 'Role not set')} | Monthly ₹{float(row.monthly_salary or 0):,.2f} "
                f"| Working {int(row.default_working_days or 0)} | {status}"
            )
            item.setData(Qt.UserRole, int(row.id))
            list_widget.addItem(item)
            if int(getattr(row, "id", 0) or 0) == int(self._salary_selected_faculty_id or 0):
                selected_row = i
        list_widget.blockSignals(False)
        if list_widget.count() > 0:
            if self._salary_clear_selection_on_next_render:
                list_widget.blockSignals(True)
                list_widget.clearSelection()
                list_widget.setCurrentItem(None)
                list_widget.blockSignals(False)
                self._salary_selected_faculty_id = None
                self._clear_salary_detail_panel()
                self._salary_clear_selection_on_next_render = False
            else:
                if selected_row < 0:
                    selected_row = 0
                list_widget.setCurrentRow(selected_row)
                current = list_widget.currentItem()
                if current is not None:
                    selected_id = current.data(Qt.UserRole)
                    self._salary_selected_faculty_id = int(selected_id) if selected_id is not None else None
                    self._on_salary_faculty_changed()
        else:
            self._salary_selected_faculty_id = None
            self._salary_clear_selection_on_next_render = False
            self._clear_salary_detail_panel()
        self._animate_widget_fade(list_widget, start=0.78, duration=150)
        if hasattr(self, "_salary_assignments_pagination"):
            self._salary_assignments_pagination.update_state(
                self._salary_assignments_page,
                len(self._salary_assignments_cache),
                self._salary_assignments_page_size,
            )

    def _salary_assignments_change_page(self, delta: int) -> None:
        new_page = self._salary_assignments_page + int(delta)
        if new_page < 0 or new_page >= page_count(
            len(self._salary_assignments_cache),
            self._salary_assignments_page_size,
        ):
            return
        self._salary_assignments_page = new_page
        self._render_salary_assignments_page()

    def _refresh_salary_history_table(self) -> None:
        if not hasattr(self, "_salary_history_table"):
            return
        faculty_id = self._salary_selected_faculty_id
        table = self._salary_history_table
        if faculty_id is None:
            table.setRowCount(0)
            if hasattr(self, "_salary_total_label"):
                self._salary_total_label.setText("Total paid: ₹0.00")
            return
        try:
            overview = self.expense_service.faculty_salary_overview(int(faculty_id), history_limit=1000)
        except Exception:
            table.setRowCount(0)
            if hasattr(self, "_salary_total_label"):
                self._salary_total_label.setText("Total paid: ₹0.00")
            return
        faculty = overview["faculty"]
        rows = overview["history"]
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            d = row.expense_date
            d_text = d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d or "")
            attendance = float(getattr(row, "attendance_days", 0) or 0)
            working = float(getattr(row, "working_days", 0) or 0)
            reverted = bool(getattr(row, "is_reverted", False))
            values = [
                d_text,
                str(getattr(row, "reference_no", "") or ""),
                str(row.month_label or ""),
                f"{attendance:.1f}/{working:.1f}",
                f"{float(row.base_amount or 0):.2f}",
                f"{float(row.amount or 0):.2f}",
                "Salary reverted" if reverted else "Paid",
                str(row.notes or ""),
            ]
            for col, value in enumerate(values):
                table.setItem(i, col, table_item(value))
        fit_table_columns_to_contents(table)
        if hasattr(self, "_salary_total_label"):
            self._salary_total_label.setText(
                f"Total paid to {faculty.faculty_name}: ₹{float(overview.get('total_paid', 0.0)):.2f}"
            )
        if hasattr(self, "_salary_stat_total_paid"):
            self._salary_stat_total_paid.setText(f"₹{float(overview.get('total_paid', 0.0)):.2f}")
        if hasattr(self, "_salary_stat_entries"):
            self._salary_stat_entries.setText(str(len(rows)))
        if hasattr(self, "_salary_stat_last_paid"):
            last_paid = rows[0].expense_date if rows else None
            last_paid_text = (
                last_paid.strftime("%d/%m/%Y")
                if hasattr(last_paid, "strftime")
                else ("—" if last_paid is None else str(last_paid))
            )
            self._salary_stat_last_paid.setText(last_paid_text)

    def _refresh_salary_attendance_snapshot(self) -> None:
        if not hasattr(self, "_salary_snapshot_month_edit"):
            return
        faculty_id = self._salary_selected_faculty_id
        if faculty_id is None:
            for attr in (
                "_salary_attendance_month_value",
                "_salary_attendance_checked_value",
                "_salary_attendance_sunday_value",
                "_salary_attendance_total_value",
                "_salary_attendance_working_value",
            ):
                lbl = getattr(self, attr, None)
                if lbl is not None:
                    lbl.setText("—")
            return
        qd = self._salary_snapshot_month_edit.date()
        year = int(qd.year())
        month = int(qd.month())
        month_label = f"{year:04d}-{month:02d}"
        try:
            overview = self.expense_service.faculty_salary_overview(int(faculty_id), history_limit=500)
            rows = overview.get("history", [])
            matching_row = next((row for row in rows if str(getattr(row, "month_label", "")) == month_label), None)
        except Exception:
            matching_row = None

        attendance_days = float(getattr(matching_row, "attendance_days", 0.0) or 0.0) if matching_row else 0.0
        working_days = float(getattr(matching_row, "working_days", 0.0) or 0.0) if matching_row else 0.0
        self._salary_attendance_month_value.setText(month_label)
        self._salary_attendance_checked_value.setText(str(int(attendance_days)))
        self._salary_attendance_sunday_value.setText("0")
        self._salary_attendance_total_value.setText(str(int(attendance_days)))
        self._salary_attendance_working_value.setText(str(int(working_days)))
        if hasattr(self, "_salary_stat_month"):
            self._salary_stat_month.setText(month_label)

    def _on_salary_snapshot_month_changed(self, selected_date: QDate) -> None:
        first_day = QDate(selected_date.year(), selected_date.month(), 1)
        if selected_date.day() != 1:
            self._salary_snapshot_month_edit.blockSignals(True)
            self._salary_snapshot_month_edit.setDate(first_day)
            self._salary_snapshot_month_edit.blockSignals(False)
        self._refresh_salary_attendance_snapshot()

    def _on_salary_assignment_selected(self) -> None:
        if not hasattr(self, "_salary_faculty_list"):
            return
        current = self._salary_faculty_list.currentItem()
        if current is None:
            return
        faculty_id = current.data(Qt.UserRole)
        if faculty_id is None:
            return
        selected_id = int(faculty_id)
        if self._salary_selected_faculty_id != selected_id:
            self._salary_selected_faculty_id = selected_id
            self._on_salary_faculty_changed()

    def _on_salary_open_faculty_window_clicked(self) -> None:
        faculty_id = self._salary_selected_faculty_id
        if faculty_id is None:
            theme.message_warning(self, "Missing faculty", "Select a faculty member first.")
            return
        self._open_salary_faculty_window(int(faculty_id))

    def _open_faculty_profile_editor_dialog(
        self,
        faculty_id: int,
        *,
        salary_only: bool,
        on_success=None,
    ) -> None:
        faculty = self.expense_service.repo.get_faculty_salary(int(faculty_id))
        if faculty is None:
            theme.message_warning(self, "Missing faculty", "Selected faculty does not exist.")
            return

        popup = QDialog(self)
        popup.setWindowTitle("Edit Salary" if salary_only else "Edit Faculty Profile")
        popup.setModal(True)
        popup.resize(520 if salary_only else 620, 220 if salary_only else 340)
        theme.apply_dialog_theme(popup)

        popup_layout = QVBoxLayout(popup)
        popup_layout.setContentsMargins(16, 14, 16, 12)
        popup_layout.setSpacing(10)

        intro = QLabel(
            f"Update salary details for {faculty.faculty_name}."
            if salary_only
            else f"Update profile details for {faculty.faculty_name}."
        )
        intro.setProperty("role", "muted")
        intro.setWordWrap(True)
        popup_layout.addWidget(intro)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        name_edit = QLineEdit(str(faculty.faculty_name or ""))
        type_combo = QComboBox()
        type_combo.addItem("Teaching", "Teaching")
        type_combo.addItem("Non Teaching", "Non Teaching")
        role_edit = QLineEdit(str(faculty.role or ""))
        monthly_salary_edit = QLineEdit(f"{float(faculty.monthly_salary or 0.0):.2f}")
        working_days_edit = QLineEdit(str(int(faculty.default_working_days or 0)))
        status_combo = QComboBox()
        status_combo.addItem("active", True)
        status_combo.addItem("inactive", False)
        faculty_type = str(faculty.faculty_type or "Teaching").strip().lower()
        type_combo.setCurrentIndex(1 if faculty_type == "non teaching" else 0)
        status_combo.setCurrentIndex(0 if bool(getattr(faculty, "is_active", True)) else 1)

        if salary_only:
            form.addRow("Current salary", QLabel(f"₹{float(faculty.monthly_salary or 0.0):.2f}"))
            monthly_salary_edit.setPlaceholderText("Enter new monthly salary")
            form.addRow("New salary", monthly_salary_edit)
        else:
            form.addRow("Faculty name", name_edit)
            form.addRow("Category", type_combo)
            form.addRow("Role / Designation", role_edit)
            form.addRow("Monthly salary", monthly_salary_edit)
            form.addRow("Default working days", working_days_edit)
            form.addRow("Status", status_combo)
        popup_layout.addLayout(form)

        actions = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        popup_layout.addWidget(actions)

        def _save_changes() -> None:
            if salary_only:
                faculty_name = str(faculty.faculty_name or "")
                faculty_type_value = str(faculty.faculty_type or "Teaching")
                role_value = str(faculty.role or "")
                salary_value = (monthly_salary_edit.text() or "").strip()
                working_days_value = max(1, int(faculty.default_working_days or 1))
                is_active_value = bool(getattr(faculty, "is_active", True))
            else:
                faculty_name = (name_edit.text() or "").strip()
                faculty_type_value = str(type_combo.currentData() or "Teaching")
                role_value = (role_edit.text() or "").strip()
                salary_value = (monthly_salary_edit.text() or "").strip()
                working_days_raw = (working_days_edit.text() or "").strip()
                is_active_value = bool(status_combo.currentData())
                try:
                    working_days_value = int(float(working_days_raw or 0))
                except ValueError:
                    theme.message_warning(
                        popup,
                        "Invalid input",
                        "Default working days must be a valid number.",
                    )
                    return

            if not salary_value:
                theme.message_warning(popup, "Invalid input", "Monthly salary is required.")
                return
            try:
                monthly_salary_value = float(salary_value)
            except ValueError:
                theme.message_warning(popup, "Invalid input", "Monthly salary must be a valid number.")
                return

            try:
                updated = self.expense_service.update_faculty_profile(
                    int(faculty.id),
                    faculty_name=faculty_name,
                    faculty_type=faculty_type_value,
                    role=role_value,
                    monthly_salary=monthly_salary_value,
                    default_working_days=working_days_value,
                    is_active=is_active_value,
                )
            except ValueError as e:
                theme.message_warning(popup, "Unable to save", str(e))
                return
            except Exception as e:
                self.session.rollback()
                theme.message_critical(popup, "Save failed", str(e))
                return

            self.session.expire_all()
            if on_success is not None:
                on_success(int(updated.id))
            theme.message_information(
                self,
                "Updated",
                (
                    f"{updated.faculty_name} details were updated."
                    if not salary_only
                    else f"Salary updated to ₹{float(updated.monthly_salary or 0.0):.2f}."
                ),
            )
            popup.accept()

        actions.accepted.connect(_save_changes)
        actions.rejected.connect(popup.reject)
        popup.exec()

    def _open_salary_faculty_window(self, faculty_id: int) -> None:
        try:
            faculty = self.expense_service.repo.get_faculty_salary(int(faculty_id))
            if faculty is None:
                raise ValueError("Selected faculty does not exist.")
        except ValueError as e:
            theme.message_warning(self, "Faculty not found", str(e))
            return
        except Exception as e:
            theme.message_critical(self, "Unable to open faculty window", str(e))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Faculty Window - {faculty.faculty_name}")
        screen = dialog.screen() or self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            target_width = min(1120, max(860, int(available.width() * 0.86)))
            target_height = min(available.height() - 12, max(680, int(available.height() * 0.92)))
            x = available.x() + max(0, (available.width() - target_width) // 2)
            y = available.y() + max(0, (available.height() - target_height) // 2)
            dialog.setGeometry(x, y, target_width, target_height)
        else:
            dialog.resize(980, 780)
        theme.apply_dialog_theme(dialog)

        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(18, 16, 18, 14)
        dialog_layout.setSpacing(10)

        heading = QLabel(f"{faculty.faculty_name} ({faculty.faculty_type})")
        heading.setProperty("role", "page-title")
        sub_heading = QLabel("Faculty details and salary history")
        sub_heading.setProperty("role", "muted")
        dialog_layout.addWidget(heading)
        dialog_layout.addWidget(sub_heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)
        profile_card = GradientProfileCard(
            str(faculty.faculty_name or "—"),
            str(faculty.faculty_type or "—"),
            str(faculty.role or "—"),
            show_action=False,
        )
        profile_card.setFixedWidth(306)
        top_row.addWidget(profile_card)

        details_box = SurfaceCard()
        details_box.body.addWidget(CardTitleBar("Faculty details"))
        details_form = QFormLayout()
        details_form.setHorizontalSpacing(16)
        details_form.setVerticalSpacing(8)
        details_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        details_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        details_form.addRow("Name", QLabel(str(faculty.faculty_name or "-")))
        details_form.addRow("Category", QLabel(str(faculty.faculty_type or "-")))
        details_form.addRow("Role", QLabel(str(faculty.role or "-")))
        details_form.addRow("Monthly salary", QLabel(f"₹{float(faculty.monthly_salary or 0):.2f}"))
        details_form.addRow("Default working days", QLabel(str(int(faculty.default_working_days or 0))))
        details_form.addRow(
            "Status",
            QLabel("Active" if bool(getattr(faculty, "is_active", True)) else "Inactive"),
        )
        details_form.addRow("Created at", QLabel(str(getattr(faculty, "created_at", "-") or "-")))
        details_box.body.addLayout(details_form)
        top_row.addWidget(details_box, 1)
        top_row.setStretch(0, 4)
        top_row.setStretch(1, 6)
        layout.addLayout(top_row)

        summary_box = SurfaceCard()
        summary_box.body.addWidget(CardTitleBar("Salary summary"))
        summary_form = QFormLayout()
        summary_form.setHorizontalSpacing(16)
        summary_form.setVerticalSpacing(8)
        summary_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        summary_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        total_paid_lbl = QLabel("₹0.00")
        entry_count_lbl = QLabel("0")
        last_salary_lbl = QLabel("-")
        summary_form.addRow("Total paid", total_paid_lbl)
        summary_form.addRow("Entries", entry_count_lbl)
        summary_form.addRow("Last salary date", last_salary_lbl)
        summary_box.body.addLayout(summary_form)
        layout.addWidget(summary_box)

        record_box = SurfaceCard()
        record_box.body.addWidget(CardTitleBar("Salary calculation inputs"))
        record_form = QFormLayout()
        record_form.setHorizontalSpacing(16)
        record_form.setVerticalSpacing(8)
        record_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        record_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        record_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        attendance_month_edit = QDateEdit(QDate.currentDate())
        attendance_month_edit.setCalendarPopup(True)
        attendance_month_edit.setDisplayFormat("MMMM yyyy")
        attendance_month_edit.setDate(QDate(QDate.currentDate().year(), QDate.currentDate().month(), 1))
        month_label_value = QLabel("-")
        month_label_value.setProperty("role", "muted")
        total_working_days_edit = QLineEdit(str(int(faculty.default_working_days or 26)))
        total_working_days_edit.setPlaceholderText("Total working days")
        total_present_days_edit = QLineEdit()
        total_present_days_edit.setPlaceholderText("Total days present")
        payment_date_edit = QDateEdit(QDate.currentDate())
        payment_date_edit.setCalendarPopup(True)
        payment_date_edit.setDisplayFormat("dd/MM/yyyy")
        payment_date_edit.setMaximumDate(QDate.currentDate())
        notes_edit = QLineEdit()
        notes_edit.setPlaceholderText("Notes (optional)")
        attendance_month_edit.setMinimumWidth(220)
        payment_date_edit.setMinimumWidth(220)
        total_working_days_edit.setMinimumWidth(220)
        total_present_days_edit.setMinimumWidth(220)

        def _theme_date_edit_popup(date_edit: QDateEdit) -> None:
            t = theme.current_tokens()
            calendar_widget = QCalendarWidget(dialog)
            calendar_widget.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
            calendar_widget.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
            calendar_widget.setStyleSheet(
                f"""
                QCalendarWidget {{
                    background: {t.bg_surface};
                    color: {t.text_primary};
                    border: 1px solid {t.border};
                    border-radius: 10px;
                }}
                QCalendarWidget QWidget#qt_calendar_navigationbar {{
                    background: {t.bg_surface};
                    border-bottom: 1px solid {t.border_light};
                }}
                QCalendarWidget QToolButton {{
                    color: {t.text_primary};
                    background: {t.bg_surface};
                    border: none;
                    border-radius: 6px;
                    padding: 4px 8px;
                }}
                QCalendarWidget QToolButton:hover {{
                    background: {t.bg_hover};
                }}
                QCalendarWidget QSpinBox {{
                    background: {t.bg_input};
                    color: {t.text_primary};
                    border: 1px solid {t.border};
                    border-radius: 6px;
                    padding: 2px 6px;
                }}
                QCalendarWidget QMenu {{
                    background: {t.bg_surface};
                    color: {t.text_primary};
                    border: 1px solid {t.border};
                }}
                QCalendarWidget QMenu::item:selected {{
                    background: {t.primary_soft};
                    color: {t.text_primary};
                }}
                QCalendarWidget QAbstractItemView:enabled {{
                    background: {t.bg_surface};
                    color: {t.text_primary};
                    selection-background-color: {t.primary};
                    selection-color: {t.text_on_primary};
                }}
                """
            )
            date_edit.setCalendarWidget(calendar_widget)

        _theme_date_edit_popup(attendance_month_edit)
        _theme_date_edit_popup(payment_date_edit)
        record_form.addRow("Attendance month", attendance_month_edit)
        record_form.addRow("Month label", month_label_value)
        record_form.addRow("Total working days", total_working_days_edit)
        record_form.addRow("Total days present", total_present_days_edit)
        record_form.addRow("Payment date", payment_date_edit)
        record_form.addRow("Notes", notes_edit)
        record_box.body.addLayout(record_form)
        layout.addWidget(record_box)

        preview_lbl = QLabel(
            "Enter total working days and total days present, then click Calculate Salary or Save Salary."
        )
        preview_lbl.setProperty("role", "muted")
        layout.addWidget(preview_lbl)

        def _selected_attendance_month() -> tuple[int, int]:
            selected = attendance_month_edit.date()
            return int(selected.year()), int(selected.month())

        def _month_label_text() -> str:
            year, month = _selected_attendance_month()
            return f"{year:04d}-{month:02d}"

        def _refresh_month_label_value() -> None:
            month_label_value.setText(_month_label_text())

        def _on_attendance_month_changed(selected_date: QDate) -> None:
            # Keep month picker anchored to day 1 so month transitions remain predictable.
            first_day = QDate(selected_date.year(), selected_date.month(), 1)
            if selected_date.day() != 1:
                attendance_month_edit.blockSignals(True)
                attendance_month_edit.setDate(first_day)
                attendance_month_edit.blockSignals(False)
            _refresh_month_label_value()

        attendance_month_edit.dateChanged.connect(_on_attendance_month_changed)
        _refresh_month_label_value()

        record_actions = QHBoxLayout()
        record_actions.addStretch(1)
        save_salary_btn = QPushButton("Calculate Salary")
        style_fee_action_button(save_salary_btn)
        record_actions.addWidget(save_salary_btn)
        save_salary_entry_btn = QPushButton("Save Salary")
        style_fee_action_button(save_salary_entry_btn)
        record_actions.addWidget(save_salary_entry_btn)
        layout.addLayout(record_actions)

        table_card = SurfaceCard()
        table_card.body.addWidget(CardTitleBar("Salary history"))
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(
            ["Date", "Month", "Attendance/Days", "Paid (₹)", "Notes"]
        )
        configure_scrollable_data_table(table)
        table.setProperty("table_variant", "scrollable")
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        table_card.body.addWidget(table, 1)
        layout.addWidget(table_card, 1)
        layout.addStretch(1)
        scroll.setWidget(content)
        dialog_layout.addWidget(scroll, 1)

        def _reload_dialog_salary_data() -> None:
            try:
                current = self.expense_service.faculty_salary_overview(int(faculty.id), history_limit=500)
            except Exception:
                return
            history = current.get("history", [])
            total_paid = float(current.get("total_paid", 0.0) or 0.0)
            last_paid = history[0].expense_date if history else None
            last_paid_text = (
                last_paid.strftime("%d/%m/%Y")
                if hasattr(last_paid, "strftime")
                else ("-" if last_paid is None else str(last_paid))
            )
            total_paid_lbl.setText(f"₹{total_paid:.2f}")
            entry_count_lbl.setText(str(len(history)))
            last_salary_lbl.setText(last_paid_text)

            table.setRowCount(len(history))
            for i, row in enumerate(history):
                d = row.expense_date
                d_text = d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d or "")
                attendance = float(getattr(row, "attendance_days", 0) or 0)
                working = float(getattr(row, "working_days", 0) or 0)
                values = [
                    d_text,
                    str(row.month_label or ""),
                    f"{attendance:.1f}/{working:.1f}",
                    f"{float(row.amount or 0):.2f}",
                    str(row.notes or ""),
                ]
                for col, value in enumerate(values):
                    table.setItem(i, col, table_item(value))
            fit_table_columns_to_contents(table)

        def _salary_inputs_from_window() -> dict:
            year, month = _selected_attendance_month()
            month_label = _month_label_text()
            working_text = (total_working_days_edit.text() or "").strip()
            present_text = (total_present_days_edit.text() or "").strip()
            if not working_text:
                raise ValueError("Enter total working days.")
            if not present_text:
                raise ValueError("Enter total days present.")
            try:
                working_days = float(working_text)
            except ValueError:
                raise ValueError("Total working days must be a valid number.")
            try:
                present_days = float(present_text)
            except ValueError:
                raise ValueError("Total days present must be a valid number.")
            if working_days <= 0:
                raise ValueError("Total working days must be greater than zero.")
            if present_days < 0:
                raise ValueError("Total days present cannot be negative.")
            if present_days > working_days:
                raise ValueError("Total days present cannot be greater than total working days.")
            qd = payment_date_edit.date()
            payment_date = date(qd.year(), qd.month(), qd.day())
            notes = (notes_edit.text() or "").strip()
            return {
                "year": int(year),
                "month": int(month),
                "month_label": month_label,
                "working_days": float(working_days),
                "present_days": float(present_days),
                "payment_date": payment_date,
                "notes": notes,
            }

        def _save_salary_entry_from_window() -> None:
            try:
                payload = _salary_inputs_from_window()
                calc = self.expense_service.calculate_salary_for_faculty(
                    int(faculty.id),
                    float(payload["present_days"]),
                    working_days=float(payload["working_days"]),
                )
            except ValueError as e:
                theme.message_warning(dialog, "Invalid salary calculation", str(e))
                return
            except Exception as e:
                self.session.rollback()
                theme.message_critical(dialog, "Salary calculation failed", str(e))
                return

            payable_amount = float(calc.get("payable_amount", 0.0) or 0.0)
            preview_lbl.setText(
                f"Payable amount: ₹{payable_amount:.2f} "
                f"({float(payload['present_days']):.1f}/{float(payload['working_days']):.1f} days)"
            )
            theme.message_information(
                dialog,
                "Salary calculated",
                f"Calculated salary for {faculty.faculty_name} ({payload['month_label']}) is ₹{payable_amount:.2f}. "
                "This amount is only calculated and not saved to history.",
            )

        def _save_salary_to_history_from_window() -> None:
            try:
                payload = _salary_inputs_from_window()
                calc = self.expense_service.calculate_salary_for_faculty(
                    int(faculty.id),
                    float(payload["present_days"]),
                    working_days=float(payload["working_days"]),
                )
                payable_amount = float(calc.get("payable_amount", 0.0) or 0.0)
                confirmed = theme.message_question(
                    dialog,
                    "Confirm salary save",
                    (
                        f"Save salary entry for {faculty.faculty_name}?\n\n"
                        f"Month: {payload['month_label']}\n"
                        f"Payment date: {payload['payment_date'].strftime('%d/%m/%Y')}\n"
                        f"Attendance: {float(payload['present_days']):.1f}/{float(payload['working_days']):.1f} days\n"
                        f"Amount paid: ₹{payable_amount:.2f}"
                    ),
                    buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    default_button=QMessageBox.StandardButton.No,
                )
                if confirmed != QMessageBox.StandardButton.Yes:
                    return
                row = self.expense_service.record_salary_from_attendance(
                    int(faculty.id),
                    float(payload["present_days"]),
                    working_days=float(payload["working_days"]),
                    month_label=str(payload["month_label"]),
                    expense_date=payload["payment_date"],
                    notes=str(payload["notes"]),
                )
            except ValueError as e:
                theme.message_warning(dialog, "Salary save error", str(e))
                return
            except Exception as e:
                self.session.rollback()
                theme.message_critical(dialog, "Salary save failed", str(e))
                return

            preview_lbl.setText(f"Payable amount: ₹{float(row.amount or 0.0):.2f} (saved to salary history)")
            notes_edit.clear()
            _reload_dialog_salary_data()
            self._refresh_salary_history_table()
            self._refresh_salary_history_tab_table(reset_page=False)
            self._refresh_salary_control_history_table()
            theme.message_information(
                dialog,
                "Salary saved",
                (
                    f"Salary saved for {row.person_name}.\n"
                    f"Month: {row.month_label}\n"
                    f"Amount paid: ₹{float(row.amount or 0.0):.2f}"
                ),
            )

        save_salary_btn.clicked.connect(_save_salary_entry_from_window)
        save_salary_entry_btn.clicked.connect(_save_salary_to_history_from_window)
        _reload_dialog_salary_data()

        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        actions.rejected.connect(dialog.reject)
        actions.accepted.connect(dialog.accept)
        dialog_layout.addWidget(actions)
        dialog.exec()

    def _build_other_expense_tab(self):
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        intro = QLabel(
            "Document and calculate non-salary expenses such as rent, donation, and stationary."
        )
        intro.setProperty("role", "hint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form_card = SurfaceCard()
        form_card.body.addWidget(CardTitleBar("Add other expense"))
        row = QHBoxLayout()
        self._other_category = QComboBox()
        self._other_category.addItems(["Rent", "Donation", "Stationary", "Other"])
        self._other_amount = QLineEdit()
        self._other_amount.setPlaceholderText("Amount (₹)")
        self._other_date = QDateEdit(QDate.currentDate())
        self._other_date.setCalendarPopup(True)
        self._other_date.setDisplayFormat("dd/MM/yyyy")
        self._other_date.setMaximumDate(QDate.currentDate())
        self._other_description = QLineEdit()
        self._other_description.setPlaceholderText("Description")
        self._other_notes = QLineEdit()
        self._other_notes.setPlaceholderText("Notes (optional)")
        self._other_add_btn = QPushButton("Add Expense")
        style_fee_action_button(self._other_add_btn)
        self._other_add_btn.clicked.connect(self._on_add_other_expense_clicked)
        row.addWidget(self._other_category)
        row.addWidget(self._other_amount)
        row.addWidget(self._other_date)
        row.addWidget(self._other_description, 2)
        row.addWidget(self._other_notes, 2)
        row.addWidget(self._other_add_btn)
        form_card.body.addLayout(row)
        layout.addWidget(form_card)

        totals_card = SurfaceCard()
        totals_card.body.addWidget(CardTitleBar("Expense totals"))
        self._other_totals_label = QLabel("Total: ₹0.00")
        self._other_totals_label.setProperty("role", "muted")
        self._other_totals_label.setWordWrap(True)
        totals_card.body.addWidget(self._other_totals_label)
        layout.addWidget(totals_card)

        table_card = SurfaceCard()
        table_card.body.addWidget(CardTitleBar("Other expense history"))
        self._other_expenses_table = QTableWidget(0, 5)
        self._other_expenses_table.setHorizontalHeaderLabels(
            ["Date", "Category", "Description", "Amount (₹)", "Notes"]
        )
        configure_scrollable_data_table(self._other_expenses_table)
        self._other_expenses_table.setProperty("table_variant", "scrollable")
        table_card.body.addWidget(self._other_expenses_table, 1)
        layout.addWidget(table_card, 1)

        self._refresh_other_expense_table()
        return wrap_page(
            "Other Expenses",
            breadcrumb_trail("Expenses", "Other"),
            body,
        )

    def _refresh_other_expense_table(self) -> None:
        if not hasattr(self, "_other_expenses_table"):
            return
        rows = self.expense_service.list_other_expenses(limit=1000)
        table = self._other_expenses_table
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            d = row.expense_date
            d_text = d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d or "")
            values = [
                d_text,
                str(row.category or ""),
                str(row.description or ""),
                f"{float(row.amount or 0):.2f}",
                str(row.notes or ""),
            ]
            for col, value in enumerate(values):
                table.setItem(i, col, table_item(value))
        fit_table_columns_to_contents(table)
        totals = self.expense_service.other_totals()
        total = float(totals.get("total", 0.0) or 0.0)
        by_category = totals.get("by_category", {})
        parts = [f"{name}: ₹{float(amount):.2f}" for name, amount in by_category.items()]
        details = " | ".join(parts) if parts else "No expense entries yet."
        if hasattr(self, "_other_totals_label"):
            self._other_totals_label.setText(f"Total: ₹{total:.2f} — {details}")

    def _on_add_other_expense_clicked(self) -> None:
        try:
            amount = float((self._other_amount.text() or "").strip() or 0.0)
            category = self._other_category.currentText()
            qd = self._other_date.date()
            expense_date = date(qd.year(), qd.month(), qd.day())
            description = (self._other_description.text() or "").strip()
            notes = (self._other_notes.text() or "").strip()
            self.expense_service.add_other_expense(
                category,
                amount,
                expense_date=expense_date,
                description=description,
                notes=notes,
            )
        except ValueError as e:
            theme.message_warning(self, "Invalid expense", str(e))
            return
        except Exception as e:
            self.session.rollback()
            theme.message_critical(self, "Expense save failed", str(e))
            return

        self._other_amount.clear()
        self._other_description.clear()
        self._other_notes.clear()
        self._refresh_other_expense_table()
        theme.message_information(self, "Saved", "Other expense entry saved.")

    def _clear_list_selection(self, list_widget: QListWidget | None) -> None:
        if list_widget is None:
            return
        list_widget.blockSignals(True)
        try:
            list_widget.clearSelection()
            list_widget.setCurrentItem(None)
        finally:
            list_widget.blockSignals(False)

    def _on_payment_history_refresh_clicked(self):
        """Clear filter, reset to page 1, and reload all payment history."""
        if hasattr(self, "_payment_history_filter"):
            self._payment_history_filter.blockSignals(True)
            try:
                self._payment_history_filter.clear()
            finally:
                self._payment_history_filter.blockSignals(False)
        clear_data_table_selection(getattr(self, "_payment_history_table", None))
        self._refresh_payment_history_table(reset_page=True)

    def _refresh_payment_history_table(self, reset_page: bool = False):
        if not hasattr(self, "_payment_history_table"):
            return
        if reset_page:
            self._payment_history_page = 0
        search = self._payment_history_filter.text() if hasattr(self, "_payment_history_filter") else ""
        self._payment_history_cache = self.payment_service.list_payment_history(
            limit=50000,
            search=search,
            include_reverted=True,
        )
        self._render_payment_history_page()

    def _render_payment_history_page(self):
        if not hasattr(self, "_payment_history_table"):
            return
        rows = slice_page(self._payment_history_cache, self._payment_history_page)
        tbl = self._payment_history_table
        tbl.setRowCount(len(rows))
        for i, r in enumerate(rows):
            is_reverted = bool(r.get("is_reverted", False))
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
            tbl.setItem(i, 8, QTableWidgetItem(str(r.get("status") or "Paid")))
            print_btn = QPushButton("Print Receipt")
            style_fee_action_button(print_btn, width=fee_action_button_width(print_btn, min_width=118))
            print_btn.clicked.connect(
                lambda _=False, payment_row=dict(r): self._on_payment_history_print_receipt(payment_row)
            )
            tbl.setCellWidget(i, 9, print_btn)
            undo_btn = QPushButton("Undo")
            style_fee_action_button(undo_btn, width=fee_action_button_width(undo_btn, min_width=92))
            if bool(r.get("is_reverted", False)):
                undo_btn.setText("Reverted")
                undo_btn.setEnabled(False)
            else:
                undo_btn.clicked.connect(
                    lambda _=False, payment_row=dict(r): self._on_payment_history_undo_payment(payment_row)
                )
            tbl.setCellWidget(i, 10, undo_btn)
        tbl.resizeColumnsToContents()
        tbl.setColumnWidth(9, max(tbl.columnWidth(9), 142))
        tbl.setColumnWidth(10, max(tbl.columnWidth(10), 116))
        if hasattr(self, "_payment_history_pagination"):
            self._payment_history_pagination.update_state(
                self._payment_history_page, len(self._payment_history_cache)
            )

    def _on_payment_history_print_receipt(self, payment_row: dict) -> None:
        reference_no = str(payment_row.get("reference_no") or "")
        student_roll = str(payment_row.get("student_roll") or "")
        student_name = str(payment_row.get("student_name") or "")
        class_name = str(payment_row.get("class_name") or "")
        section = str(payment_row.get("section") or "")
        guardian_name = str(
            payment_row.get("father_name") or payment_row.get("guardian_name") or ""
        )
        amount = float(payment_row.get("amount", 0) or 0)
        discount = float(payment_row.get("discount", 0) or 0)
        net_paid = max(0.0, amount - discount)

        default_name = f"Receipt_{student_roll}_{reference_no}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save receipt",
            str(Path.home() / default_name),
            "PDF (*.pdf)",
        )
        if not path:
            return
        if not str(path).lower().endswith(".pdf"):
            path = f"{path}.pdf"
        try:
            from backend.reports.payment_receipt_pdf import render_payment_receipt

            render_payment_receipt(
                Path(path),
                student_name=student_name,
                roll_number=student_roll,
                class_name=class_name,
                section=section,
                guardian_name=guardian_name,
                school_fees_paid=net_paid,
                van_fees_paid=0.0,
                discount=discount,
                receipt_no=reference_no,
                generated_at=datetime.now(),
            )
        except Exception as e:
            theme.message_warning(
                self,
                "Receipt file error",
                f"Could not generate receipt PDF:\n{e}",
            )
            return
        theme.message_information(
            self,
            "Receipt saved",
            f"Receipt saved to:\n{path}",
        )

    def _on_payment_history_undo_payment(self, payment_row: dict) -> None:
        if bool(payment_row.get("is_reverted", False)):
            theme.message_information(self, "Already reverted", "This payment is already reverted.")
            return
        reference_no = str(payment_row.get("reference_no") or "")
        if not reference_no:
            theme.message_warning(self, "Missing reference", "Cannot undo payment without a reference number.")
            return
        reply = theme.message_question(
            self,
            "Confirm undo payment",
            f"Undo payment reference “{reference_no}”?\n\n"
            "This will revert the payment impact on fees and discount, and keep the payment row "
            "in history with status “Payment reverted”.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            payment = self.payment_service.undo_payment(reference_no)
        except Exception as e:
            self.session.rollback()
            theme.message_critical(self, "Undo payment failed", str(e))
            return

        self._refresh_payment_history_table(reset_page=False)
        self.perform_search(reset_page=False)
        self._invalidate_payment_student_cache()
        pay_date = self._payment_record_date(getattr(payment, "payment_date", None))
        self._refresh_dashboard(chart_date=pay_date)
        theme.message_information(
            self,
            "Payment reverted",
            f"Payment {reference_no} has been reverted and marked as “Payment reverted”.",
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
            theme.message_warning(self, "Invalid amount", "Enter a valid number for the school fee.")
            return
        if new_amt < 0:
            theme.message_warning(self, "Invalid amount", "School fee cannot be negative.")
            return
        n = self.class_fee_service.count_students_in_class(class_key)
        reply = theme.message_question(
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
            theme.message_information(
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
            theme.message_critical(self, "Fee update failed", str(e))

    def _on_van_fee_control_apply_clicked(self, village_key: str):
        edit = self._van_fee_control_amount_edits.get(village_key)
        if edit is None:
            return
        raw = (edit.text() or "").strip()
        try:
            new_amt = float(raw) if raw else 0.0
        except ValueError:
            theme.message_warning(self, "Invalid amount", "Enter a valid number for the van fee.")
            return
        if new_amt < 0:
            theme.message_warning(self, "Invalid amount", "Van fee cannot be negative.")
            return
        n = self.village_van_fee_service.count_students_on_van_transport_in_village(village_key)
        reply = theme.message_question(
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
            theme.message_information(
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
            theme.message_critical(self, "Van fee update failed", str(e))

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
            "Mobile Number 1": "Enter mobile number 1",
            "Mobile Number 2": "Enter mobile number 2",
            "Village": "Enter village name",
            "Class-Section": "Enter class-section (example: I-A or 10-B)",
            "Status": "Enter student status",
            "Father Name": "Enter father name",
            "Mother Name": "Enter mother name",
            "Aadhaar": "Enter aadhaar number",
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
        self._clear_list_selection(tab.student_results)
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
        candidate_ids = [s.student_id for s in candidates]
        due_map = (
            self.payment_service.get_students_due_breakdown(candidate_ids)
            if candidate_ids
            else {}
        )
        if outstanding_only:
            candidates = [s for s in candidates if float(due_map.get(s.student_id, {}).get("total", 0) or 0) > 0.01]
        self._details_filtered_ids = [s.student_id for s in candidates]
        self._details_due_map = due_map

    def _refresh_details_tab(self, reset_page: bool = False) -> None:
        tab = self._student_details_tab
        if tab is None:
            return
        if reset_page:
            self._details_page_index = 0
        self._rebuild_details_filtered_ids()
        self._render_details_list()
        if self.selected_student and self.selected_student.student_id in self._details_filtered_ids:
            self._show_details_for_student(self.selected_student)
        elif not tab.student_results.currentItem():
            tab.clear_detail()

    def _render_details_list(self) -> None:
        tab = self._student_details_tab
        if tab is None:
            return
        ids = slice_page(self._details_filtered_ids, self._details_page_index)
        self._ensure_payment_students_loaded()
        by_id = {s.student_id: s for s in self._all_payment_students}
        due_map = getattr(self, "_details_due_map", {})
        current_id = self.selected_student.student_id if self.selected_student else None
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
            transport = str(getattr(s, "transport_mode", "van") or "van").strip().lower()
            transport_tag = "Own" if transport == "own" else "Van"
            due_tag = "Paid up" if total <= 0.01 else f"Due ₹{total:.2f}"
            line = (
                f"{s.student_id} - {s.full_name}\n"
                f"Class {s.class_name}-{s.section} | {status.title()} | {transport_tag} | {due_tag}"
            )
            item = QListWidgetItem(line)
            item.setData(Qt.UserRole, s.student_id)
            if total > 0.01:
                item.setForeground(Qt.GlobalColor.darkRed)
            tab.student_results.addItem(item)
            if current_id and s.student_id == current_id:
                selected_item = item
        if selected_item:
            tab.student_results.setCurrentItem(selected_item)
        tab.student_results.blockSignals(False)
        self._details_pagination.update_state(self._details_page_index, len(self._details_filtered_ids))
        if hasattr(tab, "animate_results_refresh"):
            tab.animate_results_refresh()

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
        s = self.session.get(Student, str(student_id))
        if not s:
            return
        self.selected_student = s
        self._show_details_for_student(s)

    def _show_details_for_student(self, student: Student) -> None:
        tab = self._student_details_tab
        if tab is None:
            return
        due = self.payment_service.get_student_due_breakdown(student.student_id)
        roll = str(getattr(student, "student_id", None) or "")
        recent = [
            p
            for p in self.payment_service.list_payment_history(
                limit=2000,
                search=roll,
                include_reverted=True,
            )
            if str(p.get("student_roll") or "") == roll
        ][:8]
        tab.show_detail(
            {
                "student": student,
                "due": due,
                "recent_payments": recent,
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

    def _payment_student_matches(self, student, criteria: str, q: str) -> bool:
        if not q:
            return True
        if criteria == "Roll Number":
            return q in str(student.student_id or "").lower()
        if criteria == "Name":
            return q in str(student.full_name or "").lower()
        if criteria == "Mobile Number 1":
            return q in str(getattr(student, "mobile_number_1", None) or student.phone or "").lower()
        if criteria == "Mobile Number 2":
            return q in str(getattr(student, "mobile_number_2", None) or "").lower()
        if criteria == "Village":
            return q in str(getattr(student, "village", None) or "").lower()
        if criteria == "Class-Section":
            return class_section_matches_query(student.class_name, student.section, q)
        if criteria == "Status":
            return q in str(student.status or "").lower()
        if criteria == "Father Name":
            return q in str(getattr(student, "father_name", None) or student.guardian_name or "").lower()
        if criteria == "Mother Name":
            return q in str(getattr(student, "mother_name", None) or "").lower()
        if criteria == "Aadhaar":
            return q in str(getattr(student, "aadhaar", None) or "").lower()
        return True

    def _rebuild_payment_filtered_ids(self, pane_id: str) -> None:
        self._ensure_payment_students_loaded()
        pane = self._payment_panes[pane_id]
        q = (pane.student_search.text() or "").strip().lower()
        criteria = pane.search_by.currentText()
        pane.filtered_ids = [
            s.student_id
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
        self._clear_list_selection(pane.student_results)
        pane.student_results.clear()
        self.selected_student = None
        self._set_payment_preview_idle(pane)
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
        by_id = {s.student_id: s for s in self._all_payment_students}
        due_map = self.payment_service.get_students_due_breakdown(ids) if ids else {}
        current_student_id = self.selected_student.student_id if self.selected_student else None
        pane.student_results.blockSignals(True)
        pane.student_results.clear()
        selected_item = None
        for sid in ids:
            s = by_id.get(sid)
            if not s:
                continue
            due = due_map.get(sid, {})
            total_due = float(due.get("total", 0) or 0)
            phone = str(getattr(s, "mobile_number_1", None) or s.phone or "—")
            status = str(s.status or "active").title()
            due_tag = "Paid up" if total_due <= 0.01 else f"Due ₹{total_due:.2f}"
            item = QListWidgetItem(
                f"{s.student_id} - {s.full_name}\n"
                f"Class {s.class_name}-{s.section} | {phone} | {status} | {due_tag}"
            )
            item.setData(Qt.UserRole, s.student_id)
            if total_due > 0.01:
                item.setForeground(QColor(theme.current_tokens().danger))
            pane.student_results.addItem(item)
            if current_student_id and s.student_id == current_student_id:
                selected_item = item
        if selected_item:
            pane.student_results.setCurrentItem(selected_item)
        pane.student_results.blockSignals(False)
        if pane.count_label is not None:
            pane.count_label.setText(
                f"{len(pane.filtered_ids)} students found • showing {len(ids)} on this page"
            )
        selected_summary = None
        if current_student_id:
            selected_summary = by_id.get(current_student_id)
            if selected_summary is None and self.selected_student is not None:
                selected_summary = self.selected_student
        if selected_summary is not None:
            selected_due = due_map.get(selected_summary.student_id)
            if selected_due is None:
                selected_due = self.payment_service.get_student_due_breakdown(selected_summary.student_id)
            self._set_payment_preview_student(pane, selected_summary, selected_due)
        else:
            self._set_payment_preview_idle(pane)
        if pane.pagination is not None:
            pane.pagination.update_state(pane.page_index, len(pane.filtered_ids))
        self._animate_widget_fade(pane.student_results, start=0.76, duration=150)

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
            "Mobile Number 1": "Enter mobile number 1",
            "Mobile Number 2": "Enter mobile number 2",
            "Village": "Enter village name",
            "Class-Section": "Enter class-section (example: I-A or 10-B)",
            "Status": "Enter student status",
            "Father Name": "Enter father name",
            "Mother Name": "Enter mother name",
            "Aadhaar": "Enter aadhaar number",
        }
        pane.student_search.setPlaceholderText(placeholder_map.get(basis, ""))
        self._refresh_payment_pane(pane_id, reset_page=True)

    def _on_payment_student_selected(self, pane_id, item):
        student_id = item.data(Qt.UserRole) if item else None
        pane = self._payment_panes.get(pane_id)
        if not student_id:
            self.selected_student = None
            if pane is not None:
                self._set_payment_preview_idle(pane)
            return
        s = self.session.get(Student, str(student_id))
        if not s:
            return
        self.selected_student = s
        if pane is not None:
            self._set_payment_preview_student(pane, s, self.payment_service.get_student_due_breakdown(s.student_id))

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
        screen = dialog.screen() or self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            target_width = min(1120, max(860, int(available.width() * 0.86)))
            target_height = min(available.height() - 12, max(680, int(available.height() * 0.92)))
            x = available.x() + max(0, (available.width() - target_width) // 2)
            y = available.y() + max(0, (available.height() - target_height) // 2)
            dialog.setGeometry(x, y, target_width, target_height)
        else:
            dialog.resize(980, 780)
        theme.apply_dialog_theme(dialog)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(12)
        heading = QLabel(f"{student.full_name} ({student.student_id})")
        heading.setProperty("role", "page-title")
        if student_fields_editable:
            sub_heading = QLabel("Edit student details below, then click Save.")
        else:
            sub_heading = QLabel("Confirm details and collect payment with a single smooth flow.")
        sub_heading.setProperty("role", "muted")
        layout.addWidget(heading)
        layout.addWidget(sub_heading)
        due_init = self.payment_service.get_student_due_breakdown(student.student_id)

        content_scroll = QScrollArea()
        content_scroll.setWidgetResizable(True)
        content_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 2, 0, 2)
        content_layout.setSpacing(12)

        pay_pending_badge = pay_school_current_badge = None
        pay_van_current_badge = pay_total_badge = None
        if show_payment_ui:
            t = theme.current_tokens()
            payoff_card = SurfaceCard()
            payoff_title = QLabel("Payment snapshot")
            payoff_title.setProperty("role", "section-title")
            payoff_hint = QLabel("Live due summary before collecting payment.")
            payoff_hint.setProperty("role", "hint")
            payoff_row = QHBoxLayout()
            payoff_row.setSpacing(8)
            pay_pending_badge = QLabel(
                f"Pending fees\n₹{pending_fees(due_init):.2f}"
            )
            pay_school_current_badge = QLabel(
                f"School fees due (current year)\n₹{float(due_init.get('fee_due', 0) or 0):.2f}"
            )
            pay_van_current_badge = QLabel(
                f"Van fees due (current year)\n₹{float(due_init.get('van_due', 0) or 0):.2f}"
            )
            pay_total_badge = QLabel(f"Total payable\n₹{float(due_init.get('total', 0) or 0):.2f}")
            for badge in (
                pay_pending_badge,
                pay_school_current_badge,
                pay_van_current_badge,
                pay_total_badge,
            ):
                badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                badge.setMinimumHeight(58)
                badge.setStyleSheet(
                    f"background: {t.bg_section_header}; color: {t.text_primary}; border: 1px solid {t.border}; "
                    "border-radius: 10px; padding: 8px 10px; font-weight: 700;"
                )
                payoff_row.addWidget(badge)
            payoff_card.body.addWidget(payoff_title)
            payoff_card.body.addWidget(payoff_hint)
            payoff_card.body.addLayout(payoff_row)
            content_layout.addWidget(payoff_card)

        details_box = QGroupBox("Student Information")
        details_layout = QFormLayout(details_box)
        lbl_created = QLabel(str(student.created_at or "-"))

        edit_student_id = edit_name = edit_class = edit_section = edit_mobile_1 = edit_mobile_2 = None
        edit_gender = edit_father_name = edit_mother_name = edit_dob = edit_caste = edit_aadhaar = None
        edit_village = edit_transport = None
        lbl_school_fees_editable = None
        lbl_van_fees_editable = None
        edit_status = None
        lbl_van_fees = None
        lbl_school_fees = None
        ro_student_id = ro_name = ro_class = ro_section = ro_mobile_1 = ro_mobile_2 = None
        ro_village = ro_transport = ro_gender = ro_father_name = ro_mother_name = ro_dob = ro_caste = ro_aadhaar = ro_status = None

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
            edit_mobile_1 = QLineEdit(
                normalize_phone_text(str(getattr(student, "mobile_number_1", None) or student.phone or ""))
            )
            configure_phone_line_edit(edit_mobile_1)
            edit_mobile_2 = QLineEdit(
                normalize_phone_text(str(getattr(student, "mobile_number_2", None) or ""))
            )
            configure_phone_line_edit(edit_mobile_2)
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
            edit_gender = QComboBox()
            edit_gender.addItems(["Male", "Female", "Other"])
            edit_gender.setCurrentText(self._gender_for_combo(getattr(student, "gender", None)))
            edit_father_name = QLineEdit(
                str(getattr(student, "father_name", None) or getattr(student, "guardian_name", None) or "")
            )
            edit_mother_name = QLineEdit(str(getattr(student, "mother_name", None) or ""))
            dob_value = getattr(student, "date_of_birth", None)
            if isinstance(dob_value, datetime):
                dob_text = dob_value.strftime("%d/%m/%Y")
            elif isinstance(dob_value, date):
                dob_text = dob_value.strftime("%d/%m/%Y")
            else:
                dob_text = str(dob_value or "")
            edit_dob = QLineEdit(dob_text)
            edit_dob.setPlaceholderText("DD/MM/YYYY")
            edit_caste = QLineEdit(str(getattr(student, "caste", None) or ""))
            edit_aadhaar = QLineEdit(str(getattr(student, "aadhaar", None) or ""))
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
            details_layout.addRow("Created At", lbl_created)
            details_layout.addRow("Student ID", edit_student_id)
            details_layout.addRow("Name", edit_name)
            details_layout.addRow("Gender", edit_gender)
            details_layout.addRow("Father Name", edit_father_name)
            details_layout.addRow("Mother Name", edit_mother_name)
            details_layout.addRow("Class", edit_class)
            details_layout.addRow("Section", edit_section)
            details_layout.addRow("Mobile Number 1", edit_mobile_1)
            details_layout.addRow("Mobile Number 2", edit_mobile_2)
            details_layout.addRow("Date of Birth", edit_dob)
            details_layout.addRow("Caste", edit_caste)
            details_layout.addRow("Aadhaar", edit_aadhaar)
            details_layout.addRow("Village", edit_village)
            details_layout.addRow("Transport", edit_transport)
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
            ro_gender = QLabel(self._gender_display(getattr(student, "gender", None)) or "-")
            ro_father_name = QLabel(
                str(getattr(student, "father_name", None) or getattr(student, "guardian_name", None) or "-")
            )
            ro_mother_name = QLabel(str(getattr(student, "mother_name", None) or "-"))
            ro_class = QLabel(str(student.class_name or "-"))
            ro_section = QLabel(str(student.section or "-"))
            ro_mobile_1 = QLabel(str(getattr(student, "mobile_number_1", None) or student.phone or "-"))
            ro_mobile_2 = QLabel(str(getattr(student, "mobile_number_2", None) or "-"))
            dob_value = getattr(student, "date_of_birth", None)
            if isinstance(dob_value, datetime):
                ro_dob = QLabel(dob_value.strftime("%d/%m/%Y"))
            elif isinstance(dob_value, date):
                ro_dob = QLabel(dob_value.strftime("%d/%m/%Y"))
            else:
                ro_dob = QLabel(str(dob_value or "-"))
            ro_caste = QLabel(str(getattr(student, "caste", None) or "-"))
            ro_aadhaar = QLabel(str(getattr(student, "aadhaar", None) or "-"))
            ro_village = QLabel(str(getattr(student, "village", None) or "-"))
            tm_ro = (getattr(student, "transport_mode", None) or "van").strip().lower()
            ro_transport = QLabel("Own transport" if tm_ro == "own" else "Van transport")
            ro_status = QLabel(str(student.status or "-"))
            lbl_van_fees = QLabel(f"{float(getattr(student, 'van_fees', 0) or 0):.2f}")
            lbl_school_fees = QLabel(f"{float(getattr(student, 'school_fees', 0) or 0):.2f}")
            details_layout.addRow("Student ID", ro_student_id)
            details_layout.addRow("Name", ro_name)
            details_layout.addRow("Gender", ro_gender)
            details_layout.addRow("Father Name", ro_father_name)
            details_layout.addRow("Mother Name", ro_mother_name)
            details_layout.addRow("Class", ro_class)
            details_layout.addRow("Section", ro_section)
            details_layout.addRow("Mobile Number 1", ro_mobile_1)
            details_layout.addRow("Mobile Number 2", ro_mobile_2)
            details_layout.addRow("Date of Birth", ro_dob)
            details_layout.addRow("Caste", ro_caste)
            details_layout.addRow("Aadhaar", ro_aadhaar)
            details_layout.addRow("Village", ro_village)
            details_layout.addRow("Transport", ro_transport)
            details_layout.addRow("Van Fees", lbl_van_fees)
            details_layout.addRow("School Fees", lbl_school_fees)
            details_layout.addRow("Status", ro_status)
        content_layout.addWidget(details_box)

        def _format_joining_date(st) -> str:
            created = getattr(st, "created_at", None)
            if created is None:
                return "—"
            if isinstance(created, datetime):
                return created.strftime("%d/%m/%Y")
            return str(created)

        fees_box = QGroupBox("Fee balance (pending + current year)")
        fees_layout = QFormLayout(fees_box)
        joining_lbl = QLabel(_format_joining_date(student))
        year_lbl = QLabel(due_init.get("current_year_label") or "—")
        pending_fees_lbl = QLabel(f"{pending_fees(due_init):.2f}")
        school_current_lbl = QLabel(f"{due_init.get('fee_due', 0):.2f}")
        van_current_lbl = QLabel(f"{due_init.get('van_due', 0):.2f}")
        school_payable_lbl = QLabel(f"{due_init.get('school_payable', due_init.get('fee_due', 0)):.2f}")
        van_payable_lbl = QLabel(f"{due_init.get('van_payable', due_init.get('van_due', 0)):.2f}")
        total_payable_lbl = QLabel(f"{due_init.get('total', 0):.2f}")
        fees_layout.addRow("Student joining date", joining_lbl)
        fees_layout.addRow("Academic year", year_lbl)
        fees_layout.addRow("Pending fees", pending_fees_lbl)
        fees_layout.addRow("School fees due (current year)", school_current_lbl)
        fees_layout.addRow("Van fees due (current year)", van_current_lbl)
        fees_layout.addRow("Payable school fees", school_payable_lbl)
        fees_layout.addRow("Payable van fees", van_payable_lbl)
        fees_layout.addRow("Total payable amount", total_payable_lbl)
        content_layout.addWidget(fees_box)

        pay_pending_fees_lbl = None
        pay_school_current_lbl = pay_van_current_lbl = None
        popup_school_pay = popup_van_pay = popup_discount = popup_payment_date = popup_mode = None

        def _apply_due_breakdown(d: dict, st=None) -> None:
            pending_fees_lbl.setText(f"{pending_fees(d):.2f}")
            school_current_lbl.setText(f"{d.get('fee_due', 0):.2f}")
            van_current_lbl.setText(f"{d.get('van_due', 0):.2f}")
            school_payable_lbl.setText(f"{d.get('school_payable', 0):.2f}")
            van_payable_lbl.setText(f"{d.get('van_payable', 0):.2f}")
            total_payable_lbl.setText(f"{d.get('total', 0):.2f}")
            year_lbl.setText(d.get("current_year_label") or "—")
            if pay_pending_badge is not None:
                pay_pending_badge.setText(f"Pending fees\n₹{pending_fees(d):.2f}")
            if pay_school_current_badge is not None:
                pay_school_current_badge.setText(
                    f"School fees due (current year)\n₹{float(d.get('fee_due', 0) or 0):.2f}"
                )
            if pay_van_current_badge is not None:
                pay_van_current_badge.setText(
                    f"Van fees due (current year)\n₹{float(d.get('van_due', 0) or 0):.2f}"
                )
            if pay_total_badge is not None:
                pay_total_badge.setText(f"Total payable\n₹{float(d.get('total', 0) or 0):.2f}")
                t = theme.current_tokens()
                total_amt = float(d.get("total", 0) or 0)
                badge_color = t.danger if total_amt > 0.01 else t.success
                pay_total_badge.setStyleSheet(
                    f"background: {t.bg_section_header}; color: {badge_color}; border: 1px solid {t.border}; "
                    "border-radius: 10px; padding: 8px 10px; font-weight: 700;"
                )
            if st is not None:
                joining_lbl.setText(_format_joining_date(st))
            if pay_pending_fees_lbl is not None:
                pay_pending_fees_lbl.setText(f"{pending_fees(d):.2f}")
                pay_school_current_lbl.setText(f"{d.get('fee_due', 0):.2f}")
                pay_van_current_lbl.setText(f"{d.get('van_due', 0):.2f}")

        if show_payment_ui:
            payment_box = QGroupBox("Payment Details")
            payment_layout = QFormLayout(payment_box)
            payment_layout.setHorizontalSpacing(14)
            payment_layout.setVerticalSpacing(8)
            pay_pending_fees_lbl = QLabel(f"{pending_fees(due_init):.2f}")
            pay_school_current_lbl = QLabel(f"{due_init.get('fee_due', 0):.2f}")
            pay_van_current_lbl = QLabel(f"{due_init.get('van_due', 0):.2f}")
            popup_school_pay = QLineEdit()
            popup_school_pay.setPlaceholderText("0.00")
            popup_school_pay.setClearButtonEnabled(True)
            popup_van_pay = QLineEdit()
            popup_van_pay.setPlaceholderText("0.00")
            popup_van_pay.setClearButtonEnabled(True)
            popup_discount = QLineEdit()
            popup_discount.setPlaceholderText("0.00")
            popup_discount.setClearButtonEnabled(True)
            popup_payment_date = QDateEdit(QDate.currentDate())
            popup_payment_date.setCalendarPopup(True)
            popup_payment_date.setDisplayFormat("dd/MM/yyyy")
            popup_payment_date.setMaximumDate(QDate.currentDate())
            popup_mode = QLineEdit("cash")
            popup_mode.setPlaceholderText("cash / upi / card")
            popup_mode.setClearButtonEnabled(True)
            payment_layout.addRow("Pending fees", pay_pending_fees_lbl)
            payment_layout.addRow("School fees due (current year)", pay_school_current_lbl)
            payment_layout.addRow("Van fees due (current year)", pay_van_current_lbl)
            payment_layout.addRow("School fee payment", popup_school_pay)
            payment_layout.addRow("Van fee payment", popup_van_pay)
            payment_layout.addRow("Discount", popup_discount)
            payment_layout.addRow("Date of payment", popup_payment_date)
            payment_layout.addRow("Mode", popup_mode)
            content_layout.addWidget(payment_box)

        _apply_due_breakdown(due_init, student)
        content_layout.addStretch(1)
        content_scroll.setWidget(content)
        layout.addWidget(content_scroll, 1)

        collect_btn = None
        print_receipt_btn = None
        if show_payment_ui:
            collect_btn = QPushButton("Collect Payment")
            print_receipt_btn = QPushButton("Print Receipt")
            close_pay_btn = QPushButton("Close")
            for action_btn in (collect_btn, print_receipt_btn, close_pay_btn):
                style_fee_action_button(action_btn)
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
            for dialog_btn in buttons.buttons():
                style_fee_action_button(dialog_btn)
            layout.addWidget(buttons)
            buttons.rejected.connect(dialog.reject)

        def _refresh_read_only_student_widgets(s):
            if not student_fields_editable and s is not None:
                heading.setText(f"{s.full_name} ({s.student_id})")
                ro_student_id.setText(str(s.student_id or "-"))
                ro_name.setText(str(s.full_name or "-"))
                if ro_gender is not None:
                    ro_gender.setText(self._gender_display(getattr(s, "gender", None)) or "-")
                if ro_father_name is not None:
                    ro_father_name.setText(
                        str(getattr(s, "father_name", None) or getattr(s, "guardian_name", None) or "-")
                    )
                if ro_mother_name is not None:
                    ro_mother_name.setText(str(getattr(s, "mother_name", None) or "-"))
                ro_class.setText(str(s.class_name or "-"))
                ro_section.setText(str(s.section or "-"))
                if ro_mobile_1 is not None:
                    ro_mobile_1.setText(str(getattr(s, "mobile_number_1", None) or s.phone or "-"))
                if ro_mobile_2 is not None:
                    ro_mobile_2.setText(str(getattr(s, "mobile_number_2", None) or "-"))
                if ro_dob is not None:
                    dob_value = getattr(s, "date_of_birth", None)
                    if isinstance(dob_value, datetime):
                        ro_dob.setText(dob_value.strftime("%d/%m/%Y"))
                    elif isinstance(dob_value, date):
                        ro_dob.setText(dob_value.strftime("%d/%m/%Y"))
                    else:
                        ro_dob.setText(str(dob_value or "-"))
                if ro_caste is not None:
                    ro_caste.setText(str(getattr(s, "caste", None) or "-"))
                if ro_aadhaar is not None:
                    ro_aadhaar.setText(str(getattr(s, "aadhaar", None) or "-"))
                ro_village.setText(str(getattr(s, "village", None) or "-"))
                if ro_transport is not None:
                    tm2 = (getattr(s, "transport_mode", None) or "van").strip().lower()
                    ro_transport.setText("Own transport" if tm2 == "own" else "Van transport")
                ro_status.setText(str(s.status or "-"))
                if lbl_van_fees is not None:
                    lbl_van_fees.setText(f"{float(getattr(s, 'van_fees', 0) or 0):.2f}")
                if lbl_school_fees is not None:
                    lbl_school_fees.setText(f"{float(getattr(s, 'school_fees', 0) or 0):.2f}")
                d = self.payment_service.get_student_due_breakdown(s.student_id)
                _apply_due_breakdown(d, s)
                lbl_created.setText(str(s.created_at or "-"))

        def on_save():
            if not edit_student_id.text().strip():
                theme.message_warning(dialog, "Validation", "Student ID is required.")
                return
            if not edit_name.text().strip():
                theme.message_warning(dialog, "Validation", "Name is required.")
                return
            if not edit_gender.currentText().strip():
                theme.message_warning(dialog, "Validation", "Gender is required.")
                return
            if not edit_father_name.text().strip():
                theme.message_warning(dialog, "Validation", "Father name is required.")
                return
            if not edit_class.currentText().strip():
                theme.message_warning(dialog, "Validation", "Class is required.")
                return
            if not edit_section.currentText().strip():
                theme.message_warning(dialog, "Validation", "Section is required.")
                return
            if not edit_village.currentText().strip():
                theme.message_warning(dialog, "Validation", "Village is required.")
                return
            if not (edit_transport.currentData() or edit_transport.currentText()).strip():
                theme.message_warning(dialog, "Validation", "Transport is required.")
                return
            mobile_1_error = phone_validation_message(edit_mobile_1.text())
            if mobile_1_error:
                theme.message_warning(
                    dialog,
                    "Validation",
                    mobile_1_error.replace("Phone", "Mobile number 1"),
                )
                return
            mobile_2_text = (edit_mobile_2.text() or "").strip()
            if mobile_2_text:
                mobile_2_error = phone_validation_message(mobile_2_text)
                if mobile_2_error:
                    theme.message_warning(dialog, "Validation", mobile_2_error.replace("Phone", "Mobile number 2"))
                    return
            aadhaar_text = normalize_phone_text((edit_aadhaar.text() or "").strip())
            if aadhaar_text and len(aadhaar_text) != 12:
                theme.message_warning(dialog, "Validation", "Aadhaar must be exactly 12 digits.")
                return
            try:
                updated = self.student_service.update_student(
                    student,
                    edit_student_id.text(),
                    edit_name.text(),
                    edit_class.currentText(),
                    edit_section.currentText(),
                    edit_mobile_1.text(),
                    edit_village.currentText(),
                    edit_father_name.text(),
                    edit_status.currentText(),
                    transport_mode=edit_transport.currentData() or "van",
                    village_fee_service=self.village_van_fee_service,
                    class_fee_service=self.class_fee_service,
                    gender=edit_gender.currentText(),
                    father_name=edit_father_name.text(),
                    mother_name=edit_mother_name.text(),
                    mobile_number_1=edit_mobile_1.text(),
                    mobile_number_2=edit_mobile_2.text(),
                    date_of_birth=edit_dob.text(),
                    caste=edit_caste.text(),
                    aadhaar=edit_aadhaar.text(),
                )
                self.selected_student = updated
                self._invalidate_payment_student_cache()
                self.perform_search(reset_page=True)
                self._load_report_filter_values()
                theme.message_information(self, "Student updated", f"Student {updated.full_name} ({updated.student_id}) updated successfully.")
                heading.setText(f"{updated.full_name} ({updated.student_id})")
                lbl_van_fees_editable.setText(f"{float(updated.van_fees):.2f}")
                if lbl_school_fees_editable is not None:
                    lbl_school_fees_editable.setText(f"{float(updated.school_fees):.2f}")
                d = self.payment_service.get_student_due_breakdown(updated.student_id)
                _apply_due_breakdown(d, updated)
            except ValueError as e:
                theme.message_warning(dialog, "Validation", str(e))
            except IntegrityError:
                self.session.rollback()
                theme.message_warning(
                    dialog,
                    "Duplicate value",
                    "Student ID, mobile number 1, mobile number 2, or aadhaar already exists. Please use unique values.",
                )
            except Exception as e:
                self.session.rollback()
                theme.message_critical(dialog, "Update error", str(e))

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
            d = self.payment_service.get_student_due_breakdown(student.student_id)
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
                theme.message_information(dialog, "Payment saved", f"Reference: {payment.reference_no}")
                _finalize_after_payment_saved(pay_date)
            except Exception as e:
                theme.message_critical(dialog, "Payment error", str(e))

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
                theme.message_critical(dialog, "Payment error", str(e))
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
                        guardian_name=str(getattr(student, "father_name", None) or student.guardian_name or ""),
                        school_fees_paid=school_amt,
                        van_fees_paid=van_amt,
                        discount=disc_amt,
                        receipt_no=payment.reference_no,
                        generated_at=datetime.now(),
                    )
                    pdf_note = f"\n\nReceipt saved to:\n{path}"
                except Exception as e:
                    theme.message_warning(
                        dialog,
                        "Receipt file error",
                        f"Payment was saved (Reference: {payment.reference_no}) but the PDF could not be written:\n{e}",
                    )
                    _finalize_after_payment_saved(pay_date)
                    return
            else:
                pdf_note = "\n\nNo PDF was saved (save dialog cancelled)."

            theme.message_information(
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
        self._animate_widget_fade(content_scroll, start=0.84, duration=210)
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
        self._run_student_search_now(reset_page=True)

    def _update_search_sort_indicator(self) -> None:
        header = self.student_table.horizontalHeader()
        col = _SEARCH_SORTABLE_COLUMNS.get(self._search_sort_column, 0)
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
        clear_data_table_selection(getattr(self, "student_table", None))
        self._run_student_search_now(reset_page=True)

    def on_student_search_basis_changed(self, _=None):
        basis = self.search_by.currentText() if hasattr(self, "search_by") else "Name"
        self.search_input.setPlaceholderText(SEARCH_PLACEHOLDERS.get(basis, "Enter search text"))
        self._run_student_search_now(reset_page=True)

    def _student_matches_search_basis(self, student, basis: str, q: str) -> bool:
        return student_matches_search(student, basis, q)

    def _schedule_report_search(self) -> None:
        if hasattr(self, "_report_search_timer"):
            self._report_search_timer.start()

    def _on_report_search_basis_changed(self, _=None) -> None:
        basis = self.report_search_by.currentText() if hasattr(self, "report_search_by") else "Name"
        self.report_student_input.setPlaceholderText(
            SEARCH_PLACEHOLDERS.get(basis, "Enter search text")
        )
        self.load_defaulters(reset_page=True)

    def _on_report_refresh_clicked(self) -> None:
        if hasattr(self, "report_student_input"):
            self.report_student_input.blockSignals(True)
            try:
                self.report_student_input.clear()
            finally:
                self.report_student_input.blockSignals(False)
        self.load_defaulters(reset_page=True)

    def _collect_filtered_students(self):
        search_text = (self.search_input.text() or "").strip()
        search_basis = self.search_by.currentText() if hasattr(self, "search_by") else "Name"
        self._ensure_payment_students_loaded()
        students = self._all_payment_students or []
        if search_text:
            q = search_text.lower()
            return [s for s in students if self._student_matches_search_basis(s, search_basis, q)]
        return list(students)

    def _fee_maps_for_ids(self, student_ids: list[str]) -> dict:
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
            page_maps = self._fee_maps_for_ids([s.student_id for s in students])
            summaries = page_maps["summaries"]
            van_summaries = page_maps["van_summaries"]
            due_map = page_maps["due_map"]
            discount_map = page_maps["discount_map"]
        self.student_table.setUpdatesEnabled(False)
        try:
            self.student_table.setRowCount(len(students))
            danger = theme.current_tokens().danger
            for i, s in enumerate(students):
                summary = summaries.get(s.student_id, {"fee_paid": 0.0, "fee_due": 0.0, "total_fees": 0.0})
                van_s = van_summaries.get(s.student_id, {"van_paid": 0.0, "van_due": 0.0})
                due = due_map.get(
                    s.student_id,
                    {
                        "pending_fees": 0.0,
                        "van_due": 0.0,
                        "fee_due": 0.0,
                        "total": 0.0,
                    },
                )
                disc = float(discount_map.get(s.student_id, 0.0) or 0.0)
                v_text = str(getattr(s, "village", None) or "")
                dob_value = getattr(s, "date_of_birth", None)
                if isinstance(dob_value, datetime):
                    dob_text = dob_value.strftime("%d/%m/%Y")
                elif isinstance(dob_value, date):
                    dob_text = dob_value.strftime("%d/%m/%Y")
                else:
                    dob_text = str(dob_value or "")
                row_cells = [
                    s.student_id,
                    s.full_name,
                    self._gender_display(getattr(s, "gender", None)),
                    str(getattr(s, "father_name", None) or getattr(s, "guardian_name", None) or ""),
                    str(getattr(s, "mother_name", None) or ""),
                    str(s.class_name),
                    str(s.section),
                    str(getattr(s, "mobile_number_1", None) or s.phone or ""),
                    str(getattr(s, "mobile_number_2", None) or ""),
                    dob_text,
                    str(getattr(s, "caste", None) or ""),
                    str(getattr(s, "aadhaar", None) or ""),
                    v_text,
                    s.status,
                    f"{float(getattr(s, 'van_fees', 0) or 0):.2f}",
                    f"{van_s['van_paid']:.2f}",
                    f"{due['van_due']:.2f}",
                    f"{float(getattr(s, 'school_fees', 0) or 0):.2f}",
                    f"{summary['fee_paid']:.2f}",
                    f"{disc:.2f}",
                    f"{pending_fees(due):.2f}",
                    f"{due['fee_due']:.2f}",
                    f"{due.get('school_payable', 0):.2f}",
                    f"{due['total']:.2f}",
                ]
                for col, text in enumerate(row_cells):
                    self.student_table.setItem(
                        i, col, table_item(text, bold=(col in (0, 1)))
                    )
                total_due = float(due.get("total", 0) or 0)
                if total_due > 0.01:
                    due_item = self.student_table.item(i, len(_SEARCH_TABLE_HEADERS) - 1)
                    if due_item:
                        due_item.setForeground(QColor(danger))
        finally:
            self.student_table.setUpdatesEnabled(True)
        fit_table_columns_to_contents(self.student_table)
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
        s=self.session.get(Student,str(item.text()))
        if not s: return
        self.selected_student = s
        d = self.payment_service.get_student_due_breakdown(s.student_id)
        self.student_info.setText(
            f"Selected: {s.full_name} ({s.student_id}) — {self._format_fee_due_lines(d)}"
        )

    def add_faculty(self) -> None:
        page = getattr(self, "_add_faculty_page", None)
        if page is not None:
            errors = page.form_validation_errors()
            if errors:
                if len(errors) == 1:
                    theme.message_warning(self, "Validation", errors[0])
                else:
                    theme.message_warning(
                        self,
                        "Validation",
                        "\n".join(f"• {msg}" for msg in errors),
                    )
                return
        try:
            faculty_name = self.add_faculty_name.text().strip()
            faculty_type = str(self.add_faculty_type.currentData() or "Teaching")
            role = self.add_faculty_role.text().strip()
            monthly_salary = float((self.add_faculty_monthly_salary.text() or "").strip() or 0.0)
            working_days = int(float((self.add_faculty_default_working_days.text() or "").strip() or 26))
            is_active = bool(self.add_faculty_status.currentData())
            row = self.expense_service.assign_faculty_salary(
                faculty_name,
                monthly_salary,
                faculty_type=faculty_type,
                role=role,
                default_working_days=working_days,
                is_active=is_active,
            )
            self.add_faculty_name.clear()
            self.add_faculty_role.clear()
            self.add_faculty_monthly_salary.clear()
            if page is not None:
                page.sync_default_working_days_current_month()
            else:
                today = date.today()
                self.add_faculty_default_working_days.setText(
                    str(self._default_working_days_for_month(today.year, today.month))
                )
            self.add_faculty_type.setCurrentIndex(0)
            self.add_faculty_status.setCurrentIndex(0)
            self._refresh_salary_faculty_options()
            self._refresh_salary_assignments_table(reset_page=True)
            self._refresh_salary_history_table()
            theme.message_information(
                self,
                "Faculty saved",
                f"Faculty {row.faculty_name} has been saved successfully.",
            )
        except ValueError as e:
            theme.message_warning(self, "Invalid faculty data", str(e))
        except Exception as e:
            self.session.rollback()
            theme.message_critical(self, "Add faculty error", str(e))

    def add_student(self):
        page = getattr(self, "_add_student_page", None)
        if page is not None:
            errors = page.form_validation_errors()
            if errors:
                if len(errors) == 1:
                    theme.message_warning(self, "Validation", errors[0])
                else:
                    theme.message_warning(
                        self,
                        "Validation",
                        "\n".join(f"• {msg}" for msg in errors),
                    )
                return
        try:
            optional = page.optional_fields_for_submit() if page is not None else {}
            st = self.student_service.create_student(
                self.add_student_id.text(),
                self.add_student_name.text(),
                self.add_student_class.currentText(),
                self.add_student_section.currentText(),
                self.add_student_mobile_number_1.text(),
                self.add_student_village.currentText(),
                self.add_student_father_name.text(),
                optional.get("status", self.add_student_status.currentText()),
                transport_mode=self.add_student_transport.currentData() or "van",
                village_fee_service=self.village_van_fee_service,
                class_fee_service=self.class_fee_service,
                gender=self.add_student_gender.currentText(),
                father_name=self.add_student_father_name.text(),
                mother_name=optional.get("mother_name", self.add_student_mother_name.text()),
                mobile_number_1=self.add_student_mobile_number_1.text(),
                mobile_number_2=optional.get("mobile_number_2", self.add_student_mobile_number_2.text()),
                date_of_birth=optional.get("date_of_birth", self.add_student_date_of_birth.text()),
                caste=optional.get("caste", self.add_student_caste.text()),
                aadhaar=optional.get("aadhaar", self.add_student_aadhaar.text()),
            )
            self.add_student_id.clear()
            self.add_student_name.clear()
            self.add_student_gender.setCurrentIndex(0)
            self.add_student_father_name.clear()
            self.add_student_mother_name.clear()
            self.add_student_class.setCurrentIndex(FIXED_CLASS_KEYS.index("1"))
            self.add_student_section.setCurrentIndex(0)
            self.add_student_mobile_number_1.clear()
            self.add_student_mobile_number_2.clear()
            self.add_student_date_of_birth.clear()
            self.add_student_caste.clear()
            self.add_student_aadhaar.clear()
            self.add_student_village.setCurrentIndex(0)
            self.add_student_transport.setCurrentIndex(0)
            self.add_student_status.setCurrentIndex(0)
            self._load_report_filter_values()
            self._invalidate_payment_student_cache()
            self.perform_search(reset_page=True)
            theme.message_information(self, "Student added", f"Student {st.full_name} ({st.student_id}) added successfully.")
        except ValueError as e:
            theme.message_warning(self, "Validation", str(e))
        except IntegrityError:
            self.session.rollback()
            theme.message_warning(
                self,
                "Duplicate value",
                "Student ID, mobile number 1, mobile number 2, or aadhaar already exists. Please use unique values.",
            )
        except Exception as e:
            self.session.rollback()
            theme.message_critical(self, "Add student error", str(e))
    def load_defaulters(self, reset_page: bool = True):
        selected_class = self.report_class.currentData()
        selected_section = self.report_section.currentData()
        fee_status = self.report_fee_filter.currentData()
        self._report_fee_status = str(fee_status) if fee_status else None
        search_basis = (
            self.report_search_by.currentText()
            if hasattr(self, "report_search_by")
            else "Name"
        )
        self._report_defaulter_rows = self.report_service.get_fee_report_rows(
            fee_status=fee_status,
            student_query=self.report_student_input.text(),
            search_basis=search_basis,
            class_name=selected_class,
            section=selected_section,
        )
        amount_header = report_amount_column_label(self._report_fee_status)
        self.report_table.setHorizontalHeaderLabels(
            ["Student ID", "Name", "Class", "Section", amount_header]
        )
        if reset_page:
            self._report_page = 0
        self._render_report_page()

    def _render_report_page(self):
        rows = slice_page(self._report_defaulter_rows, self._report_page)
        self.report_table.setRowCount(len(rows))
        paid_filter = self._report_fee_status == FEE_FILTER_PAID
        for i, r in enumerate(rows):
            self.report_table.setItem(i, 0, QTableWidgetItem(str(r.student_id)))
            self.report_table.setItem(i, 1, QTableWidgetItem(str(r.full_name)))
            self.report_table.setItem(i, 2, QTableWidgetItem(str(r.class_name)))
            self.report_table.setItem(i, 3, QTableWidgetItem(str(r.section)))
            if paid_filter:
                amount_text = "Paid"
            else:
                amount_text = f"{float(r.amount):.2f}"
            self.report_table.setItem(i, 4, QTableWidgetItem(amount_text))
        if hasattr(self, "_report_pagination"):
            self._report_pagination.update_state(self._report_page, len(self._report_defaulter_rows))

    def _report_change_page(self, delta: int):
        new_page = self._report_page + delta
        if new_page < 0 or new_page >= page_count(len(self._report_defaulter_rows)):
            return
        self._report_page = new_page
        self._render_report_page()

    def _rows(self):
        paid_filter = self._report_fee_status == FEE_FILTER_PAID
        out = []
        for r in self._report_defaulter_rows:
            if paid_filter:
                amount_text = "Paid"
            else:
                amount_text = f"{float(r.amount):.2f}"
            out.append(
                {
                    "student_id": str(r.student_id),
                    "name": str(r.full_name),
                    "class": str(r.class_name),
                    "section": str(r.section),
                    "amount": amount_text,
                }
            )
        return out

    def _report_export_headers(self) -> list[str]:
        amount_header = report_amount_column_label(self._report_fee_status or "")
        return ["Student ID", "Name", "Class", "Section", amount_header]

    def _report_export_title(self) -> str:
        if not self._report_fee_status:
            return "All Students Report"
        labels = {
            FEE_FILTER_PENDING_DUE: "Pending Fees Due Report",
            FEE_FILTER_CURRENT_YEAR: "Fees Due (Current Year) Report",
            FEE_FILTER_PAID: "Fees Paid Report",
        }
        return labels.get(self._report_fee_status, "Fee Report")

    def export_excel(self):
        if not self._report_defaulter_rows:
            theme.message_warning(self, "No data", "Load a report before exporting.")
            return
        p, _ = QFileDialog.getSaveFileName(self, "Save Excel", "fee_report.xlsx", "Excel Files (*.xlsx)")
        if not p:
            return
        from backend.reports.excel_export import ExcelExporter

        ExcelExporter.export_rows(self._rows(), Path(p))
        theme.message_information(self, "Exported", f"Excel report saved to {p}")

    def export_pdf(self):
        if not self._report_defaulter_rows:
            theme.message_warning(self, "No data", "Load a report before exporting.")
            return
        p, _ = QFileDialog.getSaveFileName(self, "Save PDF", "fee_report.pdf", "PDF Files (*.pdf)")
        if not p:
            return
        from backend.reports.pdf_export import PdfExporter

        rows = self._rows()
        headers = self._report_export_headers()
        table = [[r["student_id"], r["name"], r["class"], r["section"], r["amount"]] for r in rows]
        PdfExporter.export_simple_table(
            self._report_export_title(),
            headers,
            table,
            Path(p),
        )
        theme.message_information(self, "Exported", f"PDF report saved to {p}")
    def create_backup(self):
        p=self.backup_service.create_backup(); self.backup_status.setText(f"Backup created: {p}")
    def restore_backup(self):
        p,_=QFileDialog.getOpenFileName(self,"Choose backup","","DB Files (*.db *.sqlite *.sqlite3)")
        if not p: return
        self.backup_service.restore_backup(Path(p)); self.backup_status.setText(f"Backup restored from: {p}")
