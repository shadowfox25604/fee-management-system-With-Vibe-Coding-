"""Sliding pill segment control (two options)."""

from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel

from frontend.ui import theme

LOGIN_SEGMENT_WIDTH = 360
_DEFAULT_WIDTH = LOGIN_SEGMENT_WIDTH
_SEGMENT_H = 48
_SEGMENT_PAD = 4
_SEGMENT_ANIM_MS = 220


class SegmentToggle(QFrame):
    """Pill toggle with a sliding highlight for two mutually exclusive options."""

    selection_changed = Signal(str)

    def __init__(
        self,
        options: tuple[str, ...],
        *,
        width: int = _DEFAULT_WIDTH,
        parent=None,
    ):
        super().__init__(parent)
        if len(options) != 2:
            raise ValueError("SegmentToggle currently supports exactly two options.")
        self._options = tuple(options)
        self._index = 0
        self._slide = 0.0

        self.setObjectName("segmentToggle")
        self.setFixedSize(width, _SEGMENT_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._thumb = QFrame(self)
        self._thumb.setObjectName("segmentToggleThumb")

        self._labels: list[QLabel] = []
        for name in self._options:
            lbl = QLabel(name, self)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self._labels.append(lbl)

        self._anim = QPropertyAnimation(self, b"slidePosition", self)
        self._anim.setDuration(_SEGMENT_ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.valueChanged.connect(lambda _v: self._sync_thumb_geometry())

        self.set_selected_index(0, animate=False)
        self.refresh_theme()

    def get_slide_position(self) -> float:
        return self._slide

    def set_slide_position(self, value: float) -> None:
        self._slide = max(0.0, min(1.0, float(value)))
        self._sync_thumb_geometry()
        self._sync_label_styles()

    slidePosition = Property(float, get_slide_position, set_slide_position)

    def selected_index(self) -> int:
        return self._index

    def selected_label(self) -> str:
        return self._options[self._index]

    def set_selected_index(self, index: int, *, animate: bool = False) -> None:
        index = max(0, min(len(self._options) - 1, index))
        if index == self._index and (animate or self._slide == float(index)):
            return
        self._index = index
        target = float(index)
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._slide)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._slide = target
            self._sync_thumb_geometry()
        self._sync_label_styles()
        self.selection_changed.emit(self.selected_label())

    def set_selected_label(self, label: str, *, animate: bool = False) -> None:
        for idx, name in enumerate(self._options):
            if name.lower() == (label or "").strip().lower():
                self.set_selected_index(idx, animate=animate)
                return

    def resizeEvent(self, event):
        super().resizeEvent(event)
        half = max(1, self.width() // 2)
        for idx, lbl in enumerate(self._labels):
            lbl.setGeometry(idx * half, 0, half, self.height())
        self._sync_thumb_geometry()
        self._thumb.lower()
        for lbl in self._labels:
            lbl.raise_()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        idx = 0 if event.position().x() < self.width() / 2 else 1
        self.set_selected_index(idx, animate=True)
        event.accept()

    def _segment_half_width(self) -> int:
        return max(1, (self.width() - _SEGMENT_PAD * 2) // 2)

    def _sync_thumb_geometry(self) -> None:
        half = self._segment_half_width()
        x = _SEGMENT_PAD + int(round(self._slide * half))
        self._thumb.setGeometry(
            x,
            _SEGMENT_PAD,
            half,
            max(1, self.height() - _SEGMENT_PAD * 2),
        )

    def _sync_label_styles(self) -> None:
        t = theme.current_tokens()
        for idx, lbl in enumerate(self._labels):
            active = idx == self._index
            lbl.setStyleSheet(
                f"color: {t.text_on_primary if active else t.text_secondary}; "
                f"background: transparent; font-size: 14px; "
                f"font-weight: {'700' if active else '600'};"
            )

    def refresh_theme(self) -> None:
        t = theme.current_tokens()
        self.setStyleSheet(
            f"QFrame#segmentToggle {{ background: {t.bg_app}; "
            f"border: 1px solid {t.border_light}; border-radius: {theme.RADIUS}; }}"
            f"QFrame#segmentToggleThumb {{ background: {t.primary}; "
            f"border-radius: {theme.RADIUS_SM}; }}"
        )
        self._sync_label_styles()
