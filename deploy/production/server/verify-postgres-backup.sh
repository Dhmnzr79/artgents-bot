#!/usr/bin/env bash
# Read-only G7 backup receipt + archive verification (no production DB restore).
set -Eeuo pipefail
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

readonly ENV_FILE=/etc/artgents/production.env
readonly HELPER=/opt/artgents/bin/backup-postgres-g7.py
readonly BACKUPS_PARENT=/var/lib/artgents/backups
readonly ARCHIVE_ROOT="${BACKUPS_PARENT}/postgres"
readonly RECEIPT_ROOT="${BACKUPS_PARENT}/receipts"
readonly CURRENT_ROOT=/opt/artgents/current
readonly COMPOSE_FILE="${CURRENT_ROOT}/deploy/production/compose.yml"

log_safe() {
  printf '%s\n' "$*" >&2
}

fail() {
  log_safe "verify failed: $*"
  exit 1
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

if [ "$#" -ne 1 ]; then
  fail "expected exactly one argument (absolute receipt path)"
fi

RECEIPT_PATH="$1"

if [[ "$RECEIPT_PATH" != /* ]]; then
  fail "receipt path must be absolute"
fi
if [[ "$RECEIPT_PATH" != "${RECEIPT_ROOT}/"* ]]; then
  fail "receipt path outside canonical receipts root"
fi
if [[ "$RECEIPT_PATH" == *$'\n'* ]] || [[ "$RECEIPT_PATH" == *$'\t'* ]] || [[ "$RECEIPT_PATH" == *$'\r'* ]]; then
  fail "unsafe characters in receipt path"
fi

check_env_permissions
check_helper_metadata
require_regular_file "$COMPOSE_FILE" readable

if ! python3 "$HELPER" verify-receipt "$RECEIPT_PATH" \
  --archive-root "$ARCHIVE_ROOT" \
  --receipt-root "$RECEIPT_ROOT" \
  --backups-parent "$BACKUPS_PARENT"; then
  fail "receipt metadata verification failed"
fi

ARCHIVE_PATH=$(
  python3 - "$RECEIPT_PATH" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(data["archive_path"])
PY
) || fail "failed to read archive path from receipt"

if [ -L "$ARCHIVE_PATH" ]; then
  fail "archive must not be a symlink"
fi
if [ ! -f "$ARCHIVE_PATH" ]; then
  fail "archive missing"
fi

if ! command -v docker >/dev/null 2>&1; then
  fail "docker not installed"
fi
if ! docker compose version >/dev/null 2>&1; then
  fail "docker compose v2 not available"
fi

if ! docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres pg_restore --list <"$ARCHIVE_PATH" >/dev/null; then
  fail "pg_restore --list failed"
fi

log_safe "G7 backup receipt and archive structurally verified (read-only)"
log_safe "UNKNOWN: full restore drill on disposable PostgreSQL is required before production reliance (G8)"
printf 'verify success receipt=%s\n' "$RECEIPT_PATH"
