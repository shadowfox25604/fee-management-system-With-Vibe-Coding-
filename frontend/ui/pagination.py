"""Shared pagination helpers for list/table tabs."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from frontend.ui.table_style import style_fee_action_button

PAGE_SIZE = 50


def page_count(total_items: int, page_size: int = PAGE_SIZE) -> int:
    if total_items <= 0:
        return 1
    return (total_items + page_size - 1) // page_size


def slice_page(items: list, page_index: int, page_size: int = PAGE_SIZE) -> list:
    if page_index < 0:
        page_index = 0
    start = page_index * page_size
    return items[start : start + page_size]


class PaginationBar(QWidget):
    """Previous / Next controls with page summary (bottom-aligned row)."""

    def __init__(self, on_previous, on_next, parent=None, *, green_style: bool = False):
        super().__init__(parent)
        self._green_style = green_style
        self._on_previous = on_previous
        self._on_next = on_next
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 6, 0, 0)
        row.addStretch(1)
        self.status_label = QLabel("Page 1 of 1")
        self.status_label.setProperty("role", "muted")
        self.prev_btn = QPushButton("← Previous")
        self.next_btn = QPushButton("Next →")
        if green_style:
            style_fee_action_button(self.prev_btn)
            style_fee_action_button(self.next_btn)
        # clicked emits a bool; swallow it so callers are not passed checked=False as pane_id etc.
        self.prev_btn.clicked.connect(lambda *_: self._on_previous())
        self.next_btn.clicked.connect(lambda *_: self._on_next())
        row.addWidget(self.status_label)
        row.addWidget(self.prev_btn)
        row.addWidget(self.next_btn)

    @property
    def green_style(self) -> bool:
        return self._green_style

    def update_state(self, page_index: int, total_items: int, page_size: int = PAGE_SIZE) -> None:
        pages = page_count(total_items, page_size)
        if page_index >= pages:
            page_index = max(0, pages - 1)
        shown_from = page_index * page_size + 1 if total_items else 0
        shown_to = min((page_index + 1) * page_size, total_items)
        self.status_label.setText(
            f"Page {page_index + 1} of {pages}  |  "
            f"Showing {shown_from}–{shown_to} of {total_items}"
        )
        self.prev_btn.setEnabled(page_index > 0)
        self.next_btn.setEnabled(page_index < pages - 1 and total_items > (page_index + 1) * page_size)

    def refresh_theme(self) -> None:
        if not self._green_style:
            return
        style_fee_action_button(self.prev_btn, width=self.prev_btn.width() if self.prev_btn.width() > 0 else None)
        style_fee_action_button(self.next_btn, width=self.next_btn.width() if self.next_btn.width() > 0 else None)
