from __future__ import annotations

import re
import shutil
import sqlite3
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import Engine

from backend.core.config import BACKUP_DIR, DB_PATH

_BACKUP_NAME_RE = re.compile(
    r"^fee_management_(?P<date>\d{8})_(?P<time>\d{6})\.db$", re.IGNORECASE
)
PROTECTED_RECENT_BACKUP_COUNT = 4


class BackupIntegrityError(ValueError):
    """Raised when a backup file fails SQLite integrity_check."""


class BackupProtectedError(ValueError):
    """Raised when attempting to delete one of the most recent protected backups."""


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    name: str
    created_at: datetime
    size_bytes: int

    @property
    def size_label(self) -> str:
        size = self.size_bytes
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"


class BackupService:
    def __init__(
        self,
        engine: Engine | None = None,
        *,
        db_path: Path | None = None,
        backup_dir: Path | None = None,
    ) -> None:
        self.engine = engine
        self.db_path = db_path or DB_PATH
        self.backup_dir = backup_dir or BACKUP_DIR

    def create_backup(self, label: str = "fee_management") -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = self.backup_dir / f"{label}_{stamp}.db"
        suffix = 0
        while dest.exists():
            suffix += 1
            dest = self.backup_dir / f"{label}_{stamp}_{suffix}.db"
        self._sqlite_snapshot(dest)
        return dest

    def verify_backup(self, backup_path: Path) -> None:
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file does not exist: {backup_path}")
        try:
            conn = sqlite3.connect(str(backup_path))
        except sqlite3.DatabaseError as exc:
            raise BackupIntegrityError(f"Backup file is damaged or incomplete: {exc}") from exc
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as exc:
            raise BackupIntegrityError(f"Backup file is damaged or incomplete: {exc}") from exc
        finally:
            conn.close()
        if not row or row[0] != "ok":
            detail = row[0] if row else "unknown error"
            raise BackupIntegrityError(f"Backup file is damaged or incomplete: {detail}")

    def list_backups(self) -> list[BackupInfo]:
        if not self.backup_dir.exists():
            return []
        items: list[BackupInfo] = []
        for path in self.backup_dir.glob("*.db"):
            if not path.is_file():
                continue
            stat = path.stat()
            created = self._timestamp_from_name(path.name) or datetime.fromtimestamp(stat.st_mtime)
            items.append(
                BackupInfo(
                    path=path,
                    name=path.name,
                    created_at=created,
                    size_bytes=stat.st_size,
                )
            )
        items.sort(key=lambda item: (item.created_at, item.name), reverse=True)
        return items

    def latest_backup(self) -> BackupInfo | None:
        backups = self.list_backups()
        return backups[0] if backups else None

    @staticmethod
    def _path_key(path: Path) -> str:
        return os.path.normcase(str(path.resolve()))

    def backup_sort_index(self, backup_path: Path) -> int | None:
        """Return 0 for the newest backup, 1 for the next, etc."""
        try:
            target_key = self._path_key(self._resolve_backup_path(backup_path))
        except (FileNotFoundError, ValueError):
            return None
        for idx, item in enumerate(self.list_backups()):
            if self._path_key(item.path) == target_key:
                return idx
        return None

    def protected_backup_paths(self) -> frozenset[Path]:
        """Paths of the newest backups that cannot be deleted."""
        backups = self.list_backups()
        protected = backups[:PROTECTED_RECENT_BACKUP_COUNT]
        return frozenset(item.path.resolve() for item in protected)

    def is_backup_deletable(self, backup_path: Path) -> bool:
        idx = self.backup_sort_index(backup_path)
        if idx is None:
            return False
        return idx >= PROTECTED_RECENT_BACKUP_COUNT

    def delete_backup(self, backup_path: Path) -> None:
        """Permanently delete a backup file from the backup folder."""
        resolved = self._resolve_deletable_backup(backup_path)
        resolved.unlink()

    def _resolve_backup_path(self, backup_path: Path) -> Path:
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file does not exist: {backup_path}")
        if not backup_path.is_file():
            raise ValueError(f"Not a backup file: {backup_path}")

        backup_dir = self.backup_dir.resolve()
        candidate = backup_path.resolve()
        live_db = self.db_path.resolve()

        if candidate == live_db:
            raise ValueError("Cannot delete the live database file.")
        try:
            candidate.relative_to(backup_dir)
        except ValueError as exc:
            raise ValueError("Backup file must be inside the backups folder.") from exc
        if candidate.suffix.lower() != ".db":
            raise ValueError("Only .db backup files can be deleted from here.")
        return candidate

    def _resolve_deletable_backup(self, backup_path: Path) -> Path:
        candidate = self._resolve_backup_path(backup_path)
        idx = self.backup_sort_index(candidate)
        if idx is None or idx < PROTECTED_RECENT_BACKUP_COUNT:
            raise BackupProtectedError(
                f"The {PROTECTED_RECENT_BACKUP_COUNT} most recent backups are protected "
                "and cannot be deleted."
            )
        return candidate

    def has_backup_for_today(self, *, today: datetime | None = None) -> bool:
        day = (today or datetime.now()).strftime("%Y%m%d")
        prefix = f"fee_management_{day}_"
        return any(
            path.name.startswith(prefix)
            for path in self.backup_dir.glob("fee_management_*.db")
            if path.is_file()
        )

    def create_daily_backup_if_needed(self) -> Path | None:
        if self.has_backup_for_today():
            return None
        return self.create_backup()

    def create_pre_restore_backup(self) -> Path:
        return self.create_backup(label="fee_management_pre_restore")

    def prepare_restore(self, backup_path: Path) -> Path:
        """Verify backup and snapshot the current database before restore."""
        self.verify_backup(backup_path)
        return self.create_pre_restore_backup()

    def apply_restore(self, backup_path: Path) -> None:
        """Replace the live database file. Call after session.close() and engine.dispose()."""
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file does not exist: {backup_path}")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_path, self.db_path)

    def restore_backup(self, backup_path: Path) -> Path:
        """Verify, create a pre-restore safety copy, and replace the live database file."""
        pre_restore = self.prepare_restore(backup_path)
        if self.engine is not None:
            self.engine.dispose()
        self.apply_restore(backup_path)
        return pre_restore

    def _sqlite_snapshot(self, dest_path: Path) -> None:
        if self.engine is not None:
            raw_conn = self.engine.raw_connection()
            try:
                source = raw_conn.driver_connection
                dest = sqlite3.connect(str(dest_path))
                try:
                    source.backup(dest)
                finally:
                    dest.close()
            finally:
                raw_conn.close()
            return

        source = sqlite3.connect(str(self.db_path))
        try:
            dest = sqlite3.connect(str(dest_path))
            try:
                source.backup(dest)
            finally:
                dest.close()
        finally:
            source.close()

    @staticmethod
    def _timestamp_from_name(name: str) -> datetime | None:
        match = _BACKUP_NAME_RE.match(name) or re.match(
            r"^fee_management_pre_restore_(?P<date>\d{8})_(?P<time>\d{6})\.db$",
            name,
            re.IGNORECASE,
        )
        if not match:
            return None
        try:
            return datetime.strptime(
                f"{match.group('date')}{match.group('time')}",
                "%Y%m%d%H%M%S",
            )
        except ValueError:
            return None
