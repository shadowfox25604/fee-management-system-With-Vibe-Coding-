import sys

from PySide6.QtCore import QEventLoop, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog
from backend.core.database import Base, SessionLocal, engine
from backend.core.master_key import ensure_master_key_file
from backend.core.schema_migrations import (
    apply_sqlite_column_migrations,
    apply_sqlite_data_migrations,
)
from backend.models import entities  # noqa: F401
from backend.services.backup_service import BackupService
from frontend.ui.login_page import LoginDialog
from frontend.ui.main_window import MainWindow
from frontend.ui.school_branding import resolve_logo_path
from frontend.ui.theme import apply_app_theme
from frontend.single_instance import acquire_single_instance

_APP_ID = "ACE.SchoolManagement.1"
_APP_NAME = "ACE School Management"


def _configure_windows_taskbar() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_ID)
    except Exception:
        pass


def run():
    _configure_windows_taskbar()
    app = QApplication(sys.argv)
    app.setApplicationName(_APP_NAME)
    app.setApplicationDisplayName(_APP_NAME)
    app.setOrganizationName("ACE High School")
    app.setQuitOnLastWindowClosed(False)
    logo_path = resolve_logo_path()
    if logo_path is not None:
        app.setWindowIcon(QIcon(str(logo_path)))
    apply_app_theme(app)

    if not acquire_single_instance(app):
        sys.exit(0)

    Base.metadata.create_all(bind=engine)
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    startup_daily_backup = BackupService(engine).create_daily_backup_if_needed()
    ensure_master_key_file()

    while True:
        session = SessionLocal()
        login = LoginDialog(session)
        if login.exec() != QDialog.DialogCode.Accepted or login.authenticated_user is None:
            session.close()
            break

        logged_out = False
        window = MainWindow(
            session,
            current_user=login.authenticated_user,
            startup_daily_backup=startup_daily_backup,
        )
        startup_daily_backup = None

        def on_logout() -> None:
            nonlocal logged_out
            logged_out = True

        window.logout_requested.connect(on_logout)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.show()

        loop = QEventLoop()
        window.destroyed.connect(loop.quit)
        loop.exec()

        session.close()
        if not logged_out:
            break

    sys.exit(0)


if __name__ == "__main__":
    run()
