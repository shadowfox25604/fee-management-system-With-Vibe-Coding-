"""EduDash visual design tokens, light/dark themes, and global Qt stylesheet."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QCompleter, QDialog, QListWidget, QMessageBox, QPushButton, QWidget

ThemeMode = Literal["light", "dark"]

# Chart / accent colors (shared across themes)
TEAL = "#26A69A"
ORANGE = "#FF7043"
PURPLE = "#AB47BC"
BLUE = "#42A5F5"
GREEN = "#66BB6A"
PINK = "#EC407A"
YELLOW = "#FFCA28"

RADIUS = "10px"
RADIUS_SM = "6px"
RADIUS_LG = "12px"
FONT = "Segoe UI"


@dataclass(frozen=True)
class ThemeTokens:
    bg_app: str
    bg_surface: str
    bg_sidebar: str
    bg_section_header: str
    bg_input: str
    bg_hover: str
    primary: str
    primary_dark: str
    primary_light: str
    primary_soft: str
    nav_active_bg: str
    nav_active_text: str
    nav_sub_active_text: str
    text_primary: str
    text_secondary: str
    text_muted: str
    text_on_primary: str
    border: str
    border_light: str
    table_alt_row: str
    table_header_bg: str
    scrollbar: str
    checkbox_bg: str
    nav_hover: str
    upload_bg: str
    list_avatar_bg: str
    quick_stat_bgs: tuple[str, str, str]
    quick_stat_text: str
    danger: str
    success: str
    profile_grad_start: str
    profile_grad_end: str


LIGHT_TOKENS = ThemeTokens(
    bg_app="#F5F7FB",
    bg_surface="#FFFFFF",
    bg_sidebar="#FFFFFF",
    bg_section_header="#F3F4F6",
    bg_input="#FFFFFF",
    bg_hover="#F3F4F6",
    primary="#1ABC9C",
    primary_dark="#16A085",
    primary_light="#D1FAF0",
    primary_soft="#E8F8F5",
    nav_active_bg="#E8F8F5",
    nav_active_text="#1ABC9C",
    nav_sub_active_text="#1ABC9C",
    text_primary="#2D3748",
    text_secondary="#718096",
    text_muted="#A0AEC0",
    text_on_primary="#FFFFFF",
    border="#E2E8F0",
    border_light="#EDF2F7",
    table_alt_row="#FAFBFC",
    table_header_bg="#FAFBFC",
    scrollbar="#CBD5E0",
    checkbox_bg="#FFFFFF",
    nav_hover="#F7FAFC",
    upload_bg="#FAFBFC",
    list_avatar_bg="#EDF2F7",
    quick_stat_bgs=("#F3E8FF", "#DCFCE7", "#DBEAFE"),
    quick_stat_text="#334155",
    danger="#DC2626",
    success="#16A34A",
    profile_grad_start="#7C3AED",
    profile_grad_end="#4F46E5",
)

DARK_TOKENS = ThemeTokens(
    bg_app="#0F172A",
    bg_surface="#1E293B",
    bg_sidebar="#1E293B",
    bg_section_header="#334155",
    bg_input="#334155",
    bg_hover="#334155",
    primary="#1ABC9C",
    primary_dark="#16A085",
    primary_light="#134E4A",
    primary_soft="#1A3D35",
    nav_active_bg="#1A3D35",
    nav_active_text="#1ABC9C",
    nav_sub_active_text="#1ABC9C",
    text_primary="#F1F5F9",
    text_secondary="#94A3B8",
    text_muted="#64748B",
    text_on_primary="#FFFFFF",
    border="#334155",
    border_light="#475569",
    table_alt_row="#253041",
    table_header_bg="#253041",
    scrollbar="#475569",
    checkbox_bg="#334155",
    nav_hover="#334155",
    upload_bg="#253041",
    list_avatar_bg="#334155",
    quick_stat_bgs=("#312E81", "#14532D", "#1E3A5F"),
    quick_stat_text="#E2E8F0",
    danger="#F87171",
    success="#4ADE80",
    profile_grad_start="#0F766E",
    profile_grad_end="#1ABC9C",
)

# Module-level aliases (updated when theme changes)
BG_APP = LIGHT_TOKENS.bg_app
BG_SURFACE = LIGHT_TOKENS.bg_surface
BG_SIDEBAR = LIGHT_TOKENS.bg_sidebar
BG_SECTION_HEADER = LIGHT_TOKENS.bg_section_header
BG_INPUT = LIGHT_TOKENS.bg_input
BG_HOVER = LIGHT_TOKENS.bg_hover
PRIMARY = LIGHT_TOKENS.primary
PRIMARY_DARK = LIGHT_TOKENS.primary_dark
PRIMARY_LIGHT = LIGHT_TOKENS.primary_light
PRIMARY_SOFT = LIGHT_TOKENS.primary_soft
NAV_ACTIVE_BG = LIGHT_TOKENS.nav_active_bg
NAV_ACTIVE_TEXT = LIGHT_TOKENS.nav_active_text
NAV_SUB_ACTIVE_TEXT = LIGHT_TOKENS.nav_sub_active_text
TEXT_PRIMARY = LIGHT_TOKENS.text_primary
TEXT_SECONDARY = LIGHT_TOKENS.text_secondary
TEXT_MUTED = LIGHT_TOKENS.text_muted
TEXT_ON_PRIMARY = LIGHT_TOKENS.text_on_primary
BORDER = LIGHT_TOKENS.border
BORDER_LIGHT = LIGHT_TOKENS.border_light

_current_mode: ThemeMode = "light"
_current_tokens: ThemeTokens = LIGHT_TOKENS


def current_theme_mode() -> ThemeMode:
    return _current_mode


def current_tokens() -> ThemeTokens:
    return _current_tokens


def _sync_module_globals(tokens: ThemeTokens) -> None:
    global BG_APP, BG_SURFACE, BG_SIDEBAR, BG_SECTION_HEADER, BG_INPUT, BG_HOVER
    global PRIMARY, PRIMARY_DARK, PRIMARY_LIGHT, PRIMARY_SOFT
    global NAV_ACTIVE_BG, NAV_ACTIVE_TEXT, NAV_SUB_ACTIVE_TEXT
    global TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_ON_PRIMARY
    global BORDER, BORDER_LIGHT

    BG_APP = tokens.bg_app
    BG_SURFACE = tokens.bg_surface
    BG_SIDEBAR = tokens.bg_sidebar
    BG_SECTION_HEADER = tokens.bg_section_header
    BG_INPUT = tokens.bg_input
    BG_HOVER = tokens.bg_hover
    PRIMARY = tokens.primary
    PRIMARY_DARK = tokens.primary_dark
    PRIMARY_LIGHT = tokens.primary_light
    PRIMARY_SOFT = tokens.primary_soft
    NAV_ACTIVE_BG = tokens.nav_active_bg
    NAV_ACTIVE_TEXT = tokens.nav_active_text
    NAV_SUB_ACTIVE_TEXT = tokens.nav_sub_active_text
    TEXT_PRIMARY = tokens.text_primary
    TEXT_SECONDARY = tokens.text_secondary
    TEXT_MUTED = tokens.text_muted
    TEXT_ON_PRIMARY = tokens.text_on_primary
    BORDER = tokens.border
    BORDER_LIGHT = tokens.border_light


class ThemeManager(QObject):
    theme_changed = Signal(str)

    _instance: ThemeManager | None = None

    @classmethod
    def instance(cls) -> ThemeManager:
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self._listeners: list[Callable[[str], None]] = []

    def register_listener(self, callback: Callable[[str], None]) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def notify(self, mode: ThemeMode) -> None:
        self.theme_changed.emit(mode)
        for cb in list(self._listeners):
            cb(mode)


def register_theme_listener(callback: Callable[[str], None]) -> None:
    ThemeManager.instance().register_listener(callback)


def refresh_widget_tree(root: QWidget | None) -> None:
    if root is None:
        return
    seen: set[int] = set()

    def _visit(widget: QWidget) -> None:
        wid = id(widget)
        if wid in seen:
            return
        seen.add(wid)
        if widget is not root and hasattr(widget, "refresh_theme") and callable(widget.refresh_theme):
            widget.refresh_theme()
        for child in widget.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
            _visit(child)

    for child in root.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
        _visit(child)


def list_widget_stylesheet() -> str:
    t = _current_tokens
    return f"""
    QListWidget {{
        background: {t.bg_surface};
        color: {t.text_primary};
        border: 1px solid {t.border};
        border-radius: 10px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 12px 14px;
        border-bottom: 1px solid {t.border_light};
        color: {t.text_primary};
    }}
    QListWidget::item:selected {{
        background: {t.primary_soft};
        color: {t.text_primary};
    }}
    QListWidget::item:hover {{
        background: {t.bg_hover};
    }}
    """


def refresh_list_widget(widget: QListWidget) -> None:
    widget.setStyleSheet(list_widget_stylesheet())
    widget.viewport().update()


def apply_dialog_theme(dialog: QDialog | QWidget) -> None:
    """Ensure modal student/payment dialogs match the active theme."""
    t = _current_tokens
    dialog.setStyleSheet(
        f"""
        QDialog, QWidget#themedDialog {{
            background-color: {t.bg_app};
            color: {t.text_primary};
        }}
        QGroupBox {{
            background: {t.bg_surface};
            color: {t.text_primary};
            border: 1px solid {t.border};
            border-radius: {RADIUS};
            margin-top: 16px;
            padding: 14px 12px 12px 12px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 6px;
            color: {t.text_secondary};
        }}
        QLabel {{
            color: {t.text_primary};
            background: transparent;
        }}
        QLineEdit, QComboBox, QDateEdit, QSpinBox {{
            background: {t.bg_input};
            color: {t.text_primary};
            border: 1px solid {t.border};
        }}
        QPushButton {{
            background: {t.bg_surface};
            color: {t.text_primary};
            border: 1px solid {t.border};
        }}
        QPushButton:hover {{
            background: {t.bg_hover};
        }}
        QDialogButtonBox QPushButton {{
            min-width: 80px;
        }}
        """
    )
    dialog.setObjectName("themedDialog")


def apply_app_theme(app: QApplication, mode: ThemeMode | None = None) -> None:
    global _current_mode, _current_tokens

    if mode is not None:
        _current_mode = mode
        _current_tokens = LIGHT_TOKENS if mode == "light" else DARK_TOKENS
    _sync_module_globals(_current_tokens)
    t = _current_tokens

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(t.bg_app))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(t.text_primary))
    palette.setColor(QPalette.ColorRole.Base, QColor(t.bg_surface))
    palette.setColor(QPalette.ColorRole.Text, QColor(t.text_primary))
    palette.setColor(QPalette.ColorRole.Button, QColor(t.bg_surface))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(t.text_primary))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(t.primary))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(t.text_on_primary))
    app.setPalette(palette)
    app.setFont(QFont(FONT, 9))
    app.setStyleSheet(_stylesheet(t))


def toggle_theme(app: QApplication) -> ThemeMode:
    new_mode: ThemeMode = "dark" if _current_mode == "light" else "light"
    apply_app_theme(app, new_mode)
    ThemeManager.instance().notify(new_mode)
    return new_mode


def _stylesheet(t: ThemeTokens) -> str:
    combo_popup_bg = t.bg_surface
    return f"""
    QMainWindow, QDialog {{ background: {t.bg_app}; }}
    QWidget {{ color: {t.text_primary}; font-family: "{FONT}"; font-size: 13px;
        background: transparent; }}

    QLineEdit, QComboBox, QDateEdit, QSpinBox {{
        background: {t.bg_input};
        color: {t.text_primary};
        border: 1px solid {t.border};
        border-radius: {RADIUS_SM};
        padding: 9px 12px;
        min-height: 18px;
    }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
        border: 1px solid {t.primary};
    }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QComboBox QAbstractItemView {{
        background: {combo_popup_bg}; color: {t.text_primary};
        border: 1px solid {t.border};
        selection-background-color: {t.primary_soft};
    }}
    QListView#completerPopup {{
        background: {combo_popup_bg};
        color: {t.text_primary};
        border: 1px solid {t.border};
        outline: none;
        padding: 2px;
    }}
    QListView#completerPopup::item {{
        padding: 6px 10px;
    }}
    QListView#completerPopup::item:selected {{
        background: {t.primary_soft};
        color: {t.text_primary};
    }}
    QListView#completerPopup::item:hover {{
        background: {t.bg_hover};
    }}

    QPushButton {{
        background: {t.bg_surface};
        border: 1px solid {t.border};
        border-radius: {RADIUS_SM};
        padding: 8px 18px;
        font-weight: 600;
        color: {t.text_primary};
    }}
    QPushButton:hover {{ background: {t.bg_hover}; }}
    QPushButton[variant="primary"] {{
        background: {t.primary};
        color: white;
        border: 1px solid {t.primary_dark};
    }}
    QPushButton[variant="primary"]:hover {{ background: {t.primary_dark}; }}
    QPushButton[variant="teal-outline"] {{
        background: transparent;
        color: {t.primary};
        border: 1px solid {t.primary};
    }}
    QPushButton[variant="icon"] {{
        background: {t.bg_surface};
        border: 1px solid {t.border};
        border-radius: 20px;
        padding: 6px;
        min-width: 36px;
        max-width: 36px;
        min-height: 36px;
        max-height: 36px;
        color: {t.text_primary};
    }}

    QTableWidget {{
        background: {t.bg_surface};
        color: {t.text_primary};
        border: none;
        gridline-color: {t.border_light};
        alternate-background-color: {t.table_alt_row};
    }}
    QHeaderView::section {{
        background: {t.table_header_bg};
        color: {t.text_secondary};
        padding: 12px 10px;
        border: none;
        border-bottom: 1px solid {t.border};
        font-weight: 600;
        font-size: 12px;
    }}
    QTableWidget::item {{
        padding: 10px 8px;
        border: none;
        outline: none;
        color: {t.text_primary};
    }}
    QTableWidget::item:selected {{
        background: transparent;
        color: {t.text_primary};
    }}
    QTableWidget::item:focus,
    QTableWidget::item:selected:focus {{
        border: none;
        outline: none;
        background: transparent;
    }}
    QTableWidget:focus {{ outline: none; }}

    QListWidget {{
        background: {t.bg_surface};
        color: {t.text_primary};
        border: 1px solid {t.border};
        border-radius: {RADIUS};
        outline: none;
    }}
    QListWidget::item {{
        padding: 12px 14px;
        border-bottom: 1px solid {t.border_light};
    }}
    QListWidget::item:selected {{
        background: {t.primary_soft}; color: {t.text_primary};
    }}
    QListWidget::item:hover {{ background: {t.bg_hover}; }}

    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{
        width: 8px; background: transparent; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.scrollbar}; border-radius: 4px; min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

    QCheckBox {{ spacing: 8px; color: {t.text_secondary}; }}
    QCheckBox::indicator {{
        width: 18px; height: 18px; border-radius: 4px;
        border: 1px solid {t.border}; background: {t.checkbox_bg};
    }}
    QCheckBox::indicator:checked {{
        background: {t.primary}; border-color: {t.primary};
    }}

    QCalendarWidget {{
        background: {t.bg_surface};
        color: {t.text_primary};
        border: 1px solid {t.border};
        border-radius: {RADIUS};
    }}
    QCalendarWidget QWidget#qt_calendar_navigationbar {{
        background: {t.bg_surface};
    }}
    QCalendarWidget QAbstractItemView {{
        background: {t.bg_surface};
        color: {t.text_primary};
        selection-background-color: {t.primary};
        selection-color: {t.text_on_primary};
    }}

    QRadioButton {{ spacing: 6px; color: {t.text_secondary}; }}
    QRadioButton::indicator {{
        width: 16px; height: 16px;
        border: 2px solid {t.border}; border-radius: 8px;
        background: {t.checkbox_bg};
    }}
    QRadioButton::indicator:checked {{
        border-color: {t.primary}; background: {t.primary};
    }}

    QGroupBox {{
        background: {t.bg_surface};
        border: 1px solid {t.border};
        border-radius: {RADIUS};
        margin-top: 12px;
        padding: 16px;
        color: {t.text_primary};
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 6px;
        color: {t.text_secondary};
    }}

    QDialogButtonBox QPushButton {{
        min-width: 80px;
    }}

    QMessageBox {{
        background-color: {t.bg_surface};
        color: {t.text_primary};
    }}
    QMessageBox QLabel {{
        color: {t.text_primary};
        background: transparent;
        font-size: 13px;
        padding: 4px;
    }}
    QMessageBox QPushButton {{
        background-color: {t.primary};
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 8px 22px;
        font-weight: 700;
        font-size: 13px;
        min-width: 88px;
        min-height: 32px;
    }}
    QMessageBox QPushButton:hover {{
        background-color: {t.primary_dark};
        color: #FFFFFF;
    }}

    QLabel[role="page-title"] {{
        font-size: 24px; font-weight: 700; color: {t.text_primary};
    }}
    QLabel[role="breadcrumb"] {{ color: {t.text_muted}; font-size: 13px; }}
    QLabel[role="card-title"] {{
        font-size: 15px; font-weight: 700; color: {t.text_primary};
    }}
    QLabel[role="section-title"] {{
        font-size: 15px; font-weight: 700; color: {t.text_primary};
    }}
    QLabel[role="field-label"] {{
        font-size: 12px; font-weight: 600; color: {t.text_secondary};
        margin-bottom: 2px;
    }}
    QLabel[role="muted"] {{ color: {t.text_secondary}; font-size: 12px; }}
    QLabel[role="hint"] {{ color: {t.text_muted}; font-size: 11px; }}
    QPushButton[role="theme-icon"], QLabel[role="theme-icon"],
    QLabel[role="theme-icon-active"] {{
        background: transparent;
        border: none;
        padding: 0px;
        font-family: "Segoe UI Emoji", "Segoe UI Symbol", sans-serif;
        font-size: 14px;
    }}

    QFrame[card="surface"] {{
        background: {t.bg_surface};
        border: 1px solid {t.border};
        border-radius: {RADIUS_LG};
    }}
    """


def polish(btn: QPushButton, variant: str) -> None:
    btn.setProperty("variant", variant)
    btn.style().unpolish(btn)
    btn.style().polish(btn)


def style_completer_popup(completer: QCompleter) -> None:
    """Theme the QCompleter suggestion list (separate popup, not styled as QComboBox)."""
    popup = completer.popup()
    if popup is None:
        return
    popup.setObjectName("completerPopup")
    t = current_tokens()
    popup.setStyleSheet(
        f"QListView#completerPopup {{"
        f"background: {t.bg_surface}; color: {t.text_primary}; "
        f"border: 1px solid {t.border}; outline: none; padding: 2px; }}"
        f"QListView#completerPopup::item {{ padding: 6px 10px; }}"
        f"QListView#completerPopup::item:selected {{"
        f"background: {t.primary_soft}; color: {t.text_primary}; }}"
        f"QListView#completerPopup::item:hover {{ background: {t.bg_hover}; }}"
    )


def style_primary(btn: QPushButton) -> None:
    polish(btn, "primary")


def _message_box_stylesheet() -> str:
    t = _current_tokens
    return f"""
    QMessageBox {{
        background-color: {t.bg_surface};
        color: {t.text_primary};
    }}
    QMessageBox QLabel {{
        color: {t.text_primary};
        background: transparent;
        font-size: 13px;
        padding: 4px;
    }}
    QMessageBox QPushButton {{
        background-color: {t.primary};
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 8px 22px;
        font-weight: 700;
        font-size: 13px;
        min-width: 88px;
        min-height: 32px;
    }}
    QMessageBox QPushButton:hover {{
        background-color: {t.primary_dark};
        color: #FFFFFF;
    }}
    """


def _apply_message_box_theme(box: QMessageBox) -> None:
    t = _current_tokens
    box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    palette = box.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(t.bg_surface))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(t.text_primary))
    palette.setColor(QPalette.ColorRole.Base, QColor(t.bg_surface))
    palette.setColor(QPalette.ColorRole.Text, QColor(t.text_primary))
    box.setPalette(palette)
    box.setStyleSheet(_message_box_stylesheet())


def message_information(parent, title: str, text: str) -> None:
    box = QMessageBox(QMessageBox.Icon.Information, title, text, QMessageBox.StandardButton.Ok, parent)
    _apply_message_box_theme(box)
    box.exec()


def message_warning(parent, title: str, text: str) -> None:
    box = QMessageBox(QMessageBox.Icon.Warning, title, text, QMessageBox.StandardButton.Ok, parent)
    _apply_message_box_theme(box)
    box.exec()


def message_critical(parent, title: str, text: str) -> None:
    box = QMessageBox(QMessageBox.Icon.Critical, title, text, QMessageBox.StandardButton.Ok, parent)
    _apply_message_box_theme(box)
    box.exec()


def message_question(
    parent,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButton = (
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    ),
    default_button: QMessageBox.StandardButton = QMessageBox.StandardButton.No,
) -> QMessageBox.StandardButton:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(buttons)
    box.setDefaultButton(default_button)
    _apply_message_box_theme(box)
    return QMessageBox.StandardButton(box.exec())
