# Operations for the initial cohort

The global pending queue budget is `PROMPTCODE_GRADING_MAX_PENDING_JOBS=100` across interview grading (`queued`, `running`) and legacy evaluation (`queued`, `retry`, `running`). Admission is serialized with a PostgreSQL transaction advisory lock, held through enqueue/commit. Existing per-account caps remain. Admission returns 429 with a retry interval. Production requires PostgreSQL; SQLite cannot provide concurrent admission guarantees.

Persistent interview artifacts have a default 20 GiB budget and a 2 GiB free disk reserve (`PROMPTCODE_INTERVIEW_STORAGE_MAX_BYTES`, `PROMPTCODE_INTERVIEW_STORAGE_MIN_FREE_BYTES`). Workspace creation, uploads, and submission freezing share a filesystem lock and count retained source, starters, dependencies, and immutable snapshots. Capacity returns 507 before growth. API and grading workers must share the same artifact root and lock filesystem. Candidate execution uses separate bounded ephemeral storage.

Host bootstrap installs `scripts/cleanup-interview.sh` daily at 04:00; it runs source cleanup inside the backend container and skips Docker cleanup when a remote broker is configured. Host preflight requires that script and its scheduled job. Cleanup retains active/submitted sessions and every session with grading, review, or appeal history, including failed grading. It removes expired/failed unsubmitted workspaces and UUID orphan directories older than an hour. It refuses paths outside the owned root and skips links. Run stopped-container cleanup on the execution host; application processes must not have Docker access. Retained review source has no automatic deletion policy: when the budget is full, expand storage or archive complete source plus its database history after deciding the appeal retention window. Do not delete `.submitted` to regain capacity.

`scripts/backup-db.sh` now writes a database dump, source archive (immutable `.submitted`, active UUID workspaces, starters, and freeze markers), and SHA256 checksums with private file permissions. The archive excludes dependencies/caches and holds the shared storage lock to preserve active edits while copying. All three must upload successfully before the success timestamp advances or old backups are pruned. Set `BACKUP_ARTIFACT_ROOT` to the application host's actual artifact mount (defaults to `PROMPTCODE_INTERVIEW_HOST_WORKDIR`). Configure `RCLONE_REMOTE` to an off-host destination; use an encrypted rclone remote for stored candidate source and database contents. Schedule daily backups and health checks using the existing host setup scripts.

Restore all three matching files using `scripts/restore-db.sh <dump.sql.gz>` while application and workers are stopped, into an empty target database and the original artifact path. Restoration refuses existing nonempty artifact destinations and links; move any current artifact tree aside first. Run as root when the archive contains another user ID; the script preserves numeric application ownership so restored progress remains editable. The source path stored in grading jobs is absolute, so changing that mount requires an explicit database path migration. Checksums and archive entry paths are validated before source/database restoration. Legacy SQL-only backups warn that source cannot be recovered. `scripts/rehearse-restore.sh` verifies a disposable PostgreSQL database, frozen source, and active coding progress round trip with a local simulated remote; it does not prove access to a real off-host destination.

Authenticated `/metrics` exposes durable grading counts by status, oldest queued age, expired running leases, retained storage bytes, and free disk bytes. It exports no candidate source, errors, or IDs. Missing production tables or failed database queries return 503. `scripts/check-prod-health.sh` exits nonzero for grading failures, expired leases, queue age above five minutes, queue depth above the cap, a stale worker heartbeat (counted **per worker**, so one dead replica among healthy ones is visible), free disk below the reserve, backup age, and last-deploy status.

### Alert delivery

There is no alert manager in this stack. `scripts/notify-alert.sh` is the single
transport and is a no-op until configured, so a health check never fails merely
because alerting is absent. Configure **one** destination before launch
(`PROMPTCODE_ALERT_WEBHOOK_URL` or `PROMPTCODE_ALERT_COMMAND`); see `.env.example`.

| Caller | Alerts when |
| --- | --- |
| `scripts/check-prod-health.sh` | any health gate fails (reason plus the measured detail) |
| `scripts/backup-db.sh` | the backup aborts (including a partial upload) |
| deploy workflow | the pre-migration dump fails, so the deploy is refused |

Retry failed grading through the existing staff flow after investigating; a durable failed job keeps the alert active until resolved. Alert delivery itself is **unverified**: no destination has been configured in this repository.

`scripts/backup-db.sh --pre-migration` writes a local database dump plus checksum
before the deploy workflow starts the backend (migrations run on container start),
and deliberately does not require rclone. It is a restore point, not a replacement
for the daily off-host backup: the archive of immutable submissions and active
candidate work still comes from the scheduled full backup.

Local verification includes a 12-account simultaneous PostgreSQL admission test proving exactly three accepts at a cap of three, a PostgreSQL submit/cleanup race check preserving submitted status, cross-session storage contention tests, cleanup retention tests, durable metrics tests, backup upload-failure/checksum tests, an actual isolated PostgreSQL/source restore rehearsal, and the alert-transport contract tests. Deployment scheduling, off-host upload, and real alert delivery still require a configured host.
