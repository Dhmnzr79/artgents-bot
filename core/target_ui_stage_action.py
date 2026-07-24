"""Hydrate typed UiStageAction from governed session-bound refs (AC3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.ui_stage_action import UiStageAction, is_ui_stage_ref, parse_ui_stage_ref
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem


@dataclass(frozen=True, slots=True)
class UiStageRefResolution:
    kind: Literal["ok", "clarify"]
    action: UiStageAction | None = None
    planner_message: str | None = None


def resolve_ui_stage_ref_click(
    *,
    ref: str,
    followups: tuple[TargetRuntimeFollowupItem, ...],
) -> UiStageRefResolution:
    ref_eff = str(ref or "").strip()
    if not is_ui_stage_ref(ref_eff):
        return UiStageRefResolution(kind="clarify")
    action = parse_ui_stage_ref(ref_eff)
    if action is None:
        return UiStageRefResolution(kind="clarify")
    shown = next((item for item in followups if item.ref == ref_eff), None)
    if shown is None:
        return UiStageRefResolution(kind="clarify")
    planner_message = shown.label.strip() or None
    return UiStageRefResolution(
        kind="ok",
        action=action,
        planner_message=planner_message,
    )
