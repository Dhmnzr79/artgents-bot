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
from contracts.response_schema_refs import (
    ResponseSchemaExternalIndex,
    validate_response_schema_external_refs,
)
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.response_schema_loader import load_response_schema_bundle
from core.target_marketing_selector import select_target_marketing


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"
DOCTOR_CATALOG_PATH = DEMO_ROOT / "doctor_catalog.json"
TODAY = date(2026, 7, 21)


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
    return bundle, doctors, external_index


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_all_on_4_cost_price_context_uses_exact_pool_without_service_fallback() -> None:
    bundle, doctors, index = _real_inputs()

    result = select_target_marketing(
        bundle,
        doctors,
        index,
        semantic_context="price",
        service_id="all_on_4",
        today=TODAY,
        include_initial_block=True,
        marketing_scenarios=["cost"],
        turn_topic="implantation",
    )

    assert result.applied_scenarios == ("cost",)
    assert result.selected_refs == result.amplifier_refs == (
        "fact:installment_12",
        "fact:implant_same_day_discount",
    )
    assert result.cta_key == "price"
    assert "fact:free_implant_consult" not in result.selected_refs


def test_all_on_4_cost_service_context_fills_exact_service_block() -> None:
    bundle, doctors, index = _real_inputs()

    result = select_target_marketing(
        bundle,
        doctors,
        index,
        semantic_context="service",
        service_id="all_on_4",
        today=TODAY,
        include_initial_block=True,
        marketing_scenarios=["cost"],
        turn_topic="implantation",
    )

    assert result.selected_refs == (
        "fact:installment_12",
        "fact:implant_same_day_discount",
        "fact:free_implant_consult",
    )
    assert result.amplifier_refs == (
        "fact:installment_12",
        "fact:implant_same_day_discount",
    )
    assert result.cta_key == "plan"


def test_professional_whitening_initial_keeps_only_applicable_discount() -> None:
    bundle, doctors, index = _real_inputs()

    result = select_target_marketing(
        bundle,
        doctors,
        index,
        semantic_context="service",
        service_id="professional_whitening",
        today=TODAY,
        include_initial_block=True,
    )

    assert result.applied_scenarios == ()
    assert result.selected_refs == ("fact:professional_whitening_discount",)
    assert result.amplifier_refs == ()
    assert result.cta_key == "plan"


def test_service_doctor_trust_filters_unlinked_doctors_but_keeps_exact_sources() -> None:
    bundle, doctors, index = _real_inputs()

    result = select_target_marketing(
        bundle,
        doctors,
        index,
        semantic_context="service",
        service_id="professional_whitening",
        today=TODAY,
        include_initial_block=True,
        marketing_scenarios=["doctor_trust"],
        turn_topic="implantation",
    )

    assert result.amplifier_refs == (
        "kb:doctors__doctor__overview.md#korotko",
        "kb:clinic__info__technology.md#korotko",
    )
    assert result.selected_refs == (
        *result.amplifier_refs,
        "fact:professional_whitening_discount",
    )
    assert not any(ref.startswith("doctor:") for ref in result.selected_refs)


def test_general_doctors_context_allows_exact_doctor_refs_and_doctor_cta() -> None:
    bundle, doctors, index = _real_inputs()

    result = select_target_marketing(
        bundle,
        doctors,
        index,
        semantic_context="doctors",
        service_id=None,
        today=TODAY,
        include_initial_block=False,
        marketing_scenarios=["doctor_trust"],
        turn_topic="doctors",
    )

    assert result.selected_refs == result.amplifier_refs == (
        "doctor:doctors__doctor__volkov",
        "doctor:doctors__doctor__orlov",
    )
    assert result.cta_key == "doctor"


def test_shown_snapshots_and_explicit_date_change_only_exact_candidates() -> None:
    bundle, doctors, index = _real_inputs()

    cost = select_target_marketing(
        bundle,
        doctors,
        index,
        semantic_context="price",
        service_id="all_on_4",
        today=TODAY,
        include_initial_block=True,
        marketing_scenarios=["cost"],
        turn_topic="implantation",
        shown_fact_ids=["installment_12"],
        shown_amplifier_refs=["fact:implant_same_day_discount"],
    )
    expired_whitening = select_target_marketing(
        bundle,
        doctors,
        index,
        semantic_context="service",
        service_id="professional_whitening",
        today=date(2026, 8, 16),
        include_initial_block=True,
    )

    assert cost.selected_refs == cost.amplifier_refs == (
        "fact:tax_deduction",
        "kb:implantation__faq__cost.md#kak-sdelat-implantatsiyu-dostupnee",
    )
    assert expired_whitening.selected_refs == ()


def test_real_selection_is_read_only_and_acceptance_has_no_product_wiring() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}
    bundle, doctors, index = _real_inputs()

    select_target_marketing(
        bundle,
        doctors,
        index,
        semantic_context="service",
        service_id="all_on_4",
        today=TODAY,
        include_initial_block=True,
        marketing_scenarios=["pain_fear", "cost"],
        turn_topic="implantation",
    )

    assert {path: _sha256(path) for path in paths} == before

    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
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
