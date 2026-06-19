"""Delete Member — remove students or faculty from the database."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from backend.core.fee_due_display import pending_fees
from backend.services.expense_service import ExpenseService
from backend.services.payment_service import PaymentService
from backend.services.student_service import StudentService
from frontend.ui import theme
from frontend.ui.edudash_widgets import FormField, SurfaceCard, wrap_page
from frontend.ui.member_search_field import FacultyMemberSearchField, StudentMemberSearchField
from frontend.ui.school_branding import breadcrumb_trail
from frontend.ui.segment_toggle import LOGIN_SEGMENT_WIDTH, SegmentToggle
from frontend.ui.table_style import style_fee_action_button

_FACULTY_INDEX = 1


def _picker_row(picker: QWidget, on_refresh) -> tuple[QWidget, QPushButton]:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    refresh_btn = QPushButton("Refresh")
    style_fee_action_button(refresh_btn)
    refresh_btn.clicked.connect(on_refresh)
    row.addWidget(refresh_btn)
    row.addWidget(picker, 1)
    host = QWidget()
    host.setLayout(row)
    return host, refresh_btn


class _MemberSummaryCard(SurfaceCard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._form = QFormLayout()
        self._form.setContentsMargins(0, 0, 0, 0)
        self._form.setSpacing(8)
        self._labels: dict[str, QLabel] = {}
        self._row_labels: dict[str, QLabel] = {}
        for key, title in (
            ("roll", "Roll number"),
            ("name", "Name"),
            ("class", "Class"),
            ("status", "Status"),
            ("pending", "Pending fees"),
            ("total", "Total due"),
            ("employee_id", "Employee ID"),
            ("category", "Category"),
        ):
            title_lbl = QLabel(title)
            title_lbl.setProperty("role", "field-label")
            value_lbl = QLabel("—")
            value_lbl.setWordWrap(True)
            self._labels[key] = value_lbl
            self._row_labels[key] = title_lbl
            self._form.addRow(title_lbl, value_lbl)
        self.body.addLayout(self._form)

    def set_student_summary(
        self,
        *,
        roll: str = "—",
        name: str = "—",
        class_text: str = "—",
        status: str = "—",
        pending: str = "—",
        total: str = "—",
    ) -> None:
        self._labels["roll"].setText(roll)
        self._labels["name"].setText(name)
        self._labels["class"].setText(class_text)
        self._labels["status"].setText(status)
        self._labels["pending"].setText(pending)
        self._labels["total"].setText(total)
        self._set_row_visible("employee_id", False)
        self._set_row_visible("category", False)
        self._set_row_visible("roll", True)
        self._set_row_visible("class", True)
        self._set_row_visible("pending", True)
        self._set_row_visible("total", True)

    def set_faculty_summary(
        self,
        *,
        employee_id: str = "—",
        name: str = "—",
        category: str = "—",
        status: str = "—",
    ) -> None:
        self._labels["employee_id"].setText(employee_id)
        self._labels["name"].setText(name)
        self._labels["category"].setText(category)
        self._labels["status"].setText(status)
        self._set_row_visible("roll", False)
        self._set_row_visible("class", False)
        self._set_row_visible("pending", False)
        self._set_row_visible("total", False)
        self._set_row_visible("employee_id", True)
        self._set_row_visible("category", True)

    def _set_row_visible(self, key: str, visible: bool) -> None:
        title_lbl = self._row_labels.get(key)
        value_lbl = self._labels.get(key)
        if title_lbl is not None:
            title_lbl.setVisible(visible)
        if value_lbl is not None:
            value_lbl.setVisible(visible)

    def show_student_layout(self) -> None:
        for key in ("roll", "name", "class", "status", "pending", "total"):
            self._set_row_visible(key, True)
        for key in ("employee_id", "category"):
            self._set_row_visible(key, False)

    def show_faculty_layout(self) -> None:
        for key in ("roll", "class", "pending", "total"):
            self._set_row_visible(key, False)
        for key in ("employee_id", "name", "category", "status"):
            self._set_row_visible(key, True)

    def clear_summary(self) -> None:
        for lbl in self._labels.values():
            lbl.setText("—")


def _style_danger_button(btn: QPushButton) -> None:
    t = theme.current_tokens()
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setMinimumHeight(44)
    btn.setStyleSheet(
        f"QPushButton {{ background: {t.danger}; color: #FFFFFF; border: none; "
        f"border-radius: 8px; font-weight: 700; padding: 10px 20px; }}"
        f"QPushButton:hover {{ background: #B91C1C; }}"
        f"QPushButton:disabled {{ background: {t.border_light}; color: {t.text_muted}; }}"
    )


class DeleteMemberPage(QWidget):
    """Admin page to permanently delete a student or faculty member."""

    def __init__(
        self,
        student_service: StudentService,
        expense_service: ExpenseService,
        payment_service: PaymentService,
        parent=None,
    ):
        super().__init__(parent)
        self._student_service = student_service
        self._expense_service = expense_service
        self._payment_service = payment_service

        body = QWidget()
        body.setObjectName("deleteMemberBody")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(20)

        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)
        self._mode_toggle = SegmentToggle(
            ("Delete Student", "Delete Faculty"),
            width=LOGIN_SEGMENT_WIDTH,
        )
        self._mode_toggle.selection_changed.connect(self._on_mode_changed)
        toggle_row.addWidget(self._mode_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        toggle_row.addStretch(1)
        body_lay.addLayout(toggle_row)
        body_lay.addSpacing(4)

        self._hint = QLabel(
            "Permanently removes the selected member and related records from the database. "
            "This action cannot be undone."
        )
        self._hint.setWordWrap(True)
        self._hint.setProperty("role", "hint")
        body_lay.addWidget(self._hint)

        self._stack = QStackedWidget()

        student_panel = QWidget()
        student_lay = QVBoxLayout(student_panel)
        student_lay.setContentsMargins(0, 0, 0, 0)
        student_lay.setSpacing(16)
        self._student_search = StudentMemberSearchField(
            student_service,
            placeholder="Select a student…",
        )
        student_picker_row, self._student_refresh_btn = _picker_row(
            self._student_search,
            self._on_student_refresh,
        )
        student_lay.addWidget(FormField("Student", student_picker_row, required=True))
        self._student_summary = _MemberSummaryCard()
        self._student_summary.show_student_layout()
        student_lay.addWidget(self._student_summary)
        self._student_search.textChanged.connect(self._on_student_selection_changed)
        self.delete_student_btn = QPushButton("Delete Student")
        _style_danger_button(self.delete_student_btn)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.delete_student_btn)
        student_lay.addLayout(btn_row)
        student_lay.addStretch(1)
        self._stack.addWidget(student_panel)

        faculty_panel = QWidget()
        faculty_lay = QVBoxLayout(faculty_panel)
        faculty_lay.setContentsMargins(0, 0, 0, 0)
        faculty_lay.setSpacing(16)
        self._faculty_search = FacultyMemberSearchField(expense_service)
        faculty_picker_row, self._faculty_refresh_btn = _picker_row(
            self._faculty_search,
            self._on_faculty_refresh,
        )
        faculty_lay.addWidget(FormField("Faculty", faculty_picker_row, required=True))
        self._faculty_summary = _MemberSummaryCard()
        self._faculty_summary.show_faculty_layout()
        faculty_lay.addWidget(self._faculty_summary)
        self._faculty_search.textChanged.connect(self._on_faculty_selection_changed)
        self.delete_faculty_btn = QPushButton("Delete Faculty")
        _style_danger_button(self.delete_faculty_btn)
        fac_btn_row = QHBoxLayout()
        fac_btn_row.addStretch(1)
        fac_btn_row.addWidget(self.delete_faculty_btn)
        faculty_lay.addLayout(fac_btn_row)
        faculty_lay.addStretch(1)
        self._stack.addWidget(faculty_panel)

        body_lay.addWidget(self._stack, 1)

        self._wrapped = wrap_page(
            "Delete Member",
            breadcrumb_trail("Admin Control", "Delete Member"),
            body,
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._wrapped)

        self._on_mode_changed(self._mode_toggle.selected_label())
        self._clear_summaries()

    def is_faculty_mode(self) -> bool:
        return self._mode_toggle.selected_index() == _FACULTY_INDEX

    def selected_student_id(self) -> str | None:
        return self._student_search.selected_student_id()

    def selected_employee_id(self) -> str | None:
        return self._faculty_search.selected_employee_id()

    def reload_pickers(self) -> None:
        self._student_search.reset()
        self._faculty_search.reset()
        self._clear_summaries()

    def _on_student_refresh(self) -> None:
        self._student_search.reset()
        self._student_summary.clear_summary()
        self._student_summary.show_student_layout()

    def _on_faculty_refresh(self) -> None:
        self._faculty_search.reset()
        self._faculty_summary.clear_summary()
        self._faculty_summary.show_faculty_layout()

    def _on_mode_changed(self, _label: str) -> None:
        self._stack.setCurrentIndex(self._mode_toggle.selected_index())
        self._clear_summaries()

    def _clear_summaries(self) -> None:
        self._student_summary.clear_summary()
        self._student_summary.show_student_layout()
        self._faculty_summary.clear_summary()
        self._faculty_summary.show_faculty_layout()

    def _on_student_selection_changed(self) -> None:
        sid = self.selected_student_id()
        if not sid:
            self._student_summary.clear_summary()
            self._student_summary.show_student_layout()
            return
        student = self._student_service.get_student(sid)
        if student is None:
            self._student_summary.clear_summary()
            self._student_summary.show_student_layout()
            return
        due = self._payment_service.get_student_due_breakdown(sid)
        pending = pending_fees(due)
        total = float(due.get("total") or 0.0)
        self._student_summary.set_student_summary(
            roll=str(student.student_id or "—"),
            name=str(student.full_name or "—"),
            class_text=f"{student.class_name or ''}-{student.section or ''}".strip("-") or "—",
            status=str(student.status or "—").title(),
            pending=f"₹{pending:,.2f}",
            total=f"₹{total:,.2f}",
        )

    def _on_faculty_selection_changed(self) -> None:
        eid = self.selected_employee_id()
        if not eid:
            self._faculty_summary.clear_summary()
            self._faculty_summary.show_faculty_layout()
            return
        row = None
        for fac in self._expense_service.list_faculty_salaries(active_only=False):
            if (getattr(fac, "employee_id", None) or "").strip().lower() == eid.lower():
                row = fac
                break
        if row is None:
            self._faculty_summary.clear_summary()
            self._faculty_summary.show_faculty_layout()
            return
        active = bool(getattr(row, "is_active", True))
        self._faculty_summary.set_faculty_summary(
            employee_id=str(row.employee_id or "—"),
            name=str(row.faculty_name or "—"),
            category=str(row.faculty_type or "—"),
            status="Active" if active else "Inactive",
        )

    def refresh_theme(self) -> None:
        body = self.findChild(QWidget, "deleteMemberBody")
        if body is not None:
            body.setStyleSheet("background: transparent;")
        self._mode_toggle.refresh_theme()
        style_fee_action_button(self._student_refresh_btn)
        style_fee_action_button(self._faculty_refresh_btn)
        self._student_search.refresh_theme()
        self._faculty_search.refresh_theme()
        _style_danger_button(self.delete_student_btn)
        _style_danger_button(self.delete_faculty_btn)
        theme.refresh_widget_tree(self._wrapped)
