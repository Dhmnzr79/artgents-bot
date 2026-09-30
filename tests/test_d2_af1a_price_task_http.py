"""AF-1a: a verified volume choice keeps its frozen price task."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from contracts.response_plan import SessionKey
from contracts.d2_session_context import D2SessionActivity
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from tests.test_d2_ui_b12_scenarios import _price_raw
from tests.test_d2_widget_replay import _mixed_widget_raw


PROSE = "Модель объяснила, как проходит имплантация."


def _overview_raw(*, brand_id: str | None = None, service_id: str | None = None,
                  relation: str = "self", statement_mode: str = "question") -> str:
    return json.dumps(production_envelope_template(
        commercial_intent="price",
        primary_price_request_id="r1",
        request_understanding={
            "subjects": [{"subject_id": "s1", "relation": relation, "age_group": "unknown"}],
            "requests": [{
                "request_id": "r1", "kind": "price", "subject_id": "s1",
                "context": "general_information", "topic_id": "implantation",
                "service_id": service_id, "brand_id": brand_id,
                "statement_mode": statement_mode, "situation": None,
            }],
        },
    ), ensure_ascii=False)


def _wrong_kind_raw(*, kind: str = "content", topic_id: str | None = None,
                    brand_id: str | None = None,
                    statement_mode: str = "question") -> str:
    return json.dumps(production_envelope_template(
        commercial_intent="none",
        request_understanding={
            "subjects": [],
            "requests": [{
                "request_id": "r1", "kind": kind, "subject_id": None,
                "context": "general_information", "topic_id": topic_id,
                "brand_id": brand_id, "content_text": PROSE,
                "content_realization": "model_prose",
                "statement_mode": statement_mode,
            }],
        },
    ), ensure_ascii=False)


def _body(response, transport: str) -> dict:
    return response.get_json() if transport == "json" else dict(sse_events(response))["ui"]


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("brand_id", [None, "implantium"])
def test_wrong_kind_volume_click_keeps_price_brand_prose_and_replay(
    http_env, transport: str, brand_id: str | None,
) -> None:
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_overview_raw(brand_id=brand_id)))
    send = post if transport == "json" else post_sse
    sid = f"af1a-{transport}-{brand_id or 'general'}"
    question = "Сколько стоят импланты Implantium?" if brand_id else "Сколько стоит имплантация?"
    first = send(client, sid=sid, request_id="overview", q=question)
    assert first.status_code == 200
    overview = _body(first, transport)
    choice = next(item for item in overview["ui"]["quick_replies"]
                  if item["reply_id"] == "volume:implantation:one_tooth")

    fake.raw = _wrong_kind_raw()
    args = dict(sid=sid, request_id="choice", q="", ref=choice["reply_id"],
                ui_revision=overview["revision"])
    clicked = send(client, **args)
    assert clicked.status_code == 200, clicked.get_data(as_text=True)
    body = _body(clicked, transport)
    assert PROSE in body["answer"]
    assert "76\u00a0200\u00a0₽" in body["answer"]
    if brand_id:
        assert "85\u00a0200\u00a0₽" not in body["answer"]
        assert "101\u00a0200\u00a0₽" not in body["answer"]
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid=sid)
        saved = store.read_latest_completion(key)
        assert saved is not None and saved.response.resolved.d2_price_block is not None
        offer_ids = {row.offer_id for row in saved.response.resolved.d2_price_block.rows}
        if brand_id:
            assert "classic.one_tooth.implantium" in offer_ids
            assert all(offer_id.endswith(".implantium") for offer_id in offer_ids)
        else:
            assert offer_ids == {
                "classic.one_tooth.implantium", "classic.one_tooth.impro",
                "classic.one_tooth.nobel",
            }
        pairs = store.read(key).state.dialogue_pairs
        assert pairs and PROSE in pairs[-1].assistant_text
        assert "76\u00a0200" not in pairs[-1].assistant_text
        assert store.read(key).state.situation_state is None
        assert saved.recent_price_scope is not None
        assert saved.recent_price_scope.extent == "one_tooth"
        assert saved.recent_price_scope.brand_id == brand_id
    replay = send(client, **args)
    assert replay.status_code == 200
    assert _body(replay, transport) == body
    assert len(fake.inputs) == 2


@pytest.mark.parametrize("relation,statement_mode", [
    ("other", "question"), ("self", "hypothesis"),
])
def test_other_person_or_hypothesis_gets_price_without_personal_situation(
    http_env, relation: str, statement_mode: str,
) -> None:
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_overview_raw(
        relation=relation, statement_mode=statement_mode,
    )))
    sid = f"af1a-{relation}-{statement_mode}"
    first = post(client, sid=sid, request_id="overview", q="Сколько стоит имплантация?")
    assert first.status_code == 200
    body = first.get_json()
    choice = next(item for item in body["ui"]["quick_replies"]
                  if item["reply_id"] == "volume:implantation:one_tooth")
    fake.raw = _wrong_kind_raw()
    clicked = post(client, sid=sid, request_id="choice", q="",
                   ref=choice["reply_id"], ui_revision=body["revision"])
    assert clicked.status_code == 200, clicked.get_json()
    assert "76\u00a0200\u00a0₽" in clicked.get_json()["answer"]
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid=sid)
        assert store.read(key).state.situation_state is None
    assert len(fake.inputs) == 2


def test_unknown_subject_choice_gives_price_without_personal_state(http_env) -> None:
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_overview_raw(relation="unknown")))
    first = post(client, sid="af1a-unknown-subject", request_id="overview",
                 q="Сколько стоит имплантация?")
    assert first.status_code == 200, first.get_json()
    overview = first.get_json()
    choice = next(item for item in overview["ui"]["quick_replies"]
                  if item["reply_id"] == "volume:implantation:one_tooth")
    fake.raw = _wrong_kind_raw()
    clicked = post(client, sid="af1a-unknown-subject", request_id="choice", q="",
                   ref=choice["reply_id"], ui_revision=overview["revision"])
    assert clicked.status_code == 200, clicked.get_json()
    assert "76\u00a0200\u00a0₽" in clicked.get_json()["answer"]
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="af1a-unknown-subject")).state.situation_state is None


@pytest.mark.parametrize("model_claim", ["statement", "situation"])
def test_model_hypothesis_does_not_turn_price_choice_into_patient_fact(
    http_env, model_claim: str,
) -> None:
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_overview_raw()))
    sid = f"af1a-hypothesis-claim-{model_claim}"
    first = post(client, sid=sid, request_id="overview", q="Сколько стоит имплантация?")
    assert first.status_code == 200, first.get_json()
    overview = first.get_json()
    choice = next(item for item in overview["ui"]["quick_replies"]
                  if item["reply_id"] == "volume:implantation:one_tooth")
    fake.raw = (
        _wrong_kind_raw(statement_mode="hypothesis")
        if model_claim == "statement" else _price_raw("implantation", {
            "scope_commitment": "hypothetical", "extent": "one_tooth",
            "tooth_count": 1, "jaw": "unknown", "continuity": "same",
        })
    )
    clicked = post(client, sid=sid, request_id="choice", q="",
                   ref=choice["reply_id"], ui_revision=overview["revision"])
    assert clicked.status_code == 200, clicked.get_json()
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid=sid)
        assert store.read(key).state.situation_state is None
        assert store.read_latest_completion(key).recent_price_scope.extent == "one_tooth"


def test_branded_scope_without_offer_keeps_honest_gap_and_model_prose(http_env) -> None:
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_overview_raw(brand_id="implantium")))
    first = post(client, sid="af1a-gap", request_id="overview", q="Сколько стоит Implantium?")
    assert first.status_code == 200
    body = first.get_json()
    choice = next(item for item in body["ui"]["quick_replies"]
                  if item["reply_id"] == "volume:implantation:few_teeth")
    fake.raw = _wrong_kind_raw()
    clicked = post(client, sid="af1a-gap", request_id="choice", q="",
                   ref=choice["reply_id"], ui_revision=body["revision"])
    assert clicked.status_code == 200, clicked.get_json()
    assert PROSE in clicked.get_json()["answer"]
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="af1a-gap"))
        assert saved.response.resolved.d2_price_block is None
        assert saved.recent_price_scope is not None
        assert saved.recent_price_scope.extent == "few_teeth"
        assert saved.recent_price_scope.brand_id == "implantium"
        assert any(part.kind == "price" and part.status == "unavailable"
                   for part in saved.response.resolved.d2_request_parts)


@pytest.mark.parametrize("brand_id,extent", [
    (None, "one_tooth"), ("implantium", "few_teeth"),
])
def test_price_choice_is_next_turn_context_not_patient_fact(
    http_env, brand_id: str | None, extent: str,
) -> None:
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_overview_raw(brand_id=brand_id)))
    sid = f"af1a-followup-{brand_id or 'general'}"
    first = post(client, sid=sid, request_id="overview", q="Сколько стоит имплантация?")
    assert first.status_code == 200, first.get_json()
    overview = first.get_json()
    choice = next(item for item in overview["ui"]["quick_replies"]
                  if item["reply_id"] == f"volume:implantation:{extent}")
    fake.raw = _wrong_kind_raw()
    clicked = post(client, sid=sid, request_id="choice", q="",
                   ref=choice["reply_id"], ui_revision=overview["revision"])
    assert clicked.status_code == 200, clicked.get_json()
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid=sid)
        assert store.read(key).state.situation_state is None
        assert store.read_latest_completion(key).recent_price_scope.extent == extent
    fake.raw = _wrong_kind_raw(topic_id="implantation")
    followup = post(client, sid=sid, request_id="duration", q="А сколько это займёт?")
    assert followup.status_code == 200, followup.get_json()
    assert PROSE in followup.get_json()["answer"]
    seen = fake.inputs[-1].context.recent_price_scope
    assert seen is not None
    assert (seen.topic_id, seen.brand_id, seen.extent) == (
        "implantation", brand_id, extent,
    )
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid=sid)).state.situation_state is None


def test_recent_price_scope_expires_before_next_provider_input(http_env) -> None:
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_overview_raw()))
    sid = "af1a-scope-ttl"
    first = post(client, sid=sid, request_id="overview", q="Сколько стоит имплантация?")
    overview = first.get_json()
    choice = next(item for item in overview["ui"]["quick_replies"]
                  if item["reply_id"] == "volume:implantation:one_tooth")
    fake.raw = _wrong_kind_raw()
    clicked = post(client, sid=sid, request_id="choice", q="",
                   ref=choice["reply_id"], ui_revision=overview["revision"])
    assert clicked.status_code == 200, clicked.get_json()
    key = SessionKey(client_id="demo", sid=sid)
    with D2DialogueStore(db) as store:
        record = store.read(key)
        old = record.model_copy(update={"activity": D2SessionActivity(
            session_key=key,
            last_user_turn_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )})
        with store._connection:
            store._connection.execute(
                "UPDATE d2_dialogue SET payload=? WHERE client_id=? AND sid=?",
                (old.model_dump_json(), "demo", sid),
            )
    fake.raw = _wrong_kind_raw(topic_id="implantation")
    next_turn = post(client, sid=sid, request_id="duration", q="Сколько займёт имплантация?")
    assert next_turn.status_code == 200, next_turn.get_json()
    assert fake.inputs[-1].context.freshness == "expired"
    assert fake.inputs[-1].context.recent_price_scope is None


def test_new_topic_replaces_recent_price_scope(http_env) -> None:
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_overview_raw()))
    sid = "af1a-scope-switch"
    first = post(client, sid=sid, request_id="overview", q="Сколько стоит имплантация?")
    overview = first.get_json()
    choice = next(item for item in overview["ui"]["quick_replies"]
                  if item["reply_id"] == "volume:implantation:one_tooth")
    fake.raw = _wrong_kind_raw()
    clicked = post(client, sid=sid, request_id="choice", q="",
                   ref=choice["reply_id"], ui_revision=overview["revision"])
    assert clicked.status_code == 200, clicked.get_json()
    fake.raw = _wrong_kind_raw(topic_id="whitening")
    switched = post(client, sid=sid, request_id="switch", q="Расскажите про отбеливание")
    assert switched.status_code == 200, switched.get_json()
    assert fake.inputs[-1].context.recent_price_scope.extent == "one_tooth"
    fake.raw = _wrong_kind_raw(topic_id="whitening")
    followup = post(client, sid=sid, request_id="after-switch", q="А сколько это займёт?")
    assert followup.status_code == 200, followup.get_json()
    assert fake.inputs[-1].context.recent_price_scope is None


def test_unknown_choice_does_not_repeat_menu_or_store_reported_extent(http_env) -> None:
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_overview_raw()))
    first = post(client, sid="af1a-unknown", request_id="overview", q="Сколько стоит имплантация?")
    assert first.status_code == 200
    body = first.get_json()
    choice = next(item for item in body["ui"]["quick_replies"]
                  if item["reply_id"] == "volume:implantation:unknown")
    fake.raw = _wrong_kind_raw()
    clicked = post(client, sid="af1a-unknown", request_id="choice", q="",
                   ref=choice["reply_id"], ui_revision=body["revision"])
    assert clicked.status_code == 200, clicked.get_json()
    assert not any(item["reply_id"].startswith("volume:")
                   for item in clicked.get_json()["ui"]["quick_replies"])
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="af1a-unknown")).state.situation_state is None


@pytest.mark.parametrize("extent", ["few_teeth", "full_arch"])
def test_other_volume_choices_keep_price_or_honest_gap(http_env, extent: str) -> None:
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_overview_raw()))
    sid = f"af1a-{extent}"
    first = post(client, sid=sid, request_id="overview", q="Сколько стоит имплантация?")
    assert first.status_code == 200, first.get_json()
    overview = first.get_json()
    choice = next(item for item in overview["ui"]["quick_replies"]
                  if item["reply_id"] == f"volume:implantation:{extent}")
    fake.raw = _wrong_kind_raw(kind="other")
    clicked = post(client, sid=sid, request_id="choice", q="",
                   ref=choice["reply_id"], ui_revision=overview["revision"])
    assert clicked.status_code == 200, clicked.get_json()
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid=sid))
        price_parts = [part for part in saved.response.resolved.d2_request_parts
                       if part.kind == "price"]
        assert len(price_parts) == 1
        assert price_parts[0].status in {"answered", "unavailable"}
        assert saved.response.resolved.d2_price_block or saved.response.resolved.d2_part_failure_blocks
        assert PROSE in saved.response.rendered_text


def test_volume_click_rejects_conflicting_model_topic_without_foreign_price(http_env) -> None:
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_overview_raw()))
    first = post(client, sid="af1a-conflict", request_id="overview", q="Сколько стоит имплантация?")
    assert first.status_code == 200
    body = first.get_json()
    choice = next(item for item in body["ui"]["quick_replies"]
                  if item["reply_id"] == "volume:implantation:one_tooth")
    fake.raw = _wrong_kind_raw(topic_id="prosthetics")
    second = post(client, sid="af1a-conflict", request_id="choice", q="",
                  ref=choice["reply_id"], ui_revision=body["revision"])
    assert second.status_code == 400
    with D2DialogueStore(db) as store:
        saved = store.read(SessionKey(client_id="demo", sid="af1a-conflict"))
        assert saved is not None and saved.state.revision == body["revision"]


def test_existing_valid_price_envelope_on_volume_choice(http_env) -> None:
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_price_raw("implantation")))
    first = post(client, sid="af1a-valid", request_id="overview", q="Сколько стоит имплантация?")
    assert first.status_code == 200, first.get_json()
    body = first.get_json()
    choice = next(item for item in body["ui"]["quick_replies"]
                  if item["reply_id"] == "volume:implantation:one_tooth")
    fake.raw = _price_raw("implantation", {
        "scope_commitment": "reported", "extent": "one_tooth",
        "tooth_count": 1, "jaw": "unknown", "continuity": "same",
    })
    clicked = post(client, sid="af1a-valid", request_id="choice", q="",
                   ref=choice["reply_id"], ui_revision=body["revision"])
    assert clicked.status_code == 200, clicked.get_json()


def test_mixed_price_and_information_survive_verified_volume_choice(http_env) -> None:
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_mixed_widget_raw()))
    sid = "af1a-mixed-click"
    first = post(client, sid=sid, request_id="overview",
                 q="Сколько стоит имплантация и расскажите о ней?")
    assert first.status_code == 200, first.get_json()
    overview = first.get_json()
    choice = next(item for item in overview["ui"]["quick_replies"]
                  if item["reply_id"] == "volume:implantation:one_tooth")
    clicked = post(client, sid=sid, request_id="choice", q="",
                   ref=choice["reply_id"], ui_revision=overview["revision"])
    assert clicked.status_code == 200, clicked.get_json()
    answer = clicked.get_json()["answer"]
    assert "76\u00a0200\u00a0₽" in answer
    assert "Живой mixed-ответ" in answer
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid=sid)
        saved = store.read_latest_completion(key)
        assert {part.kind for part in saved.response.resolved.d2_request_parts} >= {
            "price", "content", "clinic_policy",
        }
        assert store.read(key).state.situation_state is None
    replay = post(client, sid=sid, request_id="choice", q="",
                  ref=choice["reply_id"], ui_revision=overview["revision"])
    assert replay.get_json() == clicked.get_json()
    assert len(fake.inputs) == 2
