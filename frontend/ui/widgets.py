"""Reusable UI building blocks for the modern shell layout."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from frontend.ui.theme import (
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_ORANGE,
    ACCENT_PURPLE,
    BG_MUTED,
    PRIMARY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class PageHeader(QWidget):
    """Title + breadcrumb-style subtitle for a content page."""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(4)
        self._title = QLabel(title)
        self._title.setProperty("role", "page-title")
        layout.addWidget(self._title)
        self._subtitle = QLabel(subtitle)
        self._subtitle.setProperty("role", "page-subtitle")
        self._subtitle.setWordWrap(True)
        layout.addWidget(self._subtitle)
        if not subtitle:
            self._subtitle.hide()

    def set_subtitle(self, text: str) -> None:
        self._subtitle.setText(text)
        self._subtitle.setVisible(bool(text))


class ContentCard(QFrame):
    """White rounded panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("card", "true")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 18, 20, 18)
        self._layout.setSpacing(12)

    @property
    def body_layout(self) -> QVBoxLayout:
        return self._layout


class FormSection(ContentCard):
    """Card with a section heading (EduDash form blocks)."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        heading = QLabel(title)
        heading.setProperty("role", "section-title")
        self._layout.addWidget(heading)


class StatCard(QFrame):
    """Dashboard metric tile with colored icon badge."""

    _ACCENTS = {
        "teal": (PRIMARY, "#E6FFFA"),
        "orange": (ACCENT_ORANGE, "#FFF7ED"),
        "blue": (ACCENT_BLUE, "#EFF6FF"),
        "purple": (ACCENT_PURPLE, "#F5F3FF"),
        "green": (ACCENT_GREEN, "#F0FDF4"),
    }

    def __init__(
        self,
        title: str,
        value: str = "—",
        *,
        icon: str = "◆",
        accent: str = "teal",
        parent=None,
    ):
        super().__init__(parent)
        self.setProperty("card", "stat")
        fg, bg = self._ACCENTS.get(accent, self._ACCENTS["teal"])

        root = QHBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(14)

        badge = QLabel(icon)
        badge.setFixedSize(48, 48)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {bg}; color: {fg}; border-radius: 24px; "
            f"font-size: 20px; font-weight: 700;"
        )

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: 600;")
        self._value_lbl = QLabel(value)
        self._value_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 26px; font-weight: 700;"
        )
        text_col.addWidget(self._title_lbl)
        text_col.addWidget(self._value_lbl)

        root.addWidget(badge)
        root.addLayout(text_col, 1)

    def set_value(self, value: str) -> None:
        self._value_lbl.setText(value)

    def set_title(self, title: str) -> None:
        self._title_lbl.setText(title)


class PageFrame(QWidget):
    """Wraps page content with header inside the main shell."""

    def __init__(self, title: str, subtitle: str, content: QWidget, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.header = PageHeader(title, subtitle)
        layout.addWidget(self.header)
        layout.addWidget(content, 1)


class ToolbarRow(QWidget):
    """Horizontal filter/action bar above tables."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(0, 0, 0, 12)
        self._row.setSpacing(10)

    def add_widget(self, widget, stretch: int = 0) -> None:
        self._row.addWidget(widget, stretch)


def stat_grid(cards: list[StatCard], columns: int = 4) -> QWidget:
    host = QWidget()
    grid = QGridLayout(host)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(14)
    grid.setVerticalSpacing(14)
    for i, card in enumerate(cards):
        grid.addWidget(card, i // columns, i % columns)
    return host
