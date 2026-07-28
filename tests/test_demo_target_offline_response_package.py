from __future__ import annotations

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
from core.target_offline_response_package import assemble_target_offline_response_package


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"


def _real_inputs() -> dict[str, object]:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")
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
    return {
        "bundle": bundle,
        "doctor_catalog": doctors,
        "external_index": external_index,
        "consultation_values": consultations,
        "service_term": "All-on-4",
        "brand_term": None,
        "strategy_context": TargetStrategyMatch(
            family="implantology",
            extent="full_arch",
        ),
        "semantic_context": "service",
        "today": date(2026, 7, 22),
        "include_initial_block": False,
        "include_consultation_close": True,
        "required_components": ("content", "price", "doctors"),
        "followup_source": "content",
        "md_root": MD_ROOT,
    }


def _package(**overrides: object):
    inputs = _real_inputs()
    inputs.update(overrides)
    return assemble_target_offline_response_package(**inputs)  # type: ignore[arg-type]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_all_on_4_content_package_is_coherent_end_to_end() -> None:
    result = _package()
    assert result.materials.service_id == "all_on_4"
    assert result.plan.service_id == result.materials.service_id
    assert result.plan.required_components == ("content", "price", "doctors")
    assert result.plan.unfulfilled_components == ()
    assert result.plan.offer_ids == tuple(
        offer.offer_id for offer in result.materials.offers
    )
    assert result.plan.doctor_ids == tuple(
        doctor.doctor_id for doctor in result.materials.doctors
    )
    assert [item.id for item in result.followup_candidates.content] == [
        "komu-podhodit-all-on-4",
        "kak-rabotaet-metod-all-on-4",
        "ogranicheniya-i-uhod",
    ]
    assert result.selected_followups.source == "content"
    assert result.selected_followups.content is result.followup_candidates.content
    assert result.selected_followups.price == ()


def test_real_all_on_4_price_and_none_followup_focus() -> None:
    price = _package(followup_source="price")
    assert [item.id for item in price.followup_candidates.price] == [
        "stages",
        "includes",
    ]
    assert price.selected_followups.source == "price"
    assert price.selected_followups.price == price.followup_candidates.price
    assert price.selected_followups.content == ()

    none = _package(followup_source=None)
    assert none.selected_followups.source is None
    assert none.selected_followups.content == ()
    assert none.selected_followups.price == ()


def test_real_unfulfilled_price_has_no_followup_fallback() -> None:
    result = _package(
        service_term="caries",
        brand_term="nobel",
        strategy_context=TargetStrategyMatch(family="therapy"),
        required_components=("price",),
        followup_source="price",
    )
    assert result.plan.unfulfilled_components == ("price",)
    assert result.followup_candidates.content == ()
    assert result.followup_candidates.price == ()
    assert result.selected_followups.source is None
    assert result.selected_followups.content == ()
    assert result.selected_followups.price == ()


def test_real_package_does_not_write_demo_files() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}
    _package()
    assert {path: _sha256(path) for path in paths} == before
