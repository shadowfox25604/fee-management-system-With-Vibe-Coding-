from datetime import date

from backend.models import Student
from backend.services.payment_service import PaymentService
from backend.services.student_service import StudentService


def _seed_student(session, *, student_id: str = "S001") -> Student:
    student = Student(
        student_id=student_id,
        full_name="Test Student",
        class_name="1",
        section="A",
        phone="9000000001",
        guardian_name="Parent",
        father_name="Father",
        mother_name="Mother",
        gender="male",
        school_fees=20000.0,
        van_fees=5000.0,
        date_of_birth=date(2015, 3, 15),
    )
    session.add(student)
    session.commit()
    session.refresh(student)
    return student


def test_build_list_export_rows(db_session):
    svc = StudentService(db_session)
    pay_svc = PaymentService(db_session)
    student = _seed_student(db_session)
    due_map = pay_svc.get_students_due_breakdown([student.student_id])
    summaries = pay_svc.get_students_school_fee_summary([student.student_id])
    van_summaries = pay_svc.get_students_van_fee_summary([student.student_id])
    discount_map = pay_svc.get_students_cumulative_payment_discount([student.student_id])

    rows = svc.build_list_export_rows(
        [student],
        summaries=summaries,
        van_summaries=van_summaries,
        due_map=due_map,
        discount_map=discount_map,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["student_id"] == "S001"
    assert row["full_name"] == "Test Student"
    assert row["gender"] == "Male"
    assert row["father_name"] == "Father"
    assert row["school_fees"] == 20000.0
    assert row["van_fees"] == 5000.0


def test_student_list_export_excel(tmp_path, db_session):
    svc = StudentService(db_session)
    pay_svc = PaymentService(db_session)
    student = _seed_student(db_session)
    student_ids = [student.student_id]
    fee_maps = {
        "summaries": pay_svc.get_students_school_fee_summary(student_ids),
        "van_summaries": pay_svc.get_students_van_fee_summary(student_ids),
        "due_map": pay_svc.get_students_due_breakdown(student_ids),
        "discount_map": pay_svc.get_students_cumulative_payment_discount(student_ids),
    }

    out = tmp_path / "student_list.xlsx"
    svc.export_list_excel(
        out,
        [student],
        summaries=fee_maps["summaries"],
        van_summaries=fee_maps["van_summaries"],
        due_map=fee_maps["due_map"],
        discount_map=fee_maps["discount_map"],
    )
    assert out.exists()
    assert out.stat().st_size > 0


def test_list_export_students_filters_by_class_and_status(db_session):
    svc = StudentService(db_session)
    active = _seed_student(db_session, student_id="S001")
    inactive = _seed_student(db_session, student_id="S002")
    inactive.status = "inactive"
    db_session.commit()

    class_rows = svc.list_export_students(class_names=["1"], status="active")
    assert [s.student_id for s in class_rows] == ["S001"]

    inactive_rows = svc.list_export_students(status="inactive")
    assert [s.student_id for s in inactive_rows] == ["S002"]


def test_export_list_excel_filtered(tmp_path, db_session):
    svc = StudentService(db_session)
    pay_svc = PaymentService(db_session)
    _seed_student(db_session, student_id="S001")

    out = tmp_path / "filtered.xlsx"
    svc.export_list_excel_filtered(
        out,
        pay_svc,
        class_names=["1"],
        status="active",
        columns=["student_id", "full_name", "total_due"],
    )
    assert out.exists()
    assert out.stat().st_size > 0


def test_count_export_rows_ignores_columns_filter(db_session):
    svc = StudentService(db_session)
    _seed_student(db_session, student_id="S001")

    assert svc.count_export_rows(class_names=["1"], columns=["student_id", "full_name"]) == 1


def test_export_with_selected_columns_only(tmp_path, db_session):
    from backend.reports.student_list_excel_export import StudentListExcelExporter

    rows = [
        {
            "student_id": "S001",
            "full_name": "Test Student",
            "gender": "Male",
            "total_due": 1000.0,
        }
    ]
    out = tmp_path / "subset.xlsx"
    StudentListExcelExporter.export(
        rows,
        out,
        columns=["student_id", "full_name", "total_due"],
    )
    assert out.exists()
    assert out.stat().st_size > 0
