from __future__ import annotations
from fastapi import FastAPI, HTTPException
from . import db
from .models import Order
from .schemas import HoldUpdate
from . import service

app = FastAPI(title="Order Service")

@app.get("/orders/{order_id}")
def get_order(order_id: str):
    order = db.get(order_id)
    if not order: raise HTTPException(404, "order not found")
    return service.to_public_dict(order)

@app.post("/orders/{order_id}/hold")
def hold_order(order_id: str, body: HoldUpdate):
    try: order = service.place_on_hold(order_id, body.hold_reason)
    except KeyError: raise HTTPException(404, "order not found")
    return service.to_public_dict(order)

@app.post("/orders/{order_id}/release")
def release_order(order_id: str):
    try: order = service.clear_hold(order_id)
    except KeyError: raise HTTPException(404, "order not found")
    return service.to_public_dict(order)
