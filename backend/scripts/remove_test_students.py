"""
Remove students left in the database by pytest (when tests used the production DB).

Usage (from project root, PYTHONPATH=.):
    uv run python -m backend.scripts.remove_test_students
"""

from backend.core.database import SessionLocal
from tests.db_cleanup import remove_all_test_students


def main() -> None:
    session = SessionLocal()
    try:
        n = remove_all_test_students(session)
        if n == 0:
            print("No pytest test students found in the database.")
        else:
            print(f"Removed {n} test student(s) and related fee data.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
