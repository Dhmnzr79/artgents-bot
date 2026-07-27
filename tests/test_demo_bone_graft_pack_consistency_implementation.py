"""COMPLETION checker for DEMO_BONE_GRAFT_PACK_CONSISTENCY implementation."""

from __future__ import annotations

import json
from pathlib import Path

from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.target_client_data import match_service_from_target_catalog
from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_demo_target_price_offers import UNIT_LABELS
from tests.test_final_price_scope_coverage_nav_implementation import (
    test_frozen_pins_unchanged as test_pscn_frozen_pins_unchanged,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_ROOT = _REPO_ROOT / "clients" / "demo"
_TARGET = _DEMO_ROOT / "target_response"
_DOCTOR_CATALOG = _DEMO_ROOT / "doctor_catalog.json"
_LEGACY_FIXTURE = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "client_pack"
    / "fixtures"
    / "demo_legacy_marketing.yaml"
)


def _doctors_for(service_id: str) -> set[str]:
    catalog = load_doctor_catalog(_DOCTOR_CATALOG)
    return {
        doctor_id
        for doctor_id, doctor in catalog.doctors.items()
        if service_id in doctor.service_ids
    }


def test_bone_graft_doctor_linkage_matches_owner_sign_off() -> None:
    assert _doctors_for("bone_graft") == {
        "doctors__doctor__orlov",
        "doctors__doctor__volkov",
    }
    assert "doctors__doctor__kuznetsov" not in _doctors_for("bone_graft")


def test_bone_graft_service_queries_resolve_to_catalog() -> None:
    who = match_service_from_target_catalog(
        "Кто делает костную пластику?",
        client_id="demo",
    )
    assert who is not None
    assert who["matched_service_id"] == "bone_graft"

    price = match_service_from_target_catalog(
        "Сколько стоит костная пластика?",
        client_id="demo",
    )
    assert price is not None
    assert price["matched_service_id"] == "bone_graft"


def test_bone_graft_no_public_price_without_dummy_unit() -> None:
    bundle = load_response_schema_bundle(_TARGET)
    offer = next(item for item in bundle.offers if item.service_id == "bone_graft")
    assert offer.price.mode == "no_public_price"
    assert "Стоимость костной пластики" in offer.price.approved_text
    assert "bone_graft" not in UNIT_LABELS

    raw_offer = json.loads(
        (_TARGET / "pricebook/services/bone_graft.default.json").read_text(encoding="utf-8")
    )
    assert "billing_unit" not in raw_offer["price"]


def test_sinus_lift_prices_unchanged() -> None:
    bundle = load_response_schema_bundle(_TARGET)
    sinus = [offer for offer in bundle.offers if offer.service_id == "sinus_lift"]
    assert {offer.price.mode for offer in sinus} == {"from"}
    assert {offer.price.min_amount for offer in sinus} == {42000, 68000}


def test_marketing_facts_applicability_without_bone_graft_promo_invention() -> None:
    facts = json.loads((_TARGET / "pricebook/facts.json").read_text(encoding="utf-8"))
    assert "bone_graft" in facts["installment_12"]["allowed_service_ids"]
    assert "bone_graft" in facts["free_implant_consult"]["allowed_service_ids"]
    assert "bone_graft" in facts["implant_same_day_discount"]["allowed_service_ids"]
    assert "bone_graft" not in facts["implant_warranty"]["allowed_service_ids"]
    assert "bone_graft" not in facts["professional_whitening_discount"]["allowed_service_ids"]
    assert "bone_graft" not in facts["tax_deduction"]["allowed_service_ids"]
    assert not any(fact_id.startswith("bone_graft") for fact_id in facts)


def test_legacy_marketing_fixture_isolated_from_active_client_pack() -> None:
    assert not (_REPO_ROOT / "tests/fixtures/demo_legacy_marketing.yaml").exists()
    assert _LEGACY_FIXTURE.is_file()
    policy_source = (_REPO_ROOT / "tests/test_demo_target_marketing_policy.py").read_text(
        encoding="utf-8"
    )
    assert "demo_legacy_marketing" not in policy_source


def test_frozen_pins_unchanged() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()
