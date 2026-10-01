# Beta operations

## Day-2 checklist

1. `GET /health` and `GET /health/ready`
2. `alembic current` / `alembic upgrade head`
3. Confirm runner mode (`PROMPTCODE_RUNNER`) and images present for docker
4. Confirm AI key configured (site stays up if AI fails; sessions degrade gracefully)
5. Run cleanup periodically: `python backend/scripts/cleanup_interview_sessions.py`
6. Inspect protected diagnostics: `GET /api/interview/internal/diagnostics` with `X-PromptCode-Internal-Token`

## Session lifecycle

States: `created` / `active` / `submitted` / `expired` / `failed`.

- TTL: `PROMPTCODE_SESSION_TTL_HOURS` (default 24). Expired sessions cannot edit/run tests/AI.
- Submitted code is immutable; double-submit returns the existing report.
- Multiple attempts per challenge are allowed (`attempt_number`); completed attempts are not overwritten.

## Retention (policy intent)

| Asset | Retention |
|-------|-----------|
| Temp Docker containers | Seconds–minutes; removed after each run + cleanup sweeper |
| Expired/failed workspaces | Removed by cleanup; **DB history kept** |
| Submitted reports/events/AI messages | Retained for product learning unless deletion requested |
| Source `challenges/` | Never deleted by cleanup |
| Access logs / metrics | Operational; no candidate code dumps |

## On-call failure modes

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| ready 503 database | bad `DATABASE_URL` / network | fix DB; check SSL flags |
| tests “runner busy” | `MAX_RUNNERS` saturated | retry; raise limit carefully |
| tests image missing | images not built | build interview Dockerfiles |
| AI 429/503 | rate/provider | wait; check key; session still usable |
| 410 on edits | TTL expired | start new attempt; history remains if submitted |

## Smoke

```bash
# with venv + migrated DB
python backend/scripts/beta_smoke.py
```

Docker E2E may be skipped/unavailable — smoke still validates auth ownership and submit/report.

## Cleanup schedule

Schedule on the beta host (cron or systemd timer), e.g. hourly:

```bash
0 * * * * cd /opt/promptcode && .venv/bin/python backend/scripts/cleanup_interview_sessions.py >> /var/log/promptcode-cleanup.log 2>&1
```

Documented in `docs/release-checklist.md` and `docs/deployment.md`.

## Alert thresholds (manual — not PagerDuty)

| Signal | Watch when | Action |
|--------|------------|--------|
| 5xx rate | >2% of requests / 15m | Check logs + `/internal/incidents` |
| Runner/docker tags | >5% of sessions | Images, `MAX_RUNNERS`, disk |
| AI infra tags | sustained spike | Provider key/quota; sessions still usable |
| Cleanup lag | workspaces growing | Run cleanup; check cron |
| DB ready failures | any sustained | Restore from backup / managed console |

## Invites & beta users

```bash
python backend/scripts/create_invite.py --cohort beta --max-uses 1
python backend/scripts/beta_users.py list
python backend/scripts/beta_users.py disable <user_id>
python backend/scripts/review_session.py <session_id>
```

Internal APIs: `/api/interview/internal/*` with `X-PromptCode-Internal-Token`.
