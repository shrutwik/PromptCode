from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
class OrderOut(BaseModel):
    id: str
    customer_id: str
    total_cents: int
    status: str
class HoldUpdate(BaseModel):
    hold_reason: Optional[str] = Field(default=None, max_length=500)
