"""Document row. id is the path key. tenant_id is the org that owns it. title and body are the content Acme was able to read."""
from dataclasses import dataclass
@dataclass
class Document:
    id: str
    tenant_id: str
    title: str
    body: str
