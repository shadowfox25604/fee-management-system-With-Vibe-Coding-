import os
import shutil
import sys
from pathlib import Path

APP_DISPLAY_NAME = "ACE School Management"


def _resolve_base_dir() -> Path:
    """Project root in dev; folder containing the .exe when frozen."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _default_user_data_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path.home() / ".local" / "share"
    return root / APP_DISPLAY_NAME


def _resolve_data_dir() -> Path:
    """One shared data folder for every installed copy of the app."""
    override = os.environ.get("FEE_MANAGEMENT_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if os.environ.get("FEE_MANAGEMENT_TESTING") == "1":
        return _resolve_base_dir() / "data"
    if getattr(sys, "frozen", False):
        return _default_user_data_dir()
    return _resolve_base_dir() / "data"


def _collect_legacy_database_candidates() -> list[Path]:
    project_root = Path(__file__).resolve().parents[2]
    candidates: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        if not path.is_file():
            return
        resolved = path.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        candidates.append(resolved)

    add(project_root / "data" / "fee_management.db")
    add(project_root / "dist" / "data" / "fee_management.db")

    if getattr(sys, "frozen", False):
        add(Path(sys.executable).resolve().parent / "data" / "fee_management.db")
        desktop = Path.home() / "Desktop"
        if desktop.is_dir():
            for db_path in desktop.rglob("fee_management.db"):
                add(db_path)

    return candidates


def _bundled_client_database() -> Path | None:
    """Preloaded client database shipped beside the .exe (Deployment/data/)."""
    if not getattr(sys, "frozen", False):
        return None
    bundled = Path(sys.executable).resolve().parent / "data" / "fee_management.db"
    return bundled if bundled.is_file() else None


def _migrate_legacy_data_if_needed(data_dir: Path) -> None:
    target_db = data_dir / "fee_management.db"
    if target_db.is_file():
        return

    bundled = _bundled_client_database()
    if bundled is not None:
        source_dir = bundled.parent
        data_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled, target_db)
        source_backups = source_dir / "backups"
        target_backups = data_dir / "backups"
        if source_backups.is_dir():
            target_backups.mkdir(parents=True, exist_ok=True)
            for backup in source_backups.glob("*.db"):
                dest = target_backups / backup.name
                if not dest.exists():
                    shutil.copy2(backup, dest)
        for name in ("master_key.txt", "school_name.txt"):
            source_file = source_dir / name
            target_file = data_dir / name
            if source_file.is_file() and not target_file.exists():
                shutil.copy2(source_file, target_file)
        return

    legacy_dbs = _collect_legacy_database_candidates()
    if not legacy_dbs:
        return

    source_db = max(legacy_dbs, key=lambda path: path.stat().st_size)
    source_dir = source_db.parent
    data_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_db, target_db)

    source_backups = source_dir / "backups"
    target_backups = data_dir / "backups"
    if source_backups.is_dir():
        target_backups.mkdir(parents=True, exist_ok=True)
        for backup in source_backups.glob("*.db"):
            dest = target_backups / backup.name
            if not dest.exists():
                shutil.copy2(backup, dest)

    for name in ("master_key.txt", "school_name.txt"):
        source_file = source_dir / name
        target_file = data_dir / name
        if source_file.is_file() and not target_file.exists():
            shutil.copy2(source_file, target_file)


BASE_DIR = _resolve_base_dir()
DATA_DIR = _resolve_data_dir()
_migrate_legacy_data_if_needed(DATA_DIR)
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "fee_management.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
