"""Run a direct smoke test against a sandbox executor instance."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from typing import Any


def _request(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    token: str = "",
    timeout_seconds: float = 10.0,
) -> tuple[int, dict[str, Any] | None]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a direct sandbox executor smoke test.")
    parser.add_argument("--url", default="http://127.0.0.1:8090")
    parser.add_argument("--token", default="")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    ready_status, ready_body = _request(
        "GET",
        f"{base_url}/ready",
        timeout_seconds=min(10.0, args.timeout_seconds),
    )
    if ready_status != 200:
        raise SystemExit(f"Sandbox executor readiness failed: {ready_status} {ready_body}")

    payload = {
        "code": "print('sandbox-executor-smoke-ok')\n",
        "entrypoint": "main.py",
        "challenge_config": {"inputs": {}, "files": {}},
    }
    run_status, run_body = _request(
        "POST",
        f"{base_url}/v1/sandbox/run",
        payload=payload,
        token=args.token,
        timeout_seconds=max(10.0, args.timeout_seconds),
    )
    if run_status != 200 or not isinstance(run_body, dict):
        raise SystemExit(f"Sandbox executor run failed: {run_status} {run_body}")
    if not bool(run_body.get("success")):
        raise SystemExit(f"Sandbox executor smoke returned failure: {run_body}")
    if "sandbox-executor-smoke-ok" not in str(run_body.get("output") or ""):
        raise SystemExit(f"Sandbox executor output mismatch: {run_body}")

    print(
        json.dumps(
            {
                "ready": ready_body,
                "run": {
                    "success": bool(run_body.get("success")),
                    "exit_code": int(run_body.get("exit_code", -1)),
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
