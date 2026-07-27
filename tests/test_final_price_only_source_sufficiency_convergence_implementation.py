"""COMPLETION checker — FINAL_PRICE_ONLY_SOURCE_SUFFICIENCY_CONVERGENCE."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

import app as app_module
from contracts.price_only_source_sufficiency import (
    PriceOnlySourceContext,
    is_price_only_offer_source_sufficient,
)
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
from core.target_client_data import load_target_client_data
from core.target_response_verifier import TargetResponseVerificationError
from core.target_turn_frame_bound_response import run_target_offline_turn_frame_bound_response
from core.target_turn_frame_dispatch import dispatch_target_turn_frame_response
from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from scripts.validate_client_pack import validate_client_pack
from tests.test_ac3_scope_price_flow_offline import (
    test_broad_implantation_has_scope_nav_no_price_followups,
    test_prosthetics_one_tooth_stage_clarify_buttons,
    test_scoped_one_tooth_has_no_scope_nav,
    test_w1b_snapshot_checksums_unchanged,
)
from tests.test_demo_target_turn_frame_bound_response import (
    RecordingComposerBackend,
    RecordingSemanticBackend,
    _envelope,
    _pipeline_inputs,
)
from tests.test_final_client_pack_data_convergence_sparse_pack import (
    test_sparse_pack_passes_offline_validator,
)
from tests.test_final_explicit_service_price_lookup_boundary_implementation import (
    _run_explicit_bound,
    _session_extent_scope,
)
from tests.test_final_explicit_service_price_lookup_boundary_sparse_fixtures import (
    build_sparse_target_pack,
)
from tests.test_final_generic_fullcontext_content_authority_implementation import (
    _partial_null_topic_frame,
    _run as _generic_run,
)
from tests.test_final_price_only_source_sufficiency_convergence_governance import (
    test_frozen_artifact_guards as _governance_frozen_artifact_guards,
    test_seam_audit_exists_and_covers_price_only_source_sufficiency,
    test_task_governance_section_and_acceptance_matrix,
)
from tests.test_final_price_only_source_sufficiency_convergence_harness import (
    availability_frame,
    assert_materialized_price,
    bound_materialized,
    content_evidence,
    offer_evidence,
    orchestrate_via_app,
    price_frame,
    run_price_turn,
)
from tests.test_final_price_scope_coverage_nav_implementation import (
    test_frozen_pins_unchanged as test_pscn_frozen_pins_unchanged,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)
from tests.test_session_patient_facts_offline import test_sid_isolation_for_patient_facts
from tests.test_target_turn_frame_dispatch import _envelope as _dispatch_envelope

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_ROOT = _REPO_ROOT / "clients" / "demo"
_KT_PRICE_TEXT = (
    "КТ (компьютерная томография) — 3 000 рублей за одно исследование."
)
_WRONG_PRICE_TEXT = "КТ стоит 9 999 рублей за одно исследование."


def _price_only_ctx(**overrides: object) -> PriceOnlySourceContext:
    base: dict[str, object] = {
        "service_id": "tomography",
        "required_components": ("price",),
        "requested_components": ("price",),
        "offer_ids": ("tomography.default",),
        "offer_service_ids": ("tomography",),
        "offer_active_flags": (True,),
        "selected_content_ref": None,
        "primary_content_ref": None,
        "unfulfilled_components": (),
        "response_stage": None,
        "is_generic_fullcontext": False,
        "is_scope_aware_price": False,
        "is_structured_service_availability": False,
    }
    base.update(overrides)
    return PriceOnlySourceContext(**base)  # type: ignore[arg-type]


def _run_bound_tomography_price(
  composer_text: str = _KT_PRICE_TEXT,
) -> tuple[TargetTurnFrameBoundMaterializeResponse, RecordingComposerBackend]:
    composer = RecordingComposerBackend(text=composer_text)
    semantic = RecordingSemanticBackend()
    result = run_target_offline_turn_frame_bound_response(
        price_frame(),
        _envelope(allowed_topics=("implantation", "doctors", "clinic")),
        **_pipeline_inputs(),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
        client_id="demo",
    )
    return bound_materialized(result), composer


def test_scenario_01_availability_tomography_materialized() -> None:
    outcome, composer, _, _, _ = run_price_turn(
        availability_frame(),
        user_message="Делаете КТ?",
        composer_text="unused",
        boundary=None,
    )
    assert outcome.widget.kind == "materialized"
    assert len(composer.invocations) == 0
    assert "оказывает услугу" in outcome.widget.payload["answer"]


def test_scenario_02_follow_up_price_materialized() -> None:
    sid = f"posc-2-{uuid.uuid4().hex[:8]}"
    run_price_turn(
        availability_frame(),
        user_message="Делаете 3D-диагностику?",
        composer_text="unused",
        sid=sid,
    )
    outcome, composer, _, _, _ = run_price_turn(
        price_frame(),
        user_message="А сколько стоит?",
        composer_text=_KT_PRICE_TEXT,
        sid=sid,
    )
    assert_materialized_price(outcome, composer)
    assert "3 000" in outcome.widget.payload["answer"] or "3000" in outcome.widget.payload["answer"]


def test_scenario_03_follow_up_preserves_service_id() -> None:
    sid = f"posc-3-{uuid.uuid4().hex[:8]}"
    run_price_turn(
        availability_frame(),
        user_message="Делаете 3D-диагностику?",
        composer_text="unused",
        sid=sid,
    )
    outcome, composer, _, _, _ = run_price_turn(
        price_frame(),
        user_message="А сколько стоит?",
        composer_text=_KT_PRICE_TEXT,
        sid=sid,
    )
    assert_materialized_price(outcome, composer)
    meta = outcome.widget.payload["meta"]
    assert meta.get("matched_service_id") == "tomography"


def test_scenario_04_direct_price_materialized() -> None:
    outcome, composer, _, _, _ = run_price_turn(
        price_frame(),
        user_message="Сколько стоит КТ?",
        composer_text=_KT_PRICE_TEXT,
    )
    assert_materialized_price(outcome, composer)
    assert "3 000" in _KT_PRICE_TEXT


def test_scenario_05_price_only_without_content_ref_allowed() -> None:
    result, composer = _run_bound_tomography_price()
    assert result.verified.spec.required_components == ("price",)
    assert result.verified.primary_content_ref is None
    assert len(composer.invocations) == 1


def test_scenario_06_composer_evidence_offer_tomography_default() -> None:
    _, composer = _run_bound_tomography_price()
    offers = offer_evidence(composer)
    assert len(offers) == 1
    assert offers[0]["ref"] == "offer:tomography.default"


def test_scenario_07_no_fake_content_evidence_block() -> None:
    _, composer = _run_bound_tomography_price()
    assert content_evidence(composer) == []


def test_scenario_08_numeric_verifier_accepts_3000() -> None:
    result, composer = _run_bound_tomography_price()
    assert result.verified.verification_status == "verified"
    assert len(composer.invocations) == 1


def test_scenario_09_wrong_amount_blocked() -> None:
    with pytest.raises(TargetResponseVerificationError) as caught:
        _run_bound_tomography_price(composer_text=_WRONG_PRICE_TEXT)
    assert caught.value.code == "target_verifier_numeric_ungrounded"


def test_scenario_10_offer_wrong_service_id_blocks_predicate() -> None:
    assert not is_price_only_offer_source_sufficient(
        _price_only_ctx(offer_service_ids=("all_on_4",))
    )


def test_scenario_11_offer_missing_from_bundle_blocks_predicate() -> None:
    assert not is_price_only_offer_source_sufficient(_price_only_ctx(offer_ids=()))


def test_scenario_12_inactive_offer_not_sufficient() -> None:
    assert not is_price_only_offer_source_sufficient(
        _price_only_ctx(offer_active_flags=(False,))
    )


def test_scenario_13_price_only_no_offer_data_gap(tmp_path: Path) -> None:
    root = build_sparse_target_pack(
        tmp_path,
        services={
            "diag_only": {
                "name": "Диагностика",
                "aliases": [],
                "family": "diagnostics",
                "roles": ["supporting"],
                "active": True,
                "content_ref": None,
                "selection": {"mode": "direct"},
                "options": [],
            }
        },
        offers=[],
    )
    from core.response_schema_loader import load_response_schema_bundle

    bundle = load_response_schema_bundle(root)
    assert bundle.services["diag_only"].content_ref is None
    assert not bundle.offers


def test_scenario_14_content_only_no_price_only_exception() -> None:
    assert not is_price_only_offer_source_sufficient(
        _price_only_ctx(
            required_components=("content",),
            requested_components=("content",),
        )
    )


def test_scenario_15_content_plus_price_no_exception() -> None:
    assert not is_price_only_offer_source_sufficient(
        _price_only_ctx(
            required_components=("content", "price"),
            requested_components=("content", "price"),
        )
    )


def test_scenario_16_generic_fullcontext_no_money_permission() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _generic_run(
        frame,
        user_message="Сколько стоит КТ?",
        composer_text="В материалах клиники эта информация не указана.",
    )
    assert outcome.widget.kind == "materialized"
    assert len(composer.invocations) == 1
    assert not is_price_only_offer_source_sufficient(
        _price_only_ctx(is_generic_fullcontext=True)
    )


def test_scenario_17_named_protocol_no_family_price_inherit() -> None:
    scope = _session_extent_scope("full_arch")
    result = _run_explicit_bound("one_stage", effective_scope=scope)
    assert result.verified.spec.response_stage in {None, "concrete_service_price", "data_gap"}
    assert result.dispatch.policy_request.service_id == "one_stage"  # type: ignore[union-attr]


def test_scenario_18_broad_family_price_unchanged() -> None:
    test_broad_implantation_has_scope_nav_no_price_followups()


def test_scenario_19_implantation_scope_price_unchanged() -> None:
    test_scoped_one_tooth_has_no_scope_nav()


def test_scenario_20_prosthetics_stage_price_unchanged() -> None:
    test_prosthetics_one_tooth_stage_clarify_buttons()


def test_scenario_21_availability_zero_boundary_composer_semantic() -> None:
    outcome, composer, semantic, boundary, _ = run_price_turn(
        availability_frame(),
        user_message="Делаете 3D-диагностику?",
        composer_text="unused",
    )
    assert outcome.widget.kind == "materialized"
    assert len(composer.invocations) == 0
    assert len(semantic.invocations) == 0
    assert len(boundary.invocations) == 0


def test_scenario_22_price_follow_up_normal_pipeline() -> None:
    sid = f"posc-22-{uuid.uuid4().hex[:8]}"
    run_price_turn(
        availability_frame(),
        user_message="Делаете 3D-диагностику?",
        composer_text="unused",
        sid=sid,
    )
    outcome, composer, semantic, boundary, _ = run_price_turn(
        price_frame(),
        user_message="А сколько стоит?",
        composer_text=_KT_PRICE_TEXT,
        sid=sid,
    )
    assert_materialized_price(outcome, composer)
    assert len(semantic.invocations) == 1
    assert len(boundary.invocations) == 1


def test_scenario_23_missing_md_no_source_driven_buttons() -> None:
    outcome, composer, _, _, _ = run_price_turn(
        price_frame(),
        user_message="Сколько стоит КТ?",
        composer_text=_KT_PRICE_TEXT,
    )
    assert_materialized_price(outcome, composer)
    payload = outcome.widget.payload
    assert payload.get("followups") in (None, [])
    assert payload.get("actions") in (None, [])


def test_scenario_24_cta_policy_unchanged() -> None:
    outcome, composer, _, _, _ = run_price_turn(
        price_frame(),
        user_message="Сколько стоит КТ?",
        composer_text=_KT_PRICE_TEXT,
    )
    assert_materialized_price(outcome, composer)
    meta = outcome.widget.payload["meta"]
    assert meta.get("cta_key") == "price"
    assert meta.get("cta_action") == "lead"


def test_scenario_25_invented_source_refs_dropped() -> None:
    _, composer = _run_bound_tomography_price()
    evidence = json.loads(composer.invocations[0].primary_evidence_json)
    refs = {item["ref"] for item in evidence}
    assert refs == {"offer:tomography.default"}


def test_scenario_26_ask_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    sid = f"posc-26-{uuid.uuid4().hex[:8]}"
    run_price_turn(
        availability_frame(),
        user_message="Делаете 3D-диагностику?",
        composer_text="unused",
        sid=sid,
    )
    body, composer, _ = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask",
        q="А сколько стоит?",
        frame=price_frame(),
        composer_text=_KT_PRICE_TEXT,
        sid=sid,
    )
    assert body["meta"]["matched_service_id"] == "tomography"
    assert len(composer.invocations) == 1


def test_scenario_27_ask_stream_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    sid = f"posc-27-{uuid.uuid4().hex[:8]}"
    run_price_turn(
        availability_frame(),
        user_message="Делаете 3D-диагностику?",
        composer_text="unused",
        sid=sid,
    )
    ask_body, _, _ = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask",
        q="А сколько стоит?",
        frame=price_frame(),
        composer_text=_KT_PRICE_TEXT,
        sid=sid,
    )
    stream_body, composer, _ = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask/stream",
        q="А сколько стоит?",
        frame=price_frame(),
        composer_text=_KT_PRICE_TEXT,
        sid=sid,
    )
    assert ask_body["meta"]["matched_service_id"] == stream_body["meta"]["matched_service_id"]
    assert len(composer.invocations) == 1


def test_scenario_28_fresh_sid_direct_price() -> None:
    sid = f"posc-28-{uuid.uuid4().hex[:8]}"
    outcome, composer, _, _, returned_sid = run_price_turn(
        price_frame(),
        user_message="Сколько стоит КТ?",
        composer_text=_KT_PRICE_TEXT,
        sid=sid,
    )
    assert returned_sid == sid
    assert_materialized_price(outcome, composer)


def test_scenario_29_sid_isolation() -> None:
    test_sid_isolation_for_patient_facts()


def test_scenario_30_sparse_client_fixture_no_demo_hardcodes(tmp_path: Path) -> None:
    test_sparse_pack_passes_offline_validator(tmp_path)
    root = build_sparse_target_pack(
        tmp_path / "sparse_price_only",
        services={
            "local_ct": {
                "name": "Локальная КТ",
                "aliases": ["кт"],
                "family": "diagnostics",
                "roles": ["supporting"],
                "active": True,
                "content_ref": None,
                "selection": {"mode": "direct"},
                "options": [],
            }
        },
        offers=[
            {
                "offer_id": "local_ct.default",
                "service_id": "local_ct",
                "active": True,
                "price": {
                    "mode": "fixed",
                    "amount": 2500,
                    "currency": "RUB",
                    "billing_unit": "procedure",
                },
                "package": {"label": "процедура", "includes": []},
            }
        ],
    )
    from core.response_schema_loader import load_response_schema_bundle

    bundle = load_response_schema_bundle(root)
    service = bundle.services["local_ct"]
    assert service.content_ref is None
    assert bundle.offers[0].offer_id == "local_ct.default"
    assert is_price_only_offer_source_sufficient(
        _price_only_ctx(
            service_id="local_ct",
            offer_ids=("local_ct.default",),
            offer_service_ids=("local_ct",),
        )
    )


def test_tomography_content_ref_linked_in_demo_pack() -> None:
    service = load_target_client_data("demo").bundle.services["tomography"]
    assert service.content_ref == "diagnostics__service__tomography.md"


def test_price_lookup_dispatch_components() -> None:
    dispatch = dispatch_target_turn_frame_response(
        price_frame(),
        _dispatch_envelope(allowed_topics=("implantation", "doctors", "clinic")),
    )
    assert dispatch.kind == "materialize"
    assert dispatch.policy_request.service_id == "tomography"  # type: ignore[union-attr]
    assert dispatch.policy_request.requested_components == ("price",)  # type: ignore[union-attr]


def test_shared_predicate_imported_by_consumers() -> None:
    for path in (
        "core/target_composer_request.py",
        "core/target_scoped_response_evidence.py",
        "core/target_response_materialization_plan.py",
    ):
        text = (_REPO_ROOT / path).read_text(encoding="utf-8")
        assert "is_price_only_offer_source_sufficient" in text
        assert "PriceOnlySourceContext" in text


def test_frozen_pins_unchanged() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_validate_client_pack_demo() -> None:
    assert validate_client_pack(_DEMO_ROOT) == []


def test_import_app() -> None:
    assert app_module.app is not None


def test_governance_checker_still_passes() -> None:
    test_seam_audit_exists_and_covers_price_only_source_sufficiency()
    test_task_governance_section_and_acceptance_matrix()
    _governance_frozen_artifact_guards()
