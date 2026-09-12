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
from core.target_response_followup_materializer import materialize_target_response_followups
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
    }
    params.update(overrides)
    return assemble_target_offline_response_materials(
        bundle,
        doctors,
        external_index,
        consultations,
        **params,  # type: ignore[arg-type]
    )


def _followups(
    service_term: str = "All-on-4",
    *,
    components: tuple[str, ...],
    md_root: Path = MD_ROOT,
    **overrides: object,
):
    materials = _materials(service_term, **overrides)
    plan = build_target_response_materialization_plan(
        materials,
        required_components=components,
    )
    result = materialize_target_response_followups(
        plan,
        materials,
        md_root=md_root,
    )
    return plan, materials, result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_all_on_4_content_uses_exact_authored_suggestions() -> None:
    _plan, _materials_result, result = _followups(components=("content",))

    assert [(item.id, item.label, item.ref) for item in result.content] == [
        (
            "komu-podhodit-all-on-4",
            "Кому подходит All-on-4",
            "implantation__service__all_on_4.md#komu-podhodit-all-on-4",
        ),
        (
            "kak-rabotaet-metod-all-on-4",
            "Как работает метод All-on-4",
            "implantation__service__all_on_4.md#kak-rabotaet-metod-all-on-4",
        ),
        (
            "ogranicheniya-i-uhod",
            "Ограничения и уход",
            "implantation__service__all_on_4.md#ogranicheniya-i-uhod",
        ),
    ]
    assert result.price == ()


def test_real_caries_content_has_no_authored_suggestions() -> None:
    _plan, _materials_result, result = _followups(
        "caries",
        components=("content",),
        strategy_context=TargetStrategyMatch(family="therapy"),
    )
    assert result.content == ()
    assert result.price == ()


def test_real_all_on_4_price_aggregates_all_selected_offer_sources() -> None:
    _plan, materials, result = _followups(components=("price",))

    assert [offer.offer_id for offer in materials.offers] == [
        "all_on_4.jaw.impro",
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.nobel",
    ]
    assert [(item.id, item.label, item.ref) for item in result.price] == [
        ("stages", "Оплата по этапам", "price:all_on_4/stages"),
        ("includes", "Что входит", "price:all_on_4/includes"),
    ]
    expected_sources = tuple(offer.offer_id for offer in materials.offers)
    assert [item.source_offer_ids for item in result.price] == [
        expected_sources,
        expected_sources,
    ]
    assert result.content == ()


def test_real_nobel_price_sources_only_nobel() -> None:
    _plan, _materials_result, result = _followups(
        components=("price",),
        brand_term="нобель",
    )
    assert [item.id for item in result.price] == ["stages", "includes"]
    assert [item.source_offer_ids for item in result.price] == [
        ("all_on_4.jaw.nobel",),
        ("all_on_4.jaw.nobel",),
    ]


def test_real_caries_price_and_caries_nobel_have_no_followups() -> None:
    _plan, _materials_result, generic = _followups(
        "caries",
        components=("price",),
        strategy_context=TargetStrategyMatch(family="therapy"),
    )
    assert generic.price == ()

    plan, _materials_result, branded = _followups(
        "caries",
        components=("price",),
        brand_term="nobel",
        strategy_context=TargetStrategyMatch(family="therapy"),
    )
    assert plan.unfulfilled_components == ("price",)
    assert branded.price == ()


def test_real_price_only_does_not_read_md_and_demo_is_unchanged(tmp_path: Path) -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}

    _plan, _materials_result, result = _followups(
        components=("price",),
        md_root=tmp_path,
    )
    assert [item.id for item in result.price] == ["stages", "includes"]
    assert {path: _sha256(path) for path in paths} == before

    tree = ast.parse(
        Path("core/target_response_followup_materializer.py").read_text(encoding="utf-8")
    )
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(
        module.startswith(
            ("app", "config", "orchestration", "routes", "session", "core.md_chunks")
        )
        for module in imported_modules
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"skip", "skipif", "xfail"}
        for node in ast.walk(tree)
    )
