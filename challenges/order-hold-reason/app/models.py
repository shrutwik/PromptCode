"""Order row. total_cents is an integer. status is a short string such as open or on_hold. hold_reason is optional text."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Order:
    id: str
    customer_id: str
    total_cents: int
    status: str = "open"
    hold_reason: Optional[str] = None
    meta: dict = field(default_factory=dict)
