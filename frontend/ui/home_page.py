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
    CardTitleBar,
    ExpensesDonutChartWidget,
    ListRow,
    RevenueChartWidget,
    SolidMetricCard,
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
        on_expense_chart_data: Callable[[int, int], dict],
        on_manage_academic_years: Callable[[], None],
        on_chart_month_bounds: Callable[[], tuple[date | None, date | None]] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._on_navigate = on_navigate
        self._on_refresh = on_refresh
        self._on_chart_data = on_chart_data
        self._on_expense_chart_data = on_expense_chart_data
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
            SolidMetricCard("Total Active Students", "0", "—", 0),
            SolidMetricCard("Total Inactive Students", "0", "—", 1),
            SolidMetricCard("Academic Years", "0", "—", 2),
            SolidMetricCard("Amount Collected This Week", "0", "—", 3),
            SolidMetricCard("Payments Made This Week", "0", "—", 4),
            SolidMetricCard("Payments Made Today", "0", "—", 5),
        ]
        for i, card in enumerate(self._cards):
            card.setMinimumHeight(100)
            metrics.addWidget(card, i // 3, i % 3)
        metrics_host = QWidget()
        metrics_host.setLayout(metrics)
        root.addWidget(metrics_host)

        # ── Collections & expenses (single container, month filter) ──
        charts_card = SurfaceCard()
        charts_card.setMinimumHeight(480)
        charts_header = QHBoxLayout()
        charts_header.setSpacing(12)
        charts_title_col = QVBoxLayout()
        charts_title_col.setSpacing(2)
        self._charts_title = QLabel("Collections & Expenses Review")
        self._charts_title.setProperty("role", "card-title")
        self._charts_filter_hint = QLabel("Select a month to review payment collections and expenses.")
        self._charts_filter_hint.setProperty("role", "muted")
        charts_title_col.addWidget(self._charts_title)
        charts_title_col.addWidget(self._charts_filter_hint)
        charts_header.addLayout(charts_title_col, 1)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)
        filter_row.addWidget(QLabel("Month"))
        self._chart_month_cb = QComboBox()
        self._chart_month_cb.addItems(
            [
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ]
        )
        self._chart_month_cb.setMinimumHeight(36)
        self._chart_month_cb.setMinimumWidth(130)
        filter_row.addWidget(self._chart_month_cb)
        filter_row.addWidget(QLabel("Year"))
        self._chart_year_spin = QSpinBox()
        self._chart_year_spin.setRange(2000, today.year)
        self._chart_year_spin.setValue(today.year)
        self._chart_year_spin.setMinimumHeight(36)
        self._chart_year_spin.setMinimumWidth(88)
        filter_row.addWidget(self._chart_year_spin)
        charts_header.addLayout(filter_row)
        charts_card.body.addLayout(charts_header)

        charts_row = QHBoxLayout()
        charts_row.setSpacing(20)
        charts_row.setContentsMargins(0, 8, 0, 0)

        revenue_section = QVBoxLayout()
        revenue_section.setSpacing(8)
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
        dot_reverted = QLabel("●")
        dot_reverted.setProperty("chart_color", "danger")
        lbl_reverted = QLabel("Amount Reverted")
        self._rev_legend.append((dot_reverted, lbl_reverted))
        legend.addSpacing(10)
        legend.addWidget(dot_reverted)
        legend.addWidget(lbl_reverted)
        legend.addStretch(1)
        rev_header.addLayout(legend, 1)
        revenue_section.addLayout(rev_header)
        self._revenue_chart = RevenueChartWidget()
        revenue_section.addWidget(self._revenue_chart, 1)

        expenses_section = QVBoxLayout()
        expenses_section.setSpacing(8)
        exp_header = QHBoxLayout()
        exp_title_col = QVBoxLayout()
        exp_title_col.setSpacing(2)
        self._exp_title = QLabel("Expense Overview")
        self._exp_title.setProperty("role", "card-title")
        self._exp_month_lbl = QLabel("")
        self._exp_month_lbl.setProperty("role", "muted")
        exp_title_col.addWidget(self._exp_title)
        exp_title_col.addWidget(self._exp_month_lbl)
        exp_header.addLayout(exp_title_col)
        exp_header.addStretch(1)
        expenses_section.addLayout(exp_header)

        expense_body = QHBoxLayout()
        expense_body.setSpacing(16)
        self._expenses_chart = ExpensesDonutChartWidget()
        self._expenses_chart.setFixedSize(220, 220)
        expense_body.addWidget(self._expenses_chart, 0, Qt.AlignmentFlag.AlignVCenter)
        legend_col = QVBoxLayout()
        legend_col.setSpacing(8)
        self._exp_legend_host = QVBoxLayout()
        self._exp_legend_host.setSpacing(8)
        legend_col.addLayout(self._exp_legend_host)
        legend_col.addStretch(1)
        expense_body.addLayout(legend_col, 1)
        expenses_section.addLayout(expense_body, 1)

        revenue_host = QWidget()
        revenue_host.setLayout(revenue_section)
        expenses_host = QWidget()
        expenses_host.setLayout(expenses_section)
        charts_row.addWidget(revenue_host, 3)
        charts_row.addWidget(expenses_host, 2)
        charts_card.body.addLayout(charts_row, 1)
        root.addWidget(charts_card, 1)

        self._chart_month_cb.currentIndexChanged.connect(self._on_chart_filter_changed)
        self._chart_year_spin.valueChanged.connect(self._on_chart_filter_changed)
        self._sync_chart_filter_widgets()

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
            f"Daily collections and reversals — {month_label}" if month_label else "Daily collections and reversals"
        )
        self._revenue_chart.set_daily_collections(
            amounts,
            month_label=month_label,
            reverted_amounts=reverted_amounts,
        )

    def _apply_expense_chart(self, data: dict) -> None:
        month_label = str(data.get("month_label", ""))
        self._exp_month_lbl.setText(
            f"Salary and miscellaneous expenses — {month_label}"
            if month_label
            else "Salary and miscellaneous expenses"
        )
        self._expenses_chart.set_expense_breakdown(data)
        self._rebuild_expense_legend(self._expenses_chart.expense_slices())

    def _rebuild_expense_legend(self, slices: list[tuple[float, str, str]]) -> None:
        while self._exp_legend_host.count():
            item = self._exp_legend_host.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not slices:
            empty = QLabel("No expenses recorded this month.")
            empty.setProperty("role", "muted")
            self._exp_legend_host.addWidget(empty)
            return
        t = theme.current_tokens()
        for amount, color, label in slices:
            if amount <= 1e-6:
                continue
            item_row = QHBoxLayout()
            item_row.setSpacing(8)
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 12px; background: transparent;")
            name = QLabel(label)
            name.setStyleSheet(f"color: {t.text_primary}; font-size: 12px; background: transparent;")
            value = QLabel(f"₹{amount:,.0f}")
            value.setStyleSheet(
                f"color: {t.text_secondary}; font-size: 12px; font-weight: 600; background: transparent;"
            )
            item_row.addWidget(dot)
            item_row.addWidget(name)
            item_row.addStretch(1)
            item_row.addWidget(value)
            host = QWidget()
            host.setLayout(item_row)
            self._exp_legend_host.addWidget(host)

    def _load_chart_from_backend(self, year: int, month: int) -> None:
        self._chart_year = year
        self._chart_month = month
        self._apply_revenue_chart(self._on_chart_data(year, month))
        self._apply_expense_chart(self._on_expense_chart_data(year, month))

    def refresh_chart(self, chart_date: date | None = None) -> None:
        """Reload chart data from the database (e.g. after a new payment)."""
        if isinstance(chart_date, date):
            self._set_chart_month(chart_date.year, chart_date.month)
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
        self._exp_month_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 11px;")
        self._charts_filter_hint.setStyleSheet(f"color: {t.text_muted}; font-size: 11px;")
        for dot, lbl in self._rev_legend:
            color_prop = dot.property("chart_color")
            color = t.danger if color_prop == "danger" else (color_prop or ORANGE)
            dot.setStyleSheet(f"color: {color}; font-size: 10px;")
            lbl.setStyleSheet(f"color: {t.text_secondary}; font-size: 11px;")
        for card in self._cards:
            card.refresh_theme()
        self._revenue_chart.refresh_theme()
        self._expenses_chart.refresh_theme()
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
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

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

        self._configure_chart_filter_bounds()
        if isinstance(chart_date, date):
            self._set_chart_month(chart_date.year, chart_date.month)
        else:
            self._load_chart_from_backend(self._chart_year, self._chart_month)

        self._clear_grid(self._payments_host)
        cols = 3
        t = theme.current_tokens()
        for i, p in enumerate(data.get("recent_payments", [])[:12]):
            is_reverted = bool(p.get("is_reverted", False))
            status = str(p.get("status") or ("Payment reverted" if is_reverted else "Paid"))
            subtitle = f"₹{p.get('amount', 0):.2f} · {p.get('mode', '')}"
            if is_reverted:
                subtitle = f"{subtitle} · {status}"
            self._payments_host.addWidget(
                ListRow(
                    p.get("initial", "P"),
                    p.get("name", ""),
                    subtitle,
                    p.get("date", ""),
                    accent=t.text_muted if is_reverted else None,
                ),
                i // cols,
                i % cols,
            )
        self._revenue_chart.update()
        self._expenses_chart.update()
        self.update()
        self.repaint()
