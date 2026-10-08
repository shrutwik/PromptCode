from fastapi.testclient import TestClient
import pytest
from app import db
from app.main import app
client = TestClient(app)

@pytest.mark.parametrize('token,foreign_id', [('tok_acme', 'doc_globex_1'), ('tok_globex', 'doc_acme_1')])
def test_cross_tenant_update_preserves_all_fields(token, foreign_id):
    doc = db.get_by_id(foreign_id)
    before = (doc.title, doc.body, doc.tenant_id)
    headers = {'Authorization': f'Bearer {token}'}
    read = client.get(f'/documents/{foreign_id}', headers=headers)
    assert read.status_code == 404
    assert doc.body not in read.text
    update = client.patch(f'/documents/{foreign_id}', headers=headers, json={'title': 'hacked', 'body': 'hacked'})
    assert update.status_code == 404
    saved = db.get_by_id(foreign_id)
    assert (saved.title, saved.body, saved.tenant_id) == before

@pytest.mark.parametrize('headers', [{}, {'Authorization': 'Bearer unknown'}])
def test_unauthenticated_update_preserves_document(headers):
    response = client.patch('/documents/doc_acme_1', headers=headers, json={'body': 'hacked'})
    assert response.status_code == 401
    assert db.get_by_id('doc_acme_1').body == 'secret-acme'
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

def test_authorized_patch_preserves_other_tenant_and_untouched_fields():
    before = db.get_by_id('doc_globex_1')
    other = (before.title, before.body, before.tenant_id)
    response = client.patch('/documents/doc_acme_1', headers={'Authorization': 'Bearer tok_acme'}, json={'body': 'own updated'})
    assert response.status_code == 200
    saved = client.get('/documents/doc_acme_1', headers={'Authorization': 'Bearer tok_acme'}).json()
    assert saved['body'] == 'own updated'
    assert saved['title'] == 'Acme Plan'
    foreign = db.get_by_id('doc_globex_1')
    assert (foreign.title, foreign.body, foreign.tenant_id) == other

def test_part_three_pressure_case():
    from fastapi.testclient import TestClient
    from app.main import app
    from app import db
    from app.models import Document
    db.reset();db.seed(Document('a','tenant_acme','A','original'));db.seed(Document('b','tenant_globex','B','foreign'));c=TestClient(app)
    ac={'Authorization':'Bearer tok_acme'};other={'Authorization':'Bearer tok_globex'}
    first=c.patch('/documents/a',headers=other,json={'body':'attack'}).status_code
    own=c.patch('/documents/a',headers=ac,json={'body':'updated'}).status_code
    last=c.patch('/documents/a',headers=other,json={'title':'attack'}).status_code
    result=[first,own,last,c.get('/documents/a',headers=ac).json()['body'],db.get_by_id('a').title,db.get_by_id('b').body]
    assert result == [404, 200, 404, 'updated', 'A', 'foreign']
