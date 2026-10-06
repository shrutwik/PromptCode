# Dedicated execution host

The production application and candidate execution now have separate deployments.
`docker-compose.yml` remains a local development topology. Production combines it
with `docker-compose.prod.yml`, which excludes the old executor and requires a
private HTTPS broker. `docker-compose.execution.yml` is a **standalone** deployment
for a second, dedicated machine. Never combine it with the application Compose files.

## Boundaries

- The API and queue workers retain the database, JWT, grading key and provider keys.
  They have no Docker socket. Production application startup refuses local Docker
  access and requires a remote HTTPS execution broker.
- The broker gets only a separate management token, pinned runner image digests and
  an execution-only temporary directory. Its role refuses application credentials
  and does not load the application's `.env` file. It never queries the database.
- Interview requests transfer bounded source files, a source digest and registered
  challenge/command identities. The broker rejects caller paths, images, mounts,
  environment variables, arbitrary commands and Docker options. Candidate containers
  have no network, capabilities or daemon socket and use read-only source/root with
  bounded temporary storage, memory, CPU, processes, logs and wall time.
- Grading comparisons and signatures occur on the application worker. The broker
  returns observations only. Provider calls for legacy exercises also occur on the
  application worker, with the existing shared billing limits. A bounded job-scoped
  relay transfers candidate requests and responses; provider/database credentials
  are never sent to the execution host. Legacy candidates share the broker network
  namespace to reach their temporary relay and need the host firewall below.

The broker has Docker daemon authority. This design protects the application host
by keeping that authority on a different machine; it does not make a compromised
execution host trustworthy. An attacker controlling the broker could fabricate
observations. Container kernel isolation and result integrity still require an
independent deployment audit; a microVM boundary is a possible later strengthening.

## Provisioning

1. Provision separate application and execution machines. Do not store app credentials,
   database files, backups, SSH deployment keys or unrelated workloads on the execution
   machine. Use distinct service credentials and do not copy the app `.env` there.
2. On the execution host, pre-pull reviewed backend, Python, Node and sandbox images.
   Set `IMAGE_TAG` to the reviewed backend release, and set
   `PROMPTCODE_BROKER_PYTHON_IMAGE`, `PROMPTCODE_BROKER_NODE_IMAGE` and
   `PROMPTCODE_SANDBOX_IMAGE` to immutable `repository@sha256:...` references. Broker
   readiness checks Python/Node availability; a missing sandbox image fails that job.
3. Create `/var/promptcode/execution` on a dedicated bounded filesystem (for example
   4 GiB with at least 2 GiB free), writable by the image's `promptcode` account.
   That same absolute path must be mounted into the broker. No NFS/shared application
   workspace is needed. Candidate-written legacy files now stay in 64 MiB tmpfs;
   source transfers are bounded to 20 MiB and 1,000 files. Containers are reaped by
   server-owned expiry labels, and abandoned transfer directories after one hour.
4. Generate a random management token of at least 32 bytes and provide it to both
   sides as `PROMPTCODE_SANDBOX_EXECUTOR_TOKEN`. Keep it away from candidate env.
5. Issue a TLS server certificate for a private DNS hostname. Set `BROKER_DOMAIN`,
   `BROKER_BIND_IP` to the host's private address, and `BROKER_TLS_DIR` to a directory
   containing `server.crt` and `server.key`. Caddy loads these files; this deployment
   does not rely on public HTTP certificate challenges. Restrict ingress TCP 443 to
   application hosts. Never publish broker port 8090 or a Docker TCP socket.
6. Restrict execution-host egress: deny routes to application/DB/private management
   networks and cloud metadata; allow only necessary infrastructure destinations.
   For legacy relay networking, enforce this for the broker's network namespace as
   well. Candidate code must not reach the app/DB host directly. Docker bridge rules
   can bypass simplistic host firewall rules: inspect effective forwarding rules.
7. Start the standalone execution Compose file. On the app host set
   `PROMPTCODE_EXECUTION_BROKER_URL=https://<private broker hostname>` and keep
   `PROMPTCODE_SANDBOX_EXECUTOR_URL` empty. For a private CA, place its public root
   certificate in `BROKER_CA_DIR` (default `docker/broker-ca`) and set
   `PROMPTCODE_EXECUTION_BROKER_CA_FILE=/etc/promptcode/broker-ca/ca.crt`.
   Never disable TLS verification. Start the base + production application Compose
   files after building/migrating the application release as usual.
8. Inspect the running app/worker mounts and environment, authenticate to broker
   `/ready`, then run advisory and submitted grading smoke jobs and a legacy sandbox
   job with a stubbed provider before enabling paid calls. Run the load harness and
   inspect actual Docker HostConfig, cleanup, disk and failure recovery on those hosts.

Use one Uvicorn broker process (configured in Compose). Its synchronous work retains
capacity until Docker finishes even if the HTTP caller disconnects. Multiple broker
replicas require additional host-wide admission accounting; do not scale replicas by
copying this service. Shared file locks bound actual Docker runs across call types.

The repository changes and local disposable Docker exercises do not provision these
machines, install firewall rules/certificates, or establish production capacity. The
user's project has not been hosted yet, so those deployment checks remain required.
