FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --gid 10001 botapp \
    && useradd --uid 10001 --gid 10001 --create-home --home-dir /home/botapp botapp

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=botapp:botapp . .

RUN mkdir -p /app/data /app/logs \
    && chown -R botapp:botapp /app/data /app/logs \
    && chmod +x /app/start.sh

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"]

CMD ["/app/start.sh"]
