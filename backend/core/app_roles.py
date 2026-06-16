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
    "Reports",
    "Backup",
    "Fee Control",
    "Login Access",
)

ACCOUNTANT_PAGE_KEYS: frozenset[str] = frozenset(
    {
        "Collect Payment",
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
