"""Shared fee-head classification helpers."""

from sqlalchemy import func, or_

from backend.models import FeeHead


def van_fee_head_filter():
    hn = func.lower(FeeHead.head_name)
    return or_(
        hn == "transport",
        hn == "van",
        hn == "van fee",
        hn == "van fees",
        hn == "bus",
        hn == "conveyance",
    )


def van_fee_head_name_match(head_name: str) -> bool:
    hn = (head_name or "").strip().lower()
    return hn in ("transport", "van", "van fee", "van fees", "bus", "conveyance")
