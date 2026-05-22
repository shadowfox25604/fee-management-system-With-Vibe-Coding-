"""EduDash-style main dashboard."""

from __future__ import annotations

from datetime import date
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from frontend.ui.edudash_widgets import (
    CardTitleBar,
    DashMetricCard,
    ListRow,
    RevenueChartWidget,
    SurfaceCard,
)
from frontend.ui import theme
from frontend.ui.school_branding import load_logo_pixmap, school_motto, school_name
from frontend.ui.theme import ORANGE


class HomePageTab(QWidget):
    def __init__(
        self,
        *,
        on_navigate: Callable[[str], None],
        on_refresh: Callable[[], dict],
        on_chart_data: Callable[[int, int], dict],
        on_manage_academic_years: Callable[[], None],
        parent=None,
    ):
        super().__init__(parent)
        self._on_navigate = on_navigate
        self._on_refresh = on_refresh
        self._on_chart_data = on_chart_data
        self._on_manage_years = on_manage_academic_years
        today = date.today()
        self._chart_year = today.year
        self._chart_month = today.month

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        self._brand_card = QFrame()
        self._brand_card.setProperty("card", "surface")
        brand_lay = QVBoxLayout(self._brand_card)
        brand_lay.setContentsMargins(28, 28, 28, 24)
        brand_lay.setSpacing(0)
        brand_lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        logo_size = 120
        self._brand_logo = QLabel()
        self._brand_logo.setFixedSize(logo_size, logo_size)
        self._brand_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_pix = load_logo_pixmap(logo_size)
        if logo_pix is not None:
            self._brand_logo.setPixmap(logo_pix)
        else:
            self._brand_logo.setText("A")

        self._brand_name = QLabel(school_name())
        self._brand_name.setProperty("role", "page-title")
        self._brand_name.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._brand_accent = QFrame()
        self._brand_accent.setFixedSize(56, 4)

        self._brand_motto = QLabel(school_motto().upper())
        self._brand_motto.setProperty("role", "muted")
        self._brand_motto.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name_block = QVBoxLayout()
        name_block.setSpacing(8)
        name_block.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        name_block.addWidget(self._brand_name, 0, Qt.AlignmentFlag.AlignHCenter)
        name_block.addWidget(self._brand_accent, 0, Qt.AlignmentFlag.AlignHCenter)
        name_block.addWidget(self._brand_motto, 0, Qt.AlignmentFlag.AlignHCenter)

        brand_lay.addWidget(self._brand_logo, 0, Qt.AlignmentFlag.AlignHCenter)
        brand_lay.addSpacing(16)
        brand_lay.addLayout(name_block)
        root.addWidget(self._brand_card)

        # ── Key metrics ──
        metrics = QGridLayout()
        metrics.setSpacing(14)
        metrics.setContentsMargins(0, 0, 0, 0)
        self._cards = [
            DashMetricCard("Total Active Students", "0", "—", 0),
            DashMetricCard("Total Inactive Students", "0", "—", 1),
            DashMetricCard("Academic Years", "0", "—", 2),
            DashMetricCard("Amount Collected This Week", "0", "—", 3),
            DashMetricCard("Payments Made This Week", "0", "—", 4),
            DashMetricCard("Payments Made Today", "0", "—", 5),
        ]
        for i, card in enumerate(self._cards):
            metrics.addWidget(card, i // 3, i % 3)
        metrics_host = QWidget()
        metrics_host.setLayout(metrics)
        root.addWidget(metrics_host)

        # ── Revenue chart (full width) ──
        revenue_card = SurfaceCard()
        revenue_card.setMinimumHeight(460)
        rev_header = QHBoxLayout()
        rev_title_col = QVBoxLayout()
        rev_title_col.setSpacing(2)
        self._rev_title = QLabel("Revenue Statistic")
        self._rev_title.setProperty("role", "card-title")
        self._rev_month_lbl = QLabel("")
        self._rev_month_lbl.setProperty("role", "muted")
        rev_title_col.addWidget(self._rev_title)
        rev_title_col.addWidget(self._rev_month_lbl)
        rev_header.addLayout(rev_title_col)
        legend = QHBoxLayout()
        self._rev_legend: list[tuple[QLabel, QLabel]] = []
        dot = QLabel("●")
        dot.setProperty("chart_color", ORANGE)
        lbl = QLabel("Amount Collected")
        self._rev_legend.append((dot, lbl))
        legend.addWidget(dot)
        legend.addWidget(lbl)
        legend.addStretch(1)
        rev_header.addLayout(legend)
        revenue_card.body.addLayout(rev_header)
        self._revenue_chart = RevenueChartWidget()
        revenue_card.body.addWidget(self._revenue_chart, 1)
        root.addWidget(revenue_card, 1)

        # ── Payment history (full width) ──
        payments_card = SurfaceCard()
        payments_card.body.addWidget(CardTitleBar("Payment History"))
        self._payments_host = QGridLayout()
        self._payments_host.setSpacing(0)
        self._payments_host.setContentsMargins(0, 0, 0, 0)
        self._payments_host.setColumnStretch(0, 1)
        self._payments_host.setColumnStretch(1, 1)
        self._payments_host.setColumnStretch(2, 1)
        payments_card.body.addLayout(self._payments_host)
        root.addWidget(payments_card)

        page = QVBoxLayout(self)
        page.setContentsMargins(0, 0, 0, 0)
        page.addWidget(scroll)
        scroll.setWidget(inner)
        self.reload()

    def _apply_revenue_chart(self, daily: dict) -> None:
        month_label = str(daily.get("month_label", ""))
        raw = daily.get("amounts")
        if raw is None:
            raw = daily.get("collected")
        amounts = list(raw or [])
        self._rev_month_lbl.setText(
            f"Daily collections — {month_label}" if month_label else "Daily collections"
        )
        self._revenue_chart.set_daily_collections(amounts, month_label=month_label)

    def _load_chart_from_backend(self, year: int, month: int) -> None:
        self._chart_year = year
        self._chart_month = month
        self._apply_revenue_chart(self._on_chart_data(year, month))

    def refresh_chart(self, chart_date: date | None = None) -> None:
        """Reload chart data from the database (e.g. after a new payment)."""
        if isinstance(chart_date, date):
            self._load_chart_from_backend(chart_date.year, chart_date.month)
        else:
            self._load_chart_from_backend(self._chart_year, self._chart_month)

    def refresh_theme(self) -> None:
        t = theme.current_tokens()
        logo_radius = self._brand_logo.width() // 2
        if self._brand_logo.pixmap() is None or self._brand_logo.pixmap().isNull():
            self._brand_logo.setStyleSheet(
                f"background: {t.primary}; color: white; border-radius: {logo_radius}px; "
                "font-size: 42px; font-weight: 800;"
            )
        else:
            self._brand_logo.setStyleSheet("background: transparent;")
        self._brand_accent.setStyleSheet(
            f"background: {t.primary}; border-radius: 2px; border: none;"
        )
        self._brand_motto.setStyleSheet(
            f"color: {t.text_muted}; font-size: 11px; font-weight: 700; "
            f"letter-spacing: 1.2px; background: transparent;"
        )
        self._brand_name.setStyleSheet(
            f"font-size: 26px; font-weight: 700; color: {t.text_primary}; "
            f"letter-spacing: 0.4px; background: transparent;"
        )
        self._rev_month_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 11px;")
        for dot, lbl in self._rev_legend:
            color = dot.property("chart_color") or ORANGE
            dot.setStyleSheet(f"color: {color}; font-size: 10px;")
            lbl.setStyleSheet(f"color: {t.text_secondary}; font-size: 11px;")
        for card in self._cards:
            card.refresh_theme()
        self._revenue_chart.refresh_theme()
        theme.refresh_widget_tree(self)
        self._load_chart_from_backend(self._chart_year, self._chart_month)

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_grid(self, layout: QGridLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def reload(self, chart_date: date | None = None) -> None:
        data = self._on_refresh()
        total = int(data.get("students_total", 0))
        active = int(data.get("students_active", 0))
        inactive = int(data.get("students_inactive", 0))
        years = int(data.get("academic_years_count", 0))
        collected_week = data.get("collected_week_display", "0")
        payments_week = int(data.get("payments_week", 0))
        payments_today = int(data.get("payments_today", 0))
        week_range = str(data.get("week_range", "—"))
        year_label = str(data.get("current_academic_year", "—"))[:32]
        today = data.get("today")
        today_s = today.strftime("%d %b %Y") if hasattr(today, "strftime") else "Today"

        self._cards[0].update_metric(
            str(active),
            f"{round(100 * active / max(total, 1))}% of {total} students",
        )
        self._cards[1].update_metric(
            str(inactive),
            f"{round(100 * inactive / max(total, 1))}% of {total} students",
        )
        self._cards[2].update_metric(str(years), year_label)
        self._cards[3].update_metric(f"₹{collected_week}", week_range)
        self._cards[4].update_metric(str(payments_week), week_range)
        self._cards[5].update_metric(str(payments_today), today_s)

        chart_ref = chart_date if isinstance(chart_date, date) else data.get("today")
        if isinstance(chart_ref, date):
            self._load_chart_from_backend(chart_ref.year, chart_ref.month)
        else:
            chart = data.get("revenue_chart") or {}
            self._apply_revenue_chart(chart)

        self._clear_grid(self._payments_host)
        cols = 3
        for i, p in enumerate(data.get("recent_payments", [])[:12]):
            self._payments_host.addWidget(
                ListRow(
                    p.get("initial", "P"),
                    p.get("name", ""),
                    f"₹{p.get('amount', 0):.2f} · {p.get('mode', '')}",
                    p.get("date", ""),
                ),
                i // cols,
                i % cols,
            )
