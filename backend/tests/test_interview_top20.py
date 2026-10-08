"""Protect the requested editorial selection, metadata and retained library content."""
import json
from pathlib import Path

from app.schemas.interview import ChallengeProgressCard, InterviewChallengeCard
from app.services.interview.registry import list_challenges

DOCS=Path(__file__).resolve().parents[2]/'docs'

def test_featured_selection_matches_reviewed_scorecard_exactly():
    manifest=json.loads((DOCS/'interview-top20-manifest.json').read_text())
    scores=json.loads((DOCS/'ai-assisted-interview-scoring.json').read_text())
    ranked=sorted((r for r in scores['rows'] if r['overall_rank']<=20),key=lambda r:r['overall_rank'])
    selected=manifest['questions']
    assert [(q['rank'],q['research_name'],q['selection_score']) for q in selected]==[(r['overall_rank'],r['name'],r['weighted_score']) for r in ranked]
    cards=list_challenges()
    assert [(c['featured_rank'],c['slug']) for c in cards if c.get('featured_rank')]==[(q['rank'],q['slug']) for q in selected]
    assert len(cards)==25 and len({c['slug'] for c in cards})==25
    assert all(c.get('featured_rank') is None for c in cards[20:])

def test_rank_survives_both_candidate_card_shapes():
    for card in list_challenges():
        assert InterviewChallengeCard(**card).featured_rank==card.get('featured_rank')
        assert ChallengeProgressCard(**card).featured_rank==card.get('featured_rank')


def test_existing_original_questions_remain_available():
    slugs={c['slug'] for c in list_challenges()}
    assert {'invoice-status-transition','order-hold-reason','catalog-suggest-latency','notification-feed-stale','workspace-label-propagation','shipment-csv-merge','tenant-document-acl','webhook-delivery-retry','pricing-rule-extract','subscription-proration-boundary'}<=slugs
