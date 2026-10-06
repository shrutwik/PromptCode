# Trusted evaluation and restricted execution

Status: trusted evaluation and the restricted execution broker are implemented.
The separate-host Compose topology is available; physical deployment remains a prerequisite. Published grades remain
off pending real calibration and independent deployment audits.

Frozen snapshots, durable leased jobs, external comparisons, signed results and
versioned inventories for all ten questions now implement the evaluation boundary.
See [grading research and architecture](grading-research-and-architecture.md) and
[operator setup](grading-operations.md). The implemented broker and dedicated host topology are documented in
[execution-host setup](execution-host.md). Physical deployment and an independent security audit remain required.

## Option B: trusted evaluator

Advisory workspace tests import candidate Python/Node code into their runtime and
cannot authenticate correctness. The submitted-source evaluator instead keeps expected
outputs, comparisons and signing credentials outside the candidate interpreter.

Use three boundaries:

1. API accepts an owned session revision and creates an immutable, content-addressed source snapshot. It submits a job ID and challenge/version ID, never arbitrary commands, mounts or Docker flags. A durable queue grants a bounded execution lease and applies admission limits.
2. Candidate worker executes the snapshot in a disposable isolated VM/container on a dedicated execution host. It has no tests, scorer, result credentials, other candidates' data, provider keys or database access. Network is denied; resource, disk, output and wall-time limits are fixed by the service. Every restart destroys the worker state. Treat every emitted byte as adversarial.
3. Trusted evaluator runs outside the candidate namespace/interpreter. It owns a versioned test inventory, inputs and expected outputs. Challenge adapters send only individual inputs through bounded RPC/stdin/HTTP and compare returned values outside candidate execution. Service challenges use a trusted external HTTP client; library challenges need per-language adapters. Tests cannot import candidate code into the evaluator. Scores and evidence are created and signed by the evaluator with credentials unavailable to workers. Bind results to job, candidate, challenge, source digest, evaluator version and exact test inventory; reject incomplete/duplicate/replayed results.

Hidden inputs necessarily reach candidate code when exercised; keep expected outputs and the test catalog outside the worker, and do not promise input secrecy once executed. Do not expose evaluator details in assistant context. Ordinary arbitrary pytest/vitest suites require migration into external adapters; running them in a separate process inside the same candidate namespace is insufficient.

Rollout: build one Python/service and one Node adapter, adversarially verify exit/forgery/timeout/isolation attacks, migrate challenge inventories, rehearse cleanup and failure recovery, then enable authoritative grading only behind a default-off feature flag. Keep advisory practice execution during migration. Do not reinterpret historical practice scores as verified grades.

Estimated engineering effort (planning estimate, not measured): 3–5 days for a two-adapter prototype; 2–4 weeks for queue, signed results, isolated host, operational controls and adversarial verification; challenge conversion roughly 0.5–2 days each depending on interface. Production approval follows a separate audit.

## Docker privilege analysis and restricted broker

Development docker-compose.yml gives sandbox-executor the daemon socket and Docker group.
Production disables that service and uses the credential-free execution broker on a separate host. That grants daemon-level authority, including starting privileged containers and mounting host root. Non-root UID, dropped capabilities and read-only socket mounts do not reduce this API authority. Compromise of the executor can therefore compromise its Docker host. The public backend socket addition was removed; existing executor privilege is unresolved.

Recommended deployment combines a narrow broker with a dedicated disposable execution host. The app/DB host must never expose its Docker daemon to the API, workers or candidates. An isolated broker on the execution host has daemon authority; the host stores no production credentials, DB, backups or unrelated workloads. Restrict management networking and reimage/recycle it independently. Consider microVMs for stronger kernel isolation; containers alone share the host kernel.

Broker contract: authenticated create-job/status/cancel endpoints only. Accept a job reference, immutable snapshot digest and registered challenge ID. Resolve images to allowlisted immutable digests and commands to fixed templates internally. Reject caller-supplied image, argv, environment, host path, device, capability, namespace, network, volume, Docker API method or arbitrary URL. Enforce non-root UID, read-only root, no-new-privileges, drop ALL capabilities, no devices/socket, network none, bounded tmpfs, CPU/memory/PID/output/time limits, concurrency leases and ownership labels. Copy bounded source through a safe transfer protocol rather than arbitrary host mounts. Status/log output is bounded and sanitized; cancel/reap can act only on jobs owned by this broker. No unrestricted Docker endpoint is forwarded.

A method-only Docker socket proxy is insufficient: a permitted create-container request can still request privileged flags or arbitrary mounts. Validate request content and construct the Docker request internally. Authentication is necessary but does not replace this restriction. Bind job ownership to server-issued identity, enforce replay protection, fail closed on image/registry errors and deny candidate access to management endpoints.

Verification before approval: fuzz broker fields and archive paths; attempt privileged/host-network/device/socket/host-root mounts, arbitrary image/command/env injections, cross-job cancellation, snapshot swaps and replay; kill/restart API/broker and verify leases/reaping; saturate concurrency and disk; measure capacity; inspect actual Docker HostConfig. Existing process-level tests do not establish this proposed boundary.

Estimated effort: narrow broker plus tests 5–10 engineering days; isolated host lifecycle/networking/monitoring 3–5 days; evaluate microVM integration separately. No broker or host infrastructure changes are authorized by this document alone.
