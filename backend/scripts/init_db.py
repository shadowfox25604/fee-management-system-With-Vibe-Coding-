from backend.core.database import Base, engine
from backend.models import entities  # noqa: F401
if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Database initialized")
