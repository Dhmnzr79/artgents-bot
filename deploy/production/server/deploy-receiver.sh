#!/usr/bin/env bash
# Forced-command SSH receiver (runs as deploy user, not root). Install per server README.
set -Eeuo pipefail
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

readonly DEPLOY_SCRIPT=/opt/artgents/bin/deploy-production
readonly ROLLBACK_SCRIPT=/opt/artgents/bin/rollback-production

if [ "$(id -u)" -eq 0 ]; then
  echo "deploy-receiver must not run as root" >&2
  exit 1
fi

if [ -z "${SSH_ORIGINAL_COMMAND:-}" ]; then
  echo "missing SSH_ORIGINAL_COMMAND" >&2
  exit 1
fi

ORIGINAL="$SSH_ORIGINAL_COMMAND"

if [[ "$ORIGINAL" == *$'\n'* || "$ORIGINAL" == *$'\r'* || "$ORIGINAL" == *$'\t'* ]]; then
  echo "command contains forbidden whitespace" >&2
  exit 1
fi

if [[ "$ORIGINAL" =~ [[:space:]] ]]; then
  trimmed="${ORIGINAL#"${ORIGINAL%%[![:space:]]*}"}"
  trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
  if [ "$ORIGINAL" != "$trimmed" ]; then
    echo "leading or trailing whitespace forbidden" >&2
    exit 1
  fi
fi

if [[ "$ORIGINAL" =~ ^deploy-production\ ([0-9a-f]{40})\ (sha256:[0-9a-f]{64})$ ]]; then
  SHA="${BASH_REMATCH[1]}"
  DIGEST="${BASH_REMATCH[2]}"
  exec sudo -n "$DEPLOY_SCRIPT" "$SHA" "$DIGEST"
fi

if [[ "$ORIGINAL" =~ ^rollback-production\ ([0-9a-f]{40})$ ]]; then
  EXPECTED_SHA="${BASH_REMATCH[1]}"
  exec sudo -n "$ROLLBACK_SCRIPT" "$EXPECTED_SHA"
fi

echo "invalid forced command grammar" >&2
exit 1
