import copy

import pytest

from app.services.interview.grading import DIMENSIONS
from app.services.interview.grading_calibration import calibration_report, pilot_template, weighted_kappa


def record(index, rating):
    return {"attempt_id": str(index), "challenge_slug": "question", "challenge_version": "1",
        "rubric_version": "v3-evidence", "synthetic": False, "external_verified": True,
        "snapshot_digest": "s", "packet_digest": "p", "evaluator_version": "e",
        "inventory_digest": "i", "ai_available": True,
        "reviews": [{"reviewer_id": name, "reviewer_kind": "human", "packet_digest": "p",
                     "ratings": {dimension: rating for dimension in DIMENSIONS}}
                    for name in ("first", "second")]}


def test_kappa_known_agreement_and_degenerate():
    assert weighted_kappa([(0,0), (2,2), (4,4)]) == 1
    assert weighted_kappa([(3,3)] * 30) is None
    assert weighted_kappa([]) is None


def test_small_pilot_never_releases():
    result = calibration_report([record(0, 3)], challenges=["question"])
    assert not result["release_ready"]
    assert not result["agreement_gate_met"]


def test_sufficient_agreement_still_needs_independent_release_gates():
    records = [record(i, i % 5) for i in range(30)]
    result = calibration_report(records, challenges=["question"])
    assert result["agreement_gate_met"]
    assert not result["release_ready"]


@pytest.mark.parametrize("field,value", [("synthetic",True), ("external_verified",False),
                                        ("packet_digest", "changed")])
def test_invalid_attempts_rejected(field, value):
    attempt = record(1, 3)
    attempt[field] = value
    result = calibration_report([attempt], challenges=["question"])
    assert result["status"] == "invalid_data"


def test_same_reviewer_missing_rating_model_and_duplicate_rejected():
    original = record(1, 3)
    same = copy.deepcopy(original)
    same["reviews"][1]["reviewer_id"] = "first"
    model = copy.deepcopy(original)
    model["attempt_id"] = "2"
    model["reviews"][1]["reviewer_kind"] = "AI"
    missing = copy.deepcopy(original)
    missing["attempt_id"] = "3"
    missing["reviews"][0]["ratings"].pop("A_correctness")
    result = calibration_report([same, model, missing, original], challenges=["question"])
    assert len(result["invalid_records"]) == 4


def test_large_disagreements_block_agreement_gate():
    records = [record(i, i % 5) for i in range(30)]
    for item in records[:5]:
        item["reviews"][1]["ratings"]["A_correctness"] = 4 - item["reviews"][0]["ratings"]["A_correctness"]
    result = calibration_report(records, challenges=["question"])
    assert not result["agreement_gate_met"]


def test_all_ten_challenges_have_explicit_pending_anchor_inventory():
    template = pilot_template()
    assert len(template["challenges"]) == 10
    assert template["records"] == []
    assert all(c["anchor_status"] == "pending_independent_validation" for c in template["challenges"])


def test_cannot_lower_required_sample_size():
    with pytest.raises(ValueError):
        calibration_report([], min_attempts=1)


def test_publication_recomputes_all_ten_gates_and_rejects_tampering(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from app.core import config
    from app.services.interview.grading_calibration import REQUIRED_AUDITS, publication_allowed
    from app.services.interview.trusted_cases import VERSION, inventory_digest
    from app.services.interview.calibration import challenge_version_for
    records = []
    inventories = {}
    for challenge in pilot_template()["challenges"]:
        slug = challenge["slug"]
        inventories[slug] = {"challenge_version": challenge_version_for(slug), "evaluator_version": VERSION,
                             "inventory_digest": inventory_digest(slug), "evidence_ref": "audit/inventory/" + slug}
        for i in range(30):
            attempt = record(slug + str(i), i % 5)
            attempt["challenge_slug"] = slug
            attempt.update({key: inventories[slug][key] for key in
                            ("challenge_version", "evaluator_version", "inventory_digest")})
            records.append(attempt)
    audits = {name: {"completed": True, "evidence_refs": ["audit/" + name]} for name in REQUIRED_AUDITS}
    audits["inventories"] = inventories
    report = calibration_report(records, audit_evidence=audits)
    assert report["release_ready"]
    path = tmp_path / "readiness.json"
    path.write_text(json.dumps(report))
    settings = SimpleNamespace(grading_publish_reviewed_scores=True, grading_calibration_report_path=str(path))
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    assert publication_allowed()
    from app.services.interview import trusted_cases, calibration
    with monkeypatch.context() as changed:
        changed.setattr(trusted_cases, "VERSION", "new evaluator")
        assert not publication_allowed()
    with monkeypatch.context() as changed:
        changed.setattr(trusted_cases, "inventory_digest", lambda slug: "changed inventory")
        assert not publication_allowed()
    with monkeypatch.context() as changed:
        changed.setattr(calibration, "challenge_version_for", lambda slug: "new challenge")
        assert not publication_allowed()
    report["records"][0]["synthetic"] = True
    path.write_text(json.dumps(report))
    assert not publication_allowed()
    settings.grading_publish_reviewed_scores = False
    assert not publication_allowed()


def test_audit_booleans_without_references_never_release():
    from app.services.interview.grading_calibration import REQUIRED_AUDITS
    result = calibration_report([record(i, i % 5) for i in range(30)], challenges=["question"],
        audit_evidence={name: {"completed": True} for name in REQUIRED_AUDITS})
    assert result["agreement_gate_met"]
    assert not result["release_ready"]


def test_online_gate_recompute_skips_bootstrap_without_changing_gates(monkeypatch):
    from app.services.interview import grading_calibration as service
    records = [record(i, i % 5) for i in range(30)]
    offline = calibration_report(records, challenges=["question"])
    def forbidden_bootstrap(pairs):
        raise AssertionError("Online publication recompute must not bootstrap")
    monkeypatch.setattr(service, "kappa_interval", forbidden_bootstrap)
    online = calibration_report(records, challenges=["question"], include_intervals=False)
    assert online["agreement_gate_met"] == offline["agreement_gate_met"]
    assert online["release_ready"] == offline["release_ready"]
    metrics = online["challenges"][0]["dimensions"]["A_correctness"]
    assert metrics["interval_status"] == "offline_report_required"
    assert metrics["kappa_bootstrap_95_interval"] is None
