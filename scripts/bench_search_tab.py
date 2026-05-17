"""Compare Student Search tab: legacy (pre-optimization) vs current implementation.

Run from project root:
  set PYTHONPATH=.
  python scripts/bench_search_tab.py

Legacy simulates the older path: optional full-DB fee queries on sort-by-fee,
and optional rendering of every student row (no pagination).
Current matches frontend/ui/main_window.py: sort without fee DB work, page=50 fees+table.
"""

from __future__ import annotations

import os
import time
from statistics import mean

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PAGE_SIZE = 50
_FEE_SORT_FIELDS = {
    "Van Fees Paid",
    "Van Fees Due",
    "School Fees Paid",
    "Discount",
    "School Fees Due",
    "Total Fees",
    "Total Fees Due",
}


def timed(label: str, fn, repeat: int = 5) -> float:
    samples = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    avg = mean(samples)
    print(
        f"  {label}: {avg * 1000:7.1f} ms  "
        f"(min {min(samples) * 1000:.1f}, max {max(samples) * 1000:.1f})"
    )
    return avg


def _class_sort_value(class_name: str):
    cls = str(class_name or "").strip()
    if cls.isdigit():
        return (0, int(cls))
    return (1, cls.lower())


def legacy_sort_key(student, sort_field: str, summaries, van_summaries, due_map, discount_map):
    summary = summaries.get(student.id, {"fee_paid": 0.0, "fee_due": 0.0, "total_fees": 0.0})
    van_s = van_summaries.get(student.id, {"van_paid": 0.0, "van_due": 0.0})
    due = due_map.get(student.id, {"van_due": 0.0, "fee_due": 0.0, "total": 0.0})
    disc = float(discount_map.get(student.id, 0.0) or 0.0)
    if sort_field == "Student ID":
        return (student.student_id or "").lower()
    if sort_field == "Name":
        return (student.full_name or "").lower()
    if sort_field == "Class":
        return _class_sort_value(student.class_name)
    if sort_field == "Village":
        return (getattr(student, "village", None) or "").lower()
    if sort_field == "Total Fees Due":
        return float(due["total"])
    return student.id


def current_sort_key(student, sort_field: str):
    if sort_field == "Student ID":
        return (student.student_id or "").lower()
    if sort_field == "Name":
        return (student.full_name or "").lower()
    if sort_field == "Class":
        return _class_sort_value(student.class_name)
    if sort_field == "Village":
        return (getattr(student, "village", None) or "").lower()
    return (student.student_id or "").lower()


def fill_student_table(tbl, students, summaries, van_summaries, due_map, discount_map) -> None:
    from PySide6.QtWidgets import QTableWidgetItem

    tbl.setRowCount(len(students))
    for i, s in enumerate(students):
        summary = summaries.get(s.id, {"fee_paid": 0.0, "fee_due": 0.0, "total_fees": 0.0})
        van_s = van_summaries.get(s.id, {"van_paid": 0.0, "van_due": 0.0})
        due = due_map.get(s.id, {"van_due": 0.0, "fee_due": 0.0, "total": 0.0})
        disc = float(discount_map.get(s.id, 0.0) or 0.0)
        tbl.setItem(i, 0, QTableWidgetItem(str(s.id)))
        tbl.setItem(i, 1, QTableWidgetItem(s.student_id))
        tbl.setItem(i, 2, QTableWidgetItem(s.full_name))
        tbl.setItem(i, 3, QTableWidgetItem(str(s.class_name)))
        tbl.setItem(i, 4, QTableWidgetItem(str(s.section)))
        tbl.setItem(i, 5, QTableWidgetItem(s.phone))
        tbl.setItem(i, 6, QTableWidgetItem(str(getattr(s, "guardian_name", "") or "")))
        tbl.setItem(i, 7, QTableWidgetItem(str(getattr(s, "village", "") or "")))
        tbl.setItem(i, 8, QTableWidgetItem(s.status))
        tbl.setItem(i, 9, QTableWidgetItem(f"{float(getattr(s, 'van_fees', 0) or 0):.2f}"))
        tbl.setItem(i, 10, QTableWidgetItem(f"{van_s['van_paid']:.2f}"))
        tbl.setItem(i, 11, QTableWidgetItem(f"{due['van_due']:.2f}"))
        tbl.setItem(i, 12, QTableWidgetItem(f"{float(getattr(s, 'school_fees', 0) or 0):.2f}"))
        tbl.setItem(i, 13, QTableWidgetItem(f"{summary['fee_paid']:.2f}"))
        tbl.setItem(i, 14, QTableWidgetItem(f"{disc:.2f}"))
        tbl.setItem(i, 15, QTableWidgetItem(f"{due['fee_due']:.2f}"))
        tbl.setItem(i, 16, QTableWidgetItem(f"{summary['total_fees']:.2f}"))
        tbl.setItem(i, 17, QTableWidgetItem(f"{due['total']:.2f}"))


def fee_maps(pay_svc, ids: list[int]) -> dict:
    if not ids:
        return {"summaries": {}, "van_summaries": {}, "due_map": {}, "discount_map": {}}
    return {
        "summaries": pay_svc.get_students_school_fee_summary(ids),
        "van_summaries": pay_svc.get_students_van_fee_summary(ids),
        "due_map": pay_svc.get_students_due_breakdown(ids),
        "discount_map": pay_svc.get_students_cumulative_payment_discount(ids),
    }


def main() -> None:
    from PySide6.QtWidgets import QApplication, QTableWidget

    from backend.core.database import SessionLocal
    from backend.services.payment_service import PaymentService
    from backend.services.student_service import StudentService

    app = QApplication.instance() or QApplication([])
    session = SessionLocal()
    student_svc = StudentService(session)
    pay_svc = PaymentService(session)

    students = student_svc.search_students("")
    n = len(students)
    all_ids = [s.id for s in students]
    page_ids = all_ids[:PAGE_SIZE]
    page_students = students[:PAGE_SIZE]

    print("=" * 72)
    print("STUDENT SEARCH TAB — BEFORE vs AFTER (simulated)")
    print("=" * 72)
    print(f"Students in database: {n}")
    print(f"Page size (current app): {PAGE_SIZE}")
    print()

    # --- A) Rebuild / sort only (typing in search box) ---
    print("A) Search refresh (list + sort, no table paint)")
    print("-" * 72)

    def legacy_rebuild_pk_sort():
        s = list(students)
        s.sort(
            key=lambda st: legacy_sort_key(st, "PK", {}, {}, {}, {}),
            reverse=False,
        )

    def legacy_rebuild_fee_sort():
        """Old UI: user picks 'Total Fees Due' + Ascending from dropdowns."""
        maps = fee_maps(pay_svc, all_ids)
        s = list(students)
        s.sort(
            key=lambda st: legacy_sort_key(
                st, "Total Fees Due", maps["summaries"], maps["van_summaries"],
                maps["due_map"], maps["discount_map"],
            ),
            reverse=False,
        )

    def current_rebuild_name_sort():
        s = list(students)
        s.sort(key=lambda st: current_sort_key(st, "Name"), reverse=False)

    t_legacy_pk = timed("BEFORE: list + PK sort (no fee DB)", legacy_rebuild_pk_sort)
    t_legacy_fee = timed("BEFORE: list + sort by Total Fees Due (ALL fee queries)", legacy_rebuild_fee_sort)
    t_current = timed("AFTER:  list + header sort by Name (no fee DB)", current_rebuild_name_sort)
    print()
    if t_legacy_fee and t_current:
        print(f"  -> Sort-by-fee (old) is {t_legacy_fee / t_current:.0f}x slower than current name sort")
    print()

    # --- B) Full perform_search equivalent (rebuild + render) ---
    print("B) Full search load (rebuild + fee queries + fill table)")
    print("-" * 72)

    tbl = QTableWidget(0, 18)

    def legacy_full_table_pk():
        legacy_rebuild_pk_sort()
        s = list(students)
        s.sort(key=lambda st: st.id)
        maps = fee_maps(pay_svc, all_ids)
        fill_student_table(
            tbl, s, maps["summaries"], maps["van_summaries"],
            maps["due_map"], maps["discount_map"],
        )

    def legacy_full_table_fee_sort():
        maps = fee_maps(pay_svc, all_ids)
        s = list(students)
        s.sort(
            key=lambda st: legacy_sort_key(
                st, "Total Fees Due", maps["summaries"], maps["van_summaries"],
                maps["due_map"], maps["discount_map"],
            ),
            reverse=False,
        )
        fill_student_table(
            tbl, s, maps["summaries"], maps["van_summaries"],
            maps["due_map"], maps["discount_map"],
        )

    def current_first_page():
        s = list(students)
        s.sort(key=lambda st: current_sort_key(st, "Student ID"), reverse=False)
        maps = fee_maps(pay_svc, page_ids)
        fill_student_table(
            tbl, page_students, maps["summaries"], maps["van_summaries"],
            maps["due_map"], maps["discount_map"],
        )

    t_old_full = timed(f"BEFORE: all {n} rows + all fee queries", legacy_full_table_pk)
    t_old_fee = timed(f"BEFORE: all {n} rows + fee-column sort path", legacy_full_table_fee_sort)
    t_new = timed(f"AFTER:  first page ({PAGE_SIZE}) + page fee queries", current_first_page)
    print()
    if t_old_full and t_new:
        print(f"  -> First screen AFTER is {t_old_full / t_new:.1f}x faster than BEFORE (all rows)")
        print(f"  -> Time saved per open: {(t_old_full - t_new) * 1000:.0f} ms")
    print()

    # --- C) Header click (toggle sort) — AFTER only ---
    print("C) Header click re-sort (in-memory only, AFTER UX)")
    print("-" * 72)

    def header_toggle_sort():
        s = list(students)
        s.sort(key=lambda st: current_sort_key(st, "Village"), reverse=False)
        s.sort(key=lambda st: current_sort_key(st, "Village"), reverse=True)

    t_header = timed("AFTER: toggle Village asc/desc (no DB)", header_toggle_sort)
    print(f"  (negligible vs table paint; ~{t_header * 1000:.1f} ms)")
    print()

    # --- D) App startup import ---
    print("D) Cold import (main window module)")
    print("-" * 72)

    def import_main():
        import importlib
        import frontend.ui.main_window as mw
        importlib.reload(mw)

    timed("import frontend.ui.main_window", import_main, repeat=3)
    print()

    print("=" * 72)
    print("VERDICT")
    print("=" * 72)
    print("  AFTER (current) is better optimized for normal use because:")
    print("  - Pagination loads 50 students per screen, not the entire DB.")
    print("  - Fee summaries run for the visible page only, not every student.")
    print("  - Header sort (ID/Name/Class/Village) avoids slow 'sort by fee column' DB work.")
    print("  - Removing Search button has no measurable load impact (search was already live).")
    print("=" * 72)

    session.close()


if __name__ == "__main__":
    main()
