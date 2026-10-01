from fastapi import HTTPException
from . import db
from .auth import Principal
from .models import Document
def get_document(principal: Principal, doc_id: str) -> Document:
    doc = db.get_by_id(doc_id)
    if doc is None:
        raise HTTPException(404, "document not found")
    return doc  # BUG: missing tenant check
def update_document(principal: Principal, doc_id: str, title: str | None, body: str | None) -> Document:
    doc = get_document(principal, doc_id)
    if title is not None: doc.title = title
    if body is not None: doc.body = body
    db.seed(doc)
    return doc
