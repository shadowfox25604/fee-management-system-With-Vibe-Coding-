from backend.repositories.report_repository import ReportRepository
class ReportService:
    def __init__(self, session): self.repo=ReportRepository(session)
    def get_defaulters(self, student_query=None, class_name=None, section=None):
        return self.repo.defaulters(student_query=student_query, class_name=class_name, section=section)
    def get_report_filter_values(self):
        return {"classes": self.repo.distinct_classes(), "sections": self.repo.distinct_sections()}
