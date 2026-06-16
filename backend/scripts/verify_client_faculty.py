"""Verify client faculty list against the database."""

from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from backend.core.database import engine
from backend.models.entities import FacultySalary

EXPECTED_TEACHING: tuple[tuple[str, str, float], ...] = (
    ("emp001", "G.VENUGOPAL REDDY", 35000),
    ("emp002", "CH. MURALIDHAR", 30000),
    ("emp003", "CH.ASHOK", 20000),
    ("emp004", "N SRIDHAR", 8000),
    ("emp005", "M.NARESH", 16000),
    ("emp006", "SWAMY", 10000),
    ("emp007", "RAMBABU", 14000),
    ("emp008", "SHANKARAIAH", 6500),
    ("emp009", "MAHENDHAR", 14000),
    ("emp010", "CHUKKA SANDHYA", 27000),
    ("emp011", "SRIJA", 12000),
    ("emp012", "CHALLA SANDHYA", 10000),
    ("emp013", "V.GEETHANJALI", 11000),
    ("emp014", "LAVANYA", 9000),
    ("emp015", "CHALLA ANUSHA/Supriya", 8000),
    ("emp016", "BANDARI ANUSHA", 5000),
    ("emp017", "SWAROOPA", 5000),
    ("emp018", "KAVITHA", 9000),
    ("emp019", "D DIVYA", 6500),
    ("emp020", "SRILATHA", 4600),
    ("emp021", "SWAPNA", 5000),
    ("emp022", "SUMALATHA", 7000),
    ("emp023", "AKSHITHA", 6000),
    ("emp024", "RAMYA/Deepika", 6000),
    ("emp025", "MUS 1", 7000),
    ("emp026", "MUS 2", 7000),
)

EXPECTED_NON_TEACHING: tuple[tuple[str, str, float], ...] = (
    ("emp027", "YOGA", 6000),
    ("emp028", "GARIGE PRAVEEN", 12000),
    ("emp029", "ASHOK", 12000),
    ("emp030", "GANGADHAR", 10000),
    ("emp031", "MAHESH(DRIVER)", 12000),
    ("emp032", "MADHUKAR", 6500),
    ("emp033", "MAHESH(CLEANER)", 5000),
    ("emp034", "HARISH", 5000),
    ("emp035", "VAZRAMMA", 6000),
    ("emp036", "KANTHAMMA", 5000),
    ("emp037", "KAMALA", 5000),
    ("emp038", "POCHAVVA", 5000),
    ("emp039", "NARSAVVA", 5000),
)


def _norm_name(value: str) -> str:
    return "".join((value or "").upper().split())


def verify() -> int:
    expected = list(EXPECTED_TEACHING) + list(EXPECTED_NON_TEACHING)
    expected_ids = {emp.lower() for emp, _, _ in expected}
    session = sessionmaker(bind=engine)()
    try:
        rows = session.query(FacultySalary).all()
        by_id = {row.employee_id.lower(): row for row in rows}
        issues: list[str] = []
        ok = 0
        for emp, name, salary in expected:
            exp_type = "Teaching" if int(emp[3:]) <= 26 else "Non Teaching"
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
