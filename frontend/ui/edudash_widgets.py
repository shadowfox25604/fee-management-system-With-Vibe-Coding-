"""EduDash-style UI components (cards, charts, forms, navigation)."""

from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPointF, QRectF, QSize, Qt, QPropertyAnimation
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from frontend.ui import theme
from frontend.ui.theme import BLUE, GREEN, ORANGE, PURPLE, TEAL


# ── Page chrome ──────────────────────────────────────────────────────────────


class BreadcrumbBar(QWidget):
  def __init__(self, parts: list[str], parent=None):
    super().__init__(parent)
    self._parts = parts
    self._labels: list[QLabel] = []
    self._seps: list[QLabel] = []
    row = QHBoxLayout(self)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    for i, part in enumerate(parts):
      if i > 0:
        sep = QLabel(" / ")
        self._seps.append(sep)
        row.addWidget(sep)
      lbl = QLabel(part)
      self._labels.append(lbl)
      row.addWidget(lbl)
    row.addStretch(1)
    self.refresh_theme()

  def refresh_theme(self) -> None:
    t = theme.current_tokens()
    for sep in self._seps:
      sep.setStyleSheet(f"color: {t.text_muted};")
    for i, lbl in enumerate(self._labels):
      if i == len(self._labels) - 1:
        lbl.setStyleSheet(f"color: {t.primary}; font-weight: 600;")
      else:
        lbl.setStyleSheet(f"color: {t.text_muted};")


class PageChrome(QWidget):
  """Title + breadcrumb block matching EduDash inner pages."""

  def __init__(self, title: str, breadcrumbs: list[str], parent=None):
    super().__init__(parent)
    lay = QVBoxLayout(self)
    lay.setContentsMargins(0, 0, 0, 20)
    lay.setSpacing(6)
    t = QLabel(title)
    t.setProperty("role", "page-title")
    lay.addWidget(t)
    if breadcrumbs:
      lay.addWidget(BreadcrumbBar(breadcrumbs))


def wrap_page(title: str, breadcrumbs: list[str], body: QWidget) -> QWidget:
  host = QWidget()
  host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
  lay = QVBoxLayout(host)
  lay.setContentsMargins(0, 0, 0, 0)
  lay.setSpacing(0)
  body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
  body.setMinimumHeight(0)
  lay.addWidget(PageChrome(title, breadcrumbs))
  lay.addWidget(body, 1)
  return host


# ── Cards ────────────────────────────────────────────────────────────────────


class SurfaceCard(QFrame):
  def __init__(self, parent=None):
    super().__init__(parent)
    self.setProperty("card", "surface")
    self._lay = QVBoxLayout(self)
    self._lay.setContentsMargins(20, 18, 20, 18)
    self._lay.setSpacing(14)

  @property
  def body(self) -> QVBoxLayout:
    return self._lay


class CardTitleBar(QWidget):
  """Widget header row with title and optional menu dots."""

  def __init__(self, title: str, parent=None):
    super().__init__(parent)
    row = QHBoxLayout(self)
    row.setContentsMargins(0, 0, 0, 0)
    lbl = QLabel(title)
    lbl.setProperty("role", "card-title")
    row.addWidget(lbl)
    row.addStretch(1)
    self._dots = QLabel("⋮")
    row.addWidget(self._dots)
    self.refresh_theme()

  def refresh_theme(self) -> None:
    t = theme.current_tokens()
    for lbl in self.findChildren(QLabel):
      if lbl.property("role") == "card-title":
        lbl.setStyleSheet(
          f"color: {t.text_primary}; font-size: 15px; font-weight: 700; "
          f"background: transparent;"
        )
    self._dots.setStyleSheet(
      f"color: {t.text_muted}; font-size: 18px; background: transparent;"
    )


# ── Dashboard stat card (gradient) ───────────────────────────────────────────


class DashMetricCard(QFrame):
  # light: (gradient_start, icon_circle_bg, accent)
  _STYLES_LIGHT = [
    ("#FFF4ED", "#FF7043", ORANGE),
    ("#EFF6FF", "#42A5F5", BLUE),
    ("#F5F3FF", "#AB47BC", PURPLE),
    ("#E6FFFA", "#26A69A", TEAL),
    ("#F0FDF4", "#66BB6A", GREEN),
    ("#E0F7FA", "#26C6DA", "#26C6DA"),
  ]
  # dark: (icon_circle_bg, accent) — card uses theme surface color
  _STYLES_DARK = [
    ("#3D2E24", ORANGE),
    ("#243347", BLUE),
    ("#322447", PURPLE),
    ("#1A3D35", TEAL),
    ("#243D2A", GREEN),
    ("#1A3A40", "#26C6DA"),
  ]

  def __init__(
    self,
    label: str,
    value: str = "0",
    trend: str = "",
    style_idx: int = 0,
    parent=None,
  ):
    super().__init__(parent)
    self._style_idx = style_idx % len(self._STYLES_LIGHT)
    self.setMinimumHeight(110)
    lay = QHBoxLayout(self)
    lay.setContentsMargins(18, 16, 18, 16)
    self._icon = QLabel("◉")
    self._icon.setFixedSize(44, 44)
    self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    col = QVBoxLayout()
    col.setSpacing(2)
    self._label = QLabel(label)
    self._value = QLabel(value)
    self._trend = QLabel(trend)
    col.addWidget(self._label)
    col.addWidget(self._value)
    if trend:
      col.addWidget(self._trend)
    lay.addWidget(self._icon)
    lay.addLayout(col, 1)
    self.refresh_theme()

  def refresh_theme(self) -> None:
    t = theme.current_tokens()
    idx = self._style_idx
    if theme.current_theme_mode() == "dark":
      icon_bg, accent = self._STYLES_DARK[idx]
      self.setStyleSheet(
        f"QFrame {{ background: {t.bg_surface}; border: 1px solid {t.border}; "
        f"border-radius: 12px; }}"
      )
      self._icon.setStyleSheet(
        f"background: {icon_bg}; color: {accent}; border-radius: 22px; "
        f"font-size: 18px; font-weight: bold;"
      )
    else:
      bg, icon_bg, accent = self._STYLES_LIGHT[idx]
      self.setStyleSheet(
        f"QFrame {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
        f"stop:0 {bg}, stop:1 {t.bg_surface}); border: 1px solid {t.border}; "
        f"border-radius: 12px; }}"
      )
      self._icon.setStyleSheet(
        f"background: {icon_bg}; color: white; border-radius: 22px; "
        f"font-size: 18px; font-weight: bold;"
      )
    self._label.setStyleSheet(
      f"color: {t.text_secondary}; font-size: 12px; font-weight: 600; "
      f"background: transparent;"
    )
    self._value.setStyleSheet(
      f"color: {t.text_primary}; font-size: 26px; font-weight: 800; "
      f"background: transparent;"
    )
    self._trend.setStyleSheet(
      f"color: {t.success}; font-size: 11px; font-weight: 600; "
      f"background: transparent;"
    )

  def update_metric(self, value: str, trend: str = "") -> None:
    self._value.setText(value)
    if trend:
      self._trend.setText(trend)
      self._trend.show()
    else:
      self._trend.hide()


# ── Charts (QPainter) ──────────────────────────────────────────────────────────


class RevenueChartWidget(QWidget):
  """Daily collected-fee bars for the current calendar month."""

  Y_AXIS_MAX = 100_000.0
  Y_AXIS_STEP = 20_000.0

  def __init__(self, parent=None):
    super().__init__(parent)
    self.setMinimumHeight(400)
    self.setMouseTracking(True)
    self._month_label = ""
    self._collected: list[float] = []
    self._hover_index: int | None = None
    self._tooltip_opacity = 0.0
    self._opacity_anim = QPropertyAnimation(self, b"tooltipOpacity")
    self._opacity_anim.setDuration(180)
    self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

  def get_tooltip_opacity(self) -> float:
    return self._tooltip_opacity

  def set_tooltip_opacity(self, value: float) -> None:
    self._tooltip_opacity = float(value)
    self.update()

  tooltipOpacity = Property(float, get_tooltip_opacity, set_tooltip_opacity)

  def set_daily_collections(self, amounts: list[float], *, month_label: str = "") -> None:
    self._collected = [float(v) for v in amounts]
    self._month_label = month_label
    self._hover_index = None
    self._tooltip_opacity = 0.0
    self.update()
    self.repaint()

  @staticmethod
  def _format_axis_amount(value: float) -> str:
    v = max(0.0, float(value))
    if v <= 0:
      return "₹0"
    if v >= 1_000 and v % 1_000 == 0:
      return f"₹{int(v / 1_000)}k"
    return f"₹{v:,.0f}"

  def _y_tick_values(self) -> list[float]:
    steps = int(self.Y_AXIS_MAX / self.Y_AXIS_STEP)
    return [i * self.Y_AXIS_STEP for i in range(steps + 1)]

  def _y_axis_labels(self) -> list[str]:
    return [self._format_axis_amount(v) for v in self._y_tick_values()]

  def _left_margin_for_axis(self) -> int:
    axis_font = QFont("Segoe UI", 8)
    fm = QFontMetrics(axis_font)
    labels = self._y_axis_labels()
    widest = max((fm.horizontalAdvance(lbl) for lbl in labels), default=0)
    return max(52, widest + 14)

  def _chart_layout(self) -> dict | None:
    n_days = len(self._collected)
    if n_days < 1:
      return None
    w, h = self.width(), self.height()
    margin_t = 24
    margin_b = 40 if n_days > 25 else 36
    max_v = self.Y_AXIS_MAX
    margin_l = self._left_margin_for_axis()
    chart_h = h - margin_b - margin_t
    chart_w = w - margin_l - 16
    gap = chart_w / n_days
    bar_w = max(2.0, gap * 0.55)
    return {
      "w": w,
      "h": h,
      "n_days": n_days,
      "margin_l": margin_l,
      "margin_t": margin_t,
      "margin_b": margin_b,
      "chart_h": chart_h,
      "chart_w": chart_w,
      "max_v": max_v,
      "y_ticks": self._y_tick_values(),
      "gap": gap,
      "bar_w": bar_w,
    }

  def _bar_rect(self, index: int, layout: dict) -> QRectF:
    amount = self._collected[index]
    if amount <= 0:
      return QRectF()
    gap = layout["gap"]
    bar_w = layout["bar_w"]
    chart_h = layout["chart_h"]
    max_v = layout["max_v"]
    margin_l = layout["margin_l"]
    margin_t = layout["margin_t"]
    slot_x = margin_l + index * gap
    x = slot_x + (gap - bar_w) / 2
    scaled = min(amount, max_v)
    coll_h = (scaled / max_v) * chart_h
    return QRectF(x, margin_t + chart_h - coll_h, bar_w, coll_h)

  def _index_at_pos(self, pos: QPointF) -> int | None:
    layout = self._chart_layout()
    if layout is None:
      return None
    for i in range(layout["n_days"]):
      bar = self._bar_rect(i, layout)
      if not bar.isEmpty() and bar.contains(pos):
        return i
    return None

  def _fade_tooltip(self, target: float) -> None:
    self._opacity_anim.stop()
    self._opacity_anim.setDuration(180 if target > self._tooltip_opacity else 140)
    self._opacity_anim.setStartValue(self._tooltip_opacity)
    self._opacity_anim.setEndValue(target)
    self._opacity_anim.start()

  def _update_hover(self, index: int | None) -> None:
    if index == self._hover_index:
      return
    prev = self._hover_index
    self._hover_index = index
    if index is not None and self._collected[index] > 0:
      self.setCursor(Qt.CursorShape.PointingHandCursor)
      if prev is None or self._collected[prev] <= 0:
        self._fade_tooltip(1.0)
      else:
        self.update()
    else:
      self.unsetCursor()
      if prev is not None and self._collected[prev] > 0:
        self._fade_tooltip(0.0)
      else:
        self.update()

  def mouseMoveEvent(self, event: QMouseEvent) -> None:
    self._update_hover(self._index_at_pos(event.position()))
    super().mouseMoveEvent(event)

  def leaveEvent(self, event) -> None:
    self._update_hover(None)
    super().leaveEvent(event)

  def _paint_tooltip(self, p: QPainter, layout: dict, index: int) -> None:
    if self._tooltip_opacity <= 0.01:
      return
    day = index + 1
    amount = self._collected[index]
    text = f"Day {day}: ₹{amount:,.0f}"
    t = theme.current_tokens()
    tip_font = QFont("Segoe UI", 9)
    tip_font.setWeight(QFont.Weight.DemiBold)
    p.setFont(tip_font)
    metrics = p.fontMetrics()
    pad_x, pad_y = 10, 6
    text_w = metrics.horizontalAdvance(text)
    text_h = metrics.height()
    box_w = text_w + pad_x * 2
    box_h = text_h + pad_y * 2
    bar = self._bar_rect(index, layout)
    cx = bar.center().x()
    box_x = max(4.0, min(cx - box_w / 2, layout["w"] - box_w - 4))
    box_y = max(4.0, bar.top() - box_h - 8)
    p.save()
    p.setOpacity(self._tooltip_opacity)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(t.bg_surface))
    p.drawRoundedRect(QRectF(box_x, box_y, box_w, box_h), 8, 8)
    p.setPen(QPen(QColor(t.border)))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(box_x, box_y, box_w, box_h), 8, 8)
    p.setPen(QColor(t.text_primary))
    p.drawText(
      QRectF(box_x + pad_x, box_y + pad_y, text_w, text_h),
      Qt.AlignmentFlag.AlignCenter,
      text,
    )
    p.restore()

  def paintEvent(self, _event):
    p = QPainter(self)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    layout = self._chart_layout()
    if layout is None:
      p.end()
      return

    w = layout["w"]
    h = layout["h"]
    n_days = layout["n_days"]
    margin_l = layout["margin_l"]
    margin_t = layout["margin_t"]
    margin_b = layout["margin_b"]
    chart_h = layout["chart_h"]
    max_v = layout["max_v"]
    y_ticks: list[float] = layout["y_ticks"]
    gap = layout["gap"]
    bar_w = layout["bar_w"]
    label_font = QFont("Segoe UI", 6 if n_days > 25 else 7)
    axis_font = QFont("Segoe UI", 8)

    t = theme.current_tokens()
    p.setPen(QPen(QColor(t.border)))
    for tick_amount in y_ticks:
      frac = tick_amount / max_v if max_v > 0 else 0.0
      y = margin_t + chart_h * (1 - frac)
      p.drawLine(margin_l, int(y), w - 8, int(y))

    p.setFont(axis_font)
    p.setPen(QColor(t.text_muted))
    axis_metrics = p.fontMetrics()
    axis_line_h = axis_metrics.height()
    for tick_amount in y_ticks:
      frac = tick_amount / max_v if max_v > 0 else 0.0
      y = margin_t + chart_h * (1 - frac)
      text = self._format_axis_amount(tick_amount)
      p.drawText(
        QRectF(4, y - axis_line_h / 2, margin_l - 10, axis_line_h),
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        text,
      )

    hover_color = QColor(ORANGE)
    hover_color.setAlpha(230)

    for i, amount in enumerate(self._collected):
      day = i + 1
      slot_x = margin_l + i * gap
      if amount > 0:
        bar = self._bar_rect(i, layout)
        is_hover = i == self._hover_index
        p.setBrush(hover_color if is_hover else QColor(ORANGE))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(bar, 3, 3)
      p.setPen(QColor(t.text_muted))
      p.setFont(label_font)
      p.drawText(
        QRectF(slot_x, h - margin_b + 2, gap, 20),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
        str(day),
      )

    if self._hover_index is not None:
      self._paint_tooltip(p, layout, self._hover_index)

    p.end()

  def refresh_theme(self) -> None:
    self.update()


class AttendanceBarWidget(QWidget):
  """Horizontal stacked attendance bar with legend."""

  def __init__(self, parent=None):
    super().__init__(parent)
    self.setMinimumHeight(100)
    self._segments = [
      ("Present", 87, TEAL),
      ("Absent", 13, ORANGE),
      ("Late", 8, PURPLE),
      ("Half day", 5, GREEN),
    ]

  def set_segments(self, segments: list[tuple[str, int, str]]) -> None:
    self._segments = segments
    self.update()

  def paintEvent(self, _event):
    p = QPainter(self)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    w = self.width()
    bar_y, bar_h = 8, 22
    x = 0
    total = sum(s[1] for s in self._segments) or 1
    bar_w = w - 20
    for label, pct, color in self._segments:
      seg_w = bar_w * (pct / total)
      p.setBrush(QColor(color))
      p.setPen(Qt.PenStyle.NoPen)
      p.drawRoundedRect(QRectF(x, bar_y, seg_w, bar_h), 4, 4)
      x += seg_w
    p.end()

  def sizeHint(self) -> QSize:
    return QSize(400, 90)

  def refresh_theme(self) -> None:
    self.update()


class DonutChartWidget(QWidget):
  def __init__(self, parent=None):
    super().__init__(parent)
    self.setMinimumSize(160, 160)
    self._slices = [
      (200, GREEN, "Present"),
      (300, BLUE, "Half Day"),
      (172, PURPLE, "Late"),
      (500, ORANGE, "Absent"),
    ]

  def set_slices(self, slices: list[tuple[int, str, str]]) -> None:
    self._slices = slices
    self.update()

  def paintEvent(self, _event):
    p = QPainter(self)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    side = min(self.width(), self.height()) - 16
    rect = QRectF((self.width() - side) / 2, 8, side, side)
    total = sum(s[0] for s in self._slices) or 1
    start = 90 * 16
    for value, color, _ in self._slices:
      span = int(360 * 16 * value / total)
      p.setBrush(QColor(color))
      p.setPen(Qt.PenStyle.NoPen)
      p.drawPie(rect, start, -span)
      start -= span
    # hole
    inner = side * 0.58
    p.setBrush(QColor(theme.current_tokens().bg_surface))
    p.drawEllipse(
      QRectF(
        rect.center().x() - inner / 2,
        rect.center().y() - inner / 2,
        inner,
        inner,
      )
    )
    p.end()

  def refresh_theme(self) -> None:
    self.update()


# ── List rows (notice / leave / event) ───────────────────────────────────────


class ListRow(QWidget):
  def __init__(
    self,
    avatar_text: str,
    title: str,
    subtitle: str,
    meta: str = "",
    accent: str | None = None,
    parent=None,
  ):
    super().__init__(parent)
    self._accent = accent
    row = QHBoxLayout(self)
    row.setContentsMargins(4, 10, 4, 10)
    self._accent_bar: QFrame | None = None
    if accent:
      self._accent_bar = QFrame()
      self._accent_bar.setFixedWidth(4)
      row.addWidget(self._accent_bar)
    self._av = QLabel(avatar_text[:1].upper())
    self._av.setFixedSize(36, 36)
    self._av.setAlignment(Qt.AlignmentFlag.AlignCenter)
    text = QVBoxLayout()
    text.setSpacing(2)
    self._title_lbl = QLabel(title)
    self._sub_lbl = QLabel(subtitle)
    self._sub_lbl.setWordWrap(True)
    text.addWidget(self._title_lbl)
    text.addWidget(self._sub_lbl)
    row.addWidget(self._av)
    row.addLayout(text, 1)
    self._meta_lbl: QLabel | None = None
    if meta:
      self._meta_lbl = QLabel(meta)
      self._meta_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
      row.addWidget(self._meta_lbl)
    self.refresh_theme()

  def refresh_theme(self) -> None:
    t = theme.current_tokens()
    self.setStyleSheet(
      f"QWidget {{ border-bottom: 1px solid {t.border}; padding: 4px 0; }}"
    )
    if self._accent_bar is not None and self._accent:
      self._accent_bar.setStyleSheet(
        f"background: {self._accent}; border-radius: 2px;"
      )
    self._av.setStyleSheet(
      f"background: {t.list_avatar_bg}; color: {t.text_secondary}; "
      f"border-radius: 18px; font-weight: 700;"
    )
    self._title_lbl.setStyleSheet(f"font-weight: 600; color: {t.text_primary};")
    self._sub_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 11px;")
    if self._meta_lbl is not None:
      self._meta_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 11px;")


class StatusPill(QLabel):
  def __init__(self, text: str, kind: str = "success", parent=None):
    super().__init__(text, parent)
    colors = {
      "success": ("#DCFCE7", "#16A34A"),
      "warning": ("#FFEDD5", "#EA580C"),
      "danger": ("#FEE2E2", "#DC2626"),
      "info": ("#DBEAFE", "#2563EB"),
    }
    bg, fg = colors.get(kind, colors["info"])
    self.setStyleSheet(
      f"background: {bg}; color: {fg}; border-radius: 10px; "
      f"padding: 4px 10px; font-size: 11px; font-weight: 600;"
    )


# ── Form layout (Add Student page) ─────────────────────────────────────────────


class SectionBlock(QFrame):
  """White card with gray section header bar."""

  def __init__(self, title: str, parent=None):
    super().__init__(parent)
    self.setProperty("card", "surface")
    outer = QVBoxLayout(self)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)
    self._header = QFrame()
    hlay = QHBoxLayout(self._header)
    hlay.setContentsMargins(20, 12, 20, 12)
    self._header_title = QLabel(title)
    hlay.addWidget(self._header_title)
    outer.addWidget(self._header)
    body_w = QWidget()
    self._body = QVBoxLayout(body_w)
    self._body.setContentsMargins(20, 20, 20, 20)
    self._body.setSpacing(16)
    outer.addWidget(body_w)
    self.refresh_theme()

  def refresh_theme(self) -> None:
    t = theme.current_tokens()
    self._header.setStyleSheet(
      f"QFrame {{ background: {t.bg_section_header}; "
      f"border-top-left-radius: 12px; border-top-right-radius: 12px; }}"
    )
    self._header_title.setStyleSheet(
      f"font-weight: 700; color: {t.text_primary}; font-size: 14px;"
    )

  @property
  def form_layout(self) -> QVBoxLayout:
    return self._body


class FormField(QWidget):
  """Label above control (EduDash field pattern)."""

  def __init__(self, label: str, widget: QWidget, required: bool = False, parent=None):
    super().__init__(parent)
    lay = QVBoxLayout(self)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    lbl_text = f"{label} *" if required else label
    lbl = QLabel(lbl_text)
    lbl.setProperty("role", "field-label")
    lay.addWidget(lbl)
    lay.addWidget(widget)


class FormGrid(QWidget):
  """Responsive N-column form grid."""

  def __init__(self, columns: int = 4, parent=None):
    super().__init__(parent)
    self._grid = QGridLayout(self)
    self._grid.setContentsMargins(0, 0, 0, 0)
    self._grid.setHorizontalSpacing(16)
    self._grid.setVerticalSpacing(16)
    self._cols = columns
    self._row = 0
    self._col = 0

  def add_field(self, field: QWidget, colspan: int = 1) -> None:
    self._grid.addWidget(field, self._row, self._col, 1, colspan)
    self._col += colspan
    if self._col >= self._cols:
      self._col = 0
      self._row += 1

  def next_row(self) -> None:
    self._col = 0
    self._row += 1


class UploadPlaceholder(QFrame):
  def __init__(self, label: str = "Drag & drop a file here or click", parent=None):
    super().__init__(parent)
    self._label_text = label
    self.setMinimumHeight(120)
    lay = QVBoxLayout(self)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._icon = QLabel("☁")
    self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._txt = QLabel(label)
    self._txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(self._icon)
    lay.addWidget(self._txt)
    self.refresh_theme()

  def refresh_theme(self) -> None:
    t = theme.current_tokens()
    self.setStyleSheet(
      f"QFrame {{ border: 2px dashed {t.border}; border-radius: 10px; "
      f"background: {t.upload_bg}; }}"
    )
    self._icon.setStyleSheet(f"font-size: 28px; color: {t.text_muted};")
    self._txt.setStyleSheet(f"color: {t.text_muted}; font-size: 12px;")


class GradientProfileCard(QFrame):
  """Student profile highlight card (theme-aware gradient)."""

  def __init__(self, name: str, class_line: str, roll: str, parent=None, show_action: bool = True):
    super().__init__(parent)
    self.setMinimumHeight(160)
    lay = QVBoxLayout(self)
    lay.setContentsMargins(20, 20, 20, 20)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.setSpacing(8)
    av = QLabel(name[:1].upper())
    av.setFixedSize(62, 62)
    av.setAlignment(Qt.AlignmentFlag.AlignCenter)
    av.setStyleSheet(
      "background: rgba(255,255,255,0.25); color: white; "
      "border-radius: 31px; font-size: 24px; font-weight: 800;"
    )
    n = QLabel(name)
    n.setStyleSheet("color: white; font-size: 18px; font-weight: 700; background: transparent;")
    n.setAlignment(Qt.AlignmentFlag.AlignCenter)
    sub = QLabel(f"Class: {class_line}  ·  Roll: {roll}")
    sub.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 12px; background: transparent;")
    sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
    btn = QPushButton("Edit Profile")
    btn.setStyleSheet(
      "QPushButton { background: transparent; color: white; "
      "border: 2px solid rgba(255,255,255,0.8); border-radius: 8px; "
      "padding: 8px 24px; font-weight: 600; }"
      "QPushButton:hover { background: rgba(255,255,255,0.15); }"
    )
    lay.addStretch(1)
    lay.addWidget(av, alignment=Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(n)
    lay.addWidget(sub)
    if show_action:
      lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
    lay.addStretch(1)
    self._avatar_lbl = av
    self._edit_btn = btn
    self._name_lbl = n
    self._sub_lbl = sub
    self._show_action = show_action
    self.refresh_theme()

  def refresh_theme(self) -> None:
    t = theme.current_tokens()
    self.setStyleSheet(
      "QFrame { border-radius: 14px; "
      "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
      f"stop:0 {t.profile_grad_start}, stop:1 {t.profile_grad_end}); }}"
    )

  def set_student(self, name: str, class_name: str, roll: str) -> None:
    raw_name = (name or "").strip()
    is_placeholder = raw_name.lower() in {"", "—", "-", "no student selected"}
    if is_placeholder:
      self._name_lbl.setText("Select a student")
      self._sub_lbl.setText("Student profile preview")
    else:
      self._name_lbl.setText(name)
      self._sub_lbl.setText(f"Class: {class_name}  ·  Roll: {roll}")
    self._avatar_lbl.setText(raw_name[:1].upper() if raw_name else "?")

  @property
  def edit_button(self) -> QPushButton:
    return self._edit_btn
