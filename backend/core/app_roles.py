"""Application login roles and page access rules."""

from __future__ import annotations

from dataclasses import dataclass

ROLE_ADMIN = "admin"
ROLE_ACCOUNTANT = "accountant"

ALL_PAGE_KEYS: tuple[str, ...] = (
    "Home Page",
    "Student Search",
    "Student Details",
    "Collect Payment",
    "Payment History",
    "Salary",
    "Salary Control",
    "Salary History",
    "Miscellaneous",
    "Income Management",
    "Add Faculty",
    "Add Student",
    "Delete Member",
    "Reports",
    "Backup",
    "Fee Control",
    "Login Access",
)

ACCOUNTANT_PAGE_KEYS: frozenset[str] = frozenset(
    {
        "Collect Payment",
        "Miscellaneous",
        "Income Management",
    }
)


@dataclass(frozen=True)
class AppUserCredentials:
    username: str
    password: str
    role: str
    display_name: str


DEFAULT_APP_USERS: tuple[AppUserCredentials, ...] = (
    AppUserCredentials("Admin", "Admin@1123", ROLE_ADMIN, "Administrator"),
    AppUserCredentials("Accountant", "Acc@123", ROLE_ACCOUNTANT, "Accountant"),
)


def allowed_page_keys(role: str) -> frozenset[str]:
    if role == ROLE_ACCOUNTANT:
        return ACCOUNTANT_PAGE_KEYS
    return frozenset(ALL_PAGE_KEYS)


def default_page_key(role: str) -> str:
    if role == ROLE_ACCOUNTANT:
        return "Collect Payment"
    return "Home Page"


def role_display_name(role: str) -> str:
    if role == ROLE_ACCOUNTANT:
        return "Accountant"
    return "Administrator"


def can_modify_ledger_entries(role: str) -> bool:
    return role == ROLE_ADMIN


def require_ledger_entry_modify_permission(role: str) -> None:
    if not can_modify_ledger_entries(role):
        raise ValueError("Only an administrator can modify or delete recorded entries.")


def operator_name_for_role(role: str) -> str:
    if role == ROLE_ACCOUNTANT:
        return ROLE_ACCOUNTANT
    return ROLE_ADMIN


def format_operator_display(operator_name: str) -> str:
    value = (operator_name or "").strip().lower()
    if value in (ROLE_ADMIN, ROLE_ACCOUNTANT):
        return value
    return ""
