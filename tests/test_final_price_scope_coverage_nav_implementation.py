"""COMPLETION checker and acceptance A–J for FINAL_PRICE_SCOPE_COVERAGE_NAV."""

from __future__ import annotations

import ast
from pathlib import Path

from contracts.effective_scope import EffectiveScope
from contracts.ui_scope_action import build_ui_scope_ref
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.target_client_ui_nav import materialize_scope_nav_followups
from core.target_response_stage import derive_response_stage
from core.target_scope_aware_selection import run_target_scope_aware_selection
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
from tests.test_final_price_and_service_coverage_implementation import (
    test_acceptance_e_umbrella_family_only_no_scope_nav,
)
from tests.test_final_price_scope_coverage_nav_sparse_fixtures import (
    classic_one_tooth_only_pack,
    three_extent_routes_pack,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_ROOT = Path("clients/demo/target_response")
DOCTOR_CATALOG = Path("clients/demo/doctor_catalog.json")
GOVERNANCE_BASELINE = "031d766"


def test_implementation_artifacts_present() -> None:
    assert (_REPO_ROOT / "core" / "target_offer_extent_applicability.py").is_file()
    assert (_REPO_ROOT / "tests" / "test_final_price_scope_coverage_nav_sparse_fixtures.py").is_file()


def test_extent_module_has_no_topic_hardcode() -> None:
    source = (_REPO_ROOT / "core" / "target_offer_extent_applicability.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in {"implantation", "prosthetics", "classic", "all_on_4"}:
                raise AssertionError(f"hardcoded literal: {node.value!r}")


def test_frozen_pins_unchanged() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_acceptance_a_rich_demo_broad_two_confirmed_extents() -> None:
    test_broad_implantation_has_scope_nav_no_price_followups()


def test_acceptance_b_one_tooth_only_sparse(tmp_path) -> None:
    _root, bundle = classic_one_tooth_only_pack(tmp_path)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=EffectiveScope(),
        topic="implantation",
    )
    assert selection.price_confirmed_extents == ("one_tooth",)
    nav = materialize_scope_nav_followups(
        "demo",
        topic="implantation",
        confirmed_extents=selection.price_confirmed_extents,
    )
    assert len(nav) == 1
    assert nav[0].ref.endswith("/one_tooth")


def test_acceptance_c_three_extent_routes(tmp_path) -> None:
    _root, bundle = three_extent_routes_pack(tmp_path)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=EffectiveScope(),
        topic="implantation",
    )
    assert set(selection.price_confirmed_extents) == {
        "one_tooth",
        "few_teeth",
        "full_arch",
    }
    nav = materialize_scope_nav_followups(
        "demo",
        topic="implantation",
        confirmed_extents=selection.price_confirmed_extents,
    )
    assert len(nav) == 3


def test_acceptance_d_few_teeth_without_route_is_data_gap(tmp_path) -> None:
    _root, bundle = classic_one_tooth_only_pack(tmp_path)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    scope = EffectiveScope(
        extent="few_teeth",
        topic="implantation",
        source="session",
        provenance=build_ui_scope_ref(topic="implantation", extent="few_teeth"),
    )
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=scope,
        topic="implantation",
    )
    assert "classic" in selection.service_ids
    assert "classic" not in selection.offers_by_service_id
    stage = derive_response_stage(
        explicit_service_id=None,
        effective_scope=scope,
        topic="implantation",
        bundle=bundle,
        selection=selection,
    )
    assert stage == "data_gap"


def test_acceptance_e_one_tooth_scoped_unchanged() -> None:
    scope = EffectiveScope(
        extent="one_tooth",
        topic="implantation",
        source="session",
        provenance=build_ui_scope_ref(topic="implantation", extent="one_tooth"),
    )
    result = _run_family_price(user_message="продолжить", effective_scope=scope)
    assert result.verified.spec.response_stage in {
        "scoped_family_price",
        "concrete_service_price",
    }
    assert result.verified.navigation_followups == ()


def test_acceptance_f_family_only_broad_no_nav(tmp_path) -> None:
    test_acceptance_e_umbrella_family_only_no_scope_nav(tmp_path)


def test_acceptance_g_named_all_on_4_unchanged() -> None:
    test_named_service_all_on_4_unchanged()


def test_acceptance_h_broad_has_no_few_teeth_anchor_without_route() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=EffectiveScope(),
        topic="implantation",
    )
    anchor_extents = {anchor.extent for anchor in selection.anchors}
    assert "few_teeth" not in anchor_extents


def test_acceptance_i_http_parity_module_importable() -> None:
    import tests.test_ac3_scope_price_flow_http_offline as http_tests

    assert hasattr(http_tests, "test_http_ask_and_stream_scope_click_parity")
