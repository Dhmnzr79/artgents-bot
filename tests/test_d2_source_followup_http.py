"""D2-118: authored source UI through JSON/SSE, not live source-selection proof."""
import json

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import build_d2_d1r_messages
from tests.test_d2_document_click_task_http import PromptProvider, _body
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse
from tests.test_d2_live_provider_offline import _request
from tests.test_d2_sim2_dialogues import raw, price, explanation


PAIN = "implantation__faq__pain.md"
DURATION = "implantation__faq__duration.md"
VOLUME = {"extent": "few_teeth", "tooth_count": 3, "jaw": "lower"}


def content(ref, *, request_id="r1", text="Объяснение по материалу клиники."):
    return explanation(text, request_id=request_id, content_ref=ref,
        target={"type": "service", "id": "classic"}, volume=VOLUME,
        brand_id="implantium")


def replies(body):
    return [item["reply_id"] for item in body["ui"]["quick_replies"]]


def test_sent_prompt_pairs_document_grounded_prose_with_existing_source_field():
    system, _ = build_d2_d1r_messages(_request())
    prompt = system["content"]
    assert "For an explanation grounded in a specific document, return its exact filename" in prompt
    assert "no source ref is required for such prose" not in prompt
    examples = prompt.split("=== D2_RESULT_SCHEMA ===", 1)[0]
    duration = next(json.loads(block.split("```", 1)[0])
        for block in examples.split("```json\n")[1:]
        if "installation_duration_from_corpus" in block.split("```", 1)[0])
    assert duration["blocks"][0]["content_ref"].endswith(".md")
    assert "do not invent buttons" in prompt


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("parts", [1, 2])
@pytest.mark.parametrize("doc,anchors,video", [
    (PAIN, ["kakuyu-anesteziyu-ispolzuyut"], True),
    (DURATION, ["ot-chego-zavisit-srok-implantatsii", "mozhno-li-uskorit-implantatsiyu"], False),
])
def test_source_answer_click_replay_next_context_and_nonrepeat(http_env, transport, parts, doc, anchors, video):
    client, db, use, _ = http_env
    blocks = [content(doc, request_id=f"r{i+1}", text=f"Пояснение номер {i+1}.") for i in range(parts)]
    fake = use(PromptProvider(raw(*blocks)))
    send = post if transport == "json" else post_sse
    first = _body(send(client, request_id="source", q="Расскажите о лечении"), transport)
    expected_refs = [f"{doc}#{anchor}" for anchor in anchors]
    assert replies(first) == expected_refs
    key = SessionKey(client_id="demo", sid="cp6a")
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(key)
        assert [b.content_ref for b in saved.response.resolved.information_blocks] == [doc] * parts
        assert saved.response.resolved.ui_plan.source_content_ref == doc
        assert (saved.response.resolved.ui_plan.video is not None) == video
        assert saved.response.resolved.ui_plan.buttons
        descriptor = saved.response.resolved.d2_request_parts[0].discussion_scope
    assert _body(send(client, request_id="source", q="Расскажите о лечении"), transport) == first
    assert len(fake.inputs) == 1

    fake.raw = json.dumps({"explanations": [{"request_id": "r1", "content_text": "Ответ на выбранное продолжение."}]})
    click_args = dict(request_id="click", q="", ref=expected_refs[0], ui_revision=first["revision"])
    clicked = _body(send(client, **click_args), transport)
    task = fake.inputs[-1].known_task.blocks[0]
    assert task.content_ref == doc
    assert task.content_section_refs == (f"a:{anchors[0]}",)
    assert (task.target, task.volume, task.brand_id) == (descriptor.target, descriptor.volume, descriptor.brand_id)
    assert not set(replies(clicked)).intersection(expected_refs)
    assert _body(send(client, **click_args), transport) == clicked
    assert len(fake.inputs) == 2
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(key)
        assert saved.response.resolved.information_blocks[0].content_ref == doc
        assert saved.response.resolved.ui_plan.video is None
    fake.raw = raw(content(doc, text="Продолжаем объяснение."))
    continued = _body(send(client, request_id="next", q="Ещё подробнее"), transport)
    assert fake.inputs[-1].context.ordinary.discussion_scope == descriptor
    assert not set(replies(continued)).intersection([*expected_refs, *replies(clicked)])


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_price_then_duration_has_its_own_document_buttons(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service", volume=VOLUME, brand_id="implantium"))))
    send = post if transport == "json" else post_sse
    first = _body(send(client, request_id="price", q="Цена восстановления трёх зубов?"), transport)
    assert all(not ref.startswith((PAIN, DURATION)) for ref in replies(first))
    fake.raw = raw(content(DURATION))
    answer = _body(send(client, request_id="duration", q="А сколько времени занимает лечение?"), transport)
    assert replies(answer) == [f"{DURATION}#ot-chego-zavisit-srok-implantatsii", f"{DURATION}#mozhno-li-uskorit-implantatsiyu"]
    assert fake.inputs[-1].context.ordinary.discussion_scope.volume.tooth_count == 3
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a"))
        assert saved.response.resolved.d2_price_block is None
        assert saved.response.resolved.d2_request_parts[0].discussion_scope.volume.tooth_count == 3


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("shape", ["two_documents", "price_and_content", "missing_source", "invalid_source"])
def test_suppression_and_missing_source_keep_prose_without_borrowed_buttons(http_env, transport, shape):
    client, db, use, _ = http_env
    blocks = {
        "two_documents": [content(PAIN), content(DURATION, request_id="r2")],
        "price_and_content": [price("classic", "service", volume=VOLUME), content(PAIN, request_id="r2")],
        "missing_source": [content(None)],
        "invalid_source": [content("absent_document.md")],
    }[shape]
    fake = use(FakeProvider(raw(*blocks)))
    send = post if transport == "json" else post_sse
    body = _body(send(client, q="Расскажите о лечении"), transport)
    assert "Объяснение по материалу клиники." in body["answer"]
    assert all(not ref.startswith((PAIN, DURATION)) for ref in replies(body))
    assert len(fake.inputs) == 1
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a"))
        assert saved.response.resolved.ui_plan.video is None
        if shape in {"missing_source", "invalid_source"}:
            assert saved.response.resolved.information_blocks[0].content_ref is None


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_same_document_different_volumes_never_pick_one_as_click_context(http_env, transport):
    client, _, use, _ = http_env
    second = content(DURATION, request_id="r2")
    second["volume"] = {"extent": "one_tooth", "tooth_count": 1, "jaw": "lower"}
    fake = use(FakeProvider(raw(content(DURATION), second)))
    send = post if transport == "json" else post_sse
    first = _body(send(client, request_id="both", q="Расскажите о сроках для одного и трёх зубов"), transport)
    fake.raw = json.dumps({"explanations": [{"request_id": "r1", "content_text": "Общее объяснение сроков."}]})
    _body(send(client, request_id="click", q="", ref=replies(first)[0], ui_revision=first["revision"]), transport)
    assert fake.inputs[-1].known_task.blocks[0].volume is None
    assert fake.inputs[-1].context.ordinary.discussion_scope is None


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_price_detail_chain_keeps_shown_offers_and_scope_without_provider(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service", volume=VOLUME, brand_id="implantium"))))
    send = post if transport == "json" else post_sse
    body = _body(send(client, request_id="price", q="Цена трёх зубов классической имплантацией Implantium?"), transport)
    assert replies(body) == ["price_detail:includes", "price_detail:stages"]
    key = SessionKey(client_id="demo", sid="cp6a")
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(key)
        offer_ids = [r.offer_id for r in saved.response.resolved.d2_price_block.rows]
        descriptor = saved.response.resolved.d2_request_parts[0].discussion_scope
    fake.raw = "Model must not be consulted for a verified detail click"
    for aspect in ("includes", "stages"):
        args = dict(request_id=aspect, q="", ref=f"price_detail:{aspect}", ui_revision=body["revision"])
        body = _body(send(client, **args), transport)
        assert _body(send(client, **args), transport) == body
        assert len(fake.inputs) == 1
        with D2DialogueStore(db) as store:
            saved = store.read_latest_completion(key)
            assert saved.response.resolved.d2_price_detail_block.aspect == aspect
            assert [r.offer_id for r in saved.response.resolved.d2_price_detail_block.rows] == offer_ids
            assert saved.response.resolved.d2_request_parts[0].discussion_scope == descriptor, aspect
    fake.raw = raw(content(DURATION))
    _body(send(client, request_id="duration", q="А по времени лечения?"), transport)
    assert fake.inputs[-1].context.ordinary.discussion_scope == descriptor


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("reverse", [False, True])
def test_same_source_unscoped_part_prevents_borrowing_other_parts_volume(http_env, transport, reverse):
    client, db, use, _ = http_env
    scoped = content(DURATION)
    unscoped = explanation("Общие сведения о сроках.", request_id="r2", content_ref=DURATION)
    blocks = [unscoped, scoped] if reverse else [scoped, unscoped]
    fake = use(FakeProvider(raw(*blocks)))
    send = post if transport == "json" else post_sse
    first = _body(send(client, request_id="mixed", q="Объясните сроки в целом и для трёх зубов"), transport)
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a"))
        assert saved.response.resolved.response_scope == "mixed"
        assert any(p.discussion_scope is None for p in saved.response.resolved.d2_request_parts)
    fake.raw = json.dumps({"explanations": [{"request_id": "r1", "content_text": "Общее объяснение выбранного раздела."}]})
    args = dict(request_id="click", q="", ref=replies(first)[0], ui_revision=first["revision"])
    clicked = _body(send(client, **args), transport)
    task = fake.inputs[-1].known_task.blocks[0]
    assert task.content_ref == DURATION
    assert task.service_id is None and task.volume is None and task.brand_id is None
    assert fake.inputs[-1].context.ordinary.discussion_scope is None
    assert _body(send(client, **args), transport) == clicked
    assert len(fake.inputs) == 2
    fake.raw = raw(explanation("Продолжение общего обсуждения."))
    _body(send(client, request_id="next", q="А ещё подробнее?"), transport)
    scope = fake.inputs[-1].context.ordinary.discussion_scope
    assert scope.topic_id == "implantation" and scope.volume is None and scope.brand_id is None
