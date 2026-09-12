"""Build and thread governed UI action context into target Composer."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from contracts.target_composer_action_context import TargetComposerActionContext
from contracts.ui_scope_action import UiScopeAction, parse_ui_scope_ref
from contracts.ui_stage_action import UiStageAction, parse_ui_stage_ref

_pending_ui_scope_action: ContextVar[UiScopeAction | None] = ContextVar(
    "target_pending_ui_scope_action",
    default=None,
)
_pending_ui_stage_action: ContextVar[UiStageAction | None] = ContextVar(
    "target_pending_ui_stage_action",
    default=None,
)


def bind_pending_ui_actions_for_composer(
    *,
    scope_action: UiScopeAction | None,
    stage_action: UiStageAction | None,
) -> tuple[Any, Any]:
    """Bind validated request UI actions for the current runtime turn."""

    try:
        from flask import request

        nav_ref = str(request.ctx.get("nav_ref") or "").strip()
        if scope_action is None and nav_ref:
            scope_action = parse_ui_scope_ref(nav_ref)
        if stage_action is None and nav_ref:
            stage_action = parse_ui_stage_ref(nav_ref)
    except Exception:
        pass
    return (
        _pending_ui_scope_action.set(scope_action),
        _pending_ui_stage_action.set(stage_action),
    )


def reset_pending_ui_actions_for_composer(tokens: tuple[Any, Any]) -> None:
    scope_token, stage_token = tokens
    _pending_ui_scope_action.reset(scope_token)
    _pending_ui_stage_action.reset(stage_token)


def read_pending_ui_actions_for_composer() -> tuple[UiScopeAction | None, UiStageAction | None]:
    scope_action = _pending_ui_scope_action.get()
    stage_action = _pending_ui_stage_action.get()
    try:
        from flask import has_request_context, request

        if has_request_context():
            scope_raw = request.ctx.get("current_ui_scope_action")
            stage_raw = request.ctx.get("current_ui_stage_action")
            if isinstance(scope_raw, dict):
                try:
                    scope_action = UiScopeAction.model_validate(scope_raw)
                except Exception:
                    pass
            if isinstance(stage_raw, dict):
                try:
                    stage_action = UiStageAction.model_validate(stage_raw)
                except Exception:
                    pass
            if scope_action is None and stage_action is None:
                nav_ref = str(request.ctx.get("nav_ref") or "").strip()
                if nav_ref:
                    scope_action = parse_ui_scope_ref(nav_ref)
                    stage_action = parse_ui_stage_ref(nav_ref)
    except Exception:
        pass
    return scope_action, stage_action


def build_target_composer_action_context(
    *,
    scope_action: UiScopeAction | None,
    stage_action: UiStageAction | None,
    response_stage: str | None,
) -> TargetComposerActionContext | None:
    """Build Composer action context only from validated session-bound UI actions."""

    if response_stage is None or not str(response_stage).strip():
        return None
    stage_eff = str(response_stage).strip()
    if scope_action is not None and stage_action is not None:
        return None
    if scope_action is not None:
        return TargetComposerActionContext(
            action_kind="ui_scope",
            topic=scope_action.topic,
            governed_ref=scope_action.ref,
            response_stage=stage_eff,
            extent=scope_action.extent,
            stage=None,
        )
    if stage_action is not None:
        return TargetComposerActionContext(
            action_kind="ui_stage",
            topic=stage_action.topic,
            governed_ref=stage_action.ref,
            response_stage=stage_eff,
            extent=None,
            stage=stage_action.stage,
        )
    return None


def resolve_target_composer_action_context(
    *,
    response_stage: str | None,
    scope_action: UiScopeAction | None = None,
    stage_action: UiStageAction | None = None,
) -> TargetComposerActionContext | None:
    if scope_action is None and stage_action is None:
        scope_action, stage_action = read_pending_ui_actions_for_composer()
    return build_target_composer_action_context(
        scope_action=scope_action,
        stage_action=stage_action,
        response_stage=response_stage,
    )


def composer_action_context_payload(
    action_context: TargetComposerActionContext | None,
) -> dict[str, object] | None:
    if action_context is None:
        return None
    return action_context.model_dump(mode="json")
