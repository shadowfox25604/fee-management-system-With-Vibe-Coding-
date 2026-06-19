"""Ensure core fee head categories exist (Tuition, Transport)."""

from __future__ import annotations

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import sessionmaker

from backend.models.entities import FeeHead

_DEFAULT_FEE_HEADS: tuple[tuple[str, str, float], ...] = (
    ("Tuition", "monthly", 2000.0),
    ("Transport", "monthly", 500.0),
)


def ensure_default_fee_heads(engine) -> None:
    """Idempotent: create Tuition and Transport fee heads if missing."""
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("fee_heads"):
        return

    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        for name, frequency, default_amount in _DEFAULT_FEE_HEADS:
            exists = session.scalars(
                select(FeeHead).where(func.lower(FeeHead.head_name) == name.lower()).limit(1)
            ).first()
            if exists is None:
                session.add(
                    FeeHead(
                        head_name=name,
                        frequency=frequency,
                        default_amount=float(default_amount),
                    )
                )
        session.commit()
    finally:
        session.close()
