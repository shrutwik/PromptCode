"""Document routes. List is scoped with list_for_tenant. Get and patch load by id through the service and return id, title, body, and tenant_id."""
from fastapi import Depends, FastAPI
from pydantic import BaseModel
from .auth import Principal, current_principal
from . import db, service
app = FastAPI(title="Docs")
class DocUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
@app.get("/documents")
def list_docs(principal: Principal = Depends(current_principal)):
    return [{"id": d.id, "title": d.title, "tenant_id": d.tenant_id} for d in db.list_for_tenant(principal.tenant_id)]
@app.get("/documents/{doc_id}")
def get_doc(doc_id: str, principal: Principal = Depends(current_principal)):
    doc = service.get_document(principal, doc_id)
    return {"id": doc.id, "title": doc.title, "body": doc.body, "tenant_id": doc.tenant_id}
@app.patch("/documents/{doc_id}")
def patch_doc(doc_id: str, payload: DocUpdate, principal: Principal = Depends(current_principal)):
    doc = service.update_document(principal, doc_id, payload.title, payload.body)
    return {"id": doc.id, "title": doc.title, "body": doc.body, "tenant_id": doc.tenant_id}
