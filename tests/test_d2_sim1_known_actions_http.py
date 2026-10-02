"""SIM-1: known actions execute without a second semantic model decision."""
from core.d2_completion_context import discussion_scope

import json

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import build_d2_d1r_messages
from tests.test_d2_document_click_task_http import PromptProvider, _body
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse
from tests.test_d2_sim2_dialogues import raw, price, explanation

def _price_raw(topic):
    return raw(price(topic))

def _raw(text, *, ref=None):
    return raw(explanation(text, content_ref=ref))


def _forbid_provider(_request):
    raise AssertionError("A known price task must not call the provider")


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("extent", ["one_tooth", "full_arch", "unknown"])
def test_three_volume_actions_execute_without_provider_and_keep_context(http_env, transport, extent):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_price_raw("implantation")))
    send = post if transport == "json" else post_sse
    first = _body(send(client, sid="sim1-volume", request_id="first", q="Сколько стоит имплантация?"), transport)
    assert [(r["reply_id"], r["label"]) for r in first["ui"]["quick_replies"]] == [
        ("volume:implantation:one_tooth", "Один зуб"),
        ("volume:implantation:full_arch", "Вся челюсть"),
        ("volume:implantation:unknown", "Пока не знаю"),
    ]
    original_generate = fake.generate
    fake.generate = _forbid_provider
    args = dict(sid="sim1-volume", request_id="click", q="",
                ref=f"volume:implantation:{extent}", ui_revision=first["revision"])
    clicked = _body(send(client, **args), transport)
    assert clicked["answer"] and "₽" in clicked["answer"]
    assert _body(send(client, **args), transport) == clicked
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="sim1-volume")
        saved = store.read_latest_completion(key)
        assert discussion_scope(saved.response.resolved).volume.extent == extent
        assert "situation_state" not in store.read(key).state.model_dump()
        assert saved.response.resolved.d2_price_block is not None
        expected = {
            "one_tooth": ("classic.one_tooth.implantium", "one_stage.one_tooth.implantium"),
            "full_arch": ("all_on_4.jaw.implantium", "all_on_6.jaw.implantium"),
            "unknown": ("classic.one_tooth.implantium", "all_on_4.jaw.implantium", "all_on_6.jaw.implantium"),
        }[extent]
        assert tuple(r.offer_id for r in saved.response.resolved.d2_price_block.rows) == expected
        assert saved.response.resolved.d2_price_scope_decision.applied_extent == (
            None if extent == "unknown" else extent
        )
    fake.generate = original_generate
    fake.raw = _raw("Сроки зависят от этапов лечения и заживления.")
    followup = _body(send(client, sid="sim1-volume", request_id="next", q="А сколько это займёт?"), transport)
    assert "Сроки" in followup["answer"]
    assert fake.inputs[-1].context.ordinary.discussion_scope.volume.extent == extent
    assert len(fake.inputs) == 2


@pytest.mark.parametrize("mode", ["omitted", "model_prose", "authored"])
def test_document_realization_preserves_frozen_section(http_env, mode):
    client, db, use_provider, _ = http_env
    doc = "implantation__faq__pain.md"
    fake = use_provider(PromptProvider(_raw("Об обезболивании", ref=doc)))
    first = post(client, sid="sim1-doc", request_id="first", q="Больно ли?").get_json()
    ref = f"{doc}#kakuyu-anesteziyu-ispolzuyut"
    item = {"request_id": "r1", "content_text": "Пояснение выбранного раздела."}
    if mode != "omitted":
        item["content_realization"] = mode
    fake.raw = json.dumps({"explanations": [item]})
    clicked = post(client, sid="sim1-doc", request_id="click", q="", ref=ref, ui_revision=first["revision"])
    assert clicked.status_code == 200, clicked.get_json()
    pending = fake.inputs[-1].known_task.blocks[0]
    assert pending.pending_question == "Какую анестезию используют"
    assert not hasattr(pending, "content_text")
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="sim1-doc"))
        block = saved.response.resolved.information_blocks[0]
        assert block.content_ref == doc
        assert block.source_section_refs == ("a:kakuyu-anesteziyu-ispolzuyut",)
        assert block.publication == ("authored" if mode == "authored" else "model_prose")
        if mode != "authored":
            assert clicked.get_json()["answer"] == item["content_text"]
        else:
            assert clicked.get_json()["answer"] != item["content_text"]
    assert "TYPED_ENVELOPE_INSTRUCTIONS" not in fake.messages[-1][0]["content"]


@pytest.mark.parametrize("reply", [
    "{bad-json",
    {"route": "CLARIFY", "explanations": []},
    {"explanations": [{"request_id": "r1", "content_text": "Текст", "service_id": "veneers"}]},
    {"explanations": [{"request_id": "r1", "content_text": "Текст", "target": {"type": "service", "id": "veneers"}}]},
    {"explanations": [{"request_id": "r1", "pending_question": "Новый вопрос"}]},
    {"explanations": [{"request_id": "r1", "content_text": "Текст", "clarification": {"missing": "stage", "choices": []}}]},
    {"explanations": [{"request_id": "r2", "content_text": "Другой ID"}]},
    {"explanations": [{"request_id": "r1", "content_text": "Текст", "content_realization": None}]},
    {"explanations": [{"request_id": "r1", "content_text": "Текст", "content_realization": "bad"}]},
    {"explanations": [{"request_id": "r1", "content_text": ""}]},
    {"explanations": []},
])
def test_explanation_cannot_reclassify_task_or_publish_invalid_text(http_env, reply):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_raw("Об обезболивании", ref="implantation__faq__pain.md")))
    first = post(client, sid="sim1-invalid", request_id="first", q="Больно ли?").get_json()
    fake.raw = reply if isinstance(reply, str) else json.dumps(reply)
    click = post(client, sid="sim1-invalid", request_id="click", q="",
                 ref="implantation__faq__pain.md#kakuyu-anesteziyu-ispolzuyut", ui_revision=first["revision"])
    assert click.status_code == 400
    assert len(fake.inputs) == 2  # No repair call.
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="sim1-invalid")).state.revision == first["revision"]


def test_ordinary_question_still_has_only_ordinary_prompt(http_env):
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_raw("Обычный связный ответ.")))
    assert post(client, sid="sim1-ordinary", request_id="first", q="Как проходит лечение?").status_code == 200
    system, _ = build_d2_d1r_messages(fake.inputs[0])
    assert "D2_OPERATIONS_INSTRUCTIONS" in system["content"]
    assert "KNOWN_TASK" not in system["content"]


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_known_action_does_not_swallow_simultaneous_free_question(http_env, transport):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_price_raw("implantation")))
    first = post(client, sid="sim1-q-ref", request_id="first", q="Сколько стоит имплантация?").get_json()
    fake.generate = _forbid_provider
    response = (post if transport == "json" else post_sse)(
        client, sid="sim1-q-ref", request_id="bad", q="А адрес?",
        ref="volume:implantation:one_tooth", ui_revision=first["revision"],
    )
    assert "d2_invalid_turn" in response.get_data(as_text=True)
    assert response.status_code == (400 if transport == "json" else 200)
    assert "event: ui" not in response.get_data(as_text=True)
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="sim1-q-ref")).state.revision == first["revision"]
