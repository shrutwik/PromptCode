from dataclasses import dataclass
@dataclass
class Document:
    id: str
    tenant_id: str
    title: str
    body: str
