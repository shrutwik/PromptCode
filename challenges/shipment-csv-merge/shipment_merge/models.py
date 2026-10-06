"""One scan from a warehouse file. event_id identifies the scan. ts is the event time. quantity_delta is an integer."""
from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class ShipmentEvent:
    event_id: str
    shipment_id: str
    status: str
    ts: str
    quantity_delta: int
