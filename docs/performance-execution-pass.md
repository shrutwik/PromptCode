# Execution performance checkpoint — 2026-10-06

This continues the [first performance pass](performance-first-pass.md). Exactly
four items were completed: two transfer optimizations and two timing additions.
Runner limits, waiting limits, deadlines, sandbox isolation and digest verification
remain unchanged. These changes have not been deployed or measured on live Modal.

## Completed items

| Issue | Reference / change | Verification |
| --- | --- | --- |
| Sandbox upload descended into dependencies before discarding them | Followed the pruned `os.walk` pattern in `workspace.workspace_has_escape_link`; `execution/modal_backend.py::_upload_source` prunes ignored dependency directories and links before descent, preserving files and empty directories | Regression fails if ignored directories are scanned; validates exact uploaded bytes and no linked content |
| Submission hydration downloaded each file twice | `interview/workspace_store.py::fetch_submission` verifies each downloaded object's size/hash once, then materializes those same bytes; retains final snapshot verification | Each object fetched once; normal hydration, missing objects, tampering and immutable-source review checks pass |
| Aggregate sandbox duration could not distinguish startup from transfer/execution | Followed structured logging in `core/logging.py`; `modal_backend.py::_execute` emits `sandbox.complete` with `create_ms`, `upload_ms`, `execute_ms`, `cleanup_ms`, `outcome` and `failed_phase` | Controlled-clock tests assert exact phase durations on success and upload failure; sandbox cleanup still executes |
| Queue waits and protective refusals were not separately timed | `execution_broker.py::execute` emits `execution.admission` with `wait_ms`, `outcome`, `active`, `waiting`, `capacity` and `max_waiters`; broker startup uses shared structured logging | Covers admitted/full/timeout/cancelled outcomes; rejected work never starts; real in-process queue wait is included; cancellation continues holding capacity until work ends |

Outcome labels are fixed service values; timing logs do not include candidate
source, output, credentials or host paths. Sandbox execution timing includes
process execution, output draining and exit-code collection. Cleanup duration
records the termination attempt, not a separate confirmation of remote deletion.

## Local comparisons

Prior implementations were loaded from the starting Git revision and compared
with the changed functions, using temporary source/object directories only.
Five samples per implementation; medians shown.

| Measurement | Before | After |
| --- | ---: | ---: |
| Source traversal with 2,000 ignored dependency files | 50.39 ms | 0.06 ms |
| Reads per hydrated object | 2 | 1 |
| One-file hydration with simulated 20 ms latency per object read | 51.02 ms | 27.16 ms |

Source traversal used 200 ignored directories with ten files each and one included
source file; filesystem upload calls were local no-ops. Hydration used the real
local object store with an artificial read delay; returned bytes were checked.
These are focused local comparisons, not remote throughput or production latency
claims. Pruning helps when ignored trees are present; it does not make a
dependency-free source tree materially smaller.

Hydration now temporarily retains verified file contents before writing. For
ordinary quota-constrained submissions this can add up to the source size
(the current source quota is 20 MiB) per concurrent hydration. This preserves the
previous behavior of rejecting invalid objects before materializing any source
files. Account for that memory in deployed worker measurements.

## Verification

Baseline: **72 passed, 1 skipped** across Modal backend, broker, runner capacity,
probe parallelism and managed storage tests.

Final targeted checks: **99 passed, 1 skipped, 1 deselected** across those suites
plus managed failure cases, grading review and logging tests. The skipped case
is the opt-in live Docker capacity test. The deselected managed duplicate-grading
test also failed using the original hydration function: its worker ended queued,
queued, then failed instead of completed. It is a pre-existing managed test
failure and is not counted as a passing end-to-end check.

`git diff --check` passed. Ruff `F,E9,I` findings were compared with the starting
revision: no new findings. Existing import-order findings and the broker's
unused `os` import remain outside this batch.

Changed implementation files:

- `backend/app/services/execution/modal_backend.py`
- `backend/app/services/interview/workspace_store.py`
- `backend/app/execution_broker.py`

Changed regression files:

- `backend/tests/test_modal_execution_backend.py`
- `backend/tests/test_managed_storage.py`
- `backend/tests/test_execution_broker.py`

## Next measurement

After deploying the reviewed branch, collect `sandbox.complete` and
`execution.admission` records for a small controlled cohort. Compare queue wait,
create, upload, execute and cleanup distributions, successful throughput and
memory/CPU headroom. Use the results to decide between reducing cold startup,
improving source transfer or increasing execution capacity. The existing local
capacity reports do not establish deployed capacity, and no paid AI or real
Modal sandbox workload was run during this pass.
