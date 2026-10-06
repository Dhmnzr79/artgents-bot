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

from tests.d2_ci_http import FakeProvider, http_env, raw, explanation
from tests.test_d2_http_contract import sse_events
from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore


@pytest.mark.parametrize('path', ['/ask', '/ask/stream'])
@pytest.mark.parametrize('tenant', ['demo', 'nikadent'])
@pytest.mark.parametrize('explicit', [False, True])
def test_d2_host_bound_tenant_json_sse(http_env, prod_tenant_boundary, monkeypatch, path, tenant, explicit):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(explanation('Объяснение клиники.'))))
    real = app_module.resolve_request_client_id
    calls = []
    def resolve(body, *, host):
        calls.append(host)
        return real(body, host=host)
    monkeypatch.setattr(app_module, 'resolve_request_client_id', resolve)
    payload = {'sid':'host-bound', 'request_id':'r1', 'q':'О клинике'}
    if explicit:
        payload['client_id'] = tenant
    response = client.post(path, json=payload, base_url=f'http://{tenant}.bot.artgents.ru',
                           headers=_prod_headers(origin=_DEMO_ORIGIN if tenant == 'demo' else _NIKADENT_ORIGIN))
    assert response.status_code == 200
    body = response.get_json() if path == '/ask' else dict(sse_events(response))['ui']
    assert body['client_id'] == tenant and body['answer'] == 'Объяснение клиники.'
    assert len(calls) == 1 and f'{tenant}.bot.artgents.ru' in calls[0]
    assert fake.inputs[0].model_view.client_id == tenant
    assert current_session_client_id() is None
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id=tenant, sid='host-bound')).state.revision == 1
        other = 'nikadent' if tenant == 'demo' else 'demo'
        assert store.read(SessionKey(client_id=other, sid='host-bound')) is None


@pytest.mark.parametrize('path', ['/ask', '/ask/stream'])
def test_d2_host_body_mismatch_never_calls_provider_or_creates_state(http_env, prod_tenant_boundary, path):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(explanation('Не должен выполняться.'))))
    response = client.post(path, json={'sid':'mismatch','request_id':'r1','q':'Вопрос','client_id':'demo'},
                           base_url=_nikadent_base_url(), headers=_prod_headers(origin=_NIKADENT_ORIGIN))
    assert response.status_code == 403
    assert fake.inputs == [] and not db.exists()


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
