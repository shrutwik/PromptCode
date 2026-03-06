"""Run a deployment smoke test against a live PromptCode stack."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
import uuid
from typing import Any


def _request(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
) -> tuple[int, dict[str, Any] | list[Any] | None]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        payload_obj = json.loads(raw) if raw else None
        return exc.code, payload_obj


def _signup_or_login(base_url: str, email: str, password: str) -> str:
    username = f"smoke_{uuid.uuid4().hex[:10]}"
    signup_payload = {
        "email": email,
        "username": username,
        "first_name": "Deploy",
        "last_name": "Smoke",
        "password": password,
    }
    status, body = _request("POST", f"{base_url}/api/auth/signup", payload=signup_payload)
    if status == 201 and isinstance(body, dict):
        return str(body["access_token"])
    if status != 409:
        raise RuntimeError(f"Signup failed with status {status}: {body}")

    login_payload = {"email": email, "password": password}
    status, body = _request("POST", f"{base_url}/api/auth/login", payload=login_payload)
    if status != 200 or not isinstance(body, dict):
        raise RuntimeError(f"Login failed with status {status}: {body}")
    return str(body["access_token"])


def _pick_challenge(base_url: str, challenge_id: str | None) -> str:
    if challenge_id:
        return challenge_id
    status, body = _request("GET", f"{base_url}/api/challenges/")
    if status != 200 or not isinstance(body, list) or not body:
        raise RuntimeError(f"Could not load challenges: {status} {body}")
    return str(body[0]["id"])


def _poll_submission(
    base_url: str,
    submission_id: str,
    token: str,
    *,
    timeout_seconds: int,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_status: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        status, body = _request(
            "GET",
            f"{base_url}/api/submissions/{submission_id}/status",
            token=token,
        )
        if status != 200 or not isinstance(body, dict):
            raise RuntimeError(f"Status polling failed with status {status}: {body}")
        last_status = body
        if str(body.get("status")) in {"completed", "failed"}:
            return body
        time.sleep(poll_interval_seconds)
    raise RuntimeError(f"Submission did not reach a terminal state: {last_status}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a live deployment smoke test.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--challenge-id", default="")
    parser.add_argument("--email", default=f"smoke_{uuid.uuid4().hex[:12]}@example.com")
    parser.add_argument("--password", default="Password123!")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    parser.add_argument(
        "--code",
        default="def solve(data):\n    return {}\n",
        help="Python submission code to send during the smoke test.",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    status, body = _request("GET", f"{base_url}/ready")
    if status != 200:
        raise SystemExit(f"Readiness check failed: {status} {body}")

    token = _signup_or_login(base_url, args.email, args.password)
    challenge_id = _pick_challenge(base_url, args.challenge_id or None)

    submission_payload = {
        "challenge_id": challenge_id,
        "code": args.code,
        "entrypoint": "main.py",
    }
    status, body = _request(
        "POST",
        f"{base_url}/api/submissions/",
        payload=submission_payload,
        token=token,
    )
    if status != 201 or not isinstance(body, dict):
        raise SystemExit(f"Submission creation failed: {status} {body}")

    submission_id = str(body["id"])
    final_status = _poll_submission(
        base_url,
        submission_id,
        token,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
    )

    if str(final_status.get("status")) == "completed":
        report_status, report = _request(
            "GET",
            f"{base_url}/api/submissions/{submission_id}/report",
            token=token,
        )
        if report_status != 200:
            raise SystemExit(f"Completed submission report failed: {report_status} {report}")

    print(
        json.dumps(
            {
                "ready": True,
                "challenge_id": challenge_id,
                "submission_id": submission_id,
                "final_status": final_status,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
