from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path


FRONTEND_ROOT = Path(__file__).resolve().parents[2] / "frontend"


def _read(page: str) -> str:
    return (FRONTEND_ROOT / page).read_text()


class _FrontendPolicyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.inline_handlers: list[tuple[str, str]] = []
        self.javascript_hrefs: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name.lower().startswith("on"):
                self.inline_handlers.append((tag, name))
            if name.lower() == "href" and isinstance(value, str) and value.lower().startswith("javascript:"):
                self.javascript_hrefs.append((tag, value))


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


def test_challenge_page_defaults_to_ai_assistant_tab() -> None:
    source = _read("challenge.html")

    assert 'data-tab="chat" data-click-action="switchRightTab" data-action-args=\'["chat"]\'' in source
    assert 'class="right-tab active" data-tab="chat"' in source
    assert 'class="right-tab-panel active" id="panelChat"' in source


def test_playground_is_hidden_from_primary_navigation() -> None:
    source = "\n".join(
        _read(page)
        for page in (
            "index.html",
            "challenges.html",
            "challenge.html",
            "leaderboard.html",
            "profile.html",
            "submission.html",
        )
    )

    assert 'href="/playground.html"' not in source


def test_playground_page_redirects_to_challenges() -> None:
    source = _read("playground.html")

    assert '<script src="/static/playground-redirect.js"></script>' in source
    assert 'http-equiv="refresh" content="0; url=/challenges.html"' in source


def test_frontend_pages_avoid_inline_script_handlers_and_javascript_urls() -> None:
    inline_handlers: list[tuple[str, str]] = []
    javascript_hrefs: list[tuple[str, str]] = []

    for page in FRONTEND_ROOT.glob("*.html"):
        parser = _FrontendPolicyParser()
        parser.feed(page.read_text())
        inline_handlers.extend(parser.inline_handlers)
        javascript_hrefs.extend(parser.javascript_hrefs)

    assert inline_handlers == []
    assert javascript_hrefs == []
