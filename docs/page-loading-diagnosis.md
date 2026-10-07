# Page loading diagnosis — 2026-10-07

## Findings

The frontend is plain HTML/CSS/JavaScript on Vercel. `/api/*` is proxied to
Modal FastAPI, with SQLAlchemy database access and separate grading workers.
Navigation links reload the document. Page controllers render data only after
API responses; workspace startup also waited for Monaco download/initialization.

Read-only production measurements (curl, sequential requests, HTTP 200):

| Request | Time to first byte | Total |
| --- | ---: | ---: |
| Direct catalogue, first probe | 11.274 s | 11.275 s |
| Catalogue through Vercel | 1.873 s | 1.928 s |
| Direct catalogue, repeat | 1.769 s | 1.769 s |
| Static dashboard HTML | 0.187 s | 0.250 s |
| Direct health, later first probe | 6.869 s | 6.869 s |
| Direct catalogue immediately afterward | 0.618 s | 0.720 s |
| Direct health immediately afterward | 0.205 s | 0.205 s |

The slow database-free health request followed by a fast repeat strongly suggests
container startup/admission or hosting variability. The API definition had no
minimum warm container. These samples do not independently prove cold starts or
measure production percentiles. No authenticated account, private session or AI
workload was accessed. Earlier authenticated measurements are retained in
`performance-final-results.md`; no new authenticated production speedup is claimed.

A warm catalogue still waited longer than warm health. Its route performs an
atomic rate-counter write/commit and an analytics write/commit before returning
already-cached registry metadata. Authenticated routes add account reads and
session/review queries. Database round trips are a likely remaining contributor,
but connection acquisition, query and commit timing must be measured before
changing authentication, rate limits or deployment regions.

## Exactly four completed changes

1. **Idle API startup:** `backend/modal_app.py` now keeps one HTTP container warm
   with an explicit 0.125 CPU request and 512 MiB memory request, and retains excess containers for up to 300 seconds. Follows the existing HTTP
   function configuration; grading concurrency is unchanged. Deployment-contract
   test passed. Warm idle capacity increases hosting usage after deployment.
2. **Editor/data waterfall:** `frontend/interview-session.html` loads API helpers
   and the new `js/pages/interview-session-bootstrap.js` before Monaco. The existing
   controller consumes the concurrent metadata requests without repeating them.
   Follows its existing Promise.all pattern. Early failures are handled while
   waiting for the editor; timer ownership and draft recovery still occur afterward.
   Workspace state checks: 27 passed, including two new regressions.
3. **Artificial content delays:** `frontend/css/pc-components.css` no longer
   fades the whole page or staggers inserted rows. HTML references across frontend
   pages use a new stylesheet version so cached CSS cannot hide the change.
   Existing layout contracts passed; selectors/version changes inspected. Explicit
   component transitions remain. No browser visual comparison was performed.
4. **Latency visibility:** `backend/app/main.py` exports existing request processing
   duration as `Server-Timing: app;dur=...`, beside X-Request-ID. The existing access
   log test checks that both measurements match. This excludes time before the
   request enters application middleware, such as container admission and network
   transit, and excludes subsequent streaming-body delivery. It does not separate
   database work from other application work. Logging/layout checks: 8 passed.

Other verification: Modal deployment-contract check 1 passed; editor/report checks
7 passed; JavaScript syntax and git diff whitespace checks passed. Backend changes were deployed to the existing Modal app with tag
`warm-api-512m-20261007` after the user selected the 512 MiB warm-container option.
Frontend changes remain local. Production measurements above describe the prior
deployment. Post-deployment checks: health HTTP 200 in 0.549 s, readiness HTTP 200
in 0.882 s, public catalogue HTTP 200 in 1.251 s. Health returned
`Server-Timing: app;dur=293.35`. These individual samples do not establish a
production latency percentile or an authenticated page-loading speedup.

One always-warm container at minimum CPU and 512 MiB memory has an approximately
$7.12 baseline over 30 days at the current Modal Function rates, before included
credits. Actual CPU/memory consumption and additional containers can increase this;
512 MiB is a resource request, not a total monthly spending cap.

## Architecture priorities if deployed pages remain slow

1. Measure warm authenticated endpoints with the new Server-Timing header and
   request IDs. Trace database connection/pool waits, statement/commit durations,
   and object-storage hydration. Check API/database regions and place them together
   if they differ. An always-running small FastAPI service is an alternative to
   Modal warm capacity; retain Modal for execution/grading if useful.
2. Add an authenticated workspace bootstrap endpoint for session metadata, file
   manifest, task level and initial README. Authenticate once, preserve ownership
   checks, and keep timer/lease acquisition separate. This reduces repeated API,
   auth and rate-counter work. Defer noncritical analytics through a durable worker
   rather than holding page content behind analytics commits.
3. Introduce a persistent client app shell for dashboard/challenges/progress with
   cached per-account reads and background revalidation. Invalidate after session
   mutations and logout/account changes; revalidate workspace revisions before
   editing. Load Monaco only on workspace routes and prefetch likely navigation
   assets conservatively. The current lightweight backend can remain.
4. Stream AI replies so text appears as it is generated. Keep tests and grading
   asynchronous with status updates. Streaming improves perceived AI response time,
   but does not fix ordinary dashboard loading.

Reference inspiration: Vercel’s open-source assistant uses App Router and a shared
shell; its Eve template documents a static shell, paginated history and a resolved
bootstrap. Adopt those interaction/data-loading patterns without a wholesale rewrite.

Sources:
- https://modal.com/docs/guide/cold-start
- https://github.com/vercel/chatbot
- https://github.com/vercel-labs/eve-chat-template/blob/main/docs/how-the-chatbot-works.md
- https://github.com/vercel/ai/blob/main/content/docs/04-ai-sdk-ui/02-chatbot.mdx
- https://web.dev/articles/link-prefetch
