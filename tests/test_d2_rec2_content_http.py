"""REC-2: one parser/frozen completion keeps prose separate from source authority."""

from __future__ import annotations

import json

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from tests.test_d2_stage4_mixed_response import _raw as mixed_raw
from tests.test_d2_ui_b12_scenarios import PAIN_FOLLOW, _content_pain_raw


def _content_raw(*, text: str, ref: object = None, sections: object = None,
                 fallback: object = None, service_id: str | None = None,
                 topic_id: str | None = None) -> str:
    part = {
        "request_id": "r1", "kind": "content", "subject_id": None,
        "context": "general_information", "service_id": service_id,
        "topic_id": topic_id, "content_realization": "model_prose",
        "content_text": text, "content_ref": ref,
        "content_section_refs": [] if sections is None else sections,
        "content_fallback_section_ref": fallback,
    }
    return json.dumps(production_envelope_template(
        request_understanding={"subjects": [], "requests": [part]},
    ), ensure_ascii=False)


@pytest.mark.parametrize("ref,sections,fallback", [
    (None, [], None),
    ("missing.md", [], None),
    ("../broken.md", [], None),
    ("implantation__faq__pain.md", ["missing-section"], None),
    ("implantation__faq__pain.md", ["duplicate", "duplicate"], None),
    ("implantation__faq__pain.md", {"not": "a list"}, None),
    ("implantation__faq__pain.md", 42, "orphan"),
    ("implantation__faq__pain.md", [], "missing-section"),
    ("implantation__faq__pain.md", [], 7),
])
def test_optional_bad_provenance_keeps_prose_but_cannot_authorize_ui(
    http_env, ref, sections, fallback,
):
    client, db, use_provider, _ = http_env
    prose = "Ответ о боли после осмотра."
    fake = use_provider(FakeProvider(_content_raw(
        text=prose, ref=ref, sections=sections, fallback=fallback,
    )))
    response = post(client, sid="rec2-provenance", q="Больно ли это?")
    assert response.status_code == 200
    body = response.get_json()
    assert prose in body["answer"]
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="rec2-provenance"))
        assert saved is not None
        part = saved.response.resolved.d2_request_parts[0]
        block = saved.response.resolved.information_blocks[0]
        assert (part.status, part.content_ref, part.content_section_refs) == (
            "answered", None, (),
        )
        assert (block.content_ref, block.source_section_refs, block.display_text) == (
            None, (), prose,
        )
        assert saved.response.resolved.ui_plan.source_content_ref is None
        assert saved.response.ui_projection.video is None
        assert saved.response.ui_projection.quick_replies == ()
        assert saved.response.rendered_text == body["answer"]
        assert store.read(SessionKey(client_id="demo", sid="rec2-provenance")).state.revision == 1
    assert len(fake.inputs) == 1


def test_owned_source_without_typed_focus_keeps_prose_and_ref(http_env):
    client, db, use_provider, _ = http_env
    prose = "Вариант обезболивания обсуждается на консультации."
    fake = use_provider(FakeProvider(_content_raw(
        text=prose, ref="implantation__faq__pain.md",
    )))
    response = post(client, sid="rec2-owned", q="Расскажите об обезболивании")
    assert response.status_code == 200
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="rec2-owned"))
        assert saved is not None
        part = saved.response.resolved.d2_request_parts[0]
        assert part.status == "answered" and part.scope == "clinic"
        assert part.service_id is None and part.topic_id is None
        assert part.content_ref == "implantation__faq__pain.md"
        assert saved.response.resolved.information_blocks[0].content_ref == part.content_ref
        assert saved.response.resolved.ui_plan.source_content_ref == part.content_ref
        assert [item.reply_id for item in saved.response.ui_projection.quick_replies] == [PAIN_FOLLOW]
        assert saved.response.resolved.session_delta.active_service_id is None
        assert prose in saved.response.rendered_text
    assert len(fake.inputs) == 1


def test_locally_incompatible_source_keeps_typed_service_but_not_its_ui(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_content_raw(
        text="Текст о винирах.", ref="implantation__faq__pain.md",
        service_id="veneers", topic_id="prosthetics",
    )))
    response = post(client, sid="rec2-local-mismatch", q="Расскажите о винирах")
    assert response.status_code == 200
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="rec2-local-mismatch"))
        part = saved.response.resolved.d2_request_parts[0]
        assert part.status == "answered" and part.service_id == "veneers"
        assert part.content_ref is None and part.failure_reason is None
        assert saved.response.resolved.information_blocks[0].content_ref is None
        assert saved.response.resolved.ui_plan.source_content_ref is None
        assert "Текст о винирах." in saved.response.rendered_text
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("fact", ["policy", "contact"])
def test_mixed_price_prose_and_exact_fact_keep_one_frozen_plan(http_env, fact):
    client, db, use_provider, _ = http_env
    payload = json.loads(mixed_raw(**{fact: True}))
    payload["request_understanding"]["requests"][1].update({
        "content_ref": "missing.md",
        "content_realization": "model_prose",
        "content_text": "Уточните детали лечения на осмотре; ориентир от 5 000 ₽.",
    })
    fake = use_provider(FakeProvider(json.dumps(payload, ensure_ascii=False)))
    response = post(client, sid=f"rec2-{fact}", request_id="mixed", q="Составной вопрос")
    assert response.status_code == 200
    body = response.get_json()
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid=f"rec2-{fact}"))
        assert saved is not None
        parts = saved.response.resolved.d2_request_parts
        assert [(part.kind, part.status) for part in parts] == [
            ("price", "answered"), ("content", "answered"),
            ("clinic_policy" if fact == "policy" else "contact", "answered"),
        ]
        assert saved.response.resolved.d2_price_block is not None
        assert parts[1].content_ref is None
        assert saved.response.resolved.information_blocks[0].content_ref is None
        assert saved.response.resolved.ui_plan.source_content_ref is None
        assert "от 5 000 ₽" in saved.response.rendered_text
        assert saved.response.rendered_text == body["answer"]
        if fact == "policy":
            assert len(saved.response.resolved.d2_policy_blocks) == 1
        else:
            assert len(saved.response.resolved.d2_contact_blocks) == 1
    assert len(fake.inputs) == 1


def test_authorized_followup_stays_server_owned_when_model_omits_ref(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_content_pain_raw()))
    first = post(client, sid="rec2-follow", request_id="first", q="Я боюсь боли при имплантации")
    assert first.status_code == 200
    shown = first.get_json()
    assert [item["reply_id"] for item in shown["ui"]["quick_replies"]] == [PAIN_FOLLOW]
    fake.raw = _content_raw(text="Дополнительный ответ об анестезии без ссылки модели.")
    second = post(
        client, sid="rec2-follow", request_id="clicked", q="", ref=PAIN_FOLLOW,
        ui_revision=shown["revision"],
    )
    assert second.status_code == 200
    assert "Дополнительный ответ" in second.get_json()["answer"]
    assert len(fake.inputs) == 2
    assert fake.inputs[1].selected_ui_ref.reply_id == PAIN_FOLLOW
    assert fake.inputs[1].selected_ui_ref.source_revision == shown["revision"]
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="rec2-follow")
        saved = store.read_latest_completion(key)
        assert saved is not None and store.read(key).state.revision == 2
        assert saved.response.resolved.d2_request_parts[0].content_ref is None


@pytest.mark.parametrize("raw", [
    _content_raw(text=""),
    json.dumps(production_envelope_template(request_understanding={
        "subjects": [], "requests": [{
            "request_id": "r1", "kind": "content", "subject_id": None,
            "context": "general_information", "content_realization": "authored",
            "content_text": "Неавторизованная цитата",
            "content_ref": "implantation__faq__pain.md",
            "content_section_refs": ["same", "same"],
        }],
    }), ensure_ascii=False),
])
def test_empty_prose_and_malformed_authored_provenance_stay_strict(http_env, raw):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(raw))
    response = post(client, sid="rec2-strict", q="Вопрос")
    assert response.status_code == 400
    assert "answer" not in response.get_json()
    with D2DialogueStore(db) as store:
        assert store.read_latest_completion(SessionKey(client_id="demo", sid="rec2-strict")) is None
    assert len(fake.inputs) == 1


def test_unknown_typed_service_is_not_hidden_by_missing_optional_source(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_content_raw(
        text="Непустой текст не даёт права выдумать услугу.",
        ref="missing.md", service_id="not_in_this_tenant",
    )))
    response = post(client, sid="rec2-unknown-service", q="Расскажите об услуге")
    assert response.status_code != 200
    assert "answer" not in response.get_json()
    with D2DialogueStore(db) as store:
        assert store.read_latest_completion(SessionKey(client_id="demo", sid="rec2-unknown-service")) is None
    assert len(fake.inputs) == 1


def test_unknown_typed_topic_is_not_hidden_by_missing_optional_source(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_content_raw(
        text="Непустой текст не даёт права выдумать направление.",
        ref="missing.md", topic_id="not_in_this_tenant",
    )))
    response = post(client, sid="rec2-unknown-topic", q="Расскажите о направлении")
    assert response.status_code != 200
    assert "answer" not in response.get_json()
    with D2DialogueStore(db) as store:
        assert store.read_latest_completion(SessionKey(client_id="demo", sid="rec2-unknown-topic")) is None
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("first_transport", ["json", "sse"])
def test_money_and_link_prose_freezes_and_replays_across_transports(http_env, first_transport):
    client, db, use_provider, tmp_path = http_env
    prose = "Стоимость от 5 000 ₽. Подробнее [здесь](https://example.test/info)."
    fake = use_provider(FakeProvider(_content_raw(text=prose, ref="missing.md")))
    params = {"sid": "rec2-replay", "request_id": "rec2", "q": "Как это работает?"}
    if first_transport == "json":
        first = post(client, **params)
        assert first.status_code == 200
        body = first.get_json()
    else:
        events = sse_events(post_sse(client, **params))
        assert [name for name, _ in events] == ["status", "typing", "ui", "done"]
        body = dict(events)["ui"]
    assert prose in body["answer"]
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="rec2-replay"))
        assert saved.response.rendered_text == body["answer"]
        assert saved.response.resolved.d2_request_parts[0].failure_reason is None
    (tmp_path / "clients" / "demo" / "clinic_policies.yaml").write_text(
        "policies: {}\n", encoding="utf-8",
    )
    if first_transport == "json":
        replay = dict(sse_events(post_sse(client, **params)))["ui"]
    else:
        replay = post(client, **params).get_json()
    assert replay == body
    assert len(fake.inputs) == 1
