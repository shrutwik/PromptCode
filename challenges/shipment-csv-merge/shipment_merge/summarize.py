from __future__ import annotations
from .merge import merge_events, total_quantity
from .models import ShipmentEvent
def summarize(batches: list[list[ShipmentEvent]]) -> dict:
    timeline = merge_events(batches)
    by_shipment: dict[str, list[str]] = {}
    for event in timeline:
        by_shipment.setdefault(event.shipment_id, []).append(event.status)
    return {"timelines": by_shipment, "quantities": {sid: total_quantity(sid) for sid in by_shipment}}
