"""Bounded LLM hook for gray-zone dialog follow-ups."""

from __future__ import annotations

from contracts.dialog_focus import DialogFocusGrayOutput
from llm import classify_dialog_focus_gray_zone as _llm_classify_dialog_focus_gray_zone


def classify_dialog_focus_gray_zone(
    q: str,
    *,
    focus_service_id: str,
    focus_label: str,
    focus_topic: str | None = None,
    client_id: str | None = None,
    sid: str | None = None,
) -> DialogFocusGrayOutput | None:
    raw = _llm_classify_dialog_focus_gray_zone(
        q,
        focus_service_id=focus_service_id,
        focus_label=focus_label,
        focus_topic=focus_topic,
        client_id=client_id,
        sid=sid,
    )
    if not raw:
        return None
    try:
        out = DialogFocusGrayOutput.model_validate(raw)
    except Exception:
        return None
    if out.kind != "follow_up":
        return None
    rewrite = (out.query_rewrite or "").strip()
    if not rewrite:
        return None
    return out
