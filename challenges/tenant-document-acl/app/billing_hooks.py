"""Seat-change hook. It does not load documents and does not check access."""
def on_seat_change(tenant_id: str, seats: int) -> None:
    return None
