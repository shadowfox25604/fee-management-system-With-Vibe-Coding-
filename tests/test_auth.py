"""Tests for login users, password verification, and role-based page access."""

from __future__ import annotations

from backend.core.app_roles import (
    ACCOUNTANT_PAGE_KEYS,
    ROLE_ACCOUNTANT,
    ROLE_ADMIN,
    allowed_page_keys,
    default_page_key,
)
from backend.core.security import hash_password, verify_password
from backend.models.entities import User
from backend.services.auth_service import AuthService


def test_verify_password_round_trip():
    raw = "Admin@1123"
    hashed = hash_password(raw)
    assert verify_password(raw, hashed)
    assert not verify_password("wrong", hashed)


def test_seed_migration_creates_login_users(isolated_test_database):
    from backend.core.schema_migrations import apply_sqlite_data_migrations

    apply_sqlite_data_migrations(isolated_test_database)
    from sqlalchemy.orm import sessionmaker

    session = sessionmaker(bind=isolated_test_database)()
    try:
        admin = session.query(User).filter(User.username == "Admin").one()
        accountant = session.query(User).filter(User.username == "Accountant").one()
        assert admin.role == ROLE_ADMIN
        assert accountant.role == ROLE_ACCOUNTANT
        assert verify_password("Admin@1123", admin.password_hash)
        assert verify_password("Acc@123", accountant.password_hash)
    finally:
        session.close()


def test_auth_service_authenticates_users(db_session):
    from backend.core.schema_migrations import apply_sqlite_data_migrations

    apply_sqlite_data_migrations(db_session.get_bind())
    auth = AuthService(db_session)
    admin = auth.authenticate("admin", "Admin@1123")
    accountant = auth.authenticate("Accountant", "Acc@123")
    assert admin is not None
    assert admin.role == ROLE_ADMIN
    assert accountant is not None
    assert accountant.role == ROLE_ACCOUNTANT
    assert auth.authenticate("Admin", "bad-password") is None


def test_role_page_access():
    admin_pages = allowed_page_keys(ROLE_ADMIN)
    accountant_pages = allowed_page_keys(ROLE_ACCOUNTANT)
    assert "Home Page" in admin_pages
    assert "Backup" in admin_pages
    assert "Login Access" in admin_pages
    assert "Home Page" not in accountant_pages
    assert "Login Access" not in accountant_pages
    assert "Miscellaneous" in accountant_pages
    assert accountant_pages == ACCOUNTANT_PAGE_KEYS
    assert default_page_key(ROLE_ADMIN) == "Home Page"
    assert default_page_key(ROLE_ACCOUNTANT) == "Collect Payment"


def test_master_key_verify(tmp_path, monkeypatch):
    import backend.core.master_key as master_key_module

    key_file = tmp_path / "master_key.txt"
    key_file.write_text("Test-Master-Key\n", encoding="utf-8")
    monkeypatch.setattr(master_key_module, "MASTER_KEY_PATH", key_file)

    assert master_key_module.verify_master_key("Test-Master-Key")
    assert not master_key_module.verify_master_key("wrong-key")


def test_reset_user_password(db_session):
    auth = AuthService(db_session)
    user = auth.reset_user_password("Accountant", "NewPass@999")
    assert user is not None
    assert user.username == "Accountant"
    assert auth.authenticate("Accountant", "NewPass@999") is not None
    assert auth.authenticate("Accountant", "Acc@123") is None


def test_reset_with_master_key(db_session, tmp_path, monkeypatch):
    import backend.core.master_key as master_key_module

    key_file = tmp_path / "master_key.txt"
    key_file.write_text("Recovery-Key\n", encoding="utf-8")
    monkeypatch.setattr(master_key_module, "MASTER_KEY_PATH", key_file)

    auth = AuthService(db_session)
    assert auth.reset_user_password_with_master_key("Admin", "wrong-key", "NewAdmin@999") is None
    user = auth.reset_user_password_with_master_key("Admin", "Recovery-Key", "NewAdmin@999")
    assert user is not None
    assert auth.authenticate("Admin", "NewAdmin@999") is not None
