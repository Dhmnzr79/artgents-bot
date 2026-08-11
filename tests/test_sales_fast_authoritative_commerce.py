"""Tests for sales-fast authoritative commerce ownership."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from contracts.effective_scope import EffectiveScope
from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.response_schema import TargetGenericPricePolicy
from core.sales_fast_authoritative_commerce import (
    AuthoritativeCommerceResult,
    apply_authoritative_commerce_to_patient_text,
    build_authoritative_commerce_result,
    resolve_authoritative_commerce,
)
from core.sales_fast_presentation import supplement_sales_fast_patient_text_with_marketing
from core.target_client_data import load_target_client_data
from core.target_strategy_context import strategy_match_from_effective_scope


def _authority() -> ExactSalesFieldAuthority:
    return ExactSalesFieldAuthority(authority="exact_turn", provenance="test")


def _resolution(**kwargs: object) -> ExactSalesResolution:
    auth = _authority()
    return ExactSalesResolution(
        service_id=kwargs.get("service_id", "classic"),
        aspect=kwargs.get("aspect", "price"),
        extent=kwargs.get("extent", "one_tooth"),
        jaw=kwargs.get("jaw", None),
        stage=kwargs.get("stage", None),
        service_id_authority=auth,
        aspect_authority=auth,
        extent_authority=auth,
        jaw_authority=auth,
        stage_authority=auth,
    )


def _strategy_context(**kwargs: object) -> object:
    return strategy_match_from_effective_scope(
        EffectiveScope(extent=kwargs.get("extent", "one_tooth")),
        service_family=str(kwargs.get("family", "implantology")),
    )


def _classic_one_tooth_offers(bundle: object) -> tuple:
    return tuple(
        offer
        for offer in bundle.offers
        if offer.service_id == "classic" and "one_tooth" in offer.applies_to_extents
    )


def _commerce_result(
    bundle: object,
    offers: tuple,
    *,
    explicit_offer_id: str | None = None,
    selected_brand_id: str | None = None,
) -> AuthoritativeCommerceResult:
    bound = _fake_bound_package(
        offers,
        selected_brand_id=selected_brand_id,
        max_options=3,
        service_id="classic",
    )
    return build_authoritative_commerce_result(
        bound_package=bound,
        resolution=_resolution(),
        bundle=bundle,
        strategy_context=_strategy_context(),
    )


def test_generic_price_overview_shows_entry_and_three_offers() -> None:
    bundle = load_target_client_data("demo").bundle
    offers = _classic_one_tooth_offers(bundle)
    result = _commerce_result(bundle, offers)
    assert result.presentation_mode == "overview"
    assert result.entry_price_amount == 76200
    assert result.patient_price_block is not None
    assert "от 76" in result.patient_price_block and "200" in result.patient_price_block
    assert "Implantium" in result.patient_price_block
    assert "Impro" in result.patient_price_block
    assert "Nobel" in result.patient_price_block
    assert result.featured_offer_id == "classic.one_tooth.impro"
    assert "рекомендуемый" in result.patient_price_block
    assert result.widget_offer_payload is not None
    assert result.widget_offer_payload["mode"] == "overview"
    assert result.widget_offer_payload["entry_amount"] == 76200
    offer_ids = [row["offer_id"] for row in result.widget_offer_payload["offers"]]
    assert offer_ids[0] == "classic.one_tooth.impro"
    assert len(offer_ids) == 3


def test_featured_impro_is_not_the_only_price() -> None:
    bundle = load_target_client_data("demo").bundle
    offers = _classic_one_tooth_offers(bundle)
    result = _commerce_result(bundle, offers)
    assert result.presentation_mode == "overview"
    assert result.selected_exact_offer is None
    assert 76200 in result.authoritative_amounts
    assert 101200 in result.authoritative_amounts
    widget = result.widget_offer_payload or {}
    assert widget.get("mode") == "overview"
    assert widget.get("amount") is None


def test_explicit_implantium_returns_only_76200() -> None:
    bundle = load_target_client_data("demo").bundle
    offers = _classic_one_tooth_offers(bundle)
    result = _commerce_result(
        bundle,
        offers,
        selected_brand_id="implantium",
    )
    assert result.presentation_mode == "exact_offer"
    assert result.selected_exact_offer is not None
    assert result.selected_exact_offer.offer_id == "classic.one_tooth.implantium"
    assert result.authoritative_amounts == frozenset({76200})
    assert result.widget_offer_payload is not None
    assert result.widget_offer_payload["amount"] == 76200


def test_explicit_impro_returns_only_85200() -> None:
    bundle = load_target_client_data("demo").bundle
    offers = _classic_one_tooth_offers(bundle)
    result = _commerce_result(
        bundle,
        offers,
        selected_brand_id="impro",
    )
    assert result.presentation_mode == "exact_offer"
    assert result.selected_exact_offer is not None
    assert result.selected_exact_offer.offer_id == "classic.one_tooth.impro"
    assert result.authoritative_amounts == frozenset({85200})


def test_governed_offer_ref_is_authoritative() -> None:
    bundle = load_target_client_data("demo").bundle
    offers = tuple(
        offer
        for offer in bundle.offers
        if offer.offer_id == "classic.one_tooth.nobel"
    )
    result = _commerce_result(bundle, offers, selected_brand_id="nobel_biocare")
    assert result.presentation_mode == "exact_offer"
    assert result.selected_exact_offer is not None
    assert result.selected_exact_offer.offer_id == "classic.one_tooth.nobel"
    assert result.authoritative_amounts == frozenset({101200})


def test_wrong_flash_price_removed_narrative_marketing_cta_preserved() -> None:
    bundle = load_target_client_data("demo").bundle
    offers = _classic_one_tooth_offers(bundle)
    marketing_fact = SimpleNamespace(
        id="installment_12",
        kind="payment",
        text_fact="Доступна рассрочка на имплантацию и протезирование до 12 месяцев.",
        render_mode="strict",
    )
    bound = _fake_bound_package(
        offers,
        marketing_refs=("fact:installment_12",),
        commercial_facts=(marketing_fact,),
        max_options=3,
        service_id="classic",
    )
    result = build_authoritative_commerce_result(
        bound_package=bound,
        resolution=_resolution(),
        bundle=bundle,
        strategy_context=_strategy_context(),
    )
    supplemented = supplement_sales_fast_patient_text_with_marketing(
        patient_text=(
            "Классическая имплантация одного зуба под ключ стоит 99 999 ₽. "
            "Мы используем современные материалы. Запишитесь на консультацию."
        ),
        bound_package=bound,
    )
    final = apply_authoritative_commerce_to_patient_text(supplemented, result)
    assert "99 999" not in final and "99999" not in final.replace(" ", "")
    assert "современные материалы" in final
    assert "консультац" in final.lower()
    assert marketing_fact.text_fact in final
    assert "от 76" in final and "200" in final


def test_multiclient_different_prices_featured_and_modes() -> None:
    bundle_a = load_target_client_data("demo").bundle
    offers_a = _classic_one_tooth_offers(bundle_a)
    result_a = _commerce_result(bundle_a, offers_a)

    offers_b = tuple(
        offer.model_copy(
            update={
                "price": offer.price.model_copy(
                    update={"amount": int(offer.price.amount or 0) + 10000}
                )
            }
        )
        for offer in offers_a
    )
    bundle_b = bundle_a.model_copy(
        update={
            "strategy": bundle_a.strategy.model_copy(
                update={
                    "rules": [
                        rule.model_copy(
                            update={
                                "generic_price_policy": TargetGenericPricePolicy(
                                    mode="featured_single",
                                    featured_offer_id="classic.one_tooth.implantium",
                                )
                            }
                        )
                        if rule.id == "one_tooth_restore"
                        else rule
                        for rule in bundle_a.strategy.rules
                    ]
                }
            )
        }
    )
    result_b = resolve_authoritative_commerce(
        offers_b,
        bundle=bundle_b,
        strategy_context=_strategy_context(),
        service_id="classic",
        explicit_offer_id=None,
        max_options=3,
        needs_consultation_quote=False,
        consultation_text=None,
    )
    assert result_a.presentation_mode == "overview"
    assert result_b.presentation_mode == "featured_single"
    assert result_a.entry_price_amount == 76200
    assert result_b.entry_price_amount == 86200
    assert result_a.featured_offer_id == "classic.one_tooth.impro"
    assert result_b.featured_offer_id == "classic.one_tooth.implantium"
    assert result_b.selected_exact_offer is not None
    assert result_b.selected_exact_offer.offer_id == "classic.one_tooth.implantium"


def test_invalid_configured_offer_id_fails_bundle_validation() -> None:
    from contracts.response_schema import ResponseSchemaBundle

    bundle = load_target_client_data("demo").bundle
    broken = bundle.model_copy(
        update={
            "strategy": bundle.strategy.model_copy(
                update={
                    "rules": [
                        rule.model_copy(
                            update={
                                "generic_price_policy": TargetGenericPricePolicy(
                                    mode="featured_single",
                                    featured_offer_id="classic.one_tooth.missing",
                                )
                            }
                        )
                        if rule.id == "one_tooth_restore"
                        else rule
                        for rule in bundle.strategy.rules
                    ]
                }
            )
        }
    )
    with pytest.raises(ValueError, match="bundle_strategy_generic_price_offer_missing"):
        ResponseSchemaBundle.model_validate(broken.model_dump())


def test_multiple_offers_without_policy_fail_closed_to_overview() -> None:
    bundle = load_target_client_data("demo").bundle
    bundle = bundle.model_copy(
        update={
            "strategy": bundle.strategy.model_copy(
                update={
                    "default_generic_price_policy": None,
                    "rules": [
                        rule.model_copy(update={"generic_price_policy": None})
                        for rule in bundle.strategy.rules
                    ],
                }
            )
        }
    )
    offers = _classic_one_tooth_offers(bundle)
    result = resolve_authoritative_commerce(
        offers,
        bundle=bundle,
        strategy_context=_strategy_context(),
        service_id="classic",
        explicit_offer_id=None,
        max_options=3,
        needs_consultation_quote=False,
        consultation_text=None,
    )
    assert result.presentation_mode == "overview"
    assert result.selected_exact_offer is None
    assert len(result.ordered_offers) == 3


def test_both_jaws_strips_currency_and_keeps_consultation() -> None:
    result = AuthoritativeCommerceResult(
        service_id="all_on_4",
        presentation_mode="none",
        entry_price_amount=None,
        entry_price_text=None,
        ordered_offers=(),
        featured_offer_id=None,
        selected_exact_offer=None,
        needs_consultation_quote=True,
        authoritative_amounts=frozenset(),
        patient_price_block="Точную сумму на обе челюсти уточним на консультации.",
        widget_offer_payload=None,
    )
    text = apply_authoritative_commerce_to_patient_text(
        "Стоимость от 318 000 до 428 000 ₽ за одну челюсть. Итоговая сумма будет рассчитываться.",
        result,
    )
    assert "318 000" not in text
    assert "636000" not in text.replace(" ", "")
    assert "консультац" in text.lower()


def _fake_bound_package(
    offers: tuple,
    *,
    marketing_refs: tuple[str, ...] = (),
    commercial_facts: tuple = (),
    selected_brand_id: str | None = None,
    max_options: int = 3,
    service_id: str | None = "classic",
) -> object:
    marketing_selection = SimpleNamespace(selected_refs=marketing_refs)
    materials = SimpleNamespace(
        offers=offers,
        consultation_close=None,
        selected_brand_id=selected_brand_id,
        commercial_facts=commercial_facts,
        marketing_selection=marketing_selection,
        max_options=max_options,
        service_id=service_id,
    )
    package = SimpleNamespace(materials=materials)
    return SimpleNamespace(package=package)
