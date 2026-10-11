"""Stage I: independent acceptance through the real JSON/SSE D2 route."""
import pytest

from contracts.d2_dialogue_result import D2RejectedOperation
from tests.d2_ci_http import FakeProvider, http_env, raw, send, explanation
from tests.test_d2_sim2_contract import parse


@pytest.mark.parametrize("metadata", [
    {"age_group": "unknown", "payment_scheme": "unspecified", "policy_ids": [0]},
    {"content_ref": "invalid"},
    {"content_section_refs": ["missing"]},
    {"target": {"type": "bad", "id": "classic"}},
    {"volume": {"extent": "one_tooth", "tooth_count": 3}},
    {"clarification": None},
])
@pytest.mark.parametrize("transport", ["json", "sse"])
def test_optional_claim_failure_preserves_text_history_and_replay(http_env, metadata, transport):
    client, _, use, _ = http_env
    text = "Консультация по имплантации бесплатная. КТ оплачивается отдельно."
    fake = use(FakeProvider(raw(explanation(text, **metadata))))
    body = send(client, transport, request_id="one", q="Консультация бесплатная?")
    assert body["answer"] == text
    assert not body["ui"]["quick_replies"]
    assert not body["ui"]["projected_commercial_ids"]["price_offer_ids"]
    replay = send(client, transport, request_id="one", q="Консультация бесплатная?")
    assert replay["answer"] == body["answer"]
    assert len(fake.inputs) == 1
    fake.raw = raw(explanation("Продолжение ответа."))
    send(client, transport, request_id="two", q="Расскажите")
    assert fake.inputs[-1].context.ordinary.dialogue_pairs[-1].assistant_text == text
    assert len(fake.inputs) == 2


BAD_PARTS = [
    {"kind": "price", "target": {"type": "service", "id": "classic"}, "brand_id": ["nobel_biocare"]},
    {"kind": "price"},
    {"kind": "price_detail", "price_detail_aspect": "includes", "price_detail_offer_id": "does_not_exist"},
    {"kind": "price_detail", "price_detail_aspect": "includes", "target": {"type": "service", "id": "does_not_exist"}},
    {"kind": "contact", "contact_fields": ["contact_address"], "contact_branch_id": "does_not_exist"},
    {"kind": "booking", "age_group": "invalid"},
    {"kind": "content", "content_text": "  "},
    {"kind": "content", "content_text": "Ответ", "pending_question": "Вопрос",
     "clarification": {"missing": "term"}},
]


@pytest.mark.parametrize("bad", BAD_PARTS)
@pytest.mark.parametrize("transport", ["json", "sse"])
def test_bad_independent_part_does_not_cancel_text_or_execute_action(http_env, bad, transport):
    client, _, use, _ = http_env
    text = "Врач обсудит с вами варианты на консультации."
    fake = use(FakeProvider(raw(explanation(text), {"request_id": "r2", **bad})))
    body = send(client, transport, request_id="one", q="Расскажите о консультации и стоимости")
    assert body["answer"].startswith(text)
    assert "Не получилось подготовить эту часть ответа" in body["answer"]
    assert not body["ui"]["projected_commercial_ids"]["price_offer_ids"]
    assert not body["ui"]["quick_replies"]
    fake.raw = raw(explanation("Продолжение."))
    send(client, transport, request_id="two", q="Расскажите")
    assert len(fake.inputs) == 2  # A rejected booking must not enter name collection.
    assert fake.inputs[-1].context.ordinary.dialogue_pairs[-1].assistant_text == body["answer"]


def test_independent_parser_order_identity_and_long_text():
    text = "Подробности лечения. " * 250
    result = parse({"outcome": "dialogue", "blocks": [
        {"kind": "content", "request_id": 0, "content_text": text},
        {"kind": "price", "request_id": 0, "volume": "broken"},
        {"kind": "content", "request_id": 0, "content_text": "Далее."},
    ]})
    assert [b.request_id for b in result.blocks] == ["r1", "r2", "r3"]
    assert result.blocks[0].content_text == text
    assert isinstance(result.blocks[1], D2RejectedOperation)
    assert result.blocks[2].content_text == "Далее."


@pytest.mark.parametrize("blocks", [
    [{"kind": "content", "content_text": ""}],
    [{"kind": "content", "content_text": 12}],
    [{"kind": "booking", "age_group": "invalid"}],
])
def test_no_valid_part_still_fails(blocks):
    with pytest.raises(ValueError):
        parse({"outcome": "dialogue", "blocks": blocks})


def test_bad_command_does_not_erase_price_guards():
    result = parse({"outcome": "dialogue", "blocks": [
        {"kind": "price", "target": {"type": "service", "id": "classic"}, "age_group": "child"},
        {"kind": "price", "target": {"type": "service", "id": "classic"}, "payment_scheme": ["oms"]},
    ]})
    assert result.blocks[0].age_group == "child"
    assert isinstance(result.blocks[1], D2RejectedOperation)


@pytest.mark.parametrize("payload", [
    {"outcome": "admin", "blocks": [{"kind": "content", "request_id": "r1", "content_text": "Ответ"}]},
    {"outcome": "bad", "blocks": []},
])
def test_root_conflict_does_not_publish_partial_text(payload):
    with pytest.raises(ValueError):
        parse(payload)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_bad_text_cannot_cancel_verified_price(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(
        {"kind": "price", "request_id": "r1", "target": {"type": "service", "id": "classic"},
         "brand_id": "nobel_biocare", "volume": {"extent": "one_tooth"}},
        {"kind": "content", "request_id": "r2", "content_text": 12},
    )))
    body = send(client, transport, q="Сколько стоит Nobel на один зуб? Расскажите об операции.")
    assert body["ui"]["projected_commercial_ids"]["price_offer_ids"] == ["classic.one_tooth.nobel"]
    assert "101" in body["answer"]
    assert "Не получилось подготовить эту часть ответа" in body["answer"]
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_partial_acceptance_preserves_child_price_refusal(http_env, transport):
    client, _, use, _ = http_env
    text = "Информация о клинике."
    use(FakeProvider(raw(explanation(text, unused_field=True),
        {"kind": "price", "request_id": "r2", "target": {"type": "service", "id": "classic"},
         "age_group": "child", "context": "current_care"})))
    body = send(client, transport, q="Расскажите о клинике и цене для ребёнка")
    assert text in body["answer"]
    assert "взросл" in body["answer"].lower() or "дет" in body["answer"].lower()
    assert not body["ui"]["projected_commercial_ids"]["price_offer_ids"]
    assert not body["ui"]["buttons"]


@pytest.mark.parametrize("bad_first", [False, True])
def test_partial_acceptance_does_not_promote_second_price(http_env, bad_first):
    client, _, use, _ = http_env
    valid = {"kind": "price", "request_id": "r2", "target": {"type": "service", "id": "caries"}}
    invalid = {"kind": "price", "request_id": "r1", "brand_id": ["invalid"]}
    use(FakeProvider(raw(*( (invalid, valid) if bad_first else (valid, invalid) ))))
    body = send(client, q="Две цены")
    assert "Не получилось подготовить эту часть ответа" in body["answer"]
    offers = body["ui"]["projected_commercial_ids"]["price_offer_ids"]
    assert bool(offers) is not bad_first
    if bad_first:
        assert "следующей услуги" in body["answer"]


def test_unrecognizable_part_has_no_executable_identity():
    result = parse({"outcome": "dialogue", "blocks": [
        {"kind": ["booking"]}, {"kind": "content", "content_text": "Ответ"},
    ]})
    assert isinstance(result.blocks[0], D2RejectedOperation)
    assert result.blocks[0].kind == "reference"
    assert result.blocks[1].content_text == "Ответ"


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("target", [None, {"type": "service", "id": "classic"}])
def test_invalid_pending_task_is_not_repaired_or_saved(http_env, transport, target):
    from contracts.response_plan import SessionKey
    from core.d2_dialogue_store import D2DialogueStore
    client, db, use, _ = http_env
    text = "Самостоятельный ответ о клинике."
    use(FakeProvider(raw(explanation(text), {
        "kind": "content", "request_id": "r2", "pending_question": "Расскажите об услуге",
        "clarification": {"missing": "service", "choices": ["classic", "all_on_4"]},
        "target": target, "brand_id": "nobel_biocare", "volume": "broken",
    })))
    body = send(client, transport, sid="pending", q="Расскажите подробнее")
    assert body["answer"].startswith(text)
    assert "Не получилось подготовить эту часть ответа" in body["answer"]
    assert not body["ui"]["quick_replies"]
    with D2DialogueStore(db) as store:
        state = store.read(SessionKey(client_id="demo", sid="pending")).state
        assert not state.clarify_pending and state.clarify_task is None


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("selector", [
    {"price_detail_offer_ordinal": 1},
    {"price_detail_offer_id": "classic.one_tooth.implantium"},
])
@pytest.mark.parametrize("constraint", [{"brand_id": "nobel_biocare"}, {"volume": {"extent": "full_arch"}}])
def test_ordinary_selector_conflict_is_local(http_env, transport, selector, constraint):
    from contracts.response_plan import SessionKey
    from core.d2_dialogue_store import D2DialogueStore
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw({"kind": "price", "request_id": "r1",
        "target": {"type": "service", "id": "classic"}, "brand_id": "implantium",
        "volume": {"extent": "one_tooth"}})))
    send(client, transport, sid="selector", request_id="first", q="Цена Implantium на один зуб?")
    text = "Самостоятельное объяснение."
    fake.raw = raw(explanation(text), {"kind": "price_detail", "request_id": "r2",
        "price_detail_aspect": "includes", **selector, **constraint})
    body = send(client, transport, sid="selector", request_id="second", q="Расскажите подробнее")
    assert body["answer"].startswith(text)
    assert "Не получилось подготовить эту часть ответа" in body["answer"]
    with D2DialogueStore(db) as store:
        resolved = store.read_latest_completion(SessionKey(client_id="demo", sid="selector")).response.resolved
        assert resolved.d2_result_status == "degraded"
        assert resolved.d2_price_detail_blocks == ()
    assert len(fake.inputs) == 2


@pytest.mark.parametrize("source", ["history", "action"])
def test_foreign_detail_binding_stays_fatal(source):
    from contracts.d2_dialogue_result import DetailOperation
    from contracts.response_plan import D2PriceDetailUiAction
    from contracts.response_plan_session import D2ShownPriceOfferRef
    from contracts.response_plan_materialization import MaterializationOwnershipError
    from core.response_plan_materialization import _d2_price_detail_offer_ids
    from tests.test_d2_independent_request_parts import _sources_ab
    sources = _sources_ab()
    operation = DetailOperation(kind="price_detail", request_id="r1", price_detail_aspect="includes")
    ref = D2ShownPriceOfferRef(source_client_id="nikadent", offer_id="foreign", service_id="foreign")
    action = D2PriceDetailUiAction(source_client_id="nikadent", reply_id="price_detail:includes",
        aspect="includes", service_id="foreign", offer_ids=("foreign",))
    with pytest.raises(MaterializationOwnershipError):
        _d2_price_detail_offer_ids(operation, sources=sources,
            shown_price_offer_refs=(ref,) if source == "history" else (),
            selected_action=action if source == "action" else None)
