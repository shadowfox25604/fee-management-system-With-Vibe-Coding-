"""Theme toggle with fixed sun/moon icons and a sliding highlight."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPen
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from frontend.ui import theme

_TRACK_W = 72
_TRACK_H = 32
_ICON = 28
_MARGIN = 2
_ANIM_MS = 240
_ICON_SUN = "☀️"
_ICON_MOON = "🌙"


def _emoji_font() -> QFont:
    for family in ("Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji"):
        if family in QFontDatabase.families():
            return QFont(family, 16)
    font = QFont()
    font.setPointSize(16)
    return font


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


class ThemeToggleWidget(QWidget):
    """Sun and moon stay fixed; only the active highlight slides between them."""

    toggled = Signal()

    def __init__(self, on_toggle: Callable[[], None] | None = None, parent=None):
        super().__init__(parent)
        self._on_toggle = on_toggle
        self._offset = 0.0
        self._anim = QPropertyAnimation(self, b"thumbOffset", self)
        self._anim.setDuration(_ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.setFixedSize(_TRACK_W, _TRACK_H)
        self.setMinimumSize(_TRACK_W, _TRACK_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setToolTip("Switch appearance")

        icon_font = _emoji_font()
        self._sun = self._make_icon(_ICON_SUN, icon_font)
        self._moon = self._make_icon(_ICON_MOON, icon_font)
        self._layout_icons()
        self.set_mode(theme.current_theme_mode(), animate=False)

    def _make_icon(self, glyph: str, icon_font: QFont) -> QLabel:
        label = QLabel(glyph, self)
        label.setFont(icon_font)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        label.setProperty("role", "theme-icon")
        return label

    def _slot_x(self, side: str) -> int:
        if side == "left":
            return _MARGIN
        return self.width() - _MARGIN - _ICON

    def _slot_center_x(self, side: str) -> int:
        return self._slot_x(side) + _ICON // 2

    def _layout_icons(self) -> None:
        y = (self.height() - _ICON) // 2
        self._sun.setGeometry(self._slot_x("left"), y, _ICON, _ICON)
        self._moon.setGeometry(self._slot_x("right"), y, _ICON, _ICON)

    def _highlight_x(self) -> int:
        travel = self._slot_center_x("right") - self._slot_center_x("left")
        return self._slot_center_x("left") + int(travel * self._offset)

    def _refresh_icon_opacity(self) -> None:
        sun_opacity = _lerp(1.0, 0.35, self._offset)
        moon_opacity = _lerp(0.35, 1.0, self._offset)
        self._sun.setStyleSheet(
            "QLabel[role='theme-icon'] { background: transparent; border: none; "
            f"padding: 0px; opacity: {sun_opacity:.2f}; }}"
        )
        self._moon.setStyleSheet(
            "QLabel[role='theme-icon'] { background: transparent; border: none; "
            f"padding: 0px; opacity: {moon_opacity:.2f}; }}"
        )

    def get_thumb_offset(self) -> float:
        return self._offset

    def set_thumb_offset(self, value: float) -> None:
        self._offset = max(0.0, min(1.0, float(value)))
        self._refresh_icon_opacity()
        self.update()

    thumbOffset = Property(float, get_thumb_offset, set_thumb_offset)

    def set_mode(self, mode: str, *, animate: bool = False) -> None:
        target = 1.0 if mode == "dark" else 0.0
        if abs(self._offset - target) < 0.001:
            self._refresh_icon_opacity()
            self.setToolTip(
                "Switch to dark theme" if mode == "light" else "Switch to light theme"
            )
            return
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._offset)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._offset = target
            self._refresh_icon_opacity()
            self.update()
        self.setToolTip(
            "Switch to dark theme" if mode == "light" else "Switch to light theme"
        )

    def refresh_theme(self) -> None:
        self._refresh_icon_opacity()
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._on_toggle is not None:
                self._on_toggle()
            else:
                self.toggled.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_icons()

    def paintEvent(self, _event) -> None:
        t = theme.current_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track = self.rect().adjusted(0, 0, -1, -1)
        painter.setPen(QPen(QColor(t.border), 1))
        painter.setBrush(QColor(t.bg_section_header))
        painter.drawRoundedRect(track, _TRACK_H / 2, _TRACK_H / 2)

        glow = QColor(t.primary)
        glow.setAlpha(48)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        cx = self._highlight_x()
        cy = self.height() // 2
        painter.drawEllipse(cx - 14, cy - 14, 28, 28)

        painter.end()

        self._sun.raise_()
        self._moon.raise_()
