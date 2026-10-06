#!/usr/bin/env bash
# restore-db.sh — Restore a PromptCode PostgreSQL backup locally or from rclone.

set -euo pipefail
umask 077

DEPLOY_DIR="${DEPLOY_DIR:-/opt/promptcode}"
BACKUP_DIR="${BACKUP_DIR:-${DEPLOY_DIR}/backups}"
BACKUP_REF="${1:-}"

if [[ -z "${BACKUP_REF}" ]]; then
    echo "Usage: bash ${0##*/} <backup-file.sql.gz>" >&2
    exit 1
fi

if [[ -f "${DEPLOY_DIR}/.env" ]]; then
    # shellcheck disable=SC1090
    set -a; source "${DEPLOY_DIR}/.env"; set +a
fi

PROMPTCODE_DB_USER="${PROMPTCODE_DB_USER:-promptcode}"
PROMPTCODE_DB_NAME="${PROMPTCODE_DB_NAME:-promptcode}"

LOCAL_BACKUP="${BACKUP_REF}"
if [[ ! -f "${LOCAL_BACKUP}" ]]; then
    if [[ -z "${RCLONE_REMOTE:-}" ]]; then
        echo "[restore] RCLONE_REMOTE must be set to download non-local backups." >&2
        exit 1
    fi
    if ! command -v rclone >/dev/null 2>&1; then
        echo "[restore] rclone is required to download remote backups." >&2
        exit 1
    fi
    mkdir -p "${BACKUP_DIR}"
    LOCAL_BACKUP="${BACKUP_DIR}/$(basename "${BACKUP_REF}")"
    echo "[restore] Downloading $(basename "${BACKUP_REF}") from ${RCLONE_REMOTE}..."
    rclone copyto "${RCLONE_REMOTE%/}/$(basename "${BACKUP_REF}")" "${LOCAL_BACKUP}"
fi

if [[ ! -f "${LOCAL_BACKUP}" ]]; then
    echo "[restore] Backup file not found: ${LOCAL_BACKUP}" >&2
    exit 1
fi

echo "[restore] Restoring ${LOCAL_BACKUP} into ${PROMPTCODE_DB_NAME} as ${PROMPTCODE_DB_USER}..."
# New backups include matching immutable source and checksums. Legacy SQL-only
# backups remain supported, but cannot recover grading source artifacts.
ARTIFACT_FILE="${LOCAL_BACKUP%.sql.gz}.artifacts.tar.gz"
CHECKSUM_FILE="${LOCAL_BACKUP%.sql.gz}.sha256"
if [[ "${LOCAL_BACKUP}" != "${BACKUP_REF}" ]]; then
    rclone copyto "${RCLONE_REMOTE%/}/$(basename "${CHECKSUM_FILE}")" "${CHECKSUM_FILE}" || true
    if [[ -f "${CHECKSUM_FILE}" ]]; then
        rclone copyto "${RCLONE_REMOTE%/}/$(basename "${ARTIFACT_FILE}")" "${ARTIFACT_FILE}"
    fi
fi
if [[ -f "${CHECKSUM_FILE}" ]]; then
    ARTIFACT_ROOT="${BACKUP_ARTIFACT_ROOT:-${PROMPTCODE_INTERVIEW_HOST_WORKDIR:-/var/promptcode/interview_workspaces}}"
    python3 - "${CHECKSUM_FILE}" "${LOCAL_BACKUP}" "${ARTIFACT_FILE}" "${ARTIFACT_ROOT}" <<'PY'
import hashlib, os, pathlib, re, sys, tarfile
root = pathlib.Path(sys.argv[4])
if root.is_symlink() or (root.exists() and any(root.iterdir())):
    raise SystemExit('[restore] Stop application/workers and use an empty artifact destination')
session = re.compile(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}(?:\.starter|\.submitted)?')
checksums = {}
for line in pathlib.Path(sys.argv[1]).read_text().splitlines():
    digest, name = line.split('  ', 1)
    checksums[name] = digest
for path in map(pathlib.Path, sys.argv[2:4]):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    if checksums.get(path.name) != digest.hexdigest():
        raise SystemExit('[restore] Backup checksum mismatch')
with tarfile.open(sys.argv[3]) as archive:
    for member in archive:
        path = pathlib.PurePosixPath(member.name)
        if member.name == '.' and member.isdir():
            pass
        elif (path.is_absolute() or '..' in path.parts or not path.parts
                or not (path.parts[0] == '.submitted' or session.fullmatch(path.parts[0]))
                or not (member.isdir() or member.isfile())):
            raise SystemExit('[restore] Unsafe source archive')
        if os.geteuid() != 0 and member.uid != os.geteuid():
            raise SystemExit('[restore] Run as root to preserve application artifact ownership')
PY
    mkdir -p "${ARTIFACT_ROOT}"
    if [[ "$(id -u)" == '0' ]]; then
        tar -xzf "${ARTIFACT_FILE}" -C "${ARTIFACT_ROOT}" --same-owner --numeric-owner
    else
        tar -xzf "${ARTIFACT_FILE}" -C "${ARTIFACT_ROOT}" --no-same-owner
    fi
elif [[ -f "${ARTIFACT_FILE}" || "$(basename "${LOCAL_BACKUP}")" =~ ^promptcode-[0-9]{8}T[0-9]{6}Z(-[0-9]+)?\.sql\.gz$ ]]; then
    echo '[restore] Missing checksums for source artifact backup.' >&2
    exit 1
else
    echo '[restore] Legacy SQL-only backup: frozen grading source is not restored.' >&2
fi
gunzip -c "${LOCAL_BACKUP}" | docker compose -f "${DEPLOY_DIR}/docker-compose.yml" \
  -f "${DEPLOY_DIR}/docker-compose.prod.yml" \
  exec -T db psql -v ON_ERROR_STOP=1 -U "${PROMPTCODE_DB_USER}" -d "${PROMPTCODE_DB_NAME}"
echo "[restore] Restore complete."
