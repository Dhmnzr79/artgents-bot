from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, fields
from datetime import date
from pathlib import Path

import pytest

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle, TargetStrategyMatch
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from contracts.service_consultation import ServiceConsultationValue
from core.target_brand_resolver import TargetBrandResolutionError
from core.target_marketing_selector import (
    TargetMarketingSelectionError,
    select_target_marketing,
)
from core.target_offline_response_assembly import (
    TargetOfflineResponseAssemblyError,
    TargetOfflineResponseMaterials,
    assemble_target_offline_response_materials,
)
from core.target_response_evidence import (
    TargetResponseEvidencePackageError,
    build_target_response_evidence_package,
)
from core.target_service_resolver import TargetServiceResolutionError


TODAY = date(2026, 7, 22)


def _offer(
    offer_id: str,
    *,
    brand_id: str | None,
    active: bool = True,
    mode: str = "fixed",
) -> dict[str, object]:
    if mode == "fixed":
        price: dict[str, object] = {
            "mode": "fixed",
            "amount": 120_000,
            "currency": "RUB",
            "billing_unit": "jaw",
        }
    elif mode == "from":
        price = {
            "mode": "from",
            "min_amount": 80_000,
            "currency": "RUB",
            "billing_unit": "procedure",
        }
    else:
        price = {
            "mode": "range",
            "min_amount": 150_000,
            "max_amount": 190_000,
            "currency": "RUB",
            "billing_unit": "jaw",
        }
    payload: dict[str, object] = {
        "offer_id": offer_id,
        "service_id": "service_one",
        "active": active,
        "price": price,
        "package": {"label": f"Package {offer_id}", "includes": ["Exact item"]},
        "fact_refs": [],
        "followups": [{"id": "includes", "label": "Includes", "action": "price_aspect"}],
    }
    if brand_id is not None:
        payload["brand_id"] = brand_id
    if offer_id == "brand_a_fixed":
        payload["payment_stages"] = [
            {"label": "Stage 1", "amount": 70_000, "currency": "RUB"},
            {"label": "Stage 2", "amount": 50_000, "currency": "RUB"},
        ]
        payload["followups"] = [
            {"id": "stages", "label": "Stages", "action": "price_aspect"},
            {"id": "includes", "label": "Includes", "action": "price_aspect"},
        ]
    return payload


def _bundle(
    *,
    ambiguous_service: bool = False,
    ambiguous_brand: bool = False,
) -> ResponseSchemaBundle:
    services: dict[str, object] = {
        "service_one": {
            "name": "Service One",
            "aliases": ["one"],
            "family": "implantology",
            "roles": ["protocol"],
            "active": True,
            "content_ref": "service_one.md",
            "selection": {"mode": "direct"},
            "options": [],
        },
        "service_inactive": {
            "name": "Inactive",
            "aliases": ["off"],
            "family": "therapy",
            "roles": ["supporting"],
            "active": False,
            "content_ref": "inactive.md",
            "selection": {"mode": "direct"},
            "options": [],
        },
    }
    if ambiguous_service:
        services["service_collision"] = {
            "name": "Collision",
            "aliases": ["one"],
            "family": "therapy",
            "roles": ["supporting"],
            "active": True,
            "content_ref": "collision.md",
            "selection": {"mode": "direct"},
            "options": [],
        }
    brand_b_aliases = ["b", "same"] if ambiguous_brand else ["b"]
    return ResponseSchemaBundle.model_validate(
        {
            "services": services,
            "brands": {
                "version": 1,
                "brands": {
                    "brand_a": {
                        "canonical_name": "Brand A",
                        "country": "Aland",
                        "aliases": ["a", "same"],
                    },
                    "brand_b": {
                        "canonical_name": "Brand B",
                        "country": "Bland",
                        "aliases": brand_b_aliases,
                    },
                    "brand_unused": {
                        "canonical_name": "Unused",
                        "country": "Nowhere",
                        "aliases": ["unused"],
                    },
                },
            },
            "offers": [
                _offer("brand_a_fixed", brand_id="brand_a"),
                _offer("brand_b_range", brand_id="brand_b", mode="range"),
                _offer("generic_from", brand_id=None, mode="from"),
                _offer("brand_a_inactive", brand_id="brand_a", active=False),
            ],
            "facts": {
                "initial_fact": {
                    "id": "initial_fact",
                    "kind": "commercial",
                    "text_fact": "Exact clinic fact.",
                    "render_mode": "strict",
                    "active": True,
                    "allowed_service_ids": ["service_one"],
                    "incompatible_with": [],
                }
            },
            "strategy": {
                "version": 1,
                "default_max_options": 3,
                "default_offer_priorities": {
                    "brand_b_range": 30,
                    "generic_from": 20,
                    "brand_a_fixed": 10,
                },
                "rules": [
                    {
                        "id": "full_arch_first",
                        "match": {"extent": "full_arch"},
                        "max_options": 2,
                        "offer_priorities": {
                            "brand_a_fixed": 100,
                            "brand_b_range": 90,
                        },
                    }
                ],
            },
            "marketing": {
                "version": 1,
                "limits": {
                    "max_marketing_facts_per_turn": 2,
                    "max_amplifiers_per_turn": 1,
                    "max_scenarios_per_turn": 1,
                },
                "initial_commercial_blocks": {
                    "service_one": {"ordered_fact_refs": ["fact:initial_fact"]}
                },
                "scenario_rules": {
                    "cost": {
                        "ordered_amplifier_refs": ["kb:cost.md#value"],
                        "allowed_semantic_contexts": ["price"],
                    }
                },
                "cta_contexts": {
                    "service": "consultation",
                    "price": "price_consultation",
                    "default": "callback",
                },
            },
        }
    )


def _doctors() -> TargetDoctorCatalog:
    return TargetDoctorCatalog.model_validate(
        {
            "doctors": {
                "doctor_z": {
                    "name": "Doctor Z",
                    "position": "Implantologist",
                    "experience_years": 18,
                    "service_ids": ["service_one"],
                    "profile_ref": "kb:doctor_z.md#profile",
                },
                "doctor_a": {
                    "name": "Doctor A",
                    "position": "Dentist",
                    "experience_years": 11,
                    "service_ids": ["service_one"],
                    "profile_ref": "kb:doctor_a.md#profile",
                },
            }
        }
    )


def _index() -> ResponseSchemaExternalIndex:
    return ResponseSchemaExternalIndex(
        kb_refs=("kb:cost.md#value",),
        doctor_refs=("doctor:doctor_z", "doctor:doctor_a"),
    )


def _consultations() -> tuple[ServiceConsultationValue, ...]:
    return (
        ServiceConsultationValue(
            content_ref="service_one.md",
            value="The consultation checks whether this service fits.",
        ),
    )


def _assemble(
    bundle: ResponseSchemaBundle | None = None,
    **overrides: object,
) -> TargetOfflineResponseMaterials:
    bundle = bundle or _bundle()
    params: dict[str, object] = {
        "service_term": "one",
        "brand_term": None,
        "strategy_context": TargetStrategyMatch(),
        "semantic_context": "service",
        "today": TODAY,
        "include_initial_block": False,
        "include_consultation_close": True,
    }
    params.update(overrides)
    return assemble_target_offline_response_materials(
        bundle,
        _doctors(),
        _index(),
        _consultations(),
        **params,  # type: ignore[arg-type]
    )


def test_exact_flat_shape_hides_unprojected_context_and_keeps_doctor_order() -> None:
    result = _assemble(strategy_context=TargetStrategyMatch(extent="full_arch"))

    assert [field.name for field in fields(TargetOfflineResponseMaterials)] == [
        "service_id",
        "service",
        "selected_brand_id",
        "brand",
        "matched_rule_id",
        "max_options",
        "offers",
        "doctors",
        "selected_content_ref",
        "marketing_selection",
        "commercial_facts",
        "external_source_refs",
        "consultation_close",
        "marketing_slots_used",
        "amplifier_slots_used",
    ]
    assert result.service_id == "service_one"
    assert result.selected_content_ref == "service_one.md"
    assert result.matched_rule_id == "full_arch_first"
    assert result.max_options == 2
    assert [offer.offer_id for offer in result.offers] == [
        "brand_a_fixed",
        "brand_b_range",
    ]
    assert [doctor.doctor_id for doctor in result.doctors] == ["doctor_z", "doctor_a"]
    assert result.consultation_close is not None
    assert not hasattr(result, "service_context")
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        result.max_options = 9  # type: ignore[misc]


@pytest.mark.parametrize("brand_term", ["brand_a", "Brand A", "a"])
def test_exact_brand_terms_keep_only_that_brand_and_preserve_stages(
    brand_term: str,
) -> None:
    result = _assemble(brand_term=brand_term)

    assert result.selected_brand_id == "brand_a"
    assert result.brand is not None
    assert result.brand.canonical_name == "Brand A"
    assert [offer.offer_id for offer in result.offers] == ["brand_a_fixed"]
    assert [stage.amount for stage in result.offers[0].payment_stages or []] == [
        70_000,
        50_000,
    ]
    assert [followup.id for followup in result.offers[0].followups] == [
        "stages",
        "includes",
    ]


def test_no_brand_keeps_eligible_multi_brand_and_generic_priority() -> None:
    result = _assemble()

    assert result.selected_brand_id is None
    assert result.brand is None
    assert [offer.offer_id for offer in result.offers] == [
        "brand_b_range",
        "generic_from",
        "brand_a_fixed",
    ]
    assert "brand_a_inactive" not in {offer.offer_id for offer in result.offers}


def test_known_brand_without_service_offer_is_empty_without_fallback() -> None:
    result = _assemble(brand_term="unused")

    assert result.selected_brand_id == "brand_unused"
    assert result.offers == ()


def test_marketing_materials_and_shown_state_pass_through_exactly() -> None:
    result = _assemble(
        semantic_context="price",
        include_initial_block=True,
        marketing_scenarios=["cost"],
        shown_fact_ids=["initial_fact"],
    )

    assert result.marketing_selection.applied_scenarios == ("cost",)
    assert result.marketing_selection.selected_refs == ("kb:cost.md#value",)
    assert result.marketing_selection.amplifier_refs == ("kb:cost.md#value",)
    assert result.marketing_selection.cta_key == "price_consultation"
    assert result.commercial_facts == ()
    assert result.external_source_refs == ("kb:cost.md#value",)
    assert result.consultation_close is None
    assert (result.marketing_slots_used, result.amplifier_slots_used) == (1, 1)


def test_service_errors_and_not_found_precede_brand_and_evidence() -> None:
    with pytest.raises(TargetServiceResolutionError) as invalid:
        _assemble(service_term="", brand_term="", semantic_context="")
    assert invalid.value.code == "service_resolution_term_invalid"

    with pytest.raises(TargetServiceResolutionError) as ambiguous:
        _assemble(
            _bundle(ambiguous_service=True),
            service_term="one",
            brand_term="",
            semantic_context="",
        )
    assert ambiguous.value.code == "service_resolution_ambiguous"

    with pytest.raises(TargetOfflineResponseAssemblyError) as missing:
        _assemble(service_term="missing", brand_term="", semantic_context="")
    assert missing.value.code == "offline_assembly_service_not_found"
    assert missing.value.value == "missing"
    assert str(missing.value) == "offline_assembly_service_not_found: 'missing'"


def test_brand_errors_and_not_found_precede_evidence_after_valid_service() -> None:
    with pytest.raises(TargetBrandResolutionError) as invalid:
        _assemble(brand_term="", semantic_context="")
    assert invalid.value.code == "brand_resolution_term_invalid"

    with pytest.raises(TargetBrandResolutionError) as ambiguous:
        _assemble(_bundle(ambiguous_brand=True), brand_term="same", semantic_context="")
    assert ambiguous.value.code == "brand_resolution_ambiguous"

    with pytest.raises(TargetOfflineResponseAssemblyError) as missing:
        _assemble(brand_term="missing", semantic_context="")
    assert missing.value.code == "offline_assembly_brand_not_found"
    assert missing.value.value == "missing"
    assert str(missing.value) == "offline_assembly_brand_not_found: 'missing'"


def test_s21_and_s22_errors_propagate_without_wrapping_or_message_changes() -> None:
    bundle = _bundle()
    with pytest.raises(TargetMarketingSelectionError) as direct_s21:
        select_target_marketing(
            bundle,
            _doctors(),
            _index(),
            semantic_context="",
            service_id="service_one",
            today=TODAY,
            include_initial_block=False,
        )
    with pytest.raises(TargetMarketingSelectionError) as assembled_s21:
        _assemble(bundle, semantic_context="")
    assert type(assembled_s21.value) is type(direct_s21.value)
    assert assembled_s21.value.code == direct_s21.value.code
    assert assembled_s21.value.value == direct_s21.value.value
    assert str(assembled_s21.value) == str(direct_s21.value)

    with pytest.raises(TargetResponseEvidencePackageError) as direct_s22:
        build_target_response_evidence_package(
            bundle,
            _doctors(),
            _index(),
            _consultations(),
            service_id="service_one",
            selected_content_ref="service_one.md",
            semantic_context="service",
            today=TODAY,
            include_initial_block=False,
            include_consultation_close=1,  # type: ignore[arg-type]
        )
    with pytest.raises(TargetResponseEvidencePackageError) as assembled_s22:
        _assemble(bundle, include_consultation_close=1)
    assert type(assembled_s22.value) is type(direct_s22.value)
    assert assembled_s22.value.code == direct_s22.value.code
    assert assembled_s22.value.value == direct_s22.value.value
    assert str(assembled_s22.value) == str(direct_s22.value)


def test_repeated_calls_are_stateless_detached_and_do_not_mutate_inputs() -> None:
    bundle = _bundle()
    before = bundle.model_dump()
    first = _assemble(bundle, brand_term="a")
    first.service.name = "Output only"
    assert first.brand is not None
    first.brand.canonical_name = "Output brand"
    first.offers[0].package.label = "Output package"
    second = _assemble(bundle, brand_term="a")

    assert second.service.name == "Service One"
    assert second.brand is not None and second.brand.canonical_name == "Brand A"
    assert second.offers[0].package.label == "Package brand_a_fixed"
    assert bundle.model_dump() == before


def test_exact_signature_error_codes_and_import_firewall() -> None:
    signature = inspect.signature(assemble_target_offline_response_materials)
    assert list(signature.parameters) == [
        "bundle",
        "doctor_catalog",
        "external_index",
        "consultation_values",
        "service_term",
        "brand_term",
        "strategy_context",
        "semantic_context",
        "today",
        "include_initial_block",
        "include_consultation_close",
        "marketing_scenarios",
        "shown_fact_ids",
        "shown_amplifier_refs",
        "shown_consultation_value_refs",
    ]
    source_path = Path("core/target_offline_response_assembly.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    assembly_codes = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith("offline_assembly_")
    }
    assert assembly_codes == {
        "offline_assembly_service_not_found",
        "offline_assembly_brand_not_found",
    }
    assert not any(isinstance(node, ast.Try) for node in ast.walk(tree))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert imported_modules <= {
        "__future__",
        "collections.abc",
        "dataclasses",
        "datetime",
        "contracts.doctor_schema",
        "contracts.response_schema",
        "contracts.response_schema_refs",
        "contracts.service_consultation",
        "core.service_data_context",
        "core.target_brand_offer_projection",
        "core.target_brand_resolver",
        "core.target_marketing_selector",
        "core.target_offer_projection",
        "core.target_response_evidence",
        "core.target_service_resolver",
    }
