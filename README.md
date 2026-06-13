# School Fee Management (Offline)

Desktop application for offline school fee operations using Python + PySide6 + SQLite.

## Features
- Search students by ID, name, or phone.
- Maintain student profiles and fee plans.
- Record payments with receipt numbers.
- Generate collection and defaulter reports.
- Export reports to Excel/PDF.
- Backup and restore local database (automatic daily backup + manual backup).

## Quick Start (Command Prompt + uv)
1. Open Command Prompt in the project folder.
2. Create virtual environment: `uv venv`
3. Install dependencies: `uv sync`
4. Initialize DB: `set PYTHONPATH=. && uv run python backend/scripts/init_db.py`
5. Seed sample data: `set PYTHONPATH=. && uv run python backend/scripts/seed_data.py`
6. Run app: `set PYTHONPATH=. && uv run python -m frontend.main`

## Detailed Setup and Run Guide

### 1) Prerequisites
- Windows 10/11
- Python 3.12+ installed and available as `python`
- `uv` installed and available as `uv`
- Internet connection only for first-time dependency installation

Verify Python and uv:

```cmd
python --version
uv --version
```

### 2) Open project folder
In Command Prompt:

```cmd
cd "c:\Users\Acer\Desktop\fee management"
```

### 3) Create and activate virtual environment
Create venv:

```cmd
uv venv
```

Activate venv:

```cmd
.venv\Scripts\activate
```

### 4) Install dependencies

```cmd
uv sync
```

### 5) Initialize database schema
This creates the local SQLite database in `data/fee_management.db` and applies schema migrations.

```cmd
set PYTHONPATH=. && uv run python backend/scripts/init_db.py
```

Opening the app also runs migrations automatically on startup.

### 6) Seed sample records (for testing/demo)

```cmd
set PYTHONPATH=. && uv run python backend/scripts/seed_data.py
```

Sample admin user created by seeding:
- Username: `admin`
- Password: `admin123`

### 7) Run the desktop application

```cmd
set PYTHONPATH=. && uv run python -m frontend.main
```

### 8) Basic usage flow
1. Open **Student Search** tab.
2. Search by student ID, name, or phone.
3. Select a student row.
4. Go to **Collect Payment** tab and enter amount/mode and date of payment.
5. Use **Reports** tab to load defaulters.
6. Export report to Excel or PDF.
7. Use **Backup** tab for DB backup/restore.

## Running Tests

```cmd
set PYTHONPATH=. && uv run pytest -q
```

Tests use an isolated temporary SQLite database per test case. The production file `data/fee_management.db` is never read or written during `pytest`.

### Remove leftover test students from the database

If older runs left rows in the production database, delete them with:

```cmd
set PYTHONPATH=. && uv run python backend/scripts/remove_test_students.py
```

This script does **not** remove normal demo/seed students created by `backend/scripts/seed_data.py` unless a row uses a test-only full name.

## Build EXE for school staff machines

```cmd
.\scripts\build_exe.ps1
```

Or directly:

```cmd
uv run pyinstaller --onefile --noconsole --name fee-manager frontend/main.py
```

Output binary is created under `dist/`.

## Backup and Restore
- All data lives in `data/fee_management.db` on your computer (no external database).
- Backups are stored in `data/backups/`.
- The app creates **one automatic backup per day** the first time you open it that day.
- You can also create a manual backup anytime from the **Backup** tab or CLI.

Manual backup script:

```cmd
set PYTHONPATH=. && uv run python backend/scripts/backup_now.py
```

Restore from CLI (app must be closed first):

```cmd
set PYTHONPATH=. && uv run python backend/scripts/restore_backup.py data\backups\fee_management_YYYYMMDD_HHMMSS.db
```

In-app restore is available in the **Backup** tab:
1. Select a backup from the list (or choose another file).
2. Confirm that you want to replace all current data.
3. Click **Proceed** when prompted — the app restarts automatically to load the backup.
4. Before restore, a safety copy of your current data is saved as `fee_management_pre_restore_*.db`.

## Troubleshooting

### `ModuleNotFoundError`
Run with:

```cmd
set PYTHONPATH=.
```

then retry command.

### `No module named pytest`
Install dependencies in active venv:

```cmd
uv sync
```

### PySide6 window does not open
- Confirm PySide6 is installed in current environment.
- Re-run from activated venv.

### SQLite DB lock issues
- Close any DB browser/editor connected to `data/fee_management.db`.
- Restart app and retry.

### Restore did not show new data
- After restore, the app must restart. Use the in-app **Proceed** button, or close and reopen manually if you restored from CLI.

## Project Structure
- `frontend/` - PySide6 UI and application entry (`frontend/main.py`)
- `backend/` - business logic, repositories, models, reports, and scripts
- `backend/scripts/` - operational scripts (`init_db.py`, `seed_data.py`, `backup_now.py`, `restore_backup.py`)
- `tests/` - test cases (isolated temp database per test)
- `data/` - local database and backups
