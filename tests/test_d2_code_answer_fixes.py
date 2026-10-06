"""Code-owned answer fixes through durable HTTP, replay and next-turn context."""
import json

import pytest
from pydantic import ValidationError

from contracts.d2_dialogue_result import DetailOperation
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse
from tests.test_d2_document_click_task_http import _body


def envelope(*blocks):
    return json.dumps({"outcome": "dialogue", "blocks": blocks}, ensure_ascii=False)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_off_topic_has_no_dental_ui_and_replays_without_model(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(envelope({"kind": "off_topic", "request_id": "r1"})))
    send = post if transport == "json" else post_sse
    args = dict(request_id="outside", q="Расскажи про курс валют")
    first = _body(send(client, **args), transport)
    assert first["answer"].strip()
    assert first["ui"]["buttons"] == first["ui"]["quick_replies"] == []
    assert _body(send(client, **args), transport) == first
    assert len(fake.inputs) == 1
    # The restriction belongs to this turn; ordinary dental CTA still works.
    fake.raw = envelope({"kind": "price", "request_id": "r1",
                         "target": {"type": "service", "id": "classic"}})
    following = _body(send(client, request_id="dental", q="Цена имплантации?"), transport)
    assert following["ui"]["buttons"]


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("block,expected", [
    ({"kind": "clinic_policy", "request_id": "r1", "payment_scheme": "oms",
      "payment_scheme_intent": "eligibility_question"}, {"no_oms"}),
    ({"kind": "clinic_policy", "request_id": "r1", "age_group": "child"},
     {"no_pediatric_dentistry"}),
    ({"kind": "price", "request_id": "r1", "age_group": "child",
      "target": {"type": "service", "id": "classic"}}, {"no_pediatric_dentistry"}),
])
def test_effective_policy_is_in_next_provider_context(http_env, transport, block, expected):
    client, _, use, _ = http_env
    fake = use(FakeProvider(envelope(block)))
    send = post if transport == "json" else post_sse
    first = _body(send(client, request_id="policy", q="Уточните правила клиники"), transport)
    assert first["answer"].strip()
    if "no_pediatric_dentistry" in expected:
        assert first["ui"]["buttons"] == []
    fake.raw = envelope({"kind": "off_topic", "request_id": "r1"})
    _body(send(client, request_id="next", q="Следующий вопрос"), transport)
    pair = fake.inputs[-1].context.ordinary.dialogue_pairs[-1]
    assert set(pair.policy_ids) == expected
    assert pair.assistant_text == ""  # IDs, not authored prose or financial text.


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_adult_booking_clarification_never_claims_pediatric_refusal_or_starts_lead(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(envelope({"kind": "booking", "request_id": "r1",
                                   "age_group": "adult", "context": "past_history"})))
    send = post if transport == "json" else post_sse
    args = dict(request_id="booking-unclear", q="Я раньше записывался")
    first = _body(send(client, **args), transport)
    assert "Уточните" in first["answer"]
    assert "детск" not in first["answer"].casefold()
    assert first["ui"]["buttons"] == first["ui"]["quick_replies"] == []
    import session
    with session.session_client_scope("demo"):
        assert session.peek_lead_activity("cp6a") == (False, False)
    assert _body(send(client, **args), transport) == first
    assert len(fake.inputs) == 1
    fake.raw = envelope({"kind": "booking", "request_id": "r1", "age_group": "adult"})
    normal = _body(send(client, request_id="booking-now", q="Хочу записаться сейчас"), transport)
    assert "Как к вам обращаться" in normal["answer"]
    with session.session_client_scope("demo"):
        assert session.peek_lead_activity("cp6a") == (False, True)


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("fields,policy_id", [
    ({"age_group": "child"}, "no_pediatric_dentistry"),
    ({"age_group": "adult", "payment_scheme": "oms",
      "payment_scheme_intent": "requested_payment"}, "no_oms"),
])
def test_booking_prohibition_keeps_actual_clinic_answer_and_no_lead(http_env, transport, fields, policy_id):
    client, _, use, tmp_path = http_env
    fake = use(FakeProvider(envelope({"kind": "booking", "request_id": "r1", **fields})))
    send = post if transport == "json" else post_sse
    args = dict(request_id="blocked-booking", q="Хочу записаться")
    body = _body(send(client, **args), transport)
    import yaml
    policy = yaml.safe_load((tmp_path / "clients/demo/clinic_policies.yaml").read_text(encoding="utf-8"))
    assert policy["policies"][policy_id]["answer"].strip() in body["answer"]
    assert body["ui"]["buttons"] == body["ui"]["quick_replies"] == []
    if policy_id == "no_oms":
        assert policy["policies"]["no_pediatric_dentistry"]["answer"].strip() not in body["answer"]
    import session
    with session.session_client_scope("demo"):
        assert session.peek_lead_activity("cp6a") == (False, False)
    assert _body(send(client, **args), transport) == body
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("ordinal", [True, 1.0, "1", False, 0])
def test_detail_selector_does_not_coerce_invalid_types_or_zero(ordinal):
    with pytest.raises(ValidationError):
        DetailOperation(kind="price_detail", request_id="r1", price_detail_aspect="includes",
                        price_detail_offer_ordinal=ordinal)
    assert DetailOperation(kind="price_detail", request_id="r1", price_detail_aspect="includes",
                           price_detail_offer_ordinal=1).price_detail_offer_ordinal == 1


@pytest.mark.parametrize("topic", ["implantation", "prosthetics", "restoration"])
def test_overview_price_rows_keep_unit_on_same_line_and_no_repeated_cta(http_env, topic):
    client, db, use, _ = http_env
    use(FakeProvider(envelope({"kind": "price", "request_id": "r1",
                              "target": {"type": "topic", "id": topic}})))
    body = _body(post(client, request_id="overview", q="Какие варианты и цены?"), "json")
    from core.d2_dialogue_store import D2DialogueStore
    from contracts.response_plan import SessionKey
    with D2DialogueStore(db) as store:
        plan = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved
    assert body["ui"]["buttons"]
    for row in plan.d2_price_block.rows:
        line = next(line for line in body["answer"].splitlines() if row.price_display_text in line)
        assert row.scope_text in line
        for condition in row.condition_texts:
            assert condition in body["answer"]
    assert "\n  " not in body["answer"]
    if plan.textual_cta_block:
        assert plan.textual_cta_block.text not in body["answer"]
