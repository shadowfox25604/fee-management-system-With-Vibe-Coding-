"""Searchable student picker for filters."""

from __future__ import annotations

from PySide6.QtCore import Qt, QStringListModel
from PySide6.QtWidgets import QComboBox, QCompleter

from backend.services.student_service import StudentService
from frontend.ui import theme


def _student_label(student) -> str:
    cls = (getattr(student, "class_name", None) or "").strip()
    class_part = f" — Class {cls}" if cls else ""
    return f"{student.full_name} ({student.student_id}){class_part}"


class StudentFilterComboBox(QComboBox):
    """Editable combo listing all students; search by name or ID."""

    def __init__(self, student_service: StudentService, *, all_label: str = "All students", parent=None):
        super().__init__(parent)
        self._student_service = student_service
        self._all_label = all_label
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMinimumHeight(36)
        line = self.lineEdit()
        if line is not None:
            line.setPlaceholderText("Search student name or ID…")
            line.setClearButtonEnabled(True)
        self._reload_items()

    def _reload_items(self) -> None:
        self.blockSignals(True)
        current = self.selected_student_id()
        self.clear()
        self.addItem(self._all_label, "")
        for student in self._student_service.list_students():
            self.addItem(_student_label(student), student.student_id)
        if current:
            idx = self.findData(current)
            if idx >= 0:
                self.setCurrentIndex(idx)
        else:
            self.setCurrentIndex(0)
        self.blockSignals(False)
        labels = [self.itemText(i) for i in range(self.count())]
        if hasattr(self, "_completer"):
            self._completer.setModel(QStringListModel(labels))
        else:
            self._completer = QCompleter(labels, self)
            self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.setCompleter(self._completer)
            theme.style_completer_popup(self._completer)

    def refresh_theme(self) -> None:
        if hasattr(self, "_completer"):
            theme.style_completer_popup(self._completer)

    def selected_student_id(self) -> str | None:
        data = self.currentData()
        if data is not None and str(data).strip():
            return str(data).strip()

        text = (self.currentText() or "").strip()
        if not text or text.lower() == self._all_label.lower():
            return None

        needle = text.lower()
        exact: str | None = None
        partial: str | None = None
        for i in range(self.count()):
            sid = self.itemData(i)
            if sid is None or not str(sid).strip():
                continue
            sid_s = str(sid)
            label = self.itemText(i).lower()
            if needle == sid_s.lower() or needle == label:
                exact = sid_s
                break
            if partial is None and (needle in label or needle in sid_s.lower()):
                partial = sid_s
        return exact or partial

    def clear_selection(self) -> None:
        self.blockSignals(True)
        self.setCurrentIndex(0)
        if self.lineEdit() is not None:
            self.lineEdit().clear()
        self.blockSignals(False)
