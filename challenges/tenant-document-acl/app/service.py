"""Load and update one document for a caller.

get_document looks up doc_id. update_document changes title and body when those arguments are not None.
principal is the authenticated user and tenant. A Document carries its own tenant_id.
"""
from fastapi import HTTPException
from . import db
from .auth import Principal
from .models import Document
def get_document(principal: Principal, doc_id: str) -> Document:
    doc = db.get_by_id(doc_id)
    if doc is None:
        raise HTTPException(404, "document not found")
    return doc
def update_document(principal: Principal, doc_id: str, title: str | None, body: str | None) -> Document:
    doc = get_document(principal, doc_id)
    if title is not None: doc.title = title
    if body is not None: doc.body = body
    db.seed(doc)
    return doc
