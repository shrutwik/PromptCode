# Pre-Launch Checklist

- File this checklist as a GitHub issue using `.github/ISSUE_TEMPLATE/pre-launch-signoff.yml`.
- Do not treat this markdown file as the sign-off record.
- Do not mark rollback rehearsal complete until `Ops Rehearsals` shows a green rollback run in the Actions tab.

- [x] Compose render clean in CI — clean, run: 22829895405
- [x] Schema drift gate passes in CI — clean, run: 22829895405
- [ ] Localhost port check passed on the deploy host: `127.0.0.1:8000` refused and `127.0.0.1:5433` refused
- [ ] External port check passed from outside the host network: `nc -zv <PROD_HOST_IP> 8000` refused or timed out, and `nc -zv <PROD_HOST_IP> 5433` refused or timed out
- [ ] Host `.env` validated by `scripts/validate-host-env.sh`
- [ ] Host preflight validated by `scripts/validate-prod-host.sh`
- [ ] GHCR pull auth configured on the host, or `PROMPTCODE_GHCR_PUBLIC_IMAGES=true` intentionally set
- [ ] DNS resolves to host, Caddy obtains TLS cert
- [ ] HTTPS ingress verified: `https://DOMAIN/health` returns 200 and `http://DOMAIN/health` redirects to HTTPS
- [ ] Challenges seeded, seed script ran twice (idempotency verified)
- [ ] Smoke test ran with a real submission reaching terminal state
- [ ] Backup ran and rclone upload confirmed
- [ ] Restore rehearsal completed against a real backup
- [ ] Rollback rehearsal completed (bad deploy -> auto-rollback -> healthy)
- [ ] Rollback rehearsal migration boundary reviewed and accepted
- [ ] check-prod-health.sh cron running and producing output
- [x] 249+ tests passing on deploy SHA — 249 passed, SHA: a77e801f6299ed688564f0a9968e60f0cedcb5fc
