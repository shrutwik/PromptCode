from fastapi.testclient import TestClient
from test_interview_multidevice import _build_test_app, _cleanup, _signup


def test_bootstrap_matches_existing_reads_without_starting_timer_and_rejects_other_owner(tmp_path, monkeypatch):
    app, engine = _build_test_app(tmp_path, monkeypatch)
    try:
        with TestClient(app) as client:
            owner = _signup(client, email="bootstrap-owner@example.com", username="bootstrap_owner")
            other = _signup(client, email="bootstrap-other@example.com", username="bootstrap_other")
            headers = {"Authorization": f"Bearer {owner['access_token']}"}
            slug = client.get("/api/interview/challenges").json()[0]["slug"]
            started = client.post("/api/interview/sessions", headers=headers, json={"challenge_slug": slug})
            assert started.status_code == 200, started.text
            sid = started.json()["id"]
            base = f"/api/interview/sessions/{sid}"
            before = client.get(base, headers=headers).json()
            expected_files = client.get(base + "/files", headers=headers).json()
            expected_readme = client.get(base + "/files/README.md", headers=headers).json()
            level_response = client.get(base + "/level", headers=headers)
            response = client.get(base + "/bootstrap", headers=headers)
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["session"] == before
            assert data["session"]["timer_running"] is False
            assert data["files"] == expected_files
            assert data["readme"] == expected_readme
            assert data["level"] == (level_response.json() if level_response.status_code == 200 else None)
            assert client.get(base + "/bootstrap", headers={"Authorization": f"Bearer {other['access_token']}"}).status_code == 404
            # TestClient retains auth cookies: remove them for the anonymous check.
            client.cookies.clear()
            assert client.get(base + "/bootstrap").status_code == 401
    finally:
        _cleanup(app, engine)
