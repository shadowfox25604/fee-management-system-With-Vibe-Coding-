"""Shared QTableWidget styling — row selection without cell focus artifacts."""

from __future__ import annotations

from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QBrush, QColor, QFont, QResizeEvent
from collections.abc import Callable

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from frontend.ui import theme

_APPLY_BTN_SIZE = QSize(76, 32)


def _apply_btn_style(*, width: int | None = None) -> str:
    t = theme.current_tokens()
    w = width if width is not None else _APPLY_BTN_SIZE.width()
    h = _APPLY_BTN_SIZE.height()
    return f"""
QPushButton#feeApplyBtn {{
    background-color: {t.primary};
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 0 14px;
    min-width: {w}px;
    max-width: {w}px;
    min-height: {h}px;
    max-height: {h}px;
    font-weight: 700;
    font-size: 13px;
}}
QPushButton#feeApplyBtn:hover {{
    background-color: {t.primary_dark};
    color: #FFFFFF;
}}
QPushButton#feeApplyBtn:pressed {{
    background-color: {t.primary_dark};
    color: #FFFFFF;
}}
QPushButton#feeApplyBtn:disabled {{
    background-color: #CBD5E0;
    color: #FFFFFF;
}}
"""


def fee_action_button_width(btn: QPushButton, *, min_width: int = 76) -> int:
    """Width that fits button label with the same horizontal padding as Apply."""
    metrics = btn.fontMetrics()
    return max(min_width, metrics.horizontalAdvance(btn.text()) + 28)


def style_fee_action_button(btn: QPushButton, *, width: int | None = None) -> None:
    """Solid green fee-control action button (same look as Apply)."""
    if width is None:
        width = fee_action_button_width(btn)
    btn.setObjectName("feeApplyBtn")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFlat(False)
    btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    btn.setFixedSize(width, _APPLY_BTN_SIZE.height())
    btn.setStyleSheet(_apply_btn_style(width=width))


class _ApplyButtonCell(QWidget):
    """Table cell host that keeps a fixed-size Apply button centered."""

    def __init__(self, on_click: Callable[[], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("feeApplyCell")
        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn = QPushButton("Apply", self)
        self._btn.clicked.connect(on_click)
        style_fee_action_button(self._btn, width=_APPLY_BTN_SIZE.width())
        self._center_button()

    def _apply_btn_styles(self) -> None:
        style_fee_action_button(self._btn, width=_APPLY_BTN_SIZE.width())

    def refresh_theme(self) -> None:
        self._apply_btn_styles()

    def _center_button(self) -> None:
        x = max(0, (self.width() - self._btn.width()) // 2)
        y = max(0, (self.height() - self._btn.height()) // 2)
        self._btn.move(x, y)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._center_button()


class RowSelectionDelegate(QStyledItemDelegate):
    """Full-row highlight with left accent; suppresses per-cell focus ring."""

    def paint(self, painter, option, index):
        t = theme.current_tokens()
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        opt.showDecorationSelected = False

        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        if selected:
            painter.save()
            painter.fillRect(opt.rect, QColor(t.primary_soft))
            stripe = QRect(opt.rect.left(), opt.rect.top(), 4, opt.rect.height())
            painter.fillRect(stripe, QColor(t.primary))
            painter.restore()
            opt.state &= ~QStyle.StateFlag.State_Selected
            opt.backgroundBrush = QBrush(Qt.BrushStyle.NoBrush)
            if index.column() in (1, 2):
                font = QFont(opt.font)
                font.setWeight(QFont.Weight.DemiBold)
                opt.font = font
                opt.palette.setColor(opt.palette.ColorRole.Text, QColor(t.text_primary))

        super().paint(painter, opt, index)


def configure_data_table(table: QTableWidget) -> None:
    """Read-only table with polished row selection."""
    t = theme.current_tokens()
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(True)
    table.setShowGrid(True)
    table.setGridStyle(Qt.PenStyle.SolidLine)
    table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    table.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
    table.setItemDelegate(RowSelectionDelegate(table))
    table.setStyleSheet(
        f"""
        QTableWidget {{
            outline: none;
            border: none;
            background: {t.bg_surface};
            color: {t.text_primary};
            gridline-color: {t.border_light};
            alternate-background-color: {t.table_alt_row};
        }}
        QTableWidget::item {{
            padding: 10px 8px;
            border: none;
            outline: none;
        }}
        QTableWidget::item:selected {{
            background: transparent;
            color: {t.text_primary};
        }}
        QTableWidget::item:focus {{
            border: none;
            outline: none;
            background: transparent;
        }}
        """
    )
    vh = table.verticalHeader()
    vh.setVisible(False)
    vh.setDefaultSectionSize(44)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setHighlightSections(False)
    table.viewport().update()


def configure_fee_editor_table(table: QTableWidget) -> None:
    """Tables with amount fields + Apply buttons (Fee Control)."""
    t = theme.current_tokens()
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.setAlternatingRowColors(True)
    table.setShowGrid(True)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(48)
    header = table.horizontalHeader()
    header.setHighlightSections(False)
    header.setStretchLastSection(False)
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
    table.setColumnWidth(1, 148)
    table.setColumnWidth(2, 96)
    table.setStyleSheet(
        f"""
        QTableWidget {{
            border: none;
            background: {t.bg_surface};
            color: {t.text_primary};
            gridline-color: {t.border_light};
            alternate-background-color: {t.table_alt_row};
        }}
        QTableWidget::item {{
            padding: 8px 10px;
        }}
        QLineEdit {{
            min-height: 36px;
            max-height: 36px;
        }}
        {_apply_btn_style()}
        """
    )


def refresh_tables_in(root: QWidget | None) -> None:
    if root is None:
        return
    for table in root.findChildren(QTableWidget):
        if table.columnCount() == 3 and table.horizontalHeaderItem(2) is not None:
            hdr = table.horizontalHeaderItem(2).text()
            if hdr == "Action":
                configure_fee_editor_table(table)
                continue
        configure_data_table(table)


def apply_button_cell(on_click: Callable[[], None]) -> QWidget:
    """Centered solid-green Apply button for a table cell."""
    return _ApplyButtonCell(on_click)


def table_item(text: str, *, bold: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    if bold:
        font = item.font()
        font.setWeight(QFont.Weight.DemiBold)
        item.setFont(font)
    return item
