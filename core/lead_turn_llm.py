"""Gray-zone LLM hook for lead active-turn classification."""
from __future__ import annotations

from contracts.lead_turn import LeadContentHint, LeadTurnDecision, LeadTurnGrayOutput
from llm import classify_lead_turn_gray_zone as _llm_classify_lead_turn_gray_zone


def classify_lead_turn_gray_zone(
    q: str,
    *,
    lead_step: str,
    client_id: str | None = None,
    sid: str | None = None,
) -> LeadTurnDecision | None:
    raw = _llm_classify_lead_turn_gray_zone(
        q,
        lead_step=lead_step,
        client_id=client_id,
        sid=sid,
    )
    if not raw:
        return None
    try:
        out = LeadTurnGrayOutput.model_validate(raw)
    except Exception:
        return None
    hint: LeadContentHint | None = out.content_hint
    if out.kind == "content" and hint is None:
        hint = "generic"
    if out.kind != "content":
        hint = None
    return LeadTurnDecision(kind=out.kind, content_hint=hint, confidence=out.confidence)
