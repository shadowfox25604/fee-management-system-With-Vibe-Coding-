import sys
from PySide6.QtWidgets import QApplication
from app.core.database import Base, SessionLocal, engine
from app.core.schema_migrations import (
    apply_sqlite_column_migrations,
    apply_sqlite_data_migrations,
)
from app.models import entities  # noqa: F401
from app.ui.main_window import MainWindow

def run():
    Base.metadata.create_all(bind=engine)
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    app = QApplication(sys.argv)
    session = SessionLocal()
    window = MainWindow(session)
    window.show()
    try:
        sys.exit(app.exec())
    finally:
        session.close()

if __name__ == "__main__":
    run()
