"""Helpers for placing application windows on the primary display."""

from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget


def ensure_on_screen(widget: QWidget) -> None:
    """Resize and move a window so it fits within the available screen area."""
    screen = widget.screen() or QGuiApplication.primaryScreen()
    if screen is None:
        return

    available = screen.availableGeometry()
    width = min(widget.width(), available.width())
    height = min(widget.height(), available.height())
    widget.resize(max(1, width), max(1, height))

    frame = widget.frameGeometry()
    frame.moveCenter(available.center())
    widget.move(frame.topLeft())


def show_maximized_on_screen(widget: QWidget) -> None:
    """Open a top-level window maximized on the current screen."""
    widget.showMaximized()
