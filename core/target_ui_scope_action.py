"""Hydrate typed UiScopeAction from governed session-bound refs (AC1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.ui_scope_action import UiScopeAction, is_ui_scope_ref, parse_ui_scope_ref
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem


@dataclass(frozen=True, slots=True)
class UiScopeRefResolution:
    kind: Literal["ok", "clarify"]
    action: UiScopeAction | None = None
    planner_message: str | None = None


def _ref_in_followups(
    ref: str,
    followups: tuple[TargetRuntimeFollowupItem, ...],
) -> TargetRuntimeFollowupItem | None:
    ref_eff = str(ref).strip()
    for item in followups:
        if item.ref == ref_eff:
            return item
    return None


def resolve_ui_scope_ref_click(
    *,
    ref: str,
    followups: tuple[TargetRuntimeFollowupItem, ...],
) -> UiScopeRefResolution:
    """Session-bound typed ref resolution; fail-closed on malformed or unshown refs."""

    ref_eff = str(ref or "").strip()
    if not is_ui_scope_ref(ref_eff):
        return UiScopeRefResolution(kind="clarify")
    action = parse_ui_scope_ref(ref_eff)
    if action is None:
        return UiScopeRefResolution(kind="clarify")
    shown = _ref_in_followups(ref_eff, followups)
    if shown is None:
        return UiScopeRefResolution(kind="clarify")
    planner_message = shown.label.strip() or None
    return UiScopeRefResolution(
        kind="ok",
        action=action,
        planner_message=planner_message,
    )
