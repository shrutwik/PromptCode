"""Server-owned behavioral probes. Expected results never enter candidate containers."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json

@dataclass(frozen=True)
class Case:
    id: str
    weight: int
    probe: str
    expected: object

VERSION = 'behavioral-2026-10-v1'
MANUAL_REQUIREMENTS = {
    'catalog-suggest-latency': ['200ms latency under calibrated load', 'scan instrumentation cannot be self-attested'],
    'notification-feed-stale': ['React rendered badge matches store'],
    'workspace-label-propagation': ['React screen displays persisted labels'],
    'pricing-rule-extract': ['quote delegates to extracted applyRules; source review'],
}

def cases_for(slug: str) -> tuple[Case, ...]:
    from .inventories import INVENTORIES
    if slug not in INVENTORIES:
        raise ValueError('Unsupported trusted evaluation challenge')
    return INVENTORIES[slug]

def inventory_digest(slug: str) -> str:
    items = [{'id':c.id,'weight':c.weight,'probe':c.probe,'expected':c.expected} for c in cases_for(slug)]
    return hashlib.sha256(json.dumps({'version':VERSION,'cases':items,'manual':MANUAL_REQUIREMENTS.get(slug,[])},sort_keys=True,separators=(',',':')).encode()).hexdigest()
