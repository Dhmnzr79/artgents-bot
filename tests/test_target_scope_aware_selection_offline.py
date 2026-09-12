from __future__ import annotations

import ast
import hashlib
import re
from copy import deepcopy
from pathlib import Path

from contracts.effective_scope import EffectiveScope
from contracts.response_schema import ResponseSchemaBundle, TargetClinicStrategy
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.target_scope_aware_selection import run_target_scope_aware_selection

TARGET_ROOT = Path("clients/demo/target_response")
DOCTOR_CATALOG = Path("clients/demo/doctor_catalog.json")
_ARTIFACT_DIR = Path("docs/artifacts/w1b_wip_checkpoint_2026-07-24")


def _inputs() -> tuple[ResponseSchemaBundle, object]:
    return (
        load_response_schema_bundle(TARGET_ROOT),
        load_doctor_catalog(DOCTOR_CATALOG),
    )


def _scope(
    *,
    extent: str = "unknown",
    topic: str = "implantation",
) -> EffectiveScope:
    return EffectiveScope(
        extent=extent,  # type: ignore[arg-type]
        topic=topic,
        source="ui_action",
        provenance="test",
    )


def _run(**kwargs):
    bundle, doctors = _inputs()
    return run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=kwargs.pop("effective_scope", _scope()),
        topic=kwargs.pop("topic", "implantation"),
        **kwargs,
    )


# --- Implantation matrix (1-8) ---


def test_unknown_returns_broad_anchors_one_tooth_and_full_arch() -> None:
    result = _run(effective_scope=_scope(extent="unknown"))
    assert result.kind == "broad_anchors"
    anchor_extents = {anchor.extent for anchor in result.anchors}
    assert "one_tooth" in anchor_extents
    assert "full_arch" in anchor_extents
    assert all(anchor.offer_id for anchor in result.anchors)


def test_one_tooth_scoped_includes_classic() -> None:
    result = _run(effective_scope=_scope(extent="one_tooth"))
    assert result.kind == "scoped_shortlist"
    assert "classic" in result.service_ids


def test_one_tooth_without_extraction_excludes_one_stage() -> None:
    result = _run(effective_scope=_scope(extent="one_tooth"))
    assert "one_stage" not in result.service_ids


def test_one_tooth_extraction_context_includes_one_stage() -> None:
    result = _run(
        effective_scope=_scope(extent="one_tooth"),
        stage="extraction_context",
    )
    assert "one_stage" in result.service_ids


def test_few_teeth_scoped_only_catalog_applicable() -> None:
    result = _run(effective_scope=_scope(extent="few_teeth"))
    assert result.kind == "scoped_shortlist"
    assert "classic" in result.service_ids
    assert "all_on_4" not in result.service_ids


def test_full_arch_allows_commercial_protocols_without_medical_claim() -> None:
    result = _run(effective_scope=_scope(extent="full_arch"))
    assert "all_on_4" in result.service_ids or "all_on_6" in result.service_ids
    assert result.kind == "scoped_shortlist"


def test_bone_deficit_context_does_not_auto_include_zygomatic_without_full_arch() -> None:
    result = _run(
        effective_scope=_scope(extent="one_tooth"),
        jaw="upper",
        reported_context="reported_bone_deficit",
    )
    assert "zygomatic_implants" not in result.service_ids


def test_explicit_all_on_4_pins_named_service() -> None:
    result = _run(
        effective_scope=_scope(extent="full_arch"),
        explicit_service_id="all_on_4",
    )
    assert result.service_ids == ("all_on_4",)
    assert "all_on_4" in result.offers_by_service_id


# --- Prosthetics matrix (9-14) ---


def test_prosthetics_one_tooth_natural_tooth_zirconia() -> None:
    result = _run(
        effective_scope=_scope(extent="one_tooth", topic="prosthetics"),
        topic="prosthetics",
        stage="natural_tooth_present",
    )
    assert "zirconia_crowns" in result.service_ids


def test_prosthetics_one_tooth_implant_placed_implant_supported() -> None:
    result = _run(
        effective_scope=_scope(extent="one_tooth", topic="prosthetics"),
        topic="prosthetics",
        stage="implant_placed",
    )
    assert "implant_supported_prosthetics" in result.service_ids


def test_unknown_stage_excludes_stage_required_zirconia() -> None:
    result = _run(
        effective_scope=_scope(extent="one_tooth", topic="prosthetics"),
        topic="prosthetics",
    )
    assert "zirconia_crowns" not in result.service_ids


def test_few_teeth_partial_denture_not_full() -> None:
    result = _run(
        effective_scope=_scope(extent="few_teeth", topic="prosthetics"),
        topic="prosthetics",
        stage="natural_tooth_present",
    )
    assert "removable_dentures" in result.service_ids
    offers = result.offers_by_service_id.get("removable_dentures", ())
    assert offers
    assert all("partial" in offer.offer_id or offer.option_id == "partial" for offer in offers)


def test_full_arch_full_denture_not_partial() -> None:
    result = _run(
        effective_scope=_scope(extent="full_arch", topic="prosthetics"),
        topic="prosthetics",
    )
    offers = result.offers_by_service_id.get("removable_dentures", ())
    assert offers
    assert all(offer.option_id == "full" for offer in offers)


def test_veneers_context_not_in_prosthetics_family_overview_path() -> None:
    result = _run(
        effective_scope=_scope(extent="one_tooth", topic="prosthetics"),
        topic="prosthetics",
        stage="natural_tooth_present",
    )
    assert "veneers" not in result.service_ids


# --- Price integrity (15-22) ---


def test_all_on_4_offers_preserve_exact_amounts_and_units() -> None:
    result = _run(effective_scope=_scope(extent="full_arch"))
    offers = result.offers_by_service_id.get("all_on_4", ())
    assert offers
    assert [offer.offer_id for offer in offers][:3] == [
        "all_on_4.jaw.impro",
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.nobel",
    ]
    assert [offer.price.amount for offer in offers][:3] == [368_000, 318_000, 428_000]  # type: ignore[union-attr]
    assert all(offer.price.billing_unit == "jaw" for offer in offers)  # type: ignore[union-attr]


def test_explicit_offer_pin_preserves_exact_offer() -> None:
    result = _run(
        effective_scope=_scope(extent="full_arch"),
        explicit_service_id="all_on_4",
        explicit_offer_id="all_on_4.jaw.nobel",
    )
    offers = result.offers_by_service_id["all_on_4"]
    assert offers[0].offer_id == "all_on_4.jaw.nobel"
    assert offers[0].price.amount == 428_000  # type: ignore[union-attr]


def test_inactive_service_excluded_from_applicability() -> None:
    bundle, doctors = _inputs()
    bundle_copy = deepcopy(bundle)
    bundle_copy.services["classic"] = bundle_copy.services["classic"].model_copy(
        update={"active": False}
    )
    result = run_target_scope_aware_selection(
        bundle_copy,
        doctors,
        effective_scope=_scope(extent="one_tooth"),
        topic="implantation",
    )
    assert "classic" not in result.service_ids


def test_from_price_mode_preserved_verbatim() -> None:
    result = _run(
        effective_scope=_scope(extent="one_tooth", topic="prosthetics"),
        topic="prosthetics",
        stage="natural_tooth_present",
    )
    offers = result.offers_by_service_id.get("zirconia_crowns", ())
    assert offers
    assert offers[0].price.mode == "from"  # type: ignore[union-attr]
    assert offers[0].price.min_amount == 25_000  # type: ignore[union-attr]


def test_brand_projection_s24_path_preserves_brand_offers() -> None:
    result = _run(
        effective_scope=_scope(extent="full_arch"),
        explicit_service_id="all_on_4",
        selected_brand_id="nobel_biocare",
    )
    offers = result.offers_by_service_id["all_on_4"]
    assert len(offers) == 1
    assert offers[0].offer_id == "all_on_4.jaw.nobel"
    assert offers[0].brand_id == "nobel_biocare"


def test_billing_units_not_multiplied_or_merged_across_offers() -> None:
    result = _run(effective_scope=_scope(extent="full_arch"))
    jaw_offers = result.offers_by_service_id.get("all_on_4", ())
    assert jaw_offers
    units = {offer.price.billing_unit for offer in jaw_offers}  # type: ignore[union-attr]
    assert units == {"jaw"}
    assert all(offer.price.amount is not None for offer in jaw_offers)  # type: ignore[union-attr]


def test_option_pin_does_not_expand_to_sibling_options() -> None:
    result = _run(
        effective_scope=_scope(extent="few_teeth", topic="prosthetics"),
        topic="prosthetics",
        stage="natural_tooth_present",
    )
    offers = result.offers_by_service_id.get("removable_dentures", ())
    assert len(offers) == 1
    assert offers[0].option_id == "partial"


def test_no_applicable_offers_emits_typed_exclusion() -> None:
    bundle, doctors = _inputs()
    bundle_copy = deepcopy(bundle)
    bundle_copy.offers = [
        offer.model_copy(update={"active": False})
        if offer.service_id == "classic"
        else offer
        for offer in bundle_copy.offers
    ]
    result = run_target_scope_aware_selection(
        bundle_copy,
        doctors,
        effective_scope=_scope(extent="one_tooth"),
        topic="implantation",
        explicit_service_id="classic",
    )
    assert "classic" not in result.offers_by_service_id
    assert "no_public_or_missing_offers:classic" in result.exclusions


def test_core_modules_have_no_hardcoded_demo_service_ids() -> None:
    demo_ids = set(_inputs()[0].services.keys())
    modules = [
        Path("core/target_scope_aware_selection.py"),
        Path("core/target_service_applicability.py"),
        Path("core/target_strategy_context.py"),
    ]
    offenders: list[str] = []
    for path in modules:
        text = path.read_text(encoding="utf-8")
        for service_id in demo_ids:
            if f'"{service_id}"' in text or f"'{service_id}'" in text:
                offenders.append(f"{path.name}:{service_id}")
    assert not offenders


def test_max_options_respected() -> None:
    result = _run(effective_scope=_scope(extent="full_arch"))
    assert "all_on_4" in result.service_ids
    assert len(result.offers_by_service_id["all_on_4"]) <= 3


def test_two_strategies_same_applicability_different_order() -> None:
    bundle, doctors = _inputs()
    alt_strategy = TargetClinicStrategy.model_validate(
        {
            "version": 1,
            "default_max_options": 3,
            "default_service_priorities": {
                **bundle.strategy.default_service_priorities,
                "all_on_6": 200,
                "all_on_4": 10,
            },
            "rules": [],
        }
    )
    bundle_a = deepcopy(bundle)
    bundle_b = deepcopy(bundle)
    bundle_b.strategy = alt_strategy

    result_a = run_target_scope_aware_selection(
        bundle_a,
        doctors,
        effective_scope=_scope(extent="full_arch"),
        topic="implantation",
    )
    result_b = run_target_scope_aware_selection(
        bundle_b,
        doctors,
        effective_scope=_scope(extent="full_arch"),
        topic="implantation",
    )
    set_a = set(result_a.service_ids)
    set_b = set(result_b.service_ids)
    assert set_a == set_b
    assert result_a.service_ids != result_b.service_ids


# --- Strategy isolation (23-26) ---


def test_strategy_cannot_resurrect_ineligible_service() -> None:
    bundle, doctors = _inputs()
    poisoned = deepcopy(bundle)
    poisoned.strategy = TargetClinicStrategy.model_validate(
        {
            **bundle.strategy.model_dump(),
            "default_service_priorities": {
                **bundle.strategy.default_service_priorities,
                "classic": 9999,
            },
            "rules": [],
        }
    )
    result = run_target_scope_aware_selection(
        poisoned,
        doctors,
        effective_scope=_scope(extent="full_arch"),
        topic="implantation",
    )
    assert "classic" not in result.service_ids


# --- Firewalls (29-34) ---


def test_ac2_modules_do_not_read_patient_scope() -> None:
    modules = [
        Path("contracts/target_scope_aware_selection.py"),
        Path("contracts/target_service_applicability.py"),
        Path("core/target_scope_aware_selection.py"),
        Path("core/target_service_applicability.py"),
        Path("core/target_strategy_context.py"),
    ]
    offenders: list[str] = []
    for rel in modules:
        text = rel.read_text(encoding="utf-8")
        if ".patient_scope" in text:
            offenders.append(rel.as_posix())
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "a9" in node.module.lower():
                offenders.append(f"{rel}: {node.module}")
    assert not offenders


def test_w1b_snapshot_checksums_unchanged() -> None:
    checksums = (_ARTIFACT_DIR / "checksums.sha256").read_text(encoding="utf-8")
    expected = dict(re.findall(r"^([A-Z_]+)=([A-F0-9]+)", checksums, re.M))
    files = {
        "TRACKED_PATCH": _ARTIFACT_DIR / "w1b_tracked.patch",
        "DIFF_STAT": _ARTIFACT_DIR / "diff_stat.txt",
        "FAMILY_PRICE_GROUPS_YAML": _ARTIFACT_DIR / "untracked/clients/demo/target_response/family_price_groups.yaml",
        "TARGET_FAMILY_PRICE_GROUP_FOLLOWUP": _ARTIFACT_DIR / "untracked/contracts/target_family_price_group_followup.py",
        "TARGET_FAMILY_PRICE_GROUPS": _ARTIFACT_DIR / "untracked/contracts/target_family_price_groups.py",
        "TEST_DRILLDOWN": _ARTIFACT_DIR / "untracked/tests/test_w1b_family_price_group_drilldown_offline.py",
        "TEST_MENU": _ARTIFACT_DIR / "untracked/tests/test_w1b_family_price_situation_menu_offline.py",
    }
    for key, path in files.items():
        digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        assert digest == expected[key]
