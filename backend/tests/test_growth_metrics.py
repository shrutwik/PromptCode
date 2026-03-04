from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.workers.evaluate import _compute_growth, _derive_mastery_state


def test_compute_growth_first_attempt():
    current = SimpleNamespace(
        overall=0.7,
        accuracy=0.8,
        edge_case_handling=0.6,
        efficiency=0.65,
    )
    growth = _compute_growth(previous=None, current=current)
    assert growth["status"] == "first_attempt"
    assert growth["growth_score"] == 0.5


def test_compute_growth_improved_status():
    previous = SimpleNamespace(
        id=uuid.uuid4(),
        score_overall=0.6,
        score_accuracy=0.62,
        score_edge_cases=0.55,
        score_efficiency=0.5,
    )
    current = SimpleNamespace(
        overall=0.74,
        accuracy=0.77,
        edge_case_handling=0.66,
        efficiency=0.6,
    )
    growth = _compute_growth(previous=previous, current=current)
    assert growth["status"] == "improved"
    assert growth["delta_overall"] > 0
    assert growth["growth_score"] > 0.5


def test_mastery_state_mastered_requires_consistency():
    current = SimpleNamespace(overall=0.9, reliability=0.8, edge_case_handling=0.82)
    history = [
        SimpleNamespace(score_overall=0.85, score_reliability=0.72, score_edge_cases=0.77),
        SimpleNamespace(score_overall=0.84, score_reliability=0.69, score_edge_cases=0.8),
    ]
    assert _derive_mastery_state(current=current, history=history) == "mastered"


def test_mastery_state_practicing_for_low_scores():
    current = SimpleNamespace(overall=0.52, reliability=0.4, edge_case_handling=0.48)
    history = [SimpleNamespace(score_overall=0.5, score_reliability=0.45, score_edge_cases=0.42)]
    assert _derive_mastery_state(current=current, history=history) == "practicing"

