"""EduDash-style main dashboard."""

from __future__ import annotations

from datetime import date
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from frontend.ui.edudash_widgets import (
    DashboardHeroStrip,
    DonutBreakdownCard,
    ListRow,
    RevenueChartWidget,
    SectionHeader,
    SolidMetricCard,
    SurfaceCard,
)
from frontend.ui import theme
from frontend.ui.school_branding import school_motto, school_name
from frontend.ui.theme import ORANGE


class HomePageTab(QWidget):
    def __init__(
        self,
        *,
        on_navigate: Callable[[str], None],
        on_refresh: Callable[[], dict],
        on_chart_data: Callable[[int, int], dict],
        on_expense_chart_data: Callable[[int, int], dict],
        on_income_chart_data: Callable[[int, int], dict] | None = None,
        on_manage_academic_years: Callable[[], None],
        on_chart_month_bounds: Callable[[], tuple[date | None, date | None]] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._on_navigate = on_navigate
        self._on_refresh = on_refresh
        self._on_chart_data = on_chart_data
        self._on_expense_chart_data = on_expense_chart_data
        self._on_income_chart_data = on_income_chart_data
        self._on_chart_month_bounds = on_chart_month_bounds
        self._on_manage_years = on_manage_academic_years
        today = date.today()
        self._chart_bounds_min = date(today.year, today.month, 1)
        self._chart_bounds_max = today
        self._syncing_chart_filter = False
        self._chart_year = today.year
        self._chart_month = today.month

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setContentsMargins(0, 0, 0, 8)
        root.setSpacing(20)

        # ── Compact hero ──
        self._hero = DashboardHeroStrip()
        self._hero.set_branding(
            name=school_name(),
            motto=school_motto(),
            device_pixel_ratio=self.devicePixelRatioF(),
        )
        root.addWidget(self._hero)

        # ── Key metrics (solid colour tiles) ──
        metrics = QGridLayout()
        metrics.setSpacing(14)
        metrics.setContentsMargins(0, 0, 0, 0)
        self._cards = [
            SolidMetricCard("Total Active Students", "0", "—", 0),
            SolidMetricCard("Total Faculty", "0", "—", 1),
            SolidMetricCard("Current Academic Year", "—", "—", 2),
            SolidMetricCard("Amount Collected This Week", "₹0", "—", 3),
            SolidMetricCard("Payments Made This Week", "0", "—", 4),
            SolidMetricCard("Payments Made Today", "0", "—", 5),
        ]
        for i, card in enumerate(self._cards):
            card.setMinimumHeight(100)
            metrics.addWidget(card, i // 3, i % 3)
        metrics_host = QWidget()
        metrics_host.setLayout(metrics)
        root.addWidget(metrics_host)

        # ── Monthly insights ──
        insights_header = QHBoxLayout()
        insights_header.setSpacing(16)
        self._insights_section = SectionHeader(
            "Monthly Insights",
            "Collections, expenses, and miscellaneous income for the selected period",
        )
        insights_header.addWidget(self._insights_section, 1)

        filter_box = QFrame()
        filter_box.setProperty("card", "surface")
        filter_lay = QHBoxLayout(filter_box)
        filter_lay.setContentsMargins(14, 10, 14, 10)
        filter_lay.setSpacing(10)
        period_lbl = QLabel("Period")
        period_lbl.setProperty("role", "muted")
        filter_lay.addWidget(period_lbl)
        self._chart_month_cb = QComboBox()
        self._chart_month_cb.addItems(
            [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December",
            ]
        )
        self._chart_month_cb.setMinimumHeight(34)
        self._chart_month_cb.setMinimumWidth(118)
        filter_lay.addWidget(self._chart_month_cb)
        self._chart_year_spin = QSpinBox()
        self._chart_year_spin.setRange(2000, today.year)
        self._chart_year_spin.setValue(today.year)
        self._chart_year_spin.setMinimumHeight(34)
        self._chart_year_spin.setMinimumWidth(80)
        filter_lay.addWidget(self._chart_year_spin)
        insights_header.addWidget(filter_box, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(insights_header)

        # Revenue — full width
        revenue_card = SurfaceCard()
        revenue_card.body.setSpacing(10)
        rev_top = QHBoxLayout()
        rev_top.setSpacing(12)
        rev_titles = QVBoxLayout()
        rev_titles.setSpacing(2)
        self._rev_title = QLabel("Daily Collections")
        self._rev_title.setProperty("role", "card-title")
        self._rev_month_lbl = QLabel("")
        self._rev_month_lbl.setProperty("role", "muted")
        rev_titles.addWidget(self._rev_title)
        rev_titles.addWidget(self._rev_month_lbl)
        rev_top.addLayout(rev_titles, 1)
        legend = QHBoxLayout()
        legend.setSpacing(14)
        self._rev_legend: list[tuple[QLabel, QLabel]] = []
        for color_key, label_text in (("chart_color", "Collected"), ("danger", "Reverted")):
            dot = QLabel("●")
            if color_key == "chart_color":
                dot.setProperty("chart_color", ORANGE)
            else:
                dot.setProperty("chart_color", "danger")
            lbl = QLabel(label_text)
            self._rev_legend.append((dot, lbl))
            legend.addWidget(dot)
            legend.addWidget(lbl)
        rev_top.addLayout(legend)
        revenue_card.body.addLayout(rev_top)
        self._revenue_chart = RevenueChartWidget()
        self._revenue_chart.setMinimumHeight(260)
        revenue_card.body.addWidget(self._revenue_chart)
        root.addWidget(revenue_card)

        # Expense + Income — side by side
        breakdown_row = QHBoxLayout()
        breakdown_row.setSpacing(14)
        self._expense_panel = DonutBreakdownCard("Expenses", center_caption="Total Expense")
        self._income_panel = DonutBreakdownCard("Income", center_caption="Total Income")
        breakdown_row.addWidget(self._expense_panel, 1)
        breakdown_row.addWidget(self._income_panel, 1)
        root.addLayout(breakdown_row)

        self._chart_month_cb.currentIndexChanged.connect(self._on_chart_filter_changed)
        self._chart_year_spin.valueChanged.connect(self._on_chart_filter_changed)
        self._sync_chart_filter_widgets()

        # ── Recent payments ──
        payments_card = SurfaceCard()
        pay_header = SectionHeader("Recent Payments", "Latest fee transactions across all students")
        payments_card.body.addWidget(pay_header)
        self._payments_host = QGridLayout()
        self._payments_host.setSpacing(8)
        self._payments_host.setContentsMargins(0, 4, 0, 0)
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

    def _configure_chart_filter_bounds(self) -> None:
        today = date.today()
        min_d: date | None = None
        max_d: date | None = today
        if self._on_chart_month_bounds is not None:
            min_d, max_d = self._on_chart_month_bounds()
        if max_d is None:
            max_d = today
        if min_d is None:
            min_d = date(today.year, today.month, 1)
        self._chart_bounds_min = date(min_d.year, min_d.month, 1)
        self._chart_bounds_max = max_d
        self._chart_year_spin.setMaximum(today.year)
        self._chart_year_spin.setMinimum(min_d.year)

    def _clamp_chart_month(self, year: int, month: int) -> tuple[int, int]:
        today = date.today()
        y, m = int(year), int(max(1, min(12, int(month))))
        if y > today.year or (y == today.year and m > today.month):
            return today.year, today.month
        earliest = self._chart_bounds_min
        if y < earliest.year or (y == earliest.year and m < earliest.month):
            return earliest.year, earliest.month
        return y, m

    def _sync_chart_filter_widgets(self) -> None:
        self._syncing_chart_filter = True
        try:
            self._chart_month_cb.setCurrentIndex(max(0, int(self._chart_month) - 1))
            self._chart_year_spin.setValue(int(self._chart_year))
        finally:
            self._syncing_chart_filter = False

    def _on_chart_filter_changed(self, *_args) -> None:
        if self._syncing_chart_filter:
            return
        year = int(self._chart_year_spin.value())
        month = int(self._chart_month_cb.currentIndex()) + 1
        self._set_chart_month(year, month)

    def _set_chart_month(self, year: int, month: int) -> None:
        y, m = self._clamp_chart_month(year, month)
        self._chart_year = y
        self._chart_month = m
        self._sync_chart_filter_widgets()
        self._load_chart_from_backend(y, m)

    def _apply_revenue_chart(self, daily: dict) -> None:
        month_label = str(daily.get("month_label", ""))
        raw = daily.get("amounts")
        if raw is None:
            raw = daily.get("collected")
        amounts = list(raw or [])
        reverted_amounts = list(daily.get("reverted_amounts") or [])
        self._rev_month_lbl.setText(
            month_label if month_label else "Daily payment activity"
        )
        self._revenue_chart.set_daily_collections(
            amounts,
            month_label=month_label,
            reverted_amounts=reverted_amounts,
        )

    def _apply_expense_chart(self, data: dict) -> None:
        month_label = str(data.get("month_label", ""))
        self._expense_panel.set_subtitle(
            f"Salary & miscellaneous — {month_label}" if month_label else "Salary & miscellaneous"
        )
        self._expense_panel.set_breakdown(data)

    def _apply_income_chart(self, data: dict) -> None:
        month_label = str(data.get("month_label", ""))
        self._income_panel.set_subtitle(
            f"By income source — {month_label}" if month_label else "By income source"
        )
        self._income_panel.set_breakdown(data)

    def _load_chart_from_backend(self, year: int, month: int) -> None:
        self._chart_year = year
        self._chart_month = month
        self._apply_revenue_chart(self._on_chart_data(year, month))
        self._apply_expense_chart(self._on_expense_chart_data(year, month))
        if self._on_income_chart_data is not None:
            self._apply_income_chart(self._on_income_chart_data(year, month))
        else:
            self._apply_income_chart({})

    def refresh_chart(self, chart_date: date | None = None) -> None:
        if isinstance(chart_date, date):
            self._set_chart_month(chart_date.year, chart_date.month)
        else:
            self._load_chart_from_backend(self._chart_year, self._chart_month)

    def refresh_theme(self) -> None:
        t = theme.current_tokens()
        self._hero.set_device_pixel_ratio(self.devicePixelRatioF())
        self._hero.refresh_theme()
        self._insights_section.refresh_theme()
        self._rev_month_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 11px;")
        for dot, lbl in self._rev_legend:
            color_prop = dot.property("chart_color")
            color = t.danger if color_prop == "danger" else (color_prop or ORANGE)
            dot.setStyleSheet(f"color: {color}; font-size: 10px; background: transparent;")
            lbl.setStyleSheet(f"color: {t.text_secondary}; font-size: 11px; background: transparent;")
        for card in self._cards:
            card.refresh_theme()
        self._revenue_chart.refresh_theme()
        self._expense_panel.refresh_theme()
        self._income_panel.refresh_theme()
        theme.refresh_widget_tree(self)
        self._load_chart_from_backend(self._chart_year, self._chart_month)

    def _clear_grid(self, layout: QGridLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def reload(self, chart_date: date | None = None) -> None:
        data = self._on_refresh()
        total = int(data.get("students_total", 0))
        active = int(data.get("students_active", 0))
        faculty_total = int(data.get("faculty_total", 0))
        faculty_active = int(data.get("faculty_active", 0))
        faculty_inactive = int(data.get("faculty_inactive", 0))
        collected_week = data.get("collected_week_display", "0")
        payments_week = int(data.get("payments_week", 0))
        payments_today = int(data.get("payments_today", 0))
        week_range = str(data.get("week_range", "—"))
        year_short = str(data.get("current_academic_year_short", "—"))
        year_range = str(data.get("current_academic_year_range", "—"))
        today = data.get("today")
        today_s = today.strftime("%d %b %Y") if hasattr(today, "strftime") else "Today"

        self._cards[0].update_metric(
            str(active),
            f"{round(100 * active / max(total, 1))}% of {total} students",
        )
        self._cards[1].update_metric(
            str(faculty_total),
            f"{faculty_active} active · {faculty_inactive} inactive",
        )
        self._cards[2].update_metric(year_short, year_range)
        self._cards[3].update_metric(f"₹{collected_week}", week_range)
        self._cards[4].update_metric(str(payments_week), week_range)
        self._cards[5].update_metric(str(payments_today), today_s)

        self._configure_chart_filter_bounds()
        if isinstance(chart_date, date):
            self._set_chart_month(chart_date.year, chart_date.month)
        else:
            self._load_chart_from_backend(self._chart_year, self._chart_month)

        self._clear_grid(self._payments_host)
        cols = 3
        tok = theme.current_tokens()
        for i, p in enumerate(data.get("recent_payments", [])[:12]):
            is_reverted = bool(p.get("is_reverted", False))
            status = str(p.get("status") or ("Payment reverted" if is_reverted else "Paid"))
            subtitle = f"₹{p.get('amount', 0):,.2f} · {p.get('mode', '')}"
            if is_reverted:
                subtitle = f"{subtitle} · {status}"
            self._payments_host.addWidget(
                ListRow(
                    p.get("initial", "P"),
                    p.get("name", ""),
                    subtitle,
                    p.get("date", ""),
                    accent=tok.text_muted if is_reverted else None,
                ),
                i // cols,
                i % cols,
            )
        self._revenue_chart.update()
        self.update()
        self.repaint()
