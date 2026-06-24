"""EduDash application shell: sidebar, stacked pages, FAB."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from frontend.ui import theme
from frontend.ui.theme_toggle import ThemeToggleWidget


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
    NavGroup(
        "Expenses",
        "💸",
        children=[
            NavLeaf("Salary", "Salary"),
            NavLeaf("Salary History", "Salary History"),
            NavLeaf("Miscellaneous", "Miscellaneous"),
            NavLeaf("Income Management", "Income Management"),
        ],
    ),
    NavGroup(
        "Admin Control",
        "🛡",
        children=[
            NavLeaf("Add Student", "Add Student"),
            NavLeaf("Add Faculty", "Add Faculty"),
            NavLeaf("Delete Member", "Delete Member"),
            NavLeaf("Salary Control", "Salary Control"),
            NavLeaf("Fee Control", "Fee Control"),
            NavLeaf("Login Access", "Login Access"),
        ],
    ),
    NavGroup("Reports", "📊", page_key="Reports"),
    NavGroup("Backup", "💾", page_key="Backup"),
]

ACCOUNTANT_NAV: list[NavGroup] = [
    NavGroup("Collect Payment", "₹", page_key="Collect Payment"),
    NavGroup("Miscellaneous", "💸", page_key="Miscellaneous"),
    NavGroup("Income Management", "📥", page_key="Income Management"),
]


def navigation_for_role(role: str) -> list[NavGroup]:
    from backend.core.app_roles import ROLE_ACCOUNTANT

    if role == ROLE_ACCOUNTANT:
        return list(ACCOUNTANT_NAV)
    return list(DEFAULT_NAV)


_NAV_ACTIVE_RADIUS = "8px"


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
        pad = "8px 12px 8px 36px" if self._sub else "10px 14px"
        if active:
            self.setStyleSheet(
                f"QPushButton {{ text-align: left; padding: {pad}; "
                f"border: none; border-radius: {_NAV_ACTIVE_RADIUS}; color: {t.text_on_primary}; "
                f"font-weight: 700; background: {t.primary}; }}"
                f"QPushButton:hover {{ background: {t.primary_dark}; color: {t.text_on_primary}; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ text-align: left; padding: {pad}; border: none; "
                f"border-radius: {_NAV_ACTIVE_RADIUS}; color: {t.text_secondary}; font-weight: 500; "
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
                f"border-radius: {_NAV_ACTIVE_RADIUS}; color: {t.text_primary}; font-weight: 600; "
                f"background: {t.nav_hover}; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ text-align: left; padding: 10px 14px; border: none; "
                f"border-radius: {_NAV_ACTIVE_RADIUS}; color: {t.text_secondary}; font-weight: 600; "
                f"background: transparent; }}"
                f"QPushButton:hover {{ background: {t.nav_hover}; color: {t.text_primary}; }}"
            )


class AppShell(QWidget):
    page_changed = Signal(int)
    logout_requested = Signal()

    def __init__(self, *, nav: list[NavGroup] | None = None, parent=None):
        super().__init__(parent)
        self._nav_groups = list(nav if nav is not None else DEFAULT_NAV)
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
        self._sidebar.setFixedWidth(self._adaptive_sidebar_width())
        side_outer = QVBoxLayout(self._sidebar)
        side_outer.setContentsMargins(0, 0, 0, 0)
        side_outer.setSpacing(0)

        profile_section = QWidget()
        profile_section.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        profile_section_lay = QVBoxLayout(profile_section)
        profile_section_lay.setContentsMargins(12, 16, 12, 8)
        profile_section_lay.setSpacing(0)

        self._profile = QFrame()
        self._profile.setObjectName("profileCard")
        self._profile.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        pl = QHBoxLayout(self._profile)
        pl.setContentsMargins(12, 10, 12, 10)
        pl.setSpacing(10)
        self._profile_avatar = QLabel("A")
        self._profile_avatar.setFixedSize(40, 40)
        self._profile_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_host = QWidget()
        text_host.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        pi = QVBoxLayout(text_host)
        pi.setContentsMargins(0, 0, 0, 0)
        pi.setSpacing(2)
        self._profile_name = QLabel("Administrator")
        self._profile_name.setWordWrap(False)
        self._profile_role = QLabel("Fee desk")
        self._profile_role.setWordWrap(False)
        pi.addWidget(self._profile_name)
        pi.addWidget(self._profile_role)
        pl.addWidget(self._profile_avatar)
        pl.addWidget(text_host, 1)
        profile_section_lay.addWidget(self._profile)
        side_outer.addWidget(profile_section)

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

        for group in self._nav_groups:
            self._add_nav_group(group)

        self._nav_layout.addStretch(1)

        self._logout_section = QFrame()
        self._logout_section.setObjectName("sidebarLogoutSection")
        logout_lay = QVBoxLayout(self._logout_section)
        logout_lay.setContentsMargins(12, 8, 12, 8)
        logout_lay.setSpacing(0)
        self._logout_btn = _NavButton("  ↪   Log out")
        self._logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._logout_btn.clicked.connect(self.logout_requested.emit)
        logout_lay.addWidget(self._logout_btn)
        side_outer.addWidget(self._logout_section)

        self._sidebar_footer = QFrame()
        self._sidebar_footer.setObjectName("sidebarFooter")
        footer_lay = QVBoxLayout(self._sidebar_footer)
        footer_lay.setContentsMargins(16, 12, 16, 14)
        footer_lay.setSpacing(0)

        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 0, 0, 0)
        footer_row.setSpacing(14)
        footer_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        theme_text = QVBoxLayout()
        theme_text.setContentsMargins(0, 0, 0, 0)
        theme_text.setSpacing(2)
        self._theme_label = QLabel("Theme")
        self._theme_hint = QLabel("Light or dark mode")
        self._theme_hint.setProperty("role", "muted")
        theme_text.addWidget(self._theme_label)
        theme_text.addWidget(self._theme_hint)

        footer_row.addLayout(theme_text, 1)
        self._theme_toggle = ThemeToggleWidget(self._on_theme_toggle)
        footer_row.addWidget(
            self._theme_toggle,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        footer_lay.addLayout(footer_row)
        side_outer.addWidget(self._sidebar_footer)

        self._main = QWidget()
        main_lay = QVBoxLayout(self._main)
        main_lay.setContentsMargins(28, 20, 28, 20)
        main_lay.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_lay.addWidget(self._stack, 1)

        self._fab = QPushButton("⚙")
        self._fab.setParent(self._main)
        self._fab.setFixedSize(48, 48)
        self._fab.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fab.raise_()

        root.addWidget(self._sidebar)
        root.addWidget(self._main, 1)

        self.refresh_theme()

    def set_user_profile(self, display_name: str, role_label: str) -> None:
        letter = (display_name.strip()[:1] or "?").upper()
        self._profile_avatar.setText(letter)
        self._profile_name.setText(display_name)
        self._profile_role.setText(role_label)

    def set_fab_visible(self, visible: bool) -> None:
        self._fab.setVisible(visible)

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

        self._profile.setStyleSheet(
            f"QFrame#profileCard {{ background: {t.bg_app}; border-radius: 12px; "
            f"border: 1px solid {t.border}; }}"
        )
        self._profile_avatar.setStyleSheet(
            f"background: {t.primary}; color: {t.text_on_primary}; border-radius: 20px; "
            f"font-weight: 700; font-size: 15px;"
        )
        self._profile_name.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {t.text_primary}; "
            f"background: transparent;"
        )
        self._profile_role.setStyleSheet(
            f"color: {t.text_muted}; font-size: 11px; font-weight: 500; "
            f"background: transparent;"
        )

        self._sidebar_footer.setStyleSheet(
            f"QFrame#sidebarFooter {{ background: {t.bg_sidebar}; "
            f"border-top: 1px solid {t.border}; }}"
        )
        self._theme_label.setStyleSheet(
            f"color: {t.text_primary}; font-size: 13px; font-weight: 700; "
            f"background: transparent;"
        )
        self._theme_hint.setStyleSheet(
            f"color: {t.text_muted}; font-size: 11px; font-weight: 500; "
            f"background: transparent;"
        )

        self._theme_toggle.set_mode(mode, animate=True)
        self._theme_toggle.refresh_theme()

        self._fab.setStyleSheet(
            f"QPushButton {{ background: {t.primary}; color: white; border-radius: 24px; "
            f"font-size: 18px; border: none; }}"
            f"QPushButton:hover {{ background: {t.primary_dark}; }}"
        )

        self._logout_section.setStyleSheet(
            f"QFrame#sidebarLogoutSection {{ background: {t.bg_sidebar}; "
            f"border-top: 1px solid {t.border}; }}"
        )
        self._logout_btn.refresh_theme()

        for btn in self._nav_buttons.values():
            btn.refresh_theme()
        for hdr in self._group_headers.values():
            hdr.refresh_theme()

    _SIDEBAR_MIN = 200
    _SIDEBAR_MAX = 272

    def _adaptive_sidebar_width(self) -> int:
        available = self.width()
        if available <= 0:
            screen = self.screen() or QGuiApplication.primaryScreen()
            available = screen.availableGeometry().width() if screen is not None else 1280
        target = int(available * 0.22)
        return max(self._SIDEBAR_MIN, min(self._SIDEBAR_MAX, target))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = self._adaptive_sidebar_width()
        if width != self._sidebar.width():
            self._sidebar.setFixedWidth(width)
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
        host = self._wrap_scrollable(widget)
        idx = self._stack.addWidget(host)
        self._page_keys.append(page_key)
        self._key_to_index[page_key] = idx
        return idx

    @staticmethod
    def _wrap_scrollable(widget: QWidget) -> QWidget:
        """Wrap a page in a vertical scroll area so it is never clipped on small
        or scaled displays. Pages that already manage their own full-page scroll
        opt out via the ``page_scrolls`` property."""
        if widget.property("page_scrolls"):
            return widget
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(widget)
        return scroll

    def go(self, page_key: str) -> None:
        idx = self._key_to_index.get(page_key)
        if idx is None:
            return
        for group in self._nav_groups:
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
        self.page_changed.emit(idx)

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

    def add_page(self, tab_name: str, widget: QWidget, **_) -> int:
        return self.register_page(tab_name, widget)
