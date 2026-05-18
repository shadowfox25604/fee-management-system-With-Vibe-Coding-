import sys
from PySide6.QtWidgets import QApplication
from backend.core.database import Base, SessionLocal, engine
from backend.core.schema_migrations import (
    apply_sqlite_column_migrations,
    apply_sqlite_data_migrations,
)
from backend.models import entities  # noqa: F401
from frontend.ui.main_window import MainWindow
from frontend.ui.theme import apply_app_theme


def run():
    Base.metadata.create_all(bind=engine)
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    app = QApplication(sys.argv)
    apply_app_theme(app)
    session = SessionLocal()
    window = MainWindow(session)
    window.show()
    try:
        sys.exit(app.exec())
    finally:
        session.close()


if __name__ == "__main__":
    run()
