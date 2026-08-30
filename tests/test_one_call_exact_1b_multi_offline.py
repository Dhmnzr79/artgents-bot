"""CP-EXACT-1B-MULTI-V1 offline wiring tests."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date

import pytest

from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.precomposer_selected_offer import (
    PrecomposerSelectedOfferContractError,
    PrecomposerSelectedOfferResult,
)
from contracts.response_schema import TargetOffer
from core.one_call_multi_offer_price_block import build_canonical_multi_offer_price_block
from core.one_call_prefix_input_fingerprint import compute_prefix_input_fingerprint
from core.one_call_price_text import resolve_price_text_for_turn
from core.one_call_prompt_contract import (
    ONE_CALL_PROMPT_CONTRACT_VERSION,
    ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS,
)
from core.one_call_selected_exact_offer_block import (
    SELECTED_EXACT_OFFER_HEADER,
    build_selected_exact_offer_block,
)
from core.resolve_precomposer_selected_offer import (
    order_precomposer_offers_neutral,
    resolve_precomposer_selected_offer,
    resolve_precomposer_selected_offer_for_turn,
)
from core.sales_fast_widget_runtime import run_sales_fast_widget_turn
from core.sales_one_plus_protocol import build_sales_one_plus_dynamic_suffix
from core.target_client_data import load_target_client_data
from core.target_runtime_client_context import load_target_runtime_client_context
from core.target_runtime_session import read_target_runtime_session
from session import bind_session_client, mem_reset
import app as app_module
import config
from tests.test_one_call_exact_1b_single_offline import (
    _Backend,
    _DEMO_BUNDLE,
    _DEMO_CATALOG,
    _DEMO_COMMERCIAL_CATALOG,
    _DEMO_CONTEXT,
    _DEMO_EXACT_CATALOG,
    _DEMO_REF_CATALOG,
    _PACK_IDENTITY,
    _count_amount_token,
    _enable_sales_fast,
    _fresh_empty_session,
    _governed_resolution,
    _normalize_visible_text,
    _reset_demo_session,
    resolve_exact_sales_resolution_for_test,
)
from tests.test_sales_one_plus_turn import _context, answer_envelope

_ALL_ON_4_PACKAGE_SCOPE = "за одну челюсть; КТ и костная пластика по показаниям — отдельно"
_FREE_IMPLANT_CONSULT_SNIPPET = "бесплатная консультация по имплантации"
_ALL_ON_4_AMOUNTS = ("318000", "368000", "428000")
_ALL_ON_4_BRANDS = ("Implantium", "Impro", "Nobel Biocare")
_ALL_ON_6_AMOUNTS = ("398000", "458000", "528000")
_ALL_ON_6_PACKAGE_SCOPE = _ALL_ON_4_PACKAGE_SCOPE
_REMOVABLE_AMOUNTS = ("45000", "65000")
_REMOVABLE_LABELS = ("Частичный съёмный протез", "Полный съёмный протез")
_REMOVABLE_PACKAGE_SCOPE = "за одну челюсть; имплантация — отдельно"
_LEGACY_RECOMMENDED_MARKER = "рекомендуемый"


def _all_on_4_multi_selection() -> PrecomposerSelectedOfferResult:
    return resolve_precomposer_selected_offer(
        bundle=_DEMO_BUNDLE,
        doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
        resolution=_governed_resolution("all_on_4"),
    )


def _all_on_6_multi_selection() -> PrecomposerSelectedOfferResult:
    return resolve_precomposer_selected_offer(
        bundle=_DEMO_BUNDLE,
        doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
        resolution=_governed_resolution("all_on_6"),
    )


def _removable_multi_selection() -> PrecomposerSelectedOfferResult:
    return resolve_precomposer_selected_offer(
        bundle=_DEMO_BUNDLE,
        doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
        resolution=_governed_resolution("removable_dentures"),
    )


def _patch_demo_bundle(monkeypatch: pytest.MonkeyPatch, bundle) -> None:
    ctx = replace(load_target_runtime_client_context("demo"), bundle=bundle)

    def _loader(_client_id: str):
        return ctx

    monkeypatch.setattr(
        "core.sales_fast_widget_runtime.load_target_runtime_client_context",
        _loader,
    )
    monkeypatch.setattr(
        "core.target_runtime_client_context.load_target_runtime_client_context",
        _loader,
    )


def _patch_post_composer_audit_failure(
    monkeypatch: pytest.MonkeyPatch,
    exc: Exception,
) -> None:
    def _raising(*_args: object, **_kwargs: object) -> object:
        raise exc

    monkeypatch.setattr(
        "core.one_call_presentation_pass.materialize_target_composer_request",
        _raising,
    )


def _broken_all_on_4_malformed_one():
    broken = _DEMO_BUNDLE.model_copy(deep=True)
    offers = list(broken.offers)
    for index, offer in enumerate(offers):
        if offer.offer_id == "all_on_4.jaw.impro":
            offers[index] = offer.model_copy(
                update={"package": offer.package.model_copy(update={"label": ""})}
            )
    broken.offers = tuple(offers)
    return broken


def _broken_all_on_4_one_fixed_one_from():
    from contracts.response_schema import TargetFromPrice

    broken = _DEMO_BUNDLE.model_copy(deep=True)
    offers: list[TargetOffer] = []
    for offer in broken.offers:
        if offer.service_id != "all_on_4":
            offers.append(offer)
            continue
        if offer.offer_id != "all_on_4.jaw.implantium":
            offers.append(offer.model_copy(update={"active": False}))
            continue
        offers.append(offer)
        offers.append(
            offer.model_copy(
                update={
                    "offer_id": "all_on_4.jaw.from_budget",
                    "brand_id": None,
                    "price": TargetFromPrice(
                        mode="from",
                        min_amount=250000,
                        currency="RUB",
                        billing_unit="jaw",  # type: ignore[arg-type]
                    ),
                }
            )
        )
    broken.offers = tuple(offers)
    return broken


def _broken_all_on_4_too_many():
    broken = _DEMO_BUNDLE.model_copy(deep=True)
    all_on_4_offers = [
        offer for offer in broken.offers if offer.service_id == "all_on_4"
    ]
    extra = all_on_4_offers[0].model_copy(
        update={
            "offer_id": "all_on_4.jaw.extra",
            "price": all_on_4_offers[0].price.model_copy(update={"amount": 999000}),
        }
    )
    broken.offers = tuple(
        offer for offer in broken.offers if offer.service_id != "all_on_4"
    ) + tuple(all_on_4_offers) + (extra,)
    return broken


def _broken_all_on_4_two_unlabeled_offers():
    broken = _DEMO_BUNDLE.model_copy(deep=True)
    stubs = (
        _offer_stub(offer_id="custom.unlabeled.a", brand_id=None, amount=111000),
        _offer_stub(offer_id="custom.unlabeled.b", brand_id=None, amount=222000),
    )
    broken.offers = tuple(
        offer for offer in broken.offers if offer.service_id != "all_on_4"
    ) + stubs
    return broken


def _offer_stub(
    *,
    offer_id: str,
    service_id: str = "all_on_4",
    brand_id: str | None = None,
    amount: int = 100000,
    billing_unit: str = "jaw",
    package_label: str = "за одну челюсть",
    active: bool = True,
    mode: str = "fixed",
) -> TargetOffer:
    from contracts.response_schema import TargetFixedPrice, TargetPricePackage

    if mode == "from":
        from contracts.response_schema import TargetFromPrice

        price = TargetFromPrice(
            mode="from",
            min_amount=amount,
            currency="RUB",
            billing_unit=billing_unit,  # type: ignore[arg-type]
        )
    else:
        price = TargetFixedPrice(
            mode="fixed",
            amount=amount,
            currency="RUB",
            billing_unit=billing_unit,  # type: ignore[arg-type]
        )
    return TargetOffer(
        offer_id=offer_id,
        service_id=service_id,
        active=active,
        price=price,
        package=TargetPricePackage(label=package_label, includes=[]),
        brand_id=brand_id,
    )


class TestPrecomposerContract:
    def test_none_invariants(self) -> None:
        result = PrecomposerSelectedOfferResult(availability="none")
        assert result.offer is None
        assert result.offers == ()

    def test_selected_invariants(self) -> None:
        offer = _offer_stub(offer_id="svc.a", brand_id="implantium")
        result = PrecomposerSelectedOfferResult(
            availability="selected",
            offer=offer,
            service_id="all_on_4",
        )
        assert result.offer is offer
        assert result.offers == ()

    def test_multiple_invariants(self) -> None:
        offers = (
            _offer_stub(offer_id="svc.a", brand_id="implantium", amount=318000),
            _offer_stub(offer_id="svc.b", brand_id="impro", amount=368000),
        )
        result = PrecomposerSelectedOfferResult(
            availability="multiple",
            offers=offers,
            service_id="all_on_4",
        )
        assert result.offer is None
        assert len(result.offers) == 2

    def test_multiple_requires_two_to_three_offers(self) -> None:
        with pytest.raises(PrecomposerSelectedOfferContractError):
            PrecomposerSelectedOfferResult(
                availability="multiple",
                offers=(_offer_stub(offer_id="only.one"),),
                service_id="all_on_4",
            )
        with pytest.raises(PrecomposerSelectedOfferContractError):
            PrecomposerSelectedOfferResult(
                availability="multiple",
                offers=tuple(
                    _offer_stub(offer_id=f"svc.{index}", amount=100000 + index)
                    for index in range(4)
                ),
                service_id="all_on_4",
            )

    def test_duplicate_ids_forbidden(self) -> None:
        offer = _offer_stub(offer_id="dup", brand_id="implantium")
        with pytest.raises(PrecomposerSelectedOfferContractError):
            PrecomposerSelectedOfferResult(
                availability="multiple",
                offers=(offer, offer.model_copy(deep=True)),
                service_id="all_on_4",
            )

    def test_mixed_services_forbidden(self) -> None:
        with pytest.raises(PrecomposerSelectedOfferContractError):
            PrecomposerSelectedOfferResult(
                availability="multiple",
                offers=(
                    _offer_stub(offer_id="a", service_id="all_on_4"),
                    _offer_stub(offer_id="b", service_id="all_on_6"),
                ),
                service_id="all_on_4",
            )

    def test_non_fixed_or_malformed_offer_forbidden(self) -> None:
        with pytest.raises(PrecomposerSelectedOfferContractError):
            PrecomposerSelectedOfferResult(
                availability="multiple",
                offers=(
                    _offer_stub(offer_id="a", mode="from"),
                    _offer_stub(offer_id="b"),
                ),
                service_id="all_on_4",
            )

    def test_invalid_state_fail_fast(self) -> None:
        with pytest.raises(PrecomposerSelectedOfferContractError):
            PrecomposerSelectedOfferResult(
                availability="selected",
                offers=(_offer_stub(offer_id="a"),),
                service_id="all_on_4",
            )


class TestDemoResolver:
    def test_all_on_4_without_brand_is_multiple(self) -> None:
        selection = _all_on_4_multi_selection()
        assert selection.availability == "multiple"
        assert len(selection.offers) == 3

    def test_all_on_4_three_brands_and_amounts(self) -> None:
        selection = _all_on_4_multi_selection()
        assert [offer.brand_id for offer in selection.offers] == [
            "implantium",
            "impro",
            "nobel_biocare",
        ]
        assert [int(offer.price.amount or 0) for offer in selection.offers] == [
            318000,
            368000,
            428000,
        ]

    def test_all_on_4_order_follows_brand_catalog_not_strategy(self) -> None:
        selection = _all_on_4_multi_selection()
        catalog_order = list(_DEMO_BUNDLE.brands.brands.keys())
        brand_positions = [catalog_order.index(offer.brand_id) for offer in selection.offers]  # type: ignore[arg-type]
        assert brand_positions == sorted(brand_positions)

    def test_all_on_4_implantium_stays_selected_single(self) -> None:
        from core.sales_fast_service_identity import resolve_catalog_service_identity

        message = "Сколько стоит All-on-4 Implantium?"
        identity = resolve_catalog_service_identity(message, _DEMO_BUNDLE)
        resolution = resolve_exact_sales_resolution_for_test(message, identity)
        selection = resolve_precomposer_selected_offer_for_turn(
            bundle=_DEMO_BUNDLE,
            doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
            resolution=resolution,
            user_message=message,
            service_identity=identity,
            session_state=_fresh_empty_session(),
        )
        assert selection.availability == "selected"
        assert selection.offer is not None
        assert selection.offer.offer_id == "all_on_4.jaw.implantium"

    def test_nobel_or_impro_filtered_multiple(self) -> None:
        message = "Сколько стоит All-on-4 Nobel или Impro?"
        from core.sales_fast_service_identity import resolve_catalog_service_identity

        identity = resolve_catalog_service_identity(message, _DEMO_BUNDLE)
        resolution = resolve_exact_sales_resolution_for_test(message, identity)
        selection = resolve_precomposer_selected_offer_for_turn(
            bundle=_DEMO_BUNDLE,
            doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
            resolution=resolution,
            user_message=message,
            service_identity=identity,
            session_state=_fresh_empty_session(),
        )
        assert selection.availability == "multiple"
        assert [offer.brand_id for offer in selection.offers] == ["impro", "nobel_biocare"]

    def test_two_brands_one_active_becomes_selected_single(self) -> None:
        broken = _DEMO_BUNDLE.model_copy(deep=True)
        offers = list(broken.offers)
        for index, offer in enumerate(offers):
            if offer.offer_id == "all_on_4.jaw.impro":
                offers[index] = offer.model_copy(update={"active": False})
        broken.offers = tuple(offers)
        selection = resolve_precomposer_selected_offer(
            bundle=broken,
            doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
            resolution=_governed_resolution("all_on_4"),
            selected_brand_ids=("impro", "nobel_biocare"),
            brand_ids_authoritative=True,
        )
        assert selection.availability == "selected"
        assert selection.offer is not None
        assert selection.offer.brand_id == "nobel_biocare"

    def test_ct_plus_implantium_is_none(self) -> None:
        message = "Сколько стоит КТ Implantium?"
        from core.sales_fast_service_identity import resolve_catalog_service_identity

        identity = resolve_catalog_service_identity(message, _DEMO_BUNDLE)
        resolution = resolve_exact_sales_resolution_for_test(message, identity)
        selection = resolve_precomposer_selected_offer_for_turn(
            bundle=_DEMO_BUNDLE,
            doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
            resolution=resolution,
            user_message=message,
            service_identity=identity,
            session_state=_fresh_empty_session(),
        )
        assert selection.availability == "none"

    def test_unknown_straumann_shows_known_three_offers(self) -> None:
        message = "Сколько стоит All-on-4 Straumann?"
        from core.sales_fast_service_identity import resolve_catalog_service_identity

        identity = resolve_catalog_service_identity(message, _DEMO_BUNDLE)
        resolution = resolve_exact_sales_resolution_for_test(message, identity)
        selection = resolve_precomposer_selected_offer_for_turn(
            bundle=_DEMO_BUNDLE,
            doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
            resolution=resolution,
            user_message=message,
            service_identity=identity,
            session_state=_fresh_empty_session(),
        )
        assert selection.availability == "multiple"
        assert "straumann" not in {offer.brand_id for offer in selection.offers}

    def test_broad_implantation_does_not_activate_multi(self) -> None:
        message = "Сколько стоит имплантация?"
        from core.sales_fast_service_identity import resolve_catalog_service_identity

        identity = resolve_catalog_service_identity(message, _DEMO_BUNDLE)
        resolution = resolve_exact_sales_resolution_for_test(message, identity)
        selection = resolve_precomposer_selected_offer_for_turn(
            bundle=_DEMO_BUNDLE,
            doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
            resolution=resolution,
            user_message=message,
            service_identity=identity,
            session_state=_fresh_empty_session(),
        )
        assert selection.availability == "none"

    def test_session_followup_uses_fresh_demo_session(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        _enable_sales_fast(monkeypatch)
        sid = "cp-exact-1b-multi-session"
        _reset_demo_session(sid)
        first = _Backend(
            answer_envelope(
                "All-on-4 — полное восстановление.",
                commercial_intent="price",
                service_id="all_on_4",
                service_reference_status="resolved",
                requested_service_id="all_on_4",
                price_text=None,
            )
        )
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-session-1"}
            run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message="Сколько стоит All-on-4?",
                backend=first,
            )
        message = "А Nobel или Impro?"
        from core.sales_fast_service_identity import resolve_catalog_service_identity

        identity = resolve_catalog_service_identity(message, _DEMO_BUNDLE)
        resolution = resolve_exact_sales_resolution_for_test(message, identity)
        selection = resolve_precomposer_selected_offer_for_turn(
            bundle=_DEMO_BUNDLE,
            doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
            resolution=resolution,
            user_message=message,
            service_identity=identity,
            session_state=read_target_runtime_session(sid),
        )
        assert selection.availability == "multiple"
        assert len(selection.offers) == 2

    def test_new_topic_cancels_old_service(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        _enable_sales_fast(monkeypatch)
        sid = "cp-exact-1b-multi-topic"
        _reset_demo_session(sid)
        first = _Backend(
            answer_envelope(
                "All-on-4 — полное восстановление.",
                commercial_intent="price",
                service_id="all_on_4",
                service_reference_status="resolved",
                requested_service_id="all_on_4",
                price_text=None,
            )
        )
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-topic-1"}
            run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message="Сколько стоит All-on-4?",
                backend=first,
            )
        message = "Сколько стоит КТ?"
        from core.sales_fast_service_identity import resolve_catalog_service_identity

        identity = resolve_catalog_service_identity(message, _DEMO_BUNDLE)
        resolution = resolve_exact_sales_resolution_for_test(message, identity)
        selection = resolve_precomposer_selected_offer_for_turn(
            bundle=_DEMO_BUNDLE,
            doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
            resolution=resolution,
            user_message=message,
            service_identity=identity,
            session_state=read_target_runtime_session(sid),
        )
        assert selection.availability == "selected"
        assert selection.offer is not None
        assert selection.offer.service_id == "tomography"


class TestFormatter:
    def test_heading_from_canonical_service_label(self) -> None:
        block = build_canonical_multi_offer_price_block(
            bundle=_DEMO_BUNDLE,
            selection=_all_on_4_multi_selection(),
        )
        assert block.block is not None
        assert block.block.startswith("Стоимость All-on-4:")

    def test_three_lines_with_real_amounts(self) -> None:
        block = build_canonical_multi_offer_price_block(
            bundle=_DEMO_BUNDLE,
            selection=_all_on_4_multi_selection(),
        )
        assert block.block is not None
        for brand, amount in zip(_ALL_ON_4_BRANDS, _ALL_ON_4_AMOUNTS, strict=True):
            assert brand in block.block
            assert amount[:3] in _normalize_visible_text(block.block)

    def test_each_amount_once(self) -> None:
        block = build_canonical_multi_offer_price_block(
            bundle=_DEMO_BUNDLE,
            selection=_all_on_4_multi_selection(),
        )
        assert block.block is not None
        for amount in _ALL_ON_4_AMOUNTS:
            assert _count_amount_token(block.block, amount) == 1

    def test_no_recommended_suffix(self) -> None:
        block = build_canonical_multi_offer_price_block(
            bundle=_DEMO_BUNDLE,
            selection=_all_on_4_multi_selection(),
        )
        assert block.block is not None
        assert "рекомендуемый" not in block.block.casefold()

    def test_shared_package_label_once(self) -> None:
        block = build_canonical_multi_offer_price_block(
            bundle=_DEMO_BUNDLE,
            selection=_all_on_4_multi_selection(),
        )
        assert block.block is not None
        assert block.block.count(_ALL_ON_4_PACKAGE_SCOPE) == 1
        assert f"Условия для всех вариантов: {_ALL_ON_4_PACKAGE_SCOPE}" in block.block

    def test_shared_footer_not_repeated_in_each_line(self) -> None:
        block = build_canonical_multi_offer_price_block(
            bundle=_DEMO_BUNDLE,
            selection=_all_on_4_multi_selection(),
        )
        assert block.block is not None
        for line in block.block.splitlines():
            if line.startswith("- "):
                assert _ALL_ON_4_PACKAGE_SCOPE not in line

    def test_different_package_labels_per_line(self) -> None:
        offers = (
            _offer_stub(offer_id="a", brand_id="implantium", package_label="пакет A"),
            _offer_stub(offer_id="b", brand_id="impro", package_label="пакет B"),
        )
        selection = PrecomposerSelectedOfferResult(
            availability="multiple",
            offers=offers,
            service_id="all_on_4",
        )
        block = build_canonical_multi_offer_price_block(
            bundle=_DEMO_BUNDLE,
            selection=selection,
        )
        assert block.block is not None
        assert "пакет A" in block.block
        assert "пакет B" in block.block
        assert "Условия для всех вариантов" not in block.block

    def test_internal_ids_not_visible(self) -> None:
        block = build_canonical_multi_offer_price_block(
            bundle=_DEMO_BUNDLE,
            selection=_all_on_4_multi_selection(),
        )
        assert block.block is not None
        assert "all_on_4.jaw." not in block.block

    def test_malformed_offer_disables_whole_block(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def broken_amount(offer):
            return ""

        monkeypatch.setattr(
            "core.one_call_multi_offer_price_block._offer_amount_only",
            broken_amount,
        )
        block = build_canonical_multi_offer_price_block(
            bundle=_DEMO_BUNDLE,
            selection=_all_on_4_multi_selection(),
        )
        assert block.block is None
        assert block.diagnostic == "multi_offer_malformed"

    def test_malformed_contract_rejected(self) -> None:
        offers = list(_all_on_4_multi_selection().offers)
        broken = offers[0].model_copy(
            update={"package": offers[0].package.model_copy(update={"label": ""})}
        )
        with pytest.raises(PrecomposerSelectedOfferContractError):
            PrecomposerSelectedOfferResult(
                availability="multiple",
                offers=(broken, offers[1], offers[2]),
                service_id="all_on_4",
            )

    def test_more_than_three_offers_no_multi_selection(self) -> None:
        selection = resolve_precomposer_selected_offer(
            bundle=_DEMO_BUNDLE,
            doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
            resolution=_governed_resolution("all_on_4"),
        )
        assert selection.availability == "multiple"
        assert len(selection.offers) == 3

    def test_neutral_order_not_by_amount(self) -> None:
        reversed_offers = tuple(reversed(_all_on_4_multi_selection().offers))
        selection = PrecomposerSelectedOfferResult(
            availability="multiple",
            offers=reversed_offers,
            service_id="all_on_4",
        )
        block = build_canonical_multi_offer_price_block(
            bundle=_DEMO_BUNDLE,
            selection=selection,
        )
        assert block.block is not None
        assert block.block.index("Implantium") < block.block.index("Impro") < block.block.index("Nobel")


class TestPromptEnvelope:
    def test_dynamic_block_contains_multiple_offers(self) -> None:
        block = build_selected_exact_offer_block(
            bundle=_DEMO_BUNDLE,
            selection=_all_on_4_multi_selection(),
        )
        assert '"availability": "multiple"' in block
        assert '"price_text_allowed": false' in block
        assert '"offers"' in block
        assert "318000" in block

    def test_stable_prefix_fingerprint_across_multi_turns(self) -> None:
        corpus = _context()
        active = _DEMO_CATALOG
        ref = _DEMO_REF_CATALOG
        exact = _DEMO_EXACT_CATALOG
        fp_a = compute_prefix_input_fingerprint(_PACK_IDENTITY, corpus, active, ref, exact)
        fp_b = compute_prefix_input_fingerprint(_PACK_IDENTITY, corpus, active, ref, exact)
        assert fp_a == fp_b
        suffix_one = build_sales_one_plus_dynamic_suffix(
            exact_sales_resolution=_governed_resolution("all_on_4"),
            current_strict_facts=(),
            sales_context={},
            user_message="Сколько стоит All-on-4?",
            exact_commercial_catalog=exact,
            precomposer_selected_offer=_all_on_4_multi_selection(),
            response_schema_bundle=_DEMO_BUNDLE,
        )
        suffix_two = build_sales_one_plus_dynamic_suffix(
            exact_sales_resolution=_governed_resolution("all_on_4"),
            current_strict_facts=(),
            sales_context={},
            user_message="Сколько стоит All-on-4 Nobel или Impro?",
            exact_commercial_catalog=exact,
            precomposer_selected_offer=resolve_precomposer_selected_offer(
                bundle=_DEMO_BUNDLE,
                doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
                resolution=_governed_resolution("all_on_4"),
                selected_brand_ids=("nobel_biocare", "impro"),
                brand_ids_authoritative=True,
            ),
            response_schema_bundle=_DEMO_BUNDLE,
        )
        assert SELECTED_EXACT_OFFER_HEADER in suffix_one
        assert SELECTED_EXACT_OFFER_HEADER in suffix_two
        assert suffix_one != suffix_two

    def test_prompt_contract_v9_documents_multiple(self) -> None:
        assert ONE_CALL_PROMPT_CONTRACT_VERSION == 9
        assert "availability=multiple" in ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS
        assert "Do not return used_offer_id" in ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS

    def test_resolve_price_text_multiple_owner(self) -> None:
        resolved = resolve_price_text_for_turn(
            price_text=None,
            commercial_intent="price",
            selection=_all_on_4_multi_selection(),
            bundle=_DEMO_BUNDLE,
        )
        assert resolved.owner == "canonical_multi"
        assert resolved.line.strip()
        assert resolved.selected_offer_id is None
        assert len(resolved.multi_offer_ids) == 3

    def test_non_null_multi_price_text_ignored_with_diagnostic(self) -> None:
        resolved = resolve_price_text_for_turn(
            price_text="Стоимость — 999 ₽",
            commercial_intent="price",
            selection=_all_on_4_multi_selection(),
            bundle=_DEMO_BUNDLE,
        )
        assert resolved.owner == "canonical_multi"
        assert resolved.diagnostic == "unexpected_multi_price_text"
        assert "318" in resolved.line

    def test_top_level_envelope_schema_not_extended(self) -> None:
        from core.one_call_envelope_protocol import production_envelope_template

        keys = set(production_envelope_template().keys())
        assert "used_offer_id" not in keys
        assert "selected_offer_ids" not in keys
        assert "price_items" not in keys


@pytest.fixture
def flask_app():
    return app_module.app


class TestWidgetPresentation:
    def test_all_on_4_price_turn_full_order(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        _enable_sales_fast(monkeypatch)
        monkeypatch.setattr(
            "core.target_runtime_client_context.runtime_today",
            lambda: date(2026, 8, 10),
        )
        user_message = "Сколько стоит All-on-4?"
        patient = "All-on-4 восстанавливает всю челюсть на четырёх опорах."
        backend = _Backend(
            answer_envelope(
                patient,
                commercial_intent="price",
                scenario="cost",
                service_id="all_on_4",
                service_reference_status="resolved",
                requested_service_id="all_on_4",
                price_text=None,
            )
        )
        sid = "cp-exact-1b-multi-full"
        _reset_demo_session(sid)
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": user_message, "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-multi-full"}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message=user_message,
                backend=backend,
            )
            answer = str(outcome.widget.payload.get("answer") or "")
            flags = request.ctx.get("turn_timing", {}).get("flags", {})
        assert outcome.widget.kind == "materialized"
        assert flags.get("precomposer_offer_availability") == "multiple"
        assert flags.get("multi_price_owner") == "canonical_multi"
        for amount in _ALL_ON_4_AMOUNTS:
            assert _count_amount_token(answer, amount) == 1
        assert patient in answer
        assert _ALL_ON_4_PACKAGE_SCOPE in answer
        assert _FREE_IMPLANT_CONSULT_SNIPPET in answer.casefold()
        list_idx = answer.casefold().index("также мы предлагаем")
        price_idx = answer.index("Implantium")
        patient_idx = answer.index(patient)
        promo_idx = answer.casefold().index(_FREE_IMPLANT_CONSULT_SNIPPET)
        assert price_idx < patient_idx < promo_idx < list_idx
        assert "рекомендуемый" not in answer.casefold()
        assert outcome.widget.payload.get("offer") is None

    def test_non_price_all_on_4_has_no_list(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        _enable_sales_fast(monkeypatch)
        backend = _Backend(
            answer_envelope(
                "All-on-4 — протокол полного восстановления челюсти.",
                commercial_intent="none",
                service_id="all_on_4",
                service_reference_status="resolved",
                requested_service_id="all_on_4",
            )
        )
        sid = "cp-exact-1b-multi-nonprice"
        _reset_demo_session(sid)
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": "Что такое All-on-4?", "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-nonprice"}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message="Что такое All-on-4?",
                backend=backend,
            )
            answer = str(outcome.widget.payload.get("answer") or "")
        for amount in _ALL_ON_4_AMOUNTS:
            assert amount not in _normalize_visible_text(answer)

    def test_two_brand_followup_only_two_lines(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        _enable_sales_fast(monkeypatch)
        sid = "cp-exact-1b-multi-two-brand"
        _reset_demo_session(sid)
        first = _Backend(
            answer_envelope(
                "All-on-4 — полное восстановление.",
                commercial_intent="price",
                service_id="all_on_4",
                service_reference_status="resolved",
                requested_service_id="all_on_4",
                price_text=None,
            )
        )
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-two-brand-1"}
            run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message="Сколько стоит All-on-4?",
                backend=first,
            )
        second = _Backend(
            answer_envelope(
                "Nobel и Impro отличаются по системе имплантов.",
                commercial_intent="price",
                service_id="all_on_4",
                service_reference_status="resolved",
                requested_service_id="all_on_4",
                price_text=None,
            )
        )
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": "А Nobel или Impro?", "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-two-brand-2"}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message="А Nobel или Impro?",
                backend=second,
            )
            answer = str(outcome.widget.payload.get("answer") or "")
        assert _count_amount_token(answer, "318000") == 0
        assert _count_amount_token(answer, "368000") == 1
        assert _count_amount_token(answer, "428000") == 1


class TestJawScenarioResolver:
    def test_all_on_6_without_brand_is_multiple(self) -> None:
        selection = _all_on_6_multi_selection()
        assert selection.availability == "multiple"
        assert len(selection.offers) == 3

    def test_all_on_6_three_brands_and_amounts(self) -> None:
        selection = _all_on_6_multi_selection()
        assert [offer.brand_id for offer in selection.offers] == [
            "implantium",
            "impro",
            "nobel_biocare",
        ]
        assert [int(offer.price.amount or 0) for offer in selection.offers] == [
            398000,
            458000,
            528000,
        ]

    def test_removable_dentures_without_option_is_multiple(self) -> None:
        selection = _removable_multi_selection()
        assert selection.availability == "multiple"
        assert len(selection.offers) == 2
        assert [offer.option_id for offer in selection.offers] == ["partial", "full"]

    def test_removable_dentures_amounts(self) -> None:
        selection = _removable_multi_selection()
        assert [int(offer.price.amount or 0) for offer in selection.offers] == [45000, 65000]


class TestEligibleSetValidation:
    def test_malformed_offer_blocks_whole_set_not_partial(self) -> None:
        broken = _broken_all_on_4_malformed_one()
        selection = resolve_precomposer_selected_offer(
            bundle=broken,
            doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
            resolution=_governed_resolution("all_on_4"),
        )
        assert selection.availability == "none"
        assert selection.diagnostic == "multi_offer_malformed"

    def test_mixed_fixed_from_blocks_not_selected_single(self) -> None:
        broken = _broken_all_on_4_one_fixed_one_from()
        selection = resolve_precomposer_selected_offer(
            bundle=broken,
            doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
            resolution=_governed_resolution("all_on_4"),
        )
        assert selection.availability == "none"
        assert selection.diagnostic == "multi_offer_mixed_price_modes"

    def test_more_than_three_blocks_without_truncation(self) -> None:
        broken = _broken_all_on_4_too_many()
        selection = resolve_precomposer_selected_offer(
            bundle=broken,
            doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
            resolution=_governed_resolution("all_on_4"),
        )
        assert selection.availability == "none"
        assert selection.diagnostic == "multi_offer_too_many"
        assert selection.offers == ()

    def test_non_jaw_uniform_billing_returns_none_without_diagnostic(self) -> None:
        resolved = resolve_precomposer_selected_offer(
            bundle=_DEMO_BUNDLE,
            doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
            resolution=_governed_resolution("classic"),
        )
        assert resolved.availability == "none"
        assert resolved.diagnostic is None


class TestJawScenarioFormatter:
    def test_all_on_6_heading_and_amounts(self) -> None:
        block = build_canonical_multi_offer_price_block(
            bundle=_DEMO_BUNDLE,
            selection=_all_on_6_multi_selection(),
        )
        assert block.block is not None
        assert block.block.startswith("Стоимость")
        assert "all_on_6" not in block.block
        for amount in _ALL_ON_6_AMOUNTS:
            assert _count_amount_token(block.block, amount) == 1
        assert f"Условия для всех вариантов: {_ALL_ON_6_PACKAGE_SCOPE}" in block.block

    def test_removable_option_labels_not_ids(self) -> None:
        block = build_canonical_multi_offer_price_block(
            bundle=_DEMO_BUNDLE,
            selection=_removable_multi_selection(),
        )
        assert block.block is not None
        assert "removable_dentures" not in block.block
        assert "partial" not in block.block
        assert "full" not in block.block
        for label in _REMOVABLE_LABELS:
            assert label in block.block
        for amount in _REMOVABLE_AMOUNTS:
            assert _count_amount_token(block.block, amount) == 1
        assert f"Условия для всех вариантов: {_REMOVABLE_PACKAGE_SCOPE}" in block.block

    def test_no_label_offer_disables_whole_block(self) -> None:
        offers = (
            _offer_stub(offer_id="custom.unlabeled.a", brand_id=None, amount=111000),
            _offer_stub(offer_id="custom.unlabeled.b", brand_id=None, amount=222000),
        )
        selection = PrecomposerSelectedOfferResult(
            availability="multiple",
            offers=offers,
            service_id="all_on_4",
        )
        block = build_canonical_multi_offer_price_block(
            bundle=_DEMO_BUNDLE,
            selection=selection,
        )
        assert block.block is None
        assert block.diagnostic == "multi_offer_malformed"


class TestJawScenarioWidget:
    def test_all_on_6_price_turn(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        _enable_sales_fast(monkeypatch)
        monkeypatch.setattr(
            "core.target_runtime_client_context.runtime_today",
            lambda: date(2026, 8, 10),
        )
        patient = "All-on-6 восстанавливает челюсть на шести опорах."
        user_message = "Сколько стоит All-on-6?"
        backend = _Backend(
            answer_envelope(
                patient,
                commercial_intent="price",
                service_id="all_on_6",
                service_reference_status="resolved",
                requested_service_id="all_on_6",
                price_text=None,
            )
        )
        sid = "cp-exact-1b-multi-all-on-6"
        _reset_demo_session(sid)
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": user_message, "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-all-on-6"}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message=user_message,
                backend=backend,
            )
            answer = str(outcome.widget.payload.get("answer") or "")
            flags = request.ctx.get("turn_timing", {}).get("flags", {})
        assert outcome.widget.kind == "materialized"
        assert flags.get("precomposer_offer_availability") == "multiple"
        assert flags.get("multi_price_owner") == "canonical_multi"
        for amount in _ALL_ON_6_AMOUNTS:
            assert _count_amount_token(answer, amount) == 1
        assert patient in answer
        assert _ALL_ON_6_PACKAGE_SCOPE in answer
        assert _LEGACY_RECOMMENDED_MARKER not in answer.casefold()

    def test_all_on_6_non_price_has_no_list(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        _enable_sales_fast(monkeypatch)
        backend = _Backend(
            answer_envelope(
                "All-on-6 — протокол на шести имплантах.",
                commercial_intent="none",
                service_id="all_on_6",
                service_reference_status="resolved",
                requested_service_id="all_on_6",
            )
        )
        sid = "cp-exact-1b-multi-all-on-6-nonprice"
        _reset_demo_session(sid)
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": "Что такое All-on-6?", "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-all-on-6-nonprice"}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message="Что такое All-on-6?",
                backend=backend,
            )
            answer = str(outcome.widget.payload.get("answer") or "")
        for amount in _ALL_ON_6_AMOUNTS:
            assert amount not in _normalize_visible_text(answer)

    def test_removable_dentures_price_turn(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        _enable_sales_fast(monkeypatch)
        monkeypatch.setattr(
            "core.target_runtime_client_context.runtime_today",
            lambda: date(2026, 8, 10),
        )
        patient = "Съёмные протезы помогают восстановить зубной ряд."
        user_message = "Сколько стоит съёмное протезирование?"
        backend = _Backend(
            answer_envelope(
                patient,
                commercial_intent="price",
                service_id="removable_dentures",
                service_reference_status="resolved",
                requested_service_id="removable_dentures",
                price_text=None,
            )
        )
        sid = "cp-exact-1b-multi-removable"
        _reset_demo_session(sid)
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": user_message, "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-removable"}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message=user_message,
                backend=backend,
            )
            answer = str(outcome.widget.payload.get("answer") or "")
            flags = request.ctx.get("turn_timing", {}).get("flags", {})
        assert outcome.widget.kind == "materialized"
        assert flags.get("precomposer_offer_availability") == "multiple"
        for label in _REMOVABLE_LABELS:
            assert label in answer
        for amount in _REMOVABLE_AMOUNTS:
            assert _count_amount_token(answer, amount) == 1
        assert "removable_dentures" not in answer
        assert "partial" not in answer
        assert "full" not in answer
        assert patient in answer
        assert _REMOVABLE_PACKAGE_SCOPE in answer
        assert _LEGACY_RECOMMENDED_MARKER not in answer.casefold()

    def test_removable_dentures_non_price_has_no_list(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        _enable_sales_fast(monkeypatch)
        backend = _Backend(
            answer_envelope(
                "Съёмное протезирование подбирается по объёму дефекта.",
                commercial_intent="none",
                service_id="removable_dentures",
                service_reference_status="resolved",
                requested_service_id="removable_dentures",
            )
        )
        sid = "cp-exact-1b-multi-removable-nonprice"
        _reset_demo_session(sid)
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": "Что такое съёмное протезирование?", "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-removable-nonprice"}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message="Что такое съёмное протезирование?",
                backend=backend,
            )
            answer = str(outcome.widget.payload.get("answer") or "")
        for amount in _REMOVABLE_AMOUNTS:
            assert amount not in _normalize_visible_text(answer)


class TestUnsafeIntegrationWidget:
    def _assert_unsafe_price_turn(
        self,
        *,
        answer: str,
        patient: str,
        flags: dict,
        forbidden_amounts: tuple[str, ...],
        diagnostic: str,
    ) -> None:
        assert patient in answer
        assert flags.get("multi_attempted_but_unsafe") is True
        assert flags.get("precomposer_offer_diagnostic") == diagnostic
        assert flags.get("multi_price_owner") != "canonical_multi"
        for amount in forbidden_amounts:
            assert _count_amount_token(answer, amount) == 0
        assert _LEGACY_RECOMMENDED_MARKER not in answer.casefold()
        assert "all_on_4.jaw." not in answer

    def test_malformed_offer_among_three_blocks_multi_and_legacy(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        _enable_sales_fast(monkeypatch)
        _patch_demo_bundle(monkeypatch, _broken_all_on_4_malformed_one())
        patient = "All-on-4 — протокол полного восстановления."
        user_message = "Сколько стоит All-on-4?"
        backend = _Backend(
            answer_envelope(
                patient,
                commercial_intent="price",
                service_id="all_on_4",
                service_reference_status="resolved",
                requested_service_id="all_on_4",
                price_text=None,
            )
        )
        sid = "cp-exact-1b-unsafe-malformed"
        _reset_demo_session(sid)
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": user_message, "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-unsafe-malformed"}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message=user_message,
                backend=backend,
            )
            answer = str(outcome.widget.payload.get("answer") or "")
            flags = request.ctx.get("turn_timing", {}).get("flags", {})
        assert outcome.widget.kind == "materialized"
        payload = dict(outcome.widget.payload or {})
        assert payload.get("meta", {}).get("terminal_mode") not in {"admin", "clarify"}
        self._assert_unsafe_price_turn(
            answer=answer,
            patient=patient,
            flags=flags,
            forbidden_amounts=_ALL_ON_4_AMOUNTS,
            diagnostic="multi_offer_malformed",
        )

    def test_mixed_fixed_from_blocks_multi_and_legacy(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        _enable_sales_fast(monkeypatch)
        _patch_demo_bundle(monkeypatch, _broken_all_on_4_one_fixed_one_from())
        patient = "All-on-4 можно обсудить на консультации."
        user_message = "Сколько стоит All-on-4?"
        backend = _Backend(
            answer_envelope(
                patient,
                commercial_intent="price",
                service_id="all_on_4",
                service_reference_status="resolved",
                requested_service_id="all_on_4",
                price_text=None,
            )
        )
        sid = "cp-exact-1b-unsafe-mixed"
        _reset_demo_session(sid)
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": user_message, "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-unsafe-mixed"}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message=user_message,
                backend=backend,
            )
            answer = str(outcome.widget.payload.get("answer") or "")
            flags = request.ctx.get("turn_timing", {}).get("flags", {})
        assert outcome.widget.kind == "materialized"
        self._assert_unsafe_price_turn(
            answer=answer,
            patient=patient,
            flags=flags,
            forbidden_amounts=("318000",),
            diagnostic="multi_offer_mixed_price_modes",
        )

    def test_more_than_three_offers_blocks_presentation(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        _enable_sales_fast(monkeypatch)
        _patch_demo_bundle(monkeypatch, _broken_all_on_4_too_many())
        patient = "All-on-4 — популярный протокол."
        user_message = "Сколько стоит All-on-4?"
        backend = _Backend(
            answer_envelope(
                patient,
                commercial_intent="price",
                service_id="all_on_4",
                service_reference_status="resolved",
                requested_service_id="all_on_4",
                price_text=None,
            )
        )
        sid = "cp-exact-1b-unsafe-too-many"
        _reset_demo_session(sid)
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": user_message, "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-unsafe-too-many"}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message=user_message,
                backend=backend,
            )
            answer = str(outcome.widget.payload.get("answer") or "")
            flags = request.ctx.get("turn_timing", {}).get("flags", {})
        assert outcome.widget.kind == "materialized"
        self._assert_unsafe_price_turn(
            answer=answer,
            patient=patient,
            flags=flags,
            forbidden_amounts=_ALL_ON_4_AMOUNTS + ("999000",),
            diagnostic="multi_offer_too_many",
        )

    def test_missing_patient_label_disables_multi_block(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        _enable_sales_fast(monkeypatch)
        _patch_demo_bundle(monkeypatch, _broken_all_on_4_two_unlabeled_offers())
        patient = "All-on-4 обсуждается индивидуально."
        user_message = "Сколько стоит All-on-4?"
        backend = _Backend(
            answer_envelope(
                patient,
                commercial_intent="price",
                service_id="all_on_4",
                service_reference_status="resolved",
                requested_service_id="all_on_4",
                price_text=None,
            )
        )
        sid = "cp-exact-1b-unsafe-no-label"
        _reset_demo_session(sid)
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": user_message, "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-unsafe-no-label"}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message=user_message,
                backend=backend,
            )
            answer = str(outcome.widget.payload.get("answer") or "")
            flags = request.ctx.get("turn_timing", {}).get("flags", {})
        assert outcome.widget.kind == "materialized"
        assert patient in answer
        assert "custom.unlabeled" not in answer
        assert flags.get("precomposer_offer_availability") == "multiple"
        assert flags.get("multi_price_owner") != "canonical_multi"
        assert flags.get("price_text_diagnostic") == "multi_offer_malformed"
        assert _count_amount_token(answer, "111000") == 0
        assert _count_amount_token(answer, "222000") == 0


class TestFailOpenIntegration:
    def test_optional_marketing_failure_preserves_multi_list(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        from core.target_marketing_selector import OptionalMarketingApplicationError

        _enable_sales_fast(monkeypatch)
        monkeypatch.setattr(
            "core.target_runtime_client_context.runtime_today",
            lambda: date(2026, 8, 10),
        )

        def _boom(*_args: object, **_kwargs: object) -> object:
            raise OptionalMarketingApplicationError("optional_marketing_test_failure")

        monkeypatch.setattr(
            "core.one_call_presentation_pass.merge_marketing_selection_into_materials",
            _boom,
        )
        patient = "All-on-4 восстанавливает всю челюсть на четырёх опорах."
        user_message = "Сколько стоит All-on-4?"
        backend = _Backend(
            answer_envelope(
                patient,
                commercial_intent="price",
                service_id="all_on_4",
                service_reference_status="resolved",
                requested_service_id="all_on_4",
                price_text=None,
            )
        )
        sid = "cp-exact-1b-multi-marketing-fail"
        _reset_demo_session(sid)
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": user_message, "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-multi-marketing-fail"}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message=user_message,
                backend=backend,
            )
            answer = str(outcome.widget.payload.get("answer") or "")
            flags = request.ctx.get("turn_timing", {}).get("flags", {})
        assert outcome.widget.kind == "materialized"
        payload = dict(outcome.widget.payload or {})
        assert payload.get("meta", {}).get("terminal_mode") not in {"admin", "clarify"}
        assert patient in answer
        assert flags.get("multi_price_owner") == "canonical_multi"
        for amount in _ALL_ON_4_AMOUNTS:
            assert _count_amount_token(answer, amount) == 1

    def test_scoped_evidence_degraded_preserves_multi_list(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        from core.target_scoped_response_evidence import TargetScopedResponseEvidenceError

        _enable_sales_fast(monkeypatch)
        monkeypatch.setattr(
            "core.target_runtime_client_context.runtime_today",
            lambda: date(2026, 8, 10),
        )
        _patch_post_composer_audit_failure(
            monkeypatch,
            TargetScopedResponseEvidenceError(
                "scoped_evidence_required_fact_missing",
                ("missing_fact",),
            ),
        )
        patient = "All-on-4 восстанавливает всю челюсть на четырёх опорах."
        user_message = "Сколько стоит All-on-4?"
        backend = _Backend(
            answer_envelope(
                patient,
                commercial_intent="price",
                service_id="all_on_4",
                service_reference_status="resolved",
                requested_service_id="all_on_4",
                price_text=None,
            )
        )
        sid = "cp-exact-1b-multi-scoped-degraded"
        _reset_demo_session(sid)
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": user_message, "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-multi-scoped-degraded"}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message=user_message,
                backend=backend,
            )
            answer = str(outcome.widget.payload.get("answer") or "")
            flags = request.ctx.get("turn_timing", {}).get("flags", {})
        assert outcome.widget.kind == "materialized"
        assert patient in answer
        assert flags.get("post_composer_evidence_degraded") is True
        assert flags.get("multi_price_owner") == "canonical_multi"
        for amount in _ALL_ON_4_AMOUNTS:
            assert _count_amount_token(answer, amount) == 1
        assert _FREE_IMPLANT_CONSULT_SNIPPET in answer.casefold()
        assert "missing_fact" not in answer
        assert "scoped_evidence" not in answer
        session = read_target_runtime_session(sid)
        assert session.last_service_id == "all_on_4"

    def test_streaming_matches_blocking_exact(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        _enable_sales_fast(monkeypatch)
        monkeypatch.setattr(
            "core.target_runtime_client_context.runtime_today",
            lambda: date(2026, 8, 10),
        )
        envelope = answer_envelope(
            "All-on-4 подходит для полного восстановления.",
            commercial_intent="price",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            price_text=None,
        )
        user_message = "Сколько стоит All-on-4?"
        sid_block = "cp-exact-1b-multi-blocking"
        sid_stream = "cp-exact-1b-multi-streaming"
        _reset_demo_session(sid_block)
        _reset_demo_session(sid_stream)
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": user_message, "sid": sid_block, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-multi-blocking"}
            blocking_outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid_block,
                user_message=user_message,
                backend=_Backend(envelope),
            )
            blocking_answer = str(blocking_outcome.widget.payload.get("answer") or "")
            blocking_flags = request.ctx.get("turn_timing", {}).get("flags", {})
        deltas: list[str] = []
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": user_message, "sid": sid_stream, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-multi-streaming"}
            streaming_outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid_stream,
                user_message=user_message,
                backend=_Backend(envelope),
                on_delta=lambda delta: deltas.append(delta),
            )
            streaming_answer = str(streaming_outcome.widget.payload.get("answer") or "")
            streaming_flags = request.ctx.get("turn_timing", {}).get("flags", {})
        assert blocking_outcome.widget.kind == "materialized"
        assert streaming_outcome.widget.kind == "materialized"
        assert streaming_answer == blocking_answer
        assert blocking_flags.get("precomposer_offer_availability") == "multiple"
        assert streaming_flags.get("precomposer_offer_availability") == "multiple"
        assert blocking_flags.get("multi_price_owner") == "canonical_multi"
        assert streaming_flags.get("multi_price_owner") == "canonical_multi"
        for amount in _ALL_ON_4_AMOUNTS:
            assert _count_amount_token(blocking_answer, amount) == 1
        assert _FREE_IMPLANT_CONSULT_SNIPPET in blocking_answer.casefold()
        assert all("price_text" not in delta for delta in deltas)
        assert all('"' not in delta or "{" not in delta for delta in deltas)
        assert read_target_runtime_session(sid_block).last_service_id == "all_on_4"
        assert read_target_runtime_session(sid_stream).last_service_id == "all_on_4"
        bind_session_client("demo")
        mem_reset("cp-exact-1b-multi-isolation-check")
        assert read_target_runtime_session("cp-exact-1b-multi-isolation-check").last_service_id is None

    def test_typeerror_not_suppressed_in_presentation(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        _enable_sales_fast(monkeypatch)

        def _raise_type_error(*_args: object, **_kwargs: object) -> object:
            raise TypeError("multi_unexpected_programming_error")

        monkeypatch.setattr(
            "core.one_call_presentation_pass.materialize_target_composer_request",
            _raise_type_error,
        )
        sid = "cp-exact-1b-multi-typeerror"
        _reset_demo_session(sid)
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-multi-typeerror"}
            with pytest.raises(TypeError, match="multi_unexpected_programming_error"):
                run_sales_fast_widget_turn(
                    client_id="demo",
                    sid=sid,
                    user_message="Сколько стоит All-on-4?",
                    backend=_Backend(
                        answer_envelope(
                            "All-on-4 — протокол.",
                            commercial_intent="price",
                            service_id="all_on_4",
                            service_reference_status="resolved",
                            requested_service_id="all_on_4",
                            price_text=None,
                        )
                    ),
                )


class TestRobustness:
    def test_model_patient_text_with_amount_preserved(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flask_app,
    ) -> None:
        _enable_sales_fast(monkeypatch)
        hostile = "999999"
        backend = _Backend(
            answer_envelope(
                f"Неправильная цена {hostile} ₽.",
                commercial_intent="price",
                service_id="all_on_4",
                service_reference_status="resolved",
                requested_service_id="all_on_4",
                price_text=None,
            )
        )
        sid = "cp-exact-1b-multi-hostile"
        _reset_demo_session(sid)
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"request_id": "rid-multi-hostile"}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message="Сколько стоит All-on-4?",
                backend=backend,
            )
            answer = str(outcome.widget.payload.get("answer") or "")
            flags = request.ctx.get("turn_timing", {}).get("flags", {})
        assert hostile in answer
        assert flags.get("multi_patient_monetary_amount") is True
        assert "318" in answer

    def test_unsafe_multi_resolver_sets_too_many_diagnostic(self) -> None:
        selection = resolve_precomposer_selected_offer(
            bundle=_broken_all_on_4_too_many(),
            doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
            resolution=_governed_resolution("all_on_4"),
        )
        assert selection.availability == "none"
        assert selection.diagnostic == "multi_offer_too_many"

    def test_unsafe_multi_blocks_legacy_authoritative_commerce(self) -> None:
        from core.one_call_presentation_pass import _precomposer_multi_unsafe_block_legacy

        selection = PrecomposerSelectedOfferResult(
            availability="none",
            diagnostic="multi_offer_too_many",
        )
        assert _precomposer_multi_unsafe_block_legacy(
            precomposer_selected_offer=selection,
            original_commercial_intent="price",
            resolved_price_text=None,
        )

    def test_typeerror_not_suppressed_in_formatter(self) -> None:
        with pytest.raises(AttributeError):
            order_precomposer_offers_neutral(
                _all_on_4_multi_selection().offers,
                bundle=object(),  # type: ignore[arg-type]
                service_id="all_on_4",
            )
