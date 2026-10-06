"""REC-3: persisted focus through real offline D2 JSON/SSE endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from contracts.response_plan import D2_PRICE_DEFERRAL_TEXT, SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template
from tests.d1r_envelope_fixtures import envelope_clinic_policy_only
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events


def _price_part(request_id: str, service_id: str | None, topic_id: str | None = None) -> dict:
    return {
        "request_id": request_id, "kind": "price", "subject_id": None,
        "context": "general_information", "service_id": service_id,
        "topic_id": topic_id, "statement_mode": "question", "situation": None,
    }


def _price_raw(*parts: dict) -> str:
    return json.dumps(production_envelope_template(
        commercial_intent="price",
        primary_price_request_id=parts[0]["request_id"],
        request_understanding={"subjects": [], "requests": list(parts)},
    ), ensure_ascii=False)


def _service_clarify_raw(*service_ids: str) -> str:
    return json.dumps(production_envelope_template(
        route="CLARIFY", patient_text="Какую услугу уточнить?",
        clarify_axis="service", clarify_service_options=list(service_ids),
        commercial_intent="none",
        request_understanding={
            "subjects": [], "requests": [_price_part("r1", None)],
        },
    ), ensure_ascii=False)


def _extent_clarify_raw() -> str:
    return json.dumps(production_envelope_template(
        route="CLARIFY", patient_text="Какой объём вы имеете в виду?",
        clarify_axis="extent", commercial_intent="none",
        request_understanding={
            "subjects": [], "requests": [_price_part("r1", None)],
        },
    ), ensure_ascii=False)


def _reported_price_raw(
    service_id: str | None, topic_id: str, *, extent: str = "one_tooth",
) -> str:
    part = _price_part("r1", service_id, topic_id)
    part["subject_id"] = "s1"
    part["situation"] = {
        "scope_commitment": "reported", "extent": extent,
        "tooth_count": 1 if extent == "one_tooth" else None,
        "jaw": "unknown", "continuity": "new",
    }
    return json.dumps(production_envelope_template(
        commercial_intent="price", primary_price_request_id="r1",
        request_understanding={
            "subjects": [{"subject_id": "s1", "relation": "self", "age_group": "unknown"}],
            "requests": [part],
        },
    ), ensure_ascii=False)


def _hypothetical_price_raw(service_id: str, topic_id: str) -> str:
    part = _price_part("r1", service_id, topic_id)
    part["subject_id"] = "s1"
    part["statement_mode"] = "hypothesis"
    part["situation"] = {
        "scope_commitment": "hypothetical", "extent": "full_arch",
        "tooth_count": None, "jaw": "unknown", "continuity": "same",
    }
    return json.dumps(production_envelope_template(
        commercial_intent="price", primary_price_request_id="r1",
        request_understanding={
            "subjects": [{"subject_id": "s1", "relation": "self", "age_group": "unknown"}],
            "requests": [part],
        },
    ), ensure_ascii=False)


def _doctor_raw(service_id: str) -> str:
    return json.dumps(production_envelope_template(
        commercial_intent="none",
        request_understanding={
            "subjects": [],
            "requests": [{
                "request_id": "r1", "kind": "content", "subject_id": None,
                "context": "general_information", "service_id": service_id,
                "topic_id": None, "statement_mode": "question",
                "situation": None,
                "content_text": "Классическую имплантацию проводит врач-имплантолог Орлов.",
                "content_ref": "doctors__doctor__orlov.md",
                "content_realization": "model_prose",
                "content_section_refs": [], "content_fallback_section_ref": None,
            }],
        },
    ), ensure_ascii=False)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_exact_service_without_topic_is_saved_and_available_to_next_turn(http_env, transport):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_price_raw(_price_part("r1", "classic"))))
    first = (post if transport == "json" else post_sse)(
        client, sid="rec3-service", request_id="first", q="Цена классической имплантации",
    )
    assert first.status_code == 200
    first_body = first.get_json() if transport == "json" else dict(sse_events(first))["ui"]
    assert first_body["answer"]
    key = SessionKey(client_id="demo", sid="rec3-service")
    with D2DialogueStore(db) as store:
        state = store.read(key).state
        assert state.active_service is not None
        assert state.active_service.service_id == "classic"
        assert state.active_topic is None
        assert store.read_latest_completion(key).response.resolved.session_delta.active_service_id == "classic"
    fake.raw = _price_raw(_price_part("r1", None))
    second = post(client, sid="rec3-service", request_id="second", q="А сколько это стоит?")
    assert second.status_code == 200, second.get_json()
    assert fake.inputs[1].context.ordinary.active_service.service_id == "classic"
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(key)
        assert saved.response.resolved.route == "ANSWER"
        assert saved.response.resolved.d2_price_block is not None
        assert {row.service_id for row in saved.response.resolved.d2_price_block.rows} == {"classic"}
        assert store.read(key).state.active_service.service_id == "classic"
        assert store.read(key).state.revision == 2
    replay = post(client, sid="rec3-service", request_id="second", q="А сколько это стоит?")
    assert replay.get_json() == second.get_json()
    assert len(fake.inputs) == 2
    fake.raw = _doctor_raw("classic")
    doctor = post(client, sid="rec3-service", request_id="third", q="А кто это делает?")
    assert doctor.status_code == 200
    assert "Орлов" in doctor.get_json()["answer"]
    assert fake.inputs[2].context.ordinary.active_service.service_id == "classic"
    doctor_replay = post(client, sid="rec3-service", request_id="third", q="А кто это делает?")
    assert doctor_replay.get_json() == doctor.get_json()
    assert len(fake.inputs) == 3


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_two_distinct_services_do_not_persist_first_price_as_focus(http_env, transport):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_price_raw(
        _price_part("r1", "classic", "implantation"),
        _price_part("r2", "veneers", "prosthetics"),
    )))
    first = (post if transport == "json" else post_sse)(
        client, sid="rec3-multipart", request_id="first",
        q="Цена имплантации и виниров",
    )
    assert first.status_code == 200
    body = first.get_json() if transport == "json" else dict(sse_events(first))["ui"]
    assert D2_PRICE_DEFERRAL_TEXT in body["answer"]
    key = SessionKey(client_id="demo", sid="rec3-multipart")
    with D2DialogueStore(db) as store:
        completion = store.read_latest_completion(key)
        state = store.read(key).state
        assert completion.response.rendered_text == body["answer"]
        assert [(part.request_id, part.status) for part in completion.response.resolved.d2_request_parts] == [
            ("r1", "answered"), ("r2", "deferred"),
        ]
        assert {row.service_id for row in completion.response.resolved.d2_price_block.rows} == {"classic"}
        assert len(completion.response.resolved.d2_part_deferred_blocks) == 1
        assert completion.response.resolved.response_scope == "mixed"
        assert completion.response.resolved.session_delta.active_service_id is None
        assert state.active_service is None
        assert state.active_topic is None
    fake.raw = _price_raw(_price_part("r1", None))
    second = post(client, sid="rec3-multipart", request_id="second", q="А сколько?")
    assert second.status_code == 200
    assert fake.inputs[1].context.ordinary.active_service is None
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(key)
        assert saved.response.resolved.route == "CLARIFY"
        assert store.read(key).state.active_service is None
    assert len(fake.inputs) == 2


def test_two_price_parts_for_one_service_keep_unambiguous_focus(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_price_raw(
        _price_part("r1", "classic", "implantation"),
        _price_part("r2", "classic", "implantation"),
    )))
    response = post(client, sid="rec3-same-service", request_id="first",
                    q="Два вопроса о цене классической имплантации")
    assert response.status_code == 200
    key = SessionKey(client_id="demo", sid="rec3-same-service")
    with D2DialogueStore(db) as store:
        completion = store.read_latest_completion(key)
        state = store.read(key).state
        assert completion.response.resolved.response_scope == "service"
        assert [(part.request_id, part.status) for part in completion.response.resolved.d2_request_parts] == [
            ("r1", "answered"), ("r2", "deferred"),
        ]
        assert state.active_service is not None and state.active_service.service_id == "classic"
        assert state.active_topic is not None and state.active_topic.topic_id == "implantation"
    assert len(fake.inputs) == 1


def test_multipart_focus_change_keeps_first_price_and_ui(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_price_raw(_price_part("r1", "classic", "implantation"))))
    one = post(client, sid="rec3-one-price", request_id="first", q="Цена имплантации")
    assert one.status_code == 200
    fake.raw = _price_raw(
        _price_part("r1", "classic", "implantation"),
        _price_part("r2", "veneers", "prosthetics"),
    )
    two = post(client, sid="rec3-two-prices", request_id="first",
               q="Цена имплантации и виниров")
    assert two.status_code == 200
    one_body, two_body = one.get_json(), two.get_json()
    assert D2_PRICE_DEFERRAL_TEXT not in one_body["answer"]
    assert D2_PRICE_DEFERRAL_TEXT in two_body["answer"]
    with D2DialogueStore(db) as store:
        one_plan = store.read_latest_completion(SessionKey(client_id="demo", sid="rec3-one-price")).response
        two_plan = store.read_latest_completion(SessionKey(client_id="demo", sid="rec3-two-prices")).response
        assert one_plan.resolved.d2_price_block == two_plan.resolved.d2_price_block
        assert one_plan.ui_projection == two_plan.ui_projection
        assert two_plan.resolved.session_delta.active_service_id is None
    assert len(fake.inputs) == 2


def test_new_exact_service_replaces_old_service_only_focus(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_price_raw(_price_part("r1", "classic"))))
    assert post(client, sid="rec3-switch", request_id="first", q="Цена имплантации").status_code == 200
    fake.raw = _price_raw(_price_part("r1", "veneers"))
    assert post(client, sid="rec3-switch", request_id="second", q="Цена виниров").status_code == 200
    key = SessionKey(client_id="demo", sid="rec3-switch")
    with D2DialogueStore(db) as store:
        state = store.read(key).state
        assert state.active_service is not None and state.active_service.service_id == "veneers"
        assert state.active_topic is None
    fake.raw = _price_raw(_price_part("r1", "veneers"))
    assert post(client, sid="rec3-switch", request_id="third", q="А сколько это стоит?").status_code == 200
    assert fake.inputs[-1].context.ordinary.active_service.service_id == "veneers"
    assert len(fake.inputs) == 3


def test_new_service_only_focus_does_not_inherit_old_treatment_situation(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_reported_price_raw(None, "implantation")))
    first = post(client, sid="rec3-new-treatment", request_id="first",
                 q="Нет одного зуба, сколько стоит восстановить?")
    assert first.status_code == 200
    key = SessionKey(client_id="demo", sid="rec3-new-treatment")
    with D2DialogueStore(db) as store:
        assert store.read(key).state.situation_state is not None
    fake.raw = _price_raw(_price_part("r1", "veneers"))
    second = post(client, sid="rec3-new-treatment", request_id="second",
                  q="А сколько стоят виниры?")
    assert second.status_code == 200
    with D2DialogueStore(db) as store:
        state = store.read(key).state
        assert state.active_service.service_id == "veneers"
        assert state.active_topic is None
        assert state.situation_state is None
    assert len(fake.inputs) == 2


def test_new_exact_service_hypothesis_does_not_delete_reported_situation(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_reported_price_raw(None, "implantation")))
    assert post(client, sid="rec3-hypothesis", request_id="first",
                q="Нет одного зуба, сколько стоит восстановить?").status_code == 200
    key = SessionKey(client_id="demo", sid="rec3-hypothesis")
    with D2DialogueStore(db) as store:
        before = store.read(key).state.situation_state
        assert before is not None and before.extent == "one_tooth"
    fake.raw = _hypothetical_price_raw("all_on_4", "implantation")
    second = post(client, sid="rec3-hypothesis", request_id="second",
                  q="А если вся челюсть, сколько стоит All-on-4?")
    assert second.status_code == 200, second.get_json()
    with D2DialogueStore(db) as store:
        after = store.read(key).state.situation_state
        assert after is not None
        assert (after.extent, after.tooth_count, after.situation_owner_id) == (
            before.extent, before.tooth_count, before.situation_owner_id,
        )
    assert len(fake.inputs) == 2


def test_service_clarify_click_keeps_price_task_and_selected_service(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_service_clarify_raw("all_on_4", "all_on_6")))
    first = post(client, sid="rec3-click", request_id="first", q="Сколько стоит?")
    assert first.status_code == 200
    shown = first.get_json()
    assert {item["reply_id"] for item in shown["ui"]["quick_replies"]} == {
        "service:all_on_4", "service:all_on_6",
    }
    with D2DialogueStore(db) as store:
        task = store.read(SessionKey(client_id="demo", sid="rec3-click")).state.clarify_task
        assert task is not None and "price" in task.request_kinds
    fake.raw = _price_raw(_price_part("r1", None))
    args = dict(sid="rec3-click", request_id="clicked", q="",
                ref="service:all_on_4", ui_revision=shown["revision"])
    second = post(client, **args)
    assert second.status_code == 200
    assert fake.inputs[1].selected_ui_ref.reply_id == "service:all_on_4"
    assert fake.inputs[1].context.ordinary.clarify_task is not None
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="rec3-click")
        saved = store.read_latest_completion(key)
        assert saved.response.resolved.d2_price_block is not None
        assert {row.service_id for row in saved.response.resolved.d2_price_block.rows} == {"all_on_4"}
        assert store.read(key).state.active_service.service_id == "all_on_4"
    assert post(client, **args).get_json() == second.get_json()
    assert len(fake.inputs) == 2


def test_service_click_needs_no_topic_in_synthetic_tenant(http_env):
    client, db, use_provider, root = http_env
    catalog_path = root / "clients" / "demo" / "target_response" / "service_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["classic"]["content_ref"] = None
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    fake = use_provider(FakeProvider(_service_clarify_raw("classic", "one_stage")))
    first = post(client, sid="rec3-click-no-topic", request_id="first", q="Сколько стоит?")
    assert first.status_code == 200
    shown = first.get_json()
    assert "service:classic" in {item["reply_id"] for item in shown["ui"]["quick_replies"]}
    fake.raw = _price_raw(_price_part("r1", None))
    second = post(client, sid="rec3-click-no-topic", request_id="clicked", q="",
                  ref="service:classic", ui_revision=shown["revision"])
    assert second.status_code == 200
    key = SessionKey(client_id="demo", sid="rec3-click-no-topic")
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(key)
        state = store.read(key).state
        assert saved.response.resolved.d2_price_block is not None
        assert state.active_service is not None and state.active_service.service_id == "classic"
        assert state.active_topic is None
    assert len(fake.inputs) == 2


def test_no_topic_service_click_clarify_drops_previous_treatment_situation(http_env):
    client, db, use_provider, root = http_env
    catalog_path = root / "clients" / "demo" / "target_response" / "service_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["classic"]["content_ref"] = None
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    fake = use_provider(FakeProvider(_reported_price_raw(None, "implantation")))
    sid = "rec3-click-no-topic-situation"
    key = SessionKey(client_id="demo", sid=sid)
    assert post(client, sid=sid, request_id="reported",
                q="Нет одного зуба, сколько стоит восстановить?").status_code == 200
    with D2DialogueStore(db) as store:
        assert store.read(key).state.situation_state is not None
    fake.raw = _service_clarify_raw("classic", "veneers")
    shown = post(client, sid=sid, request_id="clarify", q="А какая услуга?")
    assert shown.status_code == 200
    assert "service:classic" in {item["reply_id"] for item in shown.get_json()["ui"]["quick_replies"]}
    with D2DialogueStore(db) as store:
        assert store.read(key).state.situation_state is not None
    fake.raw = _extent_clarify_raw()
    clicked = post(client, sid=sid, request_id="clicked", q="",
                   ref="service:classic", ui_revision=shown.get_json()["revision"])
    assert clicked.status_code == 200
    with D2DialogueStore(db) as store:
        state = store.read(key).state
        assert state.active_service is not None and state.active_service.service_id == "classic"
        assert state.active_topic is None
        assert state.situation_state is None
        assert state.shown_options_snapshot is None
    assert len(fake.inputs) == 3


def test_expired_focus_does_not_revive_after_neutral_turn(http_env):
    _, db, _, root = http_env
    key = SessionKey(client_id="demo", sid="rec3-expiry")
    at = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
    fake = FakeProvider(_price_raw(_price_part("r1", "classic")))
    with D2DialogueStore(db) as store:
        run_d2_dialogue_turn(
            session_key=key, user_message="Цена классической имплантации",
            provider=fake, clients_root=root / "clients", store=store,
            now=at, request_id="first",
        )
        initial_state = store.read(key).state
        assert initial_state.active_service.service_id == "classic"
        assert initial_state.accumulated_shown_ids.price_offer_ids
        fake.raw = envelope_clinic_policy_only("no_pediatric_dentistry")
        run_d2_dialogue_turn(
            session_key=key, user_message="Можно ли детям?",
            provider=fake, clients_root=root / "clients", store=store,
            now=at + timedelta(minutes=30), request_id="neutral",
        )
        expired_state = store.read(key).state
        assert expired_state.active_service is None
        assert expired_state.active_topic is None
        assert expired_state.accumulated_shown_ids.price_offer_ids == initial_state.accumulated_shown_ids.price_offer_ids
        fake.raw = _price_raw(_price_part("r1", None))
        follow = run_d2_dialogue_turn(
            session_key=key, user_message="А сколько?", provider=fake,
            clients_root=root / "clients", store=store,
            now=at + timedelta(minutes=31), request_id="follow",
        )
        assert follow.response.resolved.route == "CLARIFY"
        assert fake.inputs[-1].context.ordinary.active_service is None
        assert store.read(key).state.active_service is None
        assert len(fake.inputs) == 3


def test_focus_survives_neutral_turn_before_idle_ttl(http_env):
    _, db, _, root = http_env
    key = SessionKey(client_id="demo", sid="rec3-fresh")
    at = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
    fake = FakeProvider(_price_raw(_price_part("r1", "classic")))
    with D2DialogueStore(db) as store:
        run_d2_dialogue_turn(
            session_key=key, user_message="Цена классической имплантации",
            provider=fake, clients_root=root / "clients", store=store,
            now=at, request_id="first",
        )
        fake.raw = envelope_clinic_policy_only("no_pediatric_dentistry")
        run_d2_dialogue_turn(
            session_key=key, user_message="Можно ли детям?",
            provider=fake, clients_root=root / "clients", store=store,
            now=at + timedelta(minutes=29, seconds=59), request_id="neutral",
        )
        assert store.read(key).state.active_service.service_id == "classic"
        fake.raw = _price_raw(_price_part("r1", "classic"))
        run_d2_dialogue_turn(
            session_key=key, user_message="А сколько?", provider=fake,
            clients_root=root / "clients", store=store,
            now=at + timedelta(minutes=30), request_id="follow",
        )
        assert fake.inputs[-1].context.ordinary.active_service.service_id == "classic"
        assert store.read(key).state.active_service.service_id == "classic"


def test_expired_focus_does_not_revive_on_non_price_clarify_writer(http_env):
    _, db, _, root = http_env
    key = SessionKey(client_id="demo", sid="rec3-expired-clarify")
    at = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
    fake = FakeProvider(_price_raw(_price_part("r1", "classic")))
    with D2DialogueStore(db) as store:
        run_d2_dialogue_turn(
            session_key=key, user_message="Цена классической имплантации",
            provider=fake, clients_root=root / "clients", store=store,
            now=at, request_id="first",
        )
        fake.raw = _extent_clarify_raw()
        run_d2_dialogue_turn(
            session_key=key, user_message="Какой объём?", provider=fake,
            clients_root=root / "clients", store=store,
            now=at + timedelta(minutes=30), request_id="clarify",
        )
        state = store.read(key).state
        assert state.active_service is None
        assert state.active_topic is None
        assert state.clarify_pending is True
        fake.raw = _price_raw(_price_part("r1", None))
        run_d2_dialogue_turn(
            session_key=key, user_message="А сколько?", provider=fake,
            clients_root=root / "clients", store=store,
            now=at + timedelta(minutes=31), request_id="follow",
        )
        assert fake.inputs[-1].context.ordinary.active_service is None
        assert len(fake.inputs) == 3
