"""Measure real MainWindow.perform_search() via offscreen Qt."""

from __future__ import annotations

import os
import time
from statistics import mean

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def timed(label: str, fn, repeat: int = 3) -> float:
    samples = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    avg = mean(samples)
    print(f"  {label}: {avg * 1000:7.1f} ms")
    return avg


def main() -> None:
    from PySide6.QtWidgets import QApplication
    from backend.core.database import SessionLocal
    from frontend.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    session = SessionLocal()
    win = MainWindow(session)
    n = len(win.student_service.search_students(""))

    print(f"Students: {n}\n")
    print("CURRENT APP (pagination + header sort):")
    timed("Open tab: perform_search(reset_page=True)", lambda: win.perform_search(reset_page=True))
    timed("Type filter 'a': perform_search(reset_page=True)", lambda: (
        win.search_input.setText("a"),
        win.perform_search(reset_page=True),
    )[-1])
    timed("Header sort toggle (Village)", lambda: win._on_search_table_header_clicked(7))
    timed("Next page", lambda: win._search_change_page(1))

    session.close()


if __name__ == "__main__":
    main()
