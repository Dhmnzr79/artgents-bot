from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle, TargetStrategyMatch
from core.response_strategy import TargetStrategyResolutionError
from core.service_data_context import build_service_data_context
from core.target_brand_offer_projection import (
    TargetBrandOfferProjection,
    TargetBrandOfferProjectionError,
    project_target_service_brand_offers,
)


def _price(mode: str) -> dict[str, object]:
    if mode == "fixed":
        return {
            "mode": "fixed",
            "amount": 120_000,
            "currency": "RUB",
            "billing_unit": "jaw",
        }
    if mode == "from":
        return {
            "mode": "from",
            "min_amount": 68_000,
            "currency": "RUB",
            "billing_unit": "procedure",
        }
    if mode == "range":
        return {
            "mode": "range",
            "min_amount": 80_000,
            "max_amount": 110_000,
            "currency": "RUB",
            "billing_unit": "tooth_package",
        }
    if mode == "no_public_price":
        return {
            "mode": "no_public_price",
            "approved_text": "Стоимость определяется после консультации.",
        }
    raise AssertionError(mode)


def _offer(
    offer_id: str,
    *,
    brand_id: str | None,
    mode: str = "fixed",
    option_id: str | None = None,
    active: bool = True,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "offer_id": offer_id,
        "service_id": "service_one",
        "active": active,
        "price": _price(mode),
        "package": {
            "label": f"Package {offer_id}",
            "includes": [f"Include {offer_id}"],
        },
        "fact_refs": [],
        "followups": [
            {"id": "includes", "label": "Что входит", "action": "price_aspect"}
        ],
    }
    if brand_id is not None:
        payload["brand_id"] = brand_id
    if option_id is not None:
        payload["option_id"] = option_id
    if offer_id == "brand_a_fixed":
        payload["payment_stages"] = [
            {"label": "Этап 1", "amount": 70_000, "currency": "RUB"},
            {"label": "Этап 2", "amount": 50_000, "currency": "RUB"},
        ]
        payload["followups"] = [
            {"id": "stages", "label": "Оплата по этапам", "action": "price_aspect"},
            {"id": "includes", "label": "Что входит", "action": "price_aspect"},
        ]
    return payload


def _bundle(*, service_active: bool = True) -> ResponseSchemaBundle:
    return ResponseSchemaBundle.model_validate(
        {
            "services": {
                "service_one": {
                    "name": "Service One",
                    "family": "implantology",
                    "roles": ["protocol"],
                    "active": service_active,
                    "selection": {"mode": "direct"},
                    "options": [
                        {"option_id": "option_a", "name": "Option A"},
                        {
                            "option_id": "option_off",
                            "name": "Option Off",
                            "active": False,
                        },
                    ],
                }
            },
            "brands": {
                "version": 1,
                "brands": {
                    "brand_a": {
                        "canonical_name": "Brand A",
                        "country": "Country A",
                        "aliases": ["a"],
                    },
                    "brand_b": {
                        "canonical_name": "Brand B",
                        "country": "Country B",
                        "aliases": ["b"],
                    },
                    "brand_unused": {
                        "canonical_name": "Unused",
                        "country": "Country U",
                        "aliases": [],
                    },
                },
            },
            "offers": [
                _offer("brand_a_fixed", brand_id="brand_a"),
                _offer("brand_b_range", brand_id="brand_b", mode="range"),
                _offer("generic_fixed", brand_id=None),
                _offer(
                    "brand_a_option",
                    brand_id="brand_a",
                    mode="from",
                    option_id="option_a",
                ),
                _offer(
                    "brand_a_option_off",
                    brand_id="brand_a",
                    mode="no_public_price",
                    option_id="option_off",
                ),
                _offer("brand_a_inactive", brand_id="brand_a", active=False),
            ],
            "facts": {},
            "strategy": {
                "version": 1,
                "default_max_options": 3,
                "default_offer_priorities": {
                    "brand_b_range": 1_000,
                    "generic_fixed": 900,
                    "brand_a_option_off": 800,
                    "brand_a_option": 30,
                    "brand_a_fixed": 20,
                },
                "rules": [
                    {
                        "id": "full_arch",
                        "match": {"extent": "full_arch"},
                        "max_options": 2,
                        "offer_priorities": {
                            "brand_a_fixed": 100,
                            "brand_b_range": 10_000,
                        },
                    }
                ],
            },
            "marketing": {
                "version": 1,
                "limits": {
                    "max_marketing_facts_per_turn": 0,
                    "max_amplifiers_per_turn": 0,
                    "max_scenarios_per_turn": 0,
                },
                "initial_commercial_blocks": {},
                "scenario_rules": {},
                "cta_contexts": {"default": "callback"},
            },
        }
    )


def _doctors() -> TargetDoctorCatalog:
    return TargetDoctorCatalog.model_validate({"doctors": {}})


def _project(
    bundle: ResponseSchemaBundle | None = None,
    **overrides: object,
) -> TargetBrandOfferProjection:
    bundle = bundle or _bundle()
    context = build_service_data_context(bundle, _doctors(), "service_one")
    params: dict[str, object] = {
        "selected_brand_id": "brand_a",
        "strategy_context": TargetStrategyMatch(),
        "selected_option_id": None,
        "explicit_offer_id": None,
    }
    params.update(overrides)
    return project_target_service_brand_offers(
        context,
        bundle.brands,
        bundle.strategy,
        params.pop("strategy_context"),  # type: ignore[arg-type]
        **params,  # type: ignore[arg-type]
    )


def test_exact_shape_keeps_only_selected_brand_and_delegates_priority() -> None:
    result = _project()

    assert [field.name for field in fields(TargetBrandOfferProjection)] == [
        "service_id",
        "selected_option_id",
        "selected_brand_id",
        "brand",
        "matched_rule_id",
        "max_options",
        "offers",
    ]
    assert result.service_id == "service_one"
    assert result.selected_brand_id == "brand_a"
    assert result.brand.canonical_name == "Brand A"
    assert result.brand.country == "Country A"
    assert [offer.offer_id for offer in result.offers] == [
        "brand_a_option",
        "brand_a_fixed",
    ]
    assert isinstance(result.offers, tuple)
    with pytest.raises(FrozenInstanceError):
        result.max_options = 99  # type: ignore[misc]
    assert not hasattr(result, "__dict__")


@pytest.mark.parametrize("brand_id", [None, 7, "", "  "])
def test_invalid_brand_id_has_stable_error(brand_id: object) -> None:
    with pytest.raises(TargetBrandOfferProjectionError) as exc_info:
        _project(selected_brand_id=brand_id)

    error = exc_info.value
    assert error.code == "brand_offer_projection_brand_id_invalid"
    assert error.value == brand_id
    assert str(error) == f"brand_offer_projection_brand_id_invalid: {brand_id!r}"


@pytest.mark.parametrize("brand_id", ["missing", "Brand_A", " brand_a "])
def test_unknown_brand_id_is_exact_and_never_normalized(brand_id: str) -> None:
    with pytest.raises(TargetBrandOfferProjectionError) as exc_info:
        _project(selected_brand_id=brand_id)

    assert exc_info.value.code == "brand_offer_projection_brand_not_found"
    assert exc_info.value.value == brand_id


def test_existing_brand_without_service_offer_is_empty_without_fallback() -> None:
    result = _project(selected_brand_id="brand_unused")

    assert result.offers == ()
    assert result.brand.canonical_name == "Unused"
    assert result.max_options == 3


def test_other_brand_and_unbranded_strategy_priorities_cannot_add_candidates() -> None:
    result = _project(strategy_context=TargetStrategyMatch(extent="full_arch"))

    assert result.matched_rule_id == "full_arch"
    assert result.max_options == 2
    assert [offer.offer_id for offer in result.offers] == [
        "brand_a_fixed",
        "brand_a_option",
    ]


def test_inactive_parent_offer_and_option_are_filtered_by_s23() -> None:
    inactive_parent = _project(_bundle(service_active=False))
    active_parent = _project()

    assert inactive_parent.offers == ()
    assert "brand_a_inactive" not in {offer.offer_id for offer in active_parent.offers}
    assert "brand_a_option_off" not in {
        offer.offer_id for offer in active_parent.offers
    }


def test_exact_option_composes_with_exact_brand_without_generic_fallback() -> None:
    selected = _project(selected_option_id="option_a")
    inactive = _project(selected_option_id="option_off")

    assert selected.selected_option_id == "option_a"
    assert [offer.offer_id for offer in selected.offers] == ["brand_a_option"]
    assert inactive.offers == ()


def test_explicit_same_brand_pins_and_other_candidates_preserve_s15_error() -> None:
    pinned = _project(explicit_offer_id="brand_a_fixed")
    assert [offer.offer_id for offer in pinned.offers] == [
        "brand_a_fixed",
        "brand_a_option",
    ]

    for offer_id in ("brand_b_range", "generic_fixed", "brand_a_inactive"):
        with pytest.raises(TargetStrategyResolutionError) as exc_info:
            _project(explicit_offer_id=offer_id)
        assert exc_info.value.code == "strategy_explicit_offer_not_candidate"
        assert exc_info.value.value == offer_id


@pytest.mark.parametrize("mode", ["fixed", "from", "range", "no_public_price"])
def test_all_price_shapes_are_preserved_without_math(mode: str) -> None:
    bundle = _bundle()
    payload = bundle.model_dump()
    payload["offers"] = [_offer("brand_a_single", brand_id="brand_a", mode=mode)]
    payload["strategy"] = {
        "version": 1,
        "default_max_options": 3,
        "default_offer_priorities": {"brand_a_single": 1},
        "rules": [],
    }
    single_bundle = ResponseSchemaBundle.model_validate(payload)
    result = _project(single_bundle)
    source = single_bundle.offers[0]

    assert len(result.offers) == 1
    assert result.offers[0].model_dump() == source.model_dump()
    assert result.offers[0] is not source


def test_repeated_calls_are_stateless_and_outputs_are_deep_detached() -> None:
    bundle = _bundle()
    context = build_service_data_context(bundle, _doctors(), "service_one")
    before = bundle.model_dump()

    first = project_target_service_brand_offers(
        context,
        bundle.brands,
        bundle.strategy,
        TargetStrategyMatch(),
        selected_brand_id="brand_a",
    )
    first.brand.canonical_name = "Output only"
    first.offers[0].package.label = "Output package"
    second = project_target_service_brand_offers(
        context,
        bundle.brands,
        bundle.strategy,
        TargetStrategyMatch(),
        selected_brand_id="brand_a",
    )

    assert second.brand.canonical_name == "Brand A"
    assert second.offers[0].package.label == "Package brand_a_option"
    assert bundle.model_dump() == before


def test_exact_signature_and_import_firewall() -> None:
    signature = inspect.signature(project_target_service_brand_offers)
    assert list(signature.parameters) == [
        "service_context",
        "brand_catalog",
        "strategy",
        "strategy_context",
        "selected_brand_id",
        "selected_option_id",
        "explicit_offer_id",
    ]
    assert signature.parameters["selected_brand_id"].default is inspect.Parameter.empty
    assert signature.parameters["selected_option_id"].default is None
    assert signature.parameters["explicit_offer_id"].default is None

    tree = ast.parse(
        Path("core/target_brand_offer_projection.py").read_text(encoding="utf-8")
    )
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert imported_modules <= {
        "__future__",
        "dataclasses",
        "contracts.response_schema",
        "core.service_data_context",
        "core.target_offer_projection",
    }
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"skip", "skipif", "xfail"}
        for node in ast.walk(tree)
    )
