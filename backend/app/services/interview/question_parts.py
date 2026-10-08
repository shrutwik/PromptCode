"""Candidate-safe progression drawn from the reviewed, server-owned quality contract."""
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

CONTRACT_PATH = Path(__file__).resolve().parents[3] / 'benchmarks/interview_quality_contract.json'
PUBLIC_FIELDS = ('number', 'title', 'task', 'acceptance', 'mode')


@lru_cache
def _reviewed_parts():
    return json.loads(CONTRACT_PATH.read_text())['questions']


def parts_for(slug: str) -> list[dict]:
    return [deepcopy({key: part[key] for key in PUBLIC_FIELDS})
            for part in _reviewed_parts().get(slug, {}).get('parts', [])]
