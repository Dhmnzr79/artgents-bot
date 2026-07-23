"""Offline tests for S63 delta correction (CTA, follow-up, doctors hydration)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from flask import Flask

from core.target_runtime_session import TargetRuntimeSessionState
from core.target_runtime_turn_frame_hydration import (
    hydrate_target_runtime_turn_frame_from_session,
)
from core.target_runtime_widget import build_target_runtime_widget_cta
from core.turn_frame_from_raw import build_turn_frame_from_raw
from evals.v5.s63_target_runtime_live_contract import assert_frozen_s62_live_artifacts_unchanged
from evals.v5.s63_target_runtime_live_harness import evaluate_summary, pick_displayed_followup
from evals.v5.s63_target_runtime_live_provider_audit import ProviderAuditState
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from session import mem_reset
from tests.test_s61_correction_target_runtime import (
    BackendPayload,
    RecordingBoundaryBackend,
    _fake_backends,
    _fake_target_turn_factory,
    _install_turn_frame,
    _seed_followups,
    _seed_target_runtime_state,
)
from tests.test_demo_target_turn_frame_bound_response import DOCTORS_TEXT
from tests.test_target_boundary_enforced_fullcontext_response import (
    PRICE_TEXT,
    RecordingComposerBackend,
    RecordingSemanticBackend,
)
from orchestration.resolver_turn import ResolverTurnOutcome


def _frame(**overrides: object):
    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["overview"],
        "primary_aspect": "overview",
        "service_id": None,
        "topic": "doctors",
        "topic_confidence": 0.95,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=frozenset({"implantation", "doctors"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )


def test_frozen_s62_pins_unchanged() -> None:
    assert_frozen_s62_live_artifacts_unchanged()


def test_cta_plan_mapping() -> None:
    cta = build_target_runtime_widget_cta(client_id="demo", selected_cta_key="plan")
    assert cta == {"text": "Составить план лечения", "action": "lead", "key": "plan"}


def test_invalid_cta_key_fail_closed() -> None:
    assert build_target_runtime_widget_cta(client_id="demo", selected_cta_key="nope") is None


def test_pick_displayed_followup_for_turn2() -> None:
    picked = pick_displayed_followup(
        [{"label": "Кому подходит All-on-4", "ref": "implantation__service__all_on_4.md#x"}]
    )
    assert picked is not None
    assert picked["label"] == "Кому подходит All-on-4"


def test_fresh_clinic_doctors_not_hydrated() -> None:
    frame = _frame()
    session = TargetRuntimeSessionState(
        last_service_id="all_on_4",
        last_topic="implantation",
        last_primary_aspect="overview",
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
        followups=(),
    )
    hydrated = hydrate_target_runtime_turn_frame_from_session(
        frame,
        user_message="Какие врачи работают в клинике?",
        session_state=session,
        allowed_service_ids=frozenset({"all_on_4"}),
    )
    assert hydrated.service_id is None


def test_missing_followup_ref_forces_automated_fail() -> None:
    audit = ProviderAuditState()
    audit.fullcontext_build_count = 1
    audit.role_totals.update({role: 3 for role in audit.role_totals})
    turn_results = [
        {
            "turn_id": "s63_turn_01_all_on_4_info",
            "meta": {"service_route": "target_fullcontext_materialized"},
            "quick_replies": [],
            "gates": {"flags": {"http_completed": True, "target_answer_path": True}},
        },
        {
            "turn_id": "s63_turn_02_followup_ref",
            "followup_ref_used": False,
            "meta": {"service_route": "target_fullcontext_materialized"},
            "gates": {"flags": {"http_completed": True, "target_answer_path": True}},
        },
        {
            "turn_id": "s63_turn_03_doctors",
            "meta": {"service_route": "target_fullcontext_materialized"},
            "session_before": {"last_service_id": "all_on_4"},
            "gates": {"flags": {"http_completed": True, "target_answer_path": True}},
        },
    ]
    summary = evaluate_summary(turn_results, audit, ledger_balanced=True)
    assert summary["automated_verdict"] == "AUTOMATED_FAIL"


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        from flask import request

        request.ctx = {}
        yield


def test_doctors_hydration_runtime_materialized(flask_ctx) -> None:
    from core.target_runtime_turn import run_target_fullcontext_runtime_turn

    sid = "s63-doctors-hydrate"
    mem_reset(sid)
    _seed_target_runtime_state(
        sid,
        last_service_id="all_on_4",
        last_topic="implantation",
    )
    _install_turn_frame(_frame())
    composer = RecordingComposerBackend(DOCTORS_TEXT)
    outcome = run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid=sid,
        user_message="А кто делает?",
        composer_backend=composer,
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(
            BackendPayload(decision="none", confidence=0.95)
        ),
    )
    assert outcome.widget.kind == "materialized"
    assert composer.invocations


def test_http_followup_ref_click_target_only(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s63corr-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(
            ref="implantation__service__all_on_4.md#komu-podhodit-all-on-4",
            label="Кому подходит All-on-4",
        ),
    )
    monkeypatch.setattr(app_module, "TARGET_FULLCONTEXT_DEV", True)
    legacy = MagicMock(side_effect=AssertionError("legacy must not run"))
    monkeypatch.setattr(app_module, "orchestrate_routing_after_resolver", legacy)
    captured: dict[str, str] = {}
    composer, semantic, boundary = _fake_backends()

    def target_turn(**kwargs):
        captured["q"] = kwargs["q"]
        return _fake_target_turn_factory(composer, semantic, boundary)(**kwargs)

    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target_turn)
    monkeypatch.setattr(
        app_module,
        "run_resolver_turn",
        lambda **k: ResolverTurnOutcome("content", None, None, False),
    )
    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={
            "q": "",
            "ref": "implantation__service__all_on_4.md#komu-podhodit-all-on-4",
            "sid": sid,
            "client_id": "demo",
        },
    )
    assert resp.status_code == 200
    assert captured["q"] == "Кому подходит All-on-4"
    legacy.assert_not_called()
    assert composer.invocations


def test_provider_audit_records_all_five_roles(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from evals.v5.s63_target_runtime_live_contract import (
        build_attempt_marker_payload,
        create_attempt_marker_exclusive,
    )
    from evals.v5.s63_target_runtime_live_provider_audit import (
        get_audit_state,
        install_provider_audit,
        reset_audit_state,
        set_current_turn,
        uninstall_provider_audit,
    )

    reset_audit_state()
    uninstall_provider_audit()
    marker = tmp_path / "attempt.json"
    ledger = tmp_path / "ledger.jsonl"
    create_attempt_marker_exclusive(marker, build_attempt_marker_payload(baseline_commit="x"))
    import llm
    from evals.v5 import s63_target_runtime_live_provider_audit as audit_module

    def fake_chat(*, model: str, **kwargs: object):
        class _Msg:
            content = "ok"

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]
            usage = None

        return _Resp()

    monkeypatch.setattr(llm, "chat_completions_create", fake_chat)
    install_provider_audit(attempt_marker_path=marker, call_ledger_path=ledger)
    roles = [
        "ingress",
        "planner",
        "medical_boundary",
        "composer",
        "semantic_verifier",
    ]
    for index, role in enumerate(roles):
        set_current_turn(index + 1)
        monkeypatch.setattr(
            audit_module,
            "_infer_provider_role",
            lambda captured_role=role: captured_role,
        )
        llm.chat_completions_create(model="qwen3.6-flash", messages=[])
    state = get_audit_state()
    assert state.total_started == 5
    for role in roles:
        assert state.role_totals[role] == 1
    uninstall_provider_audit()
