"""§34: commercial conditions through real D2 JSON/SSE, with fake provider."""
import json

import pytest

from contracts.response_plan import ResolvedResponsePlan, SessionKey
from pydantic import ValidationError
from core.d2_dialogue_store import D2DialogueStore
from tests.d2_ci_http import FakeProvider, http_env, raw, send
from tests.test_d2_http_contract import post, post_sse, sse_events

COMPAT = "Скидка и рассрочка не суммируются: можно выбрать один вариант."
GAP = "У меня пока недостаточно информации по этому вопросу"


@pytest.fixture(autouse=True)
def audit_off(monkeypatch):
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "0")


def commercial(fact_id=None, *, target=None, request_id="r1", promotion_scope="none"):
    result = {"kind": "commercial_fact", "request_id": request_id,
              "fact_ids": [fact_id] if fact_id else [], "promotion_scope": promotion_scope}
    if target:
        result["target"] = {"type": target[0], "id": target[1]}
    else:
        # These fixtures intentionally ask for the clinic-wide fact/list.
        result["target"] = {"type": "clinic"}
    return result


def saved(db, sid="commercial"):
    with D2DialogueStore(db) as store:
        return store.read_latest_completion(SessionKey(client_id="demo", sid=sid)).response.resolved


def mutate(root, relative, change):
    path = root / "clients" / "demo" / "target_response" / relative
    value = json.loads(path.read_text(encoding="utf-8"))
    change(value)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("target", [None, ("topic", "implantation"),
                                    ("topic", "prosthetics"), ("service", "classic")])
def test_direct_free_consult_has_full_qualified_conditions_and_replay(http_env, transport, target):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(commercial("free_implant_consult", target=target))))
    args = dict(sid="commercial", request_id="free", q="А консультация бесплатная?")
    body = send(client, transport, **args)
    assert "по имплантации и протезированию" in body["answer"]
    assert "31 декабря 2026" in body["answer"]
    assert "КТ при необходимости оплачивается отдельно" in body["answer"]
    resolved = saved(db)
    assert resolved.d2_result_status == "complete"
    assert resolved.d2_exact_text_blocks[0].requested_fact_ids == ("free_implant_consult",)
    assert send(client, transport, **args) == body
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("service,excluded", [("caries", True), ("tooth_extraction", True),
                                             ("professional_whitening", False)])
def test_installment_exclusion_is_authored_other_scope_is_gap(http_env, transport, service, excluded):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(commercial("installment_12", target=("service", service)))))
    body = send(client, transport, sid="commercial", q="Есть рассрочка на эту услугу?")
    resolved = saved(db)
    if excluded:
        assert "На лечение кариеса и удаление зуба рассрочка не предоставляется." in body["answer"]
        assert GAP not in body["answer"]
        assert resolved.d2_result_status == "complete"
        assert resolved.d2_exact_text_blocks[0].requested_fact_ids == ()
    else:
        assert body["answer"] == GAP
        assert "не предоставляется" not in body["answer"]
        assert resolved.d2_result_status == "failed"
        assert resolved.d2_request_parts[0].failure_reason == "d2_commercial_fact_unavailable"
        assert resolved.d2_part_failure_blocks[0].reason == "d2_commercial_fact_unavailable"
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("service,free", [("caries", False), ("classic", True)])
def test_doctors_cta_uses_actual_service_applicability(http_env, transport, service, free):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw({"kind": "doctors", "request_id": "r1",
                                "target": {"type": "service", "id": service}})))
    body = send(client, transport, sid="commercial", q="Кто выполняет эту услугу?")
    cta = [button for button in body["ui"]["buttons"] if button["action_kind"] == "cta"]
    assert len(cta) == 1
    assert ("бесплатн" in cta[0]["label"].casefold()) is free
    assert saved(db).d2_request_parts[0].service_id == service
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("kind,aspect", [("price", None), ("price_detail", "stages")])
def test_direct_promotion_after_previous_show_combines_with_final_offers(http_env, transport, kind, aspect):
    client, db, use, root = http_env
    service = "all_on_4" if aspect else "pterygoid_implants"
    offer = "all_on_4.jaw.nobel" if aspect else "pterygoid_implants.default"
    # Explicit synthetic offer/fact rule tests final-set resolution; demo data
    # itself only declares the real discount/installment fact pair.
    fixture_compat = "Эти тестовые предложения не суммируются."
    mutate(root, "d2_commercial.json", lambda data: data.update(incompatibility_groups=[{
        "group_id": "fixture", "offer_or_fact_ids": ["implant_same_day_discount", offer],
        "explanation_text": fixture_compat}]))
    promo = commercial(target=("service", "classic" if aspect else service), request_id="r2", promotion_scope="service")
    fake = use(FakeProvider(raw(promo)))
    send(client, transport, sid="commercial", request_id="promo", q="Какая акция?")
    operation = {"kind": kind, "request_id": "r1", "target": {"type": "service", "id": service}}
    if aspect:
        operation["price_detail_aspect"] = aspect
        operation["brand_id"] = "nobel_biocare"
    fake.raw = raw(operation, promo)
    body = send(client, transport, sid="commercial", request_id="combined", q="Цена или этапы и акция?")
    assert body["answer"].count(fixture_compat) == 1
    resolved = saved(db)
    assert len(resolved.d2_compatibility_blocks) == 1
    assert set(resolved.d2_compatibility_blocks[0].member_ids) == {
        "implant_same_day_discount", offer}
    assert len(fake.inputs) == 2


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_missing_detail_does_not_count_as_published_offer(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(
        {"kind": "price_detail", "request_id": "r1", "target": {"type": "service", "id": "pterygoid_implants"},
         "price_detail_aspect": "stages"},
        commercial(target=("service", "pterygoid_implants"), request_id="r2", promotion_scope="service"),
    )))
    body = send(client, transport, sid="commercial", q="Какие этапы оплаты и акции?")
    assert "порядок оплаты не указан" in body["answer"]
    assert "скидка" in body["answer"].casefold()
    assert COMPAT not in body["answer"]
    assert saved(db).d2_compatibility_blocks == ()
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_expired_fact_preserves_independent_answer_and_neutral_doctor_cta(http_env, transport):
    client, db, use, root = http_env
    mutate(root, "pricebook/facts.json", lambda facts: facts["free_implant_consult"].update(active_until="2020-01-01"))
    fake = use(FakeProvider(raw(
        commercial("free_implant_consult"),
        {"kind": "content", "request_id": "r2", "content_text": "Независимый ответ о лечении."},
        {"kind": "doctors", "request_id": "r3", "target": {"type": "service", "id": "classic"}},
    )))
    body = send(client, transport, sid="commercial", q="Консультация бесплатная, как лечат и кто врач?")
    assert GAP in body["answer"] and "Независимый ответ о лечении." in body["answer"]
    assert "бесплатн" not in body["answer"].casefold()
    assert all("бесплатн" not in b["label"].casefold() for b in body["ui"]["buttons"])
    resolved = saved(db)
    assert resolved.d2_result_status == "degraded"
    assert [(p.request_id, p.status) for p in resolved.d2_request_parts] == [
        ("r1", "unavailable"), ("r2", "answered"), ("r3", "answered")]
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("excluded", [False, True])
def test_only_published_positive_facts_trigger_compatibility(http_env, transport, excluded):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(
        commercial("installment_12", target=("service", "caries" if excluded else "classic")),
        commercial("implant_same_day_discount", target=("service", "classic"), request_id="r2"),
    )))
    body = send(client, transport, sid="commercial", q="Расскажите про рассрочку и скидку.")
    assert (COMPAT in body["answer"]) is (not excluded)
    assert bool(saved(db).d2_compatibility_blocks) is (not excluded)
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("with_installment", [False, True])
def test_demo_price_discount_requires_actual_installment_for_compatibility(http_env, transport, with_installment):
    client, db, use, _ = http_env
    price = {"kind": "price", "request_id": "r1",
             "target": {"type": "service", "id": "pterygoid_implants"}}
    blocks = [price]
    if with_installment:
        blocks.append(commercial("installment_12", target=("service", "pterygoid_implants"), request_id="r2"))
    fake = use(FakeProvider(raw(*blocks)))
    args = dict(sid="commercial", request_id="price", q="Цена птеригоидного импланта и условия оплаты?")
    body = send(client, transport, **args)
    resolved = saved(db)
    assert [(row.offer_id, row.min_amount) for row in resolved.d2_price_block.rows] == [
        ("pterygoid_implants.default", 95_000)]
    assert "до 15%" in body["answer"]
    assert body["answer"].count(COMPAT) == int(with_installment)
    assert bool(resolved.d2_compatibility_blocks) is with_installment
    if with_installment:
        assert "до 12 месяцев" in body["answer"]
        assert resolved.d2_compatibility_blocks[0].member_ids == (
            "implant_same_day_discount", "installment_12")
    else:
        assert "рассроч" not in body["answer"].casefold()
    assert send(client, transport, **args) == body
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_unknown_fact_remains_strict_and_does_not_publish_sibling(http_env, transport):
    client, db, use, _ = http_env
    use(FakeProvider(raw(commercial("foreign-fact"),
                         {"kind": "content", "request_id": "r2", "content_text": "Не публиковать."})))
    response = (post if transport == "json" else post_sse)(client, sid="commercial")
    if transport == "json":
        assert response.status_code != 200
    else:
        events = dict(sse_events(response))
        assert "error" in events and "ui" not in events and "done" not in events
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="commercial")) is None


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("missing", ["expired_fact", "empty_promotions"])
@pytest.mark.parametrize("sibling", [False, True])
def test_partial_commercial_operation_preserves_facts_and_honest_failure(http_env, transport, missing, sibling):
    client, db, use, root = http_env
    operation = commercial("installment_12", target=("service", "classic"))
    if missing == "expired_fact":
        mutate(root, "pricebook/facts.json", lambda facts: facts["free_implant_consult"].update(active_until="2020-01-01"))
        operation["fact_ids"].append("free_implant_consult")
    else:
        def empty_promotions(data):
            next(p for p in data["service_profiles"] if p["service_id"] == "classic")["promo_refs"] = []
        mutate(root, "d2_commercial.json", empty_promotions)
        operation["promotion_scope"] = "service"
    others = [{"kind": "content", "request_id": "r2", "content_text": "Независимый ответ."}] if sibling else []
    fake = use(FakeProvider(raw(operation, *others)))
    args = dict(sid="commercial", request_id="partial", q="Расскажите про условия оплаты и акции.")
    body = send(client, transport, **args)
    resolved = saved(db)
    exact = resolved.d2_exact_text_blocks[0]
    failure = resolved.d2_part_failure_blocks[0]
    assert body["answer"].count(GAP) == 1
    assert body["answer"].count(exact.display_text) == 1
    assert "12" in exact.display_text and exact.display_text != GAP
    assert failure.display_text == exact.display_text
    assert exact.requested_fact_ids == ("installment_12",)
    assert exact.promo_fact_ids == ()
    assert resolved.finalized_commercial_ids.requested_fact_ids == ("installment_12",)
    assert resolved.d2_request_parts[0].status == "unavailable"
    assert resolved.d2_request_parts[0].failure_reason == failure.reason == "d2_commercial_fact_unavailable"
    assert resolved.d2_result_status == ("degraded" if sibling else "failed")
    if sibling:
        assert "Независимый ответ." in body["answer"]
        assert resolved.d2_request_parts[1].status == "answered"
    tampered = resolved.model_dump(mode="json")
    tampered["d2_part_failure_blocks"][0]["display_text"] = GAP
    with pytest.raises(ValidationError, match="d2_commercial_gap_text_linkage_invalid"):
        ResolvedResponsePlan.model_validate(tampered)
    assert send(client, transport, **args) == body
    assert len(fake.inputs) == 1
    fake.raw = raw({"kind": "content", "request_id": "r1", "content_text": "Следующий ответ."})
    send(client, transport, sid="commercial", request_id="next", q="Спасибо. А как проходит лечение?")
    previous = fake.inputs[-1].context.ordinary.dialogue_pairs[-1]
    assert previous.fact_ids == ("installment_12",)
    assert previous.parts[0].status == "unavailable"
    assert previous.parts[0].failure_reason == "d2_commercial_fact_unavailable"
    assert len(fake.inputs) == 2


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("fact_id", ["free_implant_consult", "implant_same_day_discount"])
@pytest.mark.parametrize("layout", ["same", "promo_first", "direct_first", "auto", "repeated_direct", "repeated_promo"])
def test_overlapping_commercial_publication_has_one_role_and_preserves_answer(http_env, transport, fact_id, layout):
    client, db, use, root = http_env
    target = None if fact_id == "free_implant_consult" else ("service", "pterygoid_implants")
    direct = commercial(fact_id, target=target)
    promo = commercial(target=target, request_id="r2", promotion_scope="general")
    if layout == "same":
        direct["promotion_scope"] = "general"
        blocks = [direct]
    elif layout == "promo_first":
        blocks = [promo, direct]
    elif layout == "direct_first":
        blocks = [direct, promo]
    elif layout == "auto":
        blocks = [direct, {"kind": "price", "request_id": "r2", "target": {"type": "service", "id": "classic"}}]
    elif layout == "repeated_direct":
        blocks = [direct, commercial(fact_id, target=target, request_id="r2")]
    else:
        blocks = [promo, {**promo, "request_id": "r3"}]
    fake = use(FakeProvider(raw(*blocks)))
    args = dict(sid="commercial", request_id="overlap", q="Расскажите об условиях и акциях.")
    body = send(client, transport, **args)
    resolved = saved(db)
    facts = json.loads((root / "clients/demo/target_response/pricebook/facts.json").read_text(encoding="utf-8"))
    authored = facts[fact_id]["text_fact"]
    assert authored in body["answer"]
    assert GAP not in body["answer"]
    assert resolved.d2_result_status == "complete"
    assert all(p.status == "answered" for p in resolved.d2_request_parts)
    requested = resolved.finalized_commercial_ids.requested_fact_ids
    promos = resolved.finalized_commercial_ids.promo_fact_ids
    assert len(requested) == len(set(requested))
    assert len(promos) == len(set(promos))
    assert not set(requested) & set(promos)
    if layout != "repeated_promo":
        assert requested == (fact_id,)
        assert fact_id not in promos
        assert body["answer"].count(authored) == (2 if layout == "repeated_direct" else 1)
    if layout in {"same", "promo_first", "direct_first", "repeated_promo"}:
        assert "professional_whitening_discount" in promos
        assert set(requested) | set(promos) == {
            "free_implant_consult", "implant_same_day_discount", "professional_whitening_discount"}
    assert send(client, transport, **args) == body
    assert len(fake.inputs) == 1
    if requested:
        tampered = resolved.model_dump(mode="json")
        tampered["d2_exact_text_blocks"][0]["promo_fact_ids"].append(fact_id)
        with pytest.raises(ValidationError, match="visible_fact_id_role_conflict"):
            ResolvedResponsePlan.model_validate(tampered)
    fake.raw = raw({"kind": "content", "request_id": "r1", "content_text": "Следующий ответ."})
    send(client, transport, sid="commercial", request_id="next", q="А как проходит лечение?")
    previous = fake.inputs[-1].context.ordinary.dialogue_pairs[-1]
    assert set(previous.fact_ids) == set(requested) | set(promos)
    assert len(previous.fact_ids) == len(set(previous.fact_ids))
    assert all(p.status == "answered" for p in previous.parts)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_completely_covered_promo_request_repeats_text_without_gap_or_duplicate_role(http_env, transport):
    client, db, use, root = http_env
    mutate(root, "d2_commercial.json", lambda data: next(
        p for p in data["service_profiles"] if p["service_id"] == "classic").update(promo_refs=["free_implant_consult"]))
    fake = use(FakeProvider(raw(
        commercial(target=("service", "classic"), promotion_scope="service"),
        commercial("free_implant_consult", request_id="r2"),
    )))
    body = send(client, transport, sid="commercial", q="Какие акции и условия консультации?")
    resolved = saved(db)
    assert GAP not in body["answer"] and resolved.d2_result_status == "complete"
    assert resolved.finalized_commercial_ids.requested_fact_ids == ("free_implant_consult",)
    assert resolved.finalized_commercial_ids.promo_fact_ids == ()
    assert all(p.status == "answered" for p in resolved.d2_request_parts)
    assert resolved.d2_exact_text_blocks[0].promo_fact_ids == ()
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_unavailable_direct_does_not_suppress_applicable_promo(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(
        commercial("free_implant_consult", target=("service", "caries")),
        commercial(target=("service", "classic"), request_id="r2", promotion_scope="service"),
    )))
    body = send(client, transport, sid="commercial", q="Какие условия консультации для этих услуг?")
    resolved = saved(db)
    assert GAP in body["answer"] and "по имплантации и протезированию" in body["answer"]
    assert resolved.d2_result_status == "degraded"
    assert resolved.finalized_commercial_ids.requested_fact_ids == ()
    assert "free_implant_consult" in resolved.finalized_commercial_ids.promo_fact_ids
    assert [p.status for p in resolved.d2_request_parts] == ["unavailable", "answered"]
    assert len(fake.inputs) == 1
