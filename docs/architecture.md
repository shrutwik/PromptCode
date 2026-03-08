# Architecture

## Current production topology

PromptCode currently deploys as a single-host Docker Compose stack:

- `caddy` terminates TLS and reverse proxies to `backend`
- `backend` serves the API and frontend assets
- `worker` and `worker-b` process queued evaluations
- `sandbox-executor` owns Docker access for nested sandbox runs
- `db` is the only persistent data store in the stack

## Single-host limitations

This deployment model is intentionally simple and has hard limits:

- The stack assumes one Docker host at `/opt/promptcode`; there is no multi-host scheduling or automatic failover.
- Rolling back the app image does not automatically roll back schema changes or restore data.
- Queue capacity, worker heartbeats, backups, and metrics all depend on that single host staying healthy.
- `sandbox-executor` depends on local Docker socket access, so it is tightly coupled to host runtime behavior.
- The current observability path is host-local cron plus logs, not centralized monitoring.

Treat this as a careful single-host launch path, not a horizontally scalable production platform.
