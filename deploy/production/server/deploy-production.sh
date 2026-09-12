#!/usr/bin/env bash
# Root-owned production deploy script (install to /opt/artgents/bin/deploy-production).
set -Eeuo pipefail
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

readonly IMAGE_REPO=ghcr.io/dhmnzr79/artgents-bot
readonly CURRENT_ROOT=/opt/artgents/current
readonly COMPOSE_FILE="${CURRENT_ROOT}/deploy/production/compose.yml"
readonly ENV_FILE=/etc/artgents/production.env
readonly BACKUP_BIN=/opt/artgents/bin/backup-postgres
readonly FINGERPRINT_HELPER=/opt/artgents/bin/migration-bundle-fingerprint.py
readonly BACKUP_RECEIPT_ROOT=/var/lib/artgents/backups/receipts
readonly DEPLOY_STATE_DIR=/var/lib/artgents/deploy
readonly LOCK_FILE=/var/lock/artgents-production-deploy.lock
readonly CURRENT_RECEIPT="${DEPLOY_STATE_DIR}/current.json"
readonly PREVIOUS_RECEIPT="${DEPLOY_STATE_DIR}/previous.json"

SOURCE_SHA="${1:-}"
IMAGE_DIGEST="${2:-}"

RECEIPT_TMP=""

MIGRATION_BUNDLE_SHA256=""

log_safe() {
  printf '%s\n' "$*" >&2
}

fail() {
  log_safe "deploy failed: $*"
  exit 1
}

cleanup_receipt_tmp() {
  if [ -n "$RECEIPT_TMP" ] && [ -f "$RECEIPT_TMP" ]; then
    rm -f "$RECEIPT_TMP"
  fi
}

on_err() {
  cleanup_receipt_tmp
  log_safe "deploy aborted (fail-closed, rollback not performed)"
}
trap on_err ERR

if [ "$(id -u)" -ne 0 ]; then
  fail "must run as root"
fi

if [ "$#" -ne 2 ]; then
  fail "expected exactly two arguments"
fi

if ! [[ "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  fail "invalid source_sha"
fi

if ! [[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  fail "invalid image digest"
fi

IMMUTABLE_REF="${IMAGE_REPO}@${IMAGE_DIGEST}"

require_file() {
  local path="$1"
  local mode="$2"
  if [ ! -e "$path" ]; then
    fail "missing required path: $path"
  fi
  case "$mode" in
    readable)
      [ -r "$path" ] || fail "not readable: $path"
      ;;
    executable)
      [ -x "$path" ] || fail "not executable: $path"
      ;;
    dir)
      [ -d "$path" ] || fail "not a directory: $path"
      ;;
  esac
}

check_env_permissions() {
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

compose() {
  env BOT_IMAGE="$IMMUTABLE_REF" docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

compose_public() {
  env BOT_IMAGE="$IMMUTABLE_REF" docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" --profile public "$@"
}

assert_internal_service_name() {
  case "$1" in
    caddy | bot | admin | postgres) ;;
    *) fail "internal service name required" ;;
  esac
}

compose_ps_all_output() {
  local use_public="$1"
  local service="$2"
  local output=""
  assert_internal_service_name "$service"
  if [ "$use_public" = "1" ]; then
    if ! output=$(compose_public ps --all -q "$service"); then
      fail "failed to inspect ${service} containers"
    fi
  else
    if ! output=$(compose ps --all -q "$service"); then
      fail "failed to inspect ${service} containers"
    fi
  fi
  printf '%s' "$output"
}

compose_ps_running_output() {
  local use_public="$1"
  local service="$2"
  local output=""
  assert_internal_service_name "$service"
  if [ "$use_public" = "1" ]; then
    if ! output=$(compose_public ps -q "$service"); then
      fail "failed to inspect running ${service} containers"
    fi
  else
    if ! output=$(compose ps -q "$service"); then
      fail "failed to inspect running ${service} containers"
    fi
  fi
  printf '%s' "$output"
}

container_ids_from_output() {
  local output="$1"
  local -n _out_arr="$2"
  _out_arr=()
  local line
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    _out_arr+=("$line")
  done <<< "$output"
}

wait_container_not_running_or_restarting() {
  local cid="$1"
  local label="$2"
  local timeout_sec="${3:-60}"
  local elapsed=0
  local status=""
  while [ "$elapsed" -lt "$timeout_sec" ]; do
    if ! status=$(docker inspect --format '{{.State.Status}}' "$cid"); then
      fail "failed to inspect ${label} container after stop"
    fi
    if [ "$status" != "running" ] && [ "$status" != "restarting" ]; then
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  fail "${label} still running or restarting after stop"
}

verify_service_not_running_or_restarting() {
  local use_public="$1"
  local service="$2"
  local -a ids=()
  local output
  output=$(compose_ps_all_output "$use_public" "$service")
  container_ids_from_output "$output" ids
  if [ "${#ids[@]}" -eq 0 ]; then
    return 0
  fi
  if [ "${#ids[@]}" -gt 1 ]; then
    fail "expected at most one ${service} container during maintenance verify, found ${#ids[@]}"
  fi
  local status=""
  if ! status=$(docker inspect --format '{{.State.Status}}' "${ids[0]}"); then
    fail "failed to inspect ${service} container during maintenance verify"
  fi
  if [ "$status" = "running" ] || [ "$status" = "restarting" ]; then
    fail "${service} still running or restarting before migration"
  fi
}

stop_service_if_present() {
  local use_public="$1"
  local service="$2"
  local -a ids=()
  local output
  output=$(compose_ps_all_output "$use_public" "$service")
  container_ids_from_output "$output" ids
  if [ "${#ids[@]}" -eq 0 ]; then
    return 0
  fi
  if [ "${#ids[@]}" -gt 1 ]; then
    fail "expected at most one ${service} container, found ${#ids[@]}"
  fi
  local cid="${ids[0]}"
  local status=""
  if ! status=$(docker inspect --format '{{.State.Status}}' "$cid"); then
    fail "failed to inspect ${service} container"
  fi
  case "$status" in
    running | restarting)
      if [ "$use_public" = "1" ]; then
        if ! compose_public stop "$service"; then
          fail "failed to stop ${service}"
        fi
      else
        if ! compose stop "$service"; then
          fail "failed to stop ${service}"
        fi
      fi
      wait_container_not_running_or_restarting "$cid" "$service" 60
      ;;
    exited | created | dead)
      return 0
      ;;
    paused | removing)
      fail "${service} container in unsafe state for maintenance: ${status}"
      ;;
    *)
      fail "unexpected ${service} container status: ${status}"
      ;;
  esac
}

get_single_running_container_id() {
  local use_public="$1"
  local service="$2"
  local -a ids=()
  local output
  output=$(compose_ps_running_output "$use_public" "$service")
  container_ids_from_output "$output" ids
  if [ "${#ids[@]}" -ne 1 ]; then
    fail "expected exactly one running container for ${service}, found ${#ids[@]}"
  fi
  printf '%s' "${ids[0]}"
}

wait_service_healthy() {
  local service="$1"
  local timeout_sec="${2:-300}"
  local elapsed=0
  while [ "$elapsed" -lt "$timeout_sec" ]; do
    local cid
    cid=$(get_single_running_container_id 0 "$service")
    local status health
    if ! status=$(docker inspect --format '{{.State.Status}}' "$cid"); then
      fail "failed to inspect ${service} container"
    fi
    if ! health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid"); then
      fail "failed to inspect ${service} health"
    fi
    if [ "$status" = "running" ] && [ "$health" = "healthy" ]; then
      return 0
    fi
    if [ "$health" = "starting" ]; then
      sleep 5
      elapsed=$((elapsed + 5))
      continue
    fi
    if [ "$health" = "none" ] || [ "$health" = "unhealthy" ] || [ "$status" = "exited" ] || [ "$status" = "dead" ]; then
      fail "service ${service} not healthy (status=${status}, health=${health})"
    fi
    sleep 5
    elapsed=$((elapsed + 5))
  done
  fail "timeout waiting for healthy: ${service}"
}

validate_backup_receipt_path() {
  local candidate="$1"
  local canonical root_real owner perms
  canonical=$(realpath -e -- "$candidate") || fail "backup receipt path invalid"
  root_real=$(realpath -e -- "$BACKUP_RECEIPT_ROOT") || fail "backup receipt root missing"
  if [ "$canonical" = "$root_real" ]; then
    fail "backup receipt must not be the root directory"
  fi
  case "$canonical" in
    "${root_real}"/*) ;;
    *) fail "backup receipt outside allowed root" ;;
  esac
  if [ ! -f "$canonical" ]; then
    fail "backup receipt must be a regular file"
  fi
  if [ -L "$candidate" ]; then
    fail "backup receipt must not be a symlink"
  fi
  owner=$(stat -c '%u:%g' "$canonical")
  if [ "$owner" != "0:0" ]; then
    fail "backup receipt must be root-owned"
  fi
  perms=$(stat -c '%a' "$canonical")
  if [ "$((10#${perms} & 022))" -ne 0 ]; then
    fail "backup receipt must not be group/world writable"
  fi
  printf '%s' "$canonical"
}

validate_current_receipt_metadata() {
  if [ -L "$CURRENT_RECEIPT" ]; then
    fail "current deploy receipt must not be a symlink"
  fi
  if [ ! -e "$CURRENT_RECEIPT" ]; then
    return 0
  fi
  if [ ! -f "$CURRENT_RECEIPT" ]; then
    fail "current deploy receipt must be a regular file"
  fi
  local state_dir receipt_dir owner perms
  state_dir=$(realpath -e -- "$DEPLOY_STATE_DIR") || fail "deploy state directory invalid"
  receipt_dir=$(realpath -e -- "$(dirname "$CURRENT_RECEIPT")") || fail "current receipt directory invalid"
  if [ "$receipt_dir" != "$state_dir" ]; then
    fail "current deploy receipt must be located in deploy state directory"
  fi
  owner=$(stat -c '%u:%g' "$CURRENT_RECEIPT")
  if [ "$owner" != "0:0" ]; then
    fail "current deploy receipt must be root-owned"
  fi
  perms=$(stat -c '%a' "$CURRENT_RECEIPT")
  if [ "$((10#${perms} & 022))" -ne 0 ]; then
    fail "current deploy receipt must not be group/world writable"
  fi
}

read_previous_digest_or_empty() {
  if [ ! -f "$CURRENT_RECEIPT" ]; then
    PREVIOUS_DIGEST=""
    return 0
  fi
  PREVIOUS_DIGEST=$(
    CURRENT_RECEIPT_PATH="$CURRENT_RECEIPT" IMAGE_REPO="$IMAGE_REPO" python3 <<'PY'
import json
import os
import re
import sys
from pathlib import Path

path = Path(os.environ["CURRENT_RECEIPT_PATH"])
repo = os.environ["IMAGE_REPO"]
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError, UnicodeError):
    sys.exit(1)
if data.get("schema_version") != 2:
    sys.exit(1)
if data.get("status") != "success":
    sys.exit(1)
operation = data.get("operation")
if operation not in ("deploy", "rollback"):
    sys.exit(1)
digest = data.get("image_digest")
if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
    sys.exit(1)
imm = data.get("immutable_reference")
if not isinstance(imm, str) or imm != f"{repo}@{digest}":
    sys.exit(1)
fp = data.get("migration_bundle_sha256")
if not isinstance(fp, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", fp):
    sys.exit(1)
print(digest)
PY
  ) || fail "invalid current deploy receipt"
}

verify_pulled_image_digest() {
  local expected_ref="${IMAGE_REPO}@${IMAGE_DIGEST}"
  local output found=0 line
  if ! output=$(docker image inspect "$IMMUTABLE_REF" --format '{{range .RepoDigests}}{{println .}}{{end}}'); then
    fail "docker image inspect failed for pulled image"
  fi
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    if [ "$line" = "$expected_ref" ]; then
      found=1
      break
    fi
  done <<< "$output"
  if [ "$found" -ne 1 ]; then
    fail "pulled image missing expected repo digest membership"
  fi
}

extract_migration_bundle_fingerprint_from_image() (
  local image_ref="$1"
  local tmpdir="" cid="" fingerprint=""
  tmpdir=$(mktemp -d)
  cleanup_extract() {
    if [ -n "$cid" ]; then
      docker rm -f "$cid" >/dev/null 2>&1
    fi
    rm -rf "$tmpdir"
  }
  trap cleanup_extract EXIT
  require_file "$FINGERPRINT_HELPER" executable
  if ! cid=$(docker create "$image_ref"); then
    fail "docker create failed for migration bundle extraction"
  fi
  if ! docker cp "${cid}:/app/deploy/postgres/migrations.manifest" "${tmpdir}/migrations.manifest"; then
    fail "failed to copy migrations manifest from image"
  fi
  if ! docker cp "${cid}:/app/migrations/postgresql" "${tmpdir}/postgresql"; then
    fail "failed to copy migrations directory from image"
  fi
  if ! fingerprint=$(python3 "$FINGERPRINT_HELPER" --manifest "${tmpdir}/migrations.manifest" --migrations-dir "${tmpdir}/postgresql"); then
    fail "failed to compute migration bundle fingerprint"
  fi
  if ! [[ "$fingerprint" =~ ^sha256:[0-9a-f]{64}$ ]]; then
    fail "invalid migration bundle fingerprint format"
  fi
  printf '%s' "$fingerprint"
)

verify_caddy_running() {
  local cid status
  cid=$(get_single_running_container_id 1 caddy)
  if ! status=$(docker inspect --format '{{.State.Status}}' "$cid"); then
    fail "failed to inspect caddy container"
  fi
  if [ "$status" != "running" ]; then
    fail "caddy not running"
  fi
}

run_application_maintenance_stop() {
  stop_service_if_present 1 caddy
  verify_service_not_running_or_restarting 1 caddy
  stop_service_if_present 0 bot
  stop_service_if_present 0 admin
  verify_service_not_running_or_restarting 0 bot
  verify_service_not_running_or_restarting 0 admin
}

write_deploy_receipt() {
  RECEIPT_TMP=$(mktemp "${DEPLOY_STATE_DIR}/.receipt.XXXXXX")
  chmod 600 "$RECEIPT_TMP"
  DEPLOY_SOURCE_SHA="$SOURCE_SHA" \
  DEPLOY_IMAGE_DIGEST="$IMAGE_DIGEST" \
  DEPLOY_IMMUTABLE_REF="$IMMUTABLE_REF" \
  DEPLOY_BACKUP_RECEIPT="$BACKUP_RECEIPT_CANONICAL" \
  DEPLOY_STARTED_AT="$STARTED_AT" \
  DEPLOY_COMPLETED_AT="$COMPLETED_AT" \
  DEPLOY_PREVIOUS_DIGEST="$PREVIOUS_DIGEST" \
  DEPLOY_MIGRATION_BUNDLE_SHA256="$MIGRATION_BUNDLE_SHA256" \
  python3 <<'PY' >"$RECEIPT_TMP"
import json
import os
import re
import sys

def req(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        sys.exit(1)
    return val

source_sha = req("DEPLOY_SOURCE_SHA")
digest = req("DEPLOY_IMAGE_DIGEST")
repo = "ghcr.io/dhmnzr79/artgents-bot"
if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
    sys.exit(1)
if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
    sys.exit(1)
imm = req("DEPLOY_IMMUTABLE_REF")
if imm != f"{repo}@{digest}":
    sys.exit(1)
backup = req("DEPLOY_BACKUP_RECEIPT")
if not backup.startswith("/var/lib/artgents/backups/receipts/"):
    sys.exit(1)
bundle = req("DEPLOY_MIGRATION_BUNDLE_SHA256")
if not re.fullmatch(r"sha256:[0-9a-f]{64}", bundle):
    sys.exit(1)
prev = os.environ.get("DEPLOY_PREVIOUS_DIGEST", "")
previous_digest = None
if prev:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", prev):
        sys.exit(1)
    previous_digest = prev
payload = {
    "schema_version": 2,
    "operation": "deploy",
    "status": "success",
    "source_sha": source_sha,
    "image_digest": digest,
    "immutable_reference": imm,
    "migration_bundle_sha256": bundle,
    "backup_receipt": backup,
    "started_at": req("DEPLOY_STARTED_AT"),
    "completed_at": req("DEPLOY_COMPLETED_AT"),
    "previous_digest": previous_digest,
    "health": {
        "bot": "healthy",
        "admin": "healthy",
        "readiness": "passed",
        "caddy": "running",
    },
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  fail "another production deploy is in progress"
fi

require_file "$ENV_FILE" readable
require_file "$COMPOSE_FILE" readable
require_file "$CURRENT_ROOT" dir
require_file "$BACKUP_BIN" executable
require_file "$FINGERPRINT_HELPER" executable
check_env_permissions

if ! command -v docker >/dev/null 2>&1; then
  fail "docker not installed"
fi
if ! docker compose version >/dev/null 2>&1; then
  fail "docker compose v2 not available"
fi

mkdir -p "$DEPLOY_STATE_DIR"
chmod 700 "$DEPLOY_STATE_DIR"

validate_current_receipt_metadata
read_previous_digest_or_empty

STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

docker pull "$IMMUTABLE_REF"
verify_pulled_image_digest
MIGRATION_BUNDLE_SHA256=$(extract_migration_bundle_fingerprint_from_image "$IMMUTABLE_REF")

compose up -d postgres
wait_service_healthy postgres 300

if ! BACKUP_OUTPUT=$("$BACKUP_BIN" --reason pre-deploy --source-sha "$SOURCE_SHA" 2>&1); then
  fail "backup gate failed (G7 utility required)"
fi

BACKUP_RECEIPT_RAW=$(printf '%s\n' "$BACKUP_OUTPUT" | tail -n 1)
BACKUP_RECEIPT_CANONICAL=$(validate_backup_receipt_path "$BACKUP_RECEIPT_RAW")

run_application_maintenance_stop

if ! compose run --rm migrate; then
  fail "migration failed"
fi

if ! compose up -d --force-recreate --no-deps bot admin; then
  fail "bot/admin start failed"
fi

wait_service_healthy bot 300
wait_service_healthy admin 300

if ! compose exec -T bot python3 -c "
import sys, urllib.request
try:
    r = urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=15)
except Exception:
    sys.exit(1)
sys.exit(0 if r.status == 200 else 1)
"; then
  fail "internal readiness check failed"
fi

if ! compose_public up -d --no-deps caddy; then
  fail "caddy start failed"
fi

verify_caddy_running

COMPLETED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

write_deploy_receipt

if [ -f "$CURRENT_RECEIPT" ]; then
  cp -a "$CURRENT_RECEIPT" "${DEPLOY_STATE_DIR}/previous.json.tmp"
  mv -f "${DEPLOY_STATE_DIR}/previous.json.tmp" "$PREVIOUS_RECEIPT"
fi
mv -f "$RECEIPT_TMP" "$CURRENT_RECEIPT"
chmod 600 "$CURRENT_RECEIPT"
RECEIPT_TMP=""

printf 'deploy success source_sha=%s digest=%s completed_at=%s receipt=%s\n' \
  "$SOURCE_SHA" "$IMAGE_DIGEST" "$COMPLETED_AT" "$CURRENT_RECEIPT"
