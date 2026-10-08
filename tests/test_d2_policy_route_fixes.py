"""§32: one captured policy authority and durable policy/reference context."""
import json

import pytest
import yaml

from contracts.d2_dialogue_result import D2DialogueResult, PolicyOperation
from tests.d2_ci_http import FakeProvider, http_env, send, raw, explanation
from core.d2_live_provider import build_d2_d1r_messages


def update_rules(tmp, mutate):
    path = tmp / "clients/demo/clinic_policies.yaml"
    rules = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(rules)
    path.write_text(yaml.safe_dump(rules, allow_unicode=True), encoding="utf-8")
    return rules


def next_pair(client, fake, transport):
    fake.raw = raw(explanation("Продолжаем разговор."))
    send(client, transport, request_id="next", q="Расскажите подробнее")
    return fake.inputs[-1].context.ordinary.dialogue_pairs[-1]


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("kind", ["clinic_policy", "price", "booking"])
def test_captured_child_rule_owns_text_ui_and_memory(http_env, monkeypatch, transport, kind):
    client, _, use, tmp = http_env
    import core.clinic_policy_resolver as resolver
    def forbidden(_client):
        raise AssertionError("D2 must not read cached filesystem policy keys")
    monkeypatch.setattr(resolver, "_pack_policy_keys", forbidden)
    rules = update_rules(tmp, lambda rules: rules["policies"]["no_pediatric_dentistry"].pop("triggers"))
    block = {"request_id": "r1", "kind": kind, "age_group": "child"}
    if kind == "price":
        block["target"] = {"type": "service", "id": "caries"}
    fake = use(FakeProvider(raw(block)))
    first = send(client, transport, request_id="first", q="Лечение ребёнка")
    approved = rules["policies"]["no_pediatric_dentistry"]["answer"].strip()
    assert first["answer"].count(approved) == 1
    assert not any(b["action_kind"] == "cta" for b in first["ui"]["buttons"])
    assert send(client, transport, request_id="first", q="Лечение ребёнка") == first
    assert len(fake.inputs) == 1
    pair = next_pair(client, fake, transport)
    assert pair.policy_ids == ("no_pediatric_dentistry",)
    assert pair.assistant_text == ""


def test_explicit_empty_policy_registry_never_falls_back(monkeypatch):
    import core.clinic_policy_resolver as resolver
    monkeypatch.setattr(resolver, "_pack_policy_keys", lambda _: (_ for _ in ()).throw(AssertionError("fallback")))
    block = PolicyOperation(kind="clinic_policy", request_id="r1", policy_ids=("no_oms",))
    result = resolver.resolve_clinic_policy_operations(client_id="demo", operations=(block,), policy_keys=())
    assert result.decisions[0].reason_code == "policy_not_in_pack"
    assert not result.suppress_forbidden_booking_cta


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_ambiguous_policy_is_clarification_with_history_not_new_pending_axis(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw({"kind": "clinic_policy", "request_id": "r1"})))
    first = send(client, transport, request_id="first", q="По полису можно?")
    assert "ОМС или ДМС" in first["answer"]
    assert first["ui"]["buttons"] == []
    pair = next_pair(client, fake, transport)
    assert "ОМС или ДМС" in pair.assistant_text
    assert pair.parts[0].kind == "clarification"
    assert fake.inputs[-1].context.ordinary.clarify_task is None


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_explicit_payment_without_rule_is_gap_not_price_or_false_policy(http_env, transport):
    client, _, use, tmp = http_env
    update_rules(tmp, lambda rules: rules["policies"].pop("no_dms"))
    fake = use(FakeProvider(raw({"kind": "price", "request_id": "r1",
        "target": {"type": "service", "id": "classic"}, "payment_scheme": "dms",
        "payment_scheme_intent": "requested_payment"})))
    first = send(client, transport, request_id="first", q="Сколько стоит по ДМС?")
    assert "недостаточно информации" in first["answer"]
    assert "76" not in first["answer"] and "ОМС или ДМС" not in first["answer"]
    assert "По ДМС напрямую не работаем" not in first["answer"]
    assert first["ui"]["projected_commercial_ids"]["price_offer_ids"] == []


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("kind", ["content", "price", "price_detail"])
def test_inactive_service_keeps_identity_and_captured_alternatives(http_env, transport, kind):
    client, _, use, _ = http_env
    block = {"kind": kind, "request_id": "r1", "target": {"type": "service", "id": "braces"}}
    if kind == "content":
        block["content_text"] = "Брекеты устанавливаем бесплатно."
    if kind == "price_detail":
        block["price_detail_aspect"] = "includes"
    fake = use(FakeProvider(raw(block)))
    first = send(client, transport, request_id="first", q="Хочу брекеты")
    assert "Брекеты мы не устанавливаем" in first["answer"]
    assert "бесплатно" not in first["answer"]
    pair = next_pair(client, fake, transport)
    assert pair.assistant_text == ""
    catalog = json.loads(fake.inputs[-1].model_view.clinic_policy_catalog_json)
    assert {"requested_service_id": "braces", "alternative_service_ids": ["aligners"]} in catalog["service_alternatives"]
    assert pair.parts[0].service_id == "braces"
    assert pair.price_scope is None  # An alternative has not been selected by the user.
    assert fake.inputs[-1].context.ordinary.discussion_scope is None
    assert pair.offers == ()


@pytest.mark.parametrize("kind", ["price", "content"])
def test_single_alternative_still_is_not_a_valid_clarification(kind):
    block = {"kind": kind, "request_id": "r1", "clarification": {"missing": "service", "choices": ["aligners"]}}
    if kind == "content":
        block["pending_question"] = "Могу рассказать про элайнеры."
    with pytest.raises(ValueError, match="at least 2"):
        D2DialogueResult.model_validate({"outcome": "dialogue", "blocks": [block]})


def test_prompt_explains_inactive_target_without_phrase_specific_branch(http_env):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(explanation())))
    send(client)
    system = build_d2_d1r_messages(fake.inputs[0])[0]["content"]
    assert "known inactive service" in system
    assert "Do not turn a proposed alternative" in system
    assert "A single alternative is not a choice menu" in system


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_price_and_commercial_text_still_excluded_from_ordinary_history(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw({"kind": "price", "request_id": "r1",
        "target": {"type": "service", "id": "classic"}, "volume": {"extent": "one_tooth"}})))
    first = send(client, transport, request_id="first", q="Цена одного импланта?")
    assert "76" in first["answer"]
    pair = next_pair(client, fake, transport)
    assert "76" not in pair.assistant_text and "₽" not in pair.assistant_text
    assert pair.offers


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_authored_availability_amount_stays_out_of_ordinary_memory(http_env, transport):
    client, _, use, tmp = http_env
    update_rules(tmp, lambda rules: rules["service_alternatives"][0].update(
        approved_text="Брекеты не устанавливаем. Элайнеры — 123456 рублей."))
    fake = use(FakeProvider(raw({"kind": "content", "request_id": "r1",
        "target": {"type": "service", "id": "braces"}, "content_text": "ignored"})))
    first = send(client, transport, request_id="first", q="Хочу брекеты")
    assert "123456" in first["answer"]
    pair = next_pair(client, fake, transport)
    assert pair.assistant_text == "" and pair.parts[0].service_id == "braces"
    catalog = fake.inputs[-1].model_view.clinic_policy_catalog_json
    assert "123456" not in catalog
    assert '"alternative_service_ids":["aligners"]' in catalog


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_booking_refusal_with_independent_answer_retains_policy_ids(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(explanation("Имплантация обсуждается на консультации."),
        {"kind": "booking", "request_id": "r2", "age_group": "child"})))
    first = send(client, transport, request_id="first", q="Расскажите про имплантацию и запись ребёнка")
    assert "Имплантация обсуждается" in first["answer"]
    assert not any(b["action_kind"] == "cta" for b in first["ui"]["buttons"])
    pair = next_pair(client, fake, transport)
    assert pair.policy_ids == ("no_pediatric_dentistry",)
    assert "дет" not in pair.assistant_text.lower()
