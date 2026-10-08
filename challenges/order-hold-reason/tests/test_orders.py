from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Order

client = TestClient(app)

def setup_function():
    db.reset()
    db.seed(Order(id="ord_legacy", customer_id="c1", total_cents=1000, status="open", hold_reason=None))
    db.seed(Order(id="ord_new", customer_id="c2", total_cents=2500, status="open", hold_reason=None))

def test_get_legacy_order_shape():
    res = client.get("/orders/ord_legacy")
    assert res.status_code == 200
    assert res.json()["id"] == "ord_legacy"

def test_hold_sets_status():
    res = client.post("/orders/ord_new/hold", json={"hold_reason": "fraud_review"})
    assert res.status_code == 200
    assert res.json()["status"] == "on_hold"

def test_release_clears_hold():
    client.post("/orders/ord_new/hold", json={"hold_reason": "stock"})
    res = client.post("/orders/ord_new/release")
    assert res.status_code == 200
    assert res.json()["status"] == "open"

def test_hold_reason_round_trip_and_legacy_null():
    assert client.get("/orders/ord_legacy").json().get("hold_reason") is None
    client.post("/orders/ord_new/hold", json={"hold_reason": "fraud_review"})
    assert client.get("/orders/ord_new").json()["hold_reason"] == "fraud_review"

def test_replacing_reason_preserves_money_and_other_orders():
    client.post('/orders/ord_new/hold', json={'hold_reason': 'first'})
    response = client.post('/orders/ord_new/hold', json={'hold_reason': 'Révision 仓库'})
    assert response.status_code == 200
    saved = client.get('/orders/ord_new').json()
    assert saved['hold_reason'] == 'Révision 仓库'
    assert saved['total_cents'] == 2500
    assert saved['customer_id'] == 'c2'
    legacy = client.get('/orders/ord_legacy').json()
    assert legacy['status'] == 'open'
    assert legacy['hold_reason'] is None

def test_optional_reason_and_repeat_release():
    held = client.post('/orders/ord_new/hold', json={})
    assert held.status_code == 200
    assert held.json()['hold_reason'] is None
    for _ in range(2):
        released = client.post('/orders/ord_new/release')
        assert released.status_code == 200
        assert released.json()['status'] == 'open'
        assert released.json()['hold_reason'] is None

def test_hold_release_and_rehold_use_current_persisted_reason():
    client.post('/orders/ord_new/hold', json={'hold_reason': 'first'})
    client.post('/orders/ord_new/release')
    assert client.get('/orders/ord_new').json()['hold_reason'] is None
    client.post('/orders/ord_new/hold', json={'hold_reason': 'second'})
    saved = client.get('/orders/ord_new').json()
    assert (saved['status'], saved['hold_reason'], saved['total_cents']) == ('on_hold', 'second', 2500)
