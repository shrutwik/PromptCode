# Security (beta)

Honest beta security notes — not a compliance claim.

## Isolation

- Candidate workspaces are per-session copies under the interview workspace root.
- `SOLUTION.md` and interviewer paths are blocked from file APIs and AI attachments.
- Docker `IsolatedRunner` mounts only the session workspace, drops caps, disables network, labels containers `promptcode.role=interview-runner`, and always removes the container in `finally`.

## Authentication

- Email/password with bcrypt hashes (never plaintext; never logged).
- JWT access (short) + refresh tokens; refresh revocation via `revoked_tokens`.
- Optional HttpOnly auth cookies when `PROMPTCODE_AUTH_COOKIE_ENABLED=true`.
- Password rules: ≥12 chars, upper/lower/digit/symbol, bcrypt 72-byte limit.

## Authorization / ownership

- Starting a challenge and all session workspace/AI/test/report/defend APIs require an authenticated user.
- `session.user_id` must match the auth user; cross-user access returns **404** (no existence leak).
- Dashboard returns only the caller’s sessions.

## Secrets

- All secrets from env (see `.env.example` placeholders). Never commit real `.env`.
- Production startup rejects placeholder JWT, default DB URL, missing DOMAIN/API key, CORS `*`.

## AI context

- Only explicitly attached files are sent; blocked paths rejected.
- Per-session AI rate limits + max request count (`PROMPTCODE_INTERVIEW_MAX_AI_REQUESTS_PER_SESSION`).
- Prompts/code are treated as sensitive in logs (conservative).

## Known beta risks

- Host Docker socket privilege if runner mode is docker on the API host.
- Bearer tokens in browser storage if cookies are not enabled.
- No email-based password reset yet.
- SQLite/local defaults are for development only.
- Rate limits are per-process/DB — not a distributed WAF.
