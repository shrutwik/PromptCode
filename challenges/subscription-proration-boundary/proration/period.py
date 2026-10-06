"""Billing period as two UTC datetimes.

period_from_iso parses start and end. contains reports whether an instant falls in the period.
days_in_period is the length in whole days, at least 1.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from .timeutil import parse_utc

@dataclass(frozen=True)
class Period:
    start: datetime
    end: datetime

def period_from_iso(start: str, end: str) -> Period:
    return Period(parse_utc(start), parse_utc(end))

def contains(period: Period, instant: datetime) -> bool:
    return period.start <= instant <= period.end

def days_in_period(period: Period) -> int:
    return max(1, int((period.end - period.start).total_seconds() // 86400))
