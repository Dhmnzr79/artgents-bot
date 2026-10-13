"""Facts own promo eligibility; selected cards ignore the prose repeat ledger."""
import json
from datetime import date
from pathlib import Path

import pytest

from core.d2_commercial_plan import resolve_d2_commercial_plan
from contracts.response_plan_materialization import D2CommercialAuthority
from core.d2_tenant_snapshot import load_d2_tenant_snapshot
from tests.d2_ci_http import FakeProvider, http_env, raw, send, explanation


def ids(body):
    return body["ui"]["projected_commercial_ids"]["promo_fact_ids"]


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_no_profile_prose_once_then_card_and_tab_always(http_env, transport):
    client, _, use, tmp = http_env
    path = tmp / "clients/demo/target_response/d2_commercial.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["service_profiles"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    fake = use(FakeProvider(raw(explanation("Описание All-on-4.",
        target={"type": "service", "id": "all_on_4"}, content_ref="implantation__service__all_on_4.md"))))
    first = send(client, transport, request_id="info", q="Расскажите об All-on-4")
    expected = ["free_implant_consult", "implant_same_day_discount"]
    assert ids(first) == expected
    assert ids(send(client, transport, request_id="again", q="Подробнее")) == []
    fake.raw = raw({"kind": "price", "request_id": "r1", "target": {"type": "service", "id": "all_on_4"}})
    price = send(client, transport, request_id="price", q="Сколько стоит?")
    assert ids(price) == expected
    assert any(part.get("price_section") == "promotion" and part["price_owned"]
               for part in price["ui"]["body_parts"])
    def forbidden(*args):
        raise AssertionError("A verified tab must not call the model")
    fake.generate = forbidden
    args = dict(request_id="tab", q="", ref="price_select:all_on_4.jaw.impro", ui_revision=price["revision"])
    tab = send(client, transport, **args)
    assert ids(tab) == expected
    card = next(p for p in tab["ui"]["body_parts"] if p["kind"] == "price_card")
    assert card["price"]["rows"][0]["offer_id"] == "all_on_4.jaw.impro"
    assert send(client, transport, **args) == tab
    assert len(fake.inputs) == 3


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_topic_uses_only_explicit_topic_fact(http_env, transport):
    client, _, use, _ = http_env
    use(FakeProvider(raw(explanation("Обзор имплантации.", target={"type": "topic", "id": "implantation"}))))
    body = send(client, transport, q="Расскажите об имплантации")
    assert ids(body) == ["free_implant_consult"]
    assert body["ui"]["projected_commercial_ids"]["price_offer_ids"] == []


@pytest.mark.parametrize("fault", ["expired", "inactive", "excluded", "wrong_service"])
def test_fact_restrictions_apply_without_offer_or_profile_lists(http_env, fault):
    client, _, use, tmp = http_env
    path = tmp / "clients/demo/target_response/pricebook/facts.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    fact = data["free_implant_consult"]
    if fault == "expired": fact["active_until"] = "2020-01-01"
    elif fault == "inactive": fact["active"] = False
    elif fault == "excluded":
        fact["excluded_service_ids"] = ["all_on_4"]
        fact["excluded_scope_text"] = "На All-on-4 это предложение не распространяется."
    else: fact["allowed_service_ids"] = ["classic"]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    use(FakeProvider(raw({"kind": "price", "request_id": "r1", "target": {"type": "service", "id": "all_on_4"}})))
    body = send(client, q="Стоимость All-on-4?")
    assert ids(body) == ["implant_same_day_discount"]
    assert body["ui"]["projected_commercial_ids"]["price_offer_ids"] == ["all_on_4.jaw.implantium"]


def test_date_boundaries_and_card_has_all_promos():
    snapshot = load_d2_tenant_snapshot("demo", clients_root=Path("clients"))
    bundle = snapshot.bundle
    common = dict(authority=D2CommercialAuthority(source_client_id="demo"), bundle=bundle,
                  service_id="all_on_4", include_packages=False, skip_shown=False, max_promo=None)
    assert {p.fact_id for p in resolve_d2_commercial_plan(**common, as_of=date(2026, 12, 31)).promo_blocks} == {
        "free_implant_consult", "implant_same_day_discount"}
    assert resolve_d2_commercial_plan(**common, as_of=date(2027, 1, 1)).promo_blocks == ()


def test_new_fact_needs_no_offer_reference_and_card_does_not_truncate(http_env):
    client, _, use, tmp = http_env
    path = tmp / "clients/demo/target_response/pricebook/facts.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["third_promo"] = dict(data["free_implant_consult"], id="third_promo",
        text_fact="Дополнительное предложение для All-on-4.", microfact_text="Дополнительное предложение.",
        allowed_service_ids=["all_on_4"], allowed_topics=[])
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    use(FakeProvider(raw({"kind": "price", "request_id": "r1", "target": {"type": "service", "id": "all_on_4"}})))
    assert ids(send(client, q="Цена All-on-4?")) == ["free_implant_consult", "implant_same_day_discount", "third_promo"]


def test_promo_validation_does_not_depend_on_optional_commercial_file(http_env):
    from tests.d2_ci_http import post
    client, _, use, tmp = http_env
    target = tmp / "clients/demo/target_response"
    (target / "d2_commercial.json").unlink()
    path = target / "pricebook/facts.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["free_implant_consult"].pop("microfact_text")
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    fake = use(FakeProvider(raw(explanation("Не должен публиковаться."))))
    response = post(client)
    assert response.get_json()["error"] == "d2_invalid_turn"
    assert fake.inputs == []
