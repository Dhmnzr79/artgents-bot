from __future__ import annotations

from contracts.pricebook import PricingFact
from core.marketing_policy import decide_promo_fact, filter_promo_facts


def _promo_fact(fact_id: str = "free_implant_consult") -> PricingFact:
    return PricingFact(
        id=fact_id,
        kind="promo",
        text_fact="Promo text.",
        render_mode="natural",
        usable_in=["price_answer"],
        active_until="2026-12-31",
    )


def test_configured_promo_fact_allowed_for_price_route():
    decision = decide_promo_fact(
        client_id="demo",
        fact=_promo_fact(),
        service_id="classic",
        route="price_lookup",
        aspect="overview",
    )

    assert decision.allowed is True
    assert decision.reason == "allowed"
    assert decision.promo_key == "free_implant_consult"


def test_configured_promo_fact_blocked_for_wrong_service():
    decision = decide_promo_fact(
        client_id="demo",
        fact=_promo_fact(),
        service_id="caries",
        route="price_lookup",
        aspect="overview",
    )

    assert decision.allowed is False
    assert decision.reason == "service_not_allowed"


def test_unconfigured_promo_fact_is_suppressed():
    kept, decisions = filter_promo_facts(
        client_id="demo",
        facts=[_promo_fact("unknown_promo")],
        service_id="classic",
        route="price_lookup",
        aspect="overview",
    )

    assert kept == []
    assert decisions[0].reason == "promo_not_configured"


def test_non_promo_fact_passes_through():
    fact = PricingFact(
        id="implant_warranty",
        kind="warranty",
        text_fact="Warranty.",
        render_mode="strict",
        usable_in=["price_answer"],
    )
    kept, decisions = filter_promo_facts(
        client_id="demo",
        facts=[fact],
        service_id="classic",
        route="price_lookup",
    )

    assert kept == [fact]
    assert decisions == []
