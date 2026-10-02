from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

FRONTEND_ROOT = Path(__file__).resolve().parents[2] / "frontend"


def _read(page: str) -> str:
    return (FRONTEND_ROOT / page).read_text()


class _FrontendPolicyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[tuple[str, dict[str, str | None]]] = []
        self.inline_handlers: list[tuple[str, str]] = []
        self.javascript_hrefs: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append((tag, dict(attrs)))
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
        source = _read(page)
        parser = _FrontendPolicyParser()
        parser.feed(source)
        for tag, attrs in parser.elements:
            href = urlsplit(attrs.get("href") or "")
            if tag == "link" and attrs.get("rel") == "stylesheet" and href.path.startswith("/static/") and not href.netloc:
                stylesheet = (FRONTEND_ROOT / href.path.removeprefix("/static/")).resolve()
                assert stylesheet.is_relative_to(FRONTEND_ROOT.resolve())
                source += stylesheet.read_text()
        assert "@media (max-width:" in source, f"{page} is missing a responsive breakpoint."


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

    parser = _FrontendPolicyParser()
    parser.feed(source)
    tabs = [attrs for tag, attrs in parser.elements if tag == "button" and attrs.get("data-tab") == "chat"]
    assert len(tabs) == 1
    tab = tabs[0]
    assert tab["class"] == "right-tab active"
    assert tab["data-click-action"] == "switchRightTab"
    assert tab["data-action-args"] == '["chat"]'
    assert tab["role"] == "tab" and tab["aria-selected"] == "true"
    assert tab["aria-controls"] == "panelChat"
    panels = [attrs for tag, attrs in parser.elements if tag == "div" and attrs.get("id") == "panelChat"]
    assert len(panels) == 1
    assert panels[0]["class"] == "right-tab-panel active"
    assert panels[0]["role"] == "tabpanel"
    assert panels[0]["aria-labelledby"] == tab["id"]


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
