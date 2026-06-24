"""Offscreen smoke test for the responsive-UI changes.

Builds MainWindow at small geometries with high DPI scaling, visits every
registered page, and asserts pages are scroll-wrapped (unless opted out) and
that the Add Student form grid reflows to fewer columns on narrow widths.

Run:
    set QT_QPA_PLATFORM=offscreen && set PYTHONPATH=.
    .venv\\Scripts\\python.exe scripts\\ui_responsive_smoke.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "1.5")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QScrollArea  # noqa: E402

from backend.core.database import Base, SessionLocal, engine  # noqa: E402
from backend.core.schema_migrations import (  # noqa: E402
    apply_sqlite_column_migrations,
    apply_sqlite_data_migrations,
)
from backend.models import User, entities  # noqa: F401,E402


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)

    from frontend.ui.theme import apply_app_theme
    from frontend.ui.main_window import MainWindow
    from frontend.ui.add_student_page import AddStudentPage

    apply_app_theme(app)
    Base.metadata.create_all(bind=engine)
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)

    session = SessionLocal()
    user = session.query(User).filter(User.role == "admin").first() or session.query(User).first()
    if user is None:
        print("No user in database to drive the UI.")
        return 1

    window = MainWindow(session, current_user=user, startup_daily_backup=None)
    shell = window._shell
    opt_out = {"Home Page", "Student Details", "Fee Control", "Add Faculty"}

    from frontend.ui.edudash_widgets import FormGrid

    problems: list[str] = []
    window.show()
    widths_cols: dict[int, int] = {}
    for geom in [(1366, 768), (1024, 640), (900, 600), (760, 560)]:
        window.resize(*geom)
        app.processEvents()
        app.processEvents()
        for key in list(shell._key_to_index.keys()):
            shell.go(key)
            app.processEvents()
            idx = shell._key_to_index[key]
            page = shell._stack.widget(idx)
            is_scroll = isinstance(page, QScrollArea)
            if key in opt_out:
                if is_scroll:
                    problems.append(f"[{geom}] {key}: expected opt-out (no outer scroll) but wrapped")
            else:
                if not is_scroll:
                    problems.append(f"[{geom}] {key}: expected scroll wrap, got {type(page).__name__}")
    # FormGrid reflow, exercised exactly like the shell wraps a page: an
    # AddStudentPage inside its own resizable QScrollArea that we resize.
    probe_page = AddStudentPage(populate_village=lambda combo: combo.addItems(["A", "B"]))
    probe_scroll = QScrollArea()
    probe_scroll.setWidgetResizable(True)
    probe_scroll.setWidget(probe_page)
    probe_scroll.resize(1200, 700)
    probe_scroll.show()
    app.processEvents()
    fg = probe_page.findChild(FormGrid)
    if fg is not None:
        for w in (1200, 760, 520):
            probe_scroll.resize(w, 700)
            app.processEvents()
            app.processEvents()
            widths_cols[w] = fg._cols

    cols_seq = [widths_cols[w] for w in sorted(widths_cols, reverse=True)]
    non_increasing = all(a >= b for a, b in zip(cols_seq, cols_seq[1:]))
    if not (cols_seq and non_increasing and min(cols_seq) < max(cols_seq)):
        problems.append(f"FormGrid did not reflow as expected: {widths_cols}")

    print("Pages visited per geometry; scroll-wrap check done.")
    print(f"Add Student FormGrid columns by window width: {widths_cols}")
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  -", p)
        return 1
    print("OK: responsive UI smoke test passed.")
    session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
