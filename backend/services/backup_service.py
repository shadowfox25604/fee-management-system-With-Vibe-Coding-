from datetime import datetime
from pathlib import Path
import shutil
from backend.core.config import BACKUP_DIR, DB_PATH
class BackupService:
    def create_backup(self):
        s=datetime.now().strftime("%Y%m%d_%H%M%S")
        t=BACKUP_DIR / f"fee_management_{s}.db"
        shutil.copy2(DB_PATH,t)
        return t
    def restore_backup(self, backup_path: Path):
        if not backup_path.exists(): raise FileNotFoundError("Backup file does not exist")
        shutil.copy2(backup_path, DB_PATH)
