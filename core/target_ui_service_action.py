"""Hydrate typed UiServiceAction from governed session-bound refs (Stage 5.1B)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.ui_service_action import UiServiceAction, is_ui_service_ref, parse_ui_service_ref
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem


@dataclass(frozen=True, slots=True)
class UiServiceRefResolution:
    kind: Literal["ok", "clarify"]
    action: UiServiceAction | None = None
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


def resolve_ui_service_ref_click(
    *,
    ref: str,
    followups: tuple[TargetRuntimeFollowupItem, ...],
    active_service_ids: frozenset[str] | None = None,
    expected_client_id: str | None = None,
) -> UiServiceRefResolution:
    """Session-bound typed ref resolution; fail-closed on malformed, unshown or inactive refs."""

    ref_eff = str(ref or "").strip()
    if not is_ui_service_ref(ref_eff):
        return UiServiceRefResolution(kind="clarify")
    action = parse_ui_service_ref(ref_eff)
    if action is None:
        return UiServiceRefResolution(kind="clarify")
    if action.ref != ref_eff:
        return UiServiceRefResolution(kind="clarify")
    shown = _ref_in_followups(ref_eff, followups)
    if shown is None:
        return UiServiceRefResolution(kind="clarify")
    if expected_client_id is not None:
        stored_client_id = str(shown.client_id or "").strip()
        if not stored_client_id or stored_client_id != str(expected_client_id).strip():
            return UiServiceRefResolution(kind="clarify")
    if active_service_ids is not None and action.service_id not in active_service_ids:
        return UiServiceRefResolution(kind="clarify")
    planner_message = shown.label.strip() or None
    return UiServiceRefResolution(
        kind="ok",
        action=action,
        planner_message=planner_message,
    )
