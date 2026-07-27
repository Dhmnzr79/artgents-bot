"""Shared offline harness for FINAL_PRICE_ONLY_SOURCE_SUFFICIENCY_CONVERGENCE."""

from __future__ import annotations

import json
import uuid
from typing import Any

from flask import Flask, request

from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
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
    build_frame,
    orchestrate_via_app,
)

__all__ = [
    "BackendPayload",
    "MessageBuildingComposerBackend",
    "RecordingBoundaryBackend",
    "RecordingSemanticBackend",
    "assert_materialized_route",
    "assert_not_error_route",
    "build_frame",
    "orchestrate_via_app",
    "availability_frame",
    "offer_evidence",
    "price_frame",
    "run_price_turn",
]

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
        "professional_whitening",
        "one_stage",
        "braces_fixture",
    }
)


def availability_frame(service_id: str = "tomography", **overrides: object):
    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["service_availability"],
        "primary_aspect": "service_availability",
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


def price_frame(service_id: str = "tomography", **overrides: object):
    payload: dict[str, object] = {
        "route": "price_lookup",
        "aspects": ["price"],
        "primary_aspect": "price",
        "service_id": service_id,
        "service_confidence": 0.95,
        "topic": "implantation",
        "topic_confidence": 0.9,
        "intent": "price_lookup",
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )


def run_price_turn(
    frame,
    *,
    user_message: str,
    composer_text: str,
    sid: str | None = None,
    primary_ref: str | None = None,
    boundary: BackendPayload | None = None,
):
    sid = sid or f"posc-{uuid.uuid4().hex[:10]}"
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


def offer_evidence(composer: MessageBuildingComposerBackend) -> list[dict[str, Any]]:
    assert composer.invocations, "composer was not invoked"
    evidence = json.loads(composer.invocations[0].primary_evidence_json)
    return [item for item in evidence if item["kind"] == "offer"]


def content_evidence(composer: MessageBuildingComposerBackend) -> list[dict[str, Any]]:
    assert composer.invocations, "composer was not invoked"
    evidence = json.loads(composer.invocations[0].primary_evidence_json)
    return [item for item in evidence if item["kind"] == "content"]


def assert_materialized_price(
    outcome,
    composer: MessageBuildingComposerBackend,
    *,
    expect_composer: bool = True,
) -> None:
    assert outcome.widget.kind == "materialized"
    meta = outcome.widget.payload.get("meta") or {}
    assert_materialized_route(meta)
    assert_not_error_route(meta)
    if expect_composer:
        assert len(composer.invocations) == 1
    else:
        assert len(composer.invocations) == 0


def bound_materialized(result: object) -> TargetTurnFrameBoundMaterializeResponse:
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    return result
