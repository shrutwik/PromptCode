#!/usr/bin/env bash
# backup-db.sh — Host-level PostgreSQL backup for PromptCode.
#
# Usage:
#   bash /opt/promptcode/scripts/backup-db.sh
#
# Env vars (sourced from /opt/promptcode/.env if not already exported):
#   PROMPTCODE_DB_PASSWORD  — Postgres password (required by pg_dump inside container)
#   PROMPTCODE_DB_USER      — Postgres user (default: promptcode)
#   PROMPTCODE_DB_NAME      — Postgres database name (default: promptcode)
#   BACKUP_DIR              — Where to store backups (default: /opt/promptcode/backups)
#   BACKUP_RETENTION_DAYS   — Number of days to keep local backups (default: 7)
#   RCLONE_REMOTE           — Required rclone remote path (e.g. s3:my-bucket/backups)
#
# To run automatically, add a crontab entry (as the deploy user):
#   0 3 * * * /opt/promptcode/scripts/backup-db.sh >> /opt/promptcode/backups/backup.log 2>&1

set -euo pipefail
umask 077

DEPLOY_DIR="${DEPLOY_DIR:-/opt/promptcode}"
BACKUP_DIR="${BACKUP_DIR:-${DEPLOY_DIR}/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)-$$"
BACKUP_FILE="${BACKUP_DIR}/promptcode-${TIMESTAMP}.sql.gz"
ARTIFACT_FILE="${BACKUP_DIR}/promptcode-${TIMESTAMP}.artifacts.tar.gz"
CHECKSUM_FILE="${BACKUP_DIR}/promptcode-${TIMESTAMP}.sha256"
LAST_SUCCESS_FILE="${BACKUP_DIR}/last-successful-backup.txt"
LAST_SUCCESS_COMPAT_FILE="${BACKUP_DIR}/.last-success-timestamp"

# Load .env if password not already in environment
if [[ -z "${PROMPTCODE_DB_PASSWORD:-}" && -f "${DEPLOY_DIR}/.env" ]]; then
    # shellcheck disable=SC1090
    set -a; source "${DEPLOY_DIR}/.env"; set +a
fi

PROMPTCODE_DB_USER="${PROMPTCODE_DB_USER:-promptcode}"
PROMPTCODE_DB_NAME="${PROMPTCODE_DB_NAME:-promptcode}"

if [[ -z "${RCLONE_REMOTE:-}" ]]; then
    echo "[backup] RCLONE_REMOTE must be set for off-host backups." >&2
    exit 1
fi

if ! command -v rclone >/dev/null 2>&1; then
    echo "[backup] rclone is required for off-host backups." >&2
    exit 1
fi

mkdir -p "${BACKUP_DIR}"
ARTIFACT_ROOT="${BACKUP_ARTIFACT_ROOT:-${PROMPTCODE_INTERVIEW_HOST_WORKDIR:-/var/promptcode/interview_workspaces}}"
if [[ ! -d "${ARTIFACT_ROOT}" ]]; then
    echo '[backup] Interview artifact root is missing; refusing an incomplete backup.' >&2
    exit 1
fi
mkdir -p "${ARTIFACT_ROOT}/.submitted"
WORK_DIR="$(mktemp -d "${BACKUP_DIR}/.backup.XXXXXX")"
trap 'rm -rf "${WORK_DIR}"' EXIT

echo "[backup] Writing ${BACKUP_FILE}..."
docker compose -f "${DEPLOY_DIR}/docker-compose.yml" \
               -f "${DEPLOY_DIR}/docker-compose.prod.yml" \
    exec -T db pg_dump -U "${PROMPTCODE_DB_USER}" "${PROMPTCODE_DB_NAME}" \
    | gzip > "${WORK_DIR}/$(basename "${BACKUP_FILE}")"

# Capture after pg_dump so every committed grading source is included. Hold the
# same host lock as API writes while copying active progress and starter source.
python3 - "${ARTIFACT_ROOT}" "${WORK_DIR}/$(basename "${ARTIFACT_FILE}")" <<'PY'
import fcntl, pathlib, re, stat, sys, tarfile
root = pathlib.Path(sys.argv[1])
session = re.compile(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}(?:\.starter|\.submitted)?')
skip = {'node_modules', '.venv', 'venv', '__pycache__', '.pytest_cache', '.git', 'dist', 'build', '.turbo', 'coverage'}
def include(member):
    if not (member.isdir() or member.isfile()):
        raise ValueError('Backup source contains a link or special file')
    if set(pathlib.PurePosixPath(member.name).parts) & skip:
        return None
    return member
with (root / '.storage.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    with tarfile.open(sys.argv[2], 'w:gz') as archive:
        archive.add(root, arcname='.', recursive=False, filter=include)
        for child in sorted(root.iterdir()):
            if child.name == '.submitted' or session.fullmatch(child.name):
                archive.add(child, arcname=child.name, filter=include)
PY
python3 - "${WORK_DIR}" "$(basename "${BACKUP_FILE}")" "$(basename "${ARTIFACT_FILE}")" > "${WORK_DIR}/$(basename "${CHECKSUM_FILE}")" <<'PY'
import hashlib, pathlib, sys
for name in sys.argv[2:]:
    digest = hashlib.sha256()
    with (pathlib.Path(sys.argv[1]) / name).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    print(f'{digest.hexdigest()}  {name}')
PY
for file in "${BACKUP_FILE}" "${ARTIFACT_FILE}" "${CHECKSUM_FILE}"; do
    mv "${WORK_DIR}/$(basename "${file}")" "${file}"
done

echo "[backup] Done. Size: $(du -sh "${BACKUP_FILE}" | cut -f1)"

# ── Retention ────────────────────────────────────────────────────────────────
echo "[backup] Pruning backups older than ${BACKUP_RETENTION_DAYS} days..."

# ── Mandatory off-host upload via rclone ─────────────────────────────────────
echo "[backup] Uploading to ${RCLONE_REMOTE}..."
rclone copy "${BACKUP_FILE}" "${RCLONE_REMOTE}"
rclone copy "${ARTIFACT_FILE}" "${RCLONE_REMOTE}"
rclone copy "${CHECKSUM_FILE}" "${RCLONE_REMOTE}"
LAST_SUCCESS_EPOCH="$(date -u +%s)"
printf '%s\n' "${LAST_SUCCESS_EPOCH}" > "${WORK_DIR}/success"
cp "${WORK_DIR}/success" "${WORK_DIR}/success-compat"
mv "${WORK_DIR}/success" "${LAST_SUCCESS_FILE}"
mv "${WORK_DIR}/success-compat" "${LAST_SUCCESS_COMPAT_FILE}"
find "${BACKUP_DIR}" -type f \( -name 'promptcode-*.sql.gz' -o -name 'promptcode-*.artifacts.tar.gz' -o -name 'promptcode-*.sha256' \) -mtime "+${BACKUP_RETENTION_DAYS}" -delete
echo "[backup] Upload complete."

echo "[backup] Backup complete."
