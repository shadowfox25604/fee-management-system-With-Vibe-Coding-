from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text

from backend.models import Student
from backend.services.backup_service import BackupIntegrityError, BackupProtectedError, BackupService


def _backup_service(isolated_test_database, tmp_path) -> BackupService:
    db_path = Path(isolated_test_database.url.database)
    backup_dir = tmp_path / "backups"
    return BackupService(
        isolated_test_database,
        db_path=db_path,
        backup_dir=backup_dir,
    )


def _add_student(session, student_id: str, name: str) -> Student:
    student = Student(
        student_id=student_id,
        full_name=name,
        class_name="6",
        section="A",
        phone="9000000099",
        guardian_name="Parent",
    )
    session.add(student)
    session.commit()
    session.refresh(student)
    return student


def test_create_backup_passes_integrity_check(db_session, isolated_test_database, tmp_path):
    service = _backup_service(isolated_test_database, tmp_path)
    _add_student(db_session, "BK001", "Backup Student")

    backup_path = service.create_backup()
    assert backup_path.exists()
    service.verify_backup(backup_path)


def test_backup_preserves_row_counts(db_session, isolated_test_database, tmp_path):
    service = _backup_service(isolated_test_database, tmp_path)
    _add_student(db_session, "BK002", "Count Student")

    backup_path = service.create_backup()
    isolated_test_database.dispose()

    restored_engine = create_engine(
        f"sqlite:///{backup_path}",
        connect_args={"check_same_thread": False},
    )
    try:
        with restored_engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM students")).scalar_one()
        assert count == 1
    finally:
        restored_engine.dispose()


def test_restore_replaces_live_database(db_session, isolated_test_database, tmp_path):
    service = _backup_service(isolated_test_database, tmp_path)
    _add_student(db_session, "BK003", "Before Backup")
    backup_path = service.create_backup()

    _add_student(db_session, "BK004", "After Backup")
    assert db_session.scalar(select(func.count()).select_from(Student)) == 2

    service.prepare_restore(backup_path)
    isolated_test_database.dispose()
    service.apply_restore(backup_path)

    verify_engine = create_engine(
        f"sqlite:///{service.db_path}",
        connect_args={"check_same_thread": False},
    )
    try:
        with verify_engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM students")).scalar_one()
            names = [
                row[0]
                for row in conn.execute(
                    text("SELECT full_name FROM students ORDER BY student_id")
                )
            ]
        assert count == 1
        assert names == ["Before Backup"]
    finally:
        verify_engine.dispose()


def test_prepare_restore_creates_pre_restore_safety_copy(
    db_session, isolated_test_database, tmp_path
):
    service = _backup_service(isolated_test_database, tmp_path)
    _add_student(db_session, "BK005", "Safety Copy")
    backup_path = service.create_backup()

    pre_restore = service.prepare_restore(backup_path)
    assert pre_restore.name.startswith("fee_management_pre_restore_")
    assert pre_restore.exists()
    service.verify_backup(pre_restore)


def test_corrupt_backup_is_rejected(isolated_test_database, tmp_path):
    service = _backup_service(isolated_test_database, tmp_path)
    service.backup_dir.mkdir(parents=True, exist_ok=True)
    corrupt = service.backup_dir / "corrupt.db"
    corrupt.write_text("not a sqlite database", encoding="utf-8")

    with pytest.raises(BackupIntegrityError):
        service.verify_backup(corrupt)


def test_has_backup_for_today(isolated_test_database, tmp_path):
    service = _backup_service(isolated_test_database, tmp_path)
    # Use real "now" so create_daily_backup_if_needed() matches the same day.
    today = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)
    assert service.has_backup_for_today(today=today) is False

    stamp = today.strftime("%Y%m%d_%H%M%S")
    existing = service.backup_dir / f"fee_management_{stamp}.db"
    service.create_backup()
    renamed = next(service.backup_dir.glob("fee_management_*.db"))
    renamed.rename(existing)

    assert service.has_backup_for_today(today=today) is True
    assert service.create_daily_backup_if_needed() is None


def test_create_daily_backup_if_needed_creates_once(db_session, isolated_test_database, tmp_path):
    service = _backup_service(isolated_test_database, tmp_path)
    _add_student(db_session, "BK006", "Daily Backup")

    first = service.create_daily_backup_if_needed()
    second = service.create_daily_backup_if_needed()

    assert first is not None
    assert second is None
    assert len(list(service.backup_dir.glob("fee_management_*.db"))) == 1


def test_list_backups_sorted_newest_first(db_session, isolated_test_database, tmp_path):
    service = _backup_service(isolated_test_database, tmp_path)
    _add_student(db_session, "BK007", "Listed Backup")

    first = service.create_backup()
    second = service.create_backup()
    backups = service.list_backups()

    assert len(backups) == 2
    assert backups[0].path == second
    assert backups[1].path == first
    assert backups[0].size_bytes > 0


def test_delete_backup_removes_file(db_session, isolated_test_database, tmp_path):
    service = _backup_service(isolated_test_database, tmp_path)
    _add_student(db_session, "BK008", "Delete Me")

    backups = [service.create_backup() for _ in range(5)]
    oldest = backups[0]
    assert oldest.exists()

    service.delete_backup(oldest)

    assert not oldest.exists()
    remaining = service.list_backups()
    assert len(remaining) == 4
    assert all(item.path.exists() for item in remaining)


def test_cannot_delete_protected_recent_backups(db_session, isolated_test_database, tmp_path):
    service = _backup_service(isolated_test_database, tmp_path)
    _add_student(db_session, "BK009", "Protected")

    created = [service.create_backup() for _ in range(5)]
    for protected_path in created[1:]:
        with pytest.raises(BackupProtectedError):
            service.delete_backup(protected_path)
        assert protected_path.exists()

    service.delete_backup(created[0])
    assert not created[0].exists()


def test_cannot_delete_when_four_or_fewer_backups(db_session, isolated_test_database, tmp_path):
    service = _backup_service(isolated_test_database, tmp_path)
    _add_student(db_session, "BK010", "Few Backups")

    only = service.create_backup()
    with pytest.raises(BackupProtectedError):
        service.delete_backup(only)
    assert only.exists()


def test_backup_sort_index_orders_newest_first(db_session, isolated_test_database, tmp_path):
    service = _backup_service(isolated_test_database, tmp_path)
    _add_student(db_session, "BK011", "Sort Index")

    created = [service.create_backup() for _ in range(3)]
    assert service.backup_sort_index(created[-1]) == 0
    assert service.backup_sort_index(created[0]) == 2
    assert service.is_backup_deletable(created[-1]) is False
    assert service.is_backup_deletable(created[0]) is False


def test_delete_backup_rejects_outside_backup_dir(isolated_test_database, tmp_path):
    service = _backup_service(isolated_test_database, tmp_path)
    outside = tmp_path / "outside.db"
    outside.write_bytes(b"sqlite")

    with pytest.raises(ValueError, match="backups folder"):
        service.delete_backup(outside)


def test_delete_backup_rejects_live_database(isolated_test_database, tmp_path):
    service = _backup_service(isolated_test_database, tmp_path)

    with pytest.raises(ValueError, match="live database"):
        service.delete_backup(service.db_path)
