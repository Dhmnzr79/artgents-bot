"""2B: exact tenant financial data reaches the sole call, without selection."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from contracts.d2_dialogue_result import AuthorizedExplanationOperation, D2ExplanationTask
from core.d2_live_provider import D2HttpProvider, build_d2_d1r_messages
from core.d2_tenant_snapshot import (
    _approved_price_catalog_json, build_d2_model_view, load_d2_tenant_snapshot,
)
from core.one_call_prompt_contract import ONE_CALL_KNOWN_TASK_INSTRUCTIONS, one_call_contract_header
from tests.test_d2_live_provider_offline import _request, _response
from tests.test_target_offer_projection import _bundle


def _block(prompt, name):
    body = prompt.split(f"=== {name} ===\n", 1)[1]
    return json.JSONDecoder().raw_decode(body)[0]


def test_sent_catalog_preserves_every_offer_term_and_fact_scope():
    snapshot = load_d2_tenant_snapshot("demo", clients_root=Path("clients"))
    request = replace(_request(), model_view=build_d2_model_view(snapshot))
    calls = []

    def transport(**kwargs):
        calls.append(kwargs)
        return _response()

    assert D2HttpProvider(transport=transport).generate(request) == "{}"
    assert len(calls) == 1
    assert calls[0]["response_format"] == {"type": "json_object"}
    system, user = calls[0]["messages"]
    prices = _block(system["content"], "D2_APPROVED_PRICE_CATALOG")
    facts = _block(system["content"], "COMMERCIAL_FACT_CATALOG")["facts"]
    assert prices["client_id"] == snapshot.client_id
    assert prices["offers"] == [offer.model_dump(mode="json") for offer in snapshot.bundle.offers]
    assert prices["commercial"] == request.model_view.commercial.model_dump(mode="json")
    assert all(set(row) == {"fact_id"} for row in prices["commercial"]["promo_facts"])
    assert len(facts) == len(snapshot.bundle.facts)
    by_id = {row["fact_id"]: row for row in facts}
    assert set(by_id) == set(snapshot.bundle.facts)
    for fact in snapshot.bundle.facts.values():
        expected = fact.model_dump(mode="json")
        expected["fact_id"] = expected.pop("id")
        assert by_id[fact.id] == expected
    # Thin identity semantics remain available, without a second copy of the block.
    for identity in json.loads(request.model_view.commercial_fact_catalog.canonical_json)["facts"]:
        assert all(by_id[identity["fact_id"]][key] == value for key, value in identity.items())
    assert system["content"].count("=== COMMERCIAL_FACT_CATALOG ===") == 1
    assert _block(system["content"], "D2_DIRECTION_PRICES") == [
        row.model_dump(mode="json") for row in request.model_view.direction_prices]
    assert request.model_view.approved_md_corpus in system["content"]
    assert request.context.model_dump_json() in user["content"]


@pytest.mark.parametrize("inactive", [False, True])
def test_catalog_does_not_select_or_drop_inactive_and_price_modes(inactive):
    bundle = _bundle(no_public_active=True)
    if inactive:
        payload = bundle.model_dump()
        for offer in payload["offers"]:
            offer["active"] = False
        bundle = type(bundle).model_validate(payload)
    catalog = json.loads(_approved_price_catalog_json(bundle, "synthetic"))
    assert catalog["client_id"] == "synthetic"
    assert catalog["offers"] == [offer.model_dump(mode="json") for offer in bundle.offers]
    assert {offer["price"]["mode"] for offer in catalog["offers"]} == {
        "fixed", "from", "range", "no_public_price"}
    services = {row["service_id"]: row for row in catalog["services"]}
    assert set(services) == set(bundle.services)
    for service_id, service in bundle.services.items():
        row = services[service_id]
        assert row["active"] == service.active
        assert row["selection"] == service.selection.model_dump(mode="json")
        assert row["options"] == [option.model_dump(mode="json", exclude={"aliases", "content_ref"})
                                  for option in service.options]


def test_price_catalog_uses_captured_bytes_and_never_reloads_tenant(monkeypatch):
    snapshot = load_d2_tenant_snapshot("demo", clients_root=Path("clients"))
    first = build_d2_model_view(snapshot)

    def forbidden(*args, **kwargs):
        raise AssertionError("post-capture filesystem read")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    second = build_d2_model_view(snapshot)
    assert second.approved_price_catalog_json == first.approved_price_catalog_json
    request = replace(_request_without_io(first), model_view=second)
    system, _ = build_d2_d1r_messages(request)
    assert _block(system["content"], "D2_APPROVED_PRICE_CATALOG")["client_id"] == "demo"


def _request_without_io(view):
    from contracts.d2_dialogue import D2ProviderInput
    from contracts.d2_session_context import D2SessionContextProjection
    from contracts.response_plan import SessionKey
    from contracts.response_plan_session import PersistedShownCommercialIds
    return D2ProviderInput(user_message="Сколько стоит?", model_view=view,
        context=D2SessionContextProjection(session_key=SessionKey(client_id="demo", sid="input"),
            source_revision=0, source_turn_index=0, freshness="unknown",
            retained_terminal_state="none", retained_shown_ids=PersistedShownCommercialIds()))


def test_known_document_task_prompt_is_byte_identical_without_price_catalog():
    request = replace(_request(), known_task=D2ExplanationTask(blocks=(
        AuthorizedExplanationOperation(request_id="r1", kind="content",
            content_ref="implantation__faq__pain.md", pending_question="Какую анестезию используют"),)))
    system, user = build_d2_d1r_messages(request)
    assert system["content"] == "\n\n".join((
        one_call_contract_header(), ONE_CALL_KNOWN_TASK_INSTRUCTIONS,
        "=== CLINIC_BUSINESS_POLICIES ===\n" + request.model_view.clinic_policy_catalog_json,
        "=== APPROVED_MD_CORPUS ===\n" + request.model_view.approved_md_corpus,
    ))
    assert user["content"] == "\n\n".join((
        "=== D2_SESSION_CONTEXT ===\n" + request.context.model_dump_json(),
        "=== KNOWN_TASK ===\n" + request.known_task.model_dump_json(),
        "=== D2_SELECTED_DOCUMENT_ACTION ===\nnull",
        "=== USER_MESSAGE ===\n" + request.user_message,
    ))
    assert "D2_APPROVED_PRICE_CATALOG" not in system["content"]
