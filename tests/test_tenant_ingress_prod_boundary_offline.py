"""Production Host-bound tenant ingress (APP_ENV=prod, offline)."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import pytest

import app as app_module
import config
import core.client_host as client_host
import core.origin_guard as origin_guard
from core.client_config_loader import load_lead_config
from session import current_session_client_id
from tests.test_sales_fast_widget_integration import _CountingBackend, _install_sales_fast_transport
from tests.test_sales_one_plus_turn import answer_envelope

_NIKADENT_HOST = "nikadent.bot.artgents.ru"
_NIKADENT_ORIGIN = "https://nikadent.bot.artgents.ru"
_DEMO_HOST = "demo.bot.artgents.ru"
_DEMO_ORIGIN = "https://artgents.ru"
_UNKNOWN_HOST = "unknown.bot.artgents.ru"


def isolated_sqlite_paths(tmp_path: Path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    def _sqlite_path(client_id: str | None) -> str:
        pack = (client_id or "demo").strip() or "demo"
        return str((sessions_dir / f"{pack}.db").resolve())

    return _sqlite_path, sessions_dir


@pytest.fixture
def prod_tenant_boundary(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(client_host, "APP_ENV", "prod")
    monkeypatch.setattr(origin_guard, "APP_ENV", "prod")
    allowed = frozenset({"demo", "nikadent"})
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", allowed)
    monkeypatch.setattr(client_host, "ALLOWED_CLIENTS", allowed)


def _nikadent_base_url() -> str:
    return f"http://{_NIKADENT_HOST}"


def _demo_base_url() -> str:
    return f"http://{_DEMO_HOST}"


def _unknown_base_url() -> str:
    return f"http://{_UNKNOWN_HOST}"


def _prod_headers(*, origin: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if origin:
        headers["Origin"] = origin
    return headers


def _table_count(db_path: Path) -> int:
    if not db_path.is_file():
        return 0
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def _parse_sse_ui_payload(resp) -> dict:
    text = resp.get_data(as_text=True)
    match = re.search(r"event: ui\ndata: (.+?)\n\n", text)
    assert match is not None
    return json.loads(match.group(1))


@pytest.mark.parametrize("path", ["/ask"])
def test_prod_ask_json_host_without_body_client_id(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    sqlite_path, sessions_dir = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    backend = _CountingBackend(answer_envelope("Ответ nikadent."))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"s-prod-{uuid.uuid4().hex[:8]}"
    client = app_module.app.test_client()
    body = {"q": "Расскажите о клинике", "sid": sid}

    resp = client.post(
        path,
        json=body,
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    assert resp.status_code == 200
    assert backend.call_count == 1
    payload = resp.get_json()
    assert payload["meta"]["client_id"] == "nikadent"
    assert _table_count(sessions_dir / "nikadent.db") >= 1
    assert _table_count(sessions_dir / "demo.db") == 0
    assert current_session_client_id() is None


def test_prod_ask_stream_host_mismatch_blocked_at_ingress(
    prod_tenant_boundary,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(answer_envelope("must not run"))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": "Привет", "sid": "s-stream-mismatch", "client_id": "demo"},
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    assert resp.status_code == 403
    assert backend.call_count == 0


def _assert_prod_nikadent_stream_terminal(
    resp,
    backend: _CountingBackend,
    sessions_dir: Path,
) -> dict:
    assert resp.status_code == 200
    body_text = resp.get_data(as_text=True)
    assert "event: done" in body_text
    payload = _parse_sse_ui_payload(resp)
    assert payload.get("error") != "unknown_client"
    assert payload["meta"]["client_id"] == "nikadent"
    assert backend.call_count == 1
    assert _table_count(sessions_dir / "nikadent.db") >= 1
    assert _table_count(sessions_dir / "demo.db") == 0
    assert current_session_client_id() is None
    return payload


@pytest.mark.parametrize(
    "include_body_client_id",
    [False, True],
    ids=["host-only", "matching-body"],
)
def test_prod_ask_stream_positive_nikadent(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    include_body_client_id: bool,
) -> None:
    sqlite_path, sessions_dir = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    backend = _CountingBackend(answer_envelope("Stream Nikadent ответ."))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"s-stream-pos-{uuid.uuid4().hex[:8]}"
    body: dict = {"q": "Расскажите о клинике", "sid": sid}
    if include_body_client_id:
        body["client_id"] = "nikadent"
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json=body,
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    _assert_prod_nikadent_stream_terminal(resp, backend, sessions_dir)


def test_prod_ask_stream_invalid_host_403_before_worker(
    prod_tenant_boundary,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(answer_envelope("must not run"))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": "Привет", "sid": "s-stream-bad-host", "client_id": "nikadent"},
        base_url=_unknown_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    assert resp.status_code == 403
    assert backend.call_count == 0


def test_prod_ask_and_stream_tenant_parity(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, sessions_dir = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    answer_text = "Parity Nikadent ответ."
    ask_backend = _CountingBackend(answer_envelope(answer_text))
    stream_backend = _CountingBackend(answer_envelope(answer_text))
    backends = [ask_backend, stream_backend]

    def _rotating_backend():
        return backends.pop(0)

    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        _rotating_backend,
    )
    question = "Расскажите о клинике"
    ask_resp = app_module.app.test_client().post(
        "/ask",
        json={"q": question, "sid": f"s-parity-ask-{uuid.uuid4().hex[:6]}"},
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    stream_resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": question, "sid": f"s-parity-stream-{uuid.uuid4().hex[:6]}"},
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    assert ask_resp.status_code == 200
    ask_payload = ask_resp.get_json()
    stream_payload = _assert_prod_nikadent_stream_terminal(
        stream_resp,
        stream_backend,
        sessions_dir,
    )
    assert ask_payload["meta"]["client_id"] == "nikadent"
    assert ask_payload.get("answer") == stream_payload.get("answer")
    assert ask_backend.call_count == 1
    assert _table_count(sessions_dir / "demo.db") == 0


def test_prod_stream_overload_fallback_preserves_validated_tenant(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import MagicMock

    sqlite_path, sessions_dir = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr(
        app_module,
        "_sse_worker_admission",
        MagicMock(acquire=MagicMock(return_value=False)),
    )
    backend = _CountingBackend(answer_envelope("Overload stream ответ."))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": "Расскажите о клинике", "sid": f"s-overload-{uuid.uuid4().hex[:6]}"},
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    _assert_prod_nikadent_stream_terminal(resp, backend, sessions_dir)


def test_prod_stream_ingress_resolves_once_without_localhost_reresolution(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, sessions_dir = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    real_resolve = client_host.resolve_request_client_id
    resolve_calls: list[dict] = []

    def _track_resolve(raw, *, host):
        resolve_calls.append({"raw": raw, "host": host})
        return real_resolve(raw, host=host)

    monkeypatch.setattr(app_module, "resolve_request_client_id", _track_resolve)
    backend = _CountingBackend(answer_envelope("Tracked stream."))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": "Расскажите о клинике", "sid": f"s-track-{uuid.uuid4().hex[:6]}"},
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    _assert_prod_nikadent_stream_terminal(resp, backend, sessions_dir)
    assert len(resolve_calls) == 1
    assert _NIKADENT_HOST in str(resolve_calls[0]["host"])
    assert "localhost" not in str(resolve_calls[0]["host"]).lower()


def test_prod_stream_trusted_handoff_passes_resolved_client_id_to_worker(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, sessions_dir = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    handoffs: list[str | None] = []
    real_inner = app_module._orchestrate_ask_turn_inner

    def _spy_inner(data, *, resolved_client_id=None):
        handoffs.append(resolved_client_id)
        return real_inner(data, resolved_client_id=resolved_client_id)

    monkeypatch.setattr(app_module, "_orchestrate_ask_turn_inner", _spy_inner)
    backend = _CountingBackend(answer_envelope("Handoff stream."))
    _install_sales_fast_transport(monkeypatch, backend)
    tampered_body = {
        "q": "Расскажите о клинике",
        "sid": f"s-handoff-{uuid.uuid4().hex[:6]}",
        "client_id": "demo",
    }
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json=tampered_body,
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    assert resp.status_code == 403
    assert handoffs == []
    assert backend.call_count == 0

    resp_ok = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": "Расскажите о клинике", "sid": f"s-handoff-ok-{uuid.uuid4().hex[:6]}"},
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    _assert_prod_nikadent_stream_terminal(resp_ok, backend, sessions_dir)
    assert handoffs == ["nikadent"]


def test_prod_ask_matching_body_client_id(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, sessions_dir = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    backend = _CountingBackend(answer_envelope("Ответ."))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"s-match-{uuid.uuid4().hex[:8]}"
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Привет", "sid": sid, "client_id": "nikadent"},
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    assert resp.status_code == 200
    assert resp.get_json()["meta"]["client_id"] == "nikadent"
    assert backend.call_count == 1


@pytest.mark.parametrize("path", ["/ask", "/ask/stream"])
def test_prod_ask_host_body_mismatch_403(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    sqlite_path, sessions_dir = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    backend = _CountingBackend(answer_envelope("must not run"))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"s-mismatch-{uuid.uuid4().hex[:8]}"
    resp = app_module.app.test_client().post(
        path,
        json={"q": "Привет", "sid": sid, "client_id": "demo"},
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    assert resp.status_code == 403
    assert backend.call_count == 0
    assert _table_count(sessions_dir / "demo.db") == 0


def test_prod_ask_unknown_host_with_body_403(
    prod_tenant_boundary,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(answer_envelope("must not run"))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Привет", "sid": "s-unknown-host", "client_id": "nikadent"},
        base_url=_unknown_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    assert resp.status_code == 403
    assert backend.call_count == 0


def test_prod_ask_missing_host_403(
    prod_tenant_boundary,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(answer_envelope("must not run"))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Привет", "sid": "s-no-host", "client_id": "nikadent"},
    )
    assert resp.status_code == 403
    assert backend.call_count == 0


def test_prod_lead_matching_host_uses_pack_config(
    prod_tenant_boundary,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict] = []

    def _fake_send(*, client_id, lead_cfg, **fields):
        sent.append({"client_id": client_id, "lead_cfg": dict(lead_cfg), **fields})
        return True, "email_sent"

    monkeypatch.setattr("lead_service.send_lead_email", _fake_send)
    monkeypatch.setattr("lead_service.leads_mode", lambda _cid: "email")

    resp = app_module.app.test_client().post(
        "/lead",
        json={
            "name": "Иван",
            "phone": "+79001234567",
            "intent": "consult",
            "sid": f"s-lead-{uuid.uuid4().hex[:6]}",
            "client_id": "nikadent",
            "recipient": "attacker@evil.example",
            "recipients": ["attacker@evil.example"],
            "email_to": "attacker@evil.example",
        },
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    assert resp.status_code == 200
    assert resp.get_json().get("ok") is True
    assert len(sent) == 1
    assert sent[0]["client_id"] == "nikadent"
    pack_cfg = load_lead_config("nikadent")
    assert sent[0]["lead_cfg"] == pack_cfg


def test_prod_lead_host_mismatch_403(prod_tenant_boundary, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _fake_send(**_kwargs):
        calls.append("send")
        return True, "email_sent"

    monkeypatch.setattr("lead_service.send_lead_email", _fake_send)
    resp = app_module.app.test_client().post(
        "/lead",
        json={
            "name": "Иван",
            "phone": "+79001234567",
            "client_id": "demo",
            "sid": "s-lead-block",
        },
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    assert resp.status_code == 403
    assert calls == []


def test_prod_lead_unknown_host_403(prod_tenant_boundary, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lead_service.send_lead_email",
        lambda **_k: (_ for _ in ()).throw(AssertionError("must not send")),
    )
    resp = app_module.app.test_client().post(
        "/lead",
        json={"name": "A", "phone": "+79001112233", "client_id": "nikadent", "sid": "s-x"},
        base_url=_unknown_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    assert resp.status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/api/widget-config",
        "/api/video-catalog",
    ],
)
def test_prod_widget_get_matching_host(
    prod_tenant_boundary,
    path: str,
) -> None:
    resp = app_module.app.test_client().get(
        path,
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    assert resp.status_code == 200
    if path == "/api/widget-config":
        assert resp.get_json().get("clientId") == "nikadent"
    else:
        assert resp.get_json().get("client_id") == "nikadent"


def test_prod_widget_query_mismatch_403(prod_tenant_boundary) -> None:
    resp = app_module.app.test_client().get(
        "/api/widget-config?client_id=demo",
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    assert resp.status_code == 403
    assert resp.get_json().get("error") == "unknown_client"


def test_prod_widget_bad_host_no_demo_fallback(prod_tenant_boundary) -> None:
    resp = app_module.app.test_client().get(
        "/api/widget-config?client_id=demo",
        base_url=_unknown_base_url(),
        headers=_prod_headers(origin=_DEMO_ORIGIN),
    )
    assert resp.status_code == 403


def test_prod_media_tenant_routing_mocked_boundary(
    prod_tenant_boundary,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[tuple[str, str]] = []

    def _external_src(*, client_id, video_key):
        return f"https://cdn.example/{client_id}/{video_key}.mp4"

    monkeypatch.setattr("app.get_external_video_src", _external_src)

    class _FakeUpstream:
        status = 200
        headers = {"Content-Type": "video/mp4"}

        def read(self, _n=65536):
            return b""

        def close(self):
            return None

    def _fake_urlopen(req, timeout=120):
        opened.append((req.full_url, timeout))
        return _FakeUpstream()

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    resp = app_module.app.test_client().get(
        "/api/media/demo-video?client_id=nikadent",
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    assert resp.status_code == 200
    assert opened
    assert "/nikadent/" in opened[0][0]

    blocked = app_module.app.test_client().get(
        "/api/media/demo-video?client_id=demo",
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin=_NIKADENT_ORIGIN),
    )
    assert blocked.status_code == 403
    assert len(opened) == 1


def test_prod_cors_options_matching_host(prod_tenant_boundary) -> None:
    resp = app_module.app.test_client().open(
        "/api/widget-config",
        method="OPTIONS",
        base_url=_nikadent_base_url(),
        headers={"Origin": _NIKADENT_ORIGIN},
    )
    assert resp.status_code == 204
    assert resp.headers.get("Access-Control-Allow-Origin") == _NIKADENT_ORIGIN


def test_prod_cors_options_bad_host_403(prod_tenant_boundary) -> None:
    resp = app_module.app.test_client().open(
        "/api/widget-config",
        method="OPTIONS",
        base_url=_unknown_base_url(),
        headers={"Origin": _NIKADENT_ORIGIN},
    )
    assert resp.status_code == 403


def test_prod_demo_host_allows_demo_tenant(
    prod_tenant_boundary,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(answer_envelope("Demo ответ."))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Привет", "sid": f"s-demo-host-{uuid.uuid4().hex[:6]}"},
        base_url=_demo_base_url(),
        headers=_prod_headers(origin=_DEMO_ORIGIN),
    )
    assert resp.status_code == 200
    assert resp.get_json()["meta"]["client_id"] == "demo"
    assert backend.call_count == 1
