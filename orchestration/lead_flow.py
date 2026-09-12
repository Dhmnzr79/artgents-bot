from __future__ import annotations

from contracts.ask_orchestration import AskOrchestrationResult
from orchestration.helpers import decision_dump


def build_service_payload(
    answer: str,
    sid: str,
    client_id: str | None,
    *,
    lead_flow: bool = False,
    lead_step: str | None = None,
    situation_mode: str = "normal",
    situation_collect: bool = False,
    booking_intent_flag: bool = False,
    situation_back: bool = False,
    lead_error: str | None = None,
    quick_replies: list | None = None,
    cta: dict | None = None,
) -> dict:
    meta = {"sid": sid, "client_id": client_id}
    if lead_flow:
        meta["lead_flow"] = True
    if lead_step:
        meta["lead_step"] = lead_step
    if situation_collect:
        meta["situation_collect"] = True
    if booking_intent_flag:
        meta["booking_intent"] = True
    if situation_back:
        meta["situation_back"] = True
    if lead_error:
        meta["lead_error"] = lead_error
    return {
        "answer": answer,
        "quick_replies": list(quick_replies or []),
        "cta": cta,
        "video": None,
        "situation": {"show": situation_mode == "pending", "mode": situation_mode},
        "offer": None,
        "meta": meta,
    }


def lead_flow_orchestration_result(
    *,
    q: str,
    sid: str,
    client_id: str | None,
    flow_result: dict,
    decision,
) -> AskOrchestrationResult:
    decision_frame = decision_dump(decision)
    return AskOrchestrationResult(
        kind="service_reply",
        q=q,
        sid=sid,
        client_id=client_id,
        service_payload=flow_result["payload"],
        service_doc_id=flow_result.get("doc_id"),
        service_track_user=True,
        service_route=str(flow_result.get("service_route") or "lead_flow"),
        decision_frame=decision_frame,
    )
