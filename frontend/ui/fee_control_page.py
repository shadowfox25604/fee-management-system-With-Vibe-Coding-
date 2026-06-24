"""Fee Control — school class tariffs and village van fees (EduDash layout)."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from backend.core.fee_control_constants import FIXED_CLASS_KEYS
from backend.services.academic_year_service import AcademicYearService
from backend.services.class_fee_service import ClassFeeService
from backend.services.village_van_fee_service import VillageVanFeeService
from frontend.ui import theme
from frontend.ui.edudash_widgets import CardTitleBar, SolidMetricCard, SurfaceCard
from frontend.ui.table_style import fee_action_button_width, style_fee_action_button

_AMOUNT_W = 132
_APPLY_MIN = 88
_ROW_H = 44
_PAD = 12


def _class_label(key: str) -> str:
    return key if key in ("Nursery", "LKG", "UKG") else f"Class {key}"


def _apply_w() -> int:
    return fee_action_button_width(QPushButton("Apply"), min_width=_APPLY_MIN)


class _ScrollList(QScrollArea):
    """Scroll area that keeps content at viewport width."""

    def __init__(self, body: QWidget, parent=None):
        super().__init__(parent)
        self._body = body
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setWidget(body)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._body.setMinimumWidth(max(0, self.viewport().width()))


class _TariffList(QWidget):
    def __init__(self, *, header: str, on_apply: Callable[[str], None], parent=None):
        super().__init__(parent)
        self._on_apply = on_apply
        self._header = header
        self.amount_edits: dict[str, QLineEdit] = {}
        self._apply_btns: dict[str, QPushButton] = {}
        self._rows: dict[str, QWidget] = {}
        self._labels: dict[str, str] = {}
        self._apply_w = _apply_w()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._hdr = QWidget()
        h = QHBoxLayout(self._hdr)
        h.setContentsMargins(_PAD, 8, _PAD, 8)
        h.setSpacing(12)
        left = QLabel(header)
        left.setProperty("role", "muted")
        left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        fee = QLabel("Annual fee (₹)")
        fee.setProperty("role", "muted")
        fee.setFixedWidth(_AMOUNT_W)
        fee.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        spacer = QWidget()
        spacer.setFixedWidth(self._apply_w)
        h.addWidget(left, 1)
        h.addWidget(fee)
        h.addWidget(spacer)
        root.addWidget(self._hdr)

        self._body = QWidget()
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(0, 0, 0, 0)
        self._body_lay.setSpacing(0)
        self._scroll = _ScrollList(self._body)
        root.addWidget(self._scroll, 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_items(self, items: list[tuple[str, str]]) -> None:
        while self._body_lay.count():
            item = self._body_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.amount_edits.clear()
        self._apply_btns.clear()
        self._rows.clear()
        self._labels.clear()

        for i, (key, label) in enumerate(items):
            self._labels[key] = label
            alt = bool(i % 2)
            row = QWidget()
            row.setObjectName("feeTariffRow")
            row.setFixedHeight(_ROW_H)
            row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            lay = QHBoxLayout(row)
            lay.setContentsMargins(_PAD, 4, _PAD, 4)
            lay.setSpacing(12)

            name = QLabel(label)
            name.setMinimumWidth(0)
            name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

            edit = QLineEdit()
            edit.setPlaceholderText("0.00")
            edit.setAlignment(Qt.AlignmentFlag.AlignRight)
            edit.setFixedSize(_AMOUNT_W, 34)

            btn = QPushButton("Apply")
            btn.setObjectName("feeApplyBtn")
            style_fee_action_button(btn, width=self._apply_w)
            btn.clicked.connect(lambda _=False, k=key: self._on_apply(k))

            lay.addWidget(name, 1)
            lay.addWidget(edit)
            lay.addWidget(btn)

            row._alt = alt  # type: ignore[attr-defined]
            self._body_lay.addWidget(row)
            self.amount_edits[key] = edit
            self._apply_btns[key] = btn
            self._rows[key] = row

        self.refresh_theme()

    def filter_rows(self, needle: str) -> int:
        q = (needle or "").strip().lower()
        n = 0
        for key, row in self._rows.items():
            show = not q or q in self._labels[key].lower() or q in key.lower()
            row.setVisible(show)
            if show:
                n += 1
        return n

    def set_read_only(self, locked: bool) -> None:
        for edit in self.amount_edits.values():
            edit.setReadOnly(locked)
        for btn in self._apply_btns.values():
            btn.setEnabled(not locked)

    def refresh_theme(self) -> None:
        t = theme.current_tokens()
        self._apply_w = _apply_w()
        self._hdr.setStyleSheet(
            f"background: {t.table_header_bg}; border-bottom: 1px solid {t.border};"
        )
        hdr_lay = self._hdr.layout()
        if isinstance(hdr_lay, QHBoxLayout) and hdr_lay.count() >= 3:
            w = hdr_lay.itemAt(2).widget()
            if w is not None:
                w.setFixedWidth(self._apply_w)
        for key, row in self._rows.items():
            bg = t.table_alt_row if getattr(row, "_alt", False) else t.bg_surface
            row.setStyleSheet(
                f"QWidget#feeTariffRow {{ background: {bg}; border: none; "
                f"border-bottom: 1px solid {t.border_light}; }}"
            )
            btn = row.findChild(QPushButton, "feeApplyBtn")
            if btn is not None:
                style_fee_action_button(btn, width=self._apply_w)


class _SegBtn(QPushButton):
    def __init__(self, text: str, *, active: bool = False, parent=None):
        super().__init__(text, parent)
        self._active = active
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.refresh()

    def set_active(self, on: bool) -> None:
        self._active = on
        self.refresh()

    def refresh(self) -> None:
        if self._active:
            style_fee_action_button(self, width=fee_action_button_width(self, min_width=128))
            return
        t = theme.current_tokens()
        self.setObjectName("feeSegInactive")
        w = max(128, self.fontMetrics().horizontalAdvance(self.text()) + 44)
        self.setFixedSize(w, 36)
        self.setStyleSheet(
            f"QPushButton#feeSegInactive {{ background: transparent; color: {t.text_secondary}; "
            f"border: none; border-radius: 18px; font-weight: 600; }}"
            f"QPushButton#feeSegInactive:hover {{ background: {t.bg_hover}; color: {t.text_primary}; }}"
        )


class FeeControlPage(QWidget):
    def __init__(
        self,
        *,
        class_fee_service: ClassFeeService,
        village_van_fee_service: VillageVanFeeService,
        academic_year_service: AcademicYearService,
        on_apply_school: Callable[[str], None],
        on_apply_van: Callable[[str], None],
        on_manage_years: Callable[[], None],
        on_add_village: Callable[[], None],
        parent=None,
    ):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._class_svc = class_fee_service
        self._van_svc = village_van_fee_service
        self._year_svc = academic_year_service

        self.fee_control_amount_edits: dict[str, QLineEdit] = {}
        self._van_edits: dict[str, QLineEdit] = {}
        self.fee_control_table = None
        self.van_fee_control_table = None
        self.add_village_btn: QPushButton | None = None
        self._van_keys: list[str] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self._fc_banner = self._banner()
        lay.addWidget(self._fc_banner)
        lay.addLayout(self._metrics())
        self._fc_segment = self._segment_bar(on_manage_years)
        lay.addWidget(self._fc_segment)

        self._stack = QStackedWidget()
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._stack.addWidget(self._school_panel(on_apply_school))
        self._stack.addWidget(self._van_panel(on_apply_van, on_add_village))
        lay.addWidget(self._stack, 1)

        self._pick(0)
        self.reload_stats()
        self.refresh_amounts()
        self.refresh_theme()

    @property
    def van_fee_control_amount_edits(self) -> dict[str, QLineEdit]:
        return self._van_edits

    @property
    def manage_years_btn(self) -> QPushButton:
        return self._years_btn

    def _banner(self) -> QFrame:
        f = QFrame()
        f.setObjectName("fcBanner")
        v = QVBoxLayout(f)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(4)
        t = QLabel("Set school and van fees independently for each academic year")
        t.setObjectName("fcBannerTitle")
        b = QLabel(
            "Choose an academic year, then set class and village tariffs for that session. "
            "Apply updates the stored tariff and each enrolled student’s fee record for that year. "
            "When you add the next academic year, current tariffs are copied forward automatically. "
            "Ended academic years are locked."
        )
        b.setWordWrap(True)
        b.setObjectName("fcBannerBody")
        v.addWidget(t)
        v.addWidget(b)
        return f

    def _metrics(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        self._m_classes = SolidMetricCard("Classes", "—", f"{len(FIXED_CLASS_KEYS)} tiers", 3)
        self._m_villages = SolidMetricCard("Villages", "—", "Van routes", 1)
        self._m_year = SolidMetricCard("Academic year", "—", "Current session", 2)
        for c in (self._m_classes, self._m_villages, self._m_year):
            c.setMinimumHeight(96)
            c.setMaximumHeight(100)
            c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.addWidget(c, 1)
        return row

    def _segment_bar(self, on_manage) -> QFrame:
        f = QFrame()
        f.setObjectName("fcSegment")
        h = QHBoxLayout(f)
        h.setContentsMargins(8, 8, 8, 8)
        h.setSpacing(6)
        self._seg_school = _SegBtn("School fees by class", active=True)
        self._seg_van = _SegBtn("Van fees by village")
        self._seg_school.clicked.connect(lambda: self._pick(0))
        self._seg_van.clicked.connect(lambda: self._pick(1))
        self._hint = QLabel("")
        self._hint.setProperty("role", "muted")
        h.addWidget(self._seg_school)
        h.addWidget(self._seg_van)
        h.addWidget(self._hint)
        h.addStretch(1)
        self._years_btn = QPushButton("Manage academic years")
        style_fee_action_button(
            self._years_btn,
            width=fee_action_button_width(self._years_btn, min_width=168),
        )
        self._years_btn.setToolTip(
            "Academic years use automatic 31 May → 1 June ranges (e.g. 2025-2026). "
            "Add the next year from Manage academic years. Forward rollover promotes students one class "
            "and carries pending fees into the new year."
        )
        self._years_btn.clicked.connect(on_manage)
        h.addWidget(self._years_btn)
        return f

    def _card(self, card: SurfaceCard) -> None:
        card.body.setContentsMargins(0, 0, 0, 0)
        card.body.setSpacing(0)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _card_head(self, title: str, hint: str) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(20, 14, 20, 8)
        v.setSpacing(6)
        v.addWidget(CardTitleBar(title))
        h = QLabel(hint)
        h.setWordWrap(True)
        h.setProperty("role", "hint")
        v.addWidget(h)
        return w

    def _school_panel(self, on_apply) -> QWidget:
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 0, 0, 0)
        card = SurfaceCard()
        self._card(card)
        card.body.addWidget(
            self._card_head(
                "School fee tariffs",
                "Annual school fee per class for the selected academic year.",
            )
        )
        year_bar = QWidget()
        yh = QHBoxLayout(year_bar)
        yh.setContentsMargins(20, 0, 20, 8)
        yh.setSpacing(10)
        year_lbl = QLabel("Academic year")
        year_lbl.setProperty("role", "field-label")
        self._school_year_combo = QComboBox()
        self._school_year_combo.setMinimumHeight(36)
        self._school_year_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._school_year_combo.currentIndexChanged.connect(self._on_school_year_changed)
        self._year_lock_hint = QLabel("")
        self._year_lock_hint.setProperty("role", "hint")
        self._year_lock_hint.setWordWrap(True)
        yh.addWidget(year_lbl)
        yh.addWidget(self._school_year_combo, 1)
        card.body.addWidget(year_bar)
        card.body.addWidget(self._year_lock_hint)
        self._school_list = _TariffList(header="Class", on_apply=on_apply)
        items = [(k, _class_label(k)) for k in FIXED_CLASS_KEYS]
        self._school_list.set_items(items)
        self.fee_control_amount_edits = self._school_list.amount_edits
        card.body.addWidget(self._school_list, 1)
        v.addWidget(card, 1)
        return p

    def _van_panel(self, on_apply, on_add) -> QWidget:
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 0, 0, 0)
        card = SurfaceCard()
        self._card(card)
        card.body.addWidget(
            self._card_head(
                "Van fee tariffs",
                "Per-village van rates for the selected academic year. Own-transport students are skipped.",
            )
        )
        year_bar = QWidget()
        yh = QHBoxLayout(year_bar)
        yh.setContentsMargins(20, 0, 20, 8)
        yh.setSpacing(10)
        year_lbl = QLabel("Academic year")
        year_lbl.setProperty("role", "field-label")
        self._van_year_combo = QComboBox()
        self._van_year_combo.setMinimumHeight(36)
        self._van_year_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._van_year_combo.currentIndexChanged.connect(self._on_van_year_changed)
        self._van_year_lock_hint = QLabel("")
        self._van_year_lock_hint.setProperty("role", "hint")
        self._van_year_lock_hint.setWordWrap(True)
        yh.addWidget(year_lbl)
        yh.addWidget(self._van_year_combo, 1)
        card.body.addWidget(year_bar)
        card.body.addWidget(self._van_year_lock_hint)
        tool = QWidget()
        th = QHBoxLayout(tool)
        th.setContentsMargins(20, 0, 20, 8)
        th.setSpacing(8)
        self._van_search = QLineEdit()
        self._van_search.setPlaceholderText("Search villages…")
        self._van_search.setClearButtonEnabled(True)
        self._van_search.setMinimumHeight(36)
        self._van_search.textChanged.connect(self._on_van_filter)
        th.addWidget(QLabel("Filter"))
        th.addWidget(self._van_search, 1)
        self.add_village_btn = QPushButton("Add village")
        style_fee_action_button(
            self.add_village_btn,
            width=fee_action_button_width(self.add_village_btn, min_width=112),
        )
        self.add_village_btn.clicked.connect(on_add)
        th.addWidget(self.add_village_btn)
        card.body.addWidget(tool)

        self._van_list = _TariffList(header="Village", on_apply=on_apply)
        self._rebuild_van()
        card.body.addWidget(self._van_list, 1)
        v.addWidget(card, 1)
        return p

    @property
    def selected_academic_year_id(self) -> int | None:
        data = self._school_year_combo.currentData()
        return int(data) if data is not None else None

    @property
    def selected_van_academic_year_id(self) -> int | None:
        data = self._van_year_combo.currentData()
        return int(data) if data is not None else None

    @property
    def selected_year_editable(self) -> bool:
        year_id = self.selected_academic_year_id
        if year_id is None:
            return False
        return self._class_svc.is_year_tariff_editable(year_id)

    @property
    def selected_van_year_editable(self) -> bool:
        year_id = self.selected_van_academic_year_id
        if year_id is None:
            return False
        return self._van_svc.is_year_tariff_editable(year_id)

    def _reload_school_year_combo(self) -> None:
        years = self._class_svc.list_years_for_fee_control()
        current = self._year_svc.get_current()
        prev_id = self.selected_academic_year_id
        self._school_year_combo.blockSignals(True)
        self._school_year_combo.clear()
        from backend.core.academic_year_dates import format_academic_year_range

        for year in years:
            label = self._year_svc.format_year_short_label(year)
            detail = format_academic_year_range(year.start_date, year.end_date)
            self._school_year_combo.addItem(f"{label}  ({detail})", year.id)
        if prev_id is not None:
            idx = self._school_year_combo.findData(prev_id)
            if idx >= 0:
                self._school_year_combo.setCurrentIndex(idx)
        elif current is not None:
            idx = self._school_year_combo.findData(current.id)
            if idx >= 0:
                self._school_year_combo.setCurrentIndex(idx)
        self._school_year_combo.blockSignals(False)
        self._update_school_year_lock_state()
        self._reload_van_year_combo()

    def _reload_van_year_combo(self) -> None:
        years = self._van_svc.list_years_for_fee_control()
        current = self._year_svc.get_current()
        prev_id = self.selected_van_academic_year_id
        self._van_year_combo.blockSignals(True)
        self._van_year_combo.clear()
        from backend.core.academic_year_dates import format_academic_year_range

        for year in years:
            label = self._year_svc.format_year_short_label(year)
            detail = format_academic_year_range(year.start_date, year.end_date)
            self._van_year_combo.addItem(f"{label}  ({detail})", year.id)
        if prev_id is not None:
            idx = self._van_year_combo.findData(prev_id)
            if idx >= 0:
                self._van_year_combo.setCurrentIndex(idx)
        elif current is not None:
            idx = self._van_year_combo.findData(current.id)
            if idx >= 0:
                self._van_year_combo.setCurrentIndex(idx)
        self._van_year_combo.blockSignals(False)
        self._update_van_year_lock_state()

    def _on_school_year_changed(self, _index: int) -> None:
        self._update_school_year_lock_state()
        self.refresh_school_amounts()

    def _on_van_year_changed(self, _index: int) -> None:
        self._update_van_year_lock_state()
        self._rebuild_van()
        self.refresh_van_amounts()

    def _update_school_year_lock_state(self) -> None:
        editable = self.selected_year_editable
        self._school_list.set_read_only(not editable)
        if not self.selected_academic_year_id:
            self._year_lock_hint.setText("Add an academic year before setting class fees.")
        elif editable:
            self._year_lock_hint.setText(
                "Fees for this session can be edited before and during the academic year."
            )
        else:
            self._year_lock_hint.setText(
                "This academic year has ended — class fees are locked and cannot be changed."
            )

    def _update_van_year_lock_state(self) -> None:
        editable = self.selected_van_year_editable
        self._van_list.set_read_only(not editable)
        if self.add_village_btn is not None:
            self.add_village_btn.setEnabled(editable)
        if not self.selected_van_academic_year_id:
            self._van_year_lock_hint.setText("Add an academic year before setting village van fees.")
        elif editable:
            self._van_year_lock_hint.setText(
                "Van fees for this session can be edited before and during the academic year."
            )
        else:
            self._van_year_lock_hint.setText(
                "This academic year has ended — village van fees are locked and cannot be changed."
            )

    def _pick(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        self._seg_school.set_active(idx == 0)
        self._seg_van.set_active(idx == 1)
        if idx == 0:
            self._hint.setText(f"{len(FIXED_CLASS_KEYS)} classes")
        else:
            self._hint.setText(f"{len(self._van_keys)} villages")

    def _on_van_filter(self, text: str) -> None:
        if self._stack.currentIndex() != 1:
            return
        n = self._van_list.filter_rows(text)
        total = len(self._van_keys)
        q = (text or "").strip()
        self._hint.setText(f"{n} of {total} villages" if q else f"{total} villages")

    def _rebuild_van(self) -> None:
        year_id = self.selected_van_academic_year_id
        keys = self._van_svc.list_village_keys_for_fee_control(year_id)
        self._van_keys = list(keys)
        self._van_list.set_items([(k, k) for k in keys])
        self._van_edits = self._van_list.amount_edits

    def rebuild_van_table(self) -> None:
        self._rebuild_van()
        self.refresh_van_amounts()
        self._on_van_filter(self._van_search.text() if hasattr(self, "_van_search") else "")
        self.reload_stats()

    def refresh_school_amounts(self) -> None:
        year_id = self.selected_academic_year_id
        for k, e in self.fee_control_amount_edits.items():
            e.setText(f"{self._class_svc.display_amount_for_class(k, year_id):.2f}")

    def refresh_van_amounts(self) -> None:
        year_id = self.selected_van_academic_year_id
        for k, e in self._van_edits.items():
            e.setText(f"{self._van_svc.display_amount_for_village(k, year_id):.2f}")

    def refresh_amounts(self) -> None:
        self.refresh_school_amounts()
        self.refresh_van_amounts()
        self.reload_stats()

    def reload_stats(self) -> None:
        self._reload_school_year_combo()
        n_v = len(self._van_svc.list_village_keys_for_fee_control(self.selected_van_academic_year_id))
        self._m_classes.update_metric(str(len(FIXED_CLASS_KEYS)), "Nursery → Class 10")
        self._m_villages.update_metric(str(n_v), "Van transport routes")
        cur = self._year_svc.get_current()
        if cur is not None:
            from backend.core.academic_year_dates import format_academic_year_range

            lbl = self._year_svc.format_year_short_label(cur)
            det = format_academic_year_range(cur.start_date, cur.end_date)
        else:
            lbl, det = "Not set", "Define an academic year range"
        self._m_year.update_metric(lbl, det)

    def refresh_theme(self) -> None:
        t = theme.current_tokens()
        banner = self.findChild(QFrame, "fcBanner")
        if banner is not None:
            banner.setStyleSheet(
                f"QFrame#fcBanner {{ background: {t.primary_soft}; "
                f"border: 1px solid {t.primary_light}; border-radius: 12px; }}"
                f"QLabel#fcBannerTitle {{ color: {t.text_primary}; font-size: 14px; "
                f"font-weight: 700; background: transparent; }}"
                f"QLabel#fcBannerBody {{ color: {t.text_secondary}; font-size: 12px; "
                f"background: transparent; }}"
            )
        seg = self.findChild(QFrame, "fcSegment")
        if seg is not None:
            seg.setStyleSheet(
                f"QFrame#fcSegment {{ background: {t.bg_section_header}; "
                f"border: 1px solid {t.border}; border-radius: 12px; }}"
            )
        self._seg_school.refresh()
        self._seg_van.refresh()
        style_fee_action_button(
            self._years_btn,
            width=fee_action_button_width(self._years_btn, min_width=168),
        )
        if self.add_village_btn is not None:
            style_fee_action_button(
                self.add_village_btn,
                width=fee_action_button_width(self.add_village_btn, min_width=112),
            )
        for c in (self._m_classes, self._m_villages, self._m_year):
            c.refresh_theme()
        if hasattr(self, "_school_list"):
            self._school_list.refresh_theme()
        if hasattr(self, "_van_list"):
            self._van_list.refresh_theme()
        theme.refresh_widget_tree(self)
        self._reapply_buttons()

    def _reapply_buttons(self) -> None:
        self._seg_school.refresh()
        self._seg_van.refresh()
        style_fee_action_button(
            self._years_btn,
            width=fee_action_button_width(self._years_btn, min_width=168),
        )
        if self.add_village_btn is not None:
            style_fee_action_button(
                self.add_village_btn,
                width=fee_action_button_width(self.add_village_btn, min_width=112),
            )
        if hasattr(self, "_school_list"):
            self._school_list.refresh_theme()
        if hasattr(self, "_van_list"):
            self._van_list.refresh_theme()
