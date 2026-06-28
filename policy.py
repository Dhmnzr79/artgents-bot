"""Детерминированные правила до/после LLM; намерение записи — regex + при необходимости LLM."""
from __future__ import annotations

import os
import re

from config import (
    BOOKING_INTENT_LLM_ON,
    BOOKING_INTENT_RE,
    CONTACTS_RE,
    IMPLANT_PAIN_FAQ_FEAR_RE,
    IMPLANT_PAIN_FAQ_IMPLANT_RE,
    PRICE_CONCERN_RE,
    PRICES_RE,
)
from core.video_catalog_loader import resolve_video_payload
from llm import classify_booking_wants_appointment
from retriever import chunk_doc_type
from session import is_lead_context
from dialog_offer import sanitize_ungrounded_continuation_invites


def contacts_intent(q: str) -> bool:
    return bool(CONTACTS_RE.search(q or ""))


def price_intent(q: str) -> bool:
    return bool(PRICES_RE.search(q or ""))


def implant_pain_faq_intent(q: str) -> bool:
    """Страх/боль/анестезия при имплантации (lead_interrupt; routing — facet_arbitration)."""
    q0 = (q or "").strip()
    if len(q0) < 4:
        return False
    if price_intent(q0) or PRICE_CONCERN_RE.search(q0):
        return False
    return bool(
        IMPLANT_PAIN_FAQ_IMPLANT_RE.search(q0) and IMPLANT_PAIN_FAQ_FEAR_RE.search(q0)
    )


_CONTINUATION_ONLY_RE = re.compile(
    r"^(?:подробнее|подробней|еще|ещё|а\s+еще|а\s+ещё|дальше)\s*[.!?…]*$",
    re.I | re.U,
)


def continuation_only_phrase(q: str) -> bool:
    """Короткая реплика «продолжи тему» без самостоятельного вопроса."""
    return bool(_CONTINUATION_ONLY_RE.match((q or "").strip()))


def session_has_continuation_context(st: dict | None) -> bool:
    """Есть тема/кнопки/предыдущий ответ бота — можно продолжать диалог."""
    s = st or {}
    if (s.get("current_doc_id") or "").strip():
        return True
    if (s.get("last_catalog_service_id") or "").strip():
        return True
    if (s.get("last_bot_action") or "none") != "none":
        return True
    if s.get("last_presented_buttons"):
        return True
    if s.get("last_content_ui_payload"):
        return True
    hist = s.get("hist") or []
    return bool(hist)


def continuation_without_context(q: str, st: dict | None) -> bool:
    return continuation_only_phrase(q) and not session_has_continuation_context(st)


def _booking_intent_cache_key(q0: str, sid: str | None, client_id: str | None) -> str:
    return f"{(client_id or '').strip()}|{(sid or '').strip()}|{q0[:600]}"


def _booking_intent_cache() -> dict[str, bool] | None:
    try:
        from flask import has_request_context, request

        if not has_request_context():
            return None
        ctx = getattr(request, "ctx", None)
        if not isinstance(ctx, dict):
            return None
        raw = ctx.setdefault("booking_intent_cache", {})
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def explicit_booking_intent(q: str) -> bool:
    """Pre-Resolver lead gate: explicit booking phrases only (no LLM)."""
    q0 = (q or "").strip()
    return len(q0) >= 2 and bool(BOOKING_INTENT_RE.search(q0))


def booking_intent(
    q: str, *, sid: str | None = None, client_id: str | None = None
) -> bool:
    q0 = (q or "").strip()
    if len(q0) < 2:
        return False

    cache_key = _booking_intent_cache_key(q0, sid, client_id)
    cache = _booking_intent_cache()
    if cache is not None:
        hit = cache.get(cache_key)
        if hit is not None:
            from core.turn_timing import set_flag

            set_flag("booking_intent_cache_hit", True)
            return bool(hit)

    if BOOKING_INTENT_RE.search(q0):
        out = True
    elif not BOOKING_INTENT_LLM_ON:
        out = False
    else:
        out = classify_booking_wants_appointment(
            q0[:600], client_id=client_id, sid=sid or ""
        )

    if cache is not None:
        cache[cache_key] = out
    return out


def pick_contacts_chunk(cands: list) -> dict | None:
    for ch in cands:
        dt = (chunk_doc_type(ch) or "").strip().lower()
        if dt == "contacts":
            return ch
        # Fallback: filename contains "contacts" (если doc_type не прописан во front-matter)
        file_base = os.path.basename((ch.get("file") or "") if isinstance(ch, dict) else "").lower()
        if "contacts" in file_base:
            return ch
    return None


def pick_prices_chunk(cands: list) -> dict | None:
    for ch in cands:
        dt = (chunk_doc_type(ch) or "").strip().lower()
        file_name = (ch.get("file") or "").strip().lower() if isinstance(ch, dict) else ""
        if dt in {"prices", "pricing"} or "__pricing__" in file_name:
            return ch
    return None


def _is_topic_exhausted(doc_meta: dict, topic_state: dict) -> bool:
    suggest_h3 = list(doc_meta.get("suggest_h3") or [])
    covered = set(topic_state.get("covered_h3_ids") or [])
    if not suggest_h3:
        return int(topic_state.get("doc_turn_count") or 0) >= 1
    return covered.issuperset(set(suggest_h3))


UI_FAMILY_MD = "md_navigation"
UI_FAMILY_PRICE = "price_navigation"
UI_FAMILY_PATIENT_OPTIONS = "patient_options"
UI_FAMILY_DOCTOR = "doctor_navigation"
UI_FAMILY_GUIDED_FALLBACK = "guided_fallback"

_UI_FAMILIES = {
    UI_FAMILY_MD,
    UI_FAMILY_PRICE,
    UI_FAMILY_PATIENT_OPTIONS,
    UI_FAMILY_DOCTOR,
    UI_FAMILY_GUIDED_FALLBACK,
}
_PRICE_UI_ROUTES = {"price_lookup", "price_concern", "price_aspect", "price_clarify"}
_PRICE_UI_INTENTS = {"price_lookup", "price_concern"}


def _payload_route(payload: dict, route: str | None = None) -> str:
    if route:
        return str(route).strip().lower()
    meta = payload.get("meta") if isinstance(payload, dict) else {}
    if not isinstance(meta, dict):
        return ""
    return str(meta.get("service_route") or meta.get("orch_route") or "").strip().lower()


def infer_ui_source_family(payload: dict, route: str | None = None) -> str:
    """Classify which subsystem owns navigation controls for this answer."""
    meta = payload.get("meta") if isinstance(payload, dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    explicit = str(meta.get("ui_source_family") or "").strip().lower()
    if explicit in _UI_FAMILIES:
        return explicit

    route_eff = _payload_route(payload, route)
    intent = str(meta.get("intent") or "").strip().lower()
    if route_eff == "patient_options_overview" or meta.get("patient_options_overview_used"):
        return UI_FAMILY_PATIENT_OPTIONS
    if route_eff in _PRICE_UI_ROUTES or intent in _PRICE_UI_INTENTS:
        return UI_FAMILY_PRICE
    doc_type = str(meta.get("doc_type") or "").strip().lower()
    doc_id = str(meta.get("doc_id") or "").strip().lower()
    if route_eff == "doctors_list" or doc_type == "doctor" or doc_id.startswith("doctors__doctor"):
        return UI_FAMILY_DOCTOR
    if meta.get("low_score") or meta.get("offtopic") or meta.get("error"):
        return UI_FAMILY_GUIDED_FALLBACK
    return UI_FAMILY_MD


def _is_price_ref(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    return str(item.get("ref") or "").strip().lower().startswith("price:")


def _is_patient_option_ref(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    return str(item.get("source") or "").strip().lower() == "patient_option"


def _merge_policy_decision_meta(meta: dict, details: dict) -> None:
    current = meta.get("policy_decision")
    if not isinstance(current, dict):
        current = {}
    current.update(details)
    meta["policy_decision"] = current


def apply_ui_source_policy(payload: dict, route: str | None = None) -> dict:
    """Keep quick replies/follow-ups owned by one UI source only."""
    if not isinstance(payload, dict):
        return payload
    meta = payload.setdefault("meta", {})
    if not isinstance(meta, dict):
        meta = {}
        payload["meta"] = meta

    family_in = str(meta.get("ui_source_family") or "").strip().lower() or None
    family = infer_ui_source_family(payload, route=route)
    route_eff = _payload_route(payload, route)
    quick_before = list(payload.get("quick_replies") or [])
    followups_before = list(meta.get("followups") or [])
    dropped: list[str] = []

    if family == UI_FAMILY_PRICE:
        if followups_before:
            dropped.append("followups_non_price_ui")
        meta["followups"] = []
    elif family == UI_FAMILY_PATIENT_OPTIONS:
        filtered = [item for item in quick_before if _is_patient_option_ref(item)]
        if len(filtered) != len(quick_before):
            dropped.append("quick_replies_non_patient_options")
        if followups_before:
            dropped.append("followups_non_patient_options")
        payload["quick_replies"] = filtered
        meta["followups"] = []
    elif family == UI_FAMILY_DOCTOR:
        if quick_before:
            dropped.append("quick_replies_non_doctor_ui")
        if followups_before:
            dropped.append("followups_non_doctor_ui")
        payload["quick_replies"] = []
        meta["followups"] = []
    elif family == UI_FAMILY_GUIDED_FALLBACK:
        if followups_before:
            dropped.append("followups_guided_fallback")
        meta["followups"] = []

    meta["ui_source_family"] = family
    _merge_policy_decision_meta(
        meta,
        {
            "ui_source_family_in": family_in,
            "ui_source_family_effective": family,
            "ui_source_route": route_eff,
            "quick_replies_before_ui_source_policy": len(quick_before),
            "followups_before_ui_source_policy": len(followups_before),
            "ui_source_dropped": dropped,
        },
    )
    return payload


def _apply_cta_gate_only(
    payload: dict,
    session_state: dict,
    q: str,
    *,
    session_id: str | None = None,
    client_id: str | None = None,
) -> dict:
    meta = payload.setdefault("meta", {})
    if not isinstance(meta, dict):
        meta = {}
        payload["meta"] = meta

    lead_flow_active = is_lead_context(session_state)
    booking = booking_intent(q, sid=session_id, client_id=client_id)
    show_cta = bool(payload.get("cta")) and not lead_flow_active and not bool(
        (session_state or {}).get("situation_pending")
    )
    if show_cta and booking:
        show_cta = False

    dropped: list[str] = []
    if payload.get("cta") and not show_cta:
        dropped.append("cta")
    payload["cta"] = payload.get("cta") if show_cta else None
    _merge_policy_decision_meta(
        meta,
        {
            "show_cta": bool(show_cta),
            "lead_flow_active": bool(lead_flow_active),
            "booking": bool(booking),
            "dropped": dropped,
        },
    )
    return payload


def build_policy_decision(
    *,
    payload: dict,
    session_state: dict,
    topic_state: dict,
    doc_meta: dict,
    q: str,
    pre_doc_turn_count: int | None = None,
    session_id: str | None = None,
    client_id: str | None = None,
) -> dict:
    meta = payload.get("meta") or {}
    low_score = bool(meta.get("low_score"))
    lead_flow_active = is_lead_context(session_state)
    booking = booking_intent(q, sid=session_id, client_id=client_id)
    exhausted = _is_topic_exhausted(doc_meta, topic_state)
    doc_turn_after = int(topic_state.get("doc_turn_count") or 0)
    doc_turn_before = (
        int(pre_doc_turn_count)
        if pre_doc_turn_count is not None
        else max(doc_turn_after - 1, 0)
    )

    covered_h3 = {str(x).strip().lower() for x in (topic_state.get("covered_h3_ids") or []) if x}
    followups_all = []
    for f in list(meta.get("followups") or []):
        if not isinstance(f, dict):
            continue
        ref = str(f.get("ref") or "")
        anchor = ref.split("#", 1)[1].strip().lower() if "#" in ref else ""
        if anchor and anchor in covered_h3:
            continue
        followups_all.append(f)

    refs_all = list(payload.get("quick_replies") or [])
    deferred = list(topic_state.get("refs_deferred") or [])
    if deferred:
        refs_all = deferred + refs_all

    has_video = bool(doc_meta.get("video_key"))
    video_shown = bool(topic_state.get("video_shown"))
    situation_allowed = bool(doc_meta.get("situation_allowed"))
    situation_offered = bool(topic_state.get("situation_offered"))
    ref_used = bool(topic_state.get("suggest_ref_used"))
    cta_from_turn = max(0, int(doc_meta.get("cta_from_turn", 0) or 0))

    is_first_content_turn = doc_turn_before == 0
    max_follow_slots = 1 if has_video else 2

    followups_out: list = []
    show_video = False
    show_situation = False
    show_ref = False

    slots = max_follow_slots
    fu_queue = list(followups_all)

    if (
        not low_score
        and has_video
        and not video_shown
        and is_first_content_turn
        and fu_queue
    ):
        show_video = True
        followups_out.append(fu_queue.pop(0))
        slots = 0
    elif (
        not low_score
        and has_video
        and not video_shown
        and is_first_content_turn
        and not fu_queue
    ):
        show_video = True
        slots = max_follow_slots - 1
        if (
            slots > 0
            and situation_allowed
            and not situation_offered
            and not lead_flow_active
            and not bool(session_state.get("situation_pending"))
        ):
            show_situation = True
            slots -= 1
        if slots > 0 and refs_all and not ref_used and exhausted:
            show_ref = True
            slots -= 1
        slots = 0
    else:
        while slots > 0 and fu_queue:
            followups_out.append(fu_queue.pop(0))
            slots -= 1
        if slots > 0 and not low_score and has_video and not video_shown:
            show_video = True
            slots -= 1

        situation_blocked = (
            is_first_content_turn
            and has_video
            and not video_shown
            and bool(followups_all)
        )
        if (
            slots > 0
            and not low_score
            and situation_allowed
            and not situation_offered
            and not lead_flow_active
            and not bool(session_state.get("situation_pending"))
            and not situation_blocked
        ):
            show_situation = True
            slots -= 1

        if (
            slots > 0
            and not low_score
            and refs_all
            and not ref_used
            and exhausted
        ):
            show_ref = True
            slots -= 1

    refs_out = refs_all[:1] if show_ref else []

    cta = payload.get("cta")
    show_cta = bool(cta) and not lead_flow_active and not bool(
        session_state.get("situation_pending")
    )
    if show_cta and doc_turn_before < cta_from_turn:
        show_cta = False
    if show_cta and booking:
        show_cta = False

    defer_refs = bool(refs_all) and not show_ref and (show_video or show_situation)
    dropped = []
    if not show_ref and refs_all:
        dropped.append("suggest_refs")
    if payload.get("cta") and not show_cta:
        dropped.append("cta")

    return {
        "low_score": low_score,
        "topic_exhausted": exhausted,
        "lead_flow_active": lead_flow_active,
        "booking": booking,
        "show_cta": show_cta,
        "show_video": show_video,
        "show_situation": show_situation,
        "show_refs": show_ref,
        "followups": followups_out,
        "refs": refs_out,
        "defer_refs": defer_refs,
        "dropped": dropped,
        "doc_turn_before": doc_turn_before,
        "doc_turn_after": doc_turn_after,
        "cta_from_turn": cta_from_turn,
    }


def apply_response_policy(
    payload: dict,
    session_state: dict,
    q: str,
    *,
    topic_state: dict | None = None,
    doc_meta: dict | None = None,
    pre_doc_turn_count: int | None = None,
    session_id: str | None = None,
    client_id: str | None = None,
) -> dict:
    topic_state = topic_state or {}
    doc_meta = doc_meta or {}
    family = infer_ui_source_family(payload)
    if family in {UI_FAMILY_PRICE, UI_FAMILY_PATIENT_OPTIONS, UI_FAMILY_DOCTOR, UI_FAMILY_GUIDED_FALLBACK}:
        _apply_cta_gate_only(
            payload,
            session_state,
            q,
            session_id=session_id,
            client_id=client_id,
        )
        return apply_ui_source_policy(payload)

    decision = build_policy_decision(
        payload=payload,
        session_state=session_state,
        topic_state=topic_state,
        doc_meta=doc_meta,
        q=q,
        pre_doc_turn_count=pre_doc_turn_count,
        session_id=session_id,
        client_id=client_id,
    )

    payload["quick_replies"] = decision["refs"] if decision["show_refs"] else []
    payload["cta"] = payload.get("cta") if decision["show_cta"] else None

    cid = ((client_id or "").strip() or "default").strip()
    video_payload = None
    if decision["show_video"] and doc_meta.get("video_key"):
        video_payload = resolve_video_payload(
            client_id=cid,
            video_key=str(doc_meta.get("video_key") or "").strip(),
        )
    payload["video"] = video_payload

    sit_show = bool(decision["show_situation"])
    payload["situation"] = {"show": sit_show, "mode": "normal"}

    meta = payload.setdefault("meta", {})
    meta["followups"] = decision["followups"]
    meta["topic_exhausted"] = bool(decision["topic_exhausted"])
    followups_out = list(meta.get("followups") or [])
    answer_raw = str(payload.get("answer") or "")
    payload["answer"] = sanitize_ungrounded_continuation_invites(
        answer_raw,
        has_structural_followups=bool(followups_out),
    )
    meta["policy_decision"] = {
        "show_video": bool(decision["show_video"]) and payload["video"] is not None,
        "show_situation": bool(decision["show_situation"]),
        "show_refs": bool(decision["show_refs"]),
        "show_cta": bool(decision["show_cta"]),
        "defer_refs": bool(decision["defer_refs"]),
        "refs_to_defer": (decision["refs"] if decision["defer_refs"] else []),
        "lead_flow_active": bool(decision["lead_flow_active"]),
        "booking": bool(decision["booking"]),
        "refs_candidate_count": len(decision["refs"]),
        "dropped": decision["dropped"],
        "doc_turn_before": decision["doc_turn_before"],
        "doc_turn_after": decision["doc_turn_after"],
        "cta_from_turn": decision["cta_from_turn"],
    }
    apply_ui_source_policy(payload)
    return payload
