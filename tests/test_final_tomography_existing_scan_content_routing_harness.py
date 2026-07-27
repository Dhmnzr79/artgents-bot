"""Shared offline harness for FINAL_TOMOGRAPHY_EXISTING_SCAN_CONTENT_ROUTING."""

from __future__ import annotations

import uuid
from typing import Any

from flask import Flask, request

from core.runtime_turn_frame import publish_planner_attempt_frame
from core.target_runtime_turn import run_target_fullcontext_runtime_turn
from core.turn_frame_from_raw import build_turn_frame_from_raw
from session import mem_reset
from tests.test_final_fullcontext_dialogue_runtime_convergence_harness import (
    BackendPayload,
    MessageBuildingComposerBackend,
    RecordingBoundaryBackend,
    RecordingSemanticBackend,
    _planner_attempt,
    assert_materialized_route,
    assert_not_error_route,
    orchestrate_via_app,
)
from tests.test_final_price_only_source_sufficiency_convergence_harness import (
    availability_frame,
    price_frame,
    run_price_turn,
)

__all__ = [
    "BackendPayload",
    "MessageBuildingComposerBackend",
    "RecordingBoundaryBackend",
    "RecordingSemanticBackend",
    "assert_materialized_route",
    "assert_not_error_route",
    "availability_frame",
    "content_frame",
    "orchestrate_via_app",
    "price_frame",
    "quick_reply_refs",
    "run_content_turn",
    "run_price_turn",
]

_ALLOWED_TOPICS = frozenset(
    {"implantation", "doctors", "clinic", "prosthetics", "aesthetics", "whitening"}
)
_ALLOWED_SERVICES = frozenset(
    {
        "all_on_4",
        "classic",
        "tomography",
        "professional_whitening",
    }
)

PRIMARY_REF = "diagnostics__service__tomography.md"


def content_frame(service_id: str = "tomography", **overrides: object):
    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["overview"],
        "primary_aspect": "overview",
        "service_id": service_id,
        "service_confidence": 0.95,
        "topic": "clinic",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )


def run_content_turn(
    frame,
    *,
    user_message: str,
    composer_text: str,
    sid: str | None = None,
    primary_ref: str = PRIMARY_REF,
    boundary: BackendPayload | None = None,
):
    sid = sid or f"tom-ct-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    boundary_backend = RecordingBoundaryBackend(boundary or BackendPayload("none", 0.95))
    composer = MessageBuildingComposerBackend(composer_text, primary_ref=primary_ref)
    semantic = RecordingSemanticBackend()
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
            boundary_backend=boundary_backend,
        )
    return outcome, composer, semantic, boundary_backend, sid


def assert_materialized_content(
    outcome,
    composer: MessageBuildingComposerBackend,
    *,
    expect_composer: bool = True,
) -> None:
    assert outcome.widget.kind == "materialized"
    meta = outcome.widget.payload.get("meta") or {}
    assert_materialized_route(meta)
    assert_not_error_route(meta)
    assert "оказывает услугу" not in (outcome.widget.payload.get("answer") or "")
    if expect_composer:
        assert len(composer.invocations) == 1
    else:
        assert len(composer.invocations) == 0


def quick_reply_refs(payload: dict[str, Any]) -> list[str]:
    replies = payload.get("quick_replies") or []
    return [str(item.get("ref") or "") for item in replies if isinstance(item, dict)]
