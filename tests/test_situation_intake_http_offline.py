"""HTTP offline tests for situation intake flow."""

from __future__ import annotations

import uuid

import pytest
from flask import Flask, request

from core.observability_pii import is_pii_withheld_route, observability_user_texts
from flow_handlers import handle_flows
from session import mem_get, mem_reset


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        yield


def _txt() -> dict[str, str]:
    return {
        "situation_prompt": "Опишите ситуацию.",
        "situation_retry_short": "Напишите чуть подробнее.",
        "situation_to_lead_name": "Как к вам обращаться?",
        "situation_back_fallback": "Вернулись к ответу.",
    }


def _service_payload(answer, sid, client_id, **kwargs):
    from orchestration.lead_flow import build_service_payload

    return build_service_payload(answer, sid, client_id, **kwargs)


def test_situation_start_sets_pending(flask_ctx) -> None:
    sid = f"s-sit-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    result = handle_flows(
        data={"situation_action": "start", "client_id": "demo"},
        st=mem_get(sid),
        sid=sid,
        q="",
        client_id="demo",
        txt=_txt(),
        service_payload=_service_payload,
        get_last_content_ui_payload=lambda _sid: None,
        get_topic_state=lambda _sid, _doc: {},
    )
    assert result is not None
    assert result["payload"]["situation"]["mode"] == "pending"
    assert result["payload"]["meta"]["situation_collect"] is True
    assert mem_get(sid).get("situation_pending") is True


def test_situation_back_clears_pending(flask_ctx) -> None:
    sid = f"s-back-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    st = mem_get(sid)
    st["situation_pending"] = True
    result = handle_flows(
        data={"situation_action": "back"},
        st=st,
        sid=sid,
        q="",
        client_id="demo",
        txt=_txt(),
        service_payload=_service_payload,
        get_last_content_ui_payload=lambda _sid: {"answer": "prev", "quick_replies": []},
        get_topic_state=lambda _sid, _doc: {},
    )
    assert result is not None
    assert mem_get(sid).get("situation_pending") is False
    assert result["payload"]["meta"].get("situation_back") is True


def test_situation_submit_moves_to_lead_name(flask_ctx) -> None:
    sid = f"s-sub-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    st = mem_get(sid)
    st["situation_pending"] = True
    result = handle_flows(
        data={},
        st=st,
        sid=sid,
        q="Нужна консультация по имплантации",
        client_id="demo",
        txt=_txt(),
        service_payload=_service_payload,
        get_last_content_ui_payload=lambda _sid: None,
        get_topic_state=lambda _sid, _doc: {},
    )
    assert result is not None
    assert mem_get(sid).get("situation_pending") is False
    assert mem_get(sid).get("lead_intent") == "collecting_name"
    assert result["payload"]["meta"]["lead_flow"] is True


def test_situation_sid_isolation(flask_ctx) -> None:
    sid_a = f"s-a-{uuid.uuid4().hex[:8]}"
    sid_b = f"s-b-{uuid.uuid4().hex[:8]}"
    mem_reset(sid_a)
    mem_reset(sid_b)
    handle_flows(
        data={"situation_action": "start"},
        st=mem_get(sid_a),
        sid=sid_a,
        q="",
        client_id="demo",
        txt=_txt(),
        service_payload=_service_payload,
        get_last_content_ui_payload=lambda _sid: None,
        get_topic_state=lambda _sid, _doc: {},
    )
    assert mem_get(sid_a).get("situation_pending") is True
    assert mem_get(sid_b).get("situation_pending") is not True


def test_situation_collect_pii_withheld() -> None:
    withheld = is_pii_withheld_route("situation_collect", {"situation_collect": True})
    assert withheld is True
    user, _preview, flag = observability_user_texts(
        "секретная ситуация",
        route="situation_collect",
        meta={"situation_collect": True},
    )
    assert flag is True


def test_lead_submit_demo_stub_no_external_send() -> None:
    from lead_service import handle_lead

    payload, status = handle_lead(
        {
            "client_id": "demo",
            "name": "Иван",
            "phone": "+79001234567",
            "intent": "lead",
        }
    )
    assert status == 200
    assert payload["delivery"] == "demo_stub"
