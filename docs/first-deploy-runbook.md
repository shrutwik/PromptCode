# First Deploy Runbook

## Before first deploy

1. Bootstrap the host with `scripts/bootstrap-prod-host.sh`.
   - If `ufw` is intentionally inactive, rerun with `PROMPTCODE_ALLOW_EXTERNAL_FIREWALL=1`
     only after confirming your cloud firewall/security group exposes `80/443` and blocks backend/db ports.
2. Edit `/opt/promptcode/.env` and set real values for:
   - `DOMAIN`
   - `PROMPTCODE_DB_PASSWORD`
   - `PROMPTCODE_JWT_SECRET`
   - `PROMPTCODE_SANDBOX_EXECUTOR_TOKEN`
   - `PROMPTCODE_OPENAI_API_KEY`
   - `PROMPTCODE_METRICS_TOKEN`
   - `RCLONE_REMOTE`
   - Either `GHCR_USERNAME` + `GHCR_TOKEN`, or `PROMPTCODE_GHCR_PUBLIC_IMAGES=true`
3. Validate the host env and configure GHCR pull auth:
   - `bash /opt/promptcode/scripts/validate-host-env.sh`
   - `bash /opt/promptcode/scripts/setup-ghcr-login.sh`
4. Point DNS for `DOMAIN` at the production host before expecting Caddy TLS issuance.

## First deploy

1. Push to `main` and let GitHub Actions deploy the current SHA.
2. The deploy workflow seeds challenge data before the post-deploy smoke test runs.
3. If you need to re-seed manually after adding or updating challenge content:

```bash
bash /opt/promptcode/scripts/seed-prod-data.sh
```

## Ongoing ops checks

1. `bootstrap-prod-host.sh` installs `check-prod-health.sh` every 5 minutes.
2. That check depends on a working `/metrics` scrape, current worker heartbeats, queue visibility, a recent successful backup timestamp, and a healthy last deploy status file.
3. Review `/opt/promptcode/backups/health-check.log` after bootstrap to confirm the cron is green.

## Rollback

1. If the failed deploy did not run a schema migration:

```bash
cd /opt/promptcode
IMAGE_TAG="$(cat /opt/promptcode/.previous-image-tag)" docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-build
```

2. If the failed deploy did run a schema migration, downgrade first:

```bash
cd /opt/promptcode
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python -m alembic downgrade -1
IMAGE_TAG="$(cat /opt/promptcode/.previous-image-tag)" docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-build
```

The old image is not safe to trust until the database schema matches it again.
Automatic `alembic downgrade -1` is intentionally not done by the repo because a failed rollout
does not prove that schema changed or that the latest downgrade is safe without operator review.

> WARNING: Image rollback restores the previous container image only. It does not revert database
> schema automatically. The rollback rehearsal now explicitly proves that a schema probe remains
> applied after the old image is restored, so the operator must decide whether `alembic downgrade -1`
> is required before trusting the rolled-back image.

## Backups and restore rehearsal

1. `scripts/backup-db.sh` requires a working `rclone` setup and a non-empty `RCLONE_REMOTE`.
2. Verify the nightly backup cron is installed for the deploy user.
3. Rehearse a restore before launch:

```bash
bash /opt/promptcode/scripts/restore-db.sh promptcode-YYYYMMDDTHHMMSSZ.sql.gz
```

Launch is blocked until a restore rehearsal succeeds end to end.

## What This Repo Cannot Automate

1. DNS configuration and public TLS issuance.
   Responsible: platform or infrastructure owner.
   When: before the first production cutover, so `DOMAIN` resolves to the host and Caddy can obtain certificates.
2. Initial `/opt/promptcode/.env` population, including `DOMAIN`, DB password, JWT secret, sandbox token, OpenAI key, metrics token, and backup remote.
   Responsible: deploy operator with secret-management access.
   When: before any production deploy or rollback attempt.
3. GHCR authentication on the host for restarts and rollbacks, unless both GHCR packages are intentionally public.
   Responsible: deploy operator or repo admin.
   When: before the first deploy and whenever the stored PAT rotates.
4. Restore rehearsal sign-off.
   Responsible: operator on call plus whoever owns the production database.
   When: before launch and after any meaningful backup/restore path change.
5. Cloud-provider or host-firewall rules that block ports `8000` and `5433` externally.
   Responsible: infrastructure owner.
   When: before the first public deploy; the compose fix removes listeners from the stack, but perimeter firewall policy is still external to this repo.
