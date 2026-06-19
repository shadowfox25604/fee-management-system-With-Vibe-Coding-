"""Search fields for Delete Member — QLineEdit input with live suggestion popup."""

from __future__ import annotations

from PySide6.QtCore import Qt, QStringListModel
from PySide6.QtWidgets import QCompleter, QLineEdit

from backend.services.expense_service import ExpenseService
from backend.services.student_service import StudentService
from frontend.ui import theme


def _student_label(student) -> str:
    cls = (getattr(student, "class_name", None) or "").strip()
    class_part = f" — Class {cls}" if cls else ""
    return f"{student.full_name} ({student.student_id}){class_part}"


def _faculty_label(row) -> str:
    name = (getattr(row, "faculty_name", None) or "").strip()
    eid = (getattr(row, "employee_id", None) or "").strip()
    ftype = (getattr(row, "faculty_type", None) or "").strip()
    type_part = f" — {ftype}" if ftype else ""
    return f"{name} ({eid}){type_part}"


def _match_id_from_text(
    text: str,
    entries: list[tuple[str, str]],
) -> str | None:
    """Resolve an entry id from typed text (exact label/id first, then partial)."""
    needle = text.strip().lower()
    if not needle:
        return None

    exact: str | None = None
    partial: str | None = None
    for entry_id, label in entries:
        label_lower = label.lower()
        id_lower = entry_id.lower()
        if needle == id_lower or needle == label_lower:
            exact = entry_id
            break
        if partial is None and (needle in label_lower or needle in id_lower):
            partial = entry_id
    return exact or partial


class _MemberSearchLineEdit(QLineEdit):
    """QLineEdit with a themed completer popup that filters as the user types."""

    def __init__(self, *, placeholder: str, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.setMinimumHeight(36)
        self._entries: list[tuple[str, str]] = []
        self._completer = QCompleter(self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(self._completer)
        theme.style_completer_popup(self._completer)
        self._completer.activated.connect(self._on_completer_activated)
        self.textChanged.connect(self._update_completer_popup)

    def _update_completer_model(self) -> None:
        labels = [label for _, label in self._entries]
        self._completer.setModel(QStringListModel(labels))

    def _update_completer_popup(self, text: str) -> None:
        prefix = text.strip()
        if not prefix:
            self._completer.popup().hide()
            return
        self._completer.setCompletionPrefix(prefix)
        if self._completer.completionCount() > 0:
            self._completer.complete()
        else:
            self._completer.popup().hide()

    def _on_completer_activated(self, text: str) -> None:
        self.setText(text)

    def refresh_theme(self) -> None:
        theme.style_completer_popup(self._completer)

    def reset(self) -> None:
        self.blockSignals(True)
        self._completer.popup().hide()
        self.clear()
        self.reload_entries()
        self.blockSignals(False)


class StudentMemberSearchField(_MemberSearchLineEdit):
    """Live student search for delete flows."""

    def __init__(
        self,
        student_service: StudentService,
        *,
        placeholder: str = "Select a student…",
        parent=None,
    ):
        super().__init__(placeholder=placeholder, parent=parent)
        self._student_service = student_service
        self.reload_entries()

    def reload_entries(self) -> None:
        self._entries = [
            (student.student_id, _student_label(student))
            for student in self._student_service.list_students()
        ]
        self._update_completer_model()

    def selected_student_id(self) -> str | None:
        return _match_id_from_text(self.text(), self._entries)


class FacultyMemberSearchField(_MemberSearchLineEdit):
    """Live faculty search for delete flows."""

    def __init__(
        self,
        expense_service: ExpenseService,
        *,
        placeholder: str = "Select a faculty member…",
        parent=None,
    ):
        super().__init__(placeholder=placeholder, parent=parent)
        self._expense_service = expense_service
        self.reload_entries()

    def reload_entries(self) -> None:
        self._entries = []
        for row in self._expense_service.list_faculty_salaries(active_only=False):
            eid = (getattr(row, "employee_id", None) or "").strip()
            if not eid:
                continue
            self._entries.append((eid, _faculty_label(row)))
        self._update_completer_model()

    def selected_employee_id(self) -> str | None:
        return _match_id_from_text(self.text(), self._entries)
