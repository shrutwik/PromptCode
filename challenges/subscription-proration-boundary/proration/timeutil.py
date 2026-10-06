"""UTC parsing and a display clock. parse_utc accepts a trailing Z. format_display renders America/Chicago unless another IANA name is passed. It does not change the instant used for credit."""
from __future__ import annotations
from datetime import datetime, timezone

def parse_utc(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def format_display(dt: datetime, tz_name: str = "America/Chicago") -> str:
    try:
        from zoneinfo import ZoneInfo
        local = dt.astimezone(ZoneInfo(tz_name))
    except Exception:
        local = dt
    return local.strftime("%Y-%m-%d %H:%M %Z")
