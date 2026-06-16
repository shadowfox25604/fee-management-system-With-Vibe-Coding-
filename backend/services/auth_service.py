"""Authenticate desktop app users."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.core.master_key import verify_master_key
from backend.core.security import hash_password, verify_password
from backend.models.entities import User

MIN_PASSWORD_LENGTH = 6


class AuthService:
    def __init__(self, session: Session):
        self.session = session

    def authenticate(self, username: str, password: str) -> User | None:
        needle = (username or "").strip()
        if not needle or not password:
            return None
        rows = self.session.query(User).all()
        user = next(
            (row for row in rows if (row.username or "").lower() == needle.lower()),
            None,
        )
        if user is None:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def list_app_users(self) -> list[User]:
        return (
            self.session.query(User)
            .order_by(User.username.asc())
            .all()
        )

    @staticmethod
    def validate_new_password(new_password: str) -> str | None:
        raw = new_password or ""
        if len(raw) < MIN_PASSWORD_LENGTH:
            return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        return None

    def reset_user_password(self, username: str, new_password: str) -> User | None:
        needle = (username or "").strip()
        if not needle:
            return None
        if self.validate_new_password(new_password) is not None:
            return None
        rows = self.session.query(User).all()
        user = next(
            (row for row in rows if (row.username or "").lower() == needle.lower()),
            None,
        )
        if user is None:
            return None
        user.password_hash = hash_password(new_password)
        self.session.commit()
        return user

    def reset_user_password_with_master_key(
        self,
        username: str,
        master_key: str,
        new_password: str,
    ) -> User | None:
        if not verify_master_key(master_key):
            return None
        return self.reset_user_password(username, new_password)
