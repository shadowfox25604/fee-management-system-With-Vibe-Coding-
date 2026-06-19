"""Login screen shown before the main application window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from backend.core.app_roles import DEFAULT_APP_USERS
from backend.models.entities import User
from frontend.ui.segment_toggle import LOGIN_SEGMENT_WIDTH, SegmentToggle
from backend.services.auth_service import AuthService
from frontend.ui import theme
from frontend.ui.school_branding import (
    APP_WINDOW_HEIGHT,
    APP_WINDOW_WIDTH,
    load_login_logo_pixmap,
    app_window_icon,
    school_motto,
    school_name,
    school_tagline,
    school_window_title,
)
from frontend.ui.window_utils import ensure_on_screen

_SEGMENT_W = LOGIN_SEGMENT_WIDTH
_SEGMENT_H = 48
_SEGMENT_PAD = 4
_SEGMENT_ANIM_MS = 220
_LOGIN_CONTROL_WIDTH = _SEGMENT_W
_HERO_LOGO_SIZE = 280


class _LoginBrandHero(QFrame):
    """Full-height branded panel with decorative background and large school identity."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("loginBrandPanel")
        self.setAutoFillBackground(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(56, 48, 56, 48)
        outer.setSpacing(0)
        outer.addStretch(2)

        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._hero_logo = QLabel()
        self._hero_logo.setFixedSize(_HERO_LOGO_SIZE, _HERO_LOGO_SIZE)
        self._hero_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hero_logo.setScaledContents(False)
        self._hero_logo.setStyleSheet("background: transparent;")
        logo_row = QHBoxLayout()
        logo_row.addStretch(1)
        logo_row.addWidget(self._hero_logo, 0, Qt.AlignmentFlag.AlignHCenter)
        logo_row.addStretch(1)
        lay.addLayout(logo_row)
        lay.addSpacing(36)

        self._hero_name = QLabel(school_name())
        self._hero_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hero_name.setWordWrap(True)
        lay.addWidget(self._hero_name)
        lay.addSpacing(10)

        self._hero_motto = QLabel(school_motto())
        self._hero_motto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hero_motto.setWordWrap(True)
        lay.addWidget(self._hero_motto)
        lay.addSpacing(28)

        self._tagline_badge = QLabel(school_tagline().upper())
        self._tagline_badge.setObjectName("loginTaglineBadge")
        self._tagline_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_row = QHBoxLayout()
        badge_row.addStretch(1)
        badge_row.addWidget(self._tagline_badge)
        badge_row.addStretch(1)
        lay.addLayout(badge_row)
        lay.addSpacing(40)

        icons_row = QHBoxLayout()
        icons_row.setSpacing(28)
        icons_row.addStretch(1)
        self._accent_icon_wraps: list[QFrame] = []
        self._accent_icon_labels: list[QLabel] = []
        for glyph in ("🏫", "💳", "📊"):
            icon_wrap = QFrame()
            icon_wrap.setObjectName("loginAccentIcon")
            icon_wrap.setFixedSize(72, 72)
            icon_lay = QVBoxLayout(icon_wrap)
            icon_lay.setContentsMargins(0, 0, 0, 0)
            icon_lbl = QLabel(glyph)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lay.addWidget(icon_lbl)
            self._accent_icon_wraps.append(icon_wrap)
            self._accent_icon_labels.append(icon_lbl)
            icons_row.addWidget(icon_wrap)
        icons_row.addStretch(1)
        lay.addLayout(icons_row)

        outer.addWidget(content)
        outer.addStretch(1)

        self._footer = QLabel("Trusted offline school management for your school")
        self._footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._footer.setWordWrap(True)
        outer.addWidget(self._footer)

    def paintEvent(self, event):
        t = theme.current_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0.0, QColor(t.primary_soft))
        grad.setColorAt(0.55, QColor(t.bg_surface))
        grad.setColorAt(1.0, QColor(t.primary_light))
        painter.fillRect(self.rect(), grad)

        soft_primary = QColor(t.primary)
        soft_primary.setAlpha(36)
        painter.setBrush(soft_primary)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(self.width() - 160, -100, 360, 360)
        painter.drawEllipse(-140, self.height() - 280, 420, 420)

        soft_white = QColor(t.bg_surface)
        soft_white.setAlpha(120)
        painter.setBrush(soft_white)
        cx = self.width() // 2
        cy = self.height() // 2 - 40
        painter.drawEllipse(cx - 210, cy - 210, 420, 420)

        painter.end()

    def refresh_theme(self) -> None:
        t = theme.current_tokens()
        dpr = float(self.devicePixelRatioF() or 1.0)

        name_font = QFont(theme.FONT, 38)
        name_font.setWeight(QFont.Weight.Bold)
        self._hero_name.setFont(name_font)
        self._hero_name.setStyleSheet(
            f"color: {t.text_primary}; background: transparent; font-weight: 700; "
            f"letter-spacing: 0.5px;"
        )
        self._hero_motto.setStyleSheet(
            f"color: {t.text_secondary}; background: transparent; font-size: 18px; "
            f"font-weight: 500; letter-spacing: 1.2px;"
        )
        self._tagline_badge.setStyleSheet(
            f"QLabel#loginTaglineBadge {{ background: {t.primary}; color: {t.text_on_primary}; "
            f"padding: 10px 22px; border-radius: 999px; font-size: 12px; font-weight: 700; "
            f"letter-spacing: 1px; }}"
        )
        self._footer.setStyleSheet(
            f"color: {t.text_muted}; background: transparent; font-size: 13px; font-weight: 500;"
        )
        for wrap in self._accent_icon_wraps:
            wrap.setStyleSheet(
                f"QFrame#loginAccentIcon {{ background: {t.bg_surface}; "
                f"border: 1px solid {t.border_light}; border-radius: 36px; }}"
            )
        for lbl in self._accent_icon_labels:
            lbl.setStyleSheet("background: transparent; font-size: 28px;")

        pix = load_login_logo_pixmap(_HERO_LOGO_SIZE, device_pixel_ratio=dpr)
        if pix is not None:
            self._hero_logo.setPixmap(pix)
            self._hero_logo.show()
        else:
            self._hero_logo.hide()


class _IconField(QFrame):
    """Rounded input row with a leading icon."""

    def __init__(
        self,
        icon: str,
        line_edit: QLineEdit,
        *,
        trailing: QWidget | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("iconField")
        self.setMinimumHeight(52)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 12, 0)
        lay.setSpacing(12)
        self._icon = QLabel(icon)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setFixedWidth(22)
        lay.addWidget(self._icon)
        line_edit.setFrame(False)
        lay.addWidget(line_edit, 1)
        if trailing is not None:
            lay.addWidget(trailing)


class ForgotPasswordDialog(QDialog):
    """Reset a login password using the offline master key."""

    def __init__(self, session, *, initial_username: str = "", parent=None):
        super().__init__(parent)
        self._auth = AuthService(session)
        self._master_visible = False
        self._new_visible = False
        self._confirm_visible = False

        self.setWindowTitle("Reset password")
        self.setModal(True)
        self.resize(440, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(0)

        self._title = QLabel("Reset password")
        root.addWidget(self._title)
        root.addSpacing(8)

        self._subtitle = QLabel(
            "Enter the master key from data/master_key.txt to set a new password "
            "for the selected account."
        )
        self._subtitle.setWordWrap(True)
        root.addWidget(self._subtitle)
        root.addSpacing(24)

        self._account_toggle = SegmentToggle(
            tuple(user.username for user in DEFAULT_APP_USERS),
            width=_SEGMENT_W,
        )
        if initial_username:
            self._account_toggle.set_selected_label(initial_username, animate=False)
        root.addWidget(self._account_toggle, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addSpacing(20)

        self._master_key = QLineEdit()
        self._master_key.setPlaceholderText("Master key")
        self._master_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._master_key.setMinimumHeight(52)
        self._toggle_master = QPushButton("Show")
        self._toggle_master.setFixedWidth(56)
        self._toggle_master.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_master.clicked.connect(lambda: self._toggle_field("master"))
        self._master_field = _IconField("🔑", self._master_key, trailing=self._toggle_master)
        root.addWidget(self._master_field)
        root.addSpacing(12)

        self._new_password = QLineEdit()
        self._new_password.setPlaceholderText("New password")
        self._new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_password.setMinimumHeight(52)
        self._toggle_new = QPushButton("Show")
        self._toggle_new.setFixedWidth(56)
        self._toggle_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_new.clicked.connect(lambda: self._toggle_field("new"))
        self._new_field = _IconField("🔒", self._new_password, trailing=self._toggle_new)
        root.addWidget(self._new_field)
        root.addSpacing(12)

        self._confirm_password = QLineEdit()
        self._confirm_password.setPlaceholderText("Confirm new password")
        self._confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_password.setMinimumHeight(52)
        self._confirm_password.returnPressed.connect(self._attempt_reset)
        self._toggle_confirm = QPushButton("Show")
        self._toggle_confirm.setFixedWidth(56)
        self._toggle_confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_confirm.clicked.connect(lambda: self._toggle_field("confirm"))
        self._confirm_field = _IconField("🔒", self._confirm_password, trailing=self._toggle_confirm)
        root.addWidget(self._confirm_field)
        root.addSpacing(12)

        self._error = QLabel("")
        self._error.setWordWrap(True)
        self._error.hide()
        root.addWidget(self._error)
        root.addSpacing(12)

        self._reset_btn = QPushButton("Reset password")
        self._reset_btn.setMinimumHeight(52)
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.clicked.connect(self._attempt_reset)
        root.addWidget(self._reset_btn)

        theme.ThemeManager.instance().theme_changed.connect(lambda _m: self.refresh_theme())
        self.refresh_theme()
        self._master_key.setFocus()

    def _toggle_field(self, which: str) -> None:
        if which == "master":
            self._master_visible = not self._master_visible
            self._master_key.setEchoMode(
                QLineEdit.EchoMode.Normal if self._master_visible else QLineEdit.EchoMode.Password
            )
            self._toggle_master.setText("Hide" if self._master_visible else "Show")
        elif which == "new":
            self._new_visible = not self._new_visible
            self._new_password.setEchoMode(
                QLineEdit.EchoMode.Normal if self._new_visible else QLineEdit.EchoMode.Password
            )
            self._toggle_new.setText("Hide" if self._new_visible else "Show")
        else:
            self._confirm_visible = not self._confirm_visible
            self._confirm_password.setEchoMode(
                QLineEdit.EchoMode.Normal if self._confirm_visible else QLineEdit.EchoMode.Password
            )
            self._toggle_confirm.setText("Hide" if self._confirm_visible else "Show")

    def _attempt_reset(self) -> None:
        self._error.hide()
        username = self._account_toggle.selected_label()
        master_key = self._master_key.text()
        new_password = self._new_password.text()
        confirm = self._confirm_password.text()

        validation = AuthService.validate_new_password(new_password)
        if validation:
            self._error.setText(validation)
            self._error.show()
            return
        if new_password != confirm:
            self._error.setText("Passwords do not match.")
            self._error.show()
            return

        if not self._auth.reset_user_password_with_master_key(username, master_key, new_password):
            self._error.setText("Invalid master key or account. Please try again.")
            self._error.show()
            self._master_key.selectAll()
            self._master_key.setFocus()
            return

        theme.message_information(
            self,
            "Password reset",
            f"Password updated for {username}. You can sign in with the new password.",
        )
        self.accept()

    def refresh_theme(self) -> None:
        t = theme.current_tokens()
        self.setStyleSheet(
            f"QDialog {{ background: {t.bg_surface}; }}"
            f"QFrame#iconField {{ background: {t.bg_app}; border: 1px solid {t.border_light}; "
            f"border-radius: {theme.RADIUS}; min-height: 52px; max-height: 52px; }}"
            f"QFrame#iconField QLineEdit {{ background: transparent; border: none; border-radius: 0px; "
            f"padding: 0; min-height: 0; }}"
        )
        title_font = QFont(theme.FONT, 22)
        title_font.setWeight(QFont.Weight.DemiBold)
        self._title.setFont(title_font)
        self._title.setStyleSheet(
            f"color: {t.text_primary}; background: transparent; font-weight: 600;"
        )
        self._subtitle.setStyleSheet(
            f"color: {t.text_secondary}; background: transparent; font-size: 13px;"
        )
        field_style = (
            f"QLineEdit {{ background: transparent; color: {t.text_primary}; border: none; "
            f"border-radius: 0px; padding: 0; font-size: 15px; min-height: 0; }}"
        )
        for edit in (self._master_key, self._new_password, self._confirm_password):
            edit.setStyleSheet(field_style)
        icon_style = f"color: {t.text_muted}; background: transparent; font-size: 16px;"
        for field in (self._master_field, self._new_field, self._confirm_field):
            field._icon.setStyleSheet(icon_style)
        toggle_style = (
            f"QPushButton {{ background: transparent; color: {t.text_secondary}; border: none; "
            f"font-size: 12px; font-weight: 600; padding: 0 4px; }}"
            f"QPushButton:hover {{ color: {t.primary}; }}"
        )
        for btn in (self._toggle_master, self._toggle_new, self._toggle_confirm):
            btn.setStyleSheet(toggle_style)
        self._reset_btn.setStyleSheet(
            f"QPushButton {{ background: {t.primary}; color: {t.text_on_primary}; "
            f"border: none; border-radius: {theme.RADIUS}; font-size: 16px; font-weight: 700; }}"
            f"QPushButton:hover {{ background: {t.primary_dark}; }}"
        )
        self._error.setStyleSheet(
            f"color: {t.danger}; background: transparent; font-size: 13px; font-weight: 500;"
        )
        self._account_toggle.refresh_theme()


class LoginDialog(QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self._session = session
        self._auth = AuthService(session)
        self.authenticated_user: User | None = None
        self._password_visible = False

        self.setWindowTitle(school_window_title())
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(APP_WINDOW_WIDTH, APP_WINDOW_HEIGHT)

        window_icon = app_window_icon()
        if window_icon is not None:
            self.setWindowIcon(window_icon)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._form_panel = QFrame()
        self._form_panel.setObjectName("loginFormPanel")
        self._form_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        form_outer = QVBoxLayout(self._form_panel)
        form_outer.setContentsMargins(72, 48, 72, 48)
        form_outer.addStretch(1)

        form_row = QHBoxLayout()
        form_row.setContentsMargins(0, 0, 0, 0)
        form_row.addStretch(1)

        form_col = QWidget()
        form_col.setMaximumWidth(460)
        form_col.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        form_lay = QVBoxLayout(form_col)
        form_lay.setContentsMargins(0, 0, 0, 0)
        form_lay.setSpacing(0)

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(14)
        self._form_logo = QLabel()
        self._form_logo.setFixedSize(56, 56)
        self._form_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._form_logo.setScaledContents(False)
        self._form_logo.setStyleSheet("background: transparent;")
        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setSpacing(2)
        self._brand_name = QLabel(school_name())
        self._brand_tagline = QLabel(school_tagline().upper())
        brand_text.addWidget(self._brand_name)
        brand_text.addWidget(self._brand_tagline)
        brand_row.addWidget(self._form_logo, 0, Qt.AlignmentFlag.AlignTop)
        brand_row.addLayout(brand_text, 1)
        form_lay.addLayout(brand_row)
        form_lay.addSpacing(48)

        self._title = QLabel("Login to your account")
        form_lay.addWidget(self._title)
        form_lay.addSpacing(24)

        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.addStretch(1)

        controls = QWidget()
        controls.setFixedWidth(_LOGIN_CONTROL_WIDTH)
        controls_lay = QVBoxLayout(controls)
        controls_lay.setContentsMargins(0, 0, 0, 0)
        controls_lay.setSpacing(0)

        self._account_toggle = SegmentToggle(
            tuple(user.username for user in DEFAULT_APP_USERS),
            width=_SEGMENT_W,
        )
        controls_lay.addWidget(self._account_toggle)
        controls_lay.addSpacing(24)

        self._password = QLineEdit()
        self._password.setPlaceholderText("Password")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setMinimumHeight(52)
        self._password.returnPressed.connect(self._attempt_login)
        self._toggle_password = QPushButton("Show")
        self._toggle_password.setFixedWidth(56)
        self._toggle_password.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_password.clicked.connect(self._toggle_password_visibility)
        self._password_field = _IconField("🔒", self._password, trailing=self._toggle_password)
        controls_lay.addWidget(self._password_field)
        controls_lay.addSpacing(8)

        forgot_row = QHBoxLayout()
        forgot_row.setContentsMargins(0, 0, 0, 0)
        forgot_row.addStretch(1)
        self._forgot_btn = QPushButton("Forgot password?")
        self._forgot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._forgot_btn.clicked.connect(self._open_forgot_password)
        forgot_row.addWidget(self._forgot_btn)
        controls_lay.addLayout(forgot_row)
        controls_lay.addSpacing(12)

        self._error = QLabel("")
        self._error.setWordWrap(True)
        self._error.hide()
        controls_lay.addWidget(self._error)
        controls_lay.addSpacing(8)

        self._login_btn = QPushButton("Login")
        self._login_btn.setMinimumHeight(52)
        self._login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._login_btn.clicked.connect(self._attempt_login)
        controls_lay.addWidget(self._login_btn)

        controls_row.addWidget(controls)
        controls_row.addStretch(1)
        form_lay.addLayout(controls_row)

        form_row.addWidget(form_col)
        form_row.addStretch(1)
        form_outer.addLayout(form_row)
        form_outer.addStretch(1)

        self._brand_panel = _LoginBrandHero()

        root.addWidget(self._brand_panel, 55)
        root.addWidget(self._form_panel, 45)

        self._account_toggle.selection_changed.connect(self._on_account_changed)
        self._password.setFocus()
        theme.ThemeManager.instance().theme_changed.connect(lambda _m: self.refresh_theme())
        self.refresh_theme()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        ensure_on_screen(self)

    def _on_account_changed(self, _username: str) -> None:
        self._error.hide()

    def _toggle_password_visibility(self) -> None:
        self._password_visible = not self._password_visible
        self._password.setEchoMode(
            QLineEdit.EchoMode.Normal if self._password_visible else QLineEdit.EchoMode.Password
        )
        self._toggle_password.setText("Hide" if self._password_visible else "Show")

    def _open_forgot_password(self) -> None:
        self._error.hide()
        dlg = ForgotPasswordDialog(
            self._session,
            initial_username=self._account_toggle.selected_label(),
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._password.clear()
            self._password.setFocus()

    def _attempt_login(self) -> None:
        self._error.hide()
        username = self._account_toggle.selected_label()
        user = self._auth.authenticate(username, self._password.text())
        if user is None:
            self._error.setText("Invalid password for the selected account. Please try again.")
            self._error.show()
            self._password.selectAll()
            self._password.setFocus()
            return
        self.authenticated_user = user
        self.accept()

    def refresh_theme(self) -> None:
        t = theme.current_tokens()
        dpr = float(self.devicePixelRatioF() or 1.0)

        self.setStyleSheet(
            f"QDialog {{ background: {t.bg_surface}; }}"
            f"QFrame#loginFormPanel {{ background: {t.bg_surface}; border: none; }}"
            f"QFrame#iconField {{ background: {t.bg_app}; border: 1px solid {t.border_light}; "
            f"border-radius: {theme.RADIUS}; min-height: 52px; max-height: 52px; }}"
            f"QFrame#iconField QLineEdit {{ background: transparent; border: none; border-radius: 0px; "
            f"padding: 0; min-height: 0; }}"
        )

        brand_name_font = QFont(theme.FONT, 18)
        brand_name_font.setWeight(QFont.Weight.Bold)
        self._brand_name.setFont(brand_name_font)
        self._brand_name.setStyleSheet(
            f"color: {t.text_primary}; background: transparent; font-weight: 700;"
        )
        self._brand_tagline.setStyleSheet(
            f"color: {t.text_muted}; background: transparent; font-size: 11px; "
            f"font-weight: 600; letter-spacing: 0.6px;"
        )

        title_font = QFont(theme.FONT, 26)
        title_font.setWeight(QFont.Weight.DemiBold)
        self._title.setFont(title_font)
        self._title.setStyleSheet(
            f"color: {t.text_primary}; background: transparent; font-weight: 600;"
        )

        field_style = (
            f"QLineEdit {{ background: transparent; color: {t.text_primary}; border: none; "
            f"border-radius: 0px; padding: 0; font-size: 15px; min-height: 0; }}"
        )
        self._password.setStyleSheet(field_style)

        icon_style = f"color: {t.text_muted}; background: transparent; font-size: 16px;"
        self._password_field._icon.setStyleSheet(icon_style)

        self._toggle_password.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {t.text_secondary}; border: none; "
            f"font-size: 12px; font-weight: 600; padding: 0 4px; }}"
            f"QPushButton:hover {{ color: {t.primary}; }}"
        )
        self._forgot_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {t.text_secondary}; border: none; "
            f"font-size: 12px; font-weight: 600; padding: 0; text-align: right; }}"
            f"QPushButton:hover {{ color: {t.primary}; }}"
        )
        self._login_btn.setStyleSheet(
            f"QPushButton {{ background: {t.primary}; color: {t.text_on_primary}; "
            f"border: none; border-radius: {theme.RADIUS}; font-size: 16px; font-weight: 700; }}"
            f"QPushButton:hover {{ background: {t.primary_dark}; }}"
        )
        self._error.setStyleSheet(
            f"color: {t.danger}; background: transparent; font-size: 13px; font-weight: 500;"
        )

        self._account_toggle.refresh_theme()
        self._brand_panel.refresh_theme()

        form_logo = load_login_logo_pixmap(56, device_pixel_ratio=dpr)
        if form_logo is not None:
            self._form_logo.setPixmap(form_logo)
            self._form_logo.show()
        else:
            self._form_logo.hide()
