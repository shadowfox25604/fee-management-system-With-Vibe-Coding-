from backend.core.database import Base, engine
from backend.core.schema_migrations import (
    apply_sqlite_column_migrations,
    apply_sqlite_data_migrations,
)
from backend.models import entities  # noqa: F401

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    print("Database initialized")
