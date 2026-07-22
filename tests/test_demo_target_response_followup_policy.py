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
from core.target_offline_response_assembly import assemble_target_offline_response_materials
from core.target_response_followup_materializer import materialize_target_response_followups
from core.target_response_followup_policy import select_target_response_followups
from core.target_response_materialization_plan import (
    build_target_response_materialization_plan,
)


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"


def _real_followups():
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
    materials = assemble_target_offline_response_materials(
        bundle,
        doctors,
        external_index,
        consultations,
        service_term="All-on-4",
        brand_term=None,
        strategy_context=TargetStrategyMatch(
            family="implantology",
            extent="full_arch",
        ),
        semantic_context="service",
        today=date(2026, 7, 22),
        include_initial_block=False,
        include_consultation_close=True,
    )
    plan = build_target_response_materialization_plan(
        materials,
        required_components=("content", "price"),
    )
    return materialize_target_response_followups(plan, materials, md_root=MD_ROOT)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_all_on_4_content_exposes_only_authored_document_links() -> None:
    followups = _real_followups()
    result = select_target_response_followups(followups, source="content")
    assert result.source == "content"
    assert [item.id for item in result.content] == [
        "komu-podhodit-all-on-4",
        "kak-rabotaet-metod-all-on-4",
        "ogranicheniya-i-uhod",
    ]
    assert result.content is followups.content
    assert result.price == ()


def test_real_all_on_4_price_exposes_only_price_links() -> None:
    followups = _real_followups()
    result = select_target_response_followups(followups, source="price")
    assert result.source == "price"
    assert [item.id for item in result.price] == ["stages", "includes"]
    assert result.price is followups.price
    assert result.content == ()


def test_real_none_exposes_nothing_and_demo_files_are_unchanged() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}
    followups = _real_followups()
    result = select_target_response_followups(followups, source=None)
    assert result.source is None
    assert result.content == ()
    assert result.price == ()
    assert {path: _sha256(path) for path in paths} == before
