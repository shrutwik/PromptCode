"""Process-local order map keyed by id. reset() empties it. seed and upsert store the same object the caller passed."""
from __future__ import annotations
from typing import Dict, Optional
from .models import Order
_DB: Dict[str, Order] = {}
def reset() -> None: _DB.clear()
def seed(order: Order) -> None: _DB[order.id] = order
def get(order_id: str) -> Optional[Order]: return _DB.get(order_id)
def upsert(order: Order) -> Order:
    _DB[order.id] = order
    return order
def all_orders() -> list[Order]: return list(_DB.values())
