# Practice session lifecycle

The practice clock measures time while the workspace is ready, visible, focused,
online, and owned by this editor. It pauses when the user leaves the window/tab,
navigates, logs out, or disconnects. Returning resumes the same saved attempt.
The server owns the accumulated time; the display uses a monotonic clock.

A heartbeat renews a 30-second editor lease every 10 seconds. Normal departures
send an immediate pause. A crash, lost pause request, or disconnected computer
can count at most the remaining 30-second lease before stopping. Only one tab or
device may hold the lease. Late heartbeats cannot restart a paused attempt, and
late pause requests from an old editor cannot pause the new editor.

## User actions

- **Save and return later:** save all changed files, pause, return to Practice.
  A save or pause failure keeps the user on the page with their recovery draft.
- **Discard attempt:** mark abandoned, freeze time, return to Practice. Saved work
  remains read-only in history. A new attempt starts with fresh code and `00:00`.
- **Resume:** restore saved files and available local drafts, acquire editing,
  continue the accumulated timer. Another editor's live lease prevents editing.
- **Submit:** save all changed files first, then freeze one submission. Accepted
  submissions stay immutable and stopped while grading runs or is retried.
- **Export work:** download the available workspace and local draft text as JSON.

Browsing a challenge creates no attempt. Starting the same challenge again reuses
its unfinished attempt; the challenge page also offers confirmed discard/restart.
Start requests are serialized with PostgreSQL transaction locks in production.
SQLite remains intended for sequential development and tests.

## Recovery and races

Changed files are autosaved every five seconds, with account/attempt-scoped local
recovery drafts on edits. Recovery drafts survive refresh, navigation, and browser
restart when local storage is available. They are device-local; another device
receives only successfully saved work. Unsaved work prompts on browser navigation.
A conflicting saved version needs explicit approval before restoring a local draft.
Save revision checks prevent overwrites from stale editors; retries of an already
accepted identical save return its existing revision. Typing during a save keeps
later edits dirty. Unaccepted AI previews are excluded from automatic saving.

Submit and discard wait for in-flight workspace actions. Submission and save-and-return
lock editing before the final saves; heartbeats cannot unlock the editor during
these actions. Failed final saves restore editing and retain recovery drafts. Lost responses are
resolved by checking the server's final state. Duplicate submit/discard requests
return the existing result. Terminal sessions cannot be edited or resurrected by
heartbeats. Only submitted attempts count toward completion and score comparisons;
all attempts, including abandoned ones, retain their existing numbering in history.

The existing wall-clock expiration (default 24 hours) is separate from practice
time and still applies while paused. Expiration freezes the clock, prevents
submission/editing, and preserves available work for viewing/export. Local drafts
are retained on expiry. Submission admitted before expiration can finish afterward;
submission admitted after expiration is rejected. Grading does not reset the timer.

## Rollout and verification

Deployment startup runs Alembic automatically. Revision `session02_pause_timer`
must complete before serving the updated API.
It preserves existing elapsed/final times and starts migrated unfinished sessions
paused. It does not alter existing reports or grading snapshots.

Regression coverage is in `backend/tests/test_interview_session_lifecycle.py` and
`frontend/js/pages/interview-session-state.test.js`, alongside existing auth,
multiple-device, level, codepad, report, AI, and submission tests. Frontend tests
exercise event handlers with a simulated DOM; production PostgreSQL concurrency
and a full browser flow require environment-specific smoke testing at rollout.
