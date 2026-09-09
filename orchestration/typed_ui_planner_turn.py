"""Typed UI TurnFrame ingress — skip LLM planner for governed UI clicks."""

from __future__ import annotations

from collections.abc import Callable

from contracts.ui_scope_action import UiScopeAction
from contracts.ui_service_action import UiServiceAction
from contracts.ui_stage_action import UiStageAction
from core import turn_timing
from core.metadata_first_observability import record_decision_frame_ctx
from core.runtime_turn_frame import (
    RUNTIME_FRAME_STATUS_OK,
    get_runtime_turn_frame_status,
    publish_typed_ui_turn_frame,
)
from core.target_typed_ui_turn_frame import (
    build_typed_ui_turn_frame_from_scope_action,
    build_typed_ui_turn_frame_from_service_action,
    build_typed_ui_turn_frame_from_stage_action,
)
from orchestration.planner_turn import PlannerTurnOutcome


def _ctx_action(raw: object, model: type) -> object | None:
    if not isinstance(raw, dict):
        return None
    try:
        return model.model_validate(raw)
    except Exception:
        return None


def _current_ui_scope_action() -> UiScopeAction | None:
    try:
        from flask import request

        return _ctx_action(request.ctx.get("current_ui_scope_action"), UiScopeAction)
    except Exception:
        return None


def _current_ui_stage_action() -> UiStageAction | None:
    try:
        from flask import request

        return _ctx_action(request.ctx.get("current_ui_stage_action"), UiStageAction)
    except Exception:
        return None


def _current_ui_service_action() -> UiServiceAction | None:
    try:
        from flask import request

        return _ctx_action(request.ctx.get("current_ui_service_action"), UiServiceAction)
    except Exception:
        return None


def try_run_typed_ui_planner_turn(
    *,
    sid: str,
    client_id: str,
    enqueue_resolver_trace: Callable[..., None],
) -> PlannerTurnOutcome | None:
    """Publish native typed TurnFrame when a governed UI action is on ctx."""

    service_action = _current_ui_service_action()
    stage_action = _current_ui_stage_action()
    scope_action = _current_ui_scope_action()
    if service_action is None and stage_action is None and scope_action is None:
        return None

    if service_action is not None:
        from contracts.target_service_content_topic import parse_service_catalog_content_topic
        from core.target_runtime_client_context import load_target_runtime_client_context

        runtime_context = load_target_runtime_client_context(client_id)
        service = runtime_context.bundle.services.get(service_action.service_id)
        topic = (
            parse_service_catalog_content_topic(service.content_ref)
            if service is not None
            else None
        )
        if not topic:
            return None
        frame = build_typed_ui_turn_frame_from_service_action(
            service_action,
            topic=topic,
        )
    elif stage_action is not None:
        frame = build_typed_ui_turn_frame_from_stage_action(stage_action)
    else:
        assert scope_action is not None
        frame = build_typed_ui_turn_frame_from_scope_action(scope_action)

    publish_typed_ui_turn_frame(frame)
    status = get_runtime_turn_frame_status()
    if status != RUNTIME_FRAME_STATUS_OK:
        return None

    try:
        from flask import request

        request.ctx["resolver_used"] = False
        request.ctx["safety_net_used"] = False
        request.ctx["effective_intent"] = "price_lookup"
    except Exception:
        pass

    record_decision_frame_ctx(None)
    enqueue_resolver_trace(
        decision=None,
        safety_net_used=[],
        resolver_bypassed_env=False,
    )
    turn_timing.stage_skipped("planner", reason="typed_ui")
    topic = str(frame.topic or "").strip().lower() or None
    return PlannerTurnOutcome(intent="price_lookup", scope_topic_candidate=topic)
