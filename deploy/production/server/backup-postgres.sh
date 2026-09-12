#!/usr/bin/env bash
# Root-owned PostgreSQL backup utility (install to /opt/artgents/bin/backup-postgres).
set -Eeuo pipefail
umask 077
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

readonly CURRENT_ROOT=/opt/artgents/current
readonly COMPOSE_FILE="${CURRENT_ROOT}/deploy/production/compose.yml"
readonly ENV_FILE=/etc/artgents/production.env
readonly HELPER=/opt/artgents/bin/backup-postgres-g7.py
readonly BACKUPS_PARENT=/var/lib/artgents/backups
readonly ARCHIVE_ROOT="${BACKUPS_PARENT}/postgres"
readonly RECEIPT_ROOT="${BACKUPS_PARENT}/receipts"
readonly LOCK_FILE=/var/lock/artgents-postgres-backup.lock
readonly RETENTION_DAYS=7

REASON=""
SOURCE_SHA=""
SOURCE_SHA_SEEN=0

ARCHIVE_TMP=""
RECEIPT_TMP=""
STDERR_TMP=""
WORK_DIR=""

POSTGRES_USER_NAME=""
DATABASE_NAME=""

BACKUP_COMMITTED=0
ARCHIVE_FINAL_CREATED=0
RECEIPT_FINAL_CREATED=0
RUN_ARCHIVE_FINAL=""
RUN_RECEIPT_FINAL=""
ARCHIVE_FINAL=""
RECEIPT_FINAL=""

BACKUP_ID=""
UNIQUE_SUFFIX=""

log_safe() {
  printf '%s\n' "$*" >&2
}

fail() {
  log_safe "backup failed: $*"
  exit 1
}

verify_work_dir_containment() {
  if [ -z "$WORK_DIR" ]; then
    return 0
  fi
  if [ -L "$WORK_DIR" ]; then
    fail "work directory must not be a symlink"
  fi
  local canonical_work="" canonical_root=""
  canonical_root=$(realpath -e -- "$ARCHIVE_ROOT") || fail "archive root invalid"
  canonical_work=$(realpath -e -- "$WORK_DIR") || fail "work directory invalid"
  if [ "$canonical_work" = "$canonical_root" ]; then
    fail "work directory must not be archive root"
  fi
  case "$canonical_work" in
    "${canonical_root}"/*) ;;
    *) fail "work directory outside archive root" ;;
  esac
}

safe_remove_run_artifact() {
  local path="$1"
  local root="$2"
  local kind="$3"
  if [ -z "$path" ]; then
    return 0
  fi
  if ! python3 "$HELPER" validate-run-artifact --path "$path" --root "$root" --kind "$kind"; then
    return 0
  fi
  rm -f "$path"
}

rollback_uncommitted_backup_pair() {
  if [ "$BACKUP_COMMITTED" -eq 1 ]; then
    return 0
  fi
  if [ "$RECEIPT_FINAL_CREATED" -eq 1 ] && [ -n "$RUN_RECEIPT_FINAL" ]; then
    safe_remove_run_artifact "$RUN_RECEIPT_FINAL" "$RECEIPT_ROOT" receipt
  fi
  if [ "$ARCHIVE_FINAL_CREATED" -eq 1 ] && [ -n "$RUN_ARCHIVE_FINAL" ]; then
    safe_remove_run_artifact "$RUN_ARCHIVE_FINAL" "$ARCHIVE_ROOT" archive
  fi
}

cleanup_on_exit() {
  cleanup_work
  rollback_uncommitted_backup_pair
}

cleanup_work() {
  if [ -n "$ARCHIVE_TMP" ] && [ -f "$ARCHIVE_TMP" ]; then
    rm -f "$ARCHIVE_TMP"
    ARCHIVE_TMP=""
  fi
  if [ -n "$STDERR_TMP" ] && [ -f "$STDERR_TMP" ]; then
    rm -f "$STDERR_TMP"
    STDERR_TMP=""
  fi
  if [ -n "$RECEIPT_TMP" ] && [ -f "$RECEIPT_TMP" ]; then
    rm -f "$RECEIPT_TMP"
    RECEIPT_TMP=""
  fi
  if [ -z "$WORK_DIR" ]; then
    return 0
  fi
  if [ ! -d "$WORK_DIR" ]; then
    WORK_DIR=""
    return 0
  fi
  verify_work_dir_containment
  rm -f "${WORK_DIR}/archive.pgdump.custom" "${WORK_DIR}/pg_dump.stderr" 2>/dev/null || true
  if rmdir "$WORK_DIR" 2>/dev/null; then
    WORK_DIR=""
  fi
}

trap cleanup_on_exit EXIT

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --reason)
        if [ "$#" -lt 2 ]; then
          fail "missing value for --reason"
        fi
        if [ -n "$REASON" ]; then
          fail "duplicate --reason"
        fi
        REASON="$2"
        shift 2
        ;;
      --source-sha)
        if [ "$#" -lt 2 ]; then
          fail "missing value for --source-sha"
        fi
        if [ "$SOURCE_SHA_SEEN" -ne 0 ]; then
          fail "duplicate --source-sha"
        fi
        SOURCE_SHA="$2"
        SOURCE_SHA_SEEN=1
        shift 2
        ;;
      *)
        fail "unexpected argument"
        ;;
    esac
  done

  if [ -z "$REASON" ]; then
    fail "missing --reason"
  fi
  case "$REASON" in
    pre-deploy | pre-rollback | scheduled) ;;
    *) fail "invalid reason" ;;
  esac
  if [ "$REASON" = "scheduled" ]; then
    if [ "$SOURCE_SHA_SEEN" -ne 0 ]; then
      fail "source-sha not allowed for scheduled backup"
    fi
  else
    if [ "$SOURCE_SHA_SEEN" -eq 0 ]; then
      fail "source-sha required"
    fi
    if ! [[ "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]; then
      fail "invalid source_sha"
    fi
  fi
}

require_regular_file() {
  local path="$1"
  local mode="$2"
  if [ -L "$path" ]; then
    fail "symlink not allowed: $path"
  fi
  case "$mode" in
    readable)
      [ -f "$path" ] && [ -r "$path" ] || fail "not a readable file: $path"
      ;;
    executable)
      [ -f "$path" ] && [ -x "$path" ] || fail "not executable: $path"
      ;;
    *)
      fail "invalid require_regular_file mode"
      ;;
  esac
}

require_trusted_dir_0700() {
  local path="$1"
  local label="$2"
  if [ -L "$path" ]; then
    fail "${label} must not be a symlink"
  fi
  if [ ! -d "$path" ]; then
    fail "${label} must be a directory"
  fi
  local owner perms
  owner=$(stat -c '%u:%g' "$path")
  perms=$(stat -c '%a' "$path")
  if [ "$owner" != "0:0" ]; then
    fail "${label} must be root-owned"
  fi
  if [ "$perms" != "700" ]; then
    fail "${label} must be mode 0700"
  fi
}

ensure_trusted_dir_0700() {
  local path="$1"
  local label="$2"
  if [ -e "$path" ]; then
    require_trusted_dir_0700 "$path" "$label"
  else
    mkdir -p "$path"
    chmod 700 "$path"
    require_trusted_dir_0700 "$path" "$label"
  fi
}

check_env_permissions() {
  require_regular_file "$ENV_FILE" readable
  local owner perms
  owner=$(stat -c '%u:%g' "$ENV_FILE")
  perms=$(stat -c '%a' "$ENV_FILE")
  if [ "$owner" != "0:0" ]; then
    fail "production env must be root-owned"
  fi
  if [ "$((10#${perms} & 077))" -ne 0 ]; then
    fail "production env must not be world/group readable"
  fi
}

check_helper_metadata() {
  require_regular_file "$HELPER" executable
  local owner perms
  owner=$(stat -c '%u:%g' "$HELPER")
  perms=$(stat -c '%a' "$HELPER")
  if [ "$owner" != "0:0" ]; then
    fail "backup helper must be root-owned"
  fi
  if [ "$perms" != "750" ]; then
    fail "backup helper must be mode 0750"
  fi
}

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

fsync_path() {
  local target="$1"
  python3 - "$target" <<'PY'
import os
import sys

path = sys.argv[1]
fd = os.open(path, os.O_RDONLY)
os.fsync(fd)
os.close(fd)
parent = os.path.dirname(path) or "."
dfd = os.open(parent, os.O_RDONLY)
os.fsync(dfd)
os.close(dfd)
PY
}

load_postgres_targets() {
  local parsed line key value
  if ! parsed=$(python3 "$HELPER" parse-targets --env-file "$ENV_FILE"); then
    fail "failed to read postgres targets from production env"
  fi
  POSTGRES_USER_NAME=""
  DATABASE_NAME=""
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    key="${line%%=*}"
    value="${line#*=}"
    case "$key" in
      POSTGRES_USER) POSTGRES_USER_NAME="$value" ;;
      POSTGRES_DB) DATABASE_NAME="$value" ;;
      *) fail "unexpected parse-targets output" ;;
    esac
  done <<< "$parsed"
  if [ -z "$POSTGRES_USER_NAME" ] || [ -z "$DATABASE_NAME" ]; then
    fail "postgres targets incomplete"
  fi
}

load_backup_identity() {
  local parsed line key value
  if ! parsed=$(python3 "$HELPER" new-backup-identity); then
    fail "failed to generate backup identity"
  fi
  BACKUP_ID=""
  UNIQUE_SUFFIX=""
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    key="${line%%=*}"
    value="${line#*=}"
    case "$key" in
      BACKUP_ID) BACKUP_ID="$value" ;;
      UNIQUE_SUFFIX) UNIQUE_SUFFIX="$value" ;;
      *) fail "unexpected new-backup-identity output" ;;
    esac
  done <<< "$parsed"
  if ! [[ "$BACKUP_ID" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
    fail "invalid backup identity"
  fi
  if ! [[ "$UNIQUE_SUFFIX" =~ ^[0-9a-f]{16}$ ]]; then
    fail "invalid backup identity suffix"
  fi
}

mark_backup_committed() {
  BACKUP_COMMITTED=1
}

parse_args "$@"

if [ "$(id -u)" -ne 0 ]; then
  fail "must run as root"
fi

exec 8>"$LOCK_FILE"
if ! flock -n 8; then
  fail "another postgres backup is in progress"
fi

check_env_permissions
require_regular_file "$COMPOSE_FILE" readable
if [ -L "$CURRENT_ROOT" ]; then
  fail "current root must not be a symlink"
fi
if [ ! -d "$CURRENT_ROOT" ]; then
  fail "current root must be a directory"
fi
check_helper_metadata

if ! command -v docker >/dev/null 2>&1; then
  fail "docker not installed"
fi
if ! docker compose version >/dev/null 2>&1; then
  fail "docker compose v2 not available"
fi

ensure_trusted_dir_0700 "$BACKUPS_PARENT" "backups parent"
ensure_trusted_dir_0700 "$ARCHIVE_ROOT" "archive root"
ensure_trusted_dir_0700 "$RECEIPT_ROOT" "receipt root"

load_postgres_targets

WORK_DIR=$(mktemp -d "${ARCHIVE_ROOT}/.work.XXXXXX")
verify_work_dir_containment
ARCHIVE_TMP="${WORK_DIR}/archive.pgdump.custom"
STDERR_TMP="${WORK_DIR}/pg_dump.stderr"

if ! compose exec -T postgres pg_dump \
  --username "$POSTGRES_USER_NAME" \
  --dbname "$DATABASE_NAME" \
  --format=custom >"$ARCHIVE_TMP" 2>"$STDERR_TMP"; then
  log_safe "pg_dump failed (stderr retained on host temp path, not printed)"
  fail "pg_dump failed"
fi

if [ ! -s "$ARCHIVE_TMP" ]; then
  fail "empty backup archive"
fi

if ! compose exec -T postgres pg_restore --list <"$ARCHIVE_TMP" >/dev/null 2>"$STDERR_TMP"; then
  fail "pg_restore --list validation failed"
fi

ARCHIVE_SHA256=$(
  python3 - "$ARCHIVE_TMP" <<'PY'
import hashlib
import sys
from pathlib import Path

path = Path(sys.argv[1])
h = hashlib.sha256()
with path.open("rb") as fh:
    for chunk in iter(lambda: fh.read(1024 * 1024), b""):
        h.update(chunk)
print(f"sha256:{h.hexdigest()}")
PY
) || fail "failed to compute archive sha256"

ARCHIVE_SIZE=$(stat -c '%s' "$ARCHIVE_TMP")
if [ "$ARCHIVE_SIZE" -le 0 ]; then
  fail "invalid archive size"
fi

CREATED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
load_backup_identity
BASENAME="pgbackup-${REASON}-${CREATED_AT//:/}-${UNIQUE_SUFFIX}"
ARCHIVE_FINAL="${ARCHIVE_ROOT}/${BASENAME}.pgdump.custom"
RECEIPT_FINAL="${RECEIPT_ROOT}/${BASENAME}.receipt.json"

if [ -e "$ARCHIVE_FINAL" ] || [ -e "$RECEIPT_FINAL" ]; then
  fail "backup path collision"
fi

mv -f "$ARCHIVE_TMP" "$ARCHIVE_FINAL"
ARCHIVE_FINAL_CREATED=1
RUN_ARCHIVE_FINAL="$ARCHIVE_FINAL"
ARCHIVE_TMP=""
chmod 600 "$ARCHIVE_FINAL"
fsync_path "$ARCHIVE_FINAL"

RECEIPT_TMP=$(mktemp "${RECEIPT_ROOT}/.receipt.XXXXXX")
chmod 600 "$RECEIPT_TMP"

SOURCE_SHA_ARG=""
if [ "$REASON" != "scheduled" ]; then
  SOURCE_SHA_ARG="$SOURCE_SHA"
fi

if ! python3 "$HELPER" write-receipt \
  --output "$RECEIPT_TMP" \
  --reason "$REASON" \
  --source-sha "$SOURCE_SHA_ARG" \
  --created-at "$CREATED_AT" \
  --archive-path "$ARCHIVE_FINAL" \
  --archive-sha256 "$ARCHIVE_SHA256" \
  --archive-size-bytes "$ARCHIVE_SIZE" \
  --database-name "$DATABASE_NAME" \
  --backup-id "$BACKUP_ID"; then
  fail "failed to write backup receipt"
fi

mv -f "$RECEIPT_TMP" "$RECEIPT_FINAL"
RECEIPT_FINAL_CREATED=1
RUN_RECEIPT_FINAL="$RECEIPT_FINAL"
RECEIPT_TMP=""
chmod 600 "$RECEIPT_FINAL"
fsync_path "$RECEIPT_FINAL"
mark_backup_committed

cleanup_work

if ! python3 "$HELPER" run-retention --days "$RETENTION_DAYS"; then
  log_safe "retention failed after successful backup (fail-closed visibility)"
  exit 1
fi

printf '%s\n' "$RECEIPT_FINAL"
