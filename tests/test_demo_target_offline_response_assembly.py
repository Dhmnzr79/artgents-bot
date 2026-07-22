from __future__ import annotations

import ast
import hashlib
from datetime import date
from pathlib import Path

import pytest

from contracts.doctor_schema_refs import (
    DoctorCatalogExternalIndex,
    build_doctor_source_refs,
    validate_doctor_catalog_external_refs,
)
from contracts.response_schema import TargetStrategyMatch
from contracts.response_schema_refs import (
    ResponseSchemaExternalIndex,
    validate_response_schema_external_refs,
)
from contracts.service_consultation import validate_service_consultation_refs
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.response_schema_loader import load_response_schema_bundle
from core.service_consultation_source import build_service_consultation_values
from core.target_offline_response_assembly import (
    TargetOfflineResponseAssemblyError,
    assemble_target_offline_response_materials,
)


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"
DOCTOR_CATALOG_PATH = DEMO_ROOT / "doctor_catalog.json"
TODAY = date(2026, 7, 22)
ALL_ON_4_CONTENT_REF = "implantation__service__all_on_4.md"


def _real_inputs():
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DOCTOR_CATALOG_PATH)
    kb_refs = build_response_schema_kb_refs(MD_ROOT)
    doctor_index = DoctorCatalogExternalIndex(
        service_ids=tuple(bundle.services),
        kb_refs=kb_refs,
    )
    assert validate_doctor_catalog_external_refs(doctors, doctor_index) is None
    external_index = ResponseSchemaExternalIndex(
        kb_refs=kb_refs,
        doctor_refs=build_doctor_source_refs(doctors),
    )
    assert validate_response_schema_external_refs(bundle, external_index) is None
    consultations = build_service_consultation_values(MD_ROOT)
    assert validate_service_consultation_refs(consultations, bundle.services) is None
    return bundle, doctors, external_index, consultations


def _assemble(service_term: str = "All-on-4", **overrides: object):
    bundle, doctors, external_index, consultations = _real_inputs()
    params: dict[str, object] = {
        "service_term": service_term,
        "brand_term": None,
        "strategy_context": TargetStrategyMatch(
            family="implantology",
            extent="full_arch",
        ),
        "semantic_context": "service",
        "today": TODAY,
        "include_initial_block": False,
        "include_consultation_close": True,
    }
    params.update(overrides)
    result = assemble_target_offline_response_materials(
        bundle,
        doctors,
        external_index,
        consultations,
        **params,  # type: ignore[arg-type]
    )
    return bundle, doctors, consultations, result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_all_on_4_vertical_materials_are_projected_and_linked() -> None:
    bundle, doctors, consultations, result = _assemble()

    assert result.service_id == "all_on_4"
    assert result.service.content_ref == ALL_ON_4_CONTENT_REF
    assert result.selected_content_ref == ALL_ON_4_CONTENT_REF
    assert result.matched_rule_id == "full_arch_restore"
    assert result.max_options == 3
    assert [offer.offer_id for offer in result.offers] == [
        "all_on_4.jaw.impro",
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.nobel",
    ]
    assert [offer.price.amount for offer in result.offers] == [  # type: ignore[union-attr]
        368_000,
        318_000,
        428_000,
    ]
    assert [doctor.doctor_id for doctor in result.doctors] == [
        "doctors__doctor__kuznetsov",
        "doctors__doctor__orlov",
        "doctors__doctor__volkov",
    ]
    assert all(
        "all_on_4" in doctors.doctors[doctor.doctor_id].service_ids
        for doctor in result.doctors
    )
    assert result.consultation_close is not None
    source_close = next(
        record for record in consultations if record.content_ref == ALL_ON_4_CONTENT_REF
    )
    assert result.consultation_close.model_dump() == source_close.model_dump()
    assert result.consultation_close is not source_close
    assert (result.marketing_slots_used, result.amplifier_slots_used) == (1, 1)
    assert result.service is not bundle.services["all_on_4"]


def test_real_nobel_term_returns_only_exact_offer_money_package_and_stages() -> None:
    _bundle, _doctors, _consultations, result = _assemble(brand_term="нобель")

    assert result.selected_brand_id == "nobel_biocare"
    assert result.brand is not None
    assert result.brand.canonical_name == "Nobel Biocare"
    assert [offer.offer_id for offer in result.offers] == ["all_on_4.jaw.nobel"]
    nobel = result.offers[0]
    assert nobel.price.amount == 428_000  # type: ignore[union-attr]
    assert nobel.price.currency == "RUB"  # type: ignore[union-attr]
    assert nobel.price.billing_unit == "jaw"  # type: ignore[union-attr]
    assert len(nobel.package.includes) == 5
    assert [stage.amount for stage in nobel.payment_stages or []] == [256_800, 171_200]
    assert [followup.id for followup in nobel.followups] == ["stages", "includes"]


def test_real_cost_marketing_fills_limits_and_suppresses_consultation() -> None:
    _bundle, _doctors, _consultations, result = _assemble(
        semantic_context="price",
        include_initial_block=True,
        marketing_scenarios=["cost"],
    )

    assert result.marketing_selection.selected_refs == (
        "fact:installment_12",
        "fact:implant_same_day_discount",
    )
    assert result.marketing_selection.amplifier_refs == (
        "fact:installment_12",
        "fact:implant_same_day_discount",
    )
    assert [fact.id for fact in result.commercial_facts] == [
        "installment_12",
        "implant_same_day_discount",
    ]
    assert result.external_source_refs == ()
    assert result.consultation_close is None
    assert (result.marketing_slots_used, result.amplifier_slots_used) == (2, 2)


def test_real_doctor_trust_keeps_exact_refs_and_fact_without_ranking() -> None:
    _bundle, _doctors, _consultations, result = _assemble(
        include_initial_block=True,
        marketing_scenarios=["doctor_trust"],
    )

    assert result.marketing_selection.selected_refs == (
        "doctor:doctors__doctor__volkov",
        "doctor:doctors__doctor__orlov",
        "fact:free_implant_consult",
    )
    assert result.external_source_refs == (
        "doctor:doctors__doctor__volkov",
        "doctor:doctors__doctor__orlov",
    )
    assert [fact.id for fact in result.commercial_facts] == ["free_implant_consult"]
    assert [doctor.doctor_id for doctor in result.doctors] == [
        "doctors__doctor__kuznetsov",
        "doctors__doctor__orlov",
        "doctors__doctor__volkov",
    ]
    assert result.consultation_close is None


def test_real_caries_generic_offer_and_brand_empty_path_are_exact() -> None:
    _bundle, _doctors, _consultations, generic = _assemble(
        "caries",
        strategy_context=TargetStrategyMatch(family="therapy"),
    )
    assert generic.service_id == "caries"
    assert generic.selected_content_ref == "treatment__service__caries.md"
    assert [offer.offer_id for offer in generic.offers] == ["caries.default"]
    assert generic.offers[0].brand_id is None
    assert generic.offers[0].price.mode == "from"
    assert generic.offers[0].price.min_amount == 6_500  # type: ignore[union-attr]
    assert [doctor.doctor_id for doctor in generic.doctors] == [
        "doctors__doctor__fedorova"
    ]

    _bundle, _doctors, _consultations, branded = _assemble(
        "caries",
        brand_term="nobel",
        strategy_context=TargetStrategyMatch(family="therapy"),
    )
    assert branded.selected_brand_id == "nobel_biocare"
    assert branded.offers == ()


def test_real_unknown_terms_fail_closed_and_assembly_is_read_only_unwired() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}

    with pytest.raises(TargetOfflineResponseAssemblyError) as service_exc:
        _assemble("not a demo service", brand_term="nobel")
    assert service_exc.value.code == "offline_assembly_service_not_found"

    with pytest.raises(TargetOfflineResponseAssemblyError) as brand_exc:
        _assemble(brand_term="not a demo brand")
    assert brand_exc.value.code == "offline_assembly_brand_not_found"

    assert {path: _sha256(path) for path in paths} == before
    tree = ast.parse(
        Path("core/target_offline_response_assembly.py").read_text(encoding="utf-8")
    )
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not any(
        module.startswith(
            ("app", "config", "handlers", "orchestration", "routes", "telegram")
        )
        for module in imported_modules
    )
    assert not (
        {"write_text", "write_bytes", "unlink", "rename", "replace", "mkdir"}
        & called_attributes
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"skip", "skipif", "xfail"}
        for node in ast.walk(tree)
    )
