"""Fold CSV batches into one event list and remember quantity deltas.

A batch is one file: a list of ShipmentEvent. merge_events takes every batch.
total_quantity reads the per-shipment totals stored on the last merge_events call.
"""
from __future__ import annotations
from collections import defaultdict
from .models import ShipmentEvent

def merge_events(batches: list[list[ShipmentEvent]]) -> list[ShipmentEvent]:
    """Combine batches into the list summarize turns into a timeline."""
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
            qty[event.shipment_id] += event.quantity_delta
            continue
        seen_status.add(key)
        out.append(event)
        qty[event.shipment_id] += event.quantity_delta
    merge_events.last_qty = dict(qty)  # type: ignore[attr-defined]
    return out

def total_quantity(shipment_id: str) -> int:
    return int(getattr(merge_events, "last_qty", {}).get(shipment_id, 0))
