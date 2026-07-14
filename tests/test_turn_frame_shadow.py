from __future__ import annotations

import ast
import copy
import inspect
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from flask import Flask

from contracts.decision_frame import DecisionFrame, DecisionFrameConfidence
from contracts.planner_attempt import PlannerAttempt
from contracts.turn_frame import TurnFrame
from contracts.turn_plan import TurnPlan
from core.turn_frame_adapter import build_turn_frame_from_legacy
from core.turn_frame_from_raw import build_turn_frame_from_raw
from core.turn_frame_shadow import (
    SHADOW_REASON_BUILD_FAILED,
    SHADOW_REASON_TURN_PLAN_MISSING,
    SHADOW_STATUS_DEGRADED,
    SHADOW_STATUS_NOT_AVAILABLE,
    SHADOW_STATUS_OK,
    SHADOW_STATUS_PARTIAL,
    mark_turn_frame_shadow_not_available,
    record_planner_attempt_shadow,
    record_turn_frame_shadow,
)
from orchestration.resolver_turn import run_resolver_turn


def _decision(**overrides) -> DecisionFrame:
    payload = {
        "route_intent": "price_lookup",
        "service_topic": "implantation",
        "service_id": "all_on_4",
        "query_mode": "specific",
        "confidence": {
            "intent": 0.9,
            "topic": 0.85,
            "service": 0.9,
            "query_mode": 0.85,
        },
        "needs_clarification": False,
    }
    payload.update(overrides)
    return DecisionFrame.model_validate(payload)


def _turn_plan(**overrides) -> TurnPlan:
    payload = {
        "route": "price_lookup",
        "aspects": ["price"],
        "service_id": "all_on_4",
        "followup_of": "all_on_4",
        "needs_clarify": False,
    }
    payload.update(overrides)
    return TurnPlan.model_validate(payload)


def _raw_shadow_frame(**overrides) -> TurnFrame:
    payload = {
        "route": "price_lookup",
        "aspects": ["price"],
        "topic": "implantation",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(payload, allowed_topics=frozenset({"doctors", "implantation"}))


def _ok_attempt(turn_plan: TurnPlan | None = None) -> PlannerAttempt:
    return PlannerAttempt(
        legacy_plan=turn_plan or _turn_plan(),
        shadow_frame=_raw_shadow_frame(),
        shadow_status="ok",
    )


def _partial_doctors_attempt() -> PlannerAttempt:
    return PlannerAttempt(
        legacy_plan=None,
        shadow_frame=_raw_shadow_frame(
            route="content",
            topic="doctors",
            topic_confidence=0.95,
            aspects=[],
        ),
        shadow_status="partial",
    )


def _patient_scope_attempt(
    patient_situation: str,
    *,
    partial: bool = False,
) -> PlannerAttempt:
    aspects = [] if partial else ["overview"]
    shadow_frame = _raw_shadow_frame(
        route="content",
        aspects=aspects,
        topic="implantation",
        topic_confidence=0.9,
        patient_situation=patient_situation,
    )
    legacy_plan = None
    if not partial:
        legacy_plan = _turn_plan(
            route="content",
            aspects=["overview"],
            service_id=None,
            followup_of=None,
            patient_situation=patient_situation,
        )
    return PlannerAttempt(
        legacy_plan=legacy_plan,
        shadow_frame=shadow_frame,
        shadow_status="partial" if partial else "ok",
    )


def _native_planner_payload(**overrides) -> dict:
    payload = {
        "route": "content",
        "aspects": ["overview"],
        "service_id": "veneers",
        "followup_of": None,
        "needs_clarify": False,
        "patient_situation": "one_tooth_missing",
        "brand_filter": None,
        "topic": "prosthetics",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return payload


def _patch_real_planner_external_completion(monkeypatch, payloads: list[dict]):
    queued = [copy.deepcopy(payload) for payload in payloads]
    calls: list[dict] = []

    def _create(**kwargs):
        calls.append(copy.deepcopy(kwargs))
        if not queued:
            raise AssertionError("unexpected second planner completion")
        payload = queued.pop(0)

        class _Message:
            content = json.dumps(payload, ensure_ascii=False)

        class _Choice:
            message = _Message()

        class _Response:
            choices = [_Choice()]

        return _Response()

    monkeypatch.setattr(
        "core.turn_planner_llm.chat_client.chat.completions.create",
        _create,
    )
    monkeypatch.setattr(
        "core.turn_planner_llm.build_compact_service_catalog",
        lambda _client_id: [
            {
                "service_id": "veneers",
                "title": "Виниры",
                "about": "эстетическая реставрация",
            }
        ],
    )
    monkeypatch.setattr(
        "core.turn_planner_llm._allowed_pricebook_filters",
        lambda _client_id: (frozenset(), frozenset()),
    )
    monkeypatch.setattr(
        "core.turn_planner_llm.load_client_topic_taxonomy",
        lambda _client_id: frozenset({"prosthetics"}),
    )
    monkeypatch.setattr("orchestration.resolver_turn.TURN_PLANNER_ON", True)
    return calls, queued


def _run_real_planner_resolver(app: Flask, *, sid: str):
    from session import mem_reset

    mem_reset(sid)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        outcome = run_resolver_turn(
            q="Расскажите о винирах",
            sid=sid,
            client_id="demo",
            st={"hist": []},
            enqueue_resolver_trace=lambda **_kwargs: None,
        )
        return outcome, copy.deepcopy(request.ctx)


_A6_FAIL_OPEN_CASE_IDS = (
    "topic_a6_04_doctors_overview",
    "topic_a6_05_doctors_named",
    "topic_a6_06_doctors_implants",
    "topic_a6_09_extraction_aftercare",
    "topic_a6_28_null_general_price",
    "topic_a6_30_null_booking",
    "topic_a6_31_null_pain",
)


def _frozen_a6_case(case_id: str) -> dict:
    spec = json.loads(
        Path("evals/v5/demo/topic_shadow_matrix.json").read_text(encoding="utf-8")
    )
    return next(case for case in spec["cases"] if case["id"] == case_id)


def _partial_attempt_for_topic(topic: str | None) -> PlannerAttempt:
    return PlannerAttempt(
        legacy_plan=None,
        shadow_frame=build_turn_frame_from_raw(
            {
                "route": "content",
                "aspects": [],
                "topic": topic,
                "topic_confidence": 0.95 if topic is not None else 0.0,
            },
            allowed_topics=frozenset({"doctors", "extraction"}),
        ),
        shadow_status="partial",
    )


def test_record_turn_frame_shadow_ok_writes_dump_and_status() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan()
    decision = _decision()
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {"turn_frame_shadow_reason": "stale"}
        frame = record_turn_frame_shadow(turn_plan=turn_plan, decision_frame=decision)

        assert frame is not None
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_OK
        assert request.ctx["turn_frame_shadow"] == frame.model_dump()
        assert "turn_frame_shadow_reason" not in request.ctx


def test_record_turn_frame_shadow_snapshot_has_field_meta_from_adapter() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan()
    decision = _decision()
    expected = build_turn_frame_from_legacy(turn_plan=turn_plan, decision_frame=decision)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        record_turn_frame_shadow(turn_plan=turn_plan, decision_frame=decision)

        snapshot = request.ctx["turn_frame_shadow"]
        assert snapshot == expected.model_dump()
        assert snapshot["field_meta"]["emotion"]["provenance"] == "default"
        assert snapshot["field_meta"]["intent"]["provenance"] == "decision_frame.route_intent"
        assert snapshot["patient_scope"] == {
            "extent": "unknown",
            "jaw": "unknown",
            "stage": "unknown",
            "modifiers": [],
        }
        for field_meta in snapshot["field_meta"]["patient_scope"].values():
            assert field_meta == {
                "confidence": 0.0,
                "provenance": "turn_plan.schema_default",
                "status": "defaulted",
                "error": None,
            }


def test_mark_turn_frame_shadow_not_available() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {"turn_frame_shadow": {"intent": "content"}}
        mark_turn_frame_shadow_not_available()

        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_NOT_AVAILABLE
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_TURN_PLAN_MISSING
        assert "turn_frame_shadow" not in request.ctx


def test_record_planner_attempt_shadow_ok_writes_exact_raw_frame() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    attempt = _ok_attempt()
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {"turn_frame_shadow_reason": "stale"}
        frame = record_planner_attempt_shadow(attempt=attempt)

        assert frame is attempt.shadow_frame
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_OK
        assert request.ctx["turn_frame_shadow"] == attempt.shadow_frame.model_dump()
        assert "turn_frame_shadow_reason" not in request.ctx


@pytest.mark.parametrize(
    ("patient_situation", "scope_field", "expected_value", "expected_provenance"),
    [
        (
            "one_tooth_missing",
            "extent",
            "one_tooth",
            "turn_plan.patient_situation.extent",
        ),
        (
            "bone_deficit_or_grafting",
            "modifiers",
            ["reported_bone_deficit"],
            "turn_plan.patient_situation.modifiers",
        ),
    ],
)
def test_record_planner_attempt_shadow_preserves_a9_nested_scope(
    patient_situation,
    scope_field,
    expected_value,
    expected_provenance,
) -> None:
    app = Flask(__name__)
    attempt = _patient_scope_attempt(patient_situation)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {"turn_frame_shadow_reason": "stale"}
        frame = record_planner_attempt_shadow(attempt=attempt)

        assert frame is attempt.shadow_frame
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_OK
        assert request.ctx["turn_frame_shadow"] == attempt.shadow_frame.model_dump()
        snapshot = request.ctx["turn_frame_shadow"]
        assert snapshot["patient_scope"][scope_field] == expected_value
        assert snapshot["field_meta"]["patient_scope"][scope_field] == {
            "confidence": 0.0,
            "provenance": expected_provenance,
            "status": "valid",
            "error": None,
        }
        for name, meta in snapshot["field_meta"]["patient_scope"].items():
            if name == scope_field:
                continue
            assert meta == {
                "confidence": 0.0,
                "provenance": "turn_plan.schema_default",
                "status": "defaulted",
                "error": None,
            }
        assert "turn_frame_shadow_reason" not in request.ctx


def test_record_planner_attempt_shadow_partial_preserves_valid_topic() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    attempt = _partial_doctors_attempt()
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {"turn_frame_shadow_reason": "stale"}
        frame = record_planner_attempt_shadow(attempt=attempt)

        assert frame is attempt.shadow_frame
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_PARTIAL
        assert request.ctx["turn_frame_shadow"]["topic"] == "doctors"
        assert request.ctx["turn_frame_shadow"]["field_meta"]["topic"]["status"] == "valid"
        assert request.ctx["turn_frame_shadow"]["field_meta"]["aspects"]["error"] == "aspects_empty"
        assert "turn_frame_shadow_reason" not in request.ctx


def test_record_planner_attempt_shadow_not_available_clears_stale_frame() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    attempt = PlannerAttempt(
        legacy_plan=None,
        shadow_frame=None,
        shadow_status="not_available",
    )
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {"turn_frame_shadow": {"topic": "stale"}}
        frame = record_planner_attempt_shadow(attempt=attempt)

        assert frame is None
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_NOT_AVAILABLE
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_TURN_PLAN_MISSING
        assert "turn_frame_shadow" not in request.ctx


def test_record_planner_attempt_shadow_degraded_preserves_stable_reason() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    attempt = PlannerAttempt(
        legacy_plan=_turn_plan(),
        shadow_frame=None,
        shadow_status="degraded",
    )
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {"turn_frame_shadow": {"topic": "stale"}}
        frame = record_planner_attempt_shadow(attempt=attempt)

        assert frame is None
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_DEGRADED
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_BUILD_FAILED
        assert "turn_frame_shadow" not in request.ctx


def test_record_planner_attempt_shadow_model_dump_failure_is_degraded(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    attempt = _ok_attempt()

    def _dump_boom(_self):
        raise RuntimeError("secret serialization exception and question")

    monkeypatch.setattr(TurnFrame, "model_dump", _dump_boom)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        frame = record_planner_attempt_shadow(attempt=attempt)

        assert frame is None
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_DEGRADED
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_BUILD_FAILED
        assert "secret serialization" not in str(request.ctx)


def test_record_planner_attempt_shadow_survives_event_failure(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    attempt = PlannerAttempt(
        legacy_plan=_turn_plan(),
        shadow_frame=None,
        shadow_status="degraded",
    )
    monkeypatch.setattr(
        "core.turn_frame_shadow.emit_bot_event",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("sink failed")),
    )
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        frame = record_planner_attempt_shadow(attempt=attempt)

        assert frame is None
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_DEGRADED
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_BUILD_FAILED


def test_record_turn_frame_shadow_degraded_isolates_builder_failure(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan()
    decision = _decision()

    def _boom(**_kwargs):
        raise RuntimeError("secret builder failure with user text")

    monkeypatch.setattr("core.turn_frame_shadow.build_turn_frame_from_legacy", _boom)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        frame = record_turn_frame_shadow(turn_plan=turn_plan, decision_frame=decision)

        assert frame is None
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_DEGRADED
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_BUILD_FAILED
        assert "turn_frame_shadow" not in request.ctx


def test_record_turn_frame_shadow_degraded_emits_structured_event_without_leaks(
    monkeypatch,
) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan()
    decision = _decision()
    captured: list[dict] = []

    def _capture(_logger, event_name, *, status=None, details=None, **_kwargs):
        captured.append(
            {
                "event_name": event_name,
                "status": status,
                "details": details or {},
            }
        )

    monkeypatch.setattr(
        "core.turn_frame_shadow.build_turn_frame_from_legacy",
        lambda **_kwargs: (_ for _ in ()).throw(ValueError("leaked exception detail")),
    )
    monkeypatch.setattr("core.turn_frame_shadow.emit_bot_event", _capture)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        record_turn_frame_shadow(turn_plan=turn_plan, decision_frame=decision)

    assert len(captured) == 1
    event = captured[0]
    assert event["event_name"] == "turn_frame_shadow"
    assert event["status"] == SHADOW_STATUS_DEGRADED
    assert event["details"]["turn_frame_shadow_status"] == SHADOW_STATUS_DEGRADED
    assert event["details"]["turn_frame_shadow_reason"] == SHADOW_REASON_BUILD_FAILED
    payload = str(event)
    assert "leaked exception detail" not in payload


def test_shadow_recorder_signatures_exclude_question_like_params() -> None:
    forbidden = {"question", "answer", "history", "payload", "q"}
    for fn in (
        record_turn_frame_shadow,
        record_planner_attempt_shadow,
        mark_turn_frame_shadow_not_available,
    ):
        params = set(inspect.signature(fn).parameters)
        assert params.isdisjoint(forbidden)


def test_run_resolver_turn_planner_success_records_shadow(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan()
    attempt = _ok_attempt(turn_plan)
    monkeypatch.setattr("orchestration.resolver_turn.TURN_PLANNER_ON", True)
    monkeypatch.setattr("core.turn_planner_llm.plan_turn_attempt", lambda *_a, **_k: attempt)
    monkeypatch.setattr("core.turn_planner_llm.publish_turn_plan", lambda _p: None)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        run_resolver_turn(
            q="сколько стоит all-on-4?",
            sid="shadow-success",
            client_id="demo",
            st={},
            enqueue_resolver_trace=lambda **_k: None,
        )

        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_OK
        assert request.ctx["turn_frame_shadow"] == attempt.shadow_frame.model_dump()


def test_run_resolver_turn_does_not_replace_decision_or_intent(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    from core.turn_planner_llm import turn_plan_to_decision_frame

    turn_plan = _turn_plan()
    attempt = _ok_attempt(turn_plan)
    expected_decision = turn_plan_to_decision_frame(turn_plan, client_id="demo")
    monkeypatch.setattr("orchestration.resolver_turn.TURN_PLANNER_ON", True)
    monkeypatch.setattr("core.turn_planner_llm.plan_turn_attempt", lambda *_a, **_k: attempt)
    monkeypatch.setattr("core.turn_planner_llm.publish_turn_plan", lambda _p: None)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        outcome = run_resolver_turn(
            q="сколько стоит?",
            sid="shadow-no-replace",
            client_id="demo",
            st={},
            enqueue_resolver_trace=lambda **_k: None,
        )

        assert outcome.decision.model_dump() == expected_decision.model_dump()
        assert outcome.intent == "price_lookup"
        assert isinstance(request.ctx.get("turn_frame_shadow"), dict)


def test_run_resolver_turn_planner_missing_marks_not_available_before_resolver(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    resolver_calls: list[str] = []
    fallback_decision = _decision(route_intent="content", query_mode="overview")

    def _resolve_with_fallback(**_kwargs):
        resolver_calls.append("called")
        return fallback_decision, [], "content"

    monkeypatch.setattr("orchestration.resolver_turn.TURN_PLANNER_ON", True)
    monkeypatch.setattr(
        "core.turn_planner_llm.plan_turn_attempt",
        lambda *_a, **_k: PlannerAttempt(
            legacy_plan=None,
            shadow_frame=None,
            shadow_status="not_available",
        ),
    )
    monkeypatch.setattr(
        "orchestration.resolver_turn.resolve_with_fallback",
        _resolve_with_fallback,
    )
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        run_resolver_turn(
            q="сколько стоит?",
            sid="shadow-missing-plan",
            client_id="demo",
            st={"hist": []},
            enqueue_resolver_trace=lambda **_k: None,
        )

        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_NOT_AVAILABLE
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_TURN_PLAN_MISSING
        assert "turn_frame_shadow" not in request.ctx
        assert resolver_calls == ["called"]


def test_run_resolver_turn_partial_shadow_keeps_legacy_fail_open(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    attempt_calls: list[tuple[str, str, str]] = []
    resolver_calls: list[str] = []
    attempt = _partial_doctors_attempt()
    fallback_decision = _decision(
        route_intent="content",
        service_topic="prosthetics",
        service_id="veneers",
        query_mode="overview",
    )

    def _attempt(q, sid, client_id):
        attempt_calls.append((q, sid, client_id))
        return attempt

    def _resolve_with_fallback(**_kwargs):
        resolver_calls.append("called")
        return fallback_decision, [], "content"

    monkeypatch.setattr("orchestration.resolver_turn.TURN_PLANNER_ON", True)
    monkeypatch.setattr("core.turn_planner_llm.plan_turn_attempt", _attempt)
    monkeypatch.setattr(
        "core.turn_planner_llm.plan_turn",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("legacy wrapper called")),
    )
    monkeypatch.setattr(
        "orchestration.resolver_turn.resolve_with_fallback",
        _resolve_with_fallback,
    )
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        outcome = run_resolver_turn(
            q="Кто занимается лечением?",
            sid="shadow-partial-fail-open",
            client_id="demo",
            st={"hist": []},
            enqueue_resolver_trace=lambda **_k: None,
        )

        assert attempt_calls == [("Кто занимается лечением?", "shadow-partial-fail-open", "demo")]
        assert resolver_calls == ["called"]
        assert request.ctx["turn_planner_used"] is False
        assert request.ctx["resolver_used"] is True
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_PARTIAL
        assert request.ctx["turn_frame_shadow"]["topic"] == "doctors"
        assert request.ctx["turn_frame_shadow"]["field_meta"]["aspects"]["error"] == "aspects_empty"
        assert outcome.decision.service_topic == "prosthetics"
        assert outcome.intent == "content"
        assert outcome.scope_topic_candidate != "doctors"


def test_a9_partial_scope_is_observable_but_does_not_change_product_fallback(
    monkeypatch,
) -> None:
    app = Flask(__name__)
    attempt = _patient_scope_attempt("one_tooth_missing", partial=True)
    recorder_calls: list[PlannerAttempt] = []
    fallback_calls: list[dict] = []
    fallback_decision = _decision(
        route_intent="content",
        service_topic="prosthetics",
        service_id="veneers",
        query_mode="overview",
    )

    def _record(*, attempt):
        recorder_calls.append(attempt)
        return record_planner_attempt_shadow(attempt=attempt)

    def _fallback(**kwargs):
        fallback_calls.append(kwargs)
        return fallback_decision, [], "fallback-content"

    monkeypatch.setattr("orchestration.resolver_turn.TURN_PLANNER_ON", True)
    monkeypatch.setattr(
        "core.turn_planner_llm.plan_turn_attempt",
        lambda *_args, **_kwargs: attempt,
    )
    monkeypatch.setattr("orchestration.resolver_turn.record_planner_attempt_shadow", _record)
    monkeypatch.setattr("orchestration.resolver_turn.resolve_with_fallback", _fallback)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        outcome = run_resolver_turn(
            q="Секретный вопрос пациента",
            sid="a9-shadow-partial",
            client_id="demo",
            st={"hist": []},
            enqueue_resolver_trace=lambda **_kwargs: None,
        )

        assert recorder_calls == [attempt]
        assert len(fallback_calls) == 1
        assert request.ctx["turn_planner_used"] is False
        assert request.ctx["resolver_used"] is True
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_PARTIAL
        snapshot = request.ctx["turn_frame_shadow"]
        assert snapshot["patient_scope"]["extent"] == "one_tooth"
        assert snapshot["field_meta"]["patient_scope"]["extent"]["status"] == "valid"
        assert snapshot["field_meta"]["aspects"]["error"] == "aspects_empty"
        assert "Секретный вопрос" not in str(snapshot)
        assert outcome.decision.model_dump() == fallback_decision.model_dump()
        assert outcome.decision.service_topic == "prosthetics"
        assert outcome.decision.service_id == "veneers"
        assert outcome.intent == "content"
        assert outcome.scope_topic_candidate == "prosthetics"


def test_native_scope_real_planner_wiring_is_product_equivalent_to_absent_control(
    monkeypatch,
) -> None:
    control = _native_planner_payload()
    native_scope = {
        "extent": "full_arch",
        "jaw": "both",
        "stage": "implant_placed",
        "modifiers": ["reported_bone_deficit"],
    }
    treatment = _native_planner_payload(patient_scope=native_scope)
    calls, queued = _patch_real_planner_external_completion(
        monkeypatch,
        [control, treatment],
    )
    monkeypatch.setattr(
        "orchestration.resolver_turn.resolve_with_fallback",
        lambda **_kwargs: pytest.fail("valid legacy planner branch must not fall back"),
    )

    app = Flask(__name__)
    control_outcome, control_ctx = _run_real_planner_resolver(app, sid="native-ab")
    assert len(calls) == 1
    treatment_outcome, treatment_ctx = _run_real_planner_resolver(app, sid="native-ab")

    assert len(calls) == 2
    assert queued == []
    assert all(call["model"] for call in calls)
    control_signature = {
        "intent": control_outcome.intent,
        "decision": control_outcome.decision.model_dump(),
        "scope_topic_candidate": control_outcome.scope_topic_candidate,
        "turn_plan": control_ctx["turn_plan"],
    }
    treatment_signature = {
        "intent": treatment_outcome.intent,
        "decision": treatment_outcome.decision.model_dump(),
        "scope_topic_candidate": treatment_outcome.scope_topic_candidate,
        "turn_plan": treatment_ctx["turn_plan"],
    }
    assert treatment_signature == control_signature
    assert "patient_scope" not in treatment_ctx["turn_plan"]
    assert treatment_ctx["turn_frame_shadow_status"] == SHADOW_STATUS_OK
    shadow = treatment_ctx["turn_frame_shadow"]
    assert shadow["patient_scope"] == native_scope
    assert shadow["field_meta"]["patient_scope"]["container"] == {
        "confidence": 0.0,
        "provenance": "turn_plan.raw.patient_scope",
        "status": "valid",
        "error": None,
    }
    for field_name in ("extent", "jaw", "stage", "modifiers"):
        assert shadow["field_meta"]["patient_scope"][field_name] == {
            "confidence": 0.0,
            "provenance": f"turn_plan.raw.patient_scope.{field_name}",
            "status": "valid",
            "error": None,
        }
    assert control_ctx["turn_plan_route"] == treatment_ctx["turn_plan_route"]
    assert control_ctx["turn_plan_aspects"] == treatment_ctx["turn_plan_aspects"]
    assert control_ctx["turn_plan_service_id"] == treatment_ctx["turn_plan_service_id"]
    assert control_ctx["turn_plan_followup_of"] == treatment_ctx["turn_plan_followup_of"]
    assert control_ctx["turn_plan_needs_clarify"] == treatment_ctx["turn_plan_needs_clarify"]


def test_invalid_native_member_stays_partial_without_changing_valid_legacy_product(
    monkeypatch,
) -> None:
    payload = _native_planner_payload(
        patient_scope={
            "extent": 42,
            "jaw": "upper",
            "stage": "implant_placed",
            "modifiers": ["reported_bone_deficit"],
        }
    )
    calls, queued = _patch_real_planner_external_completion(monkeypatch, [payload])
    monkeypatch.setattr(
        "orchestration.resolver_turn.resolve_with_fallback",
        lambda **_kwargs: pytest.fail("invalid native sibling must not invalidate legacy"),
    )

    outcome, ctx = _run_real_planner_resolver(Flask(__name__), sid="native-invalid-member")

    assert len(calls) == 1
    assert queued == []
    assert ctx["turn_planner_used"] is True
    assert ctx["resolver_used"] is False
    assert ctx["turn_frame_shadow_status"] == SHADOW_STATUS_PARTIAL
    assert "patient_scope" not in ctx["turn_plan"]
    expected_legacy = copy.deepcopy(payload)
    expected_legacy.pop("patient_scope")
    assert ctx["turn_plan"] == expected_legacy
    assert outcome.decision.service_id == "veneers"
    assert outcome.decision.model_dump()["route_intent"] == ctx["turn_plan"]["route"]
    shadow = ctx["turn_frame_shadow"]
    assert shadow["patient_scope"] == {
        "extent": "unknown",
        "jaw": "upper",
        "stage": "implant_placed",
        "modifiers": ["reported_bone_deficit"],
    }
    assert shadow["field_meta"]["patient_scope"]["extent"] == {
        "confidence": 0.0,
        "provenance": "turn_plan.raw.patient_scope.extent",
        "status": "invalid",
        "error": "patient_extent_invalid_type",
    }
    for field_name in ("jaw", "stage", "modifiers"):
        assert shadow["field_meta"]["patient_scope"][field_name]["status"] == "valid"


def test_valid_native_scope_does_not_rescue_invalid_legacy_product_branch(
    monkeypatch,
) -> None:
    native_scope = {
        "extent": "few_teeth",
        "jaw": "lower",
        "stage": "extraction_context",
        "modifiers": ["reported_bone_deficit"],
    }
    payload = _native_planner_payload(aspects=[], patient_scope=native_scope)
    calls, queued = _patch_real_planner_external_completion(monkeypatch, [payload])
    fallback_calls: list[dict] = []
    fallback_decision = _decision(
        route_intent="content",
        service_topic="prosthetics",
        service_id="veneers",
        query_mode="overview",
    )

    def _fallback(**kwargs):
        fallback_calls.append(copy.deepcopy(kwargs))
        return fallback_decision, [], "controlled-fallback"

    monkeypatch.setattr("orchestration.resolver_turn.resolve_with_fallback", _fallback)

    outcome, ctx = _run_real_planner_resolver(Flask(__name__), sid="native-invalid-legacy")

    assert len(calls) == 1
    assert queued == []
    assert len(fallback_calls) == 1
    assert "patient_scope" not in str(fallback_calls[0])
    assert ctx["turn_planner_used"] is False
    assert ctx["resolver_used"] is True
    assert "turn_plan" not in ctx
    assert ctx["turn_frame_shadow_status"] == SHADOW_STATUS_PARTIAL
    shadow = ctx["turn_frame_shadow"]
    assert shadow["patient_scope"] == native_scope
    assert shadow["field_meta"]["aspects"]["error"] == "aspects_empty"
    for field_name in ("extent", "jaw", "stage", "modifiers"):
        assert shadow["field_meta"]["patient_scope"][field_name]["provenance"] == (
            f"turn_plan.raw.patient_scope.{field_name}"
        )
    assert outcome.decision.model_dump() == fallback_decision.model_dump()
    assert outcome.intent == "content"
    assert outcome.scope_topic_candidate == "prosthetics"


@pytest.mark.parametrize("case_id", _A6_FAIL_OPEN_CASE_IDS)
def test_frozen_a6_partial_paths_keep_product_fallback(monkeypatch, case_id: str) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    case = _frozen_a6_case(case_id)
    question = case["question"]
    expected_topic = case["expected_topic"]
    attempt = _partial_attempt_for_topic(expected_topic)
    attempt_calls: list[tuple[str, str | None, str | None]] = []
    fallback_calls: list[dict] = []
    fallback_decision = _decision(
        route_intent="content",
        service_topic="prosthetics",
        service_id="veneers",
        query_mode="overview",
    )

    def _attempt(q, sid, client_id):
        attempt_calls.append((q, sid, client_id))
        return attempt

    def _fallback(**kwargs):
        fallback_calls.append(kwargs)
        return fallback_decision, [], "fallback-content"

    monkeypatch.setattr("orchestration.resolver_turn.TURN_PLANNER_ON", True)
    monkeypatch.setattr("core.turn_planner_llm.plan_turn_attempt", _attempt)
    monkeypatch.setattr(
        "core.turn_planner_llm.plan_turn",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("legacy wrapper called")),
    )
    monkeypatch.setattr(
        "core.turn_planner_llm.publish_turn_plan",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("partial plan published")),
    )
    monkeypatch.setattr("orchestration.resolver_turn.resolve_with_fallback", _fallback)

    sid = f"a7-regression-{case_id}"
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        outcome = run_resolver_turn(
            q=question,
            sid=sid,
            client_id="demo",
            st={"hist": []},
            enqueue_resolver_trace=lambda **_k: None,
        )

        assert attempt_calls == [(question, sid, "demo")]
        assert len(fallback_calls) == 1
        assert fallback_calls[0]["question"] == question
        assert request.ctx["turn_planner_used"] is False
        assert request.ctx["resolver_used"] is True
        assert request.ctx["legacy_intent"] == "fallback-content"
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_PARTIAL
        assert request.ctx["turn_frame_shadow"]["topic"] == expected_topic
        assert request.ctx["turn_frame_shadow"]["field_meta"]["aspects"]["error"] == "aspects_empty"
        assert outcome.decision.model_dump() == fallback_decision.model_dump()
        assert outcome.decision.service_topic == "prosthetics"
        assert outcome.intent == "content"
        if expected_topic is not None:
            assert outcome.scope_topic_candidate != expected_topic


def test_run_resolver_turn_degraded_shadow_keeps_valid_legacy_product_path(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan()
    attempt = PlannerAttempt(
        legacy_plan=turn_plan,
        shadow_frame=None,
        shadow_status="degraded",
    )
    monkeypatch.setattr("orchestration.resolver_turn.TURN_PLANNER_ON", True)
    monkeypatch.setattr("core.turn_planner_llm.plan_turn_attempt", lambda *_a, **_k: attempt)
    monkeypatch.setattr("core.turn_planner_llm.publish_turn_plan", lambda _p: None)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        outcome = run_resolver_turn(
            q="сколько стоит all-on-4?",
            sid="shadow-degraded-valid-legacy",
            client_id="demo",
            st={},
            enqueue_resolver_trace=lambda **_k: None,
        )

        assert outcome.intent == "price_lookup"
        assert outcome.decision.service_id == "all_on_4"
        assert request.ctx["turn_planner_used"] is True
        assert request.ctx["resolver_used"] is False
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_DEGRADED
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_BUILD_FAILED
        assert "turn_frame_shadow" not in request.ctx


def test_run_resolver_turn_source_uses_attempt_once_and_only_legacy_for_product() -> None:
    source = inspect.getsource(run_resolver_turn)
    assert source.count("plan_turn_attempt(q, sid, client_id)") == 1
    assert "plan_turn(q, sid, client_id)" not in source
    assert "plan = attempt.legacy_plan" in source
    assert "attempt.shadow_frame" not in source
    assert "attempt.shadow_status" not in source
    assert "record_planner_attempt_shadow(attempt=attempt)" in source
    assert "patient_scope" not in source


def _native_shadow_ast_hits(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            expression = ast.unparse(node)
            if node.attr == "patient_scope" and "shadow" in expression:
                hits.append(expression)
            if node.attr in {"extent", "jaw", "stage", "modifiers"}:
                if "patient_scope" in expression and "shadow" in expression:
                    hits.append(expression)
        if isinstance(node, ast.Subscript):
            expression = ast.unparse(node)
            key = node.slice.value if isinstance(node.slice, ast.Constant) else None
            if key == "patient_scope" and "turn_frame_shadow" in expression:
                hits.append(expression)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if any(alias.name == "PatientScopeFrame" for alias in node.names):
                hits.append("PatientScopeFrame import")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "PatientScopeFrame":
                hits.append("PatientScopeFrame constructor")
    return sorted(set(hits))


def test_product_sources_do_not_read_a9_nested_shadow_scope() -> None:
    paths = sorted(Path(".").glob("*.py"))
    paths.extend(sorted(Path("core").rglob("*.py")))
    paths.extend(sorted(Path("orchestration").rglob("*.py")))
    allowed = {
        "core/turn_frame_adapter.py",
        "core/turn_frame_from_raw.py",
    }
    forbidden = (
        "shadow_frame.patient_scope",
        '.patient_scope.extent',
        '.patient_scope.jaw',
        '.patient_scope.stage',
        '.patient_scope.modifiers',
        'turn_frame_shadow"]["patient_scope',
        "turn_frame_shadow']['patient_scope",
    )
    offenders: dict[str, list[str]] = {}
    for path in paths:
        relative = path.as_posix()
        if relative in allowed:
            continue
        source = path.read_text(encoding="utf-8")
        hits = [token for token in forbidden if token in source]
        hits.extend(_native_shadow_ast_hits(path))
        if hits:
            offenders[relative] = sorted(set(hits))
    assert offenders == {}

    from core.turn_planner_llm import publish_turn_plan, turn_plan_to_decision_frame

    for product_boundary in (turn_plan_to_decision_frame, publish_turn_plan):
        assert "patient_scope" not in inspect.getsource(product_boundary)
    assert "patient_scope" not in TurnPlan.model_fields


def test_run_resolver_turn_comparison_override_does_not_rebuild_raw_shadow(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    from core.turn_planner_llm import turn_plan_to_decision_frame

    turn_plan = _turn_plan(route="content", aspects=["overview"])
    pre_override_decision = turn_plan_to_decision_frame(turn_plan, client_id="demo")
    assert pre_override_decision.query_mode != "comparison"

    comparison_question = "что лучше all-on-4 или 6?"
    attempt = _ok_attempt(turn_plan)

    monkeypatch.setattr("orchestration.resolver_turn.TURN_PLANNER_ON", True)
    monkeypatch.setattr("core.turn_planner_llm.plan_turn_attempt", lambda *_a, **_k: attempt)
    monkeypatch.setattr("core.turn_planner_llm.publish_turn_plan", lambda _p: None)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        outcome = run_resolver_turn(
            q=comparison_question,
            sid="shadow-comparison-override",
            client_id="demo",
            st={},
            enqueue_resolver_trace=lambda **_k: None,
        )

        assert outcome.decision.query_mode == "comparison"
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_OK
        assert request.ctx["turn_frame_shadow"] == attempt.shadow_frame.model_dump()
        assert request.ctx["turn_frame_shadow"]["specificity"] == "unknown"


def test_record_turn_frame_shadow_degraded_on_model_dump_failure(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan()
    decision = _decision()

    class _FrameWithBadDump:
        def model_dump(self):
            raise RuntimeError("serialization exploded with secret")

    monkeypatch.setattr(
        "core.turn_frame_shadow.build_turn_frame_from_legacy",
        lambda **_kwargs: _FrameWithBadDump(),
    )
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        frame = record_turn_frame_shadow(turn_plan=turn_plan, decision_frame=decision)

        assert frame is None
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_DEGRADED
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_BUILD_FAILED
        assert "turn_frame_shadow" not in request.ctx
        assert "serialization exploded" not in str(request.ctx)


def test_record_turn_frame_shadow_degraded_survives_emit_bot_event_failure(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan()
    decision = _decision()

    monkeypatch.setattr(
        "core.turn_frame_shadow.build_turn_frame_from_legacy",
        lambda **_kwargs: (_ for _ in ()).throw(ValueError("builder failed")),
    )

    def _emit_boom(*_args, **_kwargs):
        raise RuntimeError("telemetry sink unavailable")

    monkeypatch.setattr("core.turn_frame_shadow.emit_bot_event", _emit_boom)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        frame = record_turn_frame_shadow(turn_plan=turn_plan, decision_frame=decision)

        assert frame is None
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_DEGRADED
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_BUILD_FAILED
        assert "turn_frame_shadow" not in request.ctx


def test_record_turn_frame_shadow_uses_native_topic_provenance() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan(topic="implantation", topic_confidence=0.82)
    decision = _decision(service_topic="prosthetics")
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        record_turn_frame_shadow(turn_plan=turn_plan, decision_frame=decision)

        snapshot = request.ctx["turn_frame_shadow"]
        assert snapshot["topic"] == "implantation"
        assert snapshot["field_meta"]["topic"]["provenance"] == "turn_plan.topic"
        assert snapshot["field_meta"]["topic"]["confidence"] == 0.82


def test_native_topic_does_not_change_shadow_intent_or_service_axes() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan(
        route="price_lookup",
        aspects=["price", "duration"],
        service_id="all_on_4",
        followup_of="all_on_4",
        topic="implantation",
        topic_confidence=0.77,
    )
    decision = _decision(
        route_intent="content",
        service_topic="prosthetics",
        service_id="veneers",
        query_mode="overview",
    )
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        record_turn_frame_shadow(turn_plan=turn_plan, decision_frame=decision)

        snapshot = request.ctx["turn_frame_shadow"]
        assert snapshot["intent"] == "content"
        assert snapshot["aspects"] == ["price", "duration"]
        assert snapshot["service_id"] == "all_on_4"
        assert snapshot["followup_of"] == "all_on_4"
        assert snapshot["topic"] == "implantation"
