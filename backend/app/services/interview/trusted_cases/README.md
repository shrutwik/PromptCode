# Trusted behavioral evaluation

These server-only inventories derive from each challenge's stated requirements;
they do not run or import candidate pytest/vitest suites. A version and content
digest cover probe code, independent expected outputs, weights, and uncovered
requirements. Changing any of those invalidates old result bindings.

Each case starts a fresh candidate container with only frozen source mounted
read-only. It receives an observation adapter and inputs, but no expected output,
scoring code, result signing key, database credential, or Docker socket. The
executor reads bounded JSON and compares it outside the candidate interpreter.
Container exit status, deadlines, memory/CPU/process limits, no networking,
read-only root, and cleanup are enforced externally. Candidate-written advisory
exit markers and test reports are never accepted as grading evidence.

The HMAC envelope binds session, job, attempt lease, challenge version, source digest, inventory digest, and
evaluator version. Backend verification checks signature, full case inventory,
weights, outcomes, totals, and explicit coverage gaps before human review.
Infrastructure errors remain retryable; malformed output, candidate exceptions,
and execution timeouts are failed behavioral cases. They never become a signed
candidate-supplied score.

These are behavioral checks, not a proof of arbitrary program correctness.
Catalog latency and scan-counter integrity, rendered React behavior, and pricing
source delegation remain explicit human-review requirements. Do not treat a
100% behavioral score as verification of those requirements. Published rubric
assessments additionally require authenticated human evidence review and
calibration readiness.

`backend/tests/trusted_reference_fixtures.py` contains test-only reviewed repairs.
The opt-in Docker tests validate each starter, each repair, a plausible incorrect
repair for every question, forged grade-shaped output, and immutable Python/Node
submission signing. Reference implementations never enter candidate images.

The v5 inventory has 202 independent cases across twenty-five coding questions: the
original 62 cases plus 80 cases for ten progressive additions, 40 cases for five ranked additions and 20 pressure cases.
Coverage includes the invoice API transition matrix, rejected-write state
preservation, bidirectional tenant isolation, Unicode and optional hold reasons,
empty and zero-limit searches, repeated concurrent notifications, multi-file
deduplication and negative quantities, exhausted retries and batch result order,
half-cent rounding, and microsecond and adjacent-period boundaries.
Visible practice suites exercise the same requirements with separate assertions.
Ten additional edge-case mutations verify that superficially correct repairs
are rejected, alongside the ten original incorrect-repair checks.

The expansion adds twenty more wrong-repair fixtures (a baseline and an edge
mutation per new question). `expansion.py` holds its independent inputs and
observations. Reviewed reference sources remain test-only in
`backend/tests/expansion_reference_fixtures.py`; they never enter candidate
images. Local authoring QA in `test_interview_expansion_quality.py` checks those
reviewed sources and known starters in fresh subprocesses; it is not the
production candidate evaluator and does not sign results. Docker release QA
continues to validate all twenty-five questions in the actual isolated runner.

Registry version 4 and evaluator version v5 intentionally invalidate old result
bindings. Checkpoints live inside one ticket; optional review discussions do not
silently add ungraded requirements to the baseline.

Run the isolated grading validation from the repository root:

```sh
PROMPTCODE_AUDIT_DOCKER=1 PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_trusted_evaluator.py -q
```

Docker and the configured runner images are required. Practice tests intentionally
fail on incident starters; validate green runs against the reviewed reference
repairs, preserving the starter bugs for candidates. Changing the inventory
version and digest intentionally invalidates previously bound grading evidence.

The five additional ranked families add forty independent probes and ten wrong-repair cases. Their reviewed references are in `backend/tests/ranked_reference_fixtures.py`. Canvas and search have rendered visible suites and explicit human-review requirements; state/HTTP probes alone do not close those requirements. The ranked top twenty remain distinguishable from five retained exercises via candidate-safe `featured_rank` metadata.

The October 8 refinement advances to evaluator v5 and registry version 4: 202 probes across 25 questions. Twenty new pressure probes live in `depth.py`, with different public fixtures. Each featured question maps all independent cases once to three baseline parts; its fourth part is optional discussion and has no grading cases. Publication checks enforce this partition. Original manual review gaps remain declared.
