from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(slots=True)
class SyncDecision:
    should_refresh: bool
    reason: str
    age_minutes: int | None = None


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def sync_age_minutes(value: str | None) -> int | None:
    stamp = parse_timestamp(value)
    if stamp is None:
        return None
    delta = datetime.now(timezone.utc) - stamp
    return max(0, int(delta.total_seconds() // 60))


def decide_refresh(
    *,
    last_sync: str | None,
    ttl_minutes: int,
    force: bool = False,
    offline: bool = False,
) -> SyncDecision:
    if offline:
        return SyncDecision(False, "offline")
    if force:
        return SyncDecision(True, "forced")

    age = sync_age_minutes(last_sync)
    if age is None:
        return SyncDecision(True, "never_synced")

    ttl = max(1, int(ttl_minutes))
    if age >= ttl:
        return SyncDecision(True, "stale", age_minutes=age)

    return SyncDecision(False, "fresh", age_minutes=age)


def relative_sync_text(value: str | None) -> str:
    age = sync_age_minutes(value)
    if age is None:
        return "nunca"

    if age < 1:
        return "agora"
    if age < 60:
        return f"há {age} min"

    hours = age // 60
    if hours < 24:
        return f"há {hours} h"

    days = hours // 24
    if days == 1:
        return "ontem"
    return f"há {days} dias"
