"""Neutral target-runtime test utilities (no legacy orchestration entry points)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.ingress_route import IngressRouteResult
from contracts.planner_attempt import PlannerAttempt
from core.runtime_turn_frame import publish_planner_attempt_frame
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.target_runtime_turn import run_target_fullcontext_runtime_turn
from core.turn_frame_from_raw import build_turn_frame_from_raw
from tests.test_target_boundary_enforced_fullcontext_response import (
    PRICE_TEXT,
    RecordingComposerBackend,
    RecordingSemanticBackend,
)


@dataclass
class BackendPayload:
    decision: str
    confidence: float


class RecordingBoundaryBackend:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.invocations: list[object] = []

    def classify(self, invocation: object, /) -> object:
        self.invocations.append(invocation)
        return self.payload


def _turn_frame(**overrides: object):
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
        allowed_topics=frozenset({"implantation", "doctors", "aesthetics", "prosthetics"}),
        allowed_service_ids=frozenset({"all_on_4", "veneers"}),
    )


def _install_turn_frame(frame) -> None:
    publish_planner_attempt_frame(
        attempt=PlannerAttempt(frame=frame, status="ok"),
    )


def _fake_backends():
    return (
        RecordingComposerBackend(PRICE_TEXT),
        RecordingSemanticBackend(),
        RecordingBoundaryBackend(BackendPayload(decision="none", confidence=0.95)),
    )


def _fake_classify_ingress_normal(*_a, **_k) -> IngressRouteResult:
    """Fake ingress classify for offline HTTP tests that mock planner but not ingress LLM."""
    return IngressRouteResult(
        route="normal",
        confidence=0.9,
        reason="fake_offline_normal",
        policy_key=None,
        requested_service=None,
        source="llm",
        is_urgent=False,
    )


def _seed_followups(sid: str, *items: TargetRuntimeFollowupItem) -> None:
    from session import _lock, _persist_unlocked, mem_get, session_client_scope

    with session_client_scope("demo"):
        with _lock:
            st = mem_get(sid)
            st["target_runtime_followups"] = [
                {"ref": item.ref, "label": item.label} for item in items
            ]
            _persist_unlocked(sid, st)


def _seed_target_runtime_state(sid: str, **fields: object) -> None:
    from session import _lock, _persist_unlocked, mem_get, session_client_scope

    with session_client_scope("demo"):
        with _lock:
            st = mem_get(sid)
            if fields.get("last_service_id") and "service_focus_set_at_turn" not in fields:
                fields = dict(fields)
                fields.setdefault("service_focus_set_at_turn", int(st.get("session_turn_count") or 0))
            st["target_runtime_state"] = fields
            _persist_unlocked(sid, st)


def _price_turn_frame():
    return _turn_frame(primary_aspect="price", aspects=["price"])


def _run_materialized_turn(
    sid: str,
    *,
    user_message: str = "Сколько стоит All-on-4?",
    composer_text: str = PRICE_TEXT,
    frame=None,
):
    from session import session_client_scope

    _install_turn_frame(frame or _price_turn_frame())
    with session_client_scope("demo"):
        return run_target_fullcontext_runtime_turn(
            client_id="demo",
            sid=sid,
            user_message=user_message,
            composer_backend=RecordingComposerBackend(composer_text),
            semantic_backend=RecordingSemanticBackend(),
            boundary_backend=RecordingBoundaryBackend(
                BackendPayload(decision="none", confidence=0.95)
            ),
        )
