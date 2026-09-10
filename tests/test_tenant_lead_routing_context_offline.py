"""CP3: tenant-bound lead routing, dialog excerpt, privacy (offline)."""

from __future__ import annotations

import uuid
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

import app as app_module
import config
import core.client_host as client_host
import core.origin_guard as origin_guard
from core.lead_dialog_excerpt import build_lead_dialog_excerpt, mask_email_in_text, sanitize_dialog_line
from core.lead_email import send_lead_email
from lead_service import handle_lead
from session import mem_add_bot, mem_add_user, mem_reset, session_client_scope
from tests.test_sales_one_plus_turn import answer_envelope
from tests.test_sales_fast_widget_integration import _CountingBackend, _install_sales_fast_transport
from tests.test_tenant_ingress_prod_boundary_offline import (
    _demo_base_url,
    _nikadent_base_url,
    _prod_headers,
    isolated_sqlite_paths,
    prod_tenant_boundary,
)

_CLINIC_A = "clinic-a-lead@example.test"
_CLINIC_B = "clinic-b-lead@example.test"


def _cfg_a() -> dict:
    return {
        "recipients": [_CLINIC_A],
        "subject_template": "Lead A",
        "store_in_postgres": False,
    }


def _cfg_b() -> dict:
    return {
        "recipients": [_CLINIC_B],
        "subject_template": "Lead B",
        "store_in_postgres": False,
    }


def _capture_send(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    sent: list[dict] = []

    def _fake_send(*, client_id, lead_cfg, **fields):
        sent.append({"client_id": client_id, "lead_cfg": dict(lead_cfg), **fields})
        return True, "email"

    monkeypatch.setattr("lead_service.send_lead_email", _fake_send)
    return sent


@patch("lead_service.leads_enabled", return_value=True)
@patch("lead_service.leads_mode", return_value="email")
def test_lead_path_reuses_send_lead_email_not_parallel_sender(
    _mode,
    _enabled,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_send = send_lead_email
    calls: list[str] = []

    def _spy(*, client_id, lead_cfg, **fields):
        calls.append("send_lead_email")
        return real_send(client_id=client_id, lead_cfg=lead_cfg, **fields)

    monkeypatch.setattr("lead_service.send_lead_email", _spy)
    monkeypatch.setattr("lead_service.load_lead_config", lambda _cid: _cfg_a())
    monkeypatch.setattr("core.lead_email.smtp_configured", lambda: False)

    payload, status = handle_lead(
        {"name": "A", "phone": "+79001112233", "intent": "lead", "sid": "s1"},
        client_id="demo",
    )
    assert status == 200
    assert calls == ["send_lead_email"]
    assert payload["delivery_status"] == "email_smtp_not_configured"


@patch("lead_service.leads_enabled", return_value=True)
@patch("lead_service.leads_mode", return_value="email")
def test_recipients_clinic_a_only(
    _mode,
    _enabled,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = _capture_send(monkeypatch)
    monkeypatch.setattr("lead_service.load_lead_config", lambda cid: _cfg_a() if cid == "demo" else _cfg_b())

    handle_lead(
        {
            "name": "A",
            "phone": "+79001112233",
            "intent": "lead",
            "sid": "s-a",
            "recipient": "evil@example",
            "email_to": "evil@example",
        },
        client_id="demo",
    )
    assert sent[0]["client_id"] == "demo"
    assert sent[0]["lead_cfg"]["recipients"] == [_CLINIC_A]


@patch("lead_service.leads_enabled", return_value=True)
@patch("lead_service.leads_mode", return_value="email")
def test_recipients_clinic_b_only(
    _mode,
    _enabled,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = _capture_send(monkeypatch)
    monkeypatch.setattr("lead_service.load_lead_config", lambda cid: _cfg_a() if cid == "demo" else _cfg_b())

    handle_lead(
        {"name": "B", "phone": "+79002223344", "intent": "lead", "sid": "s-b"},
        client_id="nikadent",
    )
    assert sent[0]["client_id"] == "nikadent"
    assert sent[0]["lead_cfg"]["recipients"] == [_CLINIC_B]


@patch("lead_service.leads_enabled", return_value=True)
@patch("lead_service.leads_mode", return_value="email")
@pytest.mark.parametrize("first,second", [("demo", "nikadent"), ("nikadent", "demo")])
def test_recipient_routing_cache_warm_order_irrelevant(
    _mode,
    _enabled,
    first: str,
    second: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = _capture_send(monkeypatch)
    monkeypatch.setattr("lead_service.load_lead_config", lambda cid: _cfg_a() if cid == "demo" else _cfg_b())

    handle_lead({"phone": "+79001112233", "sid": "w1"}, client_id=first)
    handle_lead({"phone": "+79001112244", "sid": "w2"}, client_id=second)
    demo_rows = [x for x in sent if x["client_id"] == "demo"]
    nika_rows = [x for x in sent if x["client_id"] == "nikadent"]
    assert demo_rows[0]["lead_cfg"]["recipients"] == [_CLINIC_A]
    assert nika_rows[0]["lead_cfg"]["recipients"] == [_CLINIC_B]


@patch("lead_service.leads_enabled", return_value=True)
@patch("lead_service.leads_mode", return_value="email")
def test_no_recipients_honest_status_no_demo_fallback(
    _mode,
    _enabled,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "lead_service.load_lead_config",
        lambda _cid: {"recipients": [], "subject_template": "x"},
    )
    payload, status = handle_lead({"phone": "+79001112233", "sid": "s0"}, client_id="nikadent")
    assert status == 200
    assert payload["delivery_status"] == "email_no_recipients"


@patch("lead_service.leads_enabled", return_value=True)
@patch("lead_service.leads_mode", return_value="email")
def test_same_sid_cross_tenant_dialog_isolation(
    _mode,
    _enabled,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = _capture_send(monkeypatch)
    monkeypatch.setattr("lead_service.load_lead_config", lambda cid: _cfg_a() if cid == "demo" else _cfg_b())
    sid = f"shared-{uuid.uuid4().hex[:8]}"
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        mem_add_user(sid, "Маркер DEMO_ONLY_4500")
        mem_add_bot(sid, "Ответ demo")
    with session_client_scope("nikadent"):
        mem_reset(sid, client_id="nikadent")
        mem_add_user(sid, "Маркер NIKADENT_ONLY_5000")
        mem_add_bot(sid, "Ответ nikadent")

    handle_lead({"phone": "+79001112233", "sid": sid}, client_id="demo")
    handle_lead({"phone": "+79002223344", "sid": sid}, client_id="nikadent")

    demo_body = sent[0]["dialog_excerpt"]
    nika_body = sent[1]["dialog_excerpt"]
    assert "DEMO_ONLY_4500" in demo_body
    assert "NIKADENT_ONLY_5000" not in demo_body
    assert "NIKADENT_ONLY_5000" in nika_body
    assert "DEMO_ONLY_4500" not in nika_body


def test_dialog_excerpt_roles_and_sanitize() -> None:
    sid = f"excerpt-{uuid.uuid4().hex[:8]}"
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        mem_add_user(sid, "Сколько стоит имплант 4500? Пишите me@secret.test +79001234567")
        mem_add_bot(sid, "Цена от 4500 руб.")
    excerpt = build_lead_dialog_excerpt("demo", sid, max_messages=6)
    assert "Пациент:" in excerpt or "user:" not in excerpt
    assert "4500" in excerpt
    assert "me@secret.test" not in excerpt
    assert "[email скрыт]" in excerpt
    assert "+79001234567" not in excerpt


def test_dialog_excerpt_empty_history_stable_dash_in_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = _capture_send(monkeypatch)
    monkeypatch.setattr("lead_service.leads_enabled", lambda _cid: True)
    monkeypatch.setattr("lead_service.leads_mode", lambda _cid: "email")
    monkeypatch.setattr("lead_service.load_lead_config", lambda _cid: _cfg_a())
    handle_lead({"phone": "+79001112233", "sid": "empty-hist"}, client_id="demo")
    assert sent[0]["dialog_excerpt"] == "—"


def test_frontend_dialog_context_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = _capture_send(monkeypatch)
    monkeypatch.setattr("lead_service.leads_enabled", lambda _cid: True)
    monkeypatch.setattr("lead_service.leads_mode", lambda _cid: "email")
    monkeypatch.setattr("lead_service.load_lead_config", lambda _cid: _cfg_a())
    handle_lead(
        {
            "phone": "+79001112233",
            "sid": "s-x",
            "dialog_context": "Пациент: FRONTEND_INJECTED",
            "transcript": "FRONTEND_INJECTED",
        },
        client_id="demo",
    )
    assert "FRONTEND_INJECTED" not in sent[0]["dialog_excerpt"]


def test_trusted_client_id_kwarg_ignores_spoofed_body_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = _capture_send(monkeypatch)
    monkeypatch.setattr("lead_service.leads_enabled", lambda _cid: True)
    monkeypatch.setattr("lead_service.leads_mode", lambda _cid: "email")
    monkeypatch.setattr("lead_service.load_lead_config", lambda cid: _cfg_a() if cid == "demo" else _cfg_b())
    handle_lead(
        {"phone": "+79001112233", "sid": "s-spoof", "client_id": "nikadent"},
        client_id="demo",
    )
    assert sent[0]["client_id"] == "demo"
    assert sent[0]["lead_cfg"]["recipients"] == [_CLINIC_A]


def test_handle_lead_invalid_tenant_403() -> None:
    payload, status = handle_lead({"phone": "+79001112233"}, client_id="_template")
    assert status == 403
    assert payload["error_code"] == "unknown_client"


def test_unknown_clinic_pack_403_no_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    side_effects: list[str] = []

    monkeypatch.setattr(
        "lead_service.send_lead_email",
        lambda **_k: side_effects.append("send") or (True, "email"),
    )
    monkeypatch.setattr(
        "lead_service.build_lead_dialog_excerpt",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not read session")),
    )
    monkeypatch.setattr(
        "lead_service._emit_lead_event",
        lambda **_k: side_effects.append("event"),
    )

    payload, status = handle_lead({"phone": "+79001112233", "sid": "s-u"}, client_id="unknown-clinic")
    assert status == 403
    assert payload["error_code"] == "unknown_client"
    assert side_effects == []


def test_handle_lead_does_not_mutate_input_data() -> None:
    data = {
        "phone": "+79001112233",
        "client_id": "nikadent",
        "recipient": "evil@example",
        "dialog_context": "injected",
        "intent": "ignored",
    }
    snapshot = dict(data)
    handle_lead(data, client_id="demo")
    assert data == snapshot


@patch("pg_sink.enqueue_lead")
@patch("lead_service.leads_enabled", return_value=True)
@patch("lead_service.leads_mode", return_value="email")
def test_forged_intent_not_in_email_pg_or_event(
    _mode,
    _enabled,
    mock_pg,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "INTENT_FORGED_SECRET_998877"
    sent = _capture_send(monkeypatch)
    captured_events: list[dict] = []

    monkeypatch.setattr(
        "lead_service.load_lead_config",
        lambda _cid: {**_cfg_a(), "store_in_postgres": True},
    )
    monkeypatch.setattr(
        "lead_service._emit_lead_event",
        lambda **kwargs: captured_events.append(kwargs),
    )

    handle_lead(
        {
            "phone": "+79001112233",
            "intent": f"{secret} +79005556677 evil@test.com",
            "sid": "s-forge",
        },
        client_id="demo",
    )
    assert sent[0]["intent"] == "lead"
    mock_pg.assert_called_once()
    row = mock_pg.call_args[0][0]
    assert row["topic"] == "lead"
    assert secret not in str(row)
    assert secret not in str(captured_events)
    assert "+79005556677" not in str(captured_events)


def test_long_last_message_excerpt_truncated_not_empty() -> None:
    from core.lead_dialog_excerpt import LEAD_DIALOG_EXCERPT_MAX_CHARS, build_lead_dialog_excerpt

    sid = f"long-{uuid.uuid4().hex[:8]}"
    tail_marker = "ENDMARKER_UNIQUE_TAIL"
    long_text = ("префикс " * 400) + tail_marker
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        mem_add_user(sid, long_text)
    excerpt = build_lead_dialog_excerpt("demo", sid, max_messages=1)
    assert excerpt.strip()
    assert len(excerpt) <= LEAD_DIALOG_EXCERPT_MAX_CHARS
    assert tail_marker in excerpt

@patch.dict(
    "os.environ",
    {"SMTP_HOST": "smtp.test", "SMTP_FROM": "bot@test", "SMTP_PASSWORD": "x"},
    clear=False,
)
@patch("core.lead_email._connect_smtp")
def test_smtp_body_has_lead_phone_excerpt_masks_contacts(mock_connect: MagicMock) -> None:
    mock_smtp = MagicMock()
    mock_connect.return_value.__enter__.return_value = mock_smtp
    ok, _ = send_lead_email(
        client_id="demo",
        lead_cfg={"recipients": ["inbox@test"], "subject_template": "T"},
        name="Anna",
        phone="+79007654321",
        intent="lead",
        situation_note="note",
        dialog_excerpt="Пациент: call +79009998877",
        sid="s",
        request_id="r",
        captured_at="2026-01-01T00:00:00+00:00",
    )
    assert ok is True
    msg: EmailMessage = mock_smtp.send_message.call_args[0][0]
    body = msg.get_content()
    assert "+79007654321" in body
    assert "Anna" in body
    assert "+79009998877" not in body


@patch("lead_service.leads_enabled", return_value=True)
@patch("lead_service.leads_mode", return_value="email")
@patch("pg_sink.enqueue_lead")
def test_pg_and_bot_event_have_no_pii_or_excerpt(
    mock_pg,
    _mode,
    _enabled,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []

    def _fake_emit(_logger, event_name, **kwargs):
        captured.append({"event": event_name, **kwargs})

    monkeypatch.setattr("lead_service.emit_bot_event", _fake_emit)
    monkeypatch.setattr(
        "lead_service.load_lead_config",
        lambda _cid: {"recipients": [_CLINIC_A], "store_in_postgres": True},
    )
    monkeypatch.setattr("lead_service.send_lead_email", lambda **_k: (True, "email"))
    sid = f"priv-{uuid.uuid4().hex[:8]}"
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        mem_add_user(sid, "Секретная история 4500")

    handle_lead(
        {
            "name": "SecretName",
            "phone": "+79001234567",
            "situation_note": "Secret situation",
            "sid": sid,
        },
        client_id="demo",
    )
    mock_pg.assert_called_once()
    row = mock_pg.call_args[0][0]
    assert row["name"] is None
    assert row["phone"] is None
    details = captured[0]["details"]
    assert "SecretName" not in str(details)
    assert "Secret situation" not in str(details)
    assert "Секретная история" not in str(details)
    assert details.get("has_dialog_excerpt") is True


def test_lead_post_zero_provider_calls(
    prod_tenant_boundary,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    backend = _CountingBackend(answer_envelope("must not run"))
    _install_sales_fast_transport(monkeypatch, backend)
    sqlite_fn, _ = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_fn)
    monkeypatch.setattr("lead_service.send_lead_email", lambda **_k: (True, "email_sent"))
    monkeypatch.setattr("lead_service.leads_mode", lambda _cid: "email")
    resp = app_module.app.test_client().post(
        "/lead",
        json={"phone": "+79001112233", "sid": "s-provider", "client_id": "nikadent"},
        base_url=_nikadent_base_url(),
        headers=_prod_headers(origin="https://nikadent.bot.artgents.ru"),
    )
    assert resp.status_code == 200
    assert backend.call_count == 0


def test_mask_email_preserves_service_price_text() -> None:
    line = sanitize_dialog_line("Имплант от 4500 руб, пишите a@b.co")
    assert "4500" in line
    assert "a@b.co" not in line


@patch.dict("os.environ", {"SMTP_HOST": "smtp.test", "SMTP_FROM": "bot@test"}, clear=False)
@patch("core.lead_email._connect_smtp", side_effect=RuntimeError("smtp down"))
def test_smtp_failure_logs_without_message_body(mock_connect, caplog) -> None:
    secret = "UNIQUE_LEAD_BODY_SECRET_12345"
    send_lead_email(
        client_id="demo",
        lead_cfg={"recipients": ["inbox@test"]},
        name=secret,
        phone="+79001234567",
        intent="lead",
        situation_note="sit",
        dialog_excerpt=f"Пациент: {secret}",
        sid="s",
        request_id="r",
        captured_at="2026-01-01T00:00:00+00:00",
    )
    blob = caplog.text
    assert secret not in blob
    assert "+79001234567" not in blob
