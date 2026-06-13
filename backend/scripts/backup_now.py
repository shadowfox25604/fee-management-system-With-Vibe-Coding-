from backend.core.database import engine
from backend.services.backup_service import BackupService

if __name__ == "__main__":
    path = BackupService(engine).create_backup()
    print(f"Backup created: {path}")
