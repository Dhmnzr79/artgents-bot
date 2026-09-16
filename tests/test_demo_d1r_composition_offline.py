"""Regression coverage for D1R price composition and free-text contact routing."""
from __future__ import annotations

import json
import uuid

import pytest

from session import mem_get, session_client_scope
from core.clinic_policies_loader import policy_answer
from core.one_call_envelope_protocol import production_envelope_template
from tests.test_one_call_tenant_isolation_offline import (
    _enable_demo_nikadent, _post_ask, _post_stream,
)


def _req(rid, kind, subject=None, **fields):
    value = dict(request_id=rid, kind=kind, subject_id=subject,
                context="current_care", policy_ids=[], payment_scheme="unspecified",
                payment_scheme_intent="unspecified", contact_fields=[],
                content_text=None)
    value.update(fields)
    return value


def _envelope(requests, subjects=(), *, price=True, hostile=None):
    fields = dict(patient_text=hostile,
                  request_understanding=dict(subjects=list(subjects), requests=requests))
    if price:
        fields.update(service_id="tomography", requested_service_id="tomography",
                      service_reference_status="resolved", commercial_intent="price",
                      primary_price_request_id="r2")
    return json.dumps(production_envelope_template(**fields), ensure_ascii=False)



@pytest.mark.parametrize("post", [_post_ask, _post_stream], ids=["json", "sse"])
@pytest.mark.parametrize("parts", [(), ("policy",), ("content",), ("policy", "contact", "content")])
def test_primary_price_composes_every_requested_part(monkeypatch, post, parts):
    _enable_demo_nikadent(monkeypatch)
    requests = [_req("r2", "price")]
    content = "Томография помогает врачу оценить состояние костной ткани."
    if "policy" in parts:
        requests.insert(0, _req("r1", "clinic_policy", policy_ids=["no_oms"]))
    if "contact" in parts:
        requests.append(_req("r3", "contact", contact_fields=["contact_address"]))
    if "content" in parts:
        requests.append(_req("r4", "content", content_text=content))
    payload, backend = post(monkeypatch, sid=f"compose-{uuid.uuid4().hex}",
        user_message="Где находитесь, принимаете по ОМС и сколько стоит КТ?" if "contact" in parts else "Сколько стоит КТ?",
        envelope_json=_envelope(requests), client_id="demo")
    text = str(payload.get("answer") or "")
    assert backend.call_count == 1
    assert "3000" in "".join(text.split()).replace("\u00a0", "")
    if "policy" in parts:
        assert text.count(policy_answer("demo", "no_oms").strip()) == 1
    if "contact" in parts:
        assert "моск" in text.lower() or "адрес" in text.lower()
    if "content" in parts:
        assert text.count(content) == 1


@pytest.mark.parametrize("post", [_post_ask, _post_stream], ids=["json", "sse"])
@pytest.mark.parametrize("prior_adult_price", [False, True])
def test_child_price_does_not_materialize_forbidden_offer(monkeypatch, post, prior_adult_price):
    _enable_demo_nikadent(monkeypatch)
    sid = f"blocked-{uuid.uuid4().hex}"
    if prior_adult_price:
        previous, previous_backend = post(monkeypatch, sid=sid,
            user_message="Сколько стоит КТ взрослому?",
            envelope_json=_envelope([_req("r2", "price")]), client_id="demo")
        assert previous_backend.call_count == 1
        assert "3000" in "".join(str(previous["answer"]).split())
        with session_client_scope("demo"):
            assert mem_get(sid)["target_runtime_state"]["last_selected_offer_id"]
    from core import one_call_presentation_pass as presentation
    def forbidden(*args, **kwargs):
        pytest.fail("Blocked primary price reached commerce materialization")
    monkeypatch.setattr(presentation, "build_precomposer_single_offer_commerce", forbidden)
    requests = [_req("r2", "price", "s1"),
                _req("r3", "contact", contact_fields=["contact_address"])]
    payload, backend = post(monkeypatch, sid=sid,
        user_message="Сколько стоит КТ ребёнку и где вы находитесь?",
        envelope_json=_envelope(requests, [dict(subject_id="s1", relation="other", age_group="child")]),
        client_id="demo")
    text = str(payload.get("answer") or "")
    assert backend.call_count == 1
    assert policy_answer("demo", "no_pediatric_dentistry").strip() in text
    assert "моск" in text.lower() or "адрес" in text.lower()
    assert "3000" not in "".join(json.dumps(payload, ensure_ascii=False).split())
    with session_client_scope("demo"):
        state = mem_get(sid)
        snapshot = state.get("validated_understanding") or {}
        assert snapshot
        runtime = state.get("target_runtime_state") or {}
        assert not runtime.get("last_selected_offer_id")
        assert not runtime.get("last_displayed_offer_ids")
    assert "lead:booking" not in json.dumps(payload)
    assert (payload.get("meta") or {}).get("lead_step") is None


@pytest.mark.parametrize("post", [_post_ask, _post_stream], ids=["json", "sse"])
def test_plain_contact_question_uses_one_model_understanding(monkeypatch, post):
    _enable_demo_nikadent(monkeypatch)
    payload, backend = post(monkeypatch, sid=f"contact-{uuid.uuid4().hex}",
        user_message="Где вы находитесь?",
        envelope_json=_envelope([_req("r1", "contact", contact_fields=["contact_address"])], price=False),
        client_id="demo")
    assert backend.call_count == 1
    assert "моск" in str(payload.get("answer") or "").lower()


@pytest.mark.parametrize("post", [_post_ask, _post_stream], ids=["json", "sse"])
def test_model_price_prose_is_not_a_price_source(monkeypatch, post):
    _enable_demo_nikadent(monkeypatch)
    payload, backend = post(monkeypatch, sid=f"hostile-{uuid.uuid4().hex}",
        user_message="Сколько стоит КТ?",
        envelope_json=_envelope([_req("r2", "price")], hostile="КТ стоит 999999 рублей. SECRET_PRICE"),
        client_id="demo")
    assert backend.call_count == 1
    text = str(payload.get("answer") or "")
    assert "3000" in "".join(text.split())
    assert "999999" not in text and "SECRET_PRICE" not in text


@pytest.mark.parametrize("post", [_post_ask, _post_stream], ids=["json", "sse"])
def test_oms_booking_payment_fact_blocks_lead(monkeypatch, post):
    _enable_demo_nikadent(monkeypatch)
    payload, backend = post(monkeypatch, sid=f"oms-book-{uuid.uuid4().hex}",
        user_message="Запишите меня на лечение по ОМС",
        envelope_json=_envelope([_req("r1", "booking", payment_scheme="oms",
            payment_scheme_intent="requested_payment")], price=False), client_id="demo")
    assert backend.call_count == 1
    assert policy_answer("demo", "no_oms").strip() in str(payload.get("answer") or "")
    assert (payload.get("meta") or {}).get("lead_step") is None
    assert "lead:booking" not in json.dumps(payload)


@pytest.mark.parametrize("post", [_post_ask, _post_stream], ids=["json", "sse"])
def test_oms_eligibility_without_policy_id_gets_authored_answer(monkeypatch, post):
    _enable_demo_nikadent(monkeypatch)
    payload, backend = post(monkeypatch, sid=f"oms-elig-{uuid.uuid4().hex}",
        user_message="Работаете по ОМС?",
        envelope_json=_envelope([_req("r1", "clinic_policy", context="general_information",
            payment_scheme="oms", payment_scheme_intent="eligibility_question")], price=False),
        client_id="demo")
    assert backend.call_count == 1
    assert policy_answer("demo", "no_oms").strip() in str(payload.get("answer") or "")


@pytest.mark.parametrize("post", [_post_ask, _post_stream], ids=["json", "sse"])
def test_requested_dms_price_has_no_offer(monkeypatch, post):
    _enable_demo_nikadent(monkeypatch)
    payload, backend = post(monkeypatch, sid=f"dms-price-{uuid.uuid4().hex}",
        user_message="Сколько стоит КТ по ДМС?",
        envelope_json=_envelope([_req("r2", "price", payment_scheme="dms",
            payment_scheme_intent="requested_payment")]), client_id="demo")
    assert backend.call_count == 1
    assert policy_answer("demo", "no_dms").strip() in str(payload.get("answer") or "")
    assert "3000" not in "".join(json.dumps(payload, ensure_ascii=False).split())
    assert "lead:booking" not in json.dumps(payload)


@pytest.mark.parametrize("post", [_post_ask, _post_stream], ids=["json", "sse"])
def test_missing_payment_rule_price_asks_for_confirmation_without_offer(monkeypatch, post):
    _enable_demo_nikadent(monkeypatch)
    from core import clinic_policy_resolver as resolver
    monkeypatch.setattr(resolver, "_pack_policy_keys", lambda _client_id: frozenset())
    payload, backend = post(monkeypatch, sid=f"missing-rule-{uuid.uuid4().hex}",
        user_message="Сколько стоит КТ по ДМС?",
        envelope_json=_envelope([_req("r2", "price", payment_scheme="dms",
            payment_scheme_intent="requested_payment")]), client_id="demo")
    assert backend.call_count == 1
    text = str(payload.get("answer") or "")
    assert "Не могу подтвердить" in text
    assert "3000" not in "".join(json.dumps(payload, ensure_ascii=False).split())
    assert "lead:booking" not in json.dumps(payload)


@pytest.mark.parametrize("post", [_post_ask, _post_stream], ids=["json", "sse"])
def test_missing_policy_rule_returns_honest_answer(monkeypatch, post):
    _enable_demo_nikadent(monkeypatch)
    from core import clinic_policy_resolver as resolver
    monkeypatch.setattr(resolver, "_pack_policy_keys", lambda _client_id: frozenset())
    payload, backend = post(monkeypatch, sid=f"unknown-rule-{uuid.uuid4().hex}",
        user_message="Работаете по ОМС?",
        envelope_json=_envelope([_req("r1", "clinic_policy", context="general_information",
            payment_scheme="oms", payment_scheme_intent="eligibility_question")], price=False),
        client_id="demo")
    assert backend.call_count == 1
    text = str(payload.get("answer") or "")
    assert "Не могу подтвердить" in text
    assert policy_answer("demo", "no_oms").strip() not in text


@pytest.mark.parametrize("post", [_post_ask, _post_stream], ids=["json", "sse"])
def test_secondary_price_is_explicitly_deferred_with_primary_amount(monkeypatch, post):
    _enable_demo_nikadent(monkeypatch)
    payload, backend = post(monkeypatch, sid=f"two-prices-{uuid.uuid4().hex}",
        user_message="Сколько стоят КТ и коронка?",
        envelope_json=_envelope([_req("r2", "price"), _req("r3", "price")]),
        client_id="demo")
    assert backend.call_count == 1
    text = str(payload.get("answer") or "")
    assert "3000" in "".join(text.split())
    assert text.count("Стоимость остальных услуг уточним отдельно") == 1


def test_composer_ledger_records_rendered_and_deferred_requests() -> None:
    from contracts.request_understanding import RequestUnderstanding
    from core.one_call_response_composition import compose_response_from_understanding
    understanding = RequestUnderstanding.model_validate(dict(subjects=[], requests=[
        _req("r1", "clinic_policy", policy_ids=["no_oms"]),
        _req("r2", "price"),
        _req("r3", "price"),
        _req("r4", "content"),
        _req("r5", "contact"),
    ]))
    result = compose_response_from_understanding(client_id="demo", understanding=understanding,
        primary_price_request_id="r2", primary_price_text="КТ — 3000 ₽")
    assert [(entry.request_id, entry.status) for entry in result.resolution.ledger] == [
        ("r1", "answered"), ("r2", "answered"), ("r3", "clarification_needed"),
        ("r4", "clarification_needed"), ("r5", "clarification_needed"),
    ]
    assert all(entry.text for entry in result.resolution.ledger)
    assert result.patient_text.count("3000") == 1


@pytest.mark.parametrize("post", [_post_ask, _post_stream], ids=["json", "sse"])
def test_partial_clarification_preserves_policy_contact_and_question(monkeypatch, post):
    _enable_demo_nikadent(monkeypatch)
    sid = f"partial-{uuid.uuid4().hex}"
    fields = dict(route="CLARIFY", patient_text="Верхняя или нижняя челюсть?",
        service_id="all_on_4", requested_service_id="all_on_4",
        service_reference_status="resolved", commercial_intent="price",
        clarify_axis="jaw", primary_price_request_id="r2",
        request_understanding=dict(subjects=[], requests=[
            _req("r1", "clinic_policy", policy_ids=["no_oms"]),
            _req("r2", "price"),
            _req("r3", "contact", contact_fields=["contact_address"]),
        ]))
    envelope_json = json.dumps(production_envelope_template(**fields), ensure_ascii=False)
    payload, backend = post(monkeypatch, sid=sid,
        user_message="По ОМС работаете, где вы и сколько стоит All-on-4?",
        envelope_json=envelope_json, client_id="demo")
    assert backend.call_count == 1
    text = str(payload.get("answer") or "")
    assert policy_answer("demo", "no_oms").strip() in text
    assert "Верхняя или нижняя челюсть?" in text
    assert "моск" in text.lower() or "адрес" in text.lower()
    assert "3000" not in "".join(json.dumps(payload, ensure_ascii=False).split())
    with session_client_scope("demo"):
        snapshot = mem_get(sid).get("validated_understanding") or {}
    assert {entry["request_id"]: entry["status"] for entry in snapshot.get("ledger", [])} == {
        "r1": "answered", "r2": "clarification_needed", "r3": "answered",
    }
