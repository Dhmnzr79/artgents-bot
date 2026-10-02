"""Existing pending operation preserves scope; no semantic recovery on click."""
import json
import re

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import build_d2_d1r_messages
from core.one_call_prompt_contract import D2_OPERATIONS_INSTRUCTIONS
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse
from tests.test_d2_document_click_task_http import _body
from tests.test_d2_sim2_dialogues import raw, explanation


def scoped_clarification():
    # Genuine unresolved service still preserves scope. Combine the published
    # unresolved-task shape with scope from the direct-price example; this
    # fixture checks persistence, not whether a live model should clarify.
    examples = [json.loads(x) for x in re.findall(r"```json\n(.*?)\n```", D2_OPERATIONS_INSTRUCTIONS, re.S)]
    example = next(x for x in examples if x["blocks"][0].get("operation", {}).get("kind") == "price")
    scoped = next(x["blocks"][0] for x in examples if x["blocks"][0].get("situation"))
    example["blocks"][0]["operation"]["situation"] = scoped["situation"]
    example["blocks"][0]["choices"] = ["classic", "implant_supported_prosthetics"]
    return example["blocks"][0]


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("extent,count,commitment,jaw", [
    ("few_teeth", 3, "hypothetical", "unknown"),
    ("few_teeth", 4, "hypothetical", "upper"),
    ("one_tooth", 1, "hypothetical", "lower"),
    ("full_arch", None, "hypothetical", "upper"),
])
def test_service_clarification_keeps_scope_through_click_replay_and_next_input(
    http_env, transport, extent, count, commitment, jaw,
):
    client, db, use, _ = http_env
    pending = scoped_clarification()
    pending["operation"]["situation"].update(
        extent=extent, tooth_count=count, scope_commitment=commitment, jaw=jaw)
    pending["operation"]["brand_id"] = "implantium"
    fake = use(FakeProvider(raw(pending, explanation("Адрес можно уточнить отдельно.", request_id="r2"))))
    send = post if transport == "json" else post_sse
    query = f"Если восстановить {count or 'все'} зубов, сколько это стоит?"
    first_args = dict(sid="clarify-scope", request_id="first", q=query)
    first = _body(send(client, **first_args), transport)
    assert "Адрес можно уточнить отдельно." in first["answer"]
    assert {x["reply_id"] for x in first["ui"]["quick_replies"]} == {
        "service:classic", "service:implant_supported_prosthetics"}
    assert _body(send(client, **first_args), transport) == first
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="clarify-scope")
        task = store.read(key).state.clarify_task.operation
        assert task.situation.model_dump() == pending["operation"]["situation"]
        assert task.brand_id == "implantium"

    def forbidden(*_args):
        raise AssertionError("known price click must not invoke the model")

    generate = fake.generate
    fake.generate = forbidden
    args = dict(sid="clarify-scope", request_id="click", q="", ref="service:classic",
                ui_revision=first["revision"])
    clicked = _body(send(client, **args), transport)
    assert _body(send(client, **args), transport) == clicked
    assert len(fake.inputs) == 1
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(key)
        result = saved.response.resolved
        assert result.d2_treatment_situation.extent == extent
        assert result.d2_treatment_situation.tooth_count == count
        assert result.d2_treatment_situation.jaw == jaw
        assert store.read(key).state.clarify_task is None
        assert store.read(key).state.situation_state is None
        if extent in {"one_tooth", "few_teeth"}:
            assert tuple(r.offer_id for r in result.d2_price_block.rows) == ("classic.one_tooth.implantium",)
            assert "76 200" in clicked["answer"].replace("\u00a0", " ")
            if extent == "few_teeth":
                assert "ориентир за один зуб" in clicked["answer"]
        else:
            assert result.d2_price_block is None
            assert result.d2_request_parts[0].status == "unavailable"
            assert "₽" not in clicked["answer"]
            assert clicked["answer"].strip()

    fake.generate = generate
    fake.raw = raw(explanation("Срок зависит от выбранного плана лечения."))
    assert send(client, sid="clarify-scope", request_id="next", q="А сколько времени?").status_code == 200
    scope = fake.inputs[-1].context.ordinary.discussion_scope
    assert scope.extent == extent and scope.service_id == "classic" and scope.brand_id == "implantium"
    assert len(fake.inputs) == 2


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_known_direction_and_explicit_three_teeth_use_unit_reference_after_information(http_env, transport):
    client, db, use, _ = http_env
    information = explanation("Имплантация проходит поэтапно.")
    information["target"] = {"type": "topic", "id": "implantation"}
    fake = use(FakeProvider(raw(information)))
    send = post if transport == "json" else post_sse
    assert send(client, sid="known-topic", request_id="info", q="Как проходит имплантация?").status_code == 200
    operation = scoped_clarification()["operation"]
    operation["target"] = {"type": "topic", "id": "implantation"}
    fake.raw = raw(operation)
    body = _body(send(client, sid="known-topic", request_id="price", q="Сколько стоит восстановить три зуба?"), transport)
    assert fake.inputs[-1].context.ordinary.active_topic.topic_id == "implantation"
    # Check the revised instructions actually reach the ordinary provider path.
    assert D2_OPERATIONS_INSTRUCTIONS in build_d2_d1r_messages(fake.inputs[-1])[0]["content"]
    assert "76 200" in body["answer"].replace("\u00a0", " ")
    assert "ориентир за один зуб" in body["answer"]
    assert not any(r["reply_id"].startswith("service:") for r in body["ui"]["quick_replies"])
    with D2DialogueStore(db) as store:
        result = store.read_latest_completion(SessionKey(client_id="demo", sid="known-topic")).response.resolved
        assert tuple(r.offer_id for r in result.d2_price_block.rows) == ("classic.one_tooth.implantium",)
        assert result.d2_request_parts[0].status == "answered"
        assert result.d2_treatment_situation.tooth_count == 3


def test_omitted_scope_is_not_recovered_by_a_second_semantic_owner(http_env):
    # The old live output remains structurally valid. Prompt guidance cannot
    # guarantee model compliance, and the server must not guess from raw text.
    client, db, use, _ = http_env
    pending = scoped_clarification()
    del pending["operation"]["situation"]
    fake = use(FakeProvider(raw(pending)))
    first = post(client, sid="omitted", request_id="first", q="Сколько стоит восстановить три зуба?").get_json()
    clicked = post(client, sid="omitted", request_id="click", q="", ref="service:classic",
                   ui_revision=first["revision"])
    assert clicked.status_code == 200 and len(fake.inputs) == 1
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="omitted")
        result = store.read_latest_completion(key).response.resolved
        assert result.d2_treatment_situation is None
        assert result.d2_price_block is not None
        assert store.read(key).state.situation_state is None


def test_price_scenario_does_not_replace_existing_reported_patient_scope(http_env):
    client, db, use, _ = http_env
    information = explanation("План лечения определяется после диагностики.")
    information["target"] = {"type": "topic", "id": "implantation"}
    information["subject"] = {"subject_id": "s1", "relation": "self", "age_group": "adult"}
    information["situation"] = dict(scope_commitment="reported", extent="one_tooth",
                                   tooth_count=1, jaw="lower", continuity="new")
    fake = use(FakeProvider(raw(information)))
    assert post(client, sid="personal", request_id="reported", q="У меня отсутствует один нижний зуб.").status_code == 200
    key = SessionKey(client_id="demo", sid="personal")
    with D2DialogueStore(db) as store:
        previous = store.read(key).state.situation_state
        assert previous is not None
    fake.raw = raw(scoped_clarification())
    first = post(client, sid="personal", request_id="scenario", q="А если восстановить три зуба, сколько стоит?").get_json()
    clicked = post(client, sid="personal", request_id="click", q="", ref="service:classic",
                   ui_revision=first["revision"])
    assert clicked.status_code == 200 and len(fake.inputs) == 2
    with D2DialogueStore(db) as store:
        assert store.read(key).state.situation_state == previous
        result = store.read_latest_completion(key).response.resolved
        assert result.d2_treatment_situation.tooth_count == 3
        assert tuple(r.offer_id for r in result.d2_price_block.rows) == ("classic.one_tooth.implantium",)
