"""Shared offline widget-faithful harness for dialogue runtime convergence tests."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from flask import Flask, request

from contracts.planner_attempt import PlannerAttempt, turn_frame_has_invalid_or_missing
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
from core.runtime_turn_frame import publish_planner_attempt_frame
from core.target_composer_executor import TargetComposerInvocation
from core.target_composer_output import composer_test_json
from core.target_response_verifier import TargetSemanticAssessment
from core.target_runtime_llm_messages import build_composer_sdk_messages
from core.target_runtime_turn import run_target_fullcontext_runtime_turn
from core.turn_frame_from_raw import build_turn_frame_from_raw
from orchestration.planner_turn import PlannerTurnOutcome
from session import mem_reset


@dataclass
class BackendPayload:
    decision: str
    confidence: float


class MessageBuildingComposerBackend:
    def __init__(self, text: str, *, primary_ref: str | None = None) -> None:
        self.text = text
        self.primary_ref = primary_ref
        self.invocations: list[TargetComposerInvocation] = []
        self.sdk_messages: list[list[dict[str, str]]] = []

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.invocations.append(invocation)
        self.sdk_messages.append(build_composer_sdk_messages(invocation))
        return composer_test_json(self.text, primary_content_ref=self.primary_ref)


class RecordingSemanticBackend:
    def __init__(self) -> None:
        self.invocations: list[object] = []

    def assess(self, invocation: object, /) -> object:
        self.invocations.append(invocation)
        return TargetSemanticAssessment()


class RecordingBoundaryBackend:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.invocations: list[object] = []

    def classify(self, invocation: object, /) -> object:
        self.invocations.append(invocation)
        if isinstance(self.payload, BackendPayload):
            return {
                "decision": self.payload.decision,
                "confidence": self.payload.confidence,
            }
        return self.payload


def build_frame(
    *,
    allowed_topics: frozenset[str],
    allowed_service_ids: frozenset[str],
    **overrides: object,
):
    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["overview"],
        "primary_aspect": "overview",
        "service_id": None,
        "topic": "implantation",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=allowed_topics,
        allowed_service_ids=allowed_service_ids,
    )


def _planner_attempt(frame) -> PlannerAttempt:
    status = "partial" if turn_frame_has_invalid_or_missing(frame) else "ok"
    return PlannerAttempt(frame=frame, status=status)  # type: ignore[arg-type]


def install_turn_frame(frame) -> None:
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        publish_planner_attempt_frame(attempt=_planner_attempt(frame))


def default_backends(
    composer_text: str,
    *,
    primary_ref: str | None = None,
    boundary: BackendPayload | None = None,
):
    return (
        MessageBuildingComposerBackend(composer_text, primary_ref=primary_ref),
        RecordingSemanticBackend(),
        RecordingBoundaryBackend(boundary or BackendPayload("none", 0.95)),
    )


def run_runtime_turn(
    *,
    sid: str,
    user_message: str,
    composer_text: str,
    frame,
    primary_ref: str | None = None,
):
    composer, semantic, boundary = default_backends(
        composer_text,
        primary_ref=primary_ref,
    )
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        publish_planner_attempt_frame(attempt=_planner_attempt(frame))
        outcome = run_target_fullcontext_runtime_turn(
            client_id="demo",
            sid=sid,
            user_message=user_message,
            composer_backend=composer,
            semantic_backend=semantic,
            boundary_backend=boundary,
        )
    return outcome, composer, semantic


def _parse_stream_ui(response) -> dict:
    import json

    for line in response.data.decode("utf-8").splitlines():
        if line.startswith("data: "):
            payload = json.loads(line[6:])
            if isinstance(payload, dict) and "meta" in payload:
                return payload
    raise AssertionError("stream_ui_payload_missing")


def orchestrate_via_app(
    monkeypatch,
    app_module,
    *,
    endpoint: str,
    q: str,
    frame,
    composer_text: str,
    sid: str | None = None,
    primary_ref: str | None = None,
) -> tuple[dict, MessageBuildingComposerBackend, str]:
    """Exercise real app._orchestrate_ask_turn with fakes only at LLM backends."""

    sid = sid or f"dlg-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    composer, semantic, boundary = default_backends(
        composer_text,
        primary_ref=primary_ref,
    )

    def _publish_frame(**_kwargs: object) -> PlannerTurnOutcome:
        publish_planner_attempt_frame(attempt=_planner_attempt(frame))
        return PlannerTurnOutcome("content", None)

    monkeypatch.setattr(app_module, "run_planner_turn", _publish_frame)
    monkeypatch.setattr(
        "orchestration.target_fullcontext_turn._default_target_runtime_backends",
        lambda: (composer, semantic, boundary),
    )

    client = app_module.app.test_client()
    response = client.post(
        endpoint,
        json={"q": q, "sid": sid, "client_id": "demo"},
    )
    assert response.status_code == 200
    if endpoint == "/ask/stream":
        body = _parse_stream_ui(response)
    else:
        body = response.get_json()
    assert body is not None
    return body, composer, sid


def orchestrate_http(
    monkeypatch,
    app_module,
    *,
    endpoint: str,
    q: str,
    sid: str | None = None,
    composer_text: str,
    frame,
    data: dict[str, Any] | None = None,
):
    _ = data
    body, composer, sid = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint=endpoint,
        q=q,
        frame=frame,
        composer_text=composer_text,
        sid=sid,
    )
    return body, composer, sid


def assert_materialized_route(meta: dict[str, object]) -> None:
    route = str(meta.get("service_route") or "")
    assert route == "target_fullcontext_materialized", route


def assert_not_error_route(meta: dict[str, object]) -> None:
    route = str(meta.get("service_route") or "")
    assert route not in {
        "target_fullcontext_error",
        "target_fullcontext_verifier_blocked",
    }, route


def pipeline_result_materialized(outcome) -> TargetTurnFrameBoundMaterializeResponse | None:
    result = outcome.pipeline_result
    if isinstance(result, TargetTurnFrameBoundMaterializeResponse):
        return result
    return None
