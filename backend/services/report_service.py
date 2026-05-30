from collections import namedtuple

from backend.core.fee_control_constants import FIXED_CLASS_KEYS
from backend.core.report_fee_constants import (
    amount_for_fee_filter,
    matches_fee_filter,
)
from backend.core.student_search_match import student_matches_search
from backend.repositories.report_repository import ReportRepository
from backend.services.fee_balance_service import FeeBalanceService

ReportFeeRow = namedtuple(
    "ReportFeeRow",
    ["student_id", "full_name", "class_name", "section", "amount", "outstanding"],
)


class ReportService:
    def __init__(self, session):
        self.session = session
        self.repo = ReportRepository(session)

    def get_defaulters(self, student_query=None, class_name=None, section=None):
        return self.repo.defaulters(
            student_query=student_query, class_name=class_name, section=section
        )

    def get_fee_report_rows(
        self,
        fee_status=None,
        student_query=None,
        search_basis=None,
        class_name=None,
        section=None,
    ):
        students = self.repo.list_students_for_report(
            class_name=class_name,
            section=section,
        )
        q = (student_query or "").strip()
        if q:
            basis = search_basis or "Name"
            students = [
                s for s in students if student_matches_search(s, basis, q)
            ]
        if not students:
            return []
        student_ids = [s.student_id for s in students]
        due_map = FeeBalanceService(self.session).get_students_due_breakdown(student_ids)
        rows: list[ReportFeeRow] = []
        for student in students:
            sid = str(student.student_id)
            due = due_map.get(sid, {})
            if fee_status:
                if not matches_fee_filter(due, fee_status):
                    continue
                amount = amount_for_fee_filter(due, fee_status)
            else:
                amount = float(due.get("total", 0) or 0)
            rows.append(
                ReportFeeRow(
                    student_id=sid,
                    full_name=str(student.full_name or ""),
                    class_name=str(student.class_name or ""),
                    section=str(student.section or ""),
                    amount=amount,
                    outstanding=amount,
                )
            )
        return rows

    def get_report_filter_values(self):
        return {
            "classes": list(FIXED_CLASS_KEYS),
            "sections": self.repo.distinct_sections(),
        }
