"""Student Details — EduDash split view with profile cards."""

from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from frontend.ui.edudash_widgets import CardTitleBar, GradientProfileCard, SurfaceCard
from frontend.ui.table_style import configure_data_table, table_item
from frontend.ui import theme
from frontend.ui.theme import style_primary as style_primary_button


class StudentDetailsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(20)

        # Left list panel
        left = SurfaceCard()
        left.setFixedWidth(360)
        ll = left.body
        tool = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        tool.addWidget(self.refresh_btn)
        tool.addWidget(QLabel("Search by"))
        self.search_by = QComboBox()
        self.search_by.addItems(
            ["Roll Number", "Name", "Phone", "Village", "Class-Section", "Status", "Guardian Name"]
        )
        self.search_by.setCurrentIndex(1)
        self.student_search = QLineEdit()
        self.student_search.setPlaceholderText("Enter student name")
        tool.addWidget(self.search_by, 1)
        ll.addLayout(tool)
        ll.addWidget(self.student_search)

        self.match_count_label = QLabel("0 students match")
        self.match_count_label.setProperty("role", "muted")
        ll.addWidget(self.match_count_label)

        filters = QHBoxLayout()
        self.filter_active_only = QCheckBox("Active only")
        self.filter_outstanding_only = QCheckBox("Outstanding only")
        filters.addWidget(self.filter_active_only)
        filters.addWidget(self.filter_outstanding_only)
        filters.addStretch(1)
        ll.addLayout(filters)

        self.student_results = QListWidget()
        theme.refresh_list_widget(self.student_results)
        ll.addWidget(self.student_results, 1)

        self.pagination_host = QWidget()
        self.pagination_layout = QHBoxLayout(self.pagination_host)
        self.pagination_layout.setContentsMargins(0, 8, 0, 0)
        ll.addWidget(self.pagination_host)
        root.addWidget(left)

        # Right detail scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        detail = QWidget()
        dl = QVBoxLayout(detail)
        dl.setSpacing(16)

        top_row = QHBoxLayout()
        self._profile_card = GradientProfileCard("—", "—", "—")
        self._profile_card.setFixedWidth(280)
        top_row.addWidget(self._profile_card)

        quick_col = QVBoxLayout()
        self._quick_stat_boxes: list[QLabel] = []
        for label, val in (
            ("Events", "—"),
            ("Notifications", "—"),
            ("Attendance", "—"),
        ):
            box = QLabel(f"{label}\n{val}")
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.setMinimumHeight(52)
            self._quick_stat_boxes.append(box)
            quick_col.addWidget(box)
        self._refresh_quick_stats()
        top_row.addLayout(quick_col, 1)
        dl.addLayout(top_row)

        fees_card = SurfaceCard()
        fees_card.body.addWidget(CardTitleBar("Fee snapshot"))
        fees_form = QFormLayout()
        self.lbl_academic_year = QLabel("—")
        self.lbl_school_pending = QLabel("—")
        self.lbl_van_pending = QLabel("—")
        self.lbl_school_due = QLabel("—")
        self.lbl_van_due = QLabel("—")
        self.lbl_school_payable = QLabel("—")
        self.lbl_van_payable = QLabel("—")
        self.lbl_total_due = QLabel("—")
        fees_form.addRow("Academic year", self.lbl_academic_year)
        fees_form.addRow("Pending school", self.lbl_school_pending)
        fees_form.addRow("Pending van", self.lbl_van_pending)
        fees_form.addRow("School due (year)", self.lbl_school_due)
        fees_form.addRow("Van due (year)", self.lbl_van_due)
        fees_form.addRow("Payable school", self.lbl_school_payable)
        fees_form.addRow("Payable van", self.lbl_van_payable)
        fees_form.addRow("Total payable", self.lbl_total_due)
        fees_card.body.addLayout(fees_form)
        dl.addWidget(fees_card)

        year_card = SurfaceCard()
        year_card.body.addWidget(CardTitleBar("Fees by academic year"))
        self.year_table = QTableWidget(0, 7)
        self.year_table.setHorizontalHeaderLabels(
            ["Year", "School tariff", "School paid", "School due", "Van tariff", "Van paid", "Van due"]
        )
        configure_data_table(self.year_table)
        year_card.body.addWidget(self.year_table)
        dl.addWidget(year_card)

        pay_card = SurfaceCard()
        pay_card.body.addWidget(CardTitleBar("Recent payments"))
        self.payments_table = QTableWidget(0, 5)
        self.payments_table.setHorizontalHeaderLabels(
            ["Date", "Reference", "Amount (₹)", "Discount (₹)", "Mode"]
        )
        configure_data_table(self.payments_table)
        pay_card.body.addWidget(self.payments_table)
        dl.addWidget(pay_card)

        btn_row = QHBoxLayout()
        self.btn_edit = QPushButton("Edit profile")
        self.btn_collect = QPushButton("Collect payment")
        style_primary_button(self.btn_collect)
        self.btn_edit.setEnabled(False)
        self.btn_collect.setEnabled(False)
        btn_row.addWidget(self.btn_edit)
        btn_row.addWidget(self.btn_collect)
        btn_row.addStretch(1)
        dl.addLayout(btn_row)
        dl.addStretch(1)

        scroll.setWidget(detail)
        root.addWidget(scroll, 1)

        # Legacy labels for compatibility
        self.detail_heading = QLabel()
        self.lbl_student_id = QLabel()
        self.lbl_name = QLabel()
        self.lbl_class = QLabel()
        self.lbl_phone = QLabel()
        self.lbl_village = QLabel()
        self.lbl_transport = QLabel()
        self.lbl_guardian = QLabel()
        self.lbl_status = QLabel()
        self.lbl_joining = QLabel()
        self.hint_label = QLabel()
        self.clear_detail()

    def _refresh_quick_stats(self) -> None:
        t = theme.current_tokens()
        for i, box in enumerate(self._quick_stat_boxes):
            bg = t.quick_stat_bgs[i] if i < len(t.quick_stat_bgs) else t.bg_section_header
            box.setStyleSheet(
                f"background: {bg}; border-radius: 10px; padding: 12px; "
                f"font-weight: 700; color: {t.quick_stat_text};"
            )

    def _style_total_due(self, total: float) -> None:
        t = theme.current_tokens()
        if total > 0.01:
            self.lbl_total_due.setStyleSheet(
                f"color: {t.danger}; font-weight: 700; background: transparent;"
            )
        else:
            self.lbl_total_due.setStyleSheet(
                f"color: {t.success}; font-weight: 700; background: transparent;"
            )

    def refresh_theme(self) -> None:
        self._refresh_quick_stats()
        self._profile_card.refresh_theme()
        theme.refresh_list_widget(self.student_results)
        configure_data_table(self.year_table)
        configure_data_table(self.payments_table)
        style_primary_button(self.btn_collect)
        try:
            total = float(self.lbl_total_due.text().replace(",", "") or 0)
            self._style_total_due(total)
        except ValueError:
            pass
        for bar in self.findChildren(CardTitleBar):
            bar.refresh_theme()

    @staticmethod
    def format_joining_date(created_at) -> str:
        if created_at is None:
            return "—"
        if isinstance(created_at, datetime):
            return created_at.strftime("%d/%m/%Y")
        if isinstance(created_at, date):
            return created_at.strftime("%d/%m/%Y")
        return str(created_at)

    def clear_detail(self) -> None:
        self._profile_card.set_student("No student selected", "—", "—")
        for lbl in (
            self.lbl_academic_year,
            self.lbl_school_pending,
            self.lbl_van_pending,
            self.lbl_school_due,
            self.lbl_van_due,
            self.lbl_school_payable,
            self.lbl_van_payable,
            self.lbl_total_due,
        ):
            lbl.setText("—")
        self.year_table.setRowCount(0)
        self.payments_table.setRowCount(0)
        self.btn_edit.setEnabled(False)
        self.btn_collect.setEnabled(False)

    def show_detail(self, data: dict) -> None:
        student = data["student"]
        due = data.get("due") or {}
        self._profile_card.set_student(
            str(student.full_name or "—"),
            str(student.class_name or "—"),
            str(student.student_id or "—"),
        )

        self.lbl_academic_year.setText(str(due.get("current_year_label") or "—"))
        self.lbl_school_pending.setText(f"{due.get('school_pending', 0):.2f}")
        self.lbl_van_pending.setText(f"{due.get('van_pending', 0):.2f}")
        self.lbl_school_due.setText(f"{due.get('fee_due', 0):.2f}")
        self.lbl_van_due.setText(f"{due.get('van_due', 0):.2f}")
        self.lbl_school_payable.setText(f"{due.get('school_payable', 0):.2f}")
        self.lbl_van_payable.setText(f"{due.get('van_payable', 0):.2f}")
        total = float(due.get("total", 0) or 0)
        self.lbl_total_due.setText(f"{total:.2f}")
        self._style_total_due(total)

        self.year_table.setRowCount(0)
        for row, yr in enumerate(data.get("yearly") or []):
            self.year_table.insertRow(row)
            label = yr.get("label") or ""
            if yr.get("is_current"):
                label = f"{label} (current)"
            cells = [
                label,
                f"{yr.get('school_tariff', 0):.2f}",
                f"{yr.get('school_paid', 0):.2f}",
                f"{yr.get('school_due', 0):.2f}",
                f"{yr.get('van_tariff', 0):.2f}",
                f"{yr.get('van_paid', 0):.2f}",
                f"{yr.get('van_due', 0):.2f}",
            ]
            for col, text in enumerate(cells):
                item = table_item(text)
                if col in (3, 6) and float(text) > 0.01:
                    item.setForeground(QColor(theme.current_tokens().danger))
                self.year_table.setItem(row, col, item)
        self.year_table.resizeColumnsToContents()

        self.payments_table.setRowCount(0)
        for row, p in enumerate(data.get("payments") or []):
            self.payments_table.insertRow(row)
            pd = p.get("payment_date")
            pd_str = pd.strftime("%d/%m/%Y") if hasattr(pd, "strftime") else str(pd or "")
            for col, text in enumerate([
                pd_str,
                str(p.get("reference_no") or ""),
                f"{float(p.get('amount', 0) or 0):.2f}",
                f"{float(p.get('discount', 0) or 0):.2f}",
                str(p.get("mode") or ""),
            ]):
                self.payments_table.setItem(row, col, table_item(text))
        self.payments_table.resizeColumnsToContents()
        self.btn_edit.setEnabled(True)
        self.btn_collect.setEnabled(True)
