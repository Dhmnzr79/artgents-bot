"""Unified lead-paused overlay after any answer route (chunk, price, contacts)."""
from __future__ import annotations

from lead_interrupt import LEAD_CANCEL_REF, LEAD_RESUME_REF
from session import (
    get_lead_paused_answer_count,
    get_lead_resume_step,
    increment_lead_paused_answer_count,
    is_lead_paused,
    mem_get,
)


def _lead_pause_quick_replies() -> list[dict]:
    return [
        {"label": "Продолжить запись", "ref": LEAD_RESUME_REF},
        {"label": "Отменить запись", "ref": LEAD_CANCEL_REF},
    ]


def finish_lead_paused_payload(
    payload: dict,
    sid: str,
    client_id: str | None,
    txt: dict,
) -> dict:
    """After a content answer during lead pause: PII meta, bridge, resume QR."""
    st = mem_get(sid)
    if not is_lead_paused(st):
        return payload
    pmeta = payload.setdefault("meta", {})
    pmeta["lead_flow"] = True
    pmeta["lead_paused"] = True
    pmeta["lead_step"] = "paused"
    kind = (st.get("lead_interrupt_kind") or "").strip()
    if kind:
        pmeta["lead_interrupt_kind"] = kind
    resume_step = get_lead_resume_step(sid) or "collecting_name"
    bridge_key = (
        "lead_paused_bridge_phone"
        if resume_step == "collecting_phone"
        else "lead_paused_bridge_name"
    )
    bridge = (txt.get(bridge_key) or "").strip()
    answer = str(payload.get("answer") or "").strip()
    if get_lead_paused_answer_count(sid) == 0 and bridge and bridge not in answer:
        payload["answer"] = f"{answer}\n\n{bridge}".strip() if answer else bridge
    increment_lead_paused_answer_count(sid)
    payload["quick_replies"] = _lead_pause_quick_replies()
    payload["cta"] = None
    payload["video"] = None
    payload["situation"] = {"show": False, "mode": "normal"}
    pmeta["followups"] = []
    return payload


def apply_lead_paused_overlay(
    payload: dict,
    sid: str,
    client_id: str | None,
    *,
    txt: dict | None = None,
) -> dict:
    if txt is None:
        from core.client_config_loader import tone_to_txt_dict

        txt = tone_to_txt_dict(client_id)
    return finish_lead_paused_payload(payload, sid, client_id, txt)
