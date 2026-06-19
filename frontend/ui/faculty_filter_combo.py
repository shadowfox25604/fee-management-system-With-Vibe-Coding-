"""Searchable faculty picker for filters and delete flows."""

from __future__ import annotations

from PySide6.QtCore import Qt, QStringListModel
from PySide6.QtWidgets import QComboBox, QCompleter

from backend.services.expense_service import ExpenseService
from frontend.ui import theme


def _faculty_label(row) -> str:
    name = (getattr(row, "faculty_name", None) or "").strip()
    eid = (getattr(row, "employee_id", None) or "").strip()
    ftype = (getattr(row, "faculty_type", None) or "").strip()
    type_part = f" — {ftype}" if ftype else ""
    return f"{name} ({eid}){type_part}"


class FacultyFilterComboBox(QComboBox):
    """Editable combo listing faculty; search by name or employee ID."""

    def __init__(
        self,
        expense_service: ExpenseService,
        *,
        prompt_label: str = "Select a faculty member…",
        prompt_as_placeholder: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._expense_service = expense_service
        self._prompt_label = prompt_label
        self._prompt_as_placeholder = prompt_as_placeholder
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMinimumHeight(36)
        line = self.lineEdit()
        if line is not None:
            placeholder = prompt_label if prompt_as_placeholder else "Search faculty name or employee ID…"
            line.setPlaceholderText(placeholder)
            line.setClearButtonEnabled(True)
            line.textChanged.connect(self._on_line_text_changed)
        self._reload_items()

    def _line_text(self) -> str:
        line = self.lineEdit()
        if line is not None:
            return (line.text() or "").strip()
        return (self.currentText() or "").strip()

    def _on_line_text_changed(self, text: str) -> None:
        if self.signalsBlocked():
            return
        stripped = text.strip()
        if not stripped:
            if self.currentIndex() != 0:
                self.blockSignals(True)
                self.setCurrentIndex(0)
                self.blockSignals(False)
            return
        idx = self.currentIndex()
        if idx > 0 and stripped != self.itemText(idx):
            self._detach_index_preserve_text(text)

    def _detach_index_preserve_text(self, text: str) -> None:
        """Drop stale combo index while the user is typing a new query."""
        self.blockSignals(True)
        line = self.lineEdit()
        if line is not None:
            line.blockSignals(True)
        self.setCurrentIndex(0)
        if line is not None:
            line.setText(text)
            line.blockSignals(False)
        self.blockSignals(False)

    def _reload_items(self, *, preserve_selection: bool = True) -> None:
        self.blockSignals(True)
        current = self.selected_employee_id() if preserve_selection else None
        self.clear()
        empty_label = "" if self._prompt_as_placeholder else self._prompt_label
        self.addItem(empty_label, "")
        for row in self._expense_service.list_faculty_salaries(active_only=False):
            eid = (getattr(row, "employee_id", None) or "").strip()
            if not eid:
                continue
            self.addItem(_faculty_label(row), eid)
        if preserve_selection and current:
            idx = self.findData(current)
            if idx >= 0:
                self.setCurrentIndex(idx)
            else:
                self._reset_empty_display()
        else:
            self._reset_empty_display()
        self.blockSignals(False)
        labels = [
            self.itemText(i) for i in range(self.count()) if self.itemText(i).strip()
        ]
        if hasattr(self, "_completer"):
            self._completer.setModel(QStringListModel(labels))
        else:
            self._completer = QCompleter(labels, self)
            self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.setCompleter(self._completer)
            theme.style_completer_popup(self._completer)
            self._completer.activated.connect(self._on_completer_activated)

    def _on_completer_activated(self, text: str) -> None:
        idx = self.findText(text)
        if idx >= 0:
            self.setCurrentIndex(idx)

    def sync_index_from_text(self) -> None:
        """Align combo index with typed/partial match so currentData() stays consistent."""
        if not self._line_text():
            if self.currentIndex() != 0:
                self.blockSignals(True)
                self.setCurrentIndex(0)
                self.blockSignals(False)
            return
        eid = self.selected_employee_id()
        if not eid:
            return
        idx = self.findData(eid)
        if idx >= 0 and self.currentIndex() != idx:
            self.blockSignals(True)
            self.setCurrentIndex(idx)
            self.blockSignals(False)

    def refresh_theme(self) -> None:
        if hasattr(self, "_completer"):
            theme.style_completer_popup(self._completer)

    def reload(self, *, preserve_selection: bool = True) -> None:
        self._reload_items(preserve_selection=preserve_selection)

    def reset(self) -> None:
        """Reload the faculty list and restore the default empty search state."""
        if hasattr(self, "_completer"):
            self._completer.popup().hide()
        self._reload_items(preserve_selection=False)

    def selected_employee_id(self) -> str | None:
        text = self._line_text()
        if not text:
            return None

        idx = self.currentIndex()
        if idx > 0 and text == self.itemText(idx):
            data = self.itemData(idx)
            if data is not None and str(data).strip():
                return str(data).strip()

        if not self._prompt_as_placeholder and text.lower() == self._prompt_label.lower():
            return None

        needle = text.lower()
        exact: str | None = None
        partial: str | None = None
        for i in range(self.count()):
            eid = self.itemData(i)
            if eid is None or not str(eid).strip():
                continue
            eid_s = str(eid)
            label = self.itemText(i).lower()
            if needle == eid_s.lower() or needle == label:
                exact = eid_s
                break
            if partial is None and (needle in label or needle in eid_s.lower()):
                partial = eid_s
        return exact or partial

    def clear_selection(self) -> None:
        self.blockSignals(True)
        self._reset_empty_display()
        self.blockSignals(False)

    def _reset_empty_display(self) -> None:
        self.setCurrentIndex(0)
        line = self.lineEdit()
        if line is not None:
            line.blockSignals(True)
            line.clear()
            line.blockSignals(False)
            if self._prompt_as_placeholder:
                line.setPlaceholderText(self._prompt_label)
        if hasattr(self, "_completer"):
            self._completer.setCompletionPrefix("")
