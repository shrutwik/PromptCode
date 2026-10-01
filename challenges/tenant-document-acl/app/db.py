from typing import Optional
from .models import Document
_DOCS: dict[str, Document] = {}
def reset() -> None: _DOCS.clear()
def seed(doc: Document) -> None: _DOCS[doc.id] = doc
def get_by_id(doc_id: str) -> Optional[Document]: return _DOCS.get(doc_id)
def list_for_tenant(tenant_id: str) -> list[Document]:
    return [d for d in _DOCS.values() if d.tenant_id == tenant_id]
