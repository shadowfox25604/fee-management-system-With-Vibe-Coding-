"""Run multi-scenario rollover analysis and print a detailed report."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base
from backend.core.schema_migrations import apply_sqlite_column_migrations, apply_sqlite_data_migrations
from backend.models import entities  # noqa: F401
from tests.test_rollover_analysis_scenarios import ScenarioResult, _run_rollover_scenarios


def main() -> int:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        results: list[ScenarioResult] = _run_rollover_scenarios(session)
    finally:
        session.close()

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    print("=" * 100)
    print("ACADEMIC YEAR ROLLOVER — MULTI-STUDENT ANALYSIS REPORT")
    print("=" * 100)
    print(f"Scenarios run: {len(results)}  |  Passed: {passed}  |  Failed: {failed}")
    print()

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.name} ({r.student_id})")
        print(f"  BEFORE rollover (end of 2024-25):")
        print(f"    Pending fees     : {r.before_pending:>12.2f}")
        print(f"    School due (cur) : {r.before_school:>12.2f}")
        print(f"    Van due (cur)    : {r.before_van:>12.2f}")
        print(f"    Formula sum      : {r.expected_rolled:>12.2f}  (= pending + school + van)")
        print(f"  AFTER rollover (start of 2025-26):")
        print(f"    Opening stored   : {r.opening_stored:>12.2f}")
        print(f"    Pending fees     : {r.after_pending:>12.2f}")
        print(f"    School due (new) : {r.after_school:>12.2f}  (tariff {r.new_year_school_tariff:.2f})")
        print(f"    Van due (new)    : {r.after_van:>12.2f}  (tariff {r.new_year_van_tariff:.2f})")
        print(f"  Notes: {r.notes}")
        print()

    print("-" * 100)
    print("SCENARIO LEGEND")
    print("-" * 100)
    print("A_only_old_pending     — Old years unpaid; current year fully paid")
    print("B_only_current_unpaid  — No prior pending; current school+van fully unpaid")
    print("C_pending_plus_current — Mixed: partial pay on prev + current")
    print("D_fully_paid           — All years fully paid before rollover")
    print("E_van_pending_only     — Mimics real case: van pending + partial current (696969-like)")
    print("F_school_pending_heavy — Large school pending across years + partial current")
    print()

    if failed:
        print("OVERALL: FAILED — see scenarios marked FAIL above.")
        return 1
    print("OVERALL: ALL SCENARIOS PASSED — rollover formula holds for every student profile.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
