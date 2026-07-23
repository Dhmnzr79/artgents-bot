"""Target follow-up ref navigation for dev FullContext path (S61 correction)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TargetRuntimeFollowupItem:
    ref: str
    label: str


@dataclass(frozen=True, slots=True)
class TargetFollowupNavigationResult:
    user_message: str
    matched_ref: str | None


_UNKNOWN_REF_MESSAGE = (
    "Чтобы ответить точнее, уточните, пожалуйста, о какой услуге или ситуации идёт речь."
)


def resolve_target_followup_navigation(
    *,
    ref: str,
    q: str,
    followups: tuple[TargetRuntimeFollowupItem, ...],
) -> TargetFollowupNavigationResult | None:
    """Map a widget ref click to a target user message without legacy chunk routing."""

    ref_eff = ref.strip()
    q_eff = q.strip()
    if q_eff:
        return TargetFollowupNavigationResult(user_message=q_eff, matched_ref=ref_eff or None)
    if not ref_eff:
        return None
    for item in followups:
        if item.ref == ref_eff:
            label = item.label.strip()
            if not label:
                return TargetFollowupNavigationResult(
                    user_message=_UNKNOWN_REF_MESSAGE,
                    matched_ref=ref_eff,
                )
            return TargetFollowupNavigationResult(user_message=label, matched_ref=ref_eff)
    return TargetFollowupNavigationResult(
        user_message=_UNKNOWN_REF_MESSAGE,
        matched_ref=None,
    )
