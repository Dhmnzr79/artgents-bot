"""T6B pass 1: health endpoints, prod readiness, Qwen-only config, Docker contracts."""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def app_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CHAT_API_KEY", "test-chat-offline")
    monkeypatch.setenv(
        "CHAT_BASE_URL",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
    monkeypatch.setenv("APP_ENV", "local")
    import app as app_module

    return app_module.app.test_client()


def test_health_live_ok_without_db(app_client) -> None:
    with patch("pg_sink.init_pg_sink"):
        resp = app_client.get("/health/live")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"ok": True, "status": "live"}


def test_health_ready_local_skips_mandatory_pg() -> None:
    from core.prod_readiness import evaluate_readiness

    ok, payload = evaluate_readiness(app_env="local")
    assert ok is True
    assert payload["checks"]["postgres"] == "skipped"


def test_readiness_prod_missing_allowed_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    import config as config_module

    monkeypatch.setattr(config_module, "APP_ENV", "prod")
    monkeypatch.setattr(config_module, "ALLOWED_CLIENTS", frozenset())
    monkeypatch.setattr(config_module, "DEFAULT_CLIENT_ID", "demo")
    from core.prod_readiness import evaluate_readiness

    ok, payload = evaluate_readiness(app_env="prod")
    assert ok is False
    assert "allowed_clients_empty" in payload["checks"]["reasons"]


def test_readiness_prod_forbidden_template_client(monkeypatch: pytest.MonkeyPatch) -> None:
    import config as config_module

    monkeypatch.setattr(config_module, "APP_ENV", "prod")
    monkeypatch.setattr(config_module, "ALLOWED_CLIENTS", frozenset({"_template"}))
    monkeypatch.setattr(config_module, "DEFAULT_CLIENT_ID", "demo")
    from core.prod_readiness import evaluate_readiness

    ok, payload = evaluate_readiness(app_env="prod")
    assert ok is False
    reasons = payload["checks"]["reasons"]
    assert any("allowed_client_id_forbidden:_template" in r for r in reasons)


def test_readiness_prod_default_not_in_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    import config as config_module

    monkeypatch.setattr(config_module, "APP_ENV", "prod")
    monkeypatch.setattr(config_module, "ALLOWED_CLIENTS", frozenset({"demo"}))
    monkeypatch.setattr(config_module, "DEFAULT_CLIENT_ID", "nikadent")
    from core.prod_readiness import evaluate_readiness

    ok, payload = evaluate_readiness(app_env="prod")
    assert ok is False
    assert "default_client_not_allowed" in payload["checks"]["reasons"]


def test_readiness_prod_missing_chat_key(monkeypatch: pytest.MonkeyPatch) -> None:
    import config as config_module

    monkeypatch.setattr(config_module, "APP_ENV", "prod")
    monkeypatch.setattr(config_module, "ALLOWED_CLIENTS", frozenset({"demo"}))
    monkeypatch.setattr(config_module, "DEFAULT_CLIENT_ID", "demo")
    monkeypatch.setattr(config_module, "CHAT_API_KEY", None)
    from core.prod_readiness import evaluate_readiness

    ok, payload = evaluate_readiness(app_env="prod")
    assert ok is False
    assert "chat_api_key_missing" in payload["checks"]["reasons"]


def test_readiness_prod_blocked_chat_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    import config as config_module

    monkeypatch.setattr(config_module, "APP_ENV", "prod")
    monkeypatch.setattr(config_module, "ALLOWED_CLIENTS", frozenset({"demo"}))
    monkeypatch.setattr(config_module, "DEFAULT_CLIENT_ID", "demo")
    monkeypatch.setattr(config_module, "CHAT_API_KEY", "sk-test")
    monkeypatch.setattr(config_module, "CHAT_BASE_URL", "https://api.openai.com/v1")
    from core.prod_readiness import evaluate_readiness

    ok, payload = evaluate_readiness(app_env="prod")
    assert ok is False
    assert "chat_base_url_host_blocked" in payload["checks"]["reasons"]


def test_readiness_prod_missing_pg_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    import config as config_module

    monkeypatch.setattr(config_module, "APP_ENV", "prod")
    monkeypatch.setattr(config_module, "ALLOWED_CLIENTS", frozenset({"demo"}))
    monkeypatch.setattr(config_module, "DEFAULT_CLIENT_ID", "demo")
    monkeypatch.setattr(config_module, "CHAT_API_KEY", "sk-test")
    monkeypatch.setattr(
        config_module,
        "CHAT_BASE_URL",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
    monkeypatch.delenv("BOT_PG_DSN", raising=False)
    from core.prod_readiness import evaluate_readiness

    ok, payload = evaluate_readiness(app_env="prod")
    assert ok is False
    assert "bot_pg_dsn_missing" in payload["checks"]["reasons"]


def test_readiness_prod_postgres_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    import config as config_module

    monkeypatch.setattr(config_module, "APP_ENV", "prod")
    monkeypatch.setattr(config_module, "ALLOWED_CLIENTS", frozenset({"demo"}))
    monkeypatch.setattr(config_module, "DEFAULT_CLIENT_ID", "demo")
    monkeypatch.setattr(config_module, "CHAT_API_KEY", "sk-test")
    monkeypatch.setattr(
        config_module,
        "CHAT_BASE_URL",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
    monkeypatch.setenv("BOT_PG_DSN", "postgresql://bot:bot@127.0.0.1:9/nope")
    with patch("psycopg.connect", side_effect=OSError("nope")):
        from core.prod_readiness import evaluate_readiness

        ok, payload = evaluate_readiness(app_env="prod")
    assert ok is False
    assert "postgres_unavailable" in payload["checks"]["reasons"]


def test_readiness_prod_schema_not_ready_closes_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    import config as config_module

    monkeypatch.setattr(config_module, "APP_ENV", "prod")
    monkeypatch.setattr(config_module, "ALLOWED_CLIENTS", frozenset({"demo"}))
    monkeypatch.setattr(config_module, "DEFAULT_CLIENT_ID", "demo")
    monkeypatch.setattr(config_module, "CHAT_API_KEY", "sk-test")
    monkeypatch.setattr(
        config_module,
        "CHAT_BASE_URL",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
    monkeypatch.setenv("BOT_PG_DSN", "postgresql://bot:bot@127.0.0.1:5432/bot_events")
    conn = MagicMock()
    with patch("psycopg.connect", return_value=conn):
        with patch(
            "core.pg_schema_readiness.check_pg_schema_ready",
            return_value=(False, "missing_table:public.bot_events"),
        ):
            from core.prod_readiness import evaluate_readiness

            ok, payload = evaluate_readiness(app_env="prod")
    conn.close.assert_called_once()
    assert ok is False
    assert any(r.startswith("postgres_schema_not_ready:") for r in payload["checks"]["reasons"])


def test_readiness_prod_schema_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    import config as config_module

    monkeypatch.setattr(config_module, "APP_ENV", "prod")
    monkeypatch.setattr(config_module, "ALLOWED_CLIENTS", frozenset({"demo"}))
    monkeypatch.setattr(config_module, "DEFAULT_CLIENT_ID", "demo")
    monkeypatch.setattr(config_module, "CHAT_API_KEY", "sk-test")
    monkeypatch.setattr(
        config_module,
        "CHAT_BASE_URL",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
    monkeypatch.setenv("BOT_PG_DSN", "postgresql://bot:bot@127.0.0.1:5432/bot_events")
    conn = MagicMock()
    with patch("psycopg.connect", return_value=conn):
        with patch("core.pg_schema_readiness.check_pg_schema_ready", return_value=(True, "")):
            from core.prod_readiness import evaluate_readiness

            ok, _payload = evaluate_readiness(app_env="prod")
    conn.close.assert_called_once()
    assert ok is True


def test_readiness_does_not_call_provider_or_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    import config as config_module

    monkeypatch.setattr(config_module, "APP_ENV", "prod")
    monkeypatch.setattr(config_module, "ALLOWED_CLIENTS", frozenset({"demo"}))
    monkeypatch.setattr(config_module, "DEFAULT_CLIENT_ID", "demo")
    monkeypatch.setattr(config_module, "CHAT_API_KEY", "sk-test")
    monkeypatch.setattr(
        config_module,
        "CHAT_BASE_URL",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
    monkeypatch.delenv("BOT_PG_DSN", raising=False)
    with patch("llm.chat_completions_create") as chat_mock:
        with patch("core.lead_email.send_lead_email") as smtp_mock:
            from core.prod_readiness import evaluate_readiness

            evaluate_readiness(app_env="prod")
    chat_mock.assert_not_called()
    smtp_mock.assert_not_called()


def test_qwen_only_config_import_without_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CHAT_API_KEY", raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-test-key")
    monkeypatch.setenv(
        "CHAT_BASE_URL",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
    monkeypatch.setenv("GITHUB_ACTIONS", "false")
    saved = sys.modules.pop("config", None)
    try:
        import config as config_module

        importlib.reload(config_module)
        assert not hasattr(config_module, "OPENAI_API_KEY")
        assert config_module.CHAT_API_KEY == "dashscope-test-key"
    finally:
        if saved is not None:
            sys.modules["config"] = saved


def test_config_runtime_has_no_openai_symbol() -> None:
    import config as config_module

    assert not hasattr(config_module, "OPENAI_API_KEY")
    assert not hasattr(config_module, "require_openai_api_key")


def test_build_index_does_not_reference_openai_embeddings() -> None:
    text = (ROOT / "build_index.py").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" not in text
    assert "embeddings.create" not in text


def test_dockerfile_non_root_user_and_start_sh() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "USER 10001:10001" in text
    assert "start.sh" in text
    assert "PYTHONDONTWRITEBYTECODE" in text


def test_start_sh_single_process_gthread_with_threads() -> None:
    text = (ROOT / "start.sh").read_text(encoding="utf-8")
    assert "exec gunicorn" in text
    assert "-w 1" in text
    assert "--worker-class gthread" in text
    assert '--threads "${GUNICORN_THREADS_RAW}"' in text
    assert "--graceful-timeout" in text


def test_gunicorn_threads_parser_bounds() -> None:
    from core.gunicorn_runtime import parse_gunicorn_threads

    assert parse_gunicorn_threads("8") == 8
    assert parse_gunicorn_threads(None) == 8
    with pytest.raises(ValueError, match="invalid"):
        parse_gunicorn_threads("8;rm")
    with pytest.raises(ValueError, match="out_of_range"):
        parse_gunicorn_threads("1")


def test_dockerfile_healthcheck_uses_python_stdlib_live() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "HEALTHCHECK" in text
    assert "/health/live" in text
    assert "urllib.request" in text
    assert "curl" not in text.lower()


def test_dockerignore_excludes_and_preserves_runtime() -> None:
    text = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    for needle in (
        ".git",
        ".github",
        ".cursor",
        ".perf9_embedding_ledger/",
        ".prewarm_ledger/",
        ".env",
        "data/",
        "logs/",
        "tests/",
        "evals/",
        ".pytest_cache/",
    ):
        assert needle in text
    for preserved in ("migrations/", "orchestration/", "admin_dashboard/"):
        assert preserved not in text
    assert "clients/" not in text.replace("!clients/**/*.md", "")
    assert "static/" not in text
    assert "core/" not in text


def test_health_endpoints_skip_http_request_logging(app_client) -> None:
    with patch("app.log_json") as log_mock:
        with patch("logging_setup.emit_bot_event") as emit_mock:
            live = app_client.get("/health/live")
            ready = app_client.get("/health/ready")
    assert live.status_code == 200
    assert ready.status_code == 200
    log_mock.assert_not_called()
    emit_mock.assert_not_called()


def test_http_ready_prod_200_and_503_without_secrets(app_client) -> None:
    with patch(
        "core.prod_readiness.evaluate_readiness",
        return_value=(True, {"ok": True, "status": "ready", "checks": {}}),
    ):
        ok_resp = app_client.get("/health/ready")
    assert ok_resp.status_code == 200
    body = ok_resp.get_json()
    assert "postgresql://" not in str(body)
    assert body["ok"] is True

    with patch(
        "core.prod_readiness.evaluate_readiness",
        return_value=(
            False,
            {
                "ok": False,
                "status": "not_ready",
                "checks": {"reasons": ["bot_pg_dsn_missing"]},
            },
        ),
    ):
        bad_resp = app_client.get("/health/ready")
    assert bad_resp.status_code == 503
    bad_body = bad_resp.get_json()
    assert bad_body["checks"]["reasons"] == ["bot_pg_dsn_missing"]
    assert "password" not in str(bad_body).lower()


def test_health_ready_no_host_or_origin_required(app_client) -> None:
    resp = app_client.get("/health/ready", headers={"Host": "unknown.example"})
    assert resp.status_code in (200, 503)


def test_session_client_binding_not_shared_across_threads() -> None:
    import concurrent.futures

    from session import bind_session_client, clear_session_client_binding, current_session_client_id

    def _worker(client_id: str) -> str | None:
        bind_session_client(client_id)
        try:
            return current_session_client_id()
        finally:
            clear_session_client_binding()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        demo = pool.submit(_worker, "demo").result()
        nika = pool.submit(_worker, "nikadent").result()
    assert demo == "demo"
    assert nika == "nikadent"
    assert current_session_client_id() is None
