from __future__ import annotations

import json
import re
import uuid

import pytest
from flask import Flask, request

from contracts.ui_scope_action import build_ui_scope_ref
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.target_runtime_session import read_target_runtime_session
from evals.v5.run_bot_cleanup_live import compare_ask_stream_payloads
from session import mem_get, mem_reset
from tests.target_runtime_test_support import _seed_followups

UI_REF = build_ui_scope_ref(topic="implantation", extent="one_tooth")
PAYMENT_REF = "price:all_on_4/stages"


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        yield


def test_http_ask_and_stream_scope_click_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    from tests.test_sales_fast_widget_integration import (
        _CountingBackend,
        _install_sales_fast_transport,
    )
    from tests.test_sales_one_plus_turn import answer_envelope

    envelope = answer_envelope("Цена для одного зуба.")

    sid_ask = f"s-parity-ask-{uuid.uuid4().hex[:8]}"
    mem_reset(sid_ask)
    _seed_followups(
        sid_ask,
        TargetRuntimeFollowupItem(ref=UI_REF, label="Один зуб"),
    )
    backend_ask = _CountingBackend(envelope)
    _install_sales_fast_transport(monkeypatch, backend_ask)
    client = app_module.app.test_client()
    ask_resp = client.post(
        "/ask",
        json={"q": "", "ref": UI_REF, "sid": sid_ask, "client_id": "demo"},
    )
    assert ask_resp.status_code == 200
    assert backend_ask.call_count == 1
    ask_payload = ask_resp.get_json()
    ask_session = read_target_runtime_session(sid_ask)

    sid_stream = f"s-parity-stream-{uuid.uuid4().hex[:8]}"
    mem_reset(sid_stream)
    _seed_followups(
        sid_stream,
        TargetRuntimeFollowupItem(ref=UI_REF, label="Один зуб"),
    )
    backend_stream = _CountingBackend(envelope)
    _install_sales_fast_transport(monkeypatch, backend_stream)
    stream_resp = client.post(
        "/ask/stream",
        json={"q": "", "ref": UI_REF, "sid": sid_stream, "client_id": "demo"},
    )
    assert stream_resp.status_code == 200
    text = stream_resp.get_data(as_text=True)
    match = re.search(r"event: ui\ndata: (.+?)\n\n", text)
    assert match is not None
    stream_payload = json.loads(match.group(1))
    assert backend_stream.call_count == 1
    stream_session = read_target_runtime_session(sid_stream)

    assert compare_ask_stream_payloads(ask_payload, stream_payload) == []
    assert ask_session.patient_facts is not None
    assert stream_session.patient_facts is not None
    assert ask_session.patient_facts.extent == stream_session.patient_facts.extent == "one_tooth"
    assert ask_session.patient_facts.ref == stream_session.patient_facts.ref == UI_REF


def test_http_unshown_ui_scope_ref_fail_closed(
    monkeypatch: pytest.MonkeyPatch | None = None,
    flask_ctx=None,
) -> None:
    if monkeypatch is None:
        with pytest.MonkeyPatch.context() as mp:
            _assert_http_unshown_ui_scope_ref_fail_closed(mp)
        return
    _assert_http_unshown_ui_scope_ref_fail_closed(monkeypatch)


def _assert_http_unshown_ui_scope_ref_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app as app_module

    from tests.test_sales_fast_widget_integration import (
        _CountingBackend,
        _install_sales_fast_transport,
    )
    from tests.test_sales_one_plus_turn import answer_envelope

    sid = f"s-ac3-unshown-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    backend = _CountingBackend(answer_envelope("ignored"))
    _install_sales_fast_transport(monkeypatch, backend)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "", "ref": UI_REF, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert backend.call_count == 0
    payload = resp.get_json()
    assert payload["meta"]["service_route"] == "sales_fast_followup_unknown"
    after = read_target_runtime_session(sid)
    assert after.patient_facts is None


def test_http_finance_followup_ref_click(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    from tests.test_sales_fast_widget_integration import (
        _CountingBackend,
        _install_sales_fast_transport,
    )
    from tests.test_sales_one_plus_turn import answer_envelope

    sid = f"s-ac3-pay-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref=PAYMENT_REF, label="Оплата по этапам"),
    )
    backend = _CountingBackend(
        answer_envelope(
            "Оплата по этапам возможна.",
            commercial_intent="payment_stages",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        )
    )
    _install_sales_fast_transport(monkeypatch, backend)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "", "ref": PAYMENT_REF, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert backend.call_count == 1
    payload = resp.get_json()
    assert payload.get("answer")
    user_history = [
        str(item.get("content") or "")
        for item in mem_get(sid).get("hist") or []
        if item.get("role") == "user"
    ]
    assert "Оплата по этапам" in user_history
