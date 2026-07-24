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


def build_target_unknown_ref_clarify_payload(
    *,
    client_id: str,
    sid: str,
) -> dict:
    """Widget payload for unknown follow-up ref in target-only mode (no legacy chunks)."""

    return {
        "answer": _UNKNOWN_REF_MESSAGE,
        "quick_replies": [],
        "cta": None,
        "video": None,
        "situation": {"show": False, "mode": "normal"},
        "offer": None,
        "meta": {
            "client_id": client_id,
            "sid": sid,
            "intent": "content",
            "answer_path": "target_fullcontext",
            "service_route": "target_fullcontext_followup_unknown",
            "ui_source_family": "guided_fallback",
            "attribution_kind": "plain",
            "terminal_mode": "clarify",
        },
    }
