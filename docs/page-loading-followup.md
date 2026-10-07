# Page loading follow-up — 2026-10-07

The warm API did not remove the remaining per-page wait. Signed-in browser samples showed dashboard/progress requests taking roughly 800 ms end to end, with approximately 580–620 ms inside the application. The challenge brief also waited for detail and progress sequentially, finishing around 1.86 seconds in the sampled navigation.

## Implemented

- Dashboard, progress, challenge catalogue and brief keep the navigation/document mounted. Route HTML is prefetched and reused; workspace, account and report navigation retain their existing lifecycle.
- Account-scoped dashboard/progress data can render immediately from session storage for five minutes. Every visit revalidates in the background. Logout and attempt mutations invalidate it; late responses cannot refill an invalidated cache or update another route/account.
- Challenge description and fresh attempt status load concurrently. Start/resume stays disabled until status is known.
- Workspace bootstrap combines session, file list, task level and README into one authenticated, ownership-checked request. It preserves README events and revisions and does not start the timer. Older backends fall back to the previous requests.
- Request logs and Server-Timing expose database operation, SQL execution and commit durations without recording SQL or parameters. These phases overlap and must not be added together; database operation duration includes acquisition/ORM/SQL work, rather than separately measuring pool wait.

## Verification

90 targeted backend tests and 51 frontend tests passed, alongside backend lint and strict type checks. A real Chrome flow using the actual frontend and synthetic data with an artificial 800 ms API delay confirmed cached repeat visits, working back navigation, and reuse of the document/shared assets.

This batch improves navigation and removes repeated waits; first visits still depend on the API. Use the new production timing breakdown before changing database location, pooling or hosting spend. The existing warm-container configuration is unchanged.
