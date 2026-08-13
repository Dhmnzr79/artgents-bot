"""Stage 5.1B governed ui_service ref click validation."""

from __future__ import annotations

from contracts.ui_service_action import build_ui_service_ref
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.target_ui_service_action import resolve_ui_service_ref_click


def _followup(service_id: str, *, client_id: str | None = "demo") -> tuple[TargetRuntimeFollowupItem, ...]:
    ref = build_ui_service_ref(service_id=service_id)
    return (TargetRuntimeFollowupItem(ref=ref, label="Элайнеры", client_id=client_id),)


def test_valid_shown_active_ref_resolves() -> None:
    ref = build_ui_service_ref(service_id="aligners")
    result = resolve_ui_service_ref_click(
        ref=ref,
        followups=_followup("aligners"),
        active_service_ids=frozenset({"aligners"}),
        expected_client_id="demo",
    )
    assert result.kind == "ok"
    assert result.action is not None
    assert result.action.service_id == "aligners"
    assert result.planner_message == "Элайнеры"


def test_unshown_ref_fails_closed_to_clarify() -> None:
    ref = build_ui_service_ref(service_id="aligners")
    result = resolve_ui_service_ref_click(
        ref=ref,
        followups=(),
        active_service_ids=frozenset({"aligners"}),
    )
    assert result.kind == "clarify"
    assert result.action is None


def test_inactive_service_ref_fails_closed() -> None:
    ref = build_ui_service_ref(service_id="braces")
    result = resolve_ui_service_ref_click(
        ref=ref,
        followups=(TargetRuntimeFollowupItem(ref=ref, label="Брекеты"),),
        active_service_ids=frozenset({"aligners"}),
    )
    assert result.kind == "clarify"


def test_malformed_ref_fails_closed() -> None:
    result = resolve_ui_service_ref_click(
        ref="target:ui_service/",
        followups=(),
        active_service_ids=frozenset({"aligners"}),
    )
    assert result.kind == "clarify"
