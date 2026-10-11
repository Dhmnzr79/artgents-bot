"""Ordinary FullContext replies no longer require information commands."""
import json

import pytest

from contracts.d2_dialogue_result import D2DialogueResult
from core.d2_live_provider import build_d2_d1r_messages
from tests.d2_ci_http import FakeProvider, http_env, raw, send, explanation
from tests.test_d2_sim2_contract import parse


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("question,text", [
    ("Расскажите об Орлове", "Орлов Никита Владимирович — имплантолог, стаж 16 лет."),
    ("Кто у вас имплантологи?", "Имплантацией занимаются Орлов и Волков."),
    ("Детей принимаете?", "Клиника принимает взрослых пациентов."),
    ("Работаете по ОМС?", "По ОМС клиника не работает."),
    ("Есть рассрочка?", "Есть рассрочка до 12 месяцев по условиям клиники."),
    ("Консультация бесплатная?", "Консультация по имплантации бесплатная до конца декабря; КТ отдельно."),
    ("У вас есть Osstem?", "Osstem не ставим. Могу рассказать об Implantium."),
    ("А брекеты?", "Брекеты не устанавливаем; в клинике есть элайнеры."),
    ("Что лучше?", "Вы хотите сравнить коронку на свой зуб и на имплант?"),
])
def test_ordinary_prose_without_ids_reaches_user_and_next_input(http_env, transport, question, text):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(explanation(text))))
    first = send(client, transport, request_id="first", q=question)
    assert first["answer"] == text
    fake.raw = raw(explanation("Продолжение по последнему вопросу."))
    send(client, transport, request_id="next", q="Расскажите")
    assert fake.inputs[-1].context.ordinary.dialogue_pairs[-1].assistant_text == text
    assert len(fake.inputs) == 2


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("metadata", [
    {"brand_id": "osstem", "target": {"type": "unresolved"}},
    {"brand_id": "unknown-brand"},
    {"target": {"type": "service", "id": "braces"}},
    {"target": {"type": "unresolved"}},
    {"target": {"type": "service", "id": "not-in-catalog"}},
    {"target": {"type": "topic", "id": "not-in-catalog"}},
    {"content_ref": "missing_document.md"},
])
def test_optional_metadata_cannot_replace_or_hide_ordinary_answer(http_env, transport, metadata):
    client, _, use, _ = http_env
    text = "Связный ответ по материалам клиники."
    fake = use(FakeProvider(raw(explanation(text, **metadata))))
    result = send(client, transport, request_id="first", q="Расскажите подробнее")
    assert result["answer"] == text
    assert not result["ui"]["quick_replies"]
    fake.raw = raw(explanation("Продолжение."))
    send(client, transport, request_id="next", q="Да")
    assert fake.inputs[-1].context.ordinary.dialogue_pairs[-1].assistant_text == text
    if metadata.get("target", {}).get("id") == "not-in-catalog":
        assert fake.inputs[-1].context.ordinary.discussion_scope is None


@pytest.mark.parametrize("kind", ["doctors", "clinic_policy", "commercial_fact"])
def test_obsolete_commands_rejected_by_actual_parser(kind):
    with pytest.raises(ValueError, match="union_tag_invalid"):
        parse({"outcome": "dialogue", "blocks": [{"kind": kind, "request_id": "r1"}]})
    schema = json.dumps(D2DialogueResult.model_json_schema())
    for name in ("DoctorsOperation", "PolicyOperation", "CommercialOperation"):
        assert name not in schema


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_doctor_question_after_price_is_prose_not_service_directory(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw({"kind": "price", "request_id": "r1", "target": {"type": "service", "id": "all_on_4"}})))
    first = send(client, transport, request_id="price", q="Сколько стоит All-on-4?")
    assert "318" in first["answer"]
    text = "Орлов Никита Владимирович — врач-имплантолог с 16-летним опытом."
    fake.raw = raw(explanation(text, content_ref="doctors__doctor__orlov.md"))
    doctor = send(client, transport, request_id="doctor", q="Расскажите об Орлове Никите Владимировиче")
    assert doctor["answer"] == text
    assert "Эту услугу" not in doctor["answer"]
    system, _ = build_d2_d1r_messages(fake.inputs[-1])
    assert "kind=doctors" not in system["content"]
    assert "Орлов" in system["content"]


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("brand", ["osstem", "not-in-catalog"])
def test_free_brand_answer_does_not_authorize_a_price(http_env, transport, brand):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(explanation("Могу рассказать о системах имплантов."))))
    send(client, transport, request_id="info", q="Расскажите об имплантах")
    fake.raw = raw({"kind": "price", "request_id": "r1", "target": {"type": "service", "id": "classic"}, "brand_id": brand})
    body = send(client, transport, request_id="price", q="Сколько стоит этот бренд?")
    assert not body["ui"]["projected_commercial_ids"]["price_offer_ids"]
    assert "76" not in body["answer"] and "318" not in body["answer"]
    assert len(fake.inputs) == 2


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_automatic_promo_once_then_direct_question_can_repeat(http_env, transport):
    client, _, use, _ = http_env
    ordinary = explanation("Описание классической имплантации.",
        target={"type": "service", "id": "classic"},
        content_ref="implantation__service__classic.md")
    fake = use(FakeProvider(raw(ordinary)))
    first = send(client, transport, request_id="one", q="Расскажите про имплантацию")
    promo_ids = first["ui"]["projected_commercial_ids"]["promo_fact_ids"]
    assert promo_ids
    second = send(client, transport, request_id="two", q="Подробнее")
    assert not second["ui"]["projected_commercial_ids"]["promo_fact_ids"]
    assert second["answer"] == ordinary["content_text"]
    direct = "По имплантации действует бесплатная консультация; КТ оплачивается отдельно."
    fake.raw = raw(explanation(direct))
    third = send(client, transport, request_id="three", q="Повторите условия акции")
    assert third["answer"] == direct
    assert len(fake.inputs) == 3


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_doctor_fullcontext_needs_only_md_profiles(http_env, transport):
    client, _, use, tmp = http_env
    assert not (tmp / "clients/demo/doctor_catalog.json").exists()
    text = "Орлов — имплантолог. Кузнецов занимается ортопедией."
    fake = use(FakeProvider(raw(explanation(text, content_ref="doctors__doctor__overview.md"))))
    body = send(client, transport, q="Расскажите о врачах")
    assert text in body["answer"]
    system = build_d2_d1r_messages(fake.inputs[0])[0]["content"]
    for name in ("fedorova", "grigoriev", "kuznetsov", "morozova", "orlov", "volkov"):
        assert f"---BEGIN APPROVED MD:doctors__doctor__{name}.md---" in system
    assert len(fake.inputs) == 1
