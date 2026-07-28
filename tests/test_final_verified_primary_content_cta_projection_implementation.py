"""COMPLETION checker — FINAL_VERIFIED_PRIMARY_CONTENT_CTA_PROJECTION."""

from __future__ import annotations

import inspect
import json
import uuid
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import app as app_module
from core.client_config_loader import resolve_lead_name_prompt
from core.target_generic_fullcontext_content import build_generic_fullcontext_content_policy_request
from core.target_response_verifier import (
    TargetSemanticAssessment,
    TargetSemanticIssue,
    TargetVerifiedComposedResponse,
)
from core.target_turn_frame_dispatch import dispatch_target_turn_frame_response
from core.target_verified_primary_content_cta_projection import (
    project_verified_primary_content_cta,
)
from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from session import mem_get, mem_reset
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_final_fullcontext_dialogue_runtime_convergence_harness import (
    BackendPayload,
    MessageBuildingComposerBackend,
    RecordingBoundaryBackend,
    RecordingSemanticBackend,
    assert_materialized_route,
    assert_not_error_route,
    build_frame,
    orchestrate_via_app,
    pipeline_result_materialized,
    run_runtime_turn,
)
from tests.test_final_generic_fullcontext_content_authority_implementation import (
    _partial_null_topic_frame,
)
from tests.test_final_price_only_source_sufficiency_convergence_harness import (
    assert_materialized_price,
    price_frame,
    run_price_turn,
)
from tests.test_final_price_scope_coverage_nav_implementation import (
    test_frozen_pins_unchanged as test_pscn_frozen_pins_unchanged,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)
from tests.test_final_verified_primary_content_cta_projection_governance import (
    test_frozen_artifact_guards as _governance_frozen_artifact_guards,
    test_seam_audit_exists_and_covers_cta_projection_seams,
    test_task_governance_section_present,
    test_verified_primary_cta_projection_normative,
)
from tests.test_target_response_verifier import _request, _spec
from tests.test_target_turn_frame_dispatch import _envelope

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_MD = _REPO_ROOT / "clients" / "demo" / "md"
_NO_CTA_PRIMARY = "generic__faq__no_cta.md"
_ALLOWED_TOPICS = frozenset(
    {"implantation", "doctors", "clinic", "prosthetics", "aesthetics", "whitening"}
)
_ALLOWED_SERVICES = frozenset(
    {
        "all_on_4",
        "classic",
        "sinus_lift",
        "bone_graft",
        "single_implant",
        "tomography",
    }
)

_PAIN_QUESTION = "Я боюсь боли"
_PAIN_PRIMARY = "implantation__faq__pain.md"
_PAIN_ANSWER = (
    "Страх боли при имплантации — нормальная реакция. "
    "Во время операции используется современная прицельная анестезия."
)
_CONSULT_CTA = {"text": "Обсудить вопрос", "action": "lead", "key": "consult"}
_KT_PRICE_TEXT = (
    "КТ (компьютерная томография) — 3 000 рублей за одно исследование."
)


def _pain_frame():
    return _partial_null_topic_frame(
        topic="implantation",
        topic_confidence=0.9,
        aspects=["overview"],
        primary_aspect="overview",
        marketing_scenarios=["pain_fear"],
    )


def _assert_consult_cta(payload: dict) -> None:
    assert payload.get("cta") == _CONSULT_CTA
    meta = payload.get("meta") or {}
    assert meta.get("cta_key") == "consult"
    assert meta.get("cta_action") == "lead"
    assert meta.get("primary_content_ref") == _PAIN_PRIMARY


def _write_no_cta_md(md_root: Path) -> None:
    (md_root / _NO_CTA_PRIMARY).write_text(
        "---\n"
        "doc_id: generic__faq__no_cta\n"
        "doc_type: faq\n"
        "topic: implantation\n"
        "---\n\n"
        "## FAQ без CTA\n\n"
        "### Коротко {#korotko}\n"
        "Ответ без CTA metadata.\n",
        encoding="utf-8",
    )


def _run_pain_turn_with_md_root(
    md_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    user_message: str = _PAIN_QUESTION,
    primary_ref: str | None = _PAIN_PRIMARY,
    sid: str | None = None,
    frame=None,
):
    from core.target_runtime_client_context import load_target_runtime_client_context

    real = load_target_runtime_client_context("demo")

    def _load_context(client_id: str):
        _ = client_id
        return replace(real, md_root=md_root)

    monkeypatch.setattr(
        "core.target_runtime_turn.load_target_runtime_client_context",
        _load_context,
    )
    sid = sid or f"vpcta-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    outcome, composer, semantic = run_runtime_turn(
        sid=sid,
        user_message=user_message,
        composer_text=_PAIN_ANSWER,
        frame=frame or _pain_frame(),
        primary_ref=primary_ref,
    )
    return outcome, composer, semantic, sid


def _run_pain_turn(
    *,
    user_message: str = _PAIN_QUESTION,
    primary_ref: str | None = _PAIN_PRIMARY,
    sid: str | None = None,
):
    sid = sid or f"vpcta-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    outcome, composer, semantic = run_runtime_turn(
        sid=sid,
        user_message=user_message,
        composer_text=_PAIN_ANSWER,
        frame=_pain_frame(),
        primary_ref=primary_ref,
    )
    return outcome, composer, semantic, sid


def _verified(**updates: object) -> TargetVerifiedComposedResponse:
    request = _request()
    base = TargetVerifiedComposedResponse(
        text="answer",
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=None,
    )
    if not updates:
        return base
    return replace(base, **updates)


def test_unit_projection_from_validated_primary() -> None:
    spec = _spec().model_copy(
        update={
            "service_id": None,
            "allow_cta": False,
            "required_components": ("content",),
        }
    )
    verified = project_verified_primary_content_cta(
        _verified(
            spec=spec,
            primary_content_ref=_PAIN_PRIMARY,
            used_content_refs=(_PAIN_PRIMARY,),
        ),
        client_id="demo",
        md_root=_DEMO_MD,
    )
    assert verified.selected_cta_key == "consult"
    assert verified.spec.allow_cta is False


def test_unit_projection_preserves_existing_service_cta() -> None:
    spec = _spec().model_copy(update={"service_id": "classic", "allow_cta": True})
    verified = project_verified_primary_content_cta(
        _verified(
            spec=spec,
            selected_cta_key="plan",
            primary_content_ref=_PAIN_PRIMARY,
        ),
        client_id="demo",
        md_root=_DEMO_MD,
    )
    assert verified.selected_cta_key == "plan"


def test_unit_projection_skips_secondary_used_ref_cta(tmp_path: Path) -> None:
    md_root = tmp_path / "md"
    md_root.mkdir()
    _write_no_cta_md(md_root)
    spec = _spec().model_copy(
        update={
            "service_id": None,
            "allow_cta": False,
            "required_components": ("content",),
        }
    )
    verified = project_verified_primary_content_cta(
        _verified(
            spec=spec,
            primary_content_ref=_NO_CTA_PRIMARY,
            used_content_refs=(_NO_CTA_PRIMARY, _PAIN_PRIMARY),
        ),
        client_id="demo",
        md_root=md_root,
    )
    assert verified.selected_cta_key is None


def test_scenario_01_pain_free_text_shows_consult_cta() -> None:
    outcome, _, _, _ = _run_pain_turn()
    payload = outcome.widget.payload
    assert_materialized_route(payload["meta"])
    assert_not_error_route(payload["meta"])
    _assert_consult_cta(payload)
    materialized = pipeline_result_materialized(outcome)
    assert materialized is not None
    assert materialized.verified.primary_content_ref == _PAIN_PRIMARY
    assert materialized.verified.selected_cta_key == "consult"
    assert materialized.verified.spec.allow_cta is False


def test_scenario_02_starter_prompt_parity() -> None:
    with (_REPO_ROOT / "clients" / "demo" / "widget_config.json").open(
        encoding="utf-8"
    ) as handle:
        starter = json.load(handle)["starterPrompts"][0]["q"]
    assert starter == _PAIN_QUESTION
    outcome, _, _, _ = _run_pain_turn(user_message=starter)
    _assert_consult_cta(outcome.widget.payload)


def test_scenario_03_generic_faq_with_valid_primary_cta() -> None:
    outcome, _, _, _ = _run_pain_turn(
        user_message="Безопасна ли имплантация?",
        primary_ref="implantation__faq__safety.md",
    )
    payload = outcome.widget.payload
    assert payload.get("cta") == _CONSULT_CTA
    assert payload["meta"]["primary_content_ref"] == "implantation__faq__safety.md"
    assert payload["meta"]["cta_key"] == "consult"


def test_scenario_04_generic_faq_without_cta_frontmatter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    md_root = tmp_path / "md"
    md_root.mkdir()
    _write_no_cta_md(md_root)
    outcome, _, _, _ = _run_pain_turn_with_md_root(
        md_root,
        monkeypatch,
        user_message="Есть ли Wi-Fi?",
        primary_ref=_NO_CTA_PRIMARY,
        frame=_partial_null_topic_frame(
            topic="implantation",
            topic_confidence=0.9,
            aspects=["overview"],
            primary_aspect="overview",
        ),
    )
    payload = outcome.widget.payload
    assert payload.get("cta") is None
    meta = payload.get("meta") or {}
    assert meta.get("cta_key") is None
    assert meta.get("primary_content_ref") == _NO_CTA_PRIMARY


def test_scenario_05_missing_primary_keeps_answer_without_cta() -> None:
    outcome, _, _, _ = _run_pain_turn(primary_ref=None)
    payload = outcome.widget.payload
    assert _PAIN_ANSWER in payload["answer"]
    assert payload.get("cta") is None
    assert payload["meta"].get("primary_content_ref") in (None, "")


def test_scenario_06_invented_secondary_ref_does_not_supply_cta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    md_root = tmp_path / "md"
    md_root.mkdir()
    _write_no_cta_md(md_root)
    (md_root / _PAIN_PRIMARY).write_text(
        (_DEMO_MD / _PAIN_PRIMARY).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    outcome, composer, _, _ = _run_pain_turn_with_md_root(
        md_root,
        monkeypatch,
        primary_ref=_NO_CTA_PRIMARY,
        frame=_partial_null_topic_frame(
            topic="implantation",
            topic_confidence=0.9,
            aspects=["overview"],
            primary_aspect="overview",
        ),
    )
    payload = outcome.widget.payload
    assert payload.get("cta") is None
    assert payload["meta"]["primary_content_ref"] == _NO_CTA_PRIMARY
    assert composer.invocations


def test_scenario_07_explicit_service_price_cta_not_replaced() -> None:
    outcome, composer, _, _, _ = run_price_turn(
        price_frame(),
        user_message="Сколько стоит КТ?",
        composer_text=_KT_PRICE_TEXT,
    )
    assert_materialized_price(outcome, composer)
    payload = outcome.widget.payload
    meta = payload["meta"]
    assert meta.get("cta_key") == "price"
    assert payload["cta"]["key"] == "price"
    materialized = pipeline_result_materialized(outcome)
    assert materialized is not None
    assert materialized.verified.selected_cta_key == "price"


def test_scenario_08_terminal_error_handoff_have_no_cta() -> None:
    from flask import Flask, request

    from core.runtime_turn_frame import publish_planner_attempt_frame
    from core.target_runtime_turn import run_target_fullcontext_runtime_turn
    from tests.test_final_fullcontext_dialogue_runtime_convergence_harness import (
        _planner_attempt,
    )

    frame = build_frame(
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
        service_id=None,
        aspects=["price"],
        primary_aspect="price",
        topic_confidence=0.2,
    )
    sid = f"vpcta-term-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    composer = MessageBuildingComposerBackend(_PAIN_ANSWER, primary_ref=_PAIN_PRIMARY)
    semantic = RecordingSemanticBackend()
    boundary = RecordingBoundaryBackend(BackendPayload("none", 0.95))
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        publish_planner_attempt_frame(attempt=_planner_attempt(frame))
        terminal = run_target_fullcontext_runtime_turn(
            client_id="demo",
            sid=sid,
            user_message="Сколько стоит?",
            composer_backend=composer,
            semantic_backend=semantic,
            boundary_backend=boundary,
        )
    assert terminal.widget.payload.get("cta") is None
    assert composer.invocations == []

    sid = f"vpcta-mh-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    composer = MessageBuildingComposerBackend(_PAIN_ANSWER, primary_ref=_PAIN_PRIMARY)
    boundary = RecordingBoundaryBackend(BackendPayload("medical_handoff", 0.92))
    with app.test_request_context():
        request.ctx = {}
        publish_planner_attempt_frame(attempt=_planner_attempt(_pain_frame()))
        handoff = run_target_fullcontext_runtime_turn(
            client_id="demo",
            sid=sid,
            user_message=_PAIN_QUESTION,
            composer_backend=composer,
            semantic_backend=RecordingSemanticBackend(),
            boundary_backend=boundary,
        )
    assert handoff.widget.payload.get("cta") is None

    class RejectingSemanticBackend:
        def assess(self, invocation: object, /) -> object:
            return TargetSemanticAssessment(
                issues=(
                    TargetSemanticIssue(
                        kind="unsupported_clinic_claim",
                        severity="blocking",
                        offending_span="bad",
                    ),
                )
            )

    sid = f"vpcta-ver-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    with app.test_request_context():
        request.ctx = {}
        publish_planner_attempt_frame(attempt=_planner_attempt(_pain_frame()))
        blocked = run_target_fullcontext_runtime_turn(
            client_id="demo",
            sid=sid,
            user_message=_PAIN_QUESTION,
            composer_backend=MessageBuildingComposerBackend(
                _PAIN_ANSWER,
                primary_ref=_PAIN_PRIMARY,
            ),
            semantic_backend=RejectingSemanticBackend(),
            boundary_backend=RecordingBoundaryBackend(BackendPayload("none", 0.95)),
        )
    assert blocked.widget.kind == "error"
    assert blocked.widget.payload.get("cta") is None


def test_scenario_09_cta_click_enters_leadflow_with_consult_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = MagicMock(side_effect=AssertionError("target must not run on CTA click"))
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target)

    sid = f"vpcta-lead-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    client = app_module.app.test_client()
    response = client.post(
        "/ask",
        json={
            "cta_action": "lead",
            "cta_key": "consult",
            "q": "",
            "sid": sid,
            "client_id": "demo",
        },
    )
    assert response.status_code == 200
    target.assert_not_called()
    payload = response.get_json()
    assert payload is not None
    meta = payload.get("meta") or {}
    assert meta.get("lead_flow") is True
    assert meta.get("lead_step") == "name"
    assert "обсудим ваш вопрос с врачом" in payload["answer"].lower()
    assert resolve_lead_name_prompt("demo", cta_key="consult").lower() in payload["answer"].lower()
    assert mem_get(sid).get("lead_intent") == "collecting_name"


def test_scenario_10_ask_and_stream_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    sid = f"vpcta-par-{uuid.uuid4().hex[:10]}"
    ask_body, _, _ = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask",
        q=_PAIN_QUESTION,
        frame=_pain_frame(),
        composer_text=_PAIN_ANSWER,
        primary_ref=_PAIN_PRIMARY,
        sid=sid,
    )
    stream_body, _, _ = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask/stream",
        q=_PAIN_QUESTION,
        frame=_pain_frame(),
        composer_text=_PAIN_ANSWER,
        primary_ref=_PAIN_PRIMARY,
        sid=f"{sid}-stream",
    )
    assert ask_body.get("cta") == stream_body.get("cta") == _CONSULT_CTA
    assert (ask_body.get("meta") or {}).get("cta_key") == "consult"
    assert (stream_body.get("meta") or {}).get("cta_key") == "consult"


def test_generic_allow_cta_policy_unchanged() -> None:
    request = build_generic_fullcontext_content_policy_request(
        response_mode="answer",
        envelope=_envelope(),
    )
    assert request.allow_cta is False
    dispatch = dispatch_target_turn_frame_response(
        _pain_frame(),
        _envelope(),
    )
    assert dispatch.kind == "materialize"
    assert dispatch.policy_request.allow_cta is False


def test_completion_governance_and_frozen_guards() -> None:
    test_seam_audit_exists_and_covers_cta_projection_seams()
    test_task_governance_section_present()
    test_verified_primary_cta_projection_normative()
    _governance_frozen_artifact_guards()


def test_completion_pipeline_wires_projection_after_verify() -> None:
    import core.target_policy_bound_verified_response_pipeline as pipeline_module

    source = inspect.getsource(
        pipeline_module.run_target_offline_policy_bound_verified_response_pipeline_with_selection
    )
    assert "run_target_offline_verified_response_pipeline" in source
    assert "project_verified_primary_content_cta" in source
    assert source.index("run_target_offline_verified_response_pipeline") < source.index(
        "project_verified_primary_content_cta"
    )


def test_completion_frozen_pins_unchanged() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()
