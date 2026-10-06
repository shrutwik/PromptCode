"""Subscription credit at cancel time.

proration_credit returns 0 when the cancel instant is outside the period.
Otherwise it is monthly_cents times remaining whole days over days_in_period, as an int.
describe_cancel formats the instant for humans and appends the credit. The formatted string is not an input to the math.
"""
from __future__ import annotations
from dataclasses import dataclass
from .period import Period, contains, days_in_period
from .timeutil import parse_utc, format_display

@dataclass
class Subscription:
    id: str
    monthly_cents: int
    period: Period

def proration_credit(sub: Subscription, cancel_at_iso: str) -> int:
    cancel_at = parse_utc(cancel_at_iso)
    if not contains(sub.period, cancel_at):
        return 0
    remaining_days = int((sub.period.end - cancel_at).total_seconds() // 86400)
    total_days = days_in_period(sub.period)
    return int(sub.monthly_cents * remaining_days / total_days)

def describe_cancel(sub: Subscription, cancel_at_iso: str) -> str:
    cancel_at = parse_utc(cancel_at_iso)
    return f"cancel {format_display(cancel_at)} credit={proration_credit(sub, cancel_at_iso)}"
