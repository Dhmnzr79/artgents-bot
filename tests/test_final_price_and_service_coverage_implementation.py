"""COMPLETION checker and acceptance matrix A–L for FINAL_PRICE_AND_SERVICE_COVERAGE."""

from __future__ import annotations

import ast
from pathlib import Path

from contracts.effective_scope import EffectiveScope
from contracts.ui_scope_action import build_ui_scope_ref
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.target_family_price_resolution import (
    FAMILY_ONLY_BROAD_EXCLUSION,
    is_family_only_broad_mode,
    list_family_prices_for_topic,
)
from core.target_response_policy import (
    broad_family_price_directive_overlay,
    data_gap_protocol_unconfirmed_directive_overlay,
)
from core.target_response_stage import derive_response_stage
from core.target_scope_aware_price_package import assemble_scope_aware_price_package
from core.target_scope_aware_selection import run_target_scope_aware_selection
from core.target_strategy_context import strategy_match_from_effective_scope
from core.target_turn_frame_bound_response import run_target_offline_turn_frame_bound_response
from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from tests.test_ac3_scope_price_flow_offline import (
    _run_family_price,
    test_broad_implantation_has_scope_nav_no_price_followups,
    test_named_service_all_on_4_unchanged,
    test_w1b_snapshot_checksums_unchanged,
)
from tests.test_final_price_and_service_coverage_sparse_fixtures import (
    family_only_detailed_catalog_pack,
    service_specific_beats_family_pack,
    umbrella_family_only_pack,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)
from tests.test_w1_family_price_overview_offline import _family_overview_frame

_REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_ROOT = Path("clients/demo/target_response")
DOCTOR_CATALOG = Path("clients/demo/doctor_catalog.json")
GOVERNANCE_BASELINE = "bc4679b"
IMPLEMENTATION_BASELINE = "bc4679b"


def test_implementation_artifacts_present() -> None:
    assert (_REPO_ROOT / "core" / "target_family_price_resolution.py").is_file()
    assert (_REPO_ROOT / "tests" / "test_final_price_and_service_coverage_sparse_fixtures.py").is_file()
    assert not (
        _REPO_ROOT / "tests" / "test_final_price_and_service_coverage_existing_paths.py"
    ).exists()


def test_family_price_resolution_has_no_topic_hardcode() -> None:
    source = (_REPO_ROOT / "core" / "target_family_price_resolution.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            lowered = node.value.lower()
            if lowered in {"implantation", "prosthetics", "all_on_4", "all_on_6"}:
                raise AssertionError(f"hardcoded topic/service literal: {node.value!r}")


def test_frozen_pins_unchanged() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


# --- Acceptance A / K: rich demo unchanged ---


def test_acceptance_a_rich_demo_broad_family_price_unchanged() -> None:
    test_broad_implantation_has_scope_nav_no_price_followups()


def test_acceptance_k_rich_demo_named_service_unchanged() -> None:
    test_named_service_all_on_4_unchanged()


def test_acceptance_k_scoped_one_tooth_no_scope_nav() -> None:
    scope = EffectiveScope(
        extent="one_tooth",
        topic="implantation",
        source="session",
        provenance=build_ui_scope_ref(topic="implantation", extent="one_tooth"),
    )
    result = _run_family_price(user_message="продолжить", effective_scope=scope)
    assert result.verified.navigation_followups == ()
    assert result.verified.spec.response_stage in {"scoped_family_price", "concrete_service_price"}


# --- Acceptance B / C / D / E ---


def test_acceptance_b_service_specific_price_beats_family(tmp_path) -> None:
    _root, bundle = service_specific_beats_family_pack(tmp_path)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=EffectiveScope(),
        topic="implantation",
    )
    assert selection.kind == "broad_anchors"
    assert FAMILY_ONLY_BROAD_EXCLUSION not in selection.exclusions
    assert selection.anchors
    anchor_offer_ids = {anchor.offer_id for anchor in selection.anchors}
    assert "classic.default" in anchor_offer_ids


def test_acceptance_d_detailed_catalog_family_only_broad(tmp_path) -> None:
    _root, bundle = family_only_detailed_catalog_pack(tmp_path)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=EffectiveScope(),
        topic="implantation",
    )
    assert is_family_only_broad_mode(selection)
    assert len(selection.anchors) == 0
    assert len(selection.offers_by_service_id) == 1
    offer = next(iter(selection.offers_by_service_id.values()))[0]
    assert offer.offer_id.startswith("family_price:")
    assert offer.price.min_amount == 25000  # type: ignore[union-attr]


def test_acceptance_d_named_protocol_not_falsely_priced(tmp_path) -> None:
    _root, bundle = family_only_detailed_catalog_pack(tmp_path)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=EffectiveScope(extent="full_arch", topic="implantation", source="session", provenance="test"),
        topic="implantation",
        explicit_service_id="all_on_4",
    )
    assert "all_on_4" not in selection.offers_by_service_id
    stage = derive_response_stage(
        explicit_service_id="all_on_4",
        effective_scope=EffectiveScope(extent="full_arch", topic="implantation", source="session", provenance="test"),
        topic="implantation",
        bundle=bundle,
        selection=selection,
    )
    assert stage == "data_gap"


def test_acceptance_e_umbrella_family_only_no_scope_nav(tmp_path) -> None:
    _root, bundle = umbrella_family_only_pack(tmp_path)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    from contracts.target_response_spec import TargetResponseSpec
    from tests.test_demo_target_turn_frame_bound_response import _pipeline_inputs

    scope = EffectiveScope()
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=scope,
        topic="implantation",
    )
    assert is_family_only_broad_mode(selection)
    inputs = _pipeline_inputs()
    spec = TargetResponseSpec.model_validate(
        {
            "response_mode": "answer",
            "response_stage": "broad_family_price",
            "scope_price_topic": "implantation",
            "tone_key": "commercial_warm",
            "allowed_topics": ("implantation",),
            "required_components": ("price",),
            "allow_marketing_facts": False,
            "allow_cta": False,
        }
    )
    package = assemble_scope_aware_price_package(
        bundle,
        doctors,
        inputs["external_index"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        spec=spec,
        effective_scope=scope,
        strategy_context=strategy_match_from_effective_scope(scope),
        client_id="demo",
        md_root=inputs["md_root"],  # type: ignore[arg-type]
        semantic_context="implantation",
        today=inputs["today"],  # type: ignore[arg-type]
        include_initial_block=False,
        include_cta=False,
    )
    assert package.navigation_followups == ()
    assert len(package.materials.offers) == 1
    assert package.materials.offers[0].offer_id.startswith("family_price:")


def test_acceptance_e_umbrella_named_protocol_unconfirmed(tmp_path) -> None:
    _root, bundle = umbrella_family_only_pack(tmp_path)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=EffectiveScope(),
        topic="implantation",
        explicit_service_id="all_on_4",
    )
    assert selection.exclusions == ("no_applicable_services",)


# --- Acceptance J: /ask parity covered by existing harness; smoke import ---


def test_acceptance_j_http_parity_module_importable() -> None:
    import tests.test_ac3_scope_price_flow_http_offline as http_tests

    assert hasattr(http_tests, "test_http_ask_and_stream_scope_click_parity")


# --- Acceptance L: no price:None refs in family resolution ---


def test_acceptance_l_no_price_none_family_offer_ids(tmp_path) -> None:
    _root, bundle = family_only_detailed_catalog_pack(tmp_path)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=EffectiveScope(),
        topic="implantation",
    )
    for offer in selection.offers_by_service_id.values():
        for item in offer:
            assert item.offer_id
            assert not item.offer_id.startswith("price:None")


def test_policy_directives_for_family_only_and_protocol_gap() -> None:
    family_only = broad_family_price_directive_overlay("broad_family_price", family_only=True)
    assert family_only["family_only_broad_price"] is True
    assert family_only["max_price_anchors"] == 1
    assert family_only["include_scale_clarify"] is False
    gap = data_gap_protocol_unconfirmed_directive_overlay(
        "data_gap",
        protocol_unconfirmed=True,
    )
    assert gap["data_gap_protocol_unconfirmed"] is True


def test_demo_pack_has_no_family_prices_records() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    assert list_family_prices_for_topic(bundle, "implantation") == ()
