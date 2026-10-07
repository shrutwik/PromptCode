# Performance checkpoint — 2026-10-06

Exactly four performance items were implemented. No execution limits, grading
policy, authentication policy or production configuration was changed.

## Starting checkpoint

Before edits, `main` at `2d2896c` matched `origin/main` (zero commits ahead or
behind); `git push origin main` returned `Everything up-to-date`. Untracked audit
notes, tool settings, screenshots, logs and generated media were left untouched
and excluded from the source push.

## Live homepage baseline

Target: https://promptcode-seven.vercel.app/. Chromium through Playwright.
Three samples per profile, browser cache cleared/disabled before navigation,
with paint/layout/long-task observers installed before loading. Each sample was
observed for three seconds after the load event. No account was created and no
authenticated workspace was exercised.

Desktop viewport: 1440 × 900, unthrottled. Mobile simulation: 390 × 844,
200,000 bytes/s download, 93,750 bytes/s upload, 150 ms configured network latency,
and 4× CPU slowdown through Chrome DevTools Protocol. This is a browser simulation,
not real-device field data or a Lighthouse score.

| Profile / sample | TTFB ms | First content ms | Largest content ms | Load event ms | Layout shift | Long tasks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Desktop 1 | 59.7 | 240 | 240 | 230.5 | 0.002697 | 0 |
| Desktop 2 | 33.2 | 132 | 132 | 153.9 | 0.002421 | 0 |
| Desktop 3 | 33.2 | 152 | 152 | 278.8 | 0.038889 | 0 |
| Mobile 1 | 41.0 | 600 | 928 | 1404.8 | 0.000561 | 0 |
| Mobile 2 | 34.8 | 580 | 912 | 1454.6 | 0.000561 | 0 |
| Mobile 3 | 35.9 | 568 | 912 | 1445.2 | 0.000561 | 0 |

Median desktop first content: **152 ms**, largest content: **152 ms**, load:
**230.5 ms**. Median simulated-mobile first content: **580 ms**, largest content:
**912 ms**, load: **1445.2 ms**. Same-origin resource transfer totaled 33,865 bytes
per sample; this excludes the HTML document and third-party resources. Three
samples are a baseline, not a percentile or capacity claim. The landing page is
already quick in this measurement; authenticated workspace and execution latency
are the next important deployment measurements.

## Four completed items

| Item / issue | Reference and change | Verification |
| --- | --- | --- |
| Challenge progress queried evaluations once per completed attempt | Followed the dashboard's batch-query pattern in `backend/app/api/routes/interview.py`; batch-select evaluated session IDs, preserving progress and existing score suppression | Regression with 24 completed attempts, a current active attempt and an untouched challenge; one evaluation query; identical before/after responses in isolated benchmark |
| Every rate-limit request deleted expired counters | Reused the cleanup loop in `backend/app/workers/queue.py`; added shared cleanup in `backend/app/core/ratelimit.py` and invoked it on scheduled Modal grading ticks in `backend/modal_app.py` | Boundary and concurrent-enforcement tests pass; periodic-worker and idle-Modal tests remove expired rows and retain active counters |
| Review hydration/verification/read operations blocked the API event loop | Followed existing `asyncio.to_thread` usage in interview routes; moved immutable-source work in `backend/app/services/interview/grading_review.py` off the event loop | Real local snapshot bytes returned; test verifies storage work runs on another thread; tampering, reviewer authorization and managed-storage tests pass |
| Workspace bootstrap used sequential metadata requests and fetched README twice | Followed `Promise.all` usage in the report page; updated `frontend/js/pages/interview-session.js` to load session/files/level concurrently and reuse README data; bumped its asset version in `frontend/interview-session.html` | Behavioral startup tests verify concurrency, one README fetch, revision preservation, unavailable-step fallback and draft recovery before timer resume; existing workspace tests pass |

Additional changed test files: `backend/tests/test_interview_session_lifecycle.py`,
`backend/tests/test_ratelimit.py`, `backend/tests/test_deployment_contracts.py`,
`backend/tests/test_grading_review_workflow.py`, and
`frontend/js/pages/interview-session-state.test.js`.

## Local before/after measurements

Challenge progress was called directly against an isolated, warmed SQLite database
with 24 submitted/evaluated attempts, five samples per implementation. The prior
function was loaded from the starting Git revision and run with the same current
dependencies, isolating the batch-query change. Responses were compared for parity.

| Check | Before | After |
| --- | ---: | ---: |
| Evaluation SELECTs per progress call | 24 | 1 |
| Median progress call | 8.47 ms | 3.67 ms |
| Median workspace bootstrap, simulated 100 ms per API response | 607.08 ms | 303.21 ms |
| Workspace API requests, excluding draft recovery | 6 | 5 |

The workspace comparison used the existing Node VM test harness against the prior
and current page sources, three samples each. Monaco was already initialized,
the account was authenticated in the fixture, and no local drafts existed. These
figures demonstrate reduced work and sequential waiting; they are **not production
latency estimates**, and do not measure editor download/parse time.

## Verification and known baseline limitations

- Combined targeted backend checks: **146 passed** across lifecycle, rate limiting,
  atomic limiting, grading review/export, managed storage, frontend contracts and
  deployment contracts.
- Frontend editor, workspace and report checks: **32 passed**.
- JavaScript syntax and `git diff --check`: passed.
- Ruff `F,E9,I` checks were compared with the starting revision: no new findings.
  Existing touched-file lint findings remain, including three unused imports and
  pre-existing import-order findings. They were not broadened into cleanup work.
- Before edits, the selected managed-stack integration test failed because its
  `_FakeStream` is not iterable in `modal_backend._read_capped`; 30 other selected
  backend tests passed. This unrelated fixture failure was not changed or counted
  as a passing end-to-end check.
- No deployed post-change comparison, paid AI workload, real Modal sandbox run,
  Postgres contention rehearsal or 50/100-user capacity rerun was performed.

## Next checkpoint

Deploy this reviewed batch, then measure authenticated editor readiness, save
latency and review latency under the same conditions. Profile sandbox startup,
source transfer, execution duration and queue waiting before changing capacity.
Retain digest verification, atomic rate enforcement and editor/timer ownership.
