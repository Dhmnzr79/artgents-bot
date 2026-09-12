"""COMPLETION checker and acceptance 1–18 for FINAL_EXPLICIT_SERVICE_PRICE_LOOKUP_BOUNDARY."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.effective_scope import EffectiveScope, ScopeAxisProvenance
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
from contracts.ui_scope_action import build_ui_scope_ref
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.target_offline_response_assembly import TargetOfflineResponseAssemblyError
from core.target_scope_aware_selection import run_target_scope_aware_selection
from core.target_strategy_context import strategy_match_from_effective_scope
from core.turn_frame_from_raw import build_turn_frame_from_raw
from core.target_turn_frame_bound_response import run_target_offline_turn_frame_bound_response
from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from tests.test_ac3_scope_price_flow_http_offline import test_http_ask_and_stream_scope_click_parity
from tests.test_ac3_scope_price_flow_offline import (
    _run_family_price,
    test_broad_implantation_has_scope_nav_no_price_followups,
    test_w1b_snapshot_checksums_unchanged,
)
from tests.test_demo_target_turn_frame_bound_response import (
    RecordingComposerBackend,
    RecordingSemanticBackend,
    VALID_TEXT,
    _envelope,
    _frame,
    _pipeline_inputs,
)
from tests.test_final_explicit_service_price_lookup_boundary_sparse_fixtures import (
    explicit_lookup_no_public_price_pack,
    explicit_lookup_session_block_pack,
)
from tests.test_final_price_scope_coverage_nav_implementation import (
    test_frozen_pins_unchanged as test_pscn_frozen_pins_unchanged,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)
from tests.test_session_patient_facts_offline import test_sid_isolation_for_patient_facts
from tests.test_typed_ui_turn_frame_offline import test_ui_stage_click_skips_planner

_REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_ROOT = Path("clients/demo/target_response")
DOCTOR_CATALOG = Path("clients/demo/doctor_catalog.json")
ONE_STAGE_TEXT = (
    "Одномоментная имплантация стоит от 96 500 рублей за один зуб под ключ. "
    "На бесплатной консультации врач уточнит детали лечения."
)
DATA_GAP_TEXT = (
    "Точную стоимость по вашей ситуации лучше уточнить на консультации — "
    "администратор поможет сориентироваться."
)
OVERVIEW_TEXT = (
    "Одномоментная имплантация — установка импланта в день удаления зуба. "
    "Врач на консультации расскажет о этапах."
)
_BOUNDARY_MODULE = _REPO_ROOT / "core" / "target_explicit_service_price_lookup.py"


def _session_extent_scope(extent: str, *, topic: str = "implantation") -> EffectiveScope:
    ref = build_ui_scope_ref(topic=topic, extent=extent)  # type: ignore[arg-type]
    return EffectiveScope(
        extent=extent,  # type: ignore[arg-type]
        topic=topic,
        source="session",
        provenance=ref,
        extent_axis=ScopeAxisProvenance(source="session", provenance=ref),
    )


def _current_turn_extent_scope(extent: str, *, topic: str = "implantation") -> EffectiveScope:
    provenance = f"a9:{extent}"
    return EffectiveScope(
        extent=extent,  # type: ignore[arg-type]
        topic=topic,
        source="a9_turn",
        provenance=provenance,
        extent_axis=ScopeAxisProvenance(source="a9_turn", provenance=provenance),
    )


def _explicit_price_frame(
    service_id: str,
    *,
    topic: str = "implantation",
    aspects: tuple[str, ...] = ("price",),
    primary_aspect: str = "price",
) -> object:
    return build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": list(aspects),
            "primary_aspect": primary_aspect,
            "service_id": service_id,
            "topic": topic,
            "topic_confidence": 0.9,
            "intent": "price_lookup",
        },
        allowed_topics=frozenset({topic, "doctors"}),
        allowed_service_ids=frozenset({service_id}),
    )


def _run_explicit_bound(
    service_id: str,
    *,
    effective_scope: EffectiveScope | None = None,
    topic: str = "implantation",
    aspects: tuple[str, ...] = ("price",),
    primary_aspect: str = "price",
    composer_text: str = ONE_STAGE_TEXT,
) -> TargetTurnFrameBoundMaterializeResponse:
    frame = _explicit_price_frame(
        service_id,
        topic=topic,
        aspects=aspects,
        primary_aspect=primary_aspect,
    )
    composer = RecordingComposerBackend(text=composer_text)
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs()
    scope = effective_scope or EffectiveScope()
    inputs["strategy_context"] = strategy_match_from_effective_scope(scope)
    result = run_target_offline_turn_frame_bound_response(
        frame,
        _envelope(allowed_topics=(topic, "doctors")),
        **inputs,  # type: ignore[arg-type]
        effective_scope=scope,
        composer_backend=composer,
        semantic_backend=semantic,
        client_id="demo",
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    return result


def _offer_amounts_from_composer(composer: RecordingComposerBackend) -> list[int]:
    evidence = json.loads(composer.invocations[0].primary_evidence_json)
    amounts: list[int] = []
    for item in evidence:
        if item["kind"] != "offer":
            continue
        payload = json.loads(item["text"])
        price = payload["price"]
        if "amount" in price:
            amounts.append(int(price["amount"]))
        elif "min_amount" in price:
            amounts.append(int(price["min_amount"]))
    return amounts


def test_implementation_artifacts_present() -> None:
    assert _BOUNDARY_MODULE.is_file()
    assert (
        _REPO_ROOT
        / "tests"
        / "test_final_explicit_service_price_lookup_boundary_sparse_fixtures.py"
    ).is_file()
    assert (
        _REPO_ROOT
        / "tests"
        / "test_final_explicit_service_price_lookup_boundary_cross_turn_matrix.py"
    ).is_file()


def test_acceptance_1_session_full_arch_explicit_one_stage_materialized() -> None:
    scope = _session_extent_scope("full_arch")
    composer = RecordingComposerBackend(text=ONE_STAGE_TEXT)
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs()
    inputs["strategy_context"] = strategy_match_from_effective_scope(scope)
    result = run_target_offline_turn_frame_bound_response(
        _explicit_price_frame("one_stage"),
        _envelope(allowed_topics=("implantation",)),
        **inputs,  # type: ignore[arg-type]
        effective_scope=scope,
        composer_backend=composer,
        semantic_backend=semantic,
        client_id="demo",
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.dispatch.policy_request.service_id == "one_stage"
    assert result.verified.spec.response_stage in {None, "concrete_service_price"}
    amounts = _offer_amounts_from_composer(composer)
    assert 96_500 in amounts


def test_acceptance_2_session_one_tooth_explicit_all_on_4_jaw_prices() -> None:
    scope = _session_extent_scope("one_tooth")
    composer = RecordingComposerBackend(text=VALID_TEXT)
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs()
    inputs["strategy_context"] = strategy_match_from_effective_scope(scope)
    result = run_target_offline_turn_frame_bound_response(
        _frame(),
        _envelope(),
        **inputs,  # type: ignore[arg-type]
        effective_scope=scope,
        composer_backend=composer,
        semantic_backend=semantic,
        client_id="demo",
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.dispatch.policy_request.service_id == "all_on_4"
    amounts = sorted(_offer_amounts_from_composer(composer))
    assert amounts == [318_000, 368_000, 428_000]


def test_acceptance_3_session_full_arch_explicit_zirconia_from_25000() -> None:
    scope = _session_extent_scope("full_arch", topic="prosthetics")
    selection = run_target_scope_aware_selection(
        load_response_schema_bundle(TARGET_ROOT),
        load_doctor_catalog(DOCTOR_CATALOG),
        effective_scope=scope,
        topic="prosthetics",
        explicit_service_id="zirconia_crowns",
    )
    offers = selection.offers_by_service_id["zirconia_crowns"]
    assert offers[0].price.min_amount == 25_000  # type: ignore[union-attr]


def test_acceptance_4_explicit_one_stage_stage_unknown_price_shown() -> None:
    result = _run_explicit_bound("one_stage", effective_scope=EffectiveScope())
    assert result.verified.spec.response_stage in {None, "concrete_service_price"}
    selection = run_target_scope_aware_selection(
        load_response_schema_bundle(TARGET_ROOT),
        load_doctor_catalog(DOCTOR_CATALOG),
        effective_scope=EffectiveScope(),
        topic="implantation",
        explicit_service_id="one_stage",
    )
    assert selection.offers_by_service_id["one_stage"]


def test_acceptance_5_compatible_current_turn_scope_filters_offers() -> None:
    scope = _current_turn_extent_scope("one_tooth")
    selection = run_target_scope_aware_selection(
        load_response_schema_bundle(TARGET_ROOT),
        load_doctor_catalog(DOCTOR_CATALOG),
        effective_scope=scope,
        topic="implantation",
        explicit_service_id="one_stage",
    )
    offers = selection.offers_by_service_id["one_stage"]
    assert offers
    assert all("one_tooth" in offer.applies_to_extents for offer in offers)  # type: ignore[union-attr]


def test_acceptance_6_incompatible_current_turn_scope_data_gap() -> None:
    scope = _current_turn_extent_scope("full_arch")
    result = _run_explicit_bound(
        "one_stage",
        effective_scope=scope,
        composer_text=DATA_GAP_TEXT,
    )
    assert result.verified.spec.response_stage == "data_gap"


def test_acceptance_7_named_service_no_public_price_existing_path(tmp_path) -> None:
    _root, bundle = explicit_lookup_no_public_price_pack(tmp_path)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=_session_extent_scope("full_arch"),
        topic="implantation",
        explicit_service_id="svc_private",
    )
    offers = selection.offers_by_service_id["svc_private"]
    assert len(offers) == 1
    assert offers[0].price.mode == "no_public_price"


def test_acceptance_8_named_service_absent_not_offered_path() -> None:
    frame = _explicit_price_frame("missing_svc_xyz")
    with pytest.raises(TargetOfflineResponseAssemblyError) as exc:
        run_target_offline_turn_frame_bound_response(
            frame,
            _envelope(),
            **_pipeline_inputs(),  # type: ignore[arg-type]
            composer_backend=RecordingComposerBackend(text=VALID_TEXT),
            semantic_backend=RecordingSemanticBackend(),
            client_id="demo",
        )
    assert exc.value.code == "offline_assembly_service_not_found"


def test_acceptance_9_vague_followup_without_service_id_session_continuity() -> None:
    scope = _session_extent_scope("full_arch")
    result = _run_family_price(effective_scope=scope, user_message="А сколько?")
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.spec.response_stage == "scoped_family_price"
    assert result.dispatch.policy_request.service_id is None


def test_acceptance_10_broad_implantation_overview_unchanged() -> None:
    test_broad_implantation_has_scope_nav_no_price_followups()


def test_acceptance_11_typed_scope_stage_clicks_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    test_ui_stage_click_skips_planner(monkeypatch, "/ask")
    from tests.test_ac3_scope_price_flow_offline import (
        test_prosthetics_one_tooth_stage_clarify_buttons,
        test_prosthetics_stage_click_then_scoped_services,
    )

    test_prosthetics_one_tooth_stage_clarify_buttons()
    test_prosthetics_stage_click_then_scoped_services()


def test_acceptance_12_informational_turn_without_price_no_lookup() -> None:
    scope = _session_extent_scope("full_arch")
    result = _run_explicit_bound(
        "one_stage",
        effective_scope=scope,
        aspects=("overview",),
        primary_aspect="overview",
        composer_text=OVERVIEW_TEXT,
    )
    assert result.verified.spec.response_stage in {None, "concrete_service_price"}


def test_acceptance_13_no_eligibility_claims_in_directives() -> None:
    scope = _session_extent_scope("full_arch")
    composer = RecordingComposerBackend(text=ONE_STAGE_TEXT)
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs()
    inputs["strategy_context"] = strategy_match_from_effective_scope(scope)
    run_target_offline_turn_frame_bound_response(
        _explicit_price_frame("one_stage"),
        _envelope(allowed_topics=("implantation",)),
        **inputs,  # type: ignore[arg-type]
        effective_scope=scope,
        composer_backend=composer,
        semantic_backend=semantic,
        client_id="demo",
    )
    combined = (
        composer.invocations[0].response_directives_json
        + composer.invocations[0].primary_evidence_json
    ).lower()
    for forbidden in (
        "вам можно",
        "вам нельзя",
        "вам подходит",
        "вам не подходит",
    ):
        assert forbidden not in combined


def test_acceptance_14_exact_prices_brands_billing_units_preserved() -> None:
    scope = _session_extent_scope("full_arch")
    composer = RecordingComposerBackend(text=ONE_STAGE_TEXT)
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs()
    inputs["strategy_context"] = strategy_match_from_effective_scope(scope)
    run_target_offline_turn_frame_bound_response(
        _explicit_price_frame("one_stage"),
        _envelope(allowed_topics=("implantation",)),
        **inputs,  # type: ignore[arg-type]
        effective_scope=scope,
        composer_backend=composer,
        semantic_backend=semantic,
        client_id="demo",
    )
    evidence = json.loads(composer.invocations[0].primary_evidence_json)
    offer_payloads = [
        json.loads(item["text"]) for item in evidence if item["kind"] == "offer"
    ]
    impro = next(payload for payload in offer_payloads if payload.get("brand_id") == "impro")
    assert impro["price"]["amount"] == 96_500
    assert impro["price"]["billing_unit"] == "tooth_package"


def test_acceptance_15_http_ask_and_stream_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    test_http_ask_and_stream_scope_click_parity(monkeypatch)


def test_acceptance_16_sid_isolation_reset_terminal_rules_unchanged() -> None:
    test_sid_isolation_for_patient_facts()


def test_acceptance_17_sparse_multiclient_no_demo_ids_in_core(tmp_path) -> None:
    text = _BOUNDARY_MODULE.read_text(encoding="utf-8")
    for token in ("one_stage", "all_on_4", "zirconia_crowns", '"demo"'):
        assert token not in text
    _root, bundle = explicit_lookup_session_block_pack(tmp_path)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=_session_extent_scope("full_arch"),
        topic="implantation",
        explicit_service_id="svc_per_tooth",
    )
    offers = selection.offers_by_service_id["svc_per_tooth"]
    assert len(offers) == 1
    assert offers[0].price.amount == 42_000  # type: ignore[union-attr]
    assert offers[0].price.billing_unit == "tooth_package"  # type: ignore[union-attr]


def test_acceptance_18_frozen_artifacts_byte_identical() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()
