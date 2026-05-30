"""Student Details view with richer analytics and activity cards."""

from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from frontend.ui.edudash_widgets import CardTitleBar, GradientProfileCard, SurfaceCard
from frontend.ui.table_style import style_fee_action_button
from backend.core.fee_due_display import pending_fees
from frontend.ui import theme


def _money(value: float) -> str:
    return f"₹{float(value or 0.0):,.2f}"


class StudentDetailsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._running_animations: list[QPropertyAnimation] = []
        self._stat_values: list[QLabel] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        # Left search/list panel
        left = SurfaceCard()
        left.setMinimumWidth(460)
        left.setMaximumWidth(560)
        left.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        ll = left.body
        ll.setSpacing(14)

        title = QLabel("Find students")
        title.setProperty("role", "section-title")
        title_hint = QLabel("Search and pick a student to preview profile details.")
        title_hint.setProperty("role", "muted")
        title_hint.setWordWrap(True)
        ll.addWidget(title)
        ll.addWidget(title_hint)

        tool = QHBoxLayout()
        tool.setSpacing(8)
        self.refresh_btn = QPushButton("Refresh")
        tool.addWidget(self.refresh_btn)
        tool.addWidget(QLabel("Search by"))
        self.search_by = QComboBox()
        self.search_by.addItems(
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
        self.search_by.setCurrentIndex(1)
        tool.addWidget(self.search_by, 1)
        ll.addLayout(tool)

        self.student_search = QLineEdit()
        self.student_search.setPlaceholderText("Enter student name")
        self.student_search.setClearButtonEnabled(True)
        ll.addWidget(self.student_search)

        meta_row = QHBoxLayout()
        self.match_count_label = QLabel("0 students match")
        self.match_count_label.setProperty("role", "muted")
        self._selection_hint = QLabel("Select a student from the list")
        self._selection_hint.setProperty("role", "hint")
        meta_row.addWidget(self.match_count_label)
        meta_row.addStretch(1)
        meta_row.addWidget(self._selection_hint)
        ll.addLayout(meta_row)

        filters = QHBoxLayout()
        filters.setSpacing(14)
        self.filter_active_only = QCheckBox("Active only")
        self.filter_outstanding_only = QCheckBox("Outstanding only")
        filters.addWidget(self.filter_active_only)
        filters.addWidget(self.filter_outstanding_only)
        filters.addStretch(1)
        ll.addLayout(filters)

        self.student_results = QListWidget()
        self.student_results.setSpacing(4)
        self._refresh_results_style()
        ll.addWidget(self.student_results, 1)

        self.pagination_host = QWidget()
        self.pagination_layout = QHBoxLayout(self.pagination_host)
        self.pagination_layout.setContentsMargins(0, 8, 0, 0)
        self.pagination_layout.setSpacing(8)
        ll.addWidget(self.pagination_host)
        root.addWidget(left, 6)

        # Right detail panel (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._detail_body = QWidget()
        self._detail_body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        dl = QVBoxLayout(self._detail_body)
        dl.setContentsMargins(0, 0, 0, 4)
        dl.setSpacing(16)

        self.detail_heading = QLabel("No student selected")
        self.detail_heading.setProperty("role", "section-title")
        self.hint_label = QLabel("Select a student from the left panel to view details.")
        self.hint_label.setProperty("role", "muted")
        self.hint_label.setWordWrap(True)
        dl.addWidget(self.detail_heading)
        dl.addWidget(self.hint_label)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)
        self._profile_card = GradientProfileCard("—", "—", "—", show_action=False)
        self._profile_card.setFixedWidth(306)
        top_row.addWidget(self._profile_card)

        overview_card = SurfaceCard()
        overview_card.body.addWidget(CardTitleBar("Student overview"))
        overview_form = QFormLayout()
        overview_form.setHorizontalSpacing(16)
        overview_form.setVerticalSpacing(8)
        self.lbl_student_id = QLabel("—")
        self.lbl_name = QLabel("—")
        self.lbl_class = QLabel("—")
        self.lbl_joining = QLabel("—")
        self._status_badge = QLabel("—")
        self._status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._status_badge.setMinimumWidth(84)
        self._status_badge.setMaximumWidth(124)
        overview_form.addRow("Roll number", self.lbl_student_id)
        overview_form.addRow("Student name", self.lbl_name)
        overview_form.addRow("Class / section", self.lbl_class)
        overview_form.addRow("Current status", self._status_badge)
        overview_form.addRow("Joined on", self.lbl_joining)
        overview_card.body.addLayout(overview_form)
        top_row.addWidget(overview_card, 1)
        top_row.setStretch(0, 4)
        top_row.setStretch(1, 6)
        dl.addLayout(top_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.btn_edit = QPushButton("Edit profile")
        style_fee_action_button(self.btn_edit)
        self.btn_edit.setEnabled(False)
        btn_row.addWidget(self.btn_edit)
        btn_row.addStretch(1)
        dl.addLayout(btn_row)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        card_total, self.lbl_stat_total = self._create_stat_card("Total payable")
        card_school, self.lbl_stat_school = self._create_stat_card("School payable")
        card_van, self.lbl_stat_van = self._create_stat_card("Van payable")
        card_year, self.lbl_stat_year = self._create_stat_card("Academic year")
        stats_row.addWidget(card_total, 1)
        stats_row.addWidget(card_school, 1)
        stats_row.addWidget(card_van, 1)
        stats_row.addWidget(card_year, 1)
        dl.addLayout(stats_row)

        middle_row = QHBoxLayout()
        middle_row.setSpacing(14)

        contact_card = SurfaceCard()
        contact_card.body.addWidget(CardTitleBar("Contact details"))
        contact_form = QFormLayout()
        contact_form.setHorizontalSpacing(16)
        contact_form.setVerticalSpacing(8)
        self.lbl_phone = QLabel("—")
        self.lbl_mobile_2 = QLabel("—")
        self.lbl_village = QLabel("—")
        self.lbl_transport = QLabel("—")
        self.lbl_gender = QLabel("—")
        self.lbl_father_name = QLabel("—")
        self.lbl_mother_name = QLabel("—")
        self.lbl_date_of_birth = QLabel("—")
        self.lbl_caste = QLabel("—")
        self.lbl_aadhaar = QLabel("—")
        contact_form.addRow("Mobile number 1", self.lbl_phone)
        contact_form.addRow("Mobile number 2", self.lbl_mobile_2)
        contact_form.addRow("Village", self.lbl_village)
        contact_form.addRow("Transport", self.lbl_transport)
        contact_form.addRow("Gender", self.lbl_gender)
        contact_form.addRow("Father name", self.lbl_father_name)
        contact_form.addRow("Mother name", self.lbl_mother_name)
        contact_form.addRow("Date of birth", self.lbl_date_of_birth)
        contact_form.addRow("Caste", self.lbl_caste)
        contact_form.addRow("Aadhaar", self.lbl_aadhaar)
        contact_card.body.addLayout(contact_form)
        middle_row.addWidget(contact_card, 1)

        fee_card = SurfaceCard()
        fee_card.body.addWidget(CardTitleBar("Fee summary"))
        fee_form = QFormLayout()
        fee_form.setHorizontalSpacing(16)
        fee_form.setVerticalSpacing(8)
        self.lbl_fee_year = QLabel("—")
        self.lbl_pending_fees = QLabel("—")
        self.lbl_school_current = QLabel("—")
        self.lbl_school_payable = QLabel("—")
        self.lbl_van_current = QLabel("—")
        self.lbl_van_payable = QLabel("—")
        self.lbl_total_payable = QLabel("—")
        fee_form.addRow("Academic year", self.lbl_fee_year)
        fee_form.addRow("Pending fees", self.lbl_pending_fees)
        fee_form.addRow("School due (current)", self.lbl_school_current)
        fee_form.addRow("School payable", self.lbl_school_payable)
        fee_form.addRow("Van due (current)", self.lbl_van_current)
        fee_form.addRow("Van payable", self.lbl_van_payable)
        fee_form.addRow("Total payable", self.lbl_total_payable)
        fee_card.body.addLayout(fee_form)
        middle_row.addWidget(fee_card, 1)
        dl.addLayout(middle_row)

        activity_card = SurfaceCard()
        activity_card.body.addWidget(CardTitleBar("Recent payment activity"))
        self.recent_payments_list = QListWidget()
        self.recent_payments_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.recent_payments_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.recent_payments_list.setMinimumHeight(170)
        activity_card.body.addWidget(self.recent_payments_list)
        self.summary_title = QLabel("Select a student to view a profile summary.")
        self.summary_title.setProperty("role", "section-title")
        self.summary_title.setWordWrap(True)
        self.summary_text = QLabel("Payment behaviour and due insights will appear here.")
        self.summary_text.setProperty("role", "muted")
        self.summary_text.setWordWrap(True)
        self.summary_hint = QLabel("Tip: use Edit profile to update student records.")
        self.summary_hint.setProperty("role", "hint")
        self.summary_hint.setWordWrap(True)
        activity_card.body.addWidget(self.summary_title)
        activity_card.body.addWidget(self.summary_text)
        activity_card.body.addWidget(self.summary_hint)
        dl.addWidget(activity_card, 1)

        scroll.setWidget(self._detail_body)
        root.addWidget(scroll, 7)
        self.clear_detail()

    def _create_stat_card(self, title: str, *, register: bool = True) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("studentDetailStatCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)
        title_lbl = QLabel(title)
        title_lbl.setProperty("role", "muted")
        value_lbl = QLabel("—")
        value_lbl.setProperty("role", "section-title")
        lay.addWidget(title_lbl)
        lay.addWidget(value_lbl)
        if register:
            self._stat_values.append(value_lbl)
        return card, value_lbl

    def _style_status_badge(self, status_text: str) -> None:
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
        self._status_badge.setText(status_text or "—")
        self._status_badge.setStyleSheet(
            f"background: {bg}; color: {fg}; padding: 4px 10px; border-radius: 10px; font-weight: 700;"
        )

    def _style_payable_label(self, label: QLabel, amount: float) -> None:
        t = theme.current_tokens()
        color = t.danger if amount > 0.01 else t.success
        label.setStyleSheet(f"color: {color}; font-weight: 700; background: transparent;")

    def _animate_widget(self, widget: QWidget, *, start: float = 0.78, duration: int = 200) -> None:
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        effect.setOpacity(start)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(duration)
        animation.setStartValue(start)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(
            lambda a=animation: self._running_animations.remove(a) if a in self._running_animations else None
        )
        self._running_animations.append(animation)
        animation.start()

    def _refresh_results_style(self) -> None:
        t = theme.current_tokens()
        self.student_results.setStyleSheet(
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
                margin: 2px 2px;
                padding: 9px 10px;
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
        if hasattr(self, "recent_payments_list"):
            self.recent_payments_list.setStyleSheet(
                f"""
                QListWidget {{
                    background: {t.bg_surface};
                    color: {t.text_primary};
                    border: 1px solid {t.border};
                    border-radius: 10px;
                    padding: 6px;
                }}
                QListWidget::item {{
                    border: 1px solid transparent;
                    border-radius: 6px;
                    padding: 7px 8px;
                    margin: 1px 0;
                }}
                QListWidget::item:hover {{
                    background: {t.bg_hover};
                }}
                """
            )
        for card in self.findChildren(QFrame):
            if card.objectName() == "studentDetailStatCard":
                card.setStyleSheet(
                    f"background: {t.bg_surface}; border: 1px solid {t.border}; border-radius: 12px;"
                )

    def animate_results_refresh(self) -> None:
        self._animate_widget(self.student_results, start=0.72, duration=160)

    def refresh_theme(self) -> None:
        self._profile_card.refresh_theme()
        self._refresh_results_style()
        style_fee_action_button(self.btn_edit, width=self.btn_edit.width() if self.btn_edit.width() > 0 else None)
        self._style_status_badge(self._status_badge.text())
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

    @staticmethod
    def format_payment_date(value) -> str:
        if isinstance(value, datetime):
            return value.strftime("%d/%m/%Y")
        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")
        return str(value or "—")

    @staticmethod
    def format_gender(value) -> str:
        text = str(value or "").strip()
        lower = text.lower()
        if lower in ("male", "boy"):
            return "Male"
        if lower in ("female", "girl"):
            return "Female"
        return text or "—"

    def clear_detail(self) -> None:
        self._profile_card.set_student("No student selected", "—", "—")
        self.detail_heading.setText("No student selected")
        self.hint_label.setText("Select a student from the left panel to view details.")
        self.lbl_student_id.setText("—")
        self.lbl_name.setText("—")
        self.lbl_class.setText("—")
        self.lbl_joining.setText("—")
        self.lbl_phone.setText("—")
        self.lbl_mobile_2.setText("—")
        self.lbl_village.setText("—")
        self.lbl_transport.setText("—")
        self.lbl_gender.setText("—")
        self.lbl_father_name.setText("—")
        self.lbl_mother_name.setText("—")
        self.lbl_date_of_birth.setText("—")
        self.lbl_caste.setText("—")
        self.lbl_aadhaar.setText("—")
        self.lbl_stat_total.setText("—")
        self.lbl_stat_school.setText("—")
        self.lbl_stat_van.setText("—")
        self.lbl_stat_year.setText("—")
        self.lbl_fee_year.setText("—")
        self.lbl_pending_fees.setText("—")
        self.lbl_school_current.setText("—")
        self.lbl_school_payable.setText("—")
        self.lbl_van_current.setText("—")
        self.lbl_van_payable.setText("—")
        self.lbl_total_payable.setText("—")
        self._style_status_badge("—")
        self.summary_title.setText("Select a student to view a profile summary.")
        self.summary_text.setText("Payment behaviour and due insights will appear here.")
        self.summary_hint.setText("Tip: use Edit profile to update student records.")
        self.recent_payments_list.clear()
        self.recent_payments_list.addItem("No payment activity to display.")
        self.btn_edit.setEnabled(False)

    def show_detail(self, data: dict) -> None:
        student = data["student"]
        due = dict(data.get("due") or {})
        recent_payments = list(data.get("recent_payments") or [])
        class_name = str(student.class_name or "—")
        section = str(student.section or "").strip()
        class_section = f"{class_name}-{section}" if section else class_name
        status = str(student.status or "—")

        pending_total = pending_fees(due)
        school_current = float(due.get("fee_due", 0) or 0)
        school_payable = float(due.get("school_payable", 0) or 0)
        van_current = float(due.get("van_due", 0) or 0)
        van_payable = float(due.get("van_payable", 0) or 0)
        total_payable = float(due.get("total", school_payable + van_payable) or 0)
        year_label = str(due.get("current_year_label") or "—")

        self._profile_card.set_student(
            str(student.full_name or "—"),
            class_section,
            str(student.student_id or "—"),
        )
        self.detail_heading.setText(f"{student.full_name or 'Student'}")
        self.hint_label.setText("Profile, fee analytics, and recent payment activity.")

        self.lbl_student_id.setText(str(student.student_id or "—"))
        self.lbl_name.setText(str(student.full_name or "—"))
        self.lbl_class.setText(class_section)
        self.lbl_joining.setText(self.format_joining_date(getattr(student, "created_at", None)))
        self.lbl_phone.setText(
            str(getattr(student, "mobile_number_1", None) or getattr(student, "phone", None) or "—")
        )
        self.lbl_mobile_2.setText(str(getattr(student, "mobile_number_2", None) or "—"))
        self.lbl_village.setText(str(getattr(student, "village", None) or "—"))
        self.lbl_transport.setText(
            "Own transport"
            if str(getattr(student, "transport_mode", "van") or "van").lower() == "own"
            else "Van transport"
        )
        self.lbl_gender.setText(self.format_gender(getattr(student, "gender", None)))
        self.lbl_father_name.setText(
            str(getattr(student, "father_name", None) or getattr(student, "guardian_name", None) or "—")
        )
        self.lbl_mother_name.setText(str(getattr(student, "mother_name", None) or "—"))
        dob = getattr(student, "date_of_birth", None)
        if isinstance(dob, datetime):
            self.lbl_date_of_birth.setText(dob.strftime("%d/%m/%Y"))
        elif isinstance(dob, date):
            self.lbl_date_of_birth.setText(dob.strftime("%d/%m/%Y"))
        else:
            self.lbl_date_of_birth.setText(str(dob or "—"))
        self.lbl_caste.setText(str(getattr(student, "caste", None) or "—"))
        self.lbl_aadhaar.setText(str(getattr(student, "aadhaar", None) or "—"))

        self.lbl_fee_year.setText(year_label)
        self.lbl_pending_fees.setText(_money(pending_total))
        self.lbl_school_current.setText(_money(school_current))
        self.lbl_school_payable.setText(_money(school_payable))
        self.lbl_van_current.setText(_money(van_current))
        self.lbl_van_payable.setText(_money(van_payable))
        self.lbl_total_payable.setText(_money(total_payable))
        self._style_payable_label(self.lbl_school_payable, school_payable)
        self._style_payable_label(self.lbl_van_payable, van_payable)
        self._style_payable_label(self.lbl_total_payable, total_payable)

        self.lbl_stat_total.setText(_money(total_payable))
        self.lbl_stat_school.setText(_money(school_payable))
        self.lbl_stat_van.setText(_money(van_payable))
        self.lbl_stat_year.setText(year_label)

        if total_payable > 0.01:
            dominant = "school" if school_payable >= van_payable else "van"
            self.summary_title.setText(f"{student.full_name or 'Student'} - Outstanding {_money(total_payable)}")
            self.summary_text.setText(
                f"{status.title()} profile with pending dues. School payable: {_money(school_payable)} | "
                f"Van payable: {_money(van_payable)}. Highest contribution: {dominant} dues."
            )
        else:
            self.summary_title.setText(f"{student.full_name or 'Student'} - All dues cleared")
            self.summary_text.setText(
                "No pending amount at the moment. This student is currently fully paid for the tracked fee buckets."
            )
        self.summary_hint.setText(
            f"Joined on {self.lbl_joining.text()} • Transport: {self.lbl_transport.text()} • "
            "Use Edit profile to update personal and enrollment details."
        )

        self.recent_payments_list.clear()
        if recent_payments:
            for row in recent_payments[:8]:
                status_text = str(row.get("status") or "Paid")
                paid = float(row.get("amount", 0) or 0) - float(row.get("discount", 0) or 0)
                payment_line = (
                    f"{self.format_payment_date(row.get('payment_date'))}  •  {_money(paid)}  •  "
                    f"{str(row.get('mode') or '').title()}  •  Ref {str(row.get('reference_no') or '')}  •  {status_text}"
                )
                self.recent_payments_list.addItem(payment_line)
        else:
            self.recent_payments_list.addItem("No payment records found for this student.")

        self._style_status_badge(status)
        self.btn_edit.setEnabled(True)
        self._animate_widget(self._detail_body, start=0.82, duration=190)
