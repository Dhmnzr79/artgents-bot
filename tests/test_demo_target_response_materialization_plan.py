from __future__ import annotations

import ast
import hashlib
from datetime import date
from pathlib import Path

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
from core.target_offline_response_assembly import assemble_target_offline_response_materials
from core.target_response_materialization_plan import (
    build_target_response_materialization_plan,
)


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"
DOCTOR_CATALOG_PATH = DEMO_ROOT / "doctor_catalog.json"
TODAY = date(2026, 7, 22)


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


def _materials(service_term: str = "All-on-4", **overrides: object):
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
        "turn_topic": "implantation",
    }
    params.update(overrides)
    return assemble_target_offline_response_materials(
        bundle,
        doctors,
        external_index,
        consultations,
        **params,  # type: ignore[arg-type]
    )


def _plan(
    service_term: str = "All-on-4",
    *,
    components: tuple[str, ...],
    **overrides: object,
):
    return build_target_response_materialization_plan(
        _materials(service_term, **overrides),
        required_components=components,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_content_only_plan_points_to_exact_md_without_price_or_doctors() -> None:
    plan = _plan(components=("content",))

    assert plan.service_id == "all_on_4"
    assert plan.required_components == ("content",)
    assert plan.unfulfilled_components == ()
    assert plan.primary_content_ref == "implantation__service__all_on_4.md"
    assert plan.offer_ids == ()
    assert plan.doctor_ids == ()
    assert plan.consultation_content_ref == "implantation__service__all_on_4.md"
    assert plan.cta_key == "plan"


def test_real_all_on_4_price_and_doctors_keep_exact_s27_orders() -> None:
    plan = _plan(components=("price", "doctors"))

    assert plan.required_components == ("price", "doctors")
    assert plan.unfulfilled_components == ()
    assert plan.offer_ids == (
        "all_on_4.jaw.impro",
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.nobel",
    )
    assert plan.doctor_ids == (
        "doctors__doctor__kuznetsov",
        "doctors__doctor__orlov",
        "doctors__doctor__volkov",
    )
    assert plan.primary_content_ref is None


def test_real_nobel_price_plan_contains_only_exact_nobel_offer() -> None:
    plan = _plan(components=("price",), brand_term="нобель")

    assert plan.selected_brand_id == "nobel_biocare"
    assert plan.offer_ids == ("all_on_4.jaw.nobel",)
    assert plan.unfulfilled_components == ()


def test_real_caries_content_price_and_nobel_gap_are_fail_closed() -> None:
    exact = _plan(
        "caries",
        components=("content", "price"),
        strategy_context=TargetStrategyMatch(family="therapy"),
    )
    assert exact.primary_content_ref == "treatment__service__caries.md"
    assert exact.offer_ids == ("caries.default",)
    assert exact.unfulfilled_components == ()

    nobel = _plan(
        "caries",
        components=("price",),
        brand_term="nobel",
        strategy_context=TargetStrategyMatch(family="therapy"),
    )
    assert nobel.selected_brand_id == "nobel_biocare"
    assert nobel.offer_ids == ()
    assert nobel.unfulfilled_components == ("price",)


def test_real_cost_and_doctor_trust_identities_pass_without_reselection() -> None:
    cost = _plan(
        components=("price",),
        semantic_context="price",
        include_initial_block=True,
        marketing_scenarios=["cost"],
    )
    assert cost.commercial_fact_ids == (
        "installment_12",
        "implant_same_day_discount",
    )
    assert cost.external_source_refs == ()
    assert cost.consultation_content_ref is None
    assert cost.cta_key == "price"

    trust = _plan(
        components=("doctors",),
        include_initial_block=True,
        marketing_scenarios=["doctor_trust"],
    )
    assert trust.commercial_fact_ids == ("free_implant_consult",)
    assert trust.external_source_refs == (
        "doctor:doctors__doctor__volkov",
        "doctor:doctors__doctor__orlov",
    )
    assert trust.consultation_content_ref is None
    assert trust.cta_key == "plan"


def test_real_plan_build_is_read_only_and_has_no_product_or_ui_wiring() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}

    _plan(components=("content", "price", "doctors"))

    assert {path: _sha256(path) for path in paths} == before
    tree = ast.parse(
        Path("core/target_response_materialization_plan.py").read_text(
            encoding="utf-8"
        )
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
            (
                "app",
                "config",
                "handlers",
                "orchestration",
                "routes",
                "telegram",
                "core.answer_packet",
                "core.md_chunks",
            )
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
