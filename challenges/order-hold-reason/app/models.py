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
