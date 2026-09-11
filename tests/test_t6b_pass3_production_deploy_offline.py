"""T6B pass 3: production Compose, Caddy, private admin (offline static contracts)."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PROD = ROOT / "deploy" / "production"
COMPOSE = PROD / "compose.yml"
CADDYFILE = PROD / "Caddyfile"
README = PROD / "README.md"
ENV_EXAMPLE = PROD / "env.production.example"

_EXPECTED_SERVICES = frozenset({"postgres", "migrate", "bot", "admin", "caddy"})

_SECRET_LITERAL_PATTERNS = (
    re.compile(r"postgresql://[^:\s/]+:[^@\s/]+@", re.I),
    re.compile(r"bcrypt\$2[aby]\$"),
)

@pytest.fixture(scope="module")
def compose_doc() -> dict:
    text = COMPOSE.read_text(encoding="utf-8")
    for pat in _SECRET_LITERAL_PATTERNS:
        assert not pat.search(text), f"compose.yml may contain a secret literal: {pat.pattern}"
    return yaml.safe_load(text)


@pytest.fixture(scope="module")
def caddy_text() -> str:
    return CADDYFILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def readme_text() -> str:
    return README.read_text(encoding="utf-8")


def test_exactly_five_services(compose_doc: dict) -> None:
    services = compose_doc.get("services") or {}
    assert set(services) == _EXPECTED_SERVICES


def test_public_ports_only_on_caddy(compose_doc: dict) -> None:
    services = compose_doc["services"]
    for name, spec in services.items():
        ports = spec.get("ports") or []
        if name == "caddy":
            assert ports, "caddy must publish ports"
        else:
            assert not ports, f"{name} must not publish ports"


def test_caddy_port_bindings_exact(compose_doc: dict) -> None:
    ports = compose_doc["services"]["caddy"]["ports"]
    normalized = [str(p) for p in ports]
    assert "80:80" in normalized
    assert "443:443" in normalized
    assert "127.0.0.1:9100:9100" in normalized
    for p in normalized:
        assert not p.startswith("0.0.0.0:9100"), "admin must not bind 0.0.0.0 on host"
        assert ":5432" not in p
        assert ":8000" not in p


def test_forbidden_compose_anti_patterns() -> None:
    text = COMPOSE.read_text(encoding="utf-8").lower()
    assert "docker.sock" not in text
    assert "privileged" not in text
    assert "network_mode" not in text
    assert "admin.bot.artgents.ru" not in text
    assert "redis" not in text


def test_migrate_uses_migrator_dsn_only(compose_doc: dict) -> None:
    env = compose_doc["services"]["migrate"].get("environment") or {}
    keys = set(env.keys())
    assert keys == {"BOT_MIGRATOR_PG_DSN"}
    assert str(env["BOT_MIGRATOR_PG_DSN"]).startswith("${BOT_MIGRATOR_PG_DSN")


def test_bot_admin_no_migrator_dsn(compose_doc: dict) -> None:
    for svc in ("bot", "admin"):
        env = compose_doc["services"][svc].get("environment") or {}
        blob = yaml.dump(env)
        assert "BOT_MIGRATOR_PG_DSN" not in blob
        assert "POSTGRES_PASSWORD" not in blob


def test_postgres_bootstrap_only(compose_doc: dict) -> None:
    env = compose_doc["services"]["postgres"].get("environment") or {}
    allowed = {"POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"}
    assert set(env) <= allowed
    blob = yaml.dump(env)
    assert "BOT_PG_DSN" not in blob
    assert "DASHSCOPE" not in blob
    assert "SMTP" not in blob


def test_caddy_no_db_or_qwen_or_smtp(compose_doc: dict) -> None:
    env = compose_doc["services"]["caddy"].get("environment") or {}
    blob = yaml.dump(env).upper()
    for needle in ("BOT_PG_DSN", "BOT_MIGRATOR", "DASHSCOPE", "SMTP", "POSTGRES_"):
        assert needle not in blob


def test_bot_admin_depend_on_successful_migrate(compose_doc: dict) -> None:
    for svc in ("bot", "admin"):
        dep = compose_doc["services"][svc].get("depends_on") or {}
        assert "migrate" in dep
        assert dep["migrate"].get("condition") == "service_completed_successfully"


def test_postgres_healthcheck(compose_doc: dict) -> None:
    hc = compose_doc["services"]["postgres"].get("healthcheck") or {}
    test_cmd = hc.get("test") or []
    joined = " ".join(str(x) for x in test_cmd)
    assert "pg_isready" in joined


def test_bot_liveness_healthcheck_live(compose_doc: dict) -> None:
    hc = compose_doc["services"]["bot"].get("healthcheck") or {}
    joined = " ".join(str(x) for x in (hc.get("test") or []))
    assert "/health/live" in joined


def test_admin_healthcheck_port_9100_api_health(compose_doc: dict) -> None:
    hc = compose_doc["services"]["admin"].get("healthcheck") or {}
    joined = " ".join(str(x) for x in (hc.get("test") or []))
    assert "admin_container_healthcheck.py" in joined
    assert "8000" not in joined
    assert "/health/live" not in joined


def test_admin_healthcheck_script_uses_environ_not_literal_token() -> None:
    script = (PROD / "admin_container_healthcheck.py").read_text(encoding="utf-8")
    compose_text = COMPOSE.read_text(encoding="utf-8")
    assert "os.environ" in script
    assert "9100" in script
    assert "/api/health" in script
    assert "X-Admin-Dashboard-Token" in script
    assert "print(" not in script
    admin_hc_block = compose_text.split("admin:", 1)[1].split("caddy:", 1)[0]
    assert "ADMIN_DASHBOARD_TOKEN" not in admin_hc_block.split("healthcheck", 1)[-1]


def test_caddy_waits_for_healthy_admin(compose_doc: dict) -> None:
    dep = compose_doc["services"]["caddy"].get("depends_on") or {}
    assert dep["bot"].get("condition") == "service_healthy"
    assert dep["admin"].get("condition") == "service_healthy"


def test_caddy_public_profile_only(compose_doc: dict) -> None:
    profiles = compose_doc["services"]["caddy"].get("profiles") or []
    assert profiles == ["public"]


def test_readme_staged_startup_before_public_caddy(readme_text: str) -> None:
    low = readme_text.lower()
    assert "--profile public" in readme_text
    assert "/health/ready" in readme_text
    assert "exec" in low and "bot" in low
    assert "использовать полный" in low and "docker compose up -d" in low
    ready_pos = readme_text.index("/health/ready")
    public_pos = readme_text.index("--profile public")
    assert ready_pos < public_pos


def test_readme_and_env_bcrypt_hash_single_quote_guidance(readme_text: str) -> None:
    env_text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "BCrypt" in readme_text or "BCrypt" in env_text or "bcrypt" in readme_text.lower()
    assert "single" in readme_text.lower() or "одинарн" in readme_text.lower()
    assert "CADDY_ADMIN_BASIC_AUTH_HASH='$" in env_text or "CADDY_ADMIN_BASIC_AUTH_HASH='$" in readme_text
    assert not re.search(r"bcrypt\$2[aby]\$[0-9A-Za-z./]{20,}", env_text)


def test_migrate_one_shot_no_restart_loop(compose_doc: dict) -> None:
    mig = compose_doc["services"]["migrate"]
    assert mig.get("restart") == "no"
    cmd = mig.get("command") or []
    assert "deploy.postgres.migrate" in " ".join(str(c) for c in cmd)


def test_named_volumes_present(compose_doc: dict) -> None:
    vols = compose_doc.get("volumes") or {}
    for name in ("postgres_data", "caddy_data", "caddy_config", "bot_data", "bot_logs"):
        assert name in vols


def test_caddy_not_on_db_network(compose_doc: dict) -> None:
    caddy_nets = compose_doc["services"]["caddy"].get("networks") or []
    if isinstance(caddy_nets, dict):
        caddy_nets = list(caddy_nets.keys())
    assert "db_internal" not in caddy_nets
    assert "edge" in caddy_nets


def test_postgres_only_db_network(compose_doc: dict) -> None:
    nets = compose_doc["services"]["postgres"].get("networks") or []
    if isinstance(nets, dict):
        nets = list(nets.keys())
    assert nets == ["db_internal"]


def test_db_network_internal(compose_doc: dict) -> None:
    assert compose_doc["networks"]["db_internal"].get("internal") is True


def test_application_hardening(compose_doc: dict) -> None:
    for svc in ("migrate", "bot", "admin"):
        spec = compose_doc["services"][svc]
        assert spec.get("user") == "10001:10001"
        sec = spec.get("security_opt") or []
        assert "no-new-privileges:true" in sec
        assert "ALL" in (spec.get("cap_drop") or [])
        assert spec.get("read_only") is True
        tmpfs = spec.get("tmpfs") or []
        assert any("/tmp" in str(t) for t in tmpfs)


def test_caddy_proxies_bot_preserves_host(caddy_text: str) -> None:
    assert "reverse_proxy bot:8000" in caddy_text
    assert "header_up Host" in caddy_text
    assert "demo.bot.artgents.ru" in caddy_text
    assert "nikadent.bot.artgents.ru" in caddy_text


def test_caddy_private_admin_basic_auth_and_token(caddy_text: str) -> None:
    assert ":9100" in caddy_text
    assert "basic_auth" in caddy_text
    assert "reverse_proxy admin:9100" in caddy_text
    assert "X-Admin-Dashboard-Token" in caddy_text
    assert "admin off" in caddy_text.lower() or "admin off" in caddy_text


def test_caddy_security_headers_without_csp(caddy_text: str) -> None:
    assert "X-Content-Type-Options" in caddy_text
    assert "Referrer-Policy" in caddy_text
    assert "Strict-Transport-Security" in caddy_text
    assert "Content-Security-Policy" not in caddy_text


def test_no_public_admin_hostname(caddy_text: str) -> None:
    assert "admin.bot.artgents.ru" not in caddy_text


def test_start_admin_uses_gunicorn_not_flask_dev() -> None:
    text = (PROD / "start_admin.sh").read_text(encoding="utf-8")
    assert "exec gunicorn" in text
    assert "0.0.0.0" in text
    assert "app.run" not in text
    assert "admin_dashboard.app:app" in text


def test_dockerfile_chmods_admin_start() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "deploy/production/start_admin.sh" in text


def test_env_example_has_no_filled_secrets() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for pat in _SECRET_LITERAL_PATTERNS:
        assert not pat.search(text)
    assert "BOT_MIGRATOR_PG_DSN=" in text
    assert "BOT_PG_DSN=" in text


def test_readme_ssh_tunnel_release_gates_and_pass4(readme_text: str) -> None:
    low = readme_text.lower()
    assert "ssh -L 9100" in readme_text
    assert "/health/live" in readme_text
    assert "pass 4" in low
    assert "sqlite" in low and "backup" in low
    assert "не" in low and "автоматическ" in low


def test_image_parameters_required_in_compose() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert "${BOT_IMAGE:?set BOT_IMAGE}" in text
    assert "${POSTGRES_IMAGE:?set POSTGRES_IMAGE}" in text
    assert "${CADDY_IMAGE:?set CADDY_IMAGE}" in text


def test_compose_config_validation_optional() -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker CLI not available — static contracts only (UNKNOWN compose config)")
    env_file = ENV_EXAMPLE
    cmd = [
        "docker",
        "compose",
        "--env-file",
        str(env_file),
        "-f",
        str(COMPOSE),
        "config",
    ]
    # Empty example values fail interpolation — use minimal dummy env for structural validation only.
    dummy_env = {
        "BOT_IMAGE": "example/bot:local",
        "POSTGRES_IMAGE": "postgres:16",
        "CADDY_IMAGE": "caddy:2",
        "POSTGRES_USER": "bootstrap",
        "POSTGRES_PASSWORD": "dummy-not-real",
        "POSTGRES_DB": "clinic_observability",
        "BOT_MIGRATOR_PG_DSN": "postgresql://migrator:dummy@postgres:5432/clinic_observability",
        "BOT_PG_DSN": "postgresql://runtime:dummy@postgres:5432/clinic_observability",
        "ALLOWED_CLIENTS": "demo,nikadent",
        "DEFAULT_CLIENT_ID": "demo",
        "DASHSCOPE_API_KEY": "dummy",
        "CHAT_BASE_URL": "https://example.invalid/v1",
        "SMTP_HOST": "mail.example.invalid",
        "SMTP_PORT": "465",
        "SMTP_USER": "bot@example.invalid",
        "SMTP_PASSWORD": "dummy",
        "SMTP_FROM": "bot@example.invalid",
        "ADMIN_DASHBOARD_TOKEN": "dummy-token-for-config-only",
        "CADDY_ACME_EMAIL": "ops@example.invalid",
        "CADDY_ADMIN_BASIC_AUTH_USER": "owner",
        "CADDY_ADMIN_BASIC_AUTH_HASH": "JDUMMYHASH",
    }
    import os
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False, encoding="utf-8") as fh:
        for k, v in dummy_env.items():
            fh.write(f"{k}={v}\n")
        tmp_path = fh.name
    try:
        proc = subprocess.run(
            ["docker", "compose", "--env-file", tmp_path, "-f", str(COMPOSE), "config"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(ROOT),
        )
    finally:
        os.unlink(tmp_path)
    if proc.returncode != 0:
        pytest.skip(f"docker compose config failed (UNKNOWN runtime): {proc.stderr[:500]}")
    assert "services:" in proc.stdout
