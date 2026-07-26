"""Verify branches 1–3 (no_public_price, service_not_offered, alternatives) without redesign."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.clinic_policies_loader import (
    build_service_not_offered_answer,
    find_service_alternative,
    service_alternative_quick_replies,
)
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.service_data_context import build_service_data_context
from core.target_offer_projection import project_target_service_offers
from core.target_response_stage import derive_response_stage
from core.target_scope_aware_selection import run_target_scope_aware_selection
from core.target_strategy_context import TargetStrategyMatch
from contracts.effective_scope import EffectiveScope
from query_selector import select_price_service_route
from tests.test_final_price_and_service_coverage_sparse_fixtures import (
    build_sparse_target_pack,
    no_public_beats_family_pack,
)

TARGET_ROOT = Path("clients/demo/target_response")
DOCTOR_CATALOG = Path("clients/demo/doctor_catalog.json")


def test_branch_h_no_public_price_offer_projects_with_approved_text(tmp_path) -> None:
    _root, bundle = no_public_beats_family_pack(tmp_path)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    context = build_service_data_context(bundle, doctors, "classic")
    projection = project_target_service_offers(
        context,
        bundle.strategy,
        TargetStrategyMatch(family=None, extent=None),
    )
    assert len(projection.offers) == 1
    assert projection.offers[0].price.mode == "no_public_price"
    assert projection.offers[0].price.approved_text == "Точная цена после консультации и КТ."  # type: ignore[union-attr]


def test_branch_c_no_public_price_beats_family_in_scoped_selection(tmp_path) -> None:
    _root, bundle = no_public_beats_family_pack(tmp_path)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=EffectiveScope(extent="one_tooth", topic="implantation", source="session", provenance="test"),
        topic="implantation",
    )
    assert selection.offers_by_service_id["classic"][0].price.mode == "no_public_price"
    assert "family_only_broad" not in selection.exclusions


def test_branch_f_not_offered_with_authored_alternative() -> None:
    q = "Сколько стоит базальная имплантация?"
    alt = find_service_alternative(q, "demo")
    assert alt is not None
    answer = build_service_not_offered_answer("demo", question=q, requested_service="базальная имплантация")
    assert answer.strip()
    assert "базал" in answer.lower() or "имплант" in answer.lower()
    replies = service_alternative_quick_replies(q, "demo")
    assert replies
    assert all(item.get("ref") for item in replies)


def test_branch_g_not_offered_without_alternative_plain_answer() -> None:
    answer = build_service_not_offered_answer(
        "demo",
        question="Сколько стоит лазерная шлифовка эмали?",
        requested_service="лазерная шлифовка эмали",
    )
    assert answer.strip()
    assert find_service_alternative("лазерная шлифовка эмали", "demo") is None
    replies = service_alternative_quick_replies("лазерная шлифовка эмали", "demo")
    assert replies == []


def test_branch_f_ingress_route_service_not_offered(monkeypatch: pytest.MonkeyPatch) -> None:
    from contracts.patient_situation import PatientSituationResult

    monkeypatch.setattr(
        "query_selector._patient_situation_for_turn",
        lambda *a, **k: (
            PatientSituationResult(
                kind="unknown",
                confidence=0.0,
                source="rule_based",
                patient_scope="unknown",
            ),
            False,
        ),
    )
    route = select_price_service_route(
        "Сколько стоит базальная имплантация?",
        client_id="demo",
        sid="fps-branch-f",
        intent_override="price_lookup",
    )
    assert route.get("mode") == "clarify"
    assert route.get("fallback_reason") == "service_not_offered"


def test_branch_i_missing_price_record_is_data_gap_not_cross_service(tmp_path) -> None:
    root = build_sparse_target_pack(
        tmp_path,
        services={
            "classic": {
                "name": "Classic",
                "aliases": [],
                "family": "implantology",
                "roles": ["protocol"],
                "active": True,
                "content_ref": "implantation__service__classic.md",
                "selection": {"mode": "scope", "extent": ["one_tooth"]},
                "options": [],
            },
            "other_srv": {
                "name": "Other",
                "aliases": [],
                "family": "implantology",
                "roles": ["supporting"],
                "active": True,
                "content_ref": "implantation__service__other_srv.md",
                "selection": {"mode": "scope", "extent": ["one_tooth"]},
                "options": [],
            },
        },
        offers=[
            {
                "offer_id": "other_srv.default",
                "service_id": "other_srv",
                "active": True,
                "price": {
                    "mode": "from",
                    "min_amount": 99000,
                    "currency": "RUB",
                    "billing_unit": "implant",
                },
                "package": {"label": "other", "includes": ["step"]},
            }
        ],
    )
    bundle = load_response_schema_bundle(root)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=EffectiveScope(extent="one_tooth", topic="implantation", source="session", provenance="test"),
        topic="implantation",
        explicit_service_id="classic",
    )
    assert "classic" not in selection.offers_by_service_id
    stage = derive_response_stage(
        explicit_service_id="classic",
        effective_scope=EffectiveScope(extent="one_tooth", topic="implantation", source="session", provenance="test"),
        topic="implantation",
        bundle=bundle,
        selection=selection,
    )
    assert stage == "data_gap"


def test_rich_demo_bundle_loads_without_family_prices_file() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    assert bundle.family_prices.records == []
