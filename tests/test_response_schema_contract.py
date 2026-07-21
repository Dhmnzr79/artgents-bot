from __future__ import annotations

import ast
import inspect
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from contracts import response_schema
from contracts.response_schema import (
    FactSourceRef,
    ResponseSchemaBundle,
    S1_MODEL_TYPES,
    SourceRef,
    TargetClinicStrategy,
    TargetCommercialFact,
    TargetFixedPrice,
    TargetMarketingLimits,
    TargetMarketingPolicy,
    TargetNoPublicPrice,
    TargetOffer,
    TargetOptionSelection,
    TargetPaymentStage,
    TargetRangePrice,
    TargetService,
    TargetStrategyMatch,
)


def _valid_bundle_payload() -> dict[str, object]:
    return {
        "services": {
            "service_one": {
                "name": "Service One",
                "aliases": ["First service"],
                "family": "implantology",
                "roles": ["protocol"],
                "active": True,
                "content_ref": "service_one.md",
                "selection": {
                    "mode": "scope",
                    "extent": ["one_tooth", "few_teeth"],
                },
                "options": [
                    {
                        "option_id": "option_one",
                        "name": "Option One",
                        "selection": {"extent": ["one_tooth"]},
                    }
                ],
            }
        },
        "brands": {
            "version": 1,
            "brands": {
                "brand_one": {
                    "canonical_name": "Brand One",
                    "country": "Country One",
                    "aliases": ["B1"],
                }
            },
        },
        "offers": [
            {
                "offer_id": "offer_one",
                "service_id": "service_one",
                "option_id": "option_one",
                "brand_id": "brand_one",
                "active": True,
                "price": {
                    "mode": "fixed",
                    "amount": 120_000,
                    "currency": "RUB",
                    "billing_unit": "tooth_package",
                },
                "package": {
                    "label": "one package",
                    "includes": ["part one", "part two"],
                },
                "fact_refs": ["consultation_offer"],
                "followups": [
                    {"id": "includes", "label": "What is included", "action": "price_aspect"}
                ],
            }
        ],
        "facts": {
            "consultation_offer": {
                "id": "consultation_offer",
                "kind": "consultation",
                "text_fact": "Exact source-owned fact.",
                "render_mode": "strict",
                "active": True,
                "active_from": "2026-07-01",
                "active_until": "2026-07-31",
                "allowed_service_ids": ["service_one"],
                "detail_ref": "clinic.md#consultation",
                "incompatible_with": [],
            }
        },
        "strategy": {
            "version": 1,
            "default_max_options": 3,
            "rules": [
                {
                    "id": "service_one_priority",
                    "match": {"family": "implantology", "extent": "one_tooth"},
                    "max_options": 2,
                    "service_priorities": {"service_one": 100},
                    "offer_priorities": {"offer_one": 80},
                }
            ],
        },
        "marketing": {
            "version": 1,
            "limits": {
                "max_marketing_facts_per_turn": 3,
                "max_amplifiers_per_turn": 2,
                "max_scenarios_per_turn": 2,
            },
            "initial_commercial_blocks": {
                "service_context": {"ordered_fact_refs": ["fact:consultation_offer"]}
            },
            "scenario_rules": {
                "cost": {
                    "ordered_amplifier_refs": [
                        "fact:consultation_offer",
                        "kb:service.md#approved_chunk",
                        "doctor:doctor_one",
                    ],
                    "allowed_semantic_contexts": ["service_context"],
                }
            },
            "cta_contexts": {"service_context": "consult", "default": "callback"},
        },
    }


def _error_text(model: type, payload: object) -> str:
    with pytest.raises(ValidationError) as exc_info:
        model.model_validate(payload)
    return str(exc_info.value)


def test_minimal_bundle_with_all_six_sources_validates() -> None:
    bundle = ResponseSchemaBundle.model_validate(_valid_bundle_payload())

    assert bundle.offers[0].price.mode == "fixed"
    assert bundle.strategy.rules[0].service_priorities == {"service_one": 100}
    assert bundle.marketing.scenario_rules["cost"].ordered_amplifier_refs[1] == (
        "kb:service.md#approved_chunk"
    )


def test_every_s1_model_forbids_extra_fields() -> None:
    discovered_models = {
        value
        for value in vars(response_schema).values()
        if inspect.isclass(value)
        and issubclass(value, BaseModel)
        and value.__module__ == response_schema.__name__
    }
    assert discovered_models == {response_schema.TargetSchemaModel, *S1_MODEL_TYPES}
    assert all(model.model_config.get("extra") == "forbid" for model in discovered_models)

    payload = _valid_bundle_payload()
    payload["offers"][0]["package"]["unexpected"] = True
    assert "extra_forbidden" in _error_text(ResponseSchemaBundle, payload)


@pytest.mark.parametrize(
    ("model", "payload", "token"),
    [
        (
            TargetService,
            {"name": "x", "family": "medical", "selection": {"mode": "scope"}},
            "literal_error",
        ),
        (
            TargetService,
            {"name": "x", "family": "therapy", "selection": {"mode": "recommend"}},
            "literal_error",
        ),
        (
            TargetService,
            {
                "name": "x",
                "family": "therapy",
                "selection": {"mode": "scope", "jaw": ["both"]},
            },
            "literal_error",
        ),
        (
            TargetService,
            {"name": "x", "family": "therapy", "selection": {"mode": "scope", "extent": []}},
            "selection_values_empty",
        ),
        (
            TargetService,
            {
                "name": "x",
                "family": "therapy",
                "selection": {"mode": "scope", "extent": ["one_tooth", "one_tooth"]},
            },
            "selection_values_duplicate",
        ),
        (TargetOptionSelection, {"mode": "scope", "extent": ["one_tooth"]}, "extra_forbidden"),
        (TargetStrategyMatch, {"extent": ["one_tooth"]}, "literal_error"),
    ],
)
def test_selection_shapes_are_strict(model: type, payload: dict[str, object], token: str) -> None:
    assert token in _error_text(model, payload)


def test_option_ids_are_unique_within_service() -> None:
    service = _valid_bundle_payload()["services"]["service_one"]
    service["options"].append(deepcopy(service["options"][0]))
    assert "service_option_id_duplicate" in _error_text(TargetService, service)


@pytest.mark.parametrize(
    "price",
    [
        {"mode": "fixed", "amount": 10, "currency": "RUB", "billing_unit": "tooth"},
        {"mode": "from", "min_amount": 10, "currency": "RUB", "billing_unit": "implant"},
        {
            "mode": "range",
            "min_amount": 10,
            "max_amount": 20,
            "currency": "RUB",
            "billing_unit": "jaw",
        },
        {"mode": "no_public_price", "approved_text": "Contact the clinic."},
    ],
)
def test_all_four_price_modes_validate(price: dict[str, object]) -> None:
    payload = _valid_bundle_payload()["offers"][0]
    payload["price"] = price
    assert TargetOffer.model_validate(payload).price.mode == price["mode"]


@pytest.mark.parametrize(
    ("price", "token"),
    [
        (
            {
                "mode": "fixed",
                "amount": 10,
                "min_amount": 5,
                "currency": "RUB",
                "billing_unit": "tooth",
            },
            "extra_forbidden",
        ),
        (
            {
                "mode": "from",
                "amount": 10,
                "currency": "RUB",
                "billing_unit": "tooth",
            },
            "min_amount",
        ),
        (
            {
                "mode": "range",
                "min_amount": 10,
                "currency": "RUB",
                "billing_unit": "jaw",
            },
            "max_amount",
        ),
        (
            {"mode": "no_public_price", "approved_text": "Call us", "amount": 10},
            "extra_forbidden",
        ),
    ],
)
def test_price_mode_shapes_reject_foreign_or_missing_fields(
    price: dict[str, object], token: str
) -> None:
    payload = _valid_bundle_payload()["offers"][0]
    payload["price"] = price
    assert token in _error_text(TargetOffer, payload)


@pytest.mark.parametrize(
    ("amount", "token"),
    [(True, "int_type"), (1.5, "int_type"), ("10", "int_type"), (-1, "greater_than_equal")],
)
def test_money_is_strict_nonnegative_integer(amount: object, token: str) -> None:
    payload = {"mode": "fixed", "amount": amount, "currency": "RUB", "billing_unit": "unit"}
    assert token in _error_text(TargetFixedPrice, payload)


def test_offer_preserves_authored_payment_stage_order_and_values() -> None:
    payload = _valid_bundle_payload()["offers"][0]
    payload["payment_stages"] = [
        {"label": "Surgery", "amount": 70_000, "currency": "RUB"},
        {"label": "Prosthetics", "amount": 50_000, "currency": "RUB"},
    ]
    payload["followups"].insert(
        0, {"id": "stages", "label": "Payment stages", "action": "price_aspect"}
    )

    offer = TargetOffer.model_validate(payload)

    assert [stage.model_dump() for stage in offer.payment_stages or []] == [
        {"label": "Surgery", "amount": 70_000, "currency": "RUB"},
        {"label": "Prosthetics", "amount": 50_000, "currency": "RUB"},
    ]


def test_missing_and_null_payment_stages_mean_no_authored_breakdown() -> None:
    missing_payload = _valid_bundle_payload()["offers"][0]
    missing_offer = TargetOffer.model_validate(missing_payload)
    assert missing_offer.payment_stages is None
    assert "payment_stages" not in missing_offer.model_dump(exclude_none=True)

    null_payload = _valid_bundle_payload()["offers"][0]
    null_payload["payment_stages"] = None
    null_offer = TargetOffer.model_validate(null_payload)
    assert null_offer.payment_stages is None
    assert "payment_stages" not in null_offer.model_dump(exclude_none=True)


def test_single_payment_stage_without_followup_is_valid() -> None:
    payload = _valid_bundle_payload()["offers"][0]
    payload["payment_stages"] = [
        {"label": "Deposit", "amount": 10_000, "currency": "RUB"}
    ]

    offer = TargetOffer.model_validate(payload)

    assert len(offer.payment_stages or []) == 1
    assert [followup.id for followup in offer.followups] == ["includes"]


def test_empty_and_duplicate_payment_stages_are_rejected() -> None:
    payload = _valid_bundle_payload()["offers"][0]
    payload["payment_stages"] = []
    assert "offer_payment_stages_empty" in _error_text(TargetOffer, payload)

    payload = _valid_bundle_payload()["offers"][0]
    payload["payment_stages"] = [
        {"label": "Same stage", "amount": 10, "currency": "RUB"},
        {"label": "Same stage", "amount": 20, "currency": "RUB"},
    ]
    assert "offer_payment_stage_label_duplicate" in _error_text(TargetOffer, payload)


@pytest.mark.parametrize(
    ("field", "value", "token"),
    [
        ("label", "   ", "string_must_not_be_blank"),
        ("currency", "   ", "string_must_not_be_blank"),
        ("amount", True, "int_type"),
        ("amount", 1.5, "int_type"),
        ("amount", "10", "int_type"),
        ("amount", -1, "greater_than_equal"),
    ],
)
def test_payment_stage_fields_are_strict(field: str, value: object, token: str) -> None:
    stage = {"label": "Stage", "amount": 10, "currency": "RUB"}
    stage[field] = value
    assert token in _error_text(TargetPaymentStage, stage)


def test_stages_followup_requires_authored_payment_stages() -> None:
    payload = _valid_bundle_payload()["offers"][0]
    payload["followups"].insert(
        0, {"id": "stages", "label": "Payment stages", "action": "price_aspect"}
    )
    assert "offer_stages_followup_requires_payment_stages" in _error_text(
        TargetOffer, payload
    )


def test_payment_stages_need_no_followup_or_sum_equality() -> None:
    payload = _valid_bundle_payload()["offers"][0]
    payload["payment_stages"] = [
        {"label": "Partial payment", "amount": 1, "currency": "RUB"}
    ]

    offer = TargetOffer.model_validate(payload)

    assert offer.price.amount == 120_000
    assert sum(stage.amount for stage in offer.payment_stages or []) == 1
    assert [followup.id for followup in offer.followups] == ["includes"]


def test_range_order_and_no_public_numeric_fields_are_strict() -> None:
    assert "price_range_min_exceeds_max" in _error_text(
        TargetRangePrice,
        {"mode": "range", "min_amount": 20, "max_amount": 10, "currency": "RUB", "billing_unit": "jaw"},
    )
    assert "extra_forbidden" in _error_text(
        TargetNoPublicPrice,
        {"mode": "no_public_price", "approved_text": "Call", "amount": 10},
    )


@pytest.mark.parametrize(
    ("field", "value", "token"),
    [
        ("service_id", "missing", "bundle_offer_service_missing"),
        ("option_id", "missing", "bundle_offer_option_missing"),
        ("brand_id", "missing", "bundle_offer_brand_missing"),
        ("fact_refs", ["missing"], "bundle_offer_fact_missing"),
    ],
)
def test_offer_cross_references_must_exist(field: str, value: object, token: str) -> None:
    payload = _valid_bundle_payload()
    payload["offers"][0][field] = value
    assert token in _error_text(ResponseSchemaBundle, payload)


@pytest.mark.parametrize(
    ("field", "value", "token"),
    [
        ("allowed_service_ids", ["missing"], "bundle_fact_service_missing"),
        ("incompatible_with", ["missing"], "bundle_fact_incompatible_missing"),
    ],
)
def test_fact_cross_references_must_exist(field: str, value: object, token: str) -> None:
    payload = _valid_bundle_payload()
    payload["facts"]["consultation_offer"][field] = value
    assert token in _error_text(ResponseSchemaBundle, payload)


def test_duplicate_ids_refs_and_self_incompatibility_are_rejected() -> None:
    payload = _valid_bundle_payload()
    payload["offers"].append(deepcopy(payload["offers"][0]))
    assert "bundle_offer_id_duplicate" in _error_text(ResponseSchemaBundle, payload)

    payload = _valid_bundle_payload()
    payload["facts"]["other_key"] = deepcopy(payload["facts"]["consultation_offer"])
    assert "bundle_fact_id_duplicate" in _error_text(ResponseSchemaBundle, payload)

    strategy = _valid_bundle_payload()["strategy"]
    strategy["rules"].append(deepcopy(strategy["rules"][0]))
    assert "strategy_rule_id_duplicate" in _error_text(TargetClinicStrategy, strategy)

    policy = _valid_bundle_payload()["marketing"]
    policy["initial_commercial_blocks"]["service_context"]["ordered_fact_refs"].append(
        "fact:consultation_offer"
    )
    assert "initial_fact_ref_duplicate" in _error_text(TargetMarketingPolicy, policy)

    fact = _valid_bundle_payload()["facts"]["consultation_offer"]
    fact["incompatible_with"] = ["consultation_offer"]
    assert "fact_incompatible_self_reference" in _error_text(TargetCommercialFact, fact)


@pytest.mark.parametrize(
    ("active_from", "active_until", "token"),
    [
        ("2026/07/01", "2026-07-31", "date_must_be_iso_yyyy_mm_dd"),
        ("2026-07-01", "2026-02-30", "date_must_be_iso_yyyy_mm_dd"),
        ("2026-08-01", "2026-07-31", "fact_active_from_after_active_until"),
    ],
)
def test_fact_dates_are_exact_and_ordered(active_from: str, active_until: str, token: str) -> None:
    fact = _valid_bundle_payload()["facts"]["consultation_offer"]
    fact["active_from"] = active_from
    fact["active_until"] = active_until
    assert token in _error_text(TargetCommercialFact, fact)


def test_strategy_limits_and_priorities_are_strict() -> None:
    strategy = _valid_bundle_payload()["strategy"]
    strategy["default_max_options"] = 4
    assert "less_than_equal" in _error_text(TargetClinicStrategy, strategy)

    strategy = _valid_bundle_payload()["strategy"]
    strategy["rules"][0]["max_options"] = 4
    assert "less_than_equal" in _error_text(TargetClinicStrategy, strategy)

    payload = _valid_bundle_payload()
    payload["strategy"]["rules"][0]["service_priorities"] = {"missing": 10}
    assert "bundle_strategy_service_missing" in _error_text(ResponseSchemaBundle, payload)

    payload = _valid_bundle_payload()
    payload["strategy"]["rules"][0]["offer_priorities"] = {"missing": 10}
    assert "bundle_strategy_offer_missing" in _error_text(ResponseSchemaBundle, payload)


def test_marketing_limits_scenarios_and_local_fact_refs_are_strict() -> None:
    assert "less_than_equal" in _error_text(
        TargetMarketingLimits,
        {
            "max_marketing_facts_per_turn": 4,
            "max_amplifiers_per_turn": 2,
            "max_scenarios_per_turn": 2,
        },
    )
    assert "marketing_amplifier_limit_exceeds_fact_limit" in _error_text(
        TargetMarketingLimits,
        {
            "max_marketing_facts_per_turn": 1,
            "max_amplifiers_per_turn": 2,
            "max_scenarios_per_turn": 2,
        },
    )
    assert "less_than_equal" in _error_text(
        TargetMarketingLimits,
        {
            "max_marketing_facts_per_turn": 3,
            "max_amplifiers_per_turn": 3,
            "max_scenarios_per_turn": 2,
        },
    )
    assert "less_than_equal" in _error_text(
        TargetMarketingLimits,
        {
            "max_marketing_facts_per_turn": 3,
            "max_amplifiers_per_turn": 2,
            "max_scenarios_per_turn": 3,
        },
    )

    policy = _valid_bundle_payload()["marketing"]
    policy["scenario_rules"] = {"medical_fear": policy["scenario_rules"]["cost"]}
    assert "literal_error" in _error_text(TargetMarketingPolicy, policy)

    payload = _valid_bundle_payload()
    payload["marketing"]["scenario_rules"]["cost"]["ordered_amplifier_refs"][0] = "fact:missing"
    assert "bundle_marketing_fact_missing" in _error_text(ResponseSchemaBundle, payload)


@pytest.mark.parametrize(
    ("value", "token"),
    [
        ("other:value", "source_ref_prefix_invalid"),
        ("fact:", "source_ref_target_empty"),
        ("doctor:   ", "source_ref_target_empty"),
        ("kb:doc-only", "kb_ref_requires_doc_and_chunk"),
        ("kb:#chunk", "kb_ref_requires_doc_and_chunk"),
        ("kb:doc#", "kb_ref_requires_doc_and_chunk"),
    ],
)
def test_source_ref_wire_format_is_strict(value: str, token: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        TypeAdapter(SourceRef).validate_python(value)
    assert token in str(exc_info.value)


def test_source_refs_are_preserved_and_external_refs_need_no_loader() -> None:
    raw = "kb:folder/doc.md#Approved_Chunk"
    assert TypeAdapter(SourceRef).validate_python(raw) == raw
    assert TypeAdapter(SourceRef).validate_python("doctor:doctor_one") == "doctor:doctor_one"
    assert TypeAdapter(FactSourceRef).validate_python("fact:consultation_offer") == (
        "fact:consultation_offer"
    )
    assert ResponseSchemaBundle.model_validate(_valid_bundle_payload())


def test_contract_imports_no_runtime_loader_session_or_a9_modules() -> None:
    source_path = Path(response_schema.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_roots = {
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_roots.update(
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert imported_roots <= {"__future__", "datetime", "typing", "pydantic"}
    assert set(ResponseSchemaBundle.model_fields) == {
        "services",
        "brands",
        "offers",
        "facts",
        "strategy",
        "marketing",
    }
