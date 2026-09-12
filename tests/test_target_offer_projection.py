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
from core.target_offer_projection import (
    TargetOfferProjection,
    TargetOfferProjectionError,
    project_target_service_offers,
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
    mode: str,
    option_id: str | None = None,
    active: bool = True,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "offer_id": offer_id,
        "service_id": "service_one",
        "active": active,
        "price": _price(mode),
        "package": {
            "label": f"Exact package {offer_id}",
            "includes": [f"Exact include {offer_id}"],
        },
        "fact_refs": [],
        "followups": [
            {
                "id": "includes",
                "label": "Что входит",
                "action": "price_aspect",
            }
        ],
    }
    if option_id is not None:
        payload["option_id"] = option_id
    if offer_id == "generic_fixed":
        payload["payment_stages"] = [
            {"label": "Этап 1", "amount": 70_000, "currency": "RUB"},
            {"label": "Этап 2", "amount": 50_000, "currency": "RUB"},
        ]
        payload["followups"] = [
            {"id": "stages", "label": "Оплата по этапам", "action": "price_aspect"},
            {"id": "includes", "label": "Что входит", "action": "price_aspect"},
        ]
    return payload


def _bundle(
    *,
    service_active: bool = True,
    no_public_active: bool = False,
) -> ResponseSchemaBundle:
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
                            "option_id": "option_b",
                            "name": "Option B",
                            "active": False,
                        },
                        {
                            "option_id": "option_c",
                            "name": "Option C",
                            "active": True,
                        },
                    ],
                },
                "service_two": {
                    "name": "Service Two",
                    "family": "therapy",
                    "roles": [],
                    "active": True,
                    "selection": {"mode": "direct"},
                    "options": [],
                },
            },
            "brands": {"version": 1, "brands": {}},
            "offers": [
                _offer("generic_fixed", mode="fixed"),
                _offer("option_a_from", mode="from", option_id="option_a"),
                _offer("option_b_range", mode="range", option_id="option_b"),
                _offer(
                    "generic_no_public",
                    mode="no_public_price",
                    active=no_public_active,
                ),
                _offer("option_c_range", mode="range", option_id="option_c"),
                _offer("inactive_offer", mode="fixed", active=False),
                {
                    **_offer("other_offer", mode="fixed"),
                    "service_id": "service_two",
                },
            ],
            "facts": {},
            "strategy": {
                "version": 1,
                "default_max_options": 3,
                "default_offer_priorities": {
                    "option_c_range": 30,
                    "generic_fixed": 20,
                    "option_a_from": 10,
                    "generic_no_public": 40,
                    "other_offer": 10_000,
                },
                "rules": [
                    {
                        "id": "extraction_first",
                        "match": {"stage": "extraction_context"},
                        "max_options": 2,
                        "offer_priorities": {
                            "generic_fixed": 100,
                            "option_c_range": 5,
                        },
                    },
                    {
                        "id": "one_tooth_later",
                        "match": {"extent": "one_tooth"},
                        "max_options": 3,
                        "offer_priorities": {"option_a_from": 1_000},
                    },
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
    return TargetDoctorCatalog.model_validate(
        {
            "doctors": {
                "doctor_one": {
                    "name": "Doctor One",
                    "position": "Implantologist",
                    "experience_years": 15,
                    "service_ids": ["service_one"],
                    "profile_ref": "kb:doctor_one.md#profile",
                }
            }
        }
    )


def _inputs(**bundle_kwargs: object):
    bundle = _bundle(**bundle_kwargs)  # type: ignore[arg-type]
    context = build_service_data_context(bundle, _doctors(), "service_one")
    return bundle, context


def _project(
    bundle: ResponseSchemaBundle | None = None,
    **overrides: object,
) -> TargetOfferProjection:
    if bundle is None:
        bundle = _bundle()
    context = build_service_data_context(bundle, _doctors(), "service_one")
    params: dict[str, object] = {
        "strategy_context": TargetStrategyMatch(),
        "selected_option_id": None,
        "explicit_offer_id": None,
    }
    params.update(overrides)
    return project_target_service_offers(
        context,
        bundle.strategy,
        params.pop("strategy_context"),  # type: ignore[arg-type]
        **params,  # type: ignore[arg-type]
    )


def test_exact_shape_filters_active_records_and_applies_default_priority() -> None:
    result = _project()

    assert [field.name for field in fields(TargetOfferProjection)] == [
        "service_id",
        "selected_option_id",
        "matched_rule_id",
        "max_options",
        "offers",
    ]
    assert result.service_id == "service_one"
    assert result.selected_option_id is None
    assert result.matched_rule_id is None
    assert result.max_options == 3
    assert [offer.offer_id for offer in result.offers] == [
        "option_c_range",
        "generic_fixed",
        "option_a_from",
    ]
    assert isinstance(result.offers, tuple)
    with pytest.raises(FrozenInstanceError):
        result.max_options = 99  # type: ignore[misc]
    assert not hasattr(result, "__dict__")


def test_inactive_parent_returns_empty_without_fallback() -> None:
    result = _project(_bundle(service_active=False))

    assert result.offers == ()
    assert result.max_options == 3


def test_inactive_offer_and_false_option_are_never_candidates() -> None:
    result = _project()
    ids = {offer.offer_id for offer in result.offers}

    assert "inactive_offer" not in ids
    assert "option_b_range" not in ids


@pytest.mark.parametrize(
    ("option_id", "expected_ids"),
    [
        ("option_a", ["option_a_from"]),
        ("option_b", []),
        ("option_c", ["option_c_range"]),
    ],
)
def test_exact_option_filter_never_substitutes_generic_or_other_option(
    option_id: str, expected_ids: list[str]
) -> None:
    result = _project(selected_option_id=option_id)

    assert result.selected_option_id == option_id
    assert [offer.offer_id for offer in result.offers] == expected_ids


@pytest.mark.parametrize("option_id", [7, ""])
def test_invalid_option_id_has_stable_error(option_id: object) -> None:
    with pytest.raises(TargetOfferProjectionError) as exc_info:
        _project(selected_option_id=option_id)

    error = exc_info.value
    assert error.code == "offer_projection_option_id_invalid"
    assert error.value == option_id
    assert str(error) == f"offer_projection_option_id_invalid: {option_id!r}"


def test_unknown_exact_option_has_stable_error() -> None:
    with pytest.raises(TargetOfferProjectionError) as exc_info:
        _project(selected_option_id="missing")

    assert exc_info.value.code == "offer_projection_option_not_found"
    assert exc_info.value.value == "missing"


def test_option_id_is_not_trimmed_or_normalized() -> None:
    with pytest.raises(TargetOfferProjectionError) as exc_info:
        _project(selected_option_id=" option_a ")

    assert exc_info.value.code == "offer_projection_option_not_found"
    assert exc_info.value.value == " option_a "


@pytest.mark.parametrize("offer_id", [5, ""])
def test_invalid_explicit_offer_id_has_stable_error(offer_id: object) -> None:
    with pytest.raises(TargetOfferProjectionError) as exc_info:
        _project(explicit_offer_id=offer_id)

    assert exc_info.value.code == "offer_projection_explicit_offer_id_invalid"
    assert exc_info.value.value == offer_id


def test_explicit_offer_id_is_not_trimmed_or_normalized() -> None:
    with pytest.raises(TargetStrategyResolutionError) as exc_info:
        _project(explicit_offer_id=" generic_fixed ")

    assert exc_info.value.code == "strategy_explicit_offer_not_candidate"
    assert exc_info.value.value == " generic_fixed "


def test_explicit_eligible_offer_is_pinned_before_priority_and_cap() -> None:
    result = _project(explicit_offer_id="option_a_from")

    assert [offer.offer_id for offer in result.offers] == [
        "option_a_from",
        "option_c_range",
        "generic_fixed",
    ]


@pytest.mark.parametrize(
    ("overrides", "explicit_id"),
    [
        ({}, "inactive_offer"),
        ({}, "option_b_range"),
        ({"selected_option_id": "option_a"}, "generic_fixed"),
        ({"selected_option_id": "option_a"}, "option_c_range"),
    ],
)
def test_explicit_non_candidate_preserves_existing_s15_error(
    overrides: dict[str, object], explicit_id: str
) -> None:
    with pytest.raises(TargetStrategyResolutionError) as exc_info:
        _project(explicit_offer_id=explicit_id, **overrides)

    assert exc_info.value.code == "strategy_explicit_offer_not_candidate"
    assert exc_info.value.value == explicit_id


def test_first_matching_rule_overrides_priority_and_cap_without_later_merge() -> None:
    result = _project(
        strategy_context=TargetStrategyMatch(
            stage="extraction_context",
            extent="one_tooth",
        )
    )

    assert result.matched_rule_id == "extraction_first"
    assert result.max_options == 2
    assert [offer.offer_id for offer in result.offers] == [
        "generic_fixed",
        "option_a_from",
    ]


def test_priority_map_cannot_add_ghost_or_filtered_candidates() -> None:
    result = _project()
    ids = {offer.offer_id for offer in result.offers}

    assert "other_offer" not in ids
    assert "option_b_range" not in ids
    assert "inactive_offer" not in ids


def test_all_price_shapes_and_source_owned_fields_are_preserved_without_math() -> None:
    bundle = _bundle(no_public_active=True)
    context = build_service_data_context(bundle, _doctors(), "service_one")
    original_by_id = {offer.offer_id: offer for offer in context.offers}

    general = project_target_service_offers(
        context,
        bundle.strategy,
        TargetStrategyMatch(),
    )
    option_a = project_target_service_offers(
        context,
        bundle.strategy,
        TargetStrategyMatch(),
        selected_option_id="option_a",
    )
    option_c = project_target_service_offers(
        context,
        bundle.strategy,
        TargetStrategyMatch(),
        selected_option_id="option_c",
    )
    returned = {offer.offer_id: offer for offer in (*general.offers, *option_a.offers, *option_c.offers)}

    assert {offer.price.mode for offer in returned.values()} == {
        "fixed",
        "from",
        "range",
        "no_public_price",
    }
    for offer_id, offer in returned.items():
        assert offer.model_dump() == original_by_id[offer_id].model_dump()
        assert offer is not original_by_id[offer_id]
    fixed = returned["generic_fixed"]
    assert [stage.amount for stage in fixed.payment_stages or []] == [70_000, 50_000]
    assert [followup.id for followup in fixed.followups] == ["stages", "includes"]


def test_repeated_calls_are_stateless_and_deep_detached() -> None:
    bundle, context = _inputs()
    bundle_before = bundle.model_dump()
    context_service_before = context.service.model_dump()
    context_offers_before = [offer.model_dump() for offer in context.offers]
    strategy_before = bundle.strategy.model_dump()
    strategy_context = TargetStrategyMatch(extent="full_arch")
    strategy_context_before = strategy_context.model_dump()

    first = project_target_service_offers(
        context,
        bundle.strategy,
        strategy_context,
    )
    first.offers[0].package.label = "Output only"
    first.offers[1].price.amount = 999_999  # type: ignore[union-attr]
    second = project_target_service_offers(
        context,
        bundle.strategy,
        strategy_context,
    )

    assert second.offers[0].package.label == "Exact package option_c_range"
    assert second.offers[1].price.amount == 120_000  # type: ignore[union-attr]
    assert bundle.model_dump() == bundle_before
    assert context.service.model_dump() == context_service_before
    assert [offer.model_dump() for offer in context.offers] == context_offers_before
    assert bundle.strategy.model_dump() == strategy_before
    assert strategy_context.model_dump() == strategy_context_before


def test_exact_signature_and_import_firewall() -> None:
    signature = inspect.signature(project_target_service_offers)
    assert list(signature.parameters) == [
        "service_context",
        "strategy",
        "strategy_context",
        "selected_option_id",
        "explicit_offer_id",
        "effective_scope",
        "explicit_service_price_lookup",
    ]
    assert signature.parameters["selected_option_id"].default is None
    assert signature.parameters["explicit_offer_id"].default is None
    assert signature.parameters["effective_scope"].default is None
    assert signature.parameters["explicit_service_price_lookup"].default is False

    source_path = Path("core/target_offer_projection.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert imported_modules <= {
        "__future__",
        "dataclasses",
        "contracts.effective_scope",
        "contracts.response_schema",
        "core.response_strategy",
        "core.service_data_context",
        "core.target_explicit_service_price_lookup",
        "core.target_offer_extent_applicability",
    }
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"skip", "skipif", "xfail"}
        for node in ast.walk(tree)
    )
