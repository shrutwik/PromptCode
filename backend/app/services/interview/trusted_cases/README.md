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
