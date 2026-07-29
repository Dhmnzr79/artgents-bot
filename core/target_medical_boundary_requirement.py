"""Pure resolver: does this turn need Medical Boundary classification, or is it a validated
governed UI scope/stage price-navigation click that can safely skip it? (PERF-2)

See TASK.md § FINAL_SAFE_MEDICAL_BOUNDARY_BYPASS and
docs/evidence/performance/FINAL_SAFE_MEDICAL_BOUNDARY_BYPASS_SEAM_AUDIT.md §4A for the exact,
binding eligibility checklist this implements. No I/O, no LLM call, no raw user text, no
request/session access of its own (the two action parameters' mere presence is the caller's
proof that the existing session-bound ref-whitelist check in the pre-resolver already ran and
passed), no regex/phrase-list matching, no confidence-based routing, no demo/service/client ID
hardcoding, no topic/service literal special-casing. Fail-safe default is always "required" --
any mismatch, missing attribute, unexpected type, or exception falls through to it. There is no
partial-credit bypass tier.
"""

from __future__ import annotations

from contracts.target_medical_boundary_requirement import TargetMedicalBoundaryRequirement
from contracts.turn_frame import TurnFrame
from contracts.ui_scope_action import UiScopeAction
from contracts.ui_stage_action import UiStageAction

_GOVERNED_UI_PROVENANCE_PREFIX = "governed_ui_action:"
_REQUIRED_VALID_PROVENANCE_FIELDS = ("intent", "aspects", "primary_aspect", "needs_clarification")


def resolve_target_medical_boundary_requirement(
    *,
    turn_frame: TurnFrame,
    current_ui_scope_action: UiScopeAction | None,
    current_ui_stage_action: UiStageAction | None,
) -> TargetMedicalBoundaryRequirement:
    try:
        eligible = _is_bypass_governed_ui_eligible(
            turn_frame=turn_frame,
            current_ui_scope_action=current_ui_scope_action,
            current_ui_stage_action=current_ui_stage_action,
        )
    except Exception:
        return "required"
    return "bypass_governed_ui" if eligible else "required"


def _is_bypass_governed_ui_eligible(
    *,
    turn_frame: TurnFrame,
    current_ui_scope_action: UiScopeAction | None,
    current_ui_stage_action: UiStageAction | None,
) -> bool:
    # 1. Exactly one governed action -- XOR. Both present or neither present -> not eligible.
    has_scope = current_ui_scope_action is not None
    has_stage = current_ui_stage_action is not None
    if has_scope == has_stage:
        return False
    action: UiScopeAction | UiStageAction
    action = current_ui_scope_action if has_scope else current_ui_stage_action  # type: ignore[assignment]

    # 2. Action must be the expected typed model (defensive; callers already validate this,
    #    see core/target_runtime_turn.py's _current_ui_scope_action_from_request/_stage_action).
    if not isinstance(action, (UiScopeAction, UiStageAction)):
        return False

    # 3. Exact TurnFrame field values -- no forgiving fallback.
    if turn_frame.intent != "price_lookup":
        return False
    if tuple(turn_frame.aspects) != ("price",):
        return False
    if turn_frame.primary_aspect != "price":
        return False
    if turn_frame.needs_clarification is not False:
        return False
    if turn_frame.topic != action.topic:
        return False

    # 4. Exact field_meta.status + provenance for intent/aspects/primary_aspect/needs_clarification.
    expected_provenance = f"{_GOVERNED_UI_PROVENANCE_PREFIX}{action.ref}"
    meta = turn_frame.field_meta
    for field_name in _REQUIRED_VALID_PROVENANCE_FIELDS:
        field_meta = getattr(meta, field_name)
        if field_meta.status != "valid":
            return False
        if field_meta.provenance != expected_provenance:
            return False

    return True
