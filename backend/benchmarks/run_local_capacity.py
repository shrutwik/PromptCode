"""Create a disposable local Postgres/backend/broker/two-worker capacity rehearsal.

No existing environment files or database URLs are consumed. Docker is required.
The measured topology shares one developer computer and is not a production claim.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

# Settings points at an absolute repository .env. Disable that source before
# importing the application, so unused credentials cannot enter this rehearsal.
ISOLATED_CONFIG = "from app.core.config import Settings; Settings.model_config['env_file'] = None; "


def isolated_module(module, *args):
    bootstrap = ISOLATED_CONFIG + "import runpy, sys; sys.argv = sys.argv[1:]; runpy.run_module(sys.argv[0], run_name='__main__')"
    return [sys.executable, "-c", bootstrap, module, *args]


def command(argv, *, env=None, timeout=120):
    result = subprocess.run(argv, cwd=BACKEND, env=env, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"{Path(argv[0]).name} failed; see local rehearsal logs")
    return result.stdout.strip()


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_ready(url, *, token=None, process=None):
    for _ in range(60):
        if process is not None and process.poll() is not None:
            raise RuntimeError("local service exited before readiness; see rehearsal logs")
        try:
            request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token} if token else {})
            with urllib.request.urlopen(request, timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    raise RuntimeError("local service did not become ready")


SEED = ISOLATED_CONFIG + '''
import asyncio, json, os, secrets, uuid
from app.db.session import async_session_factory, engine
from app.models.user import User
from app.core.security import hash_password, create_access_token
async def seed():
    accounts=[]
    password_hash=hash_password(secrets.token_urlsafe(32))
    async with async_session_factory() as db:
        for i in range(100):
            uid=uuid.uuid4()
            email=f"benchmark_{os.environ['BENCHMARK_NAMESPACE']}_{i}@example.com"
            db.add(User(id=uid,email=email,username=f"benchmark_{i}_{uid.hex[:8]}",
                        password_hash=password_hash,first_name="Benchmark",last_name="Disposable"))
            accounts.append({"email":email,"access_token":create_access_token(uid,os.environ['PROMPTCODE_JWT_SECRET'])})
        await db.commit()
    fd=os.open(os.environ['BENCHMARK_ACCOUNTS'],os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as output:
        json.dump({"namespace":os.environ['BENCHMARK_NAMESPACE'],"disposable":True,"accounts":accounts},output)
    await engine.dispose()
asyncio.run(seed())
'''

JOB_METRICS = ISOLATED_CONFIG + '''
import asyncio,json,os
from sqlalchemy import select
from app.db.session import async_session_factory,engine
from app.models.interview_grading import InterviewGradingJob
from benchmarks.interview_load import distribution
async def collect():
    report=json.load(open(os.environ['BENCHMARK_REPORT']))
    async with async_session_factory() as db:
        for stage in report['stages']:
            from uuid import UUID
            ids=[UUID(sid) for sid in stage['session_ids']]
            jobs=list((await db.execute(select(InterviewGradingJob).where(InterviewGradingJob.session_id.in_(ids)))).scalars()) if ids else []
            waits=[(job.started_at-job.created_at).total_seconds()*1000 for job in jobs if job.started_at]
            durations=[(job.finished_at-job.started_at).total_seconds()*1000 for job in jobs if job.started_at and job.finished_at]
            from collections import Counter
            stage['durable_jobs']={'statuses':dict(Counter(job.status for job in jobs)),
                                  'queue_wait_ms':distribution(waits),'execution_duration_ms':distribution(durations),
                                  'retry_attempts':sum(max(0,job.attempts-1) for job in jobs),
                                  'timing_scope':'latest claim per job; retries include backoff in queue wait'}
    json.dump(report,open(os.environ['BENCHMARK_REPORT'],'w'),indent=2)
    await engine.dispose()
asyncio.run(collect())
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stages", nargs="+", type=int, default=[50, 100])
    parser.add_argument("--skip-execution", action="store_true")
    parser.add_argument("--max-throttle-rate", type=float, default=0.25)
    parser.add_argument("--capacity-retries", type=int, default=10)
    parser.add_argument("--stage-timeout", type=int, default=600)
    args = parser.parse_args()
    if args.stages != sorted(set(args.stages)) or any(n < 1 or n > 100 for n in args.stages):
        parser.error("stages must increase and remain between 1 and 100")
    if not 1 <= args.stage_timeout <= 1800:
        parser.error("stage timeout must remain between 1 and 1800 seconds")
    if not 0 <= args.max_throttle_rate <= 1 or not 0 <= args.capacity_retries <= 20:
        parser.error("throttle rate must be 0-1 and capacity retries 0-20")
    args.output = args.output.resolve()
    namespace = "local_" + secrets.token_hex(5)
    container = "promptcode-capacity-" + secrets.token_hex(5)
    processes, handles = [], []
    with tempfile.TemporaryDirectory(prefix="promptcode-capacity-") as tmp:
        root = Path(tmp)
        (root / "workspaces").mkdir()
        (root / "broker").mkdir()
        safe_env = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "TMPDIR", "LANG", "DOCKER_HOST", "DOCKER_CONTEXT"}}
        # SDK uses the active macOS Docker socket; no existing app credentials.
        docker_host = safe_env.get("DOCKER_HOST")
        if not docker_host:
            context = json.loads(command(["docker", "context", "inspect"], env=safe_env))[0]
            docker_host = context["Endpoints"]["docker"]["Host"]
        broker_token = secrets.token_hex(32)
        db_password = secrets.token_hex(24)
        backend_port, broker_port = free_port(), free_port()
        common = {**safe_env, "PROMPTCODE_DEBUG": "true", "PROMPTCODE_RUNNER": "docker",
                  "PROMPTCODE_AI_KILL_SWITCH": "true", "PROMPTCODE_OPENAI_API_KEY": "",
                  "PROMPTCODE_AI_API_KEY": "", "DEEPSEEK_API_KEY": "",
                  "PROMPTCODE_JWT_SECRET": secrets.token_hex(32),
                  "PROMPTCODE_GRADING_SIGNING_KEY": secrets.token_hex(32),
                  "PROMPTCODE_EXECUTION_BROKER_URL": f"http://127.0.0.1:{broker_port}",
                  "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN": broker_token,
                  "PROMPTCODE_INTERVIEW_WORKSPACE_ROOT": str(root / "workspaces"),
                  "PROMPTCODE_INTERVIEW_INTERNAL_TOKEN": secrets.token_hex(32),
                  "PROMPTCODE_DATABASE_ECHO": "false", "PROMPTCODE_SANDBOX_EXECUTOR_URL": "",
                  "PYTHONPATH": str(BACKEND),
                  "BENCHMARK_NAMESPACE": namespace, "BENCHMARK_ACCOUNTS": str(root / "accounts.json"),
                  "BENCHMARK_REPORT": str(args.output)}
        def start(argv, env, label):
            handle = (root / (label + ".log")).open("w")
            handles.append(handle)
            process = subprocess.Popen(argv, cwd=BACKEND, env=env, stdout=handle, stderr=handle)
            processes.append(process)
            return process
        try:
            command(["docker", "run", "--detach", "--name", container, "--label", "promptcode.capacity.disposable=true",
                     "--publish", "127.0.0.1::5432", "--tmpfs", "/var/lib/postgresql/data:rw,size=1g",
                     "--env", "POSTGRES_USER=benchmark", "--env", f"POSTGRES_PASSWORD={db_password}",
                     "--env", "POSTGRES_DB=benchmark", "postgres:16.11-alpine3.23"], env=safe_env)
            db_port = command(["docker", "port", container, "5432/tcp"], env=safe_env).rsplit(":", 1)[1]
            common["PROMPTCODE_DATABASE_URL"] = f"postgresql+asyncpg://benchmark:{db_password}@127.0.0.1:{db_port}/benchmark"
            for _ in range(60):
                result = subprocess.run(["docker", "exec", container, "pg_isready", "-U", "benchmark"],
                                        env=safe_env, capture_output=True, check=False)
                if result.returncode == 0:
                    break
                time.sleep(0.5)
            migration = subprocess.run(isolated_module("alembic", "upgrade", "head"), cwd=BACKEND,
                                       env=common, capture_output=True, text=True, timeout=120, check=False)
            if migration.returncode:
                (root / "migration.log").write_text(migration.stdout + migration.stderr)
                raise RuntimeError("disposable database migrations failed")
            command([sys.executable, "-c", SEED], env=common)
            if not args.skip_execution:
                broker_env = {**safe_env, "DOCKER_HOST": docker_host,
                              "PROMPTCODE_DEBUG": "true", "PROMPTCODE_EXECUTION_BROKER_MODE": "true",
                              "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN": broker_token,
                              "PROMPTCODE_INTERVIEW_WORKSPACE_ROOT": str(root / "broker"),
                              "PROMPTCODE_SANDBOX_HOST_WORKDIR": str(root / "broker"),
                              "PROMPTCODE_BROKER_PYTHON_IMAGE": "promptcode-runner-python:latest",
                              "PROMPTCODE_BROKER_NODE_IMAGE": "promptcode-runner-node:latest",
                              "PYTHONPATH": str(BACKEND)}
                broker = start(isolated_module("uvicorn", "app.execution_broker:app", "--host", "127.0.0.1",
                                "--port", str(broker_port)), broker_env, "broker")
                wait_ready(f"http://127.0.0.1:{broker_port}/ready", token=broker_token, process=broker)
                for i in range(2):
                    start(isolated_module("scripts.run_queue_worker"),
                          {**common, "PROMPTCODE_WORKER_ID": f"{namespace}-worker-{i}"}, f"worker-{i}")
            backend = start(isolated_module("uvicorn", "app.main:create_app", "--factory", "--host", "127.0.0.1",
                             "--port", str(backend_port)), common, "backend")
            wait_ready(f"http://127.0.0.1:{backend_port}/health", process=backend)
            print("Disposable local rehearsal ready; starting bounded workload.", flush=True)
            workload_args = [sys.executable, "-m", "benchmarks.interview_load", "--base-url", f"http://127.0.0.1:{backend_port}",
                             "--accounts", str(root / "accounts.json"), "--namespace", namespace,
                             "--output", str(args.output), "--stages", *map(str, args.stages),
                             "--stage-timeout", str(args.stage_timeout),
                             "--max-throttle-rate", str(args.max_throttle_rate),
                             "--capacity-retries", str(args.capacity_retries), "--local-host-telemetry",
                             "--host-disk-path", str(root), "--host-pids", *[str(p.pid) for p in processes]]
            if args.skip_execution:
                workload_args.append("--skip-execution")
            result = subprocess.run(workload_args, cwd=BACKEND, env=common,
                                    timeout=len(args.stages) * (args.stage_timeout + 30) + 60, check=False)
            if not args.output.exists():
                raise RuntimeError("workload did not write its measurement report")
            command([sys.executable, "-c", JOB_METRICS], env=common)
            report = json.loads(args.output.read_text())
            info = json.loads(command(["docker", "info", "--format", "{{json .}}"], env=safe_env))
            report["topology"] = {"scope": "disposable local developer rehearsal", "os": platform.platform(),
                                  "client_and_services_share_host": True, "backend_processes": 1,
                                  "worker_processes": 0 if args.skip_execution else 2,
                                  "broker_processes": 0 if args.skip_execution else 1,
                                  "docker_cpus": info.get("NCPU"), "docker_memory_bytes": info.get("MemTotal"),
                                  "database": "Postgres 16.11, tmpfs, no existing volumes", "runner_limit": 4,
                                  "migrations_applied": True, "paid_ai_disabled": True,
                                  "settings_scope": "generated environment only; repository .env disabled",
                                  "database_pool": {"size": 20, "max_overflow": 10, "wait_timeout_seconds": 15},
                                  "image_pinning": "local development tags"}
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            if result.returncode:
                logs_dir = args.output.parent / (args.output.stem + "-logs")
                logs_dir.mkdir(parents=True, exist_ok=True)
                for path in root.glob("*.log"):
                    shutil.copyfile(path, logs_dir / path.name)
            print("Report:", args.output, flush=True)
            raise SystemExit(result.returncode)
        except Exception:
            # Copy logs only on failure for debugging; do not copy account tokens or environment.
            logs_dir = args.output.parent / (args.output.stem + "-logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            for path in root.glob("*.log"):
                shutil.copyfile(path, logs_dir / path.name)
            print("Service failure logs:", logs_dir, file=sys.stderr)
            raise
        finally:
            for process in reversed(processes):
                process.terminate()
            for process in reversed(processes):
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            for handle in handles:
                handle.close()
            # Only reap runners whose bind source belongs to this temporary broker.
            # Other agents' or developers' containers are never removed.
            try:
                ids = command(["docker", "ps", "--all", "--quiet", "--filter", "label=promptcode.role=interview-runner"], env=safe_env).split()
                if ids:
                    runners = json.loads(command(["docker", "inspect", *ids], env=safe_env))
                    owned = [runner["Id"] for runner in runners if any(
                        Path(mount.get("Source", "")).resolve().is_relative_to((root / "broker").resolve())
                        for mount in runner.get("Mounts", []) if mount.get("Source"))]
                    if owned:
                        command(["docker", "rm", "--force", *owned], env=safe_env, timeout=30)
            except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired):
                print("Runner cleanup inspection unavailable; Docker expiry labels remain in place.", file=sys.stderr)
            subprocess.run(["docker", "rm", "--force", container], env=safe_env, capture_output=True, timeout=30, check=False)


if __name__ == "__main__":
    main()
