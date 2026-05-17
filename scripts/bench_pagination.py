"""Compare full-table load vs paginated (50) backend work. Run from project root with PYTHONPATH=."""

from __future__ import annotations

import time
from statistics import mean

PAGE_SIZE = 50


def timed(label: str, fn, repeat: int = 3) -> float:
    samples = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    avg = mean(samples)
    print(f"{label}: {avg * 1000:.0f} ms  (min={min(samples)*1000:.0f}, max={max(samples)*1000:.0f})")
    return avg


def main() -> None:
    print("=== IMPORT TIMING ===")
    t0 = time.perf_counter()
    from frontend.ui.main_window import MainWindow  # noqa: F401

    t_main = time.perf_counter() - t0
    print(f"main_window import (lazy PDF): {t_main * 1000:.0f} ms")

    t0 = time.perf_counter()
    import reportlab  # noqa: F401
    from backend.reports.excel_export import ExcelExporter  # noqa: F401
    from backend.reports.payment_receipt_pdf import render_payment_receipt  # noqa: F401
    from backend.reports.pdf_export import PdfExporter  # noqa: F401

    t_eager = time.perf_counter() - t0
    print(f"eager reportlab+exports add-on: {t_eager * 1000:.0f} ms")

    from backend.core.database import SessionLocal
    from backend.services.payment_service import PaymentService
    from backend.services.student_service import StudentService

    session = SessionLocal()
    student_svc = StudentService(session)
    pay_svc = PaymentService(session)
    students = student_svc.search_students("")
    n = len(students)
    ids = [s.id for s in students]
    print(f"\n=== DATA SCALE ===\nstudents in DB: {n}")

    def full_fee_queries():
        s = student_svc.search_students("")
        pay_svc.get_students_school_fee_summary([x.id for x in s])
        pay_svc.get_students_van_fee_summary([x.id for x in s])
        pay_svc.get_students_due_breakdown([x.id for x in s])
        pay_svc.get_students_cumulative_payment_discount([x.id for x in s])

    def page_fee_queries():
        chunk = students[:PAGE_SIZE]
        pids = [x.id for x in chunk]
        pay_svc.get_students_school_fee_summary(pids)
        pay_svc.get_students_van_fee_summary(pids)
        pay_svc.get_students_due_breakdown(pids)
        pay_svc.get_students_cumulative_payment_discount(pids)

    print("\n=== BACKEND FEE QUERIES (no Qt table paint) ===")
    t_full = timed(f"ALL {n} students (old startup path)", full_fee_queries)
    t_page = timed(f"FIRST PAGE {PAGE_SIZE} students (new startup path)", page_fee_queries)
    if t_page:
        print(f"speedup (backend only): {t_full / t_page:.1f}x faster for first page")

    filtered = [s for s in students if "a" in (s.full_name or "").lower()]
    fids = [s.id for s in filtered]

    def filter_all_fees():
        pay_svc.get_students_school_fee_summary(fids)
        pay_svc.get_students_van_fee_summary(fids)
        pay_svc.get_students_due_breakdown(fids)
        pay_svc.get_students_cumulative_payment_discount(fids)

    def filter_page_fees():
        pids = [s.id for s in filtered[:PAGE_SIZE]]
        pay_svc.get_students_school_fee_summary(pids)
        pay_svc.get_students_van_fee_summary(pids)
        pay_svc.get_students_due_breakdown(pids)
        pay_svc.get_students_cumulative_payment_discount(pids)

    print(f"\n=== FILTER (name contains 'a'): {len(filtered)} matches ===")
    t_fa = timed("fees for ALL filtered matches", filter_all_fees)
    t_fp = timed("fees for first page only", filter_page_fees)
    if t_fa and t_fp:
        print(f"savings on filtered browse: {(1 - t_fp / t_fa) * 100:.0f}% less fee-query time")

    # Qt table row creation (major UI cost)
    try:
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

        app = QApplication.instance() or QApplication([])

        def fill_table(row_count: int):
            tbl = QTableWidget(row_count, 18)
            for i in range(row_count):
                for j in range(18):
                    tbl.setItem(i, j, QTableWidgetItem("x"))

        print("\n=== QT TABLE WIDGET (18 columns, synthetic cells) ===")
        t_tbl_full = timed(f"fill {n} rows", lambda: fill_table(n))
        t_tbl_page = timed(f"fill {PAGE_SIZE} rows", lambda: fill_table(PAGE_SIZE))
        if t_tbl_page:
            print(f"UI table speedup first page: {t_tbl_full / t_tbl_page:.1f}x faster")

        # Simulated cold app: migrations + first search page
        from backend.core.database import Base, engine
        from backend.core.schema_migrations import (
            apply_sqlite_column_migrations,
            apply_sqlite_data_migrations,
        )
        from backend.models import entities  # noqa: F401

        def cold_first_page():
            Base.metadata.create_all(bind=engine)
            apply_sqlite_column_migrations(engine)
            apply_sqlite_data_migrations(engine)
            page_fee_queries()
            fill_table(PAGE_SIZE)

        def cold_full_table():
            Base.metadata.create_all(bind=engine)
            apply_sqlite_column_migrations(engine)
            apply_sqlite_data_migrations(engine)
            full_fee_queries()
            fill_table(n)

        print("\n=== SIMULATED OPEN (migrations + fee queries + table fill) ===")
        t_cold_page = timed("paginated first screen", cold_first_page, repeat=2)
        t_cold_full = timed("full student table", cold_full_table, repeat=2)
        if t_cold_page:
            print(f"estimated open speedup: {t_cold_full / t_cold_page:.1f}x faster to first screen")
    except Exception as e:
        print(f"\n(Qt benchmark skipped: {e})")

    session.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
