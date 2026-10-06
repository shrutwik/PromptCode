from datetime import datetime, timezone
from proration.period import Period, contains, period_from_iso
from proration.billing import Subscription, proration_credit

def test_mid_period_cancel_gets_credit():
    period = period_from_iso("2024-01-01T00:00:00Z", "2024-02-01T00:00:00Z")
    sub = Subscription("s1", 3100, period)
    assert proration_credit(sub, "2024-01-16T00:00:00Z") == 1600

def test_cancel_before_period_no_credit():
    period = period_from_iso("2024-01-01T00:00:00Z", "2024-02-01T00:00:00Z")
    sub = Subscription("s1", 3100, period)
    assert proration_credit(sub, "2023-12-31T23:00:00Z") == 0

def test_contains_start_inclusive():
    period = period_from_iso("2024-01-01T00:00:00Z", "2024-02-01T00:00:00Z")
    assert contains(period, datetime(2024, 1, 1, tzinfo=timezone.utc)) is True

def test_cancel_exactly_at_period_end_no_credit():
    period = period_from_iso("2024-01-01T00:00:00Z", "2024-02-01T00:00:00Z")
    sub = Subscription("s1", 3100, period)
    assert contains(period, period.end) is False
    assert proration_credit(sub, "2024-02-01T00:00:00Z") == 0

def test_display_helper_smoke():
    from proration.timeutil import format_display, parse_utc
    assert "2024" in format_display(parse_utc("2024-01-01T06:00:00Z"))
