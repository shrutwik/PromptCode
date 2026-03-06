from __future__ import annotations

from pathlib import Path


FRONTEND_ROOT = Path(__file__).resolve().parents[2] / "frontend"


def _read(page: str) -> str:
    return (FRONTEND_ROOT / page).read_text()


def test_core_frontend_pages_have_mobile_breakpoints() -> None:
    for page in (
        "index.html",
        "challenges.html",
        "challenge.html",
        "login.html",
        "signup.html",
        "leaderboard.html",
        "profile.html",
        "submission.html",
        "playground.html",
    ):
        assert "@media (max-width:" in _read(page), f"{page} is missing a responsive breakpoint."


def test_frontend_copy_avoids_stale_hardcoded_badges() -> None:
    source = "\n".join(
        _read(page)
        for page in (
            "index.html",
            "challenges.html",
            "challenge.html",
            "signup.html",
        )
    )

    assert "847 engineers enrolled" not in source
    assert "800+ engineers" not in source
    assert "v0.4.1" not in source
