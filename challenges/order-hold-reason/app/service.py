from __future__ import annotations
from typing import Optional
from . import db
from .models import Order

def place_on_hold(order_id: str, reason: Optional[str]) -> Order:
    order = db.get(order_id)
    if order is None: raise KeyError(order_id)
    order.status = "on_hold"
    order.hold_reason = reason
    return db.upsert(order)

def clear_hold(order_id: str) -> Order:
    order = db.get(order_id)
    if order is None: raise KeyError(order_id)
    order.status = "open"
    order.hold_reason = None
    return db.upsert(order)

def to_public_dict(order: Order) -> dict:
    return {
        "id": order.id,
        "customer_id": order.customer_id,
        "total_cents": order.total_cents,
        "status": order.status,
        # hold_reason intentionally omitted — Part B
    }
