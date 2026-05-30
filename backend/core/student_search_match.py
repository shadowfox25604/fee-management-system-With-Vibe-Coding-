"""Shared student text search matching (Student List, Reports, etc.)."""

from backend.core.fee_control_constants import class_name_matches_query

STUDENT_SEARCH_BASIS_OPTIONS: tuple[str, ...] = (
    "Roll Number",
    "Name",
    "Gender",
    "Father Name",
    "Mother Name",
    "Mobile Number 1",
    "Mobile Number 2",
    "Aadhaar",
    "Village",
    "Class",
    "Caste",
)

SEARCH_PLACEHOLDERS: dict[str, str] = {
    "Roll Number": "Enter student roll number",
    "Name": "Enter student name",
    "Gender": "Enter gender",
    "Father Name": "Enter father name",
    "Mother Name": "Enter mother name",
    "Mobile Number 1": "Enter mobile number 1",
    "Mobile Number 2": "Enter mobile number 2",
    "Aadhaar": "Enter aadhaar number",
    "Village": "Enter village name",
    "Class": "Enter class",
    "Caste": "Enter caste",
}


def student_matches_search(student, basis: str, query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return True
    if basis == "Roll Number":
        return q in str(student.student_id or "").lower()
    if basis == "Village":
        return q in str(getattr(student, "village", None) or "").lower()
    if basis == "Gender":
        return q in str(getattr(student, "gender", None) or "").lower()
    if basis == "Father Name":
        return q in str(
            getattr(student, "father_name", None)
            or getattr(student, "guardian_name", None)
            or ""
        ).lower()
    if basis == "Mother Name":
        return q in str(getattr(student, "mother_name", None) or "").lower()
    if basis == "Mobile Number 1":
        return q in str(getattr(student, "mobile_number_1", None) or student.phone or "").lower()
    if basis == "Mobile Number 2":
        return q in str(getattr(student, "mobile_number_2", None) or "").lower()
    if basis == "Aadhaar":
        return q in str(getattr(student, "aadhaar", None) or "").lower()
    if basis == "Caste":
        return q in str(getattr(student, "caste", None) or "").lower()
    if basis == "Class":
        return class_name_matches_query(student.class_name, q)
    return q in str(student.full_name or "").lower()
