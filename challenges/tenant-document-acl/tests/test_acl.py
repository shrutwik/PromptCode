from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
def test_list_is_tenant_scoped():
    res = client.get("/documents", headers={"Authorization": "Bearer tok_acme"})
    assert {d["id"] for d in res.json()} == {"doc_acme_1"}
def test_owner_can_read_own_doc():
    assert client.get("/documents/doc_acme_1", headers={"Authorization": "Bearer tok_acme"}).json()["body"] == "secret-acme"
def test_missing_doc_is_404():
    assert client.get("/documents/nope", headers={"Authorization": "Bearer tok_acme"}).status_code == 404
def test_cross_tenant_get_is_404():
    res = client.get("/documents/doc_globex_1", headers={"Authorization": "Bearer tok_acme"})
    assert res.status_code == 404
    assert "secret-globex" not in res.text
def test_cross_tenant_patch_is_404():
    assert client.patch("/documents/doc_globex_1", headers={"Authorization": "Bearer tok_acme"}, json={"title": "hacked"}).status_code == 404
