import pytest
from app import db
from app.models import Document
@pytest.fixture(autouse=True)
def seed_docs():
    db.reset()
    db.seed(Document("doc_acme_1", "tenant_acme", "Acme Plan", "secret-acme"))
    db.seed(Document("doc_globex_1", "tenant_globex", "Globex Plan", "secret-globex"))
