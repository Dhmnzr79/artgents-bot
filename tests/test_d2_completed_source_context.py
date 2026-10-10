"""Completed source/outcome survives the actual JSON/SSE dialogue projection."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from contracts.response_plan import D2SourceResult, SessionKey
from contracts.d2_session_context import D2SessionActivity
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import build_d2_d1r_messages
from tests.d2_ci_http import FakeProvider, http_env, raw, send, explanation, completed_context


@pytest.fixture(autouse=True)
def show_internal_failure(monkeypatch):
    import core.d2_http_adapter as adapter
    original = adapter.run_d2_dialogue_turn
    def traced(**kwargs):
        try:
            return original(**kwargs)
        except Exception:
            import traceback
            traceback.print_exc()
            raise
    monkeypatch.setattr(adapter, "run_d2_dialogue_turn", traced)


def context(db, sid="sources"):
    with D2DialogueStore(db) as store:
        return completed_context(store, SessionKey(client_id="demo", sid=sid))


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("subject", ["brand", "service"])
def test_new_availability_keeps_source_and_clears_stale_subject(http_env, transport, subject):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(explanation("КТ помогает планировать лечение.",
        target={"type": "service", "id": "tomography"}))))
    send(client, transport, sid="sources", request_id="ct", q="Расскажите про КТ")
    block = explanation("ignored", target={"type": "unresolved"}, brand_id="osstem") if subject == "brand" else explanation("ignored", target={"type": "service", "id": "braces"})
    fake.raw = raw(block)
    args = dict(sid="sources", request_id="availability", q="Есть такой вариант?")
    first = send(client, transport, **args)
    assert send(client, transport, **args) == first
    assert len(fake.inputs) == 2
    projected = context(db)
    assert projected.ordinary.discussion_scope is None
    pair = projected.ordinary.dialogue_pairs[-1]
    ref = "brand_policy:osstem" if subject == "brand" else "service_alternative:braces"
    assert pair.parts[0].source_results == (D2SourceResult(source_ref=ref, outcome="answered"),)
    assert pair.assistant_text == "" and pair.offers == ()
    fake.raw = raw(explanation("Продолжение по последнему предмету."))
    send(client, transport, sid="sources", request_id="continue", q="Расскажите")
    incoming = fake.inputs[-1].context.ordinary
    assert incoming.discussion_scope is None
    assert incoming.dialogue_pairs[-1].parts[0].source_results[0].source_ref == ref
    system, user = build_d2_d1r_messages(fake.inputs[-1])
    assert ref in user["content"] and "source_results" in system["content"]
    if subject == "brand":
        catalog = json.loads(fake.inputs[-1].model_view.clinic_policy_catalog_json)
        answer = next(row["answer"] for row in catalog["brand_policies"] if row["brand_id"] == "osstem")
        assert "могу рассказать" in answer and answer in first["answer"]


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("service,outcome", [("classic", "answered"), ("caries", "excluded")])
def test_scoped_commercial_retains_subject_and_negative_is_not_positive(http_env, transport, service, outcome):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw({"kind": "commercial_fact", "request_id": "r1",
        "target": {"type": "service", "id": service}, "fact_ids": ["installment_12"]})))
    first = send(client, transport, sid="sources", request_id="fact", q="Есть рассрочка на эту услугу?")
    projected = context(db).ordinary
    assert projected.discussion_scope.service_id == service
    pair = projected.dialogue_pairs[-1]
    assert pair.parts[0].service_id == service
    assert pair.parts[0].source_results == (D2SourceResult(source_ref="fact:installment_12", outcome=outcome),)
    assert pair.assistant_text == ""
    assert pair.fact_ids == (("installment_12",) if outcome == "answered" else ())
    assert ("рассрочка не предоставляется" in first["answer"]) == (outcome == "excluded")


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_card_same_subject_fact_contacts_detail_keep_selected_offer(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw({"kind": "price", "request_id": "r1",
        "target": {"type": "service", "id": "classic"}, "brand_id": "nobel_biocare",
        "volume": {"extent": "one_tooth"}})))
    send(client, transport, sid="sources", request_id="price", q="Цена Nobel на один зуб?")
    before = context(db).ordinary
    assert before.d2_shown_price_offer_refs
    fake.raw = raw({"kind": "commercial_fact", "request_id": "r1",
        "target": {"type": "service", "id": "classic"}, "fact_ids": ["installment_12"]})
    send(client, transport, sid="sources", request_id="fact", q="А рассрочка?")
    after = context(db).ordinary
    assert after.discussion_scope == before.discussion_scope
    assert after.d2_shown_price_offer_refs == before.d2_shown_price_offer_refs
    for i, field in enumerate(["contact_address", "contact_hours", "contact_phone", "contact_address"]):
        fake.raw = raw({"kind": "contact", "request_id": "r1", "contact_fields": [field]})
        send(client, transport, sid="sources", request_id=f"contact{i}", q="Контакты?")
    after = context(db).ordinary
    assert len(after.dialogue_pairs) == 3
    assert after.discussion_scope == before.discussion_scope
    assert after.d2_shown_price_offer_refs == before.d2_shown_price_offer_refs
    fake.raw = raw({"kind": "price_detail", "request_id": "r1", "price_detail_aspect": "includes"})
    send(client, transport, sid="sources", request_id="detail", q="Что входит?")
    assert fake.inputs[-1].context.ordinary.d2_shown_price_offer_refs == before.d2_shown_price_offer_refs
    after = context(db).ordinary
    assert after.d2_shown_price_offer_refs == before.d2_shown_price_offer_refs


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_policy_source_and_expired_receipts_do_not_leak(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw({"kind": "clinic_policy", "request_id": "r1", "policy_ids": ["no_oms"]})))
    send(client, transport, sid="sources", request_id="policy", q="Работаете по ОМС?")
    pair = context(db).ordinary.dialogue_pairs[-1]
    assert pair.parts[0].source_results == (D2SourceResult(source_ref="policy:no_oms", outcome="answered"),)
    assert pair.policy_ids == ("no_oms",) and pair.assistant_text == ""
    key = SessionKey(client_id="demo", sid="sources")
    with D2DialogueStore(db) as store:
        record = store.read(key)
        expired = record.model_copy(update={"activity": D2SessionActivity(session_key=key,
            last_user_turn_at=datetime.now(timezone.utc)-timedelta(hours=1))})
        store._connection.execute("UPDATE d2_dialogue SET payload=? WHERE client_id=? AND sid=?",
            (expired.model_dump_json(), key.client_id, key.sid))
        store._connection.commit()
    fake.raw = raw(explanation("Уточните вопрос."))
    send(client, transport, sid="sources", request_id="expired", q="Расскажите")
    assert fake.inputs[-1].context.ordinary.dialogue_pairs == ()


@pytest.mark.parametrize("ref", ["md:test", "policy:", "fact: ", "policy: no_oms"])
def test_source_contract_rejects_invalid_identity(ref):
    with pytest.raises(ValueError, match="d2_source_result_ref_invalid"):
        D2SourceResult(source_ref=ref, outcome="answered")


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_same_subject_availability_keeps_descriptor_without_selecting_alternative(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(explanation("Обсуждаем один зуб.", target={"type": "service", "id": "classic"},
        volume={"extent": "one_tooth"}, brand_id="implantium"))))
    send(client, transport, sid="sources", request_id="first", q="Расскажите про Implantium")
    before = context(db).ordinary.discussion_scope
    fake.raw = raw(explanation("ignored", target={"type": "service", "id": "classic"}, brand_id="osstem"))
    send(client, transport, sid="sources", request_id="brand", q="А Osstem для этого варианта?")
    after = context(db).ordinary
    assert after.discussion_scope == before
    assert after.dialogue_pairs[-1].parts[0].brand_id == "osstem"
    assert after.dialogue_pairs[-1].parts[0].source_results[0].source_ref == "brand_policy:osstem"


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_expired_fact_is_gap_with_identity_and_no_positive_fact(http_env, transport):
    client, db, use, tmp = http_env
    path = tmp / "clients/demo/target_response/pricebook/facts.json"
    facts = json.loads(path.read_text(encoding="utf-8"))
    facts["installment_12"]["active_until"] = "2020-01-01"
    path.write_text(json.dumps(facts, ensure_ascii=False), encoding="utf-8")
    fake = use(FakeProvider(raw({"kind": "commercial_fact", "request_id": "r1",
        "target": {"type": "service", "id": "classic"}, "fact_ids": ["installment_12"]})))
    first = send(client, transport, sid="sources", request_id="fact", q="Рассрочка?")
    assert "недостаточно информации" in first["answer"]
    pair = context(db).ordinary.dialogue_pairs[-1]
    assert pair.parts[0].status == "unavailable"
    assert pair.parts[0].source_results[0].outcome == "unavailable"
    assert pair.fact_ids == () and pair.assistant_text == ""


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_mixed_subjects_keep_order_but_do_not_choose_active_service(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(
        {"kind": "commercial_fact", "request_id": "r1", "target": {"type": "service", "id": "caries"}, "fact_ids": ["installment_12"]},
        explanation("Ответ о КТ.", request_id="r2", target={"type": "service", "id": "tomography"}))))
    send(client, transport, sid="sources", request_id="mixed", q="Рассрочка на лечение кариеса и что такое КТ?")
    after = context(db).ordinary
    assert after.discussion_scope is None
    pair = after.dialogue_pairs[-1]
    assert [p.request_id for p in pair.parts] == ["r1", "r2"]
    assert pair.parts[0].source_results[0].outcome == "excluded"
    assert pair.parts[1].service_id == "tomography"
    assert pair.assistant_text == "Ответ о КТ."


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_bounded_history_masks_pii_and_keeps_reference_identity(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(explanation("Телефон +7 (999) 123-45-67, email test@example.com; " + "Содержательный ответ. " * 100,
        target={"type": "service", "id": "tomography"}))))
    send(client, transport, sid="sources", request_id="long", q="Расскажите подробнее")
    pair = context(db).ordinary.dialogue_pairs[-1]
    assert len(pair.assistant_text) <= 1000
    assert "123-45-67" not in pair.assistant_text and "test@example.com" not in pair.assistant_text
    fake.raw = raw(explanation("ignored", target={"type": "unresolved"}, brand_id="osstem"))
    send(client, transport, sid="sources", request_id="brand", q="Есть Osstem?")
    pair = context(db).ordinary.dialogue_pairs[-1]
    assert pair.parts[0].source_results[0].source_ref == "brand_policy:osstem"


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_repeated_promotion_keeps_each_source_without_duplicate_positive_ledger(http_env, transport):
    client, db, use, _ = http_env
    blocks = [{"kind": "commercial_fact", "request_id": request_id,
        "target": {"type": "service", "id": "classic"}, "promotion_scope": "service"}
        for request_id in ["r1", "r2"]]
    fake = use(FakeProvider(raw(*blocks)))
    args = dict(sid="sources", request_id="promotions", q="Расскажите про акции на эту услугу")
    first = send(client, transport, **args)
    pair = context(db).ordinary.dialogue_pairs[-1]
    assert [p.request_id for p in pair.parts] == ["r1", "r2"]
    assert pair.parts[0].source_results and pair.parts[0].source_results == pair.parts[1].source_results
    assert all(s.outcome == "answered" for s in pair.parts[1].source_results)
    with D2DialogueStore(db) as store:
        resolved = store.read_latest_completion(SessionKey(client_id="demo", sid="sources")).response.resolved
    ids = resolved.finalized_commercial_ids.promo_fact_ids
    assert len(ids) == len(set(ids)) == len(pair.parts[0].source_results)
    assert send(client, transport, **args) == first and len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("target", [{"type": "service", "id": "implantation"}, {"type": "topic", "id": "classic"}])
def test_unknown_commercial_subject_does_not_become_active_context(http_env, transport, target):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw({"kind": "commercial_fact", "request_id": "r1",
        "target": target, "fact_ids": ["installment_12"]})))
    first = send(client, transport, sid="sources", request_id="bad-subject", q="Рассрочка на этот вариант?")
    assert "недостаточно информации" in first["answer"]
    after = context(db).ordinary
    assert after.discussion_scope is None and after.d2_shown_price_offer_refs == ()
    part = after.dialogue_pairs[-1].parts[0]
    assert part.discussion_scope is None
    assert part.source_results[0].source_ref == "fact:installment_12"
    assert part.source_results[0].outcome == "unavailable"


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("target", [{"type": "service", "id": "missing_service"}, {"type": "topic", "id": "clinic"}])
def test_clinic_wide_answer_keeps_only_valid_subject(http_env, transport, target):
    client, db, use, tmp = http_env
    path = tmp / "clients/demo/target_response/pricebook/facts.json"
    facts = json.loads(path.read_text(encoding="utf-8"))
    fact = {**facts["tax_deduction"], "id": "clinic_benefit", "allowed_service_ids": [],
        "allowed_topics": [], "excluded_service_ids": []}
    facts["clinic_benefit"] = fact
    path.write_text(json.dumps(facts, ensure_ascii=False), encoding="utf-8")
    fake = use(FakeProvider(raw({"kind": "commercial_fact", "request_id": "r1",
        "target": target, "fact_ids": ["clinic_benefit"]})))
    first = send(client, transport, sid="sources", request_id="clinic-fact", q="Расскажите об этом условии")
    assert fact["text_fact"] in first["answer"]
    after = context(db).ordinary
    assert after.d2_shown_price_offer_refs == ()
    pair = after.dialogue_pairs[-1]
    assert pair.parts[0].source_results == (D2SourceResult(source_ref="fact:clinic_benefit", outcome="answered"),)
    assert pair.fact_ids == ("clinic_benefit",)
    if target["type"] == "service":
        assert after.discussion_scope is None and pair.parts[0].discussion_scope is None
    else:
        assert after.discussion_scope.topic_id == "clinic"
        assert pair.parts[0].discussion_scope == after.discussion_scope


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("prior", [False, True])
def test_compound_price_owns_matching_commercial_descriptor_before_prior_scope(http_env, transport, prior):
    client, db, use, _ = http_env
    target = {"type": "service", "id": "classic"}
    fake = use(FakeProvider(raw({"kind": "price", "request_id": "r1", "target": target, "brand_id": "implantium"})))
    if prior:
        send(client, transport, sid="sources", request_id="old", q="Цена Implantium?")
    fake.raw = raw(
        {"kind": "price", "request_id": "r1", "target": target, "brand_id": "nobel_biocare"},
        {"kind": "commercial_fact", "request_id": "r2", "target": target, "fact_ids": ["installment_12"]})
    send(client, transport, sid="sources", request_id="compound", q="Цена Nobel и рассрочка?")
    after = context(db).ordinary
    assert after.discussion_scope.service_id == "classic"
    assert after.discussion_scope.brand_id == "nobel_biocare"
    pair = after.dialogue_pairs[-1]
    assert pair.parts[0].discussion_scope == pair.parts[1].discussion_scope
    offers = after.d2_shown_price_offer_refs
    assert len(offers) == 1 and offers[0].offer_id == "classic.one_tooth.nobel"
    fake.raw = raw({"kind": "price_detail", "request_id": "r1", "price_detail_aspect": "includes"})
    send(client, transport, sid="sources", request_id="follow", q="Что входит?")
    assert fake.inputs[-1].context.ordinary.d2_shown_price_offer_refs == offers
    assert context(db).ordinary.d2_shown_price_offer_refs == offers
