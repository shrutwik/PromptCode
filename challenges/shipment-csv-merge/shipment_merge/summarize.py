"""Timelines and quantities for a set of batches. timelines maps shipment_id to status labels in merge order. quantities maps shipment_id to total_quantity."""
from __future__ import annotations
from .merge import merge_events, total_quantity
from .models import ShipmentEvent
def summarize(batches: list[list[ShipmentEvent]]) -> dict:
    timeline = merge_events(batches)
    by_shipment: dict[str, list[str]] = {}
    for event in timeline:
        by_shipment.setdefault(event.shipment_id, []).append(event.status)
    return {"timelines": by_shipment, "quantities": {sid: total_quantity(sid) for sid in by_shipment}}
