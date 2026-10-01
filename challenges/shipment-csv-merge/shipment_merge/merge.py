from __future__ import annotations
from collections import defaultdict
from .models import ShipmentEvent

def merge_events(batches: list[list[ShipmentEvent]]) -> list[ShipmentEvent]:
    """Merge batches. BUG: dedupes by (shipment_id, status) and still adds qty for skipped rows,
    so duplicate event_ids double-count and repeated status labels drop later events.
    Ordering by timestamp is OK so unique-status happy paths pass.
    """
    combined: list[ShipmentEvent] = []
    for batch in batches:
        combined.extend(batch)
    combined.sort(key=lambda e: (e.shipment_id, e.ts, e.event_id))
    seen_status: set[tuple[str, str]] = set()
    out: list[ShipmentEvent] = []
    qty: dict[str, int] = defaultdict(int)
    for event in combined:
        key = (event.shipment_id, event.status)
        if key in seen_status:
            qty[event.shipment_id] += event.quantity_delta  # double-count risk
            continue
        seen_status.add(key)
        out.append(event)
        qty[event.shipment_id] += event.quantity_delta
    merge_events.last_qty = dict(qty)  # type: ignore[attr-defined]
    return out

def total_quantity(shipment_id: str) -> int:
    return int(getattr(merge_events, "last_qty", {}).get(shipment_id, 0))
