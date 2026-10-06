"""D1R HTTP offline tests with fake backend request_understanding JSON."""

from __future__ import annotations

import uuid
import json

import pytest

from core.clinic_policies_loader import policy_answer
from session import exit_lead_flow, mem_get, session_client_scope
from tests.d1r_envelope_fixtures import (
    envelope_adult_booking_only,
    envelope_booking_plus_contact,
    envelope_child_booking_blocked,
    envelope_clinic_policy_only,
    envelope_content_only,
    envelope_no_subjects_contact_address,
    envelope_pediatric_policy_plus_contact,
)
from tests.test_one_call_tenant_isolation_offline import _enable_demo_nikadent, _post_ask, _post_stream


def _demo_policy_snippet(policy_key: str) -> str:
    text = policy_answer("demo", policy_key) or ""
    assert text.strip()
    return text.split(".")[0].strip().lower()


@pytest.mark.parametrize(
    ("user_message", "policy_key"),
    [
        ("Лечите детей?", "no_pediatric_dentistry"),
        ("Лечите по ОМС?", "no_oms"),
        ("Принимаете ДМС?", "no_dms"),
    ],
)
def test_d1r_policy_http_uses_authored_answer(
    monkeypatch: pytest.MonkeyPatch,
    user_message: str,
    policy_key: str,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-{uuid.uuid4().hex}"
    snippet = _demo_policy_snippet(policy_key)
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message=user_message,
        envelope_json=envelope_clinic_policy_only(policy_key),
        client_id="demo",
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert snippet[:40] in answer or snippet in answer


def test_d1r_contact_without_subjects(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-addr-{uuid.uuid4().hex}"
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Нужна справочная информация по локации",
        envelope_json=envelope_no_subjects_contact_address(),
        client_id="demo",
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert "моск" in answer or "адрес" in answer


def test_d1r_adult_booking_enters_lead_after_one_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-book-{uuid.uuid4().hex}"
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Хочу записаться",
        envelope_json=envelope_adult_booking_only(),
        client_id="demo",
    )
    assert backend.call_count == 1
    with session_client_scope("demo"):
        assert mem_get(sid).get("lead_intent") == "collecting_name"
    assert (payload.get("meta") or {}).get("lead_step") == "name"


def test_d1r_child_booking_blocked_no_lead_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-child-{uuid.uuid4().hex}"
    snippet = _demo_policy_snippet("no_pediatric_dentistry")
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Запишите ребёнка на приём",
        envelope_json=envelope_child_booking_blocked(),
        client_id="demo",
    )
    assert backend.call_count == 1
    with session_client_scope("demo"):
        assert mem_get(sid).get("lead_intent") in (None, "", "none")
    answer = str(payload.get("answer") or "").lower()
    assert snippet[:30] in answer or "дет" in answer


@pytest.mark.parametrize("stream", [False, True])
def test_d1r_old_booking_cannot_restart_after_failed_turn(monkeypatch: pytest.MonkeyPatch, stream: bool) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-stale-{uuid.uuid4().hex}"
    post = _post_stream if stream else _post_ask
    post(monkeypatch, sid=sid, user_message="Запишите меня", envelope_json=envelope_adult_booking_only(), client_id="demo")
    with session_client_scope("demo"):
        exit_lead_flow(sid)
    payload, _ = post(monkeypatch, sid=sid, user_message="Что такое КТ?", envelope_json="INVALID_JSON", client_id="demo")
    assert (payload.get("meta") or {}).get("lead_step") != "name"
    with session_client_scope("demo"):
        assert mem_get(sid).get("lead_intent") != "collecting_name"


@pytest.mark.parametrize("entry", [{"ref": "lead:booking"}, {"cta_action": "lead"}])
def test_d1r_child_denial_rejects_booking_entry(monkeypatch: pytest.MonkeyPatch, entry: dict) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-deny-ui-{uuid.uuid4().hex}"
    _post_ask(monkeypatch, sid=sid, user_message="Запишите ребёнка", envelope_json=envelope_child_booking_blocked(), client_id="demo")
    from app import app
    response = app.test_client().post("/ask", json={"sid": sid, "client_id": "demo", **entry})
    assert response.status_code == 200
    assert (response.get_json().get("meta") or {}).get("lead_step") != "name"
    with session_client_scope("demo"):
        assert mem_get(sid).get("lead_intent") != "collecting_name"


def test_d1r_emitted_booking_cta_accepts_current_click(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-valid-ui-{uuid.uuid4().hex}"
    envelope = json.loads(envelope_content_only("Имплантация заменяет отсутствующий зуб."))
    envelope.update(service_id="all_on_4", requested_service_id="all_on_4", service_reference_status="resolved")
    payload, _ = _post_ask(
        monkeypatch, sid=sid, user_message="Что такое имплантация?",
        envelope_json=json.dumps(envelope, ensure_ascii=False), client_id="demo",
    )
    assert payload.get("cta"), payload
    from app import app
    response = app.test_client().post("/ask", json={"sid": sid, "client_id": "demo", "cta_action": "lead"})
    assert response.status_code == 200
    assert (response.get_json().get("meta") or {}).get("lead_step") == "name"


@pytest.mark.parametrize("client_id", ["demo", "nikadent"])
def test_d1r_forged_booking_ref_has_no_permission(monkeypatch: pytest.MonkeyPatch, client_id: str) -> None:
    _enable_demo_nikadent(monkeypatch)
    from app import app
    sid = f"d1r-forged-{uuid.uuid4().hex}"
    response = app.test_client().post("/ask", json={"sid": sid, "client_id": client_id, "ref": "lead:booking"})
    assert response.status_code == 200
    assert (response.get_json().get("meta") or {}).get("lead_step") != "name"


def test_d1r_booking_permission_is_tenant_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-tenant-ui-{uuid.uuid4().hex}"
    _post_ask(monkeypatch, sid=sid, user_message="Запишите меня", envelope_json=envelope_adult_booking_only(), client_id="demo")
    from app import app
    response = app.test_client().post("/ask", json={"sid": sid, "client_id": "nikadent", "ref": "lead:booking"})
    assert response.status_code == 200
    assert (response.get_json().get("meta") or {}).get("lead_step") != "name"


def test_d1r_price_cta_accepts_current_click(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_demo_nikadent(monkeypatch)
    from core.one_call_envelope_protocol import dumps_production_envelope
    from app import app
    sid = f"d1r-price-ui-{uuid.uuid4().hex}"
    envelope = dumps_production_envelope(
        patient_text=None, service_id="tomography", requested_service_id="tomography",
        service_reference_status="resolved", commercial_intent="price", primary_price_request_id="r1",
        request_understanding={"subjects": [{"subject_id": "s1", "relation": "self", "age_group": "adult"}],
                               "requests": [{"request_id": "r1", "kind": "price", "subject_id": "s1",
                                             "context": "current_care", "policy_ids": [], "payment_scheme": "unspecified",
                                             "payment_scheme_intent": "not_requested", "contact_fields": [], "content_text": None}]},
    )
    payload, backend = _post_ask(monkeypatch, sid=sid, user_message="Сколько стоит КТ взрослому?", envelope_json=envelope, client_id="demo")
    assert backend.call_count == 1
    assert payload.get("cta"), payload
    response = app.test_client().post("/ask", json={"sid": sid, "client_id": "demo", "cta_action": "lead"})
    assert response.status_code == 200
    assert (response.get_json().get("meta") or {}).get("lead_step") == "name"


@pytest.mark.parametrize("entry", [{"cta_action": "lead"}, {"ref": "lead:booking"}])
def test_d1r_cta_with_new_child_request_uses_new_turn(monkeypatch: pytest.MonkeyPatch, entry: dict) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-ui-new-q-{uuid.uuid4().hex}"
    envelope = json.loads(envelope_content_only("Имплантация заменяет отсутствующий зуб."))
    envelope.update(service_id="all_on_4", requested_service_id="all_on_4", service_reference_status="resolved")
    payload, _ = _post_ask(monkeypatch, sid=sid, user_message="Что такое имплантация?", envelope_json=json.dumps(envelope, ensure_ascii=False), client_id="demo")
    assert payload.get("cta")
    from app import app
    from tests.test_one_call_tenant_isolation_offline import _CountingBackend, _install_sales_fast_transport
    backend = _CountingBackend(envelope_child_booking_blocked())
    _install_sales_fast_transport(monkeypatch, backend)
    response = app.test_client().post("/ask", json={"sid": sid, "client_id": "demo", "q": "Запишите ребёнка", **entry})
    assert response.status_code == 200
    assert backend.call_count == 1
    assert (response.get_json().get("meta") or {}).get("lead_step") != "name"


def test_d1r_booking_plus_contact_keeps_both_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-mix-{uuid.uuid4().hex}"
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Запись и справка по локации клиники",
        envelope_json=envelope_booking_plus_contact(),
        client_id="demo",
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert "адрес" in answer or "моск" in answer
    with session_client_scope("demo"):
        assert mem_get(sid).get("lead_intent") == "collecting_name"


@pytest.mark.parametrize("post", [_post_ask, _post_stream], ids=["json", "sse"])
def test_d1r_policy_plus_contact(monkeypatch: pytest.MonkeyPatch, post) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-pol-addr-{uuid.uuid4().hex}"
    snippet = _demo_policy_snippet("no_pediatric_dentistry")
    hostile = "Да, лечим детей. HOSTILE_CHILD_PROMISE"
    raw = envelope_pediatric_policy_plus_contact(hostile)
    assert json.loads(raw)["patient_text"] == hostile
    payload, backend = post(
        monkeypatch,
        sid=sid,
        user_message="Политика по детям и справка по локации",
        envelope_json=raw,
        client_id="demo",
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert snippet[:30] in answer or "дет" in answer
    assert "адрес" in answer or "моск" in answer
    assert "hostile_child_promise" not in answer


def test_d1r_content_plus_policy_block(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-content-{uuid.uuid4().hex}"
    line = "Профессиональная гигиена занимает около часа."
    raw = json.loads(envelope_content_only(line))
    policy_request = json.loads(envelope_clinic_policy_only("no_oms"))["request_understanding"]["requests"][0]
    policy_request["request_id"] = "r2"
    raw["request_understanding"]["requests"].append(policy_request)
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Сколько длится чистка и работаете ли по ОМС?",
        envelope_json=json.dumps(raw, ensure_ascii=False),
        client_id="demo",
    )
    assert backend.call_count == 1
    assert line.split()[0].lower() in str(payload.get("answer") or "").lower()
    assert policy_answer("demo", "no_oms") in payload["answer"]


def test_d1r_policy_stream_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-stream-{uuid.uuid4().hex}"
    snippet = _demo_policy_snippet("no_oms")
    ask_payload, ask_backend = _post_ask(
        monkeypatch,
        sid=f"{sid}-ask",
        user_message="Лечите по ОМС?",
        envelope_json=envelope_clinic_policy_only("no_oms"),
        client_id="demo",
    )
    stream_payload, stream_backend = _post_stream(
        monkeypatch,
        sid=f"{sid}-stream",
        user_message="Лечите по ОМС?",
        envelope_json=envelope_clinic_policy_only("no_oms"),
        client_id="demo",
    )
    assert ask_backend.call_count == 1 and stream_backend.call_count == 1
    assert snippet[:30] in str(ask_payload.get("answer") or "").lower()
    assert snippet[:30] in str(stream_payload.get("answer") or "").lower()
