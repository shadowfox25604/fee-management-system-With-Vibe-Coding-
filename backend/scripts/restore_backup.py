import argparse
import sys
from pathlib import Path

from backend.core.database import engine
from backend.services.backup_service import BackupIntegrityError, BackupService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Restore the local fee management database from a backup file.")
    parser.add_argument("backup_path", help="Path to a .db backup file")
    args = parser.parse_args(argv)
    backup_path = Path(args.backup_path)
    service = BackupService(engine)
    try:
        pre_restore = service.prepare_restore(backup_path)
    except BackupIntegrityError as exc:
        print(f"Backup integrity check failed: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    engine.dispose()
    service.apply_restore(backup_path)
    print(f"Backup restored from: {backup_path}")
    print(f"Safety copy of previous data: {pre_restore}")
    print("Close and restart the app to load the restored data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
