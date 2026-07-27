"""Offline tests for S62 correction (session hydration, CTA, harness gates)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import uuid

import pytest
from flask import Flask

from core.target_runtime_session import TargetRuntimeSessionState
from core.target_runtime_turn_frame_hydration import (
    hydrate_target_runtime_turn_frame_from_session,
)
from core.target_runtime_widget import build_target_runtime_widget_cta

from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.turn_frame_from_raw import build_turn_frame_from_raw
from evals.v5.fullcontext_response_eval_contract import sha256_file_hex
from evals.v5.fullcontext_quality_eval_contract import assert_frozen_prior_artifacts_unchanged
from evals.v5.s62_target_runtime_live_contract import LIVE_RESULT_ARTIFACT_PATH
from evals.v5.s62_target_runtime_live_harness import (
    _evaluate_summary,
    _pick_displayed_followup,
)
from evals.v5.s62_target_runtime_live_provider_audit import ProviderAuditState
from evals.v5.s62_target_runtime_live_recompute import recompute_frozen_live_verdict
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
from orchestration.planner_turn import PlannerTurnOutcome
from contracts.ask_orchestration import AskOrchestrationResult
from tests.test_target_boundary_enforced_fullcontext_response import (
    PRICE_TEXT,
    RecordingComposerBackend,
    RecordingSemanticBackend,
)


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


def test_hydrate_doctors_followup_from_session() -> None:
    frame = _frame()
    session = TargetRuntimeSessionState(
        last_service_id="all_on_4",
        last_topic="implantation",
        last_primary_aspect="overview",
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
        shown_video_ids=(),
        shown_content_followup_refs=(),
        shown_price_followup_refs=(),
        situation_offered=False,
        service_focus_set_at_turn=0,
        session_turn_count=0,
        followups=(),
    )
    hydrated = hydrate_target_runtime_turn_frame_from_session(
        frame,
        user_message="А кто делает?",
        session_state=session,
        allowed_service_ids=frozenset({"all_on_4"}),
    )
    assert hydrated.service_id == "all_on_4"
    assert hydrated.followup_of == "all_on_4"
    assert hydrated.follow_up is True
    assert hydrated.field_meta.service_id.provenance == "target_runtime_session.last_service_id"


def test_hydrate_price_followup_from_session() -> None:
    frame = _frame(topic="implantation", aspects=["price"], primary_aspect="price")
    session = TargetRuntimeSessionState(
        last_service_id="all_on_4",
        last_topic="implantation",
        last_primary_aspect="overview",
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
        shown_video_ids=(),
        shown_content_followup_refs=(),
        shown_price_followup_refs=(),
        situation_offered=False,
        service_focus_set_at_turn=0,
        session_turn_count=0,
        followups=(),
    )
    hydrated = hydrate_target_runtime_turn_frame_from_session(
        frame,
        user_message="А сколько стоит?",
        session_state=session,
        allowed_service_ids=frozenset({"all_on_4"}),
    )
    assert hydrated.service_id == "all_on_4"


def test_hydrate_payment_followup_from_session() -> None:
    frame = _frame(topic="implantation", aspects=["payment"], primary_aspect="payment")
    session = TargetRuntimeSessionState(
        last_service_id="all_on_4",
        last_topic="implantation",
        last_primary_aspect="price",
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
        shown_video_ids=(),
        shown_content_followup_refs=(),
        shown_price_followup_refs=(),
        situation_offered=False,
        service_focus_set_at_turn=0,
        session_turn_count=0,
        followups=(),
    )
    hydrated = hydrate_target_runtime_turn_frame_from_session(
        frame,
        user_message="А как оплатить?",
        session_state=session,
        allowed_service_ids=frozenset({"all_on_4"}),
    )
    assert hydrated.service_id == "all_on_4"


def test_fresh_clinic_doctors_question_not_hydrated() -> None:
    frame = _frame()
    session = TargetRuntimeSessionState(
        last_service_id="all_on_4",
        last_topic="implantation",
        last_primary_aspect="overview",
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
        shown_video_ids=(),
        shown_content_followup_refs=(),
        shown_price_followup_refs=(),
        situation_offered=False,
        service_focus_set_at_turn=0,
        session_turn_count=0,
        followups=(),
    )
    hydrated = hydrate_target_runtime_turn_frame_from_session(
        frame,
        user_message="Какие врачи работают в клинике?",
        session_state=session,
        allowed_service_ids=frozenset({"all_on_4"}),
    )
    assert hydrated.service_id is None


def test_cta_plan_price_doctor_mapping() -> None:
    plan = build_target_runtime_widget_cta(client_id="demo", selected_cta_key="plan")
    price = build_target_runtime_widget_cta(client_id="demo", selected_cta_key="price")
    doctor = build_target_runtime_widget_cta(client_id="demo", selected_cta_key="doctor")
    assert plan == {"text": "Составить план лечения", "action": "lead", "key": "plan"}
    assert price == {"text": "Уточнить стоимость", "action": "lead", "key": "price"}
    assert doctor == {"text": "Записаться к врачу", "action": "lead", "key": "doctor"}


def test_invalid_cta_key_returns_none() -> None:
    assert build_target_runtime_widget_cta(client_id="demo", selected_cta_key="nope") is None


def test_medical_handoff_selected_cta_key_absent_returns_none() -> None:
    assert build_target_runtime_widget_cta(client_id="demo", selected_cta_key=None) is None
    assert build_target_runtime_widget_cta(client_id="demo", selected_cta_key="") is None


def test_pick_displayed_followup_prefers_first_visible() -> None:
    picked = _pick_displayed_followup(
        [{"label": "Кому подходит All-on-4", "ref": "implantation__service__all_on_4.md#x"}]
    )
    assert picked is not None
    assert picked["label"] == "Кому подходит All-on-4"


def test_corrected_summary_flags_frozen_live_failures() -> None:
    payload = json.loads(LIVE_RESULT_ARTIFACT_PATH.read_text(encoding="utf-8"))
    audit = ProviderAuditState()
    audit.total_started = 10
    audit.role_totals.update(
        {
            "ingress": 0,
            "planner": 0,
            "medical_boundary": 4,
            "composer": 3,
            "semantic_verifier": 3,
        }
    )
    summary = _evaluate_summary(payload["turn_results"], audit)
    assert summary["automated_verdict"] == "AUTOMATED_FAIL"
    assert summary["technical"]["followup_ref_pass"] is False
    assert summary["technical"]["doctors_materialized"] is False


def test_frozen_s62_recompute_returns_fail_without_mutation() -> None:
    before = LIVE_RESULT_ARTIFACT_PATH.read_bytes()
    result = recompute_frozen_live_verdict()
    after = LIVE_RESULT_ARTIFACT_PATH.read_bytes()
    assert before == after
    assert result["frozen_automated_verdict"] == "AUTOMATED_PASS"
    assert result["corrected_automated_verdict"] == "AUTOMATED_FAIL"


def test_frozen_prior_artifacts_and_s62_result_pin_unchanged() -> None:
    assert_frozen_prior_artifacts_unchanged()
    assert (
        sha256_file_hex(LIVE_RESULT_ARTIFACT_PATH)
        == "1091fff43615e9a9adb43bf492dabb46009636eed23d92eac95d8a6073b2a428"
    )


def test_provider_audit_counts_ingress_planner_with_module_rebind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from evals.v5.s62_target_runtime_live_contract import build_attempt_marker_payload, create_attempt_marker_exclusive
    from evals.v5.s62_target_runtime_live_provider_audit import (
        install_provider_audit,
        set_current_turn,
        uninstall_provider_audit,
    )

    marker = tmp_path / "attempt.json"
    ledger = tmp_path / "ledger.jsonl"
    create_attempt_marker_exclusive(marker, build_attempt_marker_payload(baseline_commit="x"))
    import ingress_gate
    import llm

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
    set_current_turn(1)
    ingress_gate.chat_completions_create(model="qwen3.6-flash", messages=[])
    from evals.v5.s62_target_runtime_live_provider_audit import get_audit_state

    assert get_audit_state().role_totals["ingress"] == 1
    uninstall_provider_audit()


@pytest.mark.parametrize(
    "route,expected_fail",
    [
        ("target_fullcontext_terminal_defer", True),
        ("target_fullcontext_materialized", False),
    ],
)
def test_terminal_doctors_route_triggers_automated_fail(route: str, expected_fail: bool) -> None:
    turn_results = [
        {
            "turn_id": "s62_turn_03_doctors",
            "meta": {"service_route": route},
            "gates": {"flags": {"http_completed": True, "target_answer_path": True}},
        }
    ]
    audit = ProviderAuditState()
    audit.total_started = 18
    audit.role_totals.update(
        {
            "ingress": 4,
            "planner": 4,
            "medical_boundary": 4,
            "composer": 3,
            "semantic_verifier": 3,
        }
    )
    summary = _evaluate_summary(turn_results, audit)
    if expected_fail:
        assert summary["automated_verdict"] == "AUTOMATED_FAIL"
    else:
        assert summary["technical"]["doctors_materialized"] is True


def test_doctors_runtime_materialized_with_session_hydration(flask_ctx) -> None:
    from core.target_runtime_turn import run_target_fullcontext_runtime_turn
    from session import mem_reset

    sid = "s62-doctors-hydrate"
    mem_reset(sid)
    _seed_target_runtime_state(
        sid,
        last_service_id="all_on_4",
        last_topic="implantation",
    )
    frame = _frame()
    _install_turn_frame(frame)
    composer, semantic, boundary = (
        RecordingComposerBackend(DOCTORS_TEXT),
        RecordingSemanticBackend(),
        RecordingBoundaryBackend(BackendPayload(decision="none", confidence=0.95)),
    )
    outcome = run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid=sid,
        user_message="А кто делает?",
        composer_backend=composer,
        semantic_backend=semantic,
        boundary_backend=boundary,
    )
    assert outcome.widget.kind == "materialized"
    assert composer.invocations
    assert boundary.invocations


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        from flask import request

        request.ctx = {}
        yield


def test_http_followup_ref_click_target_only(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s62corr-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(
            ref="implantation__service__all_on_4.md#komu-podhodit-all-on-4",
            label="Кому подходит All-on-4",
        ),
    )
    captured: dict[str, str] = {}
    composer, semantic, boundary = _fake_backends()

    def target_turn(**kwargs):
        captured["q"] = kwargs["q"]
        return _fake_target_turn_factory(composer, semantic, boundary)(**kwargs)

    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target_turn)
    monkeypatch.setattr(
        app_module,
        "run_planner_turn",
        lambda **k: PlannerTurnOutcome("content", None),
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
    assert composer.invocations


def test_http_stream_target_only(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    monkeypatch.setattr(
        app_module,
        "_orchestrate_ask_turn",
        lambda data: AskOrchestrationResult(
            kind="service_reply",
            q="q",
            sid="sid-s62-stream",
            client_id="demo",
            service_payload={
                "answer": "verified target",
                "quick_replies": [],
                "meta": {"service_route": "target_fullcontext_materialized"},
            },
            service_route="target_fullcontext_materialized",
        ),
    )
    client = app_module.app.test_client()
    resp = client.post(
        "/ask/stream",
        json={"q": "q", "sid": "sid-s62-stream", "client_id": "demo"},
    )
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "event: ui" in text
    assert "event: done" in text
    assert "verified target" in text


def test_provider_audit_records_all_five_roles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from evals.v5.s62_target_runtime_live_contract import build_attempt_marker_payload, create_attempt_marker_exclusive
    from evals.v5.s62_target_runtime_live_provider_audit import (
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
    from evals.v5 import s62_target_runtime_live_provider_audit as audit_module

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
