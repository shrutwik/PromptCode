"""Frontend HTML serving must stay inside the frontend directory."""

from pathlib import Path

from app.main import resolve_frontend_html


def test_resolve_frontend_html_allows_known_pages():
    page = resolve_frontend_html("login")
    assert page is not None
    assert page.name == "login.html"


def test_resolve_frontend_html_blocks_traversal(tmp_path, monkeypatch):
    from app import main as main_module

    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "login.html").write_text("ok", encoding="utf-8")
    secret = tmp_path / "secret.html"
    secret.write_text("secret", encoding="utf-8")
    monkeypatch.setattr(main_module, "FRONTEND_DIR", frontend)

    assert resolve_frontend_html("login") == (frontend / "login.html").resolve()
    assert resolve_frontend_html("../secret") is None
    assert resolve_frontend_html("..") is None
    assert resolve_frontend_html("..\\secret") is None
    assert resolve_frontend_html("login/../../secret") is None
    assert secret.read_text(encoding="utf-8") == "secret"
    assert not Path(str(secret)).samefile(frontend / "login.html")
