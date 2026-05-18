"""EduDash application shell: sidebar, top bar, stacked pages, FAB."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from frontend.ui.school_branding import load_logo_pixmap, school_motto, school_name
from frontend.ui import theme


@dataclass
class NavLeaf:
    label: str
    page_key: str


@dataclass
class NavGroup:
    label: str
    icon: str
    children: list[NavLeaf] = field(default_factory=list)
    page_key: str | None = None  # single-item groups


DEFAULT_NAV: list[NavGroup] = [
    NavGroup("Dashboard", "▣", page_key="Home Page"),
    NavGroup(
        "Students",
        "👥",
        children=[
            NavLeaf("Student List", "Student Search"),
            NavLeaf("Add New Student", "Add Student"),
            NavLeaf("Student Details", "Student Details"),
        ],
    ),
    NavGroup(
        "Fees Collection",
        "₹",
        children=[
            NavLeaf("Collect Payment", "Collect Payment"),
            NavLeaf("Payment History", "Payment History"),
        ],
    ),
    NavGroup("Reports", "📊", page_key="Reports"),
    NavGroup("Fee Control", "⚙", page_key="Fee Control"),
    NavGroup("Backup", "💾", page_key="Backup"),
]

_HIDE_TOP_SEARCH: frozenset[str] = frozenset({"Add Student"})


class _NavButton(QPushButton):
    def __init__(self, text: str, *, sub: bool = False, parent=None):
        super().__init__(text, parent)
        self._sub = sub
        self._active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self._apply(False)

    def set_active(self, active: bool) -> None:
        self._active = active
        self._apply(active)

    def refresh_theme(self) -> None:
        self._apply(self._active)

    def _apply(self, active: bool) -> None:
        t = theme.current_tokens()
        if active:
            if self._sub:
                self.setStyleSheet(
                    f"QPushButton {{ text-align: left; padding: 8px 12px 8px 36px; "
                    f"border: none; border-radius: 8px; color: {t.nav_active_text}; "
                    f"font-weight: 600; background: {t.nav_active_bg}; }}"
                )
            else:
                self.setStyleSheet(
                    f"QPushButton {{ text-align: left; padding: 10px 14px; "
                    f"border: none; border-radius: 10px; color: {t.text_on_primary}; "
                    f"font-weight: 600; background: {t.primary}; }}"
                )
        else:
            pad = "8px 12px 8px 36px" if self._sub else "10px 14px"
            self.setStyleSheet(
                f"QPushButton {{ text-align: left; padding: {pad}; border: none; "
                f"border-radius: 10px; color: {t.text_secondary}; font-weight: 500; "
                f"background: transparent; }}"
                f"QPushButton:hover {{ background: {t.nav_hover}; color: {t.text_primary}; }}"
            )


class _GroupHeader(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._expanded = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.refresh_theme()

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.refresh_theme()

    def refresh_theme(self) -> None:
        t = theme.current_tokens()
        if self._expanded:
            self.setStyleSheet(
                f"QPushButton {{ text-align: left; padding: 10px 14px; border: none; "
                f"border-radius: 10px; color: {t.nav_active_text}; font-weight: 600; "
                f"background: {t.nav_active_bg}; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ text-align: left; padding: 10px 14px; border: none; "
                f"border-radius: 10px; color: {t.text_secondary}; font-weight: 600; "
                f"background: transparent; }}"
                f"QPushButton:hover {{ background: {t.nav_hover}; }}"
            )


class AppShell(QWidget):
    page_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._page_keys: list[str] = []
        self._key_to_index: dict[str, int] = {}
        self._nav_buttons: dict[str, _NavButton] = {}
        self._group_frames: dict[str, QWidget] = {}
        self._group_headers: dict[str, _GroupHeader] = {}
        self._expanded: set[str] = set()

        root = QHBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        self._sidebar = QFrame()
        self._sidebar.setFixedWidth(272)
        side_outer = QVBoxLayout(self._sidebar)
        side_outer.setContentsMargins(0, 0, 0, 0)
        side_outer.setSpacing(0)

        brand = QWidget()
        brand_lay = QHBoxLayout(brand)
        brand_lay.setContentsMargins(20, 22, 20, 16)
        brand_lay.setSpacing(12)
        self._logo = QLabel()
        self._logo.setFixedSize(52, 52)
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = load_logo_pixmap(52)
        if pix is not None:
            self._logo.setPixmap(pix)
        else:
            self._logo.setText("A")
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self._school_name_lbl = QLabel(school_name())
        self._school_name_lbl.setWordWrap(True)
        self._motto_lbl = QLabel(school_motto())
        self._motto_lbl.setWordWrap(True)
        title_col.addWidget(self._school_name_lbl)
        title_col.addWidget(self._motto_lbl)
        brand_lay.addWidget(self._logo)
        brand_lay.addLayout(title_col, 1)
        side_outer.addWidget(brand)

        self._profile = QFrame()
        pl = QHBoxLayout(self._profile)
        pl.setContentsMargins(12, 10, 12, 10)
        self._profile_avatar = QLabel("A")
        self._profile_avatar.setFixedSize(40, 40)
        self._profile_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pi = QVBoxLayout()
        pi.setSpacing(0)
        self._profile_name = QLabel("Administrator")
        self._profile_role = QLabel("Fee desk")
        pi.addWidget(self._profile_name)
        pi.addWidget(self._profile_role)
        pl.addWidget(self._profile_avatar)
        pl.addLayout(pi, 1)
        self._profile_chev = QLabel("⌄")
        pl.addWidget(self._profile_chev)
        side_outer.addWidget(self._profile)

        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_host = QWidget()
        self._nav_layout = QVBoxLayout(nav_host)
        self._nav_layout.setContentsMargins(12, 4, 12, 16)
        self._nav_layout.setSpacing(2)
        nav_scroll.setWidget(nav_host)
        side_outer.addWidget(nav_scroll, 1)

        for group in DEFAULT_NAV:
            self._add_nav_group(group)

        self._nav_layout.addStretch(1)

        self._main = QWidget()
        main_lay = QVBoxLayout(self._main)
        main_lay.setContentsMargins(28, 20, 28, 20)
        main_lay.setSpacing(0)

        self._top = QFrame()
        top_row = QHBoxLayout(self._top)
        top_row.setContentsMargins(16, 10, 16, 10)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search")
        self._search.setClearButtonEnabled(True)
        self._search.setMinimumHeight(40)
        top_row.addWidget(self._search, 1)

        self._theme_btn = QPushButton("☀")
        self._theme_btn.setProperty("variant", "icon")
        self._theme_btn.setToolTip("Switch to dark theme")
        self._theme_btn.setFixedSize(40, 40)
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.clicked.connect(self._on_theme_toggle)
        top_row.addWidget(self._theme_btn)

        main_lay.addWidget(self._top)
        main_lay.addSpacing(20)

        content_scroll = QScrollArea()
        content_scroll.setWidgetResizable(True)
        content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._stack = QStackedWidget()
        content_scroll.setWidget(self._stack)
        main_lay.addWidget(content_scroll, 1)

        self._fab = QPushButton("⚙")
        self._fab.setParent(self._main)
        self._fab.setFixedSize(48, 48)
        self._fab.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fab.raise_()

        root.addWidget(self._sidebar)
        root.addWidget(self._main, 1)

        self.refresh_theme()

    def _on_theme_toggle(self) -> None:
        app = QApplication.instance()
        if app is not None:
            theme.toggle_theme(app)

    def refresh_theme(self) -> None:
        t = theme.current_tokens()
        mode = theme.current_theme_mode()

        self._sidebar.setStyleSheet(
            f"QFrame {{ background: {t.bg_sidebar}; border-right: 1px solid {t.border}; }}"
        )
        self._main.setStyleSheet(f"background: {t.bg_app};")
        self._top.setStyleSheet(
            f"QFrame {{ background: {t.bg_surface}; border: 1px solid {t.border}; "
            f"border-radius: 12px; }}"
        )

        if self._logo.pixmap() is None or self._logo.pixmap().isNull():
            self._logo.setStyleSheet(
                f"background: {t.primary}; color: white; border-radius: 26px; "
                "font-size: 22px; font-weight: 800;"
            )
        else:
            self._logo.setStyleSheet("background: transparent;")

        self._school_name_lbl.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {t.text_primary}; line-height: 1.2;"
        )
        self._motto_lbl.setStyleSheet(
            f"font-size: 10px; color: {t.text_muted}; font-weight: 600;"
        )

        self._profile.setStyleSheet(
            f"QFrame {{ background: {t.bg_app}; margin: 0 16px 12px 16px; "
            f"border-radius: 12px; border: 1px solid {t.border}; }}"
        )
        self._profile_avatar.setStyleSheet(
            f"background: {t.primary}; color: white; border-radius: 20px; font-weight: 700;"
        )
        self._profile_name.setStyleSheet(
            f"font-weight: 700; color: {t.text_primary}; background: transparent;"
        )
        self._profile_role.setStyleSheet(
            f"color: {t.text_muted}; font-size: 11px; background: transparent;"
        )
        self._profile_chev.setStyleSheet(f"color: {t.text_muted}; background: transparent;")

        self._fab.setStyleSheet(
            f"QPushButton {{ background: {t.primary}; color: white; border-radius: 24px; "
            f"font-size: 18px; border: none; }}"
            f"QPushButton:hover {{ background: {t.primary_dark}; }}"
        )

        self._theme_btn.setText("☀" if mode == "light" else "🌙")
        self._theme_btn.setToolTip(
            "Switch to dark theme" if mode == "light" else "Switch to light theme"
        )
        self._theme_btn.style().unpolish(self._theme_btn)
        self._theme_btn.style().polish(self._theme_btn)

        for btn in self._nav_buttons.values():
            btn.refresh_theme()
        for hdr in self._group_headers.values():
            hdr.refresh_theme()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        m = self._main.geometry()
        self._fab.move(m.right() - 64, m.bottom() - 64)

    def _add_nav_group(self, group: NavGroup) -> None:
        if group.page_key and not group.children:
            btn = _NavButton(f"  {group.icon}   {group.label}")
            btn.clicked.connect(lambda _=False, k=group.page_key: self.go(k))
            self._nav_layout.addWidget(btn)
            self._nav_buttons[group.page_key] = btn
            return

        header = _GroupHeader(f"  {group.icon}   {group.label}          ›")
        children_w = QWidget()
        child_lay = QVBoxLayout(children_w)
        child_lay.setContentsMargins(0, 0, 0, 0)
        child_lay.setSpacing(2)
        for leaf in group.children:
            sub = _NavButton(f"    {leaf.label}", sub=True)
            sub.clicked.connect(lambda _=False, k=leaf.page_key: self.go(k))
            child_lay.addWidget(sub)
            self._nav_buttons[leaf.page_key] = sub
        children_w.hide()
        self._group_frames[group.label] = children_w
        self._group_headers[group.label] = header

        def toggle(_=False, g=group.label, box=children_w, hdr=header):
            if g in self._expanded:
                self._expanded.discard(g)
                box.hide()
                hdr.set_expanded(False)
            else:
                self._expanded.add(g)
                box.show()
                hdr.set_expanded(True)

        header.clicked.connect(toggle)
        self._nav_layout.addWidget(header)
        self._nav_layout.addWidget(children_w)
        if group.label == "Students":
            self._expanded.add(group.label)
            children_w.show()
            header.set_expanded(True)

    def register_page(self, page_key: str, widget: QWidget) -> int:
        idx = self._stack.addWidget(widget)
        self._page_keys.append(page_key)
        self._key_to_index[page_key] = idx
        return idx

    def go(self, page_key: str) -> None:
        idx = self._key_to_index.get(page_key)
        if idx is None:
            return
        for group in DEFAULT_NAV:
            if group.children:
                for leaf in group.children:
                    if leaf.page_key == page_key:
                        box = self._group_frames.get(group.label)
                        hdr = self._group_headers.get(group.label)
                        if box is not None:
                            box.show()
                            self._expanded.add(group.label)
                        if hdr is not None:
                            hdr.set_expanded(True)
        self._stack.setCurrentIndex(idx)
        for key, btn in self._nav_buttons.items():
            btn.set_active(key == page_key)
        self._update_top_search_visibility(page_key)
        self.page_changed.emit(idx)

    def _update_top_search_visibility(self, page_key: str) -> None:
        self._search.setVisible(page_key not in _HIDE_TOP_SEARCH)

    def set_current_index(self, index: int) -> None:
        if 0 <= index < len(self._page_keys):
            self.go(self._page_keys[index])

    def set_current_by_name(self, tab_name: str) -> bool:
        if tab_name in self._key_to_index:
            self.go(tab_name)
            return True
        return False

    def current_index(self) -> int:
        return self._stack.currentIndex()

    def current_page_key(self) -> str:
        idx = self._stack.currentIndex()
        if 0 <= idx < len(self._page_keys):
            return self._page_keys[idx]
        return ""

    def count(self) -> int:
        return self._stack.count()

    def search_field(self) -> QLineEdit:
        return self._search

    def set_search_placeholder(self, text: str) -> None:
        self._search.setPlaceholderText(text)

    def add_page(self, tab_name: str, widget: QWidget, **_) -> int:
        return self.register_page(tab_name, widget)
