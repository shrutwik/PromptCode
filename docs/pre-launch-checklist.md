# Pre-Launch Checklist

- [ ] Compose render verified clean (no 8000/5433/build:)
- [ ] Host firewall blocks 8000 and 5433 externally
- [ ] .env populated with no placeholders, DOMAIN set
- [ ] DNS resolves to host, Caddy obtains TLS cert
- [ ] Challenges seeded, seed script ran twice (idempotency verified)
- [ ] Smoke test ran with a real submission reaching terminal state
- [ ] Backup ran and rclone upload confirmed
- [ ] Restore rehearsal completed against a real backup
- [ ] Rollback rehearsal completed (bad deploy -> auto-rollback -> healthy)
- [ ] check-prod-health.sh cron running and producing output
- [ ] All 24 tests passing on the deploy SHA
