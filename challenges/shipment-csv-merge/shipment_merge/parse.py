from __future__ import annotations
import csv, io
from .models import ShipmentEvent
def parse_csv(text: str) -> list[ShipmentEvent]:
    reader = csv.DictReader(io.StringIO(text))
    return [ShipmentEvent(row["event_id"], row["shipment_id"], row["status"], row["ts"], int(row["quantity_delta"])) for row in reader]
