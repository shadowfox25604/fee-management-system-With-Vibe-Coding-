"""EduDash-style main dashboard."""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCalendarWidget,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from frontend.ui.edudash_widgets import (
    AttendanceBarWidget,
    BreadcrumbBar,
    CardTitleBar,
    DashMetricCard,
    ListRow,
    RevenueChartWidget,
    SurfaceCard,
)
from frontend.ui.school_branding import load_logo_pixmap, school_motto, school_name
from frontend.ui import theme
from frontend.ui.theme import GREEN, ORANGE, PURPLE, TEAL


class HomePageTab(QWidget):
    def __init__(
        self,
        *,
        on_navigate: Callable[[str], None],
        on_refresh: Callable[[], dict],
        on_manage_academic_years: Callable[[], None],
        parent=None,
    ):
        super().__init__(parent)
        self._on_navigate = on_navigate
        self._on_refresh = on_refresh
        self._on_manage_years = on_manage_academic_years

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(20)

        # Page header with school branding
        header = QWidget()
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(16)
        logo = QLabel()
        logo.setFixedSize(56, 56)
        pix = load_logo_pixmap(56)
        if pix is not None:
            logo.setPixmap(pix)
        header_text = QVBoxLayout()
        header_text.setSpacing(4)
        title = QLabel("Dashboard")
        title.setProperty("role", "page-title")
        header_text.addWidget(title)
        header_text.addWidget(
            BreadcrumbBar(
                [
                    school_name(),
                    f"{school_motto()} — manage students, fees, and collections.",
                ]
            )
        )
        header_row.addWidget(logo)
        header_row.addLayout(header_text, 1)
        root.addWidget(header)

        # ── 6 metric cards ──
        metrics = QGridLayout()
        metrics.setSpacing(16)
        self._cards = [
            DashMetricCard("Total Students", "0", "—", 0),
            DashMetricCard("Active Students", "0", "—", 1),
            DashMetricCard("Fee Defaulters", "0", "—", 2),
            DashMetricCard("Collected (₹)", "0", "—", 3),
            DashMetricCard("Academic Years", "0", "—", 4),
            DashMetricCard("Payments", "0", "—", 5),
        ]
        for i, card in enumerate(self._cards):
            metrics.addWidget(card, i // 3, i % 3)
        root.addLayout(metrics)

        # ── Middle row: revenue + attendance + calendar ──
        mid = QHBoxLayout()
        mid.setSpacing(16)

        revenue_card = SurfaceCard()
        revenue_card.setMinimumHeight(320)
        rev_header = QHBoxLayout()
        rev_header.addWidget(CardTitleBar("Revenue Statistic"))
        legend = QHBoxLayout()
        self._rev_legend: list[tuple[QLabel, QLabel]] = []
        for label, color in (("Total Fee", TEAL), ("Collected Fee", ORANGE)):
            dot = QLabel("●")
            dot.setProperty("chart_color", color)
            lbl = QLabel(label)
            self._rev_legend.append((dot, lbl))
            legend.addWidget(dot)
            legend.addWidget(lbl)
            legend.addSpacing(8)
        legend.addStretch(1)
        rev_header.addLayout(legend)
        revenue_card.body.addLayout(rev_header)
        self._revenue_chart = RevenueChartWidget()
        revenue_card.body.addWidget(self._revenue_chart, 1)
        mid.addWidget(revenue_card, 3)

        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        att_card = SurfaceCard()
        att_card.body.addWidget(CardTitleBar("Student Attendance"))
        self._att_bar = AttendanceBarWidget()
        att_card.body.addWidget(self._att_bar)
        self._att_legend: list[tuple[QLabel, QLabel]] = []
        for label, pct, color in [
            ("Present", "87%", TEAL),
            ("Absent", "13%", ORANGE),
            ("Late", "8%", PURPLE),
            ("Half day", "5%", GREEN),
        ]:
            row = QHBoxLayout()
            dot = QLabel("■")
            dot.setProperty("chart_color", color)
            lbl = QLabel(f"{label}: {pct}")
            self._att_legend.append((dot, lbl))
            row.addWidget(dot)
            row.addWidget(lbl)
            row.addStretch(1)
            att_card.body.addLayout(row)
        right_col.addWidget(att_card)

        cal_card = SurfaceCard()
        cal_card.body.addWidget(CardTitleBar("Calendar"))
        self._calendar = QCalendarWidget()
        self._calendar.setGridVisible(True)
        cal_card.body.addWidget(self._calendar)
        right_col.addWidget(cal_card)

        mid.addLayout(right_col, 2)
        root.addLayout(mid)

        # ── Bottom row: notice, leave, events ──
        bottom = QHBoxLayout()
        bottom.setSpacing(16)

        notice_card = SurfaceCard()
        notice_card.body.addWidget(CardTitleBar("Notice Board"))
        self._notice_host = QVBoxLayout()
        notice_card.body.addLayout(self._notice_host)
        bottom.addWidget(notice_card, 1)

        leave_card = SurfaceCard()
        leave_card.body.addWidget(CardTitleBar("Recent Payments"))
        self._leave_host = QVBoxLayout()
        leave_card.body.addLayout(self._leave_host)
        bottom.addWidget(leave_card, 1)

        events_card = SurfaceCard()
        events_card.body.addWidget(CardTitleBar("Upcoming Events"))
        self._events_host = QVBoxLayout()
        events_card.body.addLayout(self._events_host)
        bottom.addWidget(events_card, 1)

        root.addLayout(bottom, 1)
        self.reload()

    def refresh_theme(self) -> None:
        t = theme.current_tokens()
        for dot, lbl in self._rev_legend:
            color = dot.property("chart_color") or TEAL
            dot.setStyleSheet(f"color: {color}; font-size: 10px;")
            lbl.setStyleSheet(f"color: {t.text_secondary}; font-size: 11px;")
        for dot, lbl in self._att_legend:
            color = dot.property("chart_color") or TEAL
            dot.setStyleSheet(f"color: {color};")
            lbl.setStyleSheet(f"color: {t.text_secondary}; font-size: 11px;")
        for card in self._cards:
            card.refresh_theme()
        self._revenue_chart.refresh_theme()
        self._att_bar.refresh_theme()
        theme.refresh_widget_tree(self)

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def reload(self) -> None:
        data = self._on_refresh()
        total = int(data.get("students_total", 0))
        active = int(data.get("students_active", 0))
        defaulters = int(data.get("defaulters_count", 0))
        collected = data.get("collected_display", "0")
        years = int(data.get("academic_years_count", 0))
        payments = int(data.get("payments_count", 0))

        self._cards[0].update_metric(str(total), f"{active} active")
        self._cards[1].update_metric(str(active), f"{round(100*active/max(total,1))}% of total")
        self._cards[2].update_metric(str(defaulters), "Outstanding balance")
        self._cards[3].update_metric(str(collected), "This session")
        self._cards[4].update_metric(str(years), str(data.get("current_academic_year", "—"))[:28])
        self._cards[5].update_metric(str(payments), "Recorded")

        chart = data.get("revenue_chart") or {}
        self._revenue_chart.set_data(
            chart.get("total", [40] * 12),
            chart.get("collected", [25] * 12),
        )

        # Notice board — fee tips
        self._clear_layout(self._notice_host)
        for title, text, who in data.get("notices", [])[:4]:
            self._notice_host.addWidget(ListRow("A", who, text, title))

        self._clear_layout(self._leave_host)
        for p in data.get("recent_payments", [])[:5]:
            self._leave_host.addWidget(
                ListRow(
                    p.get("initial", "P"),
                    p.get("name", ""),
                    f"₹{p.get('amount', 0):.2f} · {p.get('mode', '')}",
                    p.get("date", ""),
                )
            )

        self._clear_layout(self._events_host)
        for ev in data.get("events", [])[:4]:
            self._events_host.addWidget(
                ListRow(
                    "E",
                    ev.get("title", ""),
                    ev.get("subtitle", ""),
                    ev.get("time", ""),
                    accent=ev.get("color", theme.PRIMARY),
                )
            )
