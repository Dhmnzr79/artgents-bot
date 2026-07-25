from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from flask import Flask

from contracts.planner_attempt import PlannerAttempt
from contracts.turn_frame import TurnFrame
from contracts.turn_plan import TurnPlan
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
)
from orchestration.planner_turn import run_planner_turn


def _raw_shadow_frame(**overrides) -> TurnFrame:
    payload = {
        "route": "price_lookup",
        "aspects": ["price"],
        "service_id": "all_on_4",
        "topic": "implantation",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=frozenset({"doctors", "implantation"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )


def _ok_attempt() -> PlannerAttempt:
    return PlannerAttempt(frame=_raw_shadow_frame(), status="ok")


def _partial_doctors_attempt() -> PlannerAttempt:
    return PlannerAttempt(
        frame=_raw_shadow_frame(
            route="content",
            topic="doctors",
            topic_confidence=0.95,
            aspects=[],
            service_id=None,
        ),
        status="partial",
    )


def _patient_scope_attempt(
    patient_situation: str,
    *,
    partial: bool = False,
) -> PlannerAttempt:
    aspects = [] if partial else ["overview"]
    frame = _raw_shadow_frame(
        route="content",
        aspects=aspects,
        topic="implantation",
        topic_confidence=0.9,
        patient_situation=patient_situation,
        service_id=None,
    )
    return PlannerAttempt(frame=frame, status="partial" if partial else "ok")


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


def test_record_planner_attempt_shadow_not_available_clears_stale_frame() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    attempt = PlannerAttempt(frame=None, status="not_available")
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
    attempt = PlannerAttempt(frame=None, status="degraded")
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
    attempt = PlannerAttempt(frame=None, status="degraded")
    monkeypatch.setattr(
        "core.runtime_turn_frame.emit_bot_event",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("sink failed")),
    )
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        frame = record_planner_attempt_shadow(attempt=attempt)

        assert frame is None
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_DEGRADED
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_BUILD_FAILED


def test_shadow_recorder_signatures_exclude_question_like_params() -> None:
    forbidden = {"question", "answer", "history", "payload", "q"}
    for fn in (
        record_planner_attempt_shadow,
        mark_turn_frame_shadow_not_available,
    ):
        params = set(inspect.signature(fn).parameters)
        assert params.isdisjoint(forbidden)


def test_run_planner_turn_planner_success_records_shadow(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    attempt = _ok_attempt()
    monkeypatch.setattr("orchestration.planner_turn.plan_turn_attempt", lambda *_a, **_k: attempt)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        run_planner_turn(
            q="сколько стоит all-on-4?",
            sid="shadow-success",
            client_id="demo",
            st={},
            enqueue_resolver_trace=lambda **_k: None,
        )

        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_OK
        assert request.ctx["turn_frame_shadow"] == attempt.shadow_frame.model_dump()
        assert request.ctx["turn_planner_used"] is True
        assert request.ctx["resolver_used"] is False


def test_run_planner_turn_not_available_fail_closed_without_resolver(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    resolver = MagicMock()
    monkeypatch.setattr(
        "orchestration.planner_turn.plan_turn_attempt",
        lambda *_a, **_k: PlannerAttempt(frame=None, status="not_available"),
    )
    monkeypatch.setattr("resolver.resolve_with_fallback", resolver)

    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        run_planner_turn(
            q="сколько стоит?",
            sid="shadow-missing-plan",
            client_id="demo",
            st={"hist": []},
            enqueue_resolver_trace=lambda **_k: None,
        )

        resolver.assert_not_called()
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_NOT_AVAILABLE
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_TURN_PLAN_MISSING
        assert "turn_frame_shadow" not in request.ctx
        assert request.ctx["turn_planner_used"] is False
        assert request.ctx["resolver_used"] is False


def test_run_planner_turn_partial_frame_published_without_resolver(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    attempt_calls: list[tuple[str, str, str]] = []
    attempt = _partial_doctors_attempt()
    resolver = MagicMock()

    def _attempt(q, sid, client_id):
        attempt_calls.append((q, sid, client_id))
        return attempt

    monkeypatch.setattr("orchestration.planner_turn.plan_turn_attempt", _attempt)
    monkeypatch.setattr("resolver.resolve_with_fallback", resolver)

    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        outcome = run_planner_turn(
            q="Кто занимается лечением?",
            sid="shadow-partial-no-resolver",
            client_id="demo",
            st={"hist": []},
            enqueue_resolver_trace=lambda **_k: None,
        )

        assert attempt_calls == [("Кто занимается лечением?", "shadow-partial-no-resolver", "demo")]
        resolver.assert_not_called()
        assert request.ctx["turn_planner_used"] is True
        assert request.ctx["resolver_used"] is False
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_PARTIAL
        assert request.ctx["turn_frame_shadow"]["topic"] == "doctors"
        assert request.ctx["turn_frame_shadow"]["field_meta"]["aspects"]["error"] == "aspects_empty"
        assert outcome.intent == "content"
        assert outcome.scope_topic_candidate == "doctors"


def test_a9_partial_scope_is_observable_but_does_not_invoke_resolver(monkeypatch) -> None:
    app = Flask(__name__)
    attempt = _patient_scope_attempt("one_tooth_missing", partial=True)
    recorder_calls: list[PlannerAttempt] = []
    resolver = MagicMock()

    def _record(*, attempt):
        recorder_calls.append(attempt)
        return record_planner_attempt_shadow(attempt=attempt)

    monkeypatch.setattr(
        "orchestration.planner_turn.plan_turn_attempt",
        lambda *_args, **_kwargs: attempt,
    )
    monkeypatch.setattr("orchestration.planner_turn.publish_planner_attempt_frame", _record)
    monkeypatch.setattr("resolver.resolve_with_fallback", resolver)

    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        outcome = run_planner_turn(
            q="Секретный вопрос пациента",
            sid="a9-shadow-partial",
            client_id="demo",
            st={"hist": []},
            enqueue_resolver_trace=lambda **_kwargs: None,
        )

        assert recorder_calls == [attempt]
        resolver.assert_not_called()
        assert request.ctx["turn_planner_used"] is True
        assert request.ctx["resolver_used"] is False
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_PARTIAL
        snapshot = request.ctx["turn_frame_shadow"]
        assert snapshot["patient_scope"]["extent"] == "one_tooth"
        assert snapshot["field_meta"]["patient_scope"]["extent"]["status"] == "valid"
        assert snapshot["field_meta"]["aspects"]["error"] == "aspects_empty"
        assert "Секретный вопрос" not in str(snapshot)
        assert outcome.intent == "content"
        assert outcome.scope_topic_candidate == "implantation"


def test_run_planner_turn_source_uses_single_planner_call_without_resolver() -> None:
    source = inspect.getsource(run_planner_turn)
    assert source.count("plan_turn_attempt(q, sid, client_id)") == 1
    assert "plan_turn(q, sid, client_id)" not in source
    assert "legacy_plan" not in source
    assert "attempt.shadow_frame" not in source
    assert "attempt.shadow_status" not in source
    assert "resolve_with_fallback" not in source
    assert "publish_planner_attempt_frame" in source
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
        "core/turn_frame_from_raw.py",
        "core/target_patient_scope_projection.py",
    }
    forbidden = (
        "shadow_frame.patient_scope",
        ".patient_scope.extent",
        ".patient_scope.jaw",
        ".patient_scope.stage",
        ".patient_scope.modifiers",
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
    assert "patient_scope" not in TurnPlan.model_fields
