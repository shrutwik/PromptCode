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

def test_adjacent_periods_have_one_owner_at_timezone_equivalent_boundary():
    from proration.timeutil import parse_utc
    previous = period_from_iso('2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z')
    following = period_from_iso('2026-02-01T00:00:00Z', '2026-03-01T00:00:00Z')
    instant = parse_utc('2026-02-01T01:00:00+01:00')
    assert not contains(previous, instant)
    assert contains(following, instant)
    assert proration_credit(Subscription('next', 2800, following), '2026-02-01T01:00:00+01:00') == 2800

def test_microsecond_boundaries():
    from proration.timeutil import parse_utc
    period = period_from_iso('2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z')
    assert contains(period, parse_utc('2026-01-31T23:59:59.999999Z'))
    assert not contains(period, parse_utc('2026-02-01T00:00:00.000001Z'))
    assert not contains(period, parse_utc('2025-12-31T23:59:59.999999Z'))

def test_start_credit_is_full_at_equivalent_offset():
    period = period_from_iso('2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z')
    assert proration_credit(Subscription('start', 3100, period), '2025-12-31T19:00:00-05:00') == 3100
