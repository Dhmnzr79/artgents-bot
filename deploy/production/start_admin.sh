#!/usr/bin/env sh
set -eu

GUNICORN_THREADS_RAW="${ADMIN_GUNICORN_THREADS:-4}"
case "${GUNICORN_THREADS_RAW}" in
  *[!0-9]*|'')
    echo "admin_gunicorn_threads_invalid: ${GUNICORN_THREADS_RAW}" >&2
    exit 1
    ;;
esac
if [ "${GUNICORN_THREADS_RAW}" -lt 2 ] || [ "${GUNICORN_THREADS_RAW}" -gt 16 ]; then
  echo "admin_gunicorn_threads_out_of_range: ${GUNICORN_THREADS_RAW}" >&2
  exit 1
fi

exec gunicorn \
  -w 1 \
  --threads "${GUNICORN_THREADS_RAW}" \
  -b "0.0.0.0:${ADMIN_DASHBOARD_PORT:-9100}" \
  --timeout 120 \
  --graceful-timeout 30 \
  admin_dashboard.app:app
