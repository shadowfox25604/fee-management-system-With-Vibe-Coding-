# School Fee Management (Offline)

Desktop application for offline school fee operations using Python + PySide6 + SQLite.

## Features
- Search students by ID, name, or phone.
- Maintain student profiles and fee plans.
- Record payments with receipt numbers.
- Generate collection and defaulter reports.
- Export reports to Excel/PDF.
- Backup and restore local database.

## Quick Start (Command Prompt + uv)
1. Open Command Prompt in the project folder.
2. Create virtual environment: `uv venv`
3. Install dependencies: `uv sync`
4. Initialize DB: `set PYTHONPATH=. && uv run python scripts/init_db.py`
5. Seed sample data: `set PYTHONPATH=. && uv run python scripts/seed_data.py`
6. Run app: `set PYTHONPATH=. && uv run python -m app.main`

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
This creates the local SQLite database in `data/fee_management.db`.

```cmd
set PYTHONPATH=. && uv run python scripts/init_db.py
```

### 6) Seed sample records (for testing/demo)

```cmd
set PYTHONPATH=. && uv run python scripts/seed_data.py
```

Sample admin user created by seeding:
- Username: `admin`
- Password: `admin123`

### 7) Run the desktop application

```cmd
set PYTHONPATH=. && uv run python -m app.main
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

### Remove leftover test students from the database

Integration tests that use the real `data/fee_management.db` file **clean up automatically**: after each run they delete any student created in that test (and related invoices, payments, allocations, fee plans).

The helper lives in `tests/db_cleanup.py` (`cleanup_test_students`).

If older runs left rows before this behavior existed, delete them **once** by exact `full_name` with:

```cmd
set PYTHONPATH=. && uv run python -m scripts.remove_test_students
```

If you use an activated virtual environment without `uv`:

```cmd
set PYTHONPATH=.
`python -m scripts.remove_test_students`
```

This script does **not** remove normal demo/seed students created by `scripts/seed_data.py` (typically `STU…` IDs with random names), unless a row happens to use one of the same test-only full names.

## Build EXE for school staff machines

```cmd
.\scripts\build_exe.ps1
```

Or directly:

```cmd
uv run pyinstaller --onefile --noconsole --name fee-manager app/main.py
```

Output binary is created under `dist/`.

## Backup and Restore
- Backups are stored in `data/backups/`.
- Manual backup script:

```cmd
set PYTHONPATH=. && uv run python scripts/backup_now.py
```

- In-app restore is available in the **Backup** tab.

## Troubleshooting

### `ModuleNotFoundError: No module named 'app'`
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

## Project Structure
- `app/` - main application source code
- `app/ui/` - PySide6 UI layer
- `app/services/` - business rules
- `app/repositories/` - database query layer
- `app/models/` - SQLAlchemy models
- `app/reports/` - Excel/PDF exporters
- `scripts/` - operational scripts
- `tests/` - test cases
- `data/` - local database and backups
