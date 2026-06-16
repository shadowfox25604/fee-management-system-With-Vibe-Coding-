"""Login Access — admin-only password reset for app users."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.core.app_roles import DEFAULT_APP_USERS
from backend.services.auth_service import AuthService
from frontend.ui import theme
from frontend.ui.edudash_widgets import CardTitleBar, FormField, FormGrid, SurfaceCard, wrap_page
from frontend.ui.school_branding import breadcrumb_trail
from frontend.ui.table_style import style_fee_action_button


class _InfoBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("loginAccessInfoBanner")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)
        self._icon = QLabel("🔐")
        self._icon.setFixedWidth(28)
        self._text = QLabel()
        self._text.setWordWrap(True)
        self._text.setProperty("role", "muted")
        lay.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)
        lay.addWidget(self._text, 1)
        self.refresh_theme()

    def set_text(self, text: str) -> None:
        self._text.setText(text)

    def refresh_theme(self) -> None:
        t = theme.current_tokens()
        self.setStyleSheet(
            f"QFrame#loginAccessInfoBanner {{ background: {t.bg_app}; border: 1px solid {t.border}; "
            f"border-radius: 12px; }}"
        )


class LoginAccessPage(QWidget):
    """Reset Admin or Accountant passwords (Administrator only)."""

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self._auth = AuthService(session)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        self._banner = _InfoBanner()
        self._banner.set_text(
            "Only the Administrator can reset login passwords for Admin and Accountant accounts. "
            "Use the master key on the login screen if you are locked out before signing in."
        )
        root.addWidget(self._banner)

        form_card = SurfaceCard()
        form_card.body.addWidget(CardTitleBar("Reset user password"))

        self._account = QComboBox()
        for cred in DEFAULT_APP_USERS:
            self._account.addItem(cred.username, cred.username)

        self._new_password = QLineEdit()
        self._new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_password.setPlaceholderText("New password")

        self._confirm_password = QLineEdit()
        self._confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_password.setPlaceholderText("Confirm new password")

        grid = FormGrid(columns=2)
        grid.add_field(FormField("Account", self._account, required=True))
        grid.add_field(FormField("New password", self._new_password, required=True))
        grid.add_field(FormField("Confirm password", self._confirm_password, required=True))
        form_card.body.addWidget(grid)

        self._error = QLabel("")
        self._error.setWordWrap(True)
        self._error.hide()
        form_card.body.addWidget(self._error)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._reset_btn = QPushButton("Reset password")
        style_fee_action_button(self._reset_btn)
        self._reset_btn.clicked.connect(self._on_reset)
        btn_row.addWidget(self._reset_btn)
        form_card.body.addLayout(btn_row)

        root.addWidget(form_card)
        root.addStretch(1)

        self._wrapped = wrap_page(
            "Login Access",
            breadcrumb_trail("Admin Control", "Login Access"),
            self,
        )

    @property
    def wrapped(self) -> QWidget:
        return self._wrapped

    def _on_reset(self) -> None:
        self._error.hide()
        username = self._account.currentData()
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

        user = self._auth.reset_user_password(str(username), new_password)
        if user is None:
            self._error.setText("Could not reset password. Check the account and try again.")
            self._error.show()
            return

        self._new_password.clear()
        self._confirm_password.clear()
        theme.message_information(
            self,
            "Password reset",
            f"Password updated for {user.username}.",
        )

    def refresh_theme(self) -> None:
        t = theme.current_tokens()
        self._banner.refresh_theme()
        self._error.setStyleSheet(
            f"color: {t.danger}; background: transparent; font-size: 13px; font-weight: 500;"
        )
