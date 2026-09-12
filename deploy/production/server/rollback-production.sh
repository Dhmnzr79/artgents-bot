#!/usr/bin/env bash
# Root-owned production rollback script (install to /opt/artgents/bin/rollback-production).
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

EXPECTED_CURRENT_SHA="${1:-}"

RECEIPT_TMP=""
TARGET_IMMUTABLE_REF=""
CURRENT_SOURCE_SHA=""
CURRENT_DIGEST=""
CURRENT_FINGERPRINT=""
TARGET_SOURCE_SHA=""
TARGET_DIGEST=""
TARGET_FINGERPRINT=""

log_safe() { printf '%s\n' "$*" >&2; }
fail() { log_safe "rollback failed: $*"; exit 1; }

require_file() {
  local path="$1" mode="$2"
  if [ -L "$path" ]; then fail "symlink not allowed: $path"; fi
  case "$mode" in
    readable)
      [ -f "$path" ] && [ -r "$path" ] || fail "not a readable file: $path"
      ;;
    executable)
      [ -f "$path" ] && [ -x "$path" ] || fail "not executable: $path"
      ;;
    dir)
      [ -d "$path" ] || fail "not a directory: $path"
      ;;
    *)
      fail "invalid require_file mode"
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

cleanup_receipt_tmp() {
  if [ -n "$RECEIPT_TMP" ] && [ -f "$RECEIPT_TMP" ]; then
    rm -f "$RECEIPT_TMP"
  fi
}

on_err() {
  cleanup_receipt_tmp
  log_safe "rollback aborted (fail-closed, no automatic roll-forward)"
}
trap on_err ERR

if [ "$(id -u)" -ne 0 ]; then fail "must run as root"; fi
if [ "$#" -ne 1 ]; then fail "expected exactly one argument"; fi
if ! [[ "$EXPECTED_CURRENT_SHA" =~ ^[0-9a-f]{40}$ ]]; then fail "invalid expected_current_sha"; fi

compose() {
  env BOT_IMAGE="$TARGET_IMMUTABLE_REF" docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}
compose_public() {
  env BOT_IMAGE="$TARGET_IMMUTABLE_REF" docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" --profile public "$@"
}

assert_internal_service_name() {
  case "$1" in
    caddy | bot | admin | postgres) ;;
    *) fail "internal service name required" ;;
  esac
}

compose_ps_all_output() {
  local use_public="$1" service="$2" output=""
  assert_internal_service_name "$service"
  if [ "$use_public" = "1" ]; then
    if ! output=$(compose_public ps --all -q "$service"); then fail "failed to inspect ${service} containers"; fi
  else
    if ! output=$(compose ps --all -q "$service"); then fail "failed to inspect ${service} containers"; fi
  fi
  printf '%s' "$output"
}

compose_ps_running_output() {
  local use_public="$1" service="$2" output=""
  assert_internal_service_name "$service"
  if [ "$use_public" = "1" ]; then
    if ! output=$(compose_public ps -q "$service"); then fail "failed to inspect running ${service} containers"; fi
  else
    if ! output=$(compose ps -q "$service"); then fail "failed to inspect running ${service} containers"; fi
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
  local cid="$1" label="$2" timeout_sec="${3:-60}" elapsed=0 status=""
  while [ "$elapsed" -lt "$timeout_sec" ]; do
    if ! status=$(docker inspect --format '{{.State.Status}}' "$cid"); then
      fail "failed to inspect ${label} container after stop"
    fi
    if [ "$status" != "running" ] && [ "$status" != "restarting" ]; then return 0; fi
    sleep 2; elapsed=$((elapsed + 2))
  done
  fail "${label} still running or restarting after stop"
}

verify_service_not_running_or_restarting() {
  local use_public="$1" service="$2"
  local -a ids=() output status=""
  output=$(compose_ps_all_output "$use_public" "$service")
  container_ids_from_output "$output" ids
  if [ "${#ids[@]}" -eq 0 ]; then return 0; fi
  if [ "${#ids[@]}" -gt 1 ]; then fail "expected at most one ${service} container during maintenance verify"; fi
  if ! status=$(docker inspect --format '{{.State.Status}}' "${ids[0]}"); then
    fail "failed to inspect ${service} container during maintenance verify"
  fi
  if [ "$status" = "running" ] || [ "$status" = "restarting" ]; then
    fail "${service} still running or restarting before rollback restart"
  fi
}

stop_service_if_present() {
  local use_public="$1" service="$2"
  local -a ids=() output cid="" status=""
  output=$(compose_ps_all_output "$use_public" "$service")
  container_ids_from_output "$output" ids
  if [ "${#ids[@]}" -eq 0 ]; then return 0; fi
  if [ "${#ids[@]}" -gt 1 ]; then fail "expected at most one ${service} container"; fi
  cid="${ids[0]}"
  if ! status=$(docker inspect --format '{{.State.Status}}' "$cid"); then fail "failed to inspect ${service} container"; fi
  case "$status" in
    running | restarting)
      if [ "$use_public" = "1" ]; then
        if ! compose_public stop "$service"; then fail "failed to stop ${service}"; fi
      else
        if ! compose stop "$service"; then fail "failed to stop ${service}"; fi
      fi
      wait_container_not_running_or_restarting "$cid" "$service" 60
      ;;
    exited | created | dead) return 0 ;;
    paused | removing) fail "${service} container in unsafe state for maintenance: ${status}" ;;
    *) fail "unexpected ${service} container status: ${status}" ;;
  esac
}

get_single_running_container_id() {
  local use_public="$1" service="$2"
  local -a ids=() output=""
  output=$(compose_ps_running_output "$use_public" "$service")
  container_ids_from_output "$output" ids
  if [ "${#ids[@]}" -ne 1 ]; then fail "expected exactly one running container for ${service}"; fi
  printf '%s' "${ids[0]}"
}

wait_service_healthy() {
  local service="$1" timeout_sec="${2:-300}" elapsed=0
  while [ "$elapsed" -lt "$timeout_sec" ]; do
    local cid status health
    cid=$(get_single_running_container_id 0 "$service")
    if ! status=$(docker inspect --format '{{.State.Status}}' "$cid"); then fail "failed to inspect ${service}"; fi
    if ! health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid"); then
      fail "failed to inspect ${service} health"
    fi
    if [ "$status" = "running" ] && [ "$health" = "healthy" ]; then return 0; fi
    if [ "$health" = "starting" ]; then sleep 5; elapsed=$((elapsed + 5)); continue; fi
    if [ "$health" = "none" ] || [ "$health" = "unhealthy" ] || [ "$status" = "exited" ] || [ "$status" = "dead" ]; then
      fail "service ${service} not healthy (status=${status}, health=${health})"
    fi
    sleep 5; elapsed=$((elapsed + 5))
  done
  fail "timeout waiting for healthy: ${service}"
}

validate_receipt_path_metadata() {
  local path="$1"
  if [ -L "$path" ]; then fail "deploy receipt must not be a symlink"; fi
  if [ ! -f "$path" ]; then fail "deploy receipt missing"; fi
  local state_dir receipt_dir owner perms
  state_dir=$(realpath -e -- "$DEPLOY_STATE_DIR") || fail "deploy state directory invalid"
  receipt_dir=$(realpath -e -- "$(dirname "$path")") || fail "receipt directory invalid"
  if [ "$receipt_dir" != "$state_dir" ]; then fail "receipt must be located in deploy state directory"; fi
  owner=$(stat -c '%u:%g' "$path")
  if [ "$owner" != "0:0" ]; then fail "receipt must be root-owned"; fi
  perms=$(stat -c '%a' "$path")
  if [ "$((10#${perms} & 022))" -ne 0 ]; then fail "receipt must not be group/world writable"; fi
}

load_receipt_fields() {
  local path="$1"
  local prefix="$2"
  local parsed line key value
  local parsed_source_sha="" parsed_image_digest="" parsed_migration_fingerprint=""
  if ! parsed=$(
    RECEIPT_PATH="$path" IMAGE_REPO="$IMAGE_REPO" python3 <<'PY'
import json, os, re, sys
from pathlib import Path
path = Path(os.environ["RECEIPT_PATH"])
repo = os.environ["IMAGE_REPO"]
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError, UnicodeError):
    sys.exit(1)
if data.get("schema_version") != 2:
    sys.exit(1)
if data.get("status") != "success":
    sys.exit(1)
op = data.get("operation")
if op not in ("deploy", "rollback"):
    sys.exit(1)
sha = data.get("source_sha")
digest = data.get("image_digest")
imm = data.get("immutable_reference")
fp = data.get("migration_bundle_sha256")
if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
    sys.exit(1)
if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
    sys.exit(1)
if not isinstance(imm, str) or imm != f"{repo}@{digest}":
    sys.exit(1)
if not isinstance(fp, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", fp):
    sys.exit(1)
print(f"SOURCE_SHA={sha}")
print(f"IMAGE_DIGEST={digest}")
print(f"MIGRATION_FINGERPRINT={fp}")
PY
  ); then
    fail "invalid deploy receipt"
  fi
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    key="${line%%=*}"
    value="${line#*=}"
    case "$key" in
      SOURCE_SHA) parsed_source_sha="$value" ;;
      IMAGE_DIGEST) parsed_image_digest="$value" ;;
      MIGRATION_FINGERPRINT) parsed_migration_fingerprint="$value" ;;
      *) fail "invalid deploy receipt" ;;
    esac
  done <<< "$parsed"
  if [ -z "$parsed_source_sha" ] || [ -z "$parsed_image_digest" ] || [ -z "$parsed_migration_fingerprint" ]; then
    fail "invalid deploy receipt"
  fi
  if ! [[ "$parsed_source_sha" =~ ^[0-9a-f]{40}$ ]]; then fail "invalid deploy receipt"; fi
  if ! [[ "$parsed_image_digest" =~ ^sha256:[0-9a-f]{64}$ ]]; then fail "invalid deploy receipt"; fi
  if ! [[ "$parsed_migration_fingerprint" =~ ^sha256:[0-9a-f]{64}$ ]]; then fail "invalid deploy receipt"; fi
  if [ "$prefix" = "CURRENT" ]; then
    CURRENT_SOURCE_SHA="$parsed_source_sha"
    CURRENT_DIGEST="$parsed_image_digest"
    CURRENT_FINGERPRINT="$parsed_migration_fingerprint"
  elif [ "$prefix" = "TARGET" ]; then
    TARGET_SOURCE_SHA="$parsed_source_sha"
    TARGET_DIGEST="$parsed_image_digest"
    TARGET_FINGERPRINT="$parsed_migration_fingerprint"
  else
    fail "invalid receipt prefix"
  fi
}

verify_image_digest_membership() {
  local image_ref="$1" digest="$2"
  local expected="${IMAGE_REPO}@${digest}" output found=0 line
  if ! output=$(docker image inspect "$image_ref" --format '{{range .RepoDigests}}{{println .}}{{end}}'); then
    fail "docker image inspect failed for target image"
  fi
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    if [ "$line" = "$expected" ]; then found=1; break; fi
  done <<< "$output"
  if [ "$found" -ne 1 ]; then fail "target image missing expected repo digest membership"; fi
}

extract_migration_bundle_fingerprint_from_image() (
  local image_ref="$1" tmpdir="" cid="" fingerprint=""
  tmpdir=$(mktemp -d)
  cleanup_extract() {
    if [ -n "$cid" ]; then docker rm -f "$cid" >/dev/null 2>&1; fi
    rm -rf "$tmpdir"
  }
  trap cleanup_extract EXIT
  if [ ! -x "$FINGERPRINT_HELPER" ]; then fail "migration fingerprint helper missing"; fi
  if ! cid=$(docker create "$image_ref"); then fail "docker create failed for migration bundle extraction"; fi
  if ! docker cp "${cid}:/app/deploy/postgres/migrations.manifest" "${tmpdir}/migrations.manifest"; then
    fail "failed to copy migrations manifest from image"
  fi
  if ! docker cp "${cid}:/app/migrations/postgresql" "${tmpdir}/postgresql"; then
    fail "failed to copy migrations directory from image"
  fi
  if ! fingerprint=$(python3 "$FINGERPRINT_HELPER" --manifest "${tmpdir}/migrations.manifest" --migrations-dir "${tmpdir}/postgresql"); then
    fail "failed to compute migration bundle fingerprint"
  fi
  if ! [[ "$fingerprint" =~ ^sha256:[0-9a-f]{64}$ ]]; then fail "invalid migration bundle fingerprint format"; fi
  printf '%s' "$fingerprint"
)

validate_backup_receipt_path() {
  local candidate="$1" canonical root_real owner perms
  canonical=$(realpath -e -- "$candidate") || fail "backup receipt path invalid"
  root_real=$(realpath -e -- "$BACKUP_RECEIPT_ROOT") || fail "backup receipt root missing"
  if [ "$canonical" = "$root_real" ]; then fail "backup receipt must not be the root directory"; fi
  case "$canonical" in "${root_real}"/*) ;; *) fail "backup receipt outside allowed root" ;; esac
  if [ ! -f "$canonical" ]; then fail "backup receipt must be a regular file"; fi
  if [ -L "$candidate" ]; then fail "backup receipt must not be a symlink"; fi
  owner=$(stat -c '%u:%g' "$canonical")
  if [ "$owner" != "0:0" ]; then fail "backup receipt must be root-owned"; fi
  perms=$(stat -c '%a' "$canonical")
  if [ "$((10#${perms} & 022))" -ne 0 ]; then fail "backup receipt must not be group/world writable"; fi
  printf '%s' "$canonical"
}

run_application_maintenance_stop() {
  stop_service_if_present 1 caddy
  verify_service_not_running_or_restarting 1 caddy
  stop_service_if_present 0 bot
  stop_service_if_present 0 admin
  verify_service_not_running_or_restarting 0 bot
  verify_service_not_running_or_restarting 0 admin
}

verify_caddy_running() {
  local cid status
  cid=$(get_single_running_container_id 1 caddy)
  if ! status=$(docker inspect --format '{{.State.Status}}' "$cid"); then fail "failed to inspect caddy container"; fi
  if [ "$status" != "running" ]; then fail "caddy not running"; fi
}

write_rollback_receipt() {
  RECEIPT_TMP=$(mktemp "${DEPLOY_STATE_DIR}/.receipt.XXXXXX")
  chmod 600 "$RECEIPT_TMP"
  RB_TARGET_SHA="$TARGET_SOURCE_SHA" RB_TARGET_DIGEST="$TARGET_DIGEST" \
  RB_TARGET_FINGERPRINT="$TARGET_FINGERPRINT" RB_FROM_SHA="$CURRENT_SOURCE_SHA" \
  RB_FROM_DIGEST="$CURRENT_DIGEST" RB_BACKUP_RECEIPT="$BACKUP_RECEIPT_CANONICAL" \
  RB_STARTED_AT="$STARTED_AT" RB_COMPLETED_AT="$COMPLETED_AT" \
  RB_PREVIOUS_DIGEST="$CURRENT_DIGEST" \
  python3 <<'PY' >"$RECEIPT_TMP"
import json, os, re, sys

def req(n):
    v = os.environ.get(n, "")
    if not v: sys.exit(1)
    return v

repo = "ghcr.io/dhmnzr79/artgents-bot"
target_sha = req("RB_TARGET_SHA")
target_digest = req("RB_TARGET_DIGEST")
target_fp = req("RB_TARGET_FINGERPRINT")
from_sha = req("RB_FROM_SHA")
from_digest = req("RB_FROM_DIGEST")
for val in (target_sha, from_sha):
    if not re.fullmatch(r"[0-9a-f]{40}", val): sys.exit(1)
for val in (target_digest, from_digest, target_fp):
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", val): sys.exit(1)
imm = f"{repo}@{target_digest}"
backup = req("RB_BACKUP_RECEIPT")
if not backup.startswith("/var/lib/artgents/backups/receipts/"): sys.exit(1)
payload = {
    "schema_version": 2,
    "operation": "rollback",
    "status": "success",
    "source_sha": target_sha,
    "image_digest": target_digest,
    "immutable_reference": imm,
    "migration_bundle_sha256": target_fp,
    "rollback_from_source_sha": from_sha,
    "rollback_from_digest": from_digest,
    "backup_receipt": backup,
    "started_at": req("RB_STARTED_AT"),
    "completed_at": req("RB_COMPLETED_AT"),
    "previous_digest": from_digest,
    "health": {"bot": "healthy", "admin": "healthy", "readiness": "passed", "caddy": "running"},
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

exec 9>"$LOCK_FILE"
if ! flock -n 9; then fail "another production deploy or rollback is in progress"; fi

require_file "$ENV_FILE" readable
check_env_permissions
require_file "$COMPOSE_FILE" readable
require_file "$BACKUP_BIN" executable
require_file "$FINGERPRINT_HELPER" executable
require_file "$CURRENT_ROOT" dir

if ! command -v docker >/dev/null 2>&1; then fail "docker not installed"; fi
if ! docker compose version >/dev/null 2>&1; then fail "docker compose v2 not available"; fi

mkdir -p "$DEPLOY_STATE_DIR"; chmod 700 "$DEPLOY_STATE_DIR"

if [ ! -f "$CURRENT_RECEIPT" ]; then fail "rollback unavailable: current receipt missing"; fi
if [ ! -f "$PREVIOUS_RECEIPT" ]; then fail "rollback unavailable: no previous successful deployment"; fi

validate_receipt_path_metadata "$CURRENT_RECEIPT"
validate_receipt_path_metadata "$PREVIOUS_RECEIPT"
load_receipt_fields "$CURRENT_RECEIPT" CURRENT
load_receipt_fields "$PREVIOUS_RECEIPT" TARGET

if [ "$CURRENT_SOURCE_SHA" != "$EXPECTED_CURRENT_SHA" ]; then
  fail "expected current SHA does not match production receipt"
fi
if [ "$TARGET_DIGEST" = "$CURRENT_DIGEST" ]; then
  fail "rollback unavailable: target matches current digest"
fi
if [ "$TARGET_SOURCE_SHA" = "$CURRENT_SOURCE_SHA" ]; then
  fail "rollback unavailable: target matches current source SHA"
fi

TARGET_IMMUTABLE_REF="${IMAGE_REPO}@${TARGET_DIGEST}"
STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

docker pull "$TARGET_IMMUTABLE_REF"
verify_image_digest_membership "$TARGET_IMMUTABLE_REF" "$TARGET_DIGEST"

RECOMPUTED_FINGERPRINT=$(extract_migration_bundle_fingerprint_from_image "$TARGET_IMMUTABLE_REF")
if [ "$RECOMPUTED_FINGERPRINT" != "$TARGET_FINGERPRINT" ] || \
   [ "$RECOMPUTED_FINGERPRINT" != "$CURRENT_FINGERPRINT" ] || \
   [ "$CURRENT_FINGERPRINT" != "$TARGET_FINGERPRINT" ]; then
  fail "automatic rollback blocked: migration bundle differs"
fi

wait_service_healthy postgres 300

if ! BACKUP_OUTPUT=$("$BACKUP_BIN" --reason pre-rollback --source-sha "$CURRENT_SOURCE_SHA" 2>&1); then
  fail "backup gate failed (G7 utility required)"
fi
BACKUP_RECEIPT_RAW=$(printf '%s\n' "$BACKUP_OUTPUT" | tail -n 1)
BACKUP_RECEIPT_CANONICAL=$(validate_backup_receipt_path "$BACKUP_RECEIPT_RAW")

run_application_maintenance_stop

if ! compose up -d --force-recreate --no-deps bot admin; then
  fail "bot/admin rollback start failed"
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

if ! compose_public up -d --no-deps caddy; then fail "caddy start failed"; fi
verify_caddy_running

COMPLETED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
write_rollback_receipt

cp -a "$CURRENT_RECEIPT" "${DEPLOY_STATE_DIR}/previous.json.tmp"
mv -f "${DEPLOY_STATE_DIR}/previous.json.tmp" "$PREVIOUS_RECEIPT"
mv -f "$RECEIPT_TMP" "$CURRENT_RECEIPT"
chmod 600 "$CURRENT_RECEIPT"
RECEIPT_TMP=""

printf 'rollback success target_sha=%s digest=%s receipt=%s\n' \
  "$TARGET_SOURCE_SHA" "$TARGET_DIGEST" "$CURRENT_RECEIPT"
