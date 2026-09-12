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
from contracts.service_consultation import validate_service_consultation_refs
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.response_schema_loader import load_response_schema_bundle
from core.service_consultation_source import build_service_consultation_values
from core.target_response_evidence import build_target_response_evidence_package


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"
DOCTOR_CATALOG_PATH = DEMO_ROOT / "doctor_catalog.json"
TODAY = date(2026, 7, 21)
ALL_ON_4_CONTENT_REF = "implantation__service__all_on_4.md"
ALL_ON_4_CONSULTATION_VALUE = (
    "На консультации врач оценит КТ и поможет понять, подходит ли протокол "
    "All-on-4 или лучше рассмотреть другой вариант восстановления."
)


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


def _build(**overrides: object):
    bundle, doctors, index, consultations = _real_inputs()
    params: dict[str, object] = {
        "service_id": "all_on_4",
        "selected_content_ref": ALL_ON_4_CONTENT_REF,
        "semantic_context": "service",
        "today": TODAY,
        "include_initial_block": False,
        "include_consultation_close": True,
        "turn_topic": "implantation",
    }
    params.update(overrides)
    result = build_target_response_evidence_package(
        bundle,
        doctors,
        index,
        consultations,
        **params,  # type: ignore[arg-type]
    )
    return bundle, doctors, consultations, result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_all_on_4_package_links_service_all_offers_doctors_and_close() -> None:
    bundle, doctors, consultations, result = _build()

    assert result.service_context.service_id == "all_on_4"
    assert result.service_context.service.content_ref == ALL_ON_4_CONTENT_REF
    assert [offer.offer_id for offer in result.service_context.offers] == [
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.impro",
        "all_on_4.jaw.nobel",
    ]
    assert [offer.price.amount for offer in result.service_context.offers] == [
        318_000,
        368_000,
        428_000,
    ]
    assert [doctor.doctor_id for doctor in result.service_context.doctors] == [
        "doctors__doctor__kuznetsov",
        "doctors__doctor__orlov",
        "doctors__doctor__volkov",
    ]
    assert all(
        "all_on_4" in doctors.doctors[doctor.doctor_id].service_ids
        for doctor in result.service_context.doctors
    )
    assert result.consultation_close is not None
    assert result.consultation_close.content_ref == ALL_ON_4_CONTENT_REF
    assert result.consultation_close.value == ALL_ON_4_CONSULTATION_VALUE
    assert result.consultation_close in consultations
    assert result.consultation_close is not next(
        record
        for record in consultations
        if record.content_ref == ALL_ON_4_CONTENT_REF
    )
    assert (result.marketing_slots_used, result.amplifier_slots_used) == (1, 1)
    assert result.service_context.service is not bundle.services["all_on_4"]


def test_real_shown_consultation_ref_suppresses_close_without_replacement() -> None:
    _bundle, _doctors, _consultations, result = _build(
        shown_consultation_value_refs=[ALL_ON_4_CONTENT_REF]
    )

    assert result.selected_content_ref == ALL_ON_4_CONTENT_REF
    assert result.consultation_close is None
    assert (result.marketing_slots_used, result.amplifier_slots_used) == (0, 0)


def test_real_cost_price_fills_amplifier_limit_and_blocks_consultation_close() -> None:
    _bundle, _doctors, _consultations, result = _build(
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


def test_real_doctor_trust_materializes_exact_external_refs_and_initial_fact() -> None:
    bundle, _doctors, _consultations, result = _build(
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
    assert [fact.id for fact in result.commercial_facts] == [
        "free_implant_consult"
    ]
    assert result.commercial_facts[0] is not bundle.facts["free_implant_consult"]
    assert result.consultation_close is None
    assert (result.marketing_slots_used, result.amplifier_slots_used) == (3, 2)


def test_real_assembly_is_read_only_and_has_no_product_wiring() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}

    _build(marketing_scenarios=["cost"])

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
