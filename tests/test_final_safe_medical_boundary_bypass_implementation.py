"""PERF-2 implementation acceptance matrix: FINAL_SAFE_MEDICAL_BOUNDARY_BYPASS.

23-scenario acceptance matrix from
docs/evidence/performance/FINAL_SAFE_MEDICAL_BOUNDARY_BYPASS_SEAM_AUDIT.md §13, plus
resolver-level implementation guards (the pure resolver never reads raw text/regex/demo
IDs, the Literal has exactly two members, the resolver cannot return a third value).

Two layers:
  - Pure resolver unit tests (no Flask, no backends) for the exact eligibility checklist
    and its fail-safe-to-`required` behavior on any mismatch/exception.
  - Integration tests via `run_target_fullcontext_runtime_turn` (direct) and the real
    `/ask` + `/ask/stream` HTTP surface (governed click flowing through the real
    pre-resolver + typed UI planner) for Boundary-call-count, PERF-0 trace, PERF-1 SSE,
    Verifier behavior, and endpoint parity.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass

import pytest
from flask import Flask, request

from contracts.planner_attempt import PlannerAttempt
from contracts.target_medical_boundary_requirement import TargetMedicalBoundaryRequirement
from contracts.turn_frame import FieldMeta
from contracts.ui_scope_action import UiScopeAction, build_ui_scope_ref
from contracts.ui_stage_action import UiStageAction, build_ui_stage_ref
from core.runtime_turn_frame import publish_planner_attempt_frame
from core.target_medical_boundary_requirement import resolve_target_medical_boundary_requirement
from core.target_response_verifier import TargetSemanticAssessment, TargetSemanticIssue
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.target_runtime_session import read_target_runtime_session
from core.target_runtime_turn import run_target_fullcontext_runtime_turn
from core.target_typed_ui_turn_frame import (
    build_typed_ui_turn_frame_from_scope_action,
    build_typed_ui_turn_frame_from_stage_action,
)
from orchestration.planner_turn import PlannerTurnOutcome
from session import mem_reset
from tests.test_s61_correction_target_runtime import (
    BackendPayload,
    RecordingBoundaryBackend,
    _seed_followups,
    _turn_frame as _free_text_turn_frame,
)
from tests.test_target_boundary_enforced_fullcontext_response import (
    PERSONAL_MEDICAL_REJECT_TEXT,
    PRICE_TEXT,
    RecordingComposerBackend,
    RecordingSemanticBackend,
)

RESOLVER_SOURCE_PATH = "core/target_medical_boundary_requirement.py"

# No numeric/money claims -- avoids tripping the (unrelated, still-active) deterministic
# Verifier's numeric-grounding check for scenarios that aren't about grounding at all.
NEUTRAL_TEXT = (
    "Такой вариант возможен. Точную стоимость и детали уточнит врач на консультации."
)


def _install_turn_frame(frame) -> None:
    publish_planner_attempt_frame(attempt=PlannerAttempt(frame=frame, status="ok"))


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        yield


def _governed_scope_click(*, topic: str = "implantation", extent: str = "one_tooth"):
    ref = build_ui_scope_ref(topic=topic, extent=extent)
    action = UiScopeAction(extent=extent, topic=topic, ref=ref)  # type: ignore[arg-type]
    frame = build_typed_ui_turn_frame_from_scope_action(action)
    return action, frame


def _governed_stage_click(*, topic: str = "implantation", stage: str = "natural_tooth_present"):
    ref = build_ui_stage_ref(topic=topic, stage=stage)  # type: ignore[arg-type]
    action = UiStageAction(stage=stage, topic=topic, ref=ref)  # type: ignore[arg-type]
    frame = build_typed_ui_turn_frame_from_stage_action(action)
    return action, frame


# --- Part A: pure resolver unit tests (rows 6/22, 7/23, 8, 9, 10 + guards) -------------


def test_resolver_literal_has_exactly_two_members() -> None:
    import typing

    args = typing.get_args(TargetMedicalBoundaryRequirement)
    assert set(args) == {"required", "bypass_governed_ui"}


def test_row1_valid_scope_click_resolves_bypass() -> None:
    action, frame = _governed_scope_click()
    result = resolve_target_medical_boundary_requirement(
        turn_frame=frame, current_ui_scope_action=action, current_ui_stage_action=None
    )
    assert result == "bypass_governed_ui"


def test_row2_valid_stage_click_resolves_bypass() -> None:
    action, frame = _governed_stage_click()
    result = resolve_target_medical_boundary_requirement(
        turn_frame=frame, current_ui_scope_action=None, current_ui_stage_action=action
    )
    assert result == "bypass_governed_ui"


def test_row22_both_actions_present_xor_violation_required() -> None:
    scope_action, frame = _governed_scope_click()
    stage_action, _ = _governed_stage_click()
    result = resolve_target_medical_boundary_requirement(
        turn_frame=frame,
        current_ui_scope_action=scope_action,
        current_ui_stage_action=stage_action,
    )
    assert result == "required"


def test_neither_action_present_required() -> None:
    _, frame = _governed_scope_click()
    result = resolve_target_medical_boundary_requirement(
        turn_frame=frame, current_ui_scope_action=None, current_ui_stage_action=None
    )
    assert result == "required"


def test_row23_provenance_mismatch_required() -> None:
    action, frame = _governed_scope_click()
    other_ref = build_ui_scope_ref(topic="implantation", extent="few_teeth")
    wrong_meta = FieldMeta(confidence=1.0, provenance=f"governed_ui_action:{other_ref}", status="valid")
    tampered = frame.model_copy(
        update={
            "field_meta": frame.field_meta.model_copy(update={"intent": wrong_meta}),
        }
    )
    result = resolve_target_medical_boundary_requirement(
        turn_frame=tampered, current_ui_scope_action=action, current_ui_stage_action=None
    )
    assert result == "required"


def test_provenance_prefix_only_match_is_not_enough_required() -> None:
    """Exact match required -- a provenance that merely *starts with* the right prefix must not pass."""
    action, frame = _governed_scope_click()
    sneaky_meta = FieldMeta(
        confidence=1.0,
        provenance=f"governed_ui_action:{action.ref}/extra",
        status="valid",
    )
    tampered = frame.model_copy(
        update={"field_meta": frame.field_meta.model_copy(update={"aspects": sneaky_meta})}
    )
    result = resolve_target_medical_boundary_requirement(
        turn_frame=tampered, current_ui_scope_action=action, current_ui_stage_action=None
    )
    assert result == "required"


@pytest.mark.parametrize("field_name", ["intent", "aspects", "primary_aspect", "needs_clarification"])
@pytest.mark.parametrize("bad_status", ["missing", "defaulted"])
def test_row8_metadata_status_not_valid_required(field_name: str, bad_status: str) -> None:
    action, frame = _governed_scope_click()
    original = getattr(frame.field_meta, field_name)
    degraded = FieldMeta(confidence=0.0, provenance=original.provenance, status=bad_status)  # type: ignore[arg-type]
    tampered = frame.model_copy(
        update={"field_meta": frame.field_meta.model_copy(update={field_name: degraded})}
    )
    result = resolve_target_medical_boundary_requirement(
        turn_frame=tampered, current_ui_scope_action=action, current_ui_stage_action=None
    )
    assert result == "required"


def test_row8_metadata_status_invalid_required() -> None:
    action, frame = _governed_scope_click()
    original = frame.field_meta.needs_clarification
    invalid_meta = FieldMeta(
        confidence=0.0,
        provenance=original.provenance,
        status="invalid",
        error="needs_clarification_invalid_type",
    )
    tampered = frame.model_copy(
        update={"field_meta": frame.field_meta.model_copy(update={"needs_clarification": invalid_meta})}
    )
    result = resolve_target_medical_boundary_requirement(
        turn_frame=tampered, current_ui_scope_action=action, current_ui_stage_action=None
    )
    assert result == "required"


def test_row9_topic_action_mismatch_required() -> None:
    action, frame = _governed_scope_click(topic="implantation")
    tampered = frame.model_copy(update={"topic": "prosthetics"})
    result = resolve_target_medical_boundary_requirement(
        turn_frame=tampered, current_ui_scope_action=action, current_ui_stage_action=None
    )
    assert result == "required"


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("intent", "content"),
        ("aspects", ["price", "warranty"]),
        ("primary_aspect", "warranty"),
        ("needs_clarification", True),
    ],
)
def test_row10_modified_required_field_falls_back_to_required(field_name: str, value: object) -> None:
    action, frame = _governed_scope_click()
    tampered = frame.model_copy(update={field_name: value})
    result = resolve_target_medical_boundary_requirement(
        turn_frame=tampered, current_ui_scope_action=action, current_ui_stage_action=None
    )
    assert result == "required"


def test_row12_ambiguous_invalid_turn_frame_required() -> None:
    """A structurally broken/unexpected turn_frame object must fail safe, not raise."""

    class _NotATurnFrame:
        pass

    action, _ = _governed_scope_click()
    result = resolve_target_medical_boundary_requirement(
        turn_frame=_NotATurnFrame(),  # type: ignore[arg-type]
        current_ui_scope_action=action,
        current_ui_stage_action=None,
    )
    assert result == "required"


def test_resolver_source_has_no_regex_import() -> None:
    text = (
        __import__("pathlib")
        .Path(RESOLVER_SOURCE_PATH)
        .read_text(encoding="utf-8")
    )
    assert "import re" not in text
    assert "re.compile" not in text
    assert "re.match" not in text
    assert "re.search" not in text


def test_resolver_source_has_no_raw_text_param_or_demo_ids() -> None:
    import inspect

    from core import target_medical_boundary_requirement as resolver_module

    sig = inspect.signature(resolver_module.resolve_target_medical_boundary_requirement)
    params = set(sig.parameters)
    assert params == {"turn_frame", "current_ui_scope_action", "current_ui_stage_action"}
    text = (
        __import__("pathlib")
        .Path(RESOLVER_SOURCE_PATH)
        .read_text(encoding="utf-8")
    )
    # Functional hardcode checks (not a bare-word ban -- the module's own docstring
    # legitimately explains these constraints in prose, e.g. "no demo/service/client
    # ID hardcoding").
    for forbidden in (
        '"all_on_4"',
        "'all_on_4'",
        '"demo"',
        "'demo'",
        "import session",
        "from session",
        "import flask",
        "from flask",
        "request.ctx",
        "user_message",
        "raw_text",
    ):
        assert forbidden not in text, forbidden


def test_resolver_never_returns_a_third_value() -> None:
    """Fuzz a handful of malformed/partial inputs -- every result must be one of the two members."""
    action, frame = _governed_scope_click()
    stage_action, stage_frame = _governed_stage_click()
    candidates = [
        (frame, action, None),
        (stage_frame, None, stage_action),
        (frame, None, None),
        (frame, action, stage_action),
        (frame.model_copy(update={"intent": "unknown"}), action, None),
        (object(), action, None),
        (frame, object(), None),
    ]
    for turn_frame, scope, stage in candidates:
        result = resolve_target_medical_boundary_requirement(
            turn_frame=turn_frame,  # type: ignore[arg-type]
            current_ui_scope_action=scope,  # type: ignore[arg-type]
            current_ui_stage_action=stage,  # type: ignore[arg-type]
        )
        assert result in ("required", "bypass_governed_ui"), result


# --- Part B: integration via run_target_fullcontext_runtime_turn (direct) --------------


def _run_direct(
    *,
    sid: str,
    frame,
    user_message: str,
    scope_action: UiScopeAction | None = None,
    stage_action: UiStageAction | None = None,
    composer_text: str = NEUTRAL_TEXT,
    semantic_assessment: TargetSemanticAssessment | None = None,
    boundary_backend: RecordingBoundaryBackend | None = None,
):
    if scope_action is not None:
        request.ctx["current_ui_scope_action"] = scope_action.model_dump()
    if stage_action is not None:
        request.ctx["current_ui_stage_action"] = stage_action.model_dump()
    _install_turn_frame(frame)
    boundary = boundary_backend or RecordingBoundaryBackend(BackendPayload("none", 0.95))
    composer = RecordingComposerBackend(composer_text)
    semantic = RecordingSemanticBackend(assessment=semantic_assessment)
    outcome = run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid=sid,
        user_message=user_message,
        composer_backend=composer,
        semantic_backend=semantic,
        boundary_backend=boundary,
    )
    return outcome, boundary, composer, semantic


def test_row1_direct_governed_scope_click_boundary_calls_zero(flask_ctx) -> None:
    sid = f"perf2-scope-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    action, frame = _governed_scope_click()
    outcome, boundary, composer, semantic = _run_direct(
        sid=sid, frame=frame, user_message="продолжить", scope_action=action
    )
    assert boundary.invocations == []
    assert len(composer.invocations) == 1
    assert len(semantic.invocations) == 1
    assert outcome.widget.kind == "materialized"


def test_row2_direct_governed_stage_click_boundary_calls_zero(flask_ctx) -> None:
    sid = f"perf2-stage-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    action, frame = _governed_stage_click()
    outcome, boundary, composer, semantic = _run_direct(
        sid=sid, frame=frame, user_message="продолжить", stage_action=action
    )
    assert boundary.invocations == []
    assert len(composer.invocations) == 1
    assert len(semantic.invocations) == 1
    assert outcome.widget.kind == "materialized"


def test_row6_cross_turn_price_followup_governed_click_bypasses(flask_ctx) -> None:
    """A governed click referencing a prior turn's followup is still just a governed click."""
    sid = f"perf2-followup-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    action, frame = _governed_scope_click(topic="implantation", extent="few_teeth")
    outcome, boundary, composer, semantic = _run_direct(
        sid=sid, frame=frame, user_message="продолжить", scope_action=action
    )
    assert boundary.invocations == []
    assert outcome.widget.kind == "materialized"


@pytest.mark.parametrize(
    "label,message",
    [
        ("row4_direct_exact_price", "Сколько стоит консультация?"),
        ("row5_broad_family_price", "Сколько стоит имплантация в целом?"),
        ("row7_exact_faq", "Что такое All-on-4?"),
        ("row8_suitability", "Подойдёт ли мне All-on-4?"),
        ("row9_complication", "Вдруг имплант не приживётся?"),
        ("row10_post_op_pain", "После имплантации болит"),
        ("row11_contraindication", "Можно ли имплантацию при диабете?"),
        ("row13_generic_microfact", "Сколько лет клинике?"),
        ("marketing_concern_pain_fear", "Я боюсь боли при имплантации"),
    ],
)
def test_free_text_paths_boundary_calls_one(flask_ctx, label: str, message: str) -> None:
    sid = f"perf2-{label}-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    frame = _free_text_turn_frame()
    outcome, boundary, composer, semantic = _run_direct(sid=sid, frame=frame, user_message=message)
    assert len(boundary.invocations) == 1, label
    assert boundary.invocations[0].user_message == message, label


def test_row12_ambiguous_frame_no_governed_action_boundary_calls_one(flask_ctx) -> None:
    """Ambiguous/unclear-intent frame, no governed action at all -> ordinary required path.

    (Structurally invalid/missing field_meta -> required is already covered directly at the
    pure-resolver level in Part A -- PlannerAttempt itself forbids publishing an "ok" frame
    with invalid/missing metadata, so that exact shape cannot reach the runtime pipeline this
    way. This test covers the other half: a frame whose *content* is ambiguous/low-signal but
    structurally valid, with no governed UI action present at all.)
    """
    sid = f"perf2-ambiguous-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    frame = _free_text_turn_frame(route="unknown")
    outcome, boundary, composer, semantic = _run_direct(
        sid=sid, frame=frame, user_message="непонятный вопрос про зубы"
    )
    assert len(boundary.invocations) == 1


def test_row16_boundary_backend_failure_on_required_path_unaffected(flask_ctx) -> None:
    class _RaisingBoundaryBackend:
        def classify(self, invocation, /):
            raise RuntimeError("backend down")

    sid = f"perf2-boundary-fail-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    frame = _free_text_turn_frame()
    outcome, boundary, composer, semantic = _run_direct(
        sid=sid,
        frame=frame,
        user_message="Сколько стоит имплант?",
        boundary_backend=_RaisingBoundaryBackend(),  # type: ignore[arg-type]
    )
    # Boundary "uncertain, backend failure" is fail-closed -> terminal defer, not a crash.
    assert outcome.widget.kind != "materialized"
    assert len(composer.invocations) == 0
    assert len(semantic.invocations) == 0


def test_row17_numeric_verifier_still_runs_after_bypass_blocks_ungrounded_price(flask_ctx) -> None:
    sid = f"perf2-numeric-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    action, frame = _governed_scope_click()
    ungrounded_text = "Стоимость — 999 999 рублей."
    outcome, boundary, composer, semantic = _run_direct(
        sid=sid,
        frame=frame,
        user_message="продолжить",
        scope_action=action,
        composer_text=ungrounded_text,
    )
    assert boundary.invocations == []
    assert outcome.widget.kind != "materialized"


def test_row18_semantic_verifier_blocks_personal_diagnosis_after_bypass(flask_ctx) -> None:
    sid = f"perf2-semantic-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    action, frame = _governed_scope_click()
    assessment = TargetSemanticAssessment(
        issues=(TargetSemanticIssue(kind="personal_medical_conclusion", offending_span="x"),),
    )
    outcome, boundary, composer, semantic = _run_direct(
        sid=sid,
        frame=frame,
        user_message="продолжить",
        scope_action=action,
        composer_text=PERSONAL_MEDICAL_REJECT_TEXT,
        semantic_assessment=assessment,
    )
    assert boundary.invocations == []
    assert len(semantic.invocations) == 1
    assert outcome.widget.kind != "materialized"
    assert PERSONAL_MEDICAL_REJECT_TEXT not in json.dumps(outcome.widget.payload, ensure_ascii=False)


def test_row22_direct_both_actions_present_boundary_calls_one(flask_ctx) -> None:
    """Even if both action objects were somehow present, the runtime path still requires Boundary."""
    sid = f"perf2-xor-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    scope_action, frame = _governed_scope_click()
    stage_action, _ = _governed_stage_click()
    outcome, boundary, composer, semantic = _run_direct(
        sid=sid,
        frame=frame,
        user_message="продолжить",
        scope_action=scope_action,
        stage_action=stage_action,
    )
    assert len(boundary.invocations) == 1


def test_row23_direct_provenance_mismatch_boundary_calls_one(flask_ctx) -> None:
    sid = f"perf2-provenance-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    action, frame = _governed_scope_click()
    other_ref = build_ui_scope_ref(topic="implantation", extent="full_arch")
    wrong_meta = FieldMeta(confidence=1.0, provenance=f"governed_ui_action:{other_ref}", status="valid")
    tampered = frame.model_copy(
        update={"field_meta": frame.field_meta.model_copy(update={"needs_clarification": wrong_meta})}
    )
    outcome, boundary, composer, semantic = _run_direct(
        sid=sid, frame=tampered, user_message="продолжить", scope_action=action
    )
    assert len(boundary.invocations) == 1


# --- Part C: PERF-0/PERF-1 trace + HTTP /ask vs /ask/stream (rows 3, 14, 15, 19, 20, 21) --


def test_row14_15_structured_capabilities_unaffected_resolver_not_invoked(flask_ctx, monkeypatch) -> None:
    """Structured clinic_contact/service_availability already skip Boundary before this
    resolver's call site is ever reached -- confirm the resolver import isn't even touched
    for that path by spying on it."""
    import core.target_runtime_turn as runtime_turn_module

    calls: list[str] = []
    real_resolver = runtime_turn_module.resolve_target_medical_boundary_requirement

    def _spy(**kwargs):
        calls.append("called")
        return real_resolver(**kwargs)

    monkeypatch.setattr(runtime_turn_module, "resolve_target_medical_boundary_requirement", _spy)

    sid = f"perf2-contact-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    frame = _free_text_turn_frame(route="content", aspects=["contact_phone"], primary_aspect="contact_phone")
    _install_turn_frame(frame)
    outcome = run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid=sid,
        user_message="Какой у вас телефон?",
        composer_backend=RecordingComposerBackend(PRICE_TEXT),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(BackendPayload("none", 0.95)),
    )
    assert calls == [], "resolver must not be invoked when structured_capability short-circuits first"


def test_row3_18_19_20_21_23_http_governed_scope_click_full_wiring(monkeypatch) -> None:
    import app as app_module
    import orchestration.target_fullcontext_turn as target_turn_module

    captured_turn_complete: list[dict] = []
    real_emit_bot_event = app_module.emit_bot_event

    def _capturing_emit_bot_event(logger, event_name, *, status=None, details=None, **overrides):
        if event_name == "turn_complete":
            captured_turn_complete.append(dict(details or {}))
        return real_emit_bot_event(logger, event_name, status=status, details=details, **overrides)

    monkeypatch.setattr("orchestration.finalize_turn.emit_bot_event", _capturing_emit_bot_event)

    planner_calls = {"n": 0}

    def _counting_planner(**k):
        planner_calls["n"] += 1
        return PlannerTurnOutcome("content", None)

    monkeypatch.setattr(app_module, "run_planner_turn", _counting_planner)

    topic, extent = "implantation", "one_tooth"
    ref = build_ui_scope_ref(topic=topic, extent=extent)  # type: ignore[arg-type]

    results: dict[str, dict] = {}
    traces: dict[str, dict] = {}
    boundary_backends: dict[str, RecordingBoundaryBackend] = {}
    sse_texts: dict[str, str] = {}

    for endpoint in ("/ask", "/ask/stream"):
        captured_turn_complete.clear()
        sid = f"perf2-http-scope-{uuid.uuid4().hex[:8]}"
        mem_reset(sid)
        _seed_followups(sid, TargetRuntimeFollowupItem(ref=ref, label="Один зуб"))

        boundary_backend = RecordingBoundaryBackend(BackendPayload("none", 0.95))
        boundary_backends[endpoint] = boundary_backend

        def _fake_default_backends(_boundary_backend=boundary_backend):
            return (
                RecordingComposerBackend(NEUTRAL_TEXT),
                RecordingSemanticBackend(),
                _boundary_backend,
            )

        monkeypatch.setattr(target_turn_module, "_default_target_runtime_backends", _fake_default_backends)

        client = app_module.app.test_client()
        resp = client.post(endpoint, json={"q": "", "ref": ref, "sid": sid, "client_id": "demo"})
        assert resp.status_code == 200

        if endpoint == "/ask":
            results[endpoint] = resp.get_json()
        else:
            # PERF-1: /ask/stream orchestrates lazily -- must actually drain the body.
            text = resp.data.decode("utf-8")
            sse_texts[endpoint] = text
            assert "event: ui" in text
            assert "event: done" in text
            ui_line = next(
                line for line in text.split("\n") if line.startswith("data: ") and '"answer"' in line
            )
            results[endpoint] = json.loads(ui_line[len("data: ") :])

        assert len(captured_turn_complete) == 1
        traces[endpoint] = captured_turn_complete[0]

    # Row 3: Planner LLM never called for a typed governed click (existing precedent, unaffected).
    assert planner_calls["n"] == 0

    # Row 1/23: Boundary backend never invoked on either endpoint (LLM count -1, eligible path).
    assert boundary_backends["/ask"].invocations == []
    assert boundary_backends["/ask/stream"].invocations == []

    # Row 18: PERF-0 trace shows boundary skipped with the exact reason; composer + both
    # verifiers still completed (still 2 real LLM-bearing stages, not 3).
    for endpoint, detail in traces.items():
        stages = detail.get("stages") or {}
        assert stages.get("boundary", {}).get("status") == "skipped", (endpoint, stages)
        assert stages.get("boundary", {}).get("reason") == "bypass_governed_ui", (endpoint, stages)
        for name in ("composer", "verifier_deterministic", "verifier_semantic"):
            assert stages.get(name, {}).get("status") == "completed", (endpoint, name, stages)

    # Row 20: /ask vs /ask/stream parity -- identical answer + route.
    assert results["/ask"]["answer"] == results["/ask/stream"]["answer"]
    assert results["/ask"]["meta"]["service_route"] == results["/ask/stream"]["meta"]["service_route"]

    # Row 19: no status event ever names an internal stage (boundary/composer/verifier/LLM).
    stream_text = sse_texts["/ask/stream"]
    status_messages = re.findall(r'event: status\ndata: (\{.*?\})\n\n', stream_text)
    assert status_messages, "expected at least the initial status event"
    for raw in status_messages:
        message = json.loads(raw).get("message", "")
        lowered = message.lower()
        for forbidden in ("boundary", "llm", "composer", "verifier"):
            assert forbidden not in lowered, message


def test_row11_invalid_unshown_ref_short_circuits_before_resolver(monkeypatch) -> None:
    import app as app_module
    import core.target_runtime_turn as runtime_turn_module

    calls: list[str] = []
    real_resolver = runtime_turn_module.resolve_target_medical_boundary_requirement

    def _spy(**kwargs):
        calls.append("called")
        return real_resolver(**kwargs)

    monkeypatch.setattr(runtime_turn_module, "resolve_target_medical_boundary_requirement", _spy)
    monkeypatch.setattr(app_module, "run_planner_turn", lambda **k: PlannerTurnOutcome("content", None))

    sid = f"perf2-badref-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    # No followups seeded -- this ref was never shown to this session.
    unshown_ref = build_ui_scope_ref(topic="implantation", extent="full_arch")  # type: ignore[arg-type]

    client = app_module.app.test_client()
    resp = client.post("/ask", json={"q": "", "ref": unshown_ref, "sid": sid, "client_id": "demo"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["meta"]["service_route"] == "target_fullcontext_followup_unknown"
    assert calls == [], "resolver must never be reached for an unshown/invalid ref"


def test_row22_final_payload_route_and_session_unchanged_for_required_path(flask_ctx) -> None:
    """A required (free-text) turn's payload/route/session write must be identical to baseline
    -- PERF-2 changes nothing about the non-eligible path."""
    sid = f"perf2-session-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    frame = _free_text_turn_frame()
    outcome, boundary, composer, semantic = _run_direct(
        sid=sid, frame=frame, user_message="Сколько стоит All-on-4?"
    )
    assert outcome.widget.kind == "materialized"
    assert outcome.widget.payload.get("meta", {}).get("service_route") == "target_fullcontext_materialized"
    after = read_target_runtime_session(sid)
    assert after.last_service_id == "all_on_4"


def test_row1_2_governed_click_session_write_still_happens(flask_ctx) -> None:
    sid = f"perf2-session-click-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    action, frame = _governed_scope_click()
    outcome, boundary, composer, semantic = _run_direct(
        sid=sid, frame=frame, user_message="продолжить", scope_action=action
    )
    assert outcome.widget.kind == "materialized"
    after = read_target_runtime_session(sid)
    assert after.followups, "expected session write to record new followups after a materialized click"
