"""COMPLETION checker and acceptance 1–16 for FINAL_PROSTHETICS_PRICE_NAV_REACHABILITY."""

from __future__ import annotations

from pathlib import Path

import pytest

from contracts.effective_scope import EffectiveScope
from contracts.response_schema import TargetOffer, TargetService
from contracts.target_response_spec import TargetResponseSpec
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
from contracts.ui_scope_action import build_ui_scope_ref
from contracts.ui_stage_action import build_ui_stage_ref, is_ui_stage_ref
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.target_client_ui_nav import materialize_scope_nav_followups
from core.target_offer_extent_applicability import resolve_offer_applies_to_extents
from core.target_scope_aware_price_package import assemble_scope_aware_price_package
from core.target_scope_aware_selection import run_target_scope_aware_selection
from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from tests.test_ac3_scope_price_flow_http_offline import test_http_ask_and_stream_scope_click_parity
from core.target_strategy_context import strategy_match_from_effective_scope
from tests.test_ac3_scope_price_flow_offline import (
    _pipeline_inputs,
    _run_family_price,
    test_broad_implantation_has_scope_nav_no_price_followups,
    test_w1b_snapshot_checksums_unchanged,
)
from tests.test_final_price_scope_coverage_nav_implementation import (
    test_frozen_pins_unchanged as test_pscn_frozen_pins_unchanged,
)
from tests.test_final_prosthetics_price_nav_reachability_sparse_fixtures import (
    prosthetics_stage_only_one_tooth_pack,
    prosthetics_stage_paths_without_prices_pack,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)
from tests.test_typed_ui_turn_frame_offline import test_ui_stage_click_skips_planner

@pytest.fixture
def flask_ctx():
    from flask import Flask, request

    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        yield

_REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_ROOT = Path("clients/demo/target_response")
DOCTOR_CATALOG = Path("clients/demo/doctor_catalog.json")


def _bundle_and_doctors():
    return (
        load_response_schema_bundle(TARGET_ROOT),
        load_doctor_catalog(DOCTOR_CATALOG),
    )


def _prosthetics_broad_selection():
    bundle, doctors = _bundle_and_doctors()
    return run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=EffectiveScope(),
        topic="prosthetics",
    )


def test_implementation_artifacts_present() -> None:
    assert (_REPO_ROOT / "core" / "target_offer_price_reachability.py").is_file()
    assert (_REPO_ROOT / "tests" / "test_final_prosthetics_price_nav_reachability_sparse_fixtures.py").is_file()


def test_acceptance_1_prosthetics_broad_one_tooth_navigable_via_stage() -> None:
    selection = _prosthetics_broad_selection()
    assert "one_tooth" in selection.price_navigable_extents
    assert "one_tooth" not in selection.price_confirmed_extents


def test_acceptance_2_one_tooth_natural_tooth_present_25000() -> None:
    bundle, doctors = _bundle_and_doctors()
    scope = EffectiveScope(
        extent="one_tooth",
        topic="prosthetics",
        source="session",
        provenance=build_ui_stage_ref(topic="prosthetics", stage="natural_tooth_present"),
        stage="natural_tooth_present",
    )
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=scope,
        topic="prosthetics",
        stage="natural_tooth_present",
    )
    offers = selection.offers_by_service_id.get("zirconia_crowns", ())
    assert offers
    assert offers[0].price.min_amount == 25_000  # type: ignore[union-attr]


def test_acceptance_3_one_tooth_implant_placed_31000() -> None:
    bundle, doctors = _bundle_and_doctors()
    scope = EffectiveScope(
        extent="one_tooth",
        topic="prosthetics",
        source="session",
        provenance=build_ui_stage_ref(topic="prosthetics", stage="implant_placed"),
        stage="implant_placed",
    )
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=scope,
        topic="prosthetics",
        stage="implant_placed",
    )
    offers = selection.offers_by_service_id.get("implant_supported_prosthetics", ())
    assert offers
    assert offers[0].price.min_amount == 31_000  # type: ignore[union-attr]


def test_acceptance_4_prosthetics_broad_partial_denture_45000() -> None:
    selection = _prosthetics_broad_selection()
    bundle, _ = _bundle_and_doctors()
    offers_by_id = {offer.offer_id: offer for offer in bundle.offers}
    partial = next(
        anchor.offer_id
        for anchor in selection.anchors
        if anchor.extent == "few_teeth"
    )
    assert offers_by_id[partial].price.amount == 45_000  # type: ignore[union-attr]


def test_acceptance_5_prosthetics_broad_full_denture_65000() -> None:
    selection = _prosthetics_broad_selection()
    bundle, _ = _bundle_and_doctors()
    offers_by_id = {offer.offer_id: offer for offer in bundle.offers}
    full = next(
        anchor.offer_id for anchor in selection.anchors if anchor.extent == "full_arch"
    )
    assert offers_by_id[full].price.amount == 65_000  # type: ignore[union-attr]


def test_acceptance_6_scope_buttons_without_duplicates() -> None:
    selection = _prosthetics_broad_selection()
    nav = materialize_scope_nav_followups(
        "demo",
        topic="prosthetics",
        confirmed_extents=selection.price_navigable_extents,
    )
    refs = [item.ref for item in nav]
    assert len(refs) == len(set(refs)) == 3


def test_acceptance_7_stage_click_planner_not_called(monkeypatch: pytest.MonkeyPatch) -> None:
    test_ui_stage_click_skips_planner(monkeypatch, "/ask")


def test_acceptance_8_invalid_unshown_ref_fail_closed(flask_ctx) -> None:
    from tests.test_ac3_scope_price_flow_http_offline import test_http_unshown_ui_scope_ref_fail_closed

    test_http_unshown_ui_scope_ref_fail_closed(flask_ctx)


def test_acceptance_9_implantation_few_teeth_stays_hidden() -> None:
    bundle, doctors = _bundle_and_doctors()
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=EffectiveScope(),
        topic="implantation",
    )
    assert "few_teeth" not in selection.price_navigable_extents


def test_acceptance_10_implantation_one_tooth_full_arch_unchanged() -> None:
    test_broad_implantation_has_scope_nav_no_price_followups()


def test_acceptance_11_no_offer_id_inference_for_applicability() -> None:
    offer = TargetOffer.model_validate(
        {
            "offer_id": "classic.one_tooth.misleading",
            "service_id": "classic",
            "active": True,
            "applies_to_extents": ["few_teeth"],
            "price": {
                "mode": "fixed",
                "amount": 1,
                "currency": "RUB",
                "billing_unit": "procedure",
            },
            "package": {"label": "x", "includes": []},
        }
    )
    service = TargetService.model_validate(
        {
            "name": "Classic",
            "aliases": [],
            "family": "implantology",
            "roles": [],
            "active": True,
            "content_ref": "implantation__service__classic.md",
            "selection": {"mode": "scope", "extent": ["one_tooth", "few_teeth"]},
            "options": [],
        }
    )
    assert resolve_offer_applies_to_extents(offer, service) == ("few_teeth",)


def test_acceptance_12_sparse_only_one_tooth_route_one_button(tmp_path) -> None:
    _root, bundle = prosthetics_stage_only_one_tooth_pack(tmp_path)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=EffectiveScope(),
        topic="prosthetics",
    )
    assert selection.price_navigable_extents == ("one_tooth",)
    nav = materialize_scope_nav_followups(
        "demo",
        topic="prosthetics",
        confirmed_extents=selection.price_navigable_extents,
    )
    assert len(nav) == 1
    assert nav[0].ref.endswith("/one_tooth")


def test_acceptance_13_sparse_stage_only_path_button_shown(tmp_path) -> None:
    _root, bundle = prosthetics_stage_only_one_tooth_pack(tmp_path)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=EffectiveScope(),
        topic="prosthetics",
    )
    assert "one_tooth" in selection.price_navigable_extents
    assert selection.price_confirmed_extents == ()


def test_acceptance_14_sparse_stage_paths_without_prices_hidden(tmp_path) -> None:
    _root, bundle = prosthetics_stage_paths_without_prices_pack(tmp_path)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=EffectiveScope(),
        topic="prosthetics",
    )
    assert selection.price_navigable_extents == ()


def test_acceptance_15_http_ask_and_stream_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    test_http_ask_and_stream_scope_click_parity(monkeypatch)


def test_acceptance_16_rich_pricebook_and_frozen_artifacts_unchanged() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_broad_prosthetics_overview_offers_include_stage_reachable_prices() -> None:
    bundle, doctors = _bundle_and_doctors()
    inputs = _pipeline_inputs()
    spec = TargetResponseSpec.model_validate(
        {
            "response_mode": "answer",
            "response_stage": "broad_family_price",
            "scope_price_topic": "prosthetics",
            "tone_key": "commercial_warm",
            "allowed_topics": ("prosthetics",),
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
        effective_scope=EffectiveScope(),
        strategy_context=strategy_match_from_effective_scope(EffectiveScope()),
        client_id="demo",
        md_root=inputs["md_root"],  # type: ignore[arg-type]
        semantic_context="prosthetics",
        today=inputs["today"],  # type: ignore[arg-type]
        include_initial_block=False,
        include_cta=False,
    )
    amounts = []
    for offer in package.materials.offers:
        price = offer.price
        if price.mode in {"from", "range"}:
            amounts.append(int(price.min_amount))  # type: ignore[arg-type]
        else:
            amounts.append(int(price.amount))  # type: ignore[arg-type]
    assert sorted(amounts) == [25_000, 31_000, 45_000, 65_000]


def test_broad_prosthetics_runtime_three_scope_buttons() -> None:
    result = _run_family_price(
        user_message="Сколько стоит протезирование?",
        frame_overrides={"topic": "prosthetics"},
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    refs = {item.ref for item in result.verified.navigation_followups}
    assert refs == {
        "target:ui_scope/prosthetics/one_tooth",
        "target:ui_scope/prosthetics/few_teeth",
        "target:ui_scope/prosthetics/full_arch",
    }


def test_one_tooth_scope_click_still_stage_clarifies() -> None:
    scope = EffectiveScope(
        extent="one_tooth",
        topic="prosthetics",
        source="session",
        provenance=build_ui_scope_ref(topic="prosthetics", extent="one_tooth"),
    )
    result = _run_family_price(
        effective_scope=scope,
        user_message="продолжить",
        frame_overrides={"topic": "prosthetics"},
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.spec.response_stage == "stage_clarify"
    assert len(result.verified.navigation_followups) == 2
    assert all(is_ui_stage_ref(item.ref) for item in result.verified.navigation_followups)
