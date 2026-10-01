#!/usr/bin/env python3
"""Lightweight verification for interview MVP services (no full ASGI boot)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.interview.registry import (  # noqa: E402
    candidate_readme,
    get_challenge,
    interviewer_file_roles,
    is_blocked_path,
    list_challenges,
)
from app.services.interview.runner import (  # noqa: E402
    LocalDevelopmentRunner,
    resolve_command,
    resolve_command_id,
)
from app.services.interview.rubric import parse_defend_questions, score_session  # noqa: E402
from app.services.interview.session_analysis import analyze_prompt_quality  # noqa: E402
from app.services.interview.workspace import (  # noqa: E402
    assert_session_isolation,
    create_workspace,
    list_files,
    read_file,
    starter_snapshot_path,
)


def main() -> int:
    items = list_challenges()
    assert len(items) == 10, len(items)
    slug = items[0]["slug"]
    assert get_challenge(slug)
    readme = candidate_readme(slug)
    assert "SOLUTION" not in readme
    assert is_blocked_path("SOLUTION.md")
    assert not is_blocked_path("README.md")
    roles = interviewer_file_roles(slug)
    assert "relevant_files" in roles

    resolve_command("npm test")
    resolve_command("pytest -q")
    resolve_command_id("run_tests", "npm test")
    try:
        resolve_command("rm -rf /")
        raise AssertionError("dangerous command allowed")
    except ValueError:
        pass
    assert isinstance(LocalDevelopmentRunner(), LocalDevelopmentRunner)

    ws = create_workspace("verify-smoke", slug)
    assert_session_isolation("verify-smoke", slug)
    assert starter_snapshot_path("verify-smoke").exists()
    files = list_files(ws)
    assert files
    assert not any("SOLUTION" in f["path"].upper() for f in files)
    try:
        read_file(ws, "SOLUTION.md")
        raise AssertionError("SOLUTION readable")
    except PermissionError:
        pass

    pq = analyze_prompt_quality(
        "tests/foo.test.ts fails: expected 1 observed 0 in src/bar.ts — explain why without rewrite"
    )
    assert pq["score"] > 40

    scored = score_session(
        events=[
            {"event_type": "session_started"},
            {"event_type": "file_viewed", "payload": {"path": "README.md"}},
            {"event_type": "test_run"},
            {"event_type": "test_result", "payload": {"ok": False}},
            {
                "event_type": "ai_prompt",
                "payload": {"message": "why does test X fail on assert Y in src/foo.ts?"},
            },
        ],
        test_summary={"ok": False},
        ai_prompts=["why does test X fail on assert Y in src/foo.ts?"],
        challenge_slug=slug,
    )
    assert "total_score" in scored
    assert all("evidence" in v for v in scored["rubric"].values())
    defend = parse_defend_questions(slug)
    assert len(defend) == 4
    print(
        "OK registry=",
        len(items),
        "workspace_files=",
        len(files),
        "score=",
        scored["total_score"],
        "prompt_q=",
        pq["score"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
