"""Verify client faculty list against the database."""

from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from backend.core.client_faculty_data import CLIENT_FACULTY_ROWS
from backend.core.database import engine
from backend.models.entities import FacultySalary


def _norm_name(value: str) -> str:
    return "".join((value or "").upper().split())


def verify() -> int:
    expected = list(CLIENT_FACULTY_ROWS)
    expected_ids = {emp.lower() for emp, _, _, _, _ in expected}
    session = sessionmaker(bind=engine)()
    try:
        rows = session.query(FacultySalary).all()
        by_id = {row.employee_id.lower(): row for row in rows}
        issues: list[str] = []
        ok = 0
        for emp, name, salary, exp_type, _role in expected:
            row = by_id.get(emp.lower())
            if row is None:
                issues.append(f"MISSING {emp} {name}")
                continue
            if int(row.monthly_salary) != int(salary):
                issues.append(
                    f"SALARY {emp}: expected {int(salary)}, got {int(row.monthly_salary)}"
                )
            elif _norm_name(row.faculty_name) != _norm_name(name):
                issues.append(
                    f'NAME {emp}: expected "{name}", got "{row.faculty_name}"'
                )
            elif row.faculty_type != exp_type:
                issues.append(
                    f"TYPE {emp}: expected {exp_type}, got {row.faculty_type}"
                )
            else:
                ok += 1
        extra = [row.employee_id for row in rows if row.employee_id.lower() not in expected_ids]
        print(f"Matched: {ok}/{len(expected)}")
        print(f"Teaching in DB: {sum(1 for r in rows if r.faculty_type == 'Teaching')}")
        print(f"Non Teaching in DB: {sum(1 for r in rows if r.faculty_type == 'Non Teaching')}")
        if issues:
            print("Issues:")
            for issue in issues:
                print(f"  - {issue}")
        if extra:
            print("Extra records:", ", ".join(extra))
        if not issues and not extra and ok == len(expected):
            print("ALL FACULTY VERIFIED OK")
        return 0 if ok == len(expected) and not extra and not issues else 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(verify())
