FROM python:3.11-slim@sha256:d1053354624536b044162aaab1e418bd000ea35184fb1ae098ab3166b1072e72

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --gid 10001 botapp \
    && useradd --uid 10001 --gid 10001 --create-home --home-dir /home/botapp botapp

COPY requirements.lock ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock

COPY --chown=botapp:botapp . .

RUN mkdir -p /app/data /app/logs \
    && chown -R botapp:botapp /app/data /app/logs \
    && chmod +x /app/start.sh /app/deploy/production/start_admin.sh \
    && chmod +x /app/deploy/production/admin_container_healthcheck.py

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"]

CMD ["/app/start.sh"]
