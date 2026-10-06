"""Bounded, authenticated interview workload for disposable benchmark accounts.

Never calls AI, creates accounts, or deletes data. See docs/capacity-validation.md.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import random
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from benchmarks.audit_load import percentile


class WorkloadError(Exception):
    """A sanitized step failure; response bodies may contain secrets."""


def load_accounts(path: Path, namespace: str, required: int) -> list[dict]:
    if not re.fullmatch(r"[a-z0-9_]{3,32}", namespace):
        raise ValueError("namespace must contain 3-32 lowercase letters, digits or underscores")
    document = json.loads(path.read_text())
    if document.get("namespace") != namespace or document.get("disposable") is not True:
        raise ValueError("accounts must explicitly declare the requested disposable namespace")
    accounts = document.get("accounts", [])
    if len(accounts) < required:
        raise ValueError("not enough distinct disposable accounts for the largest stage")
    emails = set()
    for account in accounts:
        email = account.get("email", "")
        if not re.fullmatch(rf"benchmark_{re.escape(namespace)}_[0-9]+@example\.com", email):
            raise ValueError("only benchmark_<namespace>_<number>@example.com accounts are allowed")
        if email in emails or not isinstance(account.get("access_token"), str) or not account["access_token"]:
            raise ValueError("accounts need distinct emails and nonempty access tokens")
        emails.add(email)
    return accounts


class Measurements:
    def __init__(self, max_error_rate: float, max_throttle_rate: float):
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.steps = defaultdict(list)
        self.errors = Counter()
        self.flows = Counter()
        self.runs = []
        self.queue_wait = []
        self.job_elapsed = []
        self.max_error_rate = max_error_rate
        self.max_throttle_rate = max_throttle_rate
        self.requests = self.failures = self.throttles = 0

    def record(self, step: str, code: int, elapsed: float, throttled: bool):
        with self.lock:
            self.steps[step].append((code, elapsed))
            self.requests += 1
            self.throttles += int(throttled)
            self.failures += int(not 200 <= code < 300 and not throttled)
            if self.requests >= 20 and (
                self.failures / self.requests > self.max_error_rate
                or self.throttles / self.requests > self.max_throttle_rate
            ):
                self.stop.set()

    def summary(self):
        with self.lock:
            return {
                "requests": self.requests, "unexpected_errors": self.failures,
                "throttles": self.throttles, "stop_threshold_reached": self.stop.is_set(),
                "flows": dict(self.flows), "flow_failures": dict(self.errors),
                "steps": {step: {"statuses": dict(Counter(str(code) for code, _ in rows)),
                                  "latency_ms": distribution([elapsed for _, elapsed in rows]),
                                  "successful_latency_ms": distribution([elapsed for code, elapsed in rows if 200 <= code < 300])}
                          for step, rows in self.steps.items()},
                "advisory_execution_duration_ms": distribution(self.runs),
                "observed_queue_wait_ms": distribution(self.queue_wait),
                "observed_job_completion_ms": distribution(self.job_elapsed),
            }


def distribution(values):
    return {"samples": len(values), "p50": percentile(values, 50),
            "p95": percentile(values, 95), "p99": percentile(values, 99),
            "max": round(max(values), 2) if values else None}


class Client:
    def __init__(self, base_url, token, metrics, timeout, deadline):
        self.base_url = base_url
        self.headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
        self.metrics, self.timeout, self.deadline = metrics, timeout, deadline
        # Credentialed requests must never follow an off-host redirect.
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, step, method, path, payload=None):
        if self.metrics.stop.is_set() or time.monotonic() >= self.deadline:
            raise WorkloadError("stopped")
        headers = dict(self.headers)
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        started = time.perf_counter()
        code, body, throttled = 0, None, False
        try:
            with self.opener.open(request, timeout=min(self.timeout, max(0.1, self.deadline - time.monotonic()))) as response:
                code = response.status
                body = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            code = exc.code
            throttled = code == 429 or (code == 503 and bool(exc.headers.get("Retry-After")))
            exc.close()
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            code = 0
        self.metrics.record(step, code, (time.perf_counter() - started) * 1000, throttled)
        if not 200 <= code < 300 or body is None:
            raise WorkloadError(f"{step}: {'throttled' if throttled else 'http_' + str(code)}")
        return body


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def user_flow(account, args, metrics, deadline):
    client = Client(args.base_url, account["access_token"], metrics, args.request_timeout, deadline)
    sid = None
    try:
        identity = client.call("identity", "GET", "/api/auth/me")
        if identity.get("email") != account["email"]:
            raise WorkloadError("account_identity_mismatch")
        client.call("challenge", "GET", "/api/interview/challenges/" + args.challenge)
        session = client.call("start", "POST", "/api/interview/sessions", {"challenge_slug": args.challenge})
        sid = str(session["id"])
        client.headers["X-Session-Token"] = session["owner_token"]
        prefix = "/api/interview/sessions/" + sid
        files = client.call("files", "GET", prefix + "/files")
        source = next((row["path"] for row in files if row["path"].endswith((".py", ".ts", ".tsx"))
                       and "test" not in row["path"].lower() and not row.get("frozen", False)), None)
        if source is None:
            raise WorkloadError("no_editable_source")
        source_url = prefix + "/files/" + urllib.parse.quote(source, safe="/")
        content = client.call("read", "GET", source_url)
        # A real authenticated file write, preserving valid source and the starter bug.
        client.call("save", "PUT", source_url, {"content": content["content"] + "\n"})
        if not args.skip_execution:
            for retry in range(args.capacity_retries + 1):
                try:
                    run = client.call("advisory_run", "POST", prefix + "/tests", {"command_id": "run_tests"})
                    break
                except WorkloadError as exc:
                    if str(exc) != "advisory_run: throttled" or retry >= args.capacity_retries:
                        raise
                    if metrics.stop.wait(2 + random.random()):
                        raise WorkloadError("stopped")
            if run.get("error_code") or run.get("timed_out"):
                raise WorkloadError("advisory_execution_unavailable")
            with metrics.lock:
                metrics.runs.append(float(run.get("duration_ms", 0)))
        submit = client.call("submit", "POST", prefix + "/submit", {})
        submitted = time.monotonic()
        client.call("defend", "GET", prefix + "/defend")
        if submit.get("defend_questions"):
            client.call("defend_answer", "POST", prefix + "/defend", {
                "index": 0, "answer": "Benchmark attempt: preserve starter behavior and inspect boundary cases."})
        first_running = None
        while True:
            report = client.call("report", "GET", prefix + "/report")
            execution_status = (report.get("assessment") or {}).get("execution_status")
            if args.skip_execution:
                break
            if execution_status == "running" and first_running is None:
                first_running = time.monotonic()
                with metrics.lock:
                    metrics.queue_wait.append((first_running - submitted) * 1000)
            if execution_status in {"completed", "failed"}:
                if execution_status == "failed":
                    raise WorkloadError("grading_failed")
                with metrics.lock:
                    metrics.job_elapsed.append((time.monotonic() - submitted) * 1000)
                break
            if execution_status not in {"queued", "running"}:
                raise WorkloadError("missing_execution_status")
            if metrics.stop.wait(args.poll_interval):
                raise WorkloadError("stopped")
        client.call("dashboard", "GET", "/api/interview/dashboard")
        with metrics.lock:
            metrics.flows["completed"] += 1
    except WorkloadError as exc:
        with metrics.lock:
            metrics.flows["incomplete"] += 1
            metrics.errors[str(exc)] += 1
    except (KeyError, TypeError, StopIteration):
        with metrics.lock:
            metrics.flows["incomplete"] += 1
            metrics.errors["unexpected_response_shape"] += 1
    # Never delete users or data, including partially completed sessions.
    return sid


def host_sample(pids, disk_path):
    snapshot = {"elapsed": time.monotonic(), "load_average": list(os.getloadavg()),
                "disk_free_bytes": shutil.disk_usage(disk_path).free}
    if platform.system() == "Darwin":
        vm = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5, check=False)
        rows = dict(re.findall(r"^([^:]+):\s+(\d+)\.", vm.stdout, re.MULTILINE))
        page_size = re.search(r"page size of (\d+) bytes", vm.stdout)
        if page_size:
            snapshot["host_memory_active_wired_compressed_bytes"] = sum(
                int(rows.get(key, 0)) for key in ("Pages active", "Pages wired down", "Pages occupied by compressor")
            ) * int(page_size.group(1))
    elif Path("/proc/meminfo").exists():
        memory = dict(re.findall(r"^(\w+):\s+(\d+)", Path("/proc/meminfo").read_text(), re.MULTILINE))
        snapshot["host_memory_used_bytes"] = (int(memory["MemTotal"]) - int(memory["MemAvailable"])) * 1024
    host_cpu = subprocess.run(["ps", "-A", "-o", "%cpu="], capture_output=True, text=True, timeout=5, check=False)
    snapshot["host_process_cpu_percent_sum"] = sum(float(row) for row in host_cpu.stdout.splitlines() if row.strip())
    if pids:
        result = subprocess.run(["ps", "-p", ",".join(map(str, pids)), "-o", "%cpu=,rss="],
                                capture_output=True, text=True, timeout=5, check=False)
        rows = [line.split() for line in result.stdout.splitlines() if len(line.split()) == 2]
        snapshot["selected_process_cpu_percent"] = sum(float(row[0]) for row in rows)
        snapshot["selected_process_rss_bytes"] = sum(int(row[1]) * 1024 for row in rows)
    return snapshot


def run(args):
    accounts = load_accounts(args.accounts, args.namespace, max(args.stages))
    stages = []
    host_samples = []
    monitor_stop = threading.Event()
    def monitor():
        while not monitor_stop.is_set():
            try:
                host_samples.append(host_sample(args.host_pids, args.host_disk_path))
            except (OSError, ValueError, subprocess.TimeoutExpired):
                host_samples.append({"unavailable": True})
            monitor_stop.wait(1)
    thread = None
    if args.local_host_telemetry:
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
    try:
        for concurrency in args.stages:
            metrics = Measurements(args.max_error_rate, args.max_throttle_rate)
            started = time.monotonic()
            deadline = started + args.stage_timeout
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                sessions = list(pool.map(lambda account, metrics=metrics, deadline=deadline: user_flow(account, args, metrics, deadline),
                                         accounts[:concurrency]))
            summary = metrics.summary()
            summary.update(concurrency=concurrency, duration_seconds=round(time.monotonic() - started, 2),
                           session_ids=[sid for sid in sessions if sid])
            advisory = summary["steps"].get("advisory_run", {}).get("statuses", {})
            advisory_total = sum(advisory.values())
            advisory_shed = advisory.get("429", 0) + advisory.get("503", 0)
            summary["readiness_gates"] = {
                "unexpected_http_error_rate": summary["unexpected_errors"] / max(1, summary["requests"]),
                "unexpected_http_errors_absent": summary["unexpected_errors"] == 0,
                "advisory_shed_rate": advisory_shed / advisory_total if advisory_total else None,
                "advisory_shed_rate_at_most_25_percent": advisory_shed / advisory_total <= 0.25 if advisory_total else None,
                "latency_acceptance": "unassessed: no product latency target specified",
                "production_headroom": "unassessed: deployment resource acceptance is outside this workload report",
            }
            stages.append(summary)
            print(json.dumps({"concurrency": concurrency, "flows": summary["flows"],
                              "duration_seconds": summary["duration_seconds"], "throttles": summary["throttles"]}), flush=True)
            if summary["stop_threshold_reached"]:
                break
    finally:
        monitor_stop.set()
        if thread:
            thread.join(timeout=6)
    result = {"schema_version": 1, "namespace": args.namespace, "target": args.base_url,
              "challenge": args.challenge, "execution_exercised": not args.skip_execution,
              "paid_ai_exercised": False, "client_host": socket.gethostname(),
              "host_telemetry_scope": "load-client host; selected PIDs only" if thread else "not collected",
              "poll_interval_seconds": args.poll_interval,
              "queue_wait_scope": "first observed running state; polling upper bound, fast jobs may be missed",
              "requested_stages": args.stages, "stages": stages, "host_samples": host_samples,
              "bounds": {"stage_timeout_seconds": args.stage_timeout, "max_error_rate": args.max_error_rate,
                         "max_throttle_rate": args.max_throttle_rate, "advisory_capacity_retries": args.capacity_retries},
              "capacity_validated": False,
              "capacity_scope": "workflow measurement; latency acceptance and deployed resource headroom remain unverified",
              "workflow_completed": len(stages) == len(args.stages) and all(
                  stage["flows"].get("completed") == stage["concurrency"] for stage in stages)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--accounts", type=Path, required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--challenge", default="subscription-proration-boundary")
    parser.add_argument("--stages", nargs="+", type=int, default=[50, 100])
    parser.add_argument("--stage-timeout", type=float, default=600)
    parser.add_argument("--request-timeout", type=float, default=120)
    parser.add_argument("--poll-interval", type=float, default=2)
    parser.add_argument("--max-error-rate", type=float, default=0.10)
    parser.add_argument("--max-throttle-rate", type=float, default=0.25)
    parser.add_argument("--capacity-retries", type=int, default=10, help="bounded advisory-run retries after explicit overload")
    parser.add_argument("--skip-execution", action="store_true", help="route/DB-only measurement; excludes runs and worker completion")
    parser.add_argument("--local-host-telemetry", action="store_true")
    parser.add_argument("--host-pids", nargs="*", type=int, default=[])
    parser.add_argument("--host-disk-path", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    parsed = urllib.parse.urlsplit(args.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        parser.error("base URL must be HTTP(S), without credentials, query or fragment")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("remote targets require HTTPS")
    if args.local_host_telemetry and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("local telemetry is valid only for a loopback target")
    if (not args.stages or any(n < 1 or n > 100 for n in args.stages)
            or args.stages != sorted(set(args.stages))):
        parser.error("stages must be distinct increasing integers from 1 through 100")
    if (not 0.1 <= args.poll_interval <= 30 or not 1 <= args.request_timeout <= 300
            or not 1 <= args.stage_timeout <= 1800):
        parser.error("invalid timeout or polling bounds")
    if not all(0 <= value <= 1 for value in (args.max_error_rate, args.max_throttle_rate)):
        parser.error("error and throttle rates must be between zero and one")
    if not 0 <= args.capacity_retries <= 20:
        parser.error("capacity retries must be from zero through 20")
    if any(pid <= 0 for pid in args.host_pids):
        parser.error("PIDs must be positive")
    args.base_url = args.base_url.rstrip("/")
    return args


def main():
    result = run(parse_args())
    print(json.dumps({"workflow_completed": result["workflow_completed"], "stages": [
        {key: stage[key] for key in ("concurrency", "duration_seconds", "flows", "throttles")}
        for stage in result["stages"]]}))
    raise SystemExit(0 if result["workflow_completed"] else 1)


if __name__ == "__main__":
    main()
