"""Offline checks for the post-REC-3 model-envelope correction."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import build_d2_d1r_messages
from core.one_call_envelope_protocol import production_envelope_template
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from tests.test_d2_live_provider_offline import _request


def test_prompt_keeps_explicit_requests_ahead_of_session_focus() -> None:
    request = replace(
        _request(), user_message="Сколько стоит классическая имплантация и виниры?"
    )
    system, user = build_d2_d1r_messages(request)
    prompt = system["content"]

    assert request.user_message in user["content"]
    assert "Interpret the current USER_MESSAGE before using dialog history" in prompt
    assert "never to replace a service explicitly named now" in prompt
    assert "do not turn them into a choice merely because several service IDs appear" in prompt
    assert "A genuine request to compare or choose among alternatives" in prompt
    assert "current message asks for one price but omits its service" in prompt
    assert "route=ANSWER" in prompt
    assert "Never emit resolved with requested_service_id=null" in prompt
    assert "Keep any other independent requests in their original order" in prompt


def test_resolved_without_id_remains_failed_turn_for_json_and_sse(http_env) -> None:
    client, db, use_provider, _ = http_env
    raw = json.dumps(production_envelope_template(
        route="CLARIFY",
        commercial_intent="price",
        clarify_axis="service",
        clarify_service_options=["classic", "veneers"],
        patient_text="С какой стоимости начать?",
        service_reference_status="resolved",
        requested_service_id=None,
        primary_price_request_id="r1",
        request_understanding={
            "subjects": [],
            "requests": [{
                "request_id": "r1", "kind": "price", "subject_id": None,
                "context": "general_information", "service_id": None,
                "topic_id": None, "statement_mode": "question", "situation": None,
            }],
        },
    ), ensure_ascii=False)
    fake = use_provider(FakeProvider(raw))

    json_response = post(
        client, sid="envelope-invalid-json", request_id="invalid",
        q="Сколько стоит классическая имплантация и виниры?",
    )
    assert json_response.status_code == 400
    assert json_response.get_json() == {"error": "d2_invalid_turn"}

    events = sse_events(post_sse(
        client, sid="envelope-invalid-sse", request_id="invalid",
        q="Сколько стоит классическая имплантация и виниры?",
    ))
    assert [kind for kind, _ in events] == ["status", "error"]
    assert events[-1][1] == {"error": "d2_invalid_turn"}
    assert len(fake.inputs) == 2
    with D2DialogueStore(db) as store:
        for sid in ("envelope-invalid-json", "envelope-invalid-sse"):
            assert store.read(SessionKey(client_id="demo", sid=sid)) is None


@pytest.mark.parametrize(
    ("client_id", "service_id", "service_name"),
    [
        ("demo", "professional_whitening", "Профессиональное отбеливание"),
        ("nikadent", "tooth_extraction", "Удаление зуба"),
    ],
)
def test_http_price_name_comes_from_current_tenant_and_replays(
    http_env, client_id: str, service_id: str, service_name: str
) -> None:
    client, _, use_provider, _ = http_env
    raw = json.dumps(production_envelope_template(
        commercial_intent="price",
        primary_price_request_id="r1",
        request_understanding={
            "subjects": [],
            "requests": [{
                "request_id": "r1", "kind": "price", "subject_id": None,
                "context": "general_information", "service_id": service_id,
                "topic_id": None, "statement_mode": "question", "situation": None,
            }],
        },
    ), ensure_ascii=False)
    fake = use_provider(FakeProvider(raw))
    sid = f"price-label-{client_id}"
    first = post(client, client_id=client_id, sid=sid, request_id="price", q="Цена услуги")
    assert first.status_code == 200
    answer = first.get_json()["answer"]
    assert f"{service_name} — " in answer

    events = sse_events(post_sse(
        client, client_id=client_id, sid=sid, request_id="price", q="Цена услуги"
    ))
    assert [kind for kind, _ in events][-2:] == ["ui", "done"]
    assert events[-2][1]["answer"] == answer
    assert len(fake.inputs) == 1
