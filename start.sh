#!/usr/bin/env sh
set -eu

# SQLite session storage is single-writer oriented: one Gunicorn process only.
# Use gthread so one long-lived /ask/stream does not block /health/live.
GUNICORN_THREADS_RAW="${GUNICORN_THREADS:-8}"
case "${GUNICORN_THREADS_RAW}" in
  *[!0-9]*|'')
    echo "gunicorn_threads_invalid: ${GUNICORN_THREADS_RAW}" >&2
    exit 1
    ;;
esac
if [ "${GUNICORN_THREADS_RAW}" -lt 2 ] || [ "${GUNICORN_THREADS_RAW}" -gt 16 ]; then
  echo "gunicorn_threads_out_of_range: ${GUNICORN_THREADS_RAW}" >&2
  exit 1
fi

exec gunicorn \
  -w 1 \
  --worker-class gthread \
  --threads "${GUNICORN_THREADS_RAW}" \
  -b 0.0.0.0:8000 \
  --timeout 120 \
  --graceful-timeout 30 \
  app:app
