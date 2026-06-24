"""Canonical ACE High School faculty roster for client deployments."""

from __future__ import annotations

# (employee_id, faculty_name, monthly_salary)
CLIENT_TEACHING_FACULTY: tuple[tuple[str, str, float], ...] = (
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

CLIENT_NON_TEACHING_FACULTY: tuple[tuple[str, str, float], ...] = (
    ("emp027", "YOGA", 6000),
    ("emp028", "GARIGE PRAVEEN", 12000),
    ("emp029", "ASHOK", 12000),
    ("emp030", "GANGADHAR", 10000),
    ("emp031", "MAHESH", 12000),
    ("emp032", "MADHUKAR", 6500),
    ("emp033", "MAHESH (2)", 5000),
    ("emp034", "HARISH", 5000),
    ("emp035", "VAZRAMMA", 6000),
    ("emp036", "KANTHAMMA", 5000),
    ("emp037", "KAMALA", 5000),
    ("emp038", "POCHAVVA", 5000),
    ("emp039", "NARSAVVA", 5000),
)

CLIENT_FACULTY_ROWS: tuple[tuple[str, str, float, str, str], ...] = tuple(
    (*row, "Teaching", "Teacher") for row in CLIENT_TEACHING_FACULTY
) + tuple(
    (*row, "Non Teaching", "Staff") for row in CLIENT_NON_TEACHING_FACULTY
)
