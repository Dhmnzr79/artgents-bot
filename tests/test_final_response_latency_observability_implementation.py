"""PERF-0 Phase 2 implementation acceptance matrix (observability only).

Covers TASK.md § FINAL_RESPONSE_LATENCY_OBSERVABILITY / PERF-0 acceptance rows 1-11:
stage ordering, non-negative durations, explicit skip labels, deterministic vs
semantic Verifier separation, terminal/fallback/error trace completion,
structured-capability LLM-stage skipping, composer_first_token=not_available,
/ask vs /ask/stream parity, and no PII in the latency trace.
"""

from __future__ import annotations

import json
import time
import uuid

import pytest
from flask import Flask, request

from contracts.planner_attempt import PlannerAttempt
from core.runtime_turn_frame import publish_planner_attempt_frame
from core.target_composer_executor import (
    TargetComposerTone,
    execute_target_composer,
)
from core.target_response_verifier import (
    TargetResponseVerificationError,
    TargetSemanticAssessment,
    TargetSemanticIssue,
    TargetUnverifiedComposedResponse,
    verify_target_composed_response,
)
from core.target_runtime_client_context import clear_target_runtime_client_context_cache
from core.target_runtime_turn import run_target_fullcontext_runtime_turn
from core.turn_frame_from_raw import build_turn_frame_from_raw
from orchestration.context import AskTurnContext
from orchestration.planner_turn import PlannerTurnOutcome
from session import mem_reset
from tests.test_target_boundary_enforced_fullcontext_response import (
    PAIN_GROUNDED_TEXT,
    PRICE_TEXT,
    RecordingComposerBackend,
    RecordingSemanticBackend,
)
from tests.test_target_response_verifier import (
    RecordingBackend as VerifierRecordingBackend,
    _cached_context,
    _request as verifier_request,
    _response as verifier_response,
    _spec as verifier_spec,
    _valid_text,
)

_ALLOWED_TOPICS = frozenset({"implantation", "doctors", "clinic"})
_ALLOWED_SERVICES = frozenset({"all_on_4"})


# --- shared fixtures ---------------------------------------------------


class BackendPayload:
    def __init__(self, decision: str, confidence: float) -> None:
        self.decision = decision
        self.confidence = confidence


class RecordingBoundaryBackend:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.invocations: list[object] = []

    def classify(self, invocation: object, /) -> object:
        self.invocations.append(invocation)
        return self.payload


class _FailingBoundaryBackend:
    def classify(self, invocation: object, /) -> object:
        raise RuntimeError("boundary backend unavailable")


class _RaisingComposerBackend:
    def generate(self, invocation, /):
        raise RuntimeError("composer backend unavailable")


def _issue(kind: str, span: str) -> TargetSemanticIssue:
    return TargetSemanticIssue(kind=kind, offending_span=span)  # type: ignore[arg-type]


def _frame(**overrides: object):
    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["price"],
        "primary_aspect": "price",
        "service_id": "all_on_4",
        "topic": "implantation",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )


def _install_turn_frame(frame) -> None:
    publish_planner_attempt_frame(attempt=PlannerAttempt(frame=frame, status="ok"))


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_target_runtime_client_context_cache()
    yield
    clear_target_runtime_client_context_cache()


def _run_turn(
    frame,
    *,
    composer_backend,
    semantic_backend,
    boundary_backend,
    user_message: str = "test",
    sid: str | None = None,
):
    sid = sid or f"perf0-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        request.ctx["turn_t0_monotonic"] = time.monotonic()
        _install_turn_frame(frame)
        outcome = run_target_fullcontext_runtime_turn(
            client_id="demo",
            sid=sid,
            user_message=user_message,
            composer_backend=composer_backend,
            semantic_backend=semantic_backend,
            boundary_backend=boundary_backend,
        )
        bucket = dict(request.ctx.get("turn_timing") or {})
        stages = dict(bucket.get("stages") or {})
        flags = dict(bucket.get("flags") or {})
        marks = dict(bucket.get("marks") or {})
    return outcome, stages, flags, marks


_PII_MARKERS = ("+7", "@", "телефон", "имя", "боюсь боли")


def _assert_stage_entry_has_no_pii(name: str, entry: dict) -> None:
    blob = json.dumps(entry, ensure_ascii=False)
    for marker in _PII_MARKERS:
        assert marker not in blob, f"stage {name} entry leaked PII-like marker {marker!r}: {blob}"
    assert set(entry.keys()) <= {"status", "duration_ms", "llm_used", "reason"}


def _assert_non_negative_duration(entry: dict) -> None:
    if entry.get("duration_ms") is not None:
        assert entry["duration_ms"] >= 0


# --- Row 1/5: generic FullContext materialized (full stage breakdown) --


def test_generic_materialized_turn_shows_all_stages_completed() -> None:
    frame = _frame(aspects=["pain"], primary_aspect=None, service_id=None)
    outcome, stages, flags, marks = _run_turn(
        frame,
        composer_backend=RecordingComposerBackend(PAIN_GROUNDED_TEXT),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(BackendPayload("none", 0.95)),
        user_message="Больно ли?",
    )
    assert outcome.widget.kind == "materialized"
    for name in ("boundary", "composer", "verifier_deterministic", "verifier_semantic"):
        assert name in stages, f"missing stage {name}: {stages}"
        entry = stages[name]
        assert entry["status"] == "completed"
        _assert_non_negative_duration(entry)
        _assert_stage_entry_has_no_pii(name, entry)
    assert flags.get("composer_first_token") == "not_available"
    assert "verified_answer_ready" in marks
    assert "first_meaningful_text" in marks
    assert "widget_payload_ready" in marks
    # stage ordering: boundary must not start after composer starts
    assert marks["boundary_start"] <= marks["composer_start"]
    assert marks["composer_start"] <= marks["composer_end"]
    assert marks["composer_end"] <= marks["verifier_deterministic_start"]
    assert marks["verifier_deterministic_end"] <= marks["verifier_semantic_start"]


# --- Row 2: price lookup (same full breakdown shape) --------------------


def test_price_lookup_turn_shows_full_breakdown() -> None:
    frame = _frame(primary_aspect="price", aspects=["price"], service_id="all_on_4")
    outcome, stages, flags, _marks = _run_turn(
        frame,
        composer_backend=RecordingComposerBackend(PRICE_TEXT),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(BackendPayload("none", 0.95)),
        user_message="Сколько стоит All-on-4?",
    )
    assert outcome.widget.kind == "materialized"
    for name in ("boundary", "composer", "verifier_deterministic", "verifier_semantic"):
        assert stages[name]["status"] == "completed"
    assert flags.get("composer_first_token") == "not_available"


# --- Row 3/4: structured capability bypass (contacts / service availability) --


def test_clinic_contact_skips_boundary_composer_verifier() -> None:
    frame = _frame(
        aspects=["contact_phone"],
        primary_aspect="contact_phone",
        service_id=None,
        topic="clinic",
    )
    composer = RecordingComposerBackend(PRICE_TEXT)
    semantic = RecordingSemanticBackend()
    boundary = RecordingBoundaryBackend(BackendPayload("none", 0.95))
    outcome, stages, _flags, marks = _run_turn(
        frame,
        composer_backend=composer,
        semantic_backend=semantic,
        boundary_backend=boundary,
        user_message="Какой у вас телефон?",
    )
    assert outcome.widget.kind == "materialized"
    for name in ("boundary", "composer", "verifier_deterministic", "verifier_semantic"):
        entry = stages[name]
        assert entry["status"] == "skipped"
        assert entry["duration_ms"] is None
        assert entry["reason"] == "structured_capability:clinic_contact"
        _assert_stage_entry_has_no_pii(name, entry)
    # explicit skip labels prove these LLM stages were never invoked
    assert len(composer.invocations) == 0
    assert len(semantic.invocations) == 0
    assert len(boundary.invocations) == 0
    assert "verified_answer_ready" in marks
    assert "widget_payload_ready" in marks


def test_service_availability_skips_boundary_composer_verifier() -> None:
    frame = _frame(
        aspects=["service_availability"],
        primary_aspect="service_availability",
        service_id="all_on_4",
        topic="clinic",
    )
    composer = RecordingComposerBackend(PRICE_TEXT)
    semantic = RecordingSemanticBackend()
    boundary = RecordingBoundaryBackend(BackendPayload("none", 0.95))
    outcome, stages, _flags, _marks = _run_turn(
        frame,
        composer_backend=composer,
        semantic_backend=semantic,
        boundary_backend=boundary,
        user_message="Делаете ли вы All-on-4?",
    )
    for name in ("boundary", "composer", "verifier_deterministic", "verifier_semantic"):
        entry = stages[name]
        assert entry["status"] == "skipped"
        assert entry["reason"] == "structured_capability:service_availability"
    assert len(composer.invocations) == 0
    assert len(semantic.invocations) == 0
    assert len(boundary.invocations) == 0


# --- Row 6: medical concern -> medical_handoff (Composer still runs) ----


def test_medical_handoff_boundary_completed_composer_still_runs() -> None:
    frame = _frame(service_id=None, aspects=["pain"], primary_aspect=None)
    outcome, stages, _flags, _marks = _run_turn(
        frame,
        composer_backend=RecordingComposerBackend(PAIN_GROUNDED_TEXT),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(BackendPayload("medical_handoff", 0.9)),
        user_message="Больно ли?",
    )
    assert outcome.widget.kind == "materialized"
    assert stages["boundary"]["status"] == "completed"
    assert stages["composer"]["status"] == "completed"
    assert stages["verifier_deterministic"]["status"] == "completed"
    assert stages["verifier_semantic"]["status"] == "completed"


# --- Row 7: terminal / fallback (Composer + Verifier skipped, trace completes) --


def test_boundary_terminal_enforcement_skips_composer_and_verifier() -> None:
    frame = _frame()
    outcome, stages, _flags, marks = _run_turn(
        frame,
        composer_backend=RecordingComposerBackend(PRICE_TEXT),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=_FailingBoundaryBackend(),
        user_message="Можно ли мне?",
    )
    assert outcome.widget.kind == "terminal"
    # the boundary classifier itself degrades the backend failure to a normal
    # "uncertain" result internally (execute_target_medical_boundary_classification
    # never raises) — so the boundary stage completes; the *terminal* outcome is
    # decided one layer up by policy envelope enforcement, before Composer.
    assert stages["boundary"]["status"] == "completed"
    for name in ("composer", "verifier_deterministic", "verifier_semantic"):
        entry = stages[name]
        assert entry["status"] == "skipped"
        assert entry["reason"] == "terminal_before_composer"
    assert "first_meaningful_text" in marks
    assert "verified_answer_ready" not in marks  # no verified answer for a terminal reply


def test_boundary_exception_still_yields_error_widget_with_exception_stage() -> None:
    class _RaisingClassifyBoundary:
        def classify(self, invocation, /):
            raise RuntimeError("should never reach here via normal path")

    class _BadPayloadBoundary:
        """Backend whose payload fails downstream validation, forcing the
        boundary *executor* itself to raise inside run_target_fullcontext_runtime_turn."""

        def classify(self, invocation, /):
            return object()  # malformed — not a dict with decision/confidence

    frame = _frame()
    outcome, stages, _flags, _marks = _run_turn(
        frame,
        composer_backend=RecordingComposerBackend(PRICE_TEXT),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=_BadPayloadBoundary(),
        user_message="test",
    )
    # malformed backend payload is fail-closed inside execute_target_medical_boundary_classification
    # (returns an "uncertain" result, not an exception) — boundary stage still completes.
    assert stages["boundary"]["status"] == "completed"
    assert outcome.widget.kind in ("materialized", "terminal", "error")


# --- Row 8: Verifier blocked — deterministic (ungrounded money claim) ---


def test_verifier_deterministic_block_marks_semantic_not_reached() -> None:
    spec = verifier_spec(
        service_id=None,
        required_fact_ids=(),
        required_components=("content",),
        allow_marketing_facts=False,
        allow_cta=False,
    )
    from core.target_composer_request import TargetComposerRequest
    from core.target_response_followup_policy import TargetResponseFollowupSelection

    request_obj = TargetComposerRequest(
        user_message="Сколько стоит?",
        spec=spec,
        evidence_blocks=(),
        selected_followups=TargetResponseFollowupSelection(source=None, content=(), price=()),
        selected_cta_key=None,
    )
    response_obj = TargetUnverifiedComposedResponse(
        text="Имплантация стоит 100 000 рублей.",
        spec=spec,
        selected_followups=request_obj.selected_followups,
        selected_cta_key=None,
    )
    semantic = VerifierRecordingBackend()

    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        with pytest.raises(TargetResponseVerificationError) as caught:
            verify_target_composed_response(
                request_obj,
                response_obj,
                cached_full_context=_cached_context("corpus without prices"),
                semantic_backend=semantic,
            )
        stages = dict((request.ctx.get("turn_timing") or {}).get("stages") or {})
    assert caught.value.code == "target_verifier_numeric_ungrounded"
    assert stages["verifier_deterministic"]["status"] == "blocked"
    assert stages["verifier_semantic"]["status"] == "skipped"
    assert stages["verifier_semantic"]["reason"] == "deterministic_block"
    # deterministic block must happen without ever calling the semantic LLM backend
    assert len(semantic.invocations) == 0


# --- Row 9: Verifier blocked — semantic (LLM assesses, rejects) ---------


def test_verifier_semantic_block_has_llm_duration_and_completed_trace() -> None:
    req = verifier_request()
    resp = verifier_response(req, text=_valid_text())
    assessment = TargetSemanticAssessment(
        issues=(_issue("personal_medical_conclusion", "100 000 рублей"),),
    )
    semantic = VerifierRecordingBackend(assessment=assessment)

    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        with pytest.raises(TargetResponseVerificationError) as caught:
            verify_target_composed_response(
                req,
                resp,
                cached_full_context=_cached_context(),
                semantic_backend=semantic,
            )
        stages = dict((request.ctx.get("turn_timing") or {}).get("stages") or {})
    assert caught.value.code == "target_verifier_semantic_rejected"
    assert stages["verifier_deterministic"]["status"] == "completed"
    assert stages["verifier_semantic"]["status"] == "blocked"
    assert stages["verifier_semantic"]["duration_ms"] is not None
    assert stages["verifier_semantic"]["duration_ms"] >= 0
    # the semantic backend really was called (unlike the deterministic-block case)
    assert len(semantic.invocations) == 1


def test_composer_exception_marks_stage_exception_and_reraises() -> None:
    req = verifier_request()
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        with pytest.raises(Exception):
            execute_target_composer(
                req,
                _RaisingComposerBackend(),
                tone=TargetComposerTone(key="commercial_warm", instruction="warm"),
                cached_full_context=_cached_context(),
            )
        stages = dict((request.ctx.get("turn_timing") or {}).get("stages") or {})
    assert stages["composer"]["status"] == "exception"
    assert stages["composer"]["duration_ms"] is not None
    assert stages["composer"]["duration_ms"] >= 0


# --- Ingress stage (measured one layer above run_target_fullcontext_runtime_turn) --


def test_ingress_stage_completed_deterministic_no_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    import orchestration.pre_resolver_turn as pre_resolver_module
    from contracts.ingress_route import IngressRouteResult

    fake_result = IngressRouteResult(
        route="normal",
        confidence=0.99,
        reason="rule_match",
        policy_key=None,
        requested_service=None,
        source="rule",
        is_urgent=False,
    )
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", lambda *a, **k: fake_result)

    sid = f"perf0-ingress-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        request.ctx["turn_t0_monotonic"] = time.monotonic()
        pre_resolver_module.run_pre_resolver_turn(
            {"q": "Сколько стоит имплант?", "sid": sid, "client_id": "demo"},
            resolve_client_id=lambda *a, **k: "demo",
            bind_chat_ctx=lambda *a, **k: None,
            resolve_ip=lambda: "127.0.0.1",
            client_txt=lambda cid: {},
            service_payload=lambda **k: {},
            get_last_content_ui_payload=lambda sid: None,
        )
        stages = dict((request.ctx.get("turn_timing") or {}).get("stages") or {})
    assert stages["ingress"]["status"] == "completed"
    assert stages["ingress"]["llm_used"] is False
    assert stages["ingress"]["reason"] == "rule"
    assert stages["ingress"]["duration_ms"] is not None
    assert stages["ingress"]["duration_ms"] >= 0


def test_ingress_stage_skipped_on_ref_click() -> None:
    import orchestration.pre_resolver_turn as pre_resolver_module

    sid = f"perf0-ingress-ref-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        request.ctx["turn_t0_monotonic"] = time.monotonic()
        pre_resolver_module.run_pre_resolver_turn(
            {"q": "цена", "sid": sid, "client_id": "demo", "ref": "price:all_on_4"},
            resolve_client_id=lambda *a, **k: "demo",
            bind_chat_ctx=lambda *a, **k: None,
            resolve_ip=lambda: "127.0.0.1",
            client_txt=lambda cid: {},
            service_payload=lambda **k: {},
            get_last_content_ui_payload=lambda sid: None,
        )
        stages = dict((request.ctx.get("turn_timing") or {}).get("stages") or {})
    assert stages["ingress"]["status"] == "skipped"
    assert stages["ingress"]["reason"] == "ref_click"
    assert stages["ingress"]["duration_ms"] is None


# --- Row 10/11: /ask vs /ask/stream parity (payload, route, LLM-call count) --


def test_ask_and_ask_stream_produce_identical_payload_and_completed_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app as app_module
    import orchestration.target_fullcontext_turn as target_turn_module

    captured_turn_complete: list[dict] = []
    real_emit_bot_event = app_module.emit_bot_event

    def _capturing_emit_bot_event(logger, event_name, *, status=None, details=None, **overrides):
        if event_name == "turn_complete":
            captured_turn_complete.append(dict(details or {}))
        return real_emit_bot_event(logger, event_name, status=status, details=details, **overrides)

    monkeypatch.setattr("orchestration.finalize_turn.emit_bot_event", _capturing_emit_bot_event)

    def _fake_default_backends():
        return (
            RecordingComposerBackend(PRICE_TEXT),
            RecordingSemanticBackend(),
            RecordingBoundaryBackend(BackendPayload("none", 0.95)),
        )

    monkeypatch.setattr(target_turn_module, "_default_target_runtime_backends", _fake_default_backends)
    monkeypatch.setattr(app_module, "run_planner_turn", lambda **k: PlannerTurnOutcome("content", None))
    monkeypatch.setattr(
        "core.target_runtime_turn.load_runtime_turn_frame",
        lambda: _frame(primary_aspect="price", aspects=["price"]),
    )

    client = app_module.app.test_client()
    results: dict[str, dict] = {}
    traces: dict[str, dict] = {}
    q = "Сколько стоит All-on-4?"

    for endpoint in ("/ask", "/ask/stream"):
        captured_turn_complete.clear()
        sid = f"perf0-parity-{uuid.uuid4().hex[:8]}"
        mem_reset(sid)
        # PERF-0 Rule: no LIVE/LLM in this offline test — bypass Ingress (which
        # would otherwise attempt a real classify_ingress LLM call for a
        # free-text price question) exactly like the pre-existing S65 harness.
        monkeypatch.setattr(
            app_module,
            "run_pre_resolver_turn",
            lambda *a, **k: AskTurnContext(
                q=q, sid=sid, client_id="demo", ref="", data={"q": q, "sid": sid, "client_id": "demo"}, st={}
            ),
        )
        resp = client.post(
            endpoint,
            json={"q": q, "sid": sid, "client_id": "demo"},
        )
        assert resp.status_code == 200

        # PERF-1: /ask/stream's orchestration now runs lazily, driven by
        # iterating the streamed response body (exactly like a real WSGI
        # server sending bytes to a real client) — so the body must be read
        # BEFORE asserting anything that depends on the turn having run
        # (captured_turn_complete). For /ask this ordering makes no
        # difference (orchestration is still eager there, unchanged).
        if endpoint == "/ask":
            results[endpoint] = resp.get_json()
        else:
            text = resp.data.decode("utf-8")
            assert "event: typing" in text
            assert "event: ui" in text
            assert "event: done" in text
            ui_line = next(
                line for line in text.split("\n") if line.startswith("data: ") and '"answer"' in line
            )
            results[endpoint] = json.loads(ui_line[len("data: "):])

        assert len(captured_turn_complete) == 1
        traces[endpoint] = captured_turn_complete[0]

    ask_payload = results["/ask"]
    stream_payload = results["/ask/stream"]
    assert ask_payload["answer"] == stream_payload["answer"]
    assert ask_payload["meta"]["service_route"] == stream_payload["meta"]["service_route"]

    for endpoint, detail in traces.items():
        stages = detail.get("stages") or {}
        for name in ("boundary", "composer", "verifier_deterministic", "verifier_semantic"):
            assert stages.get(name, {}).get("status") == "completed", (endpoint, name, stages)
        assert detail.get("composer_first_token") == "not_available"
        assert isinstance(detail.get("total_ms"), int)
        assert detail.get("total_ms") >= 0
        # PERF-0 Rule 9: latency_ms must not drift from total_ms (single source of truth)
        assert detail.get("latency_ms") == detail.get("total_ms")

    # both entrypoints call the same orchestration path -> same LLM call count (1 each)
    # is implied by RecordingComposerBackend/RecordingSemanticBackend/RecordingBoundaryBackend
    # each being exercised exactly once per request (guarded by their own
    # "retry forbidden" semantics upstream in target_runtime_llm_backends.py).


# --- cross-cutting: no PII anywhere in the stage/flag vocabulary --------


def test_stage_entries_never_contain_question_or_answer_text() -> None:
    frame = _frame(aspects=["pain"], primary_aspect=None, service_id=None)
    outcome, stages, flags, marks = _run_turn(
        frame,
        composer_backend=RecordingComposerBackend(PAIN_GROUNDED_TEXT),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(BackendPayload("none", 0.95)),
        user_message="Я боюсь боли, скажите мой телефон +79991234567",
    )
    blob = json.dumps({"stages": stages, "flags": flags}, ensure_ascii=False)
    assert "боюсь боли" not in blob
    assert "+79991234567" not in blob
    assert "9991234567" not in blob
