"""Flow orchestration for non-retrieval branches in /ask."""

import os

from core.lead_context import bind_lead_context_turn
from core.lead_turn_classifier import classify_lead_active_turn, interrupt_kind_for_content_hint
from lead_interrupt import LEAD_CANCEL_REF, LEAD_PAUSE_REF, LEAD_RESUME_REF, parse_lead_cancel
from lead_service import handle_lead, resolve_lead_submit_message
from name_gate import accept_lead_name
from policy import explicit_booking_intent
from session import (
    clear_lead_pii,
    exit_lead_flow,
    extract_phone,
    get_lead_paused_answer_count,
    get_lead_pending_name,
    get_lead_resume_step,
    increment_lead_paused_answer_count,
    is_active_lead_flow,
    is_lead_paused,
    mark_booking_intent_ever,
    mem_get,
    parse_no,
    parse_yes,
    clear_pending_lead_offer,
    pause_lead_flow,
    resume_lead_from_pause,
    set_lead_intent,
    set_lead_pending_name,
    set_situation_note,
    set_situation_pending,
    update_profile,
)
from core.client_config_loader import (
    lead_cta_dict_for_menu,
    resolve_lead_name_prompt,
    situation_enabled,
)
from dialog_offer import parse_lead_offer_no, parse_lead_offer_yes

_LEAD_NAME_CONFIRM_YES = "lead:name_confirm:yes"
_LEAD_NAME_CONFIRM_NO = "lead:name_confirm:no"
LEAD_BOOKING_REF = "lead:booking"
LEAD_BOOKING_CTA_KEY = "booking"


def _lead_entry_name_prompt(
    client_id: str | None,
    txt: dict,
    data: dict | None = None,
    *,
    cta_key: str | None = None,
) -> str:
    payload = data or {}
    return resolve_lead_name_prompt(
        client_id,
        cta_key=cta_key or (str(payload.get("cta_key") or "").strip() or None),
        cta_label=str(payload.get("cta_label") or "").strip() or None,
        txt=txt,
    )


def _name_confirm_quick_replies() -> list[dict]:
    return [
        {"label": "Да", "ref": _LEAD_NAME_CONFIRM_YES},
        {"label": "Нет, введу по-другому", "ref": _LEAD_NAME_CONFIRM_NO},
    ]


def _merge_lead_slot_qrs(quick_replies: list | None, txt: dict) -> list[dict]:
    base = list(quick_replies or [])
    if any((qr.get("ref") or "").strip() == LEAD_PAUSE_REF for qr in base):
        return base
    label = (txt.get("lead_ask_question_label") or "Задать вопрос").strip()
    base.append({"label": label, "ref": LEAD_PAUSE_REF})
    return base


def _lead_pause_quick_replies() -> list[dict]:
    return [
        {"label": "Продолжить запись", "ref": LEAD_RESUME_REF},
        {"label": "Отменить запись", "ref": LEAD_CANCEL_REF},
    ]


def _exit_lead_flow_result(
    *,
    sid: str,
    client_id: str | None,
    txt: dict,
    service_payload,
) -> dict:
    exit_lead_flow(sid)
    return {
        "payload": service_payload(
            txt.get(
                "lead_offer_declined",
                "Хорошо. Если появятся вопросы — спрашивайте.",
            ),
            sid,
            client_id,
        ),
        "doc_id": None,
        "service_route": "lead_cancelled",
    }


def _resume_step_payload(
    step: str,
    *,
    sid: str,
    client_id: str | None,
    txt: dict,
    service_payload,
) -> dict:
    if step == "collecting_phone":
        prof = mem_get(sid).get("profile") or {}
        name = (prof.get("name") or "").strip()
        prompt = (
            txt["lead_phone_prompt_tpl"].format(name=name)
            if name
            else txt.get("lead_name_prompt", "Как к вам можно обращаться?")
        )
        return service_payload(
            prompt,
            sid,
            client_id,
            lead_flow=True,
            lead_step="phone" if name else "name",
            quick_replies=[],
        )
    if step == "confirming_name":
        pending = get_lead_pending_name(sid)
        if not pending:
            pending = str((mem_get(sid).get("profile") or {}).get("name") or "").strip()
        return service_payload(
            txt["lead_name_confirm_tpl"].format(name=pending),
            sid,
            client_id,
            lead_flow=True,
            lead_step="confirm_name",
            quick_replies=_name_confirm_quick_replies(),
        )
    return service_payload(
        txt.get("lead_name_prompt", "Как к вам можно обращаться?"),
        sid,
        client_id,
        lead_flow=True,
        lead_step="name",
    )


def _lead_pause_prompt_result(
    *,
    sid: str,
    client_id: str | None,
    txt: dict,
    service_payload,
) -> dict:
    return {
        "payload": service_payload(
            txt.get(
                "lead_ask_question_prompt",
                "Хорошо, задайте вопрос — после ответа сможете продолжить запись.",
            ),
            sid,
            client_id,
            lead_flow=True,
            lead_step="paused",
        ),
        "doc_id": None,
    }


def _lead_defer_result(
    *,
    sid: str,
    client_id: str | None,
    txt: dict,
    service_payload,
) -> dict:
    exit_lead_flow(sid)
    return {
        "payload": service_payload(
            txt.get(
                "lead_defer_exit",
                "Хорошо, без спешки. Когда будете готовы — нажмите «Записаться» или напишите.",
            ),
            sid,
            client_id,
        ),
        "doc_id": None,
        "service_route": "lead_deferred",
    }


def _lead_unclear_reply(
    sid: str,
    client_id: str | None,
    *,
    txt: dict,
    service_payload,
    lead_step: str,
) -> dict:
    return service_payload(
        txt.get(
            "lead_unclear_retry",
            "Напишите, пожалуйста, имя — или задайте вопрос, и я отвечу.",
        ),
        sid,
        client_id,
        lead_flow=True,
        lead_step=lead_step,
        quick_replies=_merge_lead_slot_qrs([], txt),
    )


def _pause_for_content(
    *,
    sid: str,
    st: dict,
    decision,
) -> None:
    resume_step = (st.get("lead_intent") or "collecting_name").strip()
    hint = decision.content_hint
    interrupt_kind = interrupt_kind_for_content_hint(hint)
    pause_lead_flow(
        sid,
        resume_step=resume_step,
        return_doc_id=(st.get("current_doc_id") or "").strip() or None,
        interrupt_kind=interrupt_kind,
    )
    bind_lead_context_turn(interrupt_no_topic=True, interrupt_kind=interrupt_kind)


def _try_lead_step_controls(
    *,
    ref: str,
    q: str,
    sid: str,
    st: dict,
    client_id: str | None,
    txt: dict,
    service_payload,
) -> tuple[str, dict | None]:
    """
    Returns (action, flow_result).
    action: proceed | cancelled | paused_pipeline | paused_prompt | defer | unclear
    """
    decision = classify_lead_active_turn(q, ref=ref, st=st, sid=sid, client_id=client_id)
    if decision.kind == "meta_cancel":
        return "cancelled", _exit_lead_flow_result(
            sid=sid, client_id=client_id, txt=txt, service_payload=service_payload
        )
    if decision.kind == "meta_pause":
        resume_step = (st.get("lead_intent") or "collecting_name").strip()
        pause_lead_flow(
            sid,
            resume_step=resume_step,
            return_doc_id=(st.get("current_doc_id") or "").strip() or None,
            interrupt_kind="manual",
        )
        return "paused_prompt", _lead_pause_prompt_result(
            sid=sid, client_id=client_id, txt=txt, service_payload=service_payload
        )
    if decision.kind == "content":
        _pause_for_content(sid=sid, st=st, decision=decision)
        return "paused_pipeline", None
    if decision.kind == "defer":
        return "defer", _lead_defer_result(
            sid=sid, client_id=client_id, txt=txt, service_payload=service_payload
        )
    if decision.kind == "unclear":
        step = (st.get("lead_intent") or "collecting_name").strip()
        lead_step = "phone" if step == "collecting_phone" else "name"
        return "unclear", {
            "payload": _lead_unclear_reply(
                sid,
                client_id,
                txt=txt,
                service_payload=service_payload,
                lead_step=lead_step,
            ),
            "doc_id": None,
        }
    return "proceed", None


def _handle_paused_lead_turn(
    *,
    data: dict,
    sid: str,
    q: str,
    client_id: str | None,
    txt: dict,
    service_payload,
    st: dict,
) -> dict | None:
    ref = (data.get("ref") or "").strip()

    if ref == LEAD_CANCEL_REF or parse_lead_cancel(q):
        return _exit_lead_flow_result(
            sid=sid, client_id=client_id, txt=txt, service_payload=service_payload
        )

    resume_step = get_lead_resume_step(sid) or "collecting_name"

    if ref == LEAD_RESUME_REF:
        step = resume_lead_from_pause(sid)
        return {
            "payload": _resume_step_payload(
                step, sid=sid, client_id=client_id, txt=txt, service_payload=service_payload
            ),
            "doc_id": None,
        }

    if resume_step == "confirming_name":
        pending = get_lead_pending_name(sid)
        yes = ref == _LEAD_NAME_CONFIRM_YES or parse_yes(q)
        no = ref == _LEAD_NAME_CONFIRM_NO or parse_no(q)
        if yes and pending:
            resume_lead_from_pause(sid)
            update_profile(sid, name=pending)
            set_lead_pending_name(sid, None)
            set_lead_intent(sid, "collecting_phone")
            return {
                "payload": service_payload(
                    txt["lead_phone_prompt_tpl"].format(name=pending),
                    sid,
                    client_id,
                    lead_flow=True,
                    lead_step="phone",
                ),
                "doc_id": None,
            }
        if no:
            resume_lead_from_pause(sid)
            set_lead_pending_name(sid, None)
            set_lead_intent(sid, "collecting_name")
            return {
                "payload": service_payload(
                    txt["lead_name_reenter"],
                    sid,
                    client_id,
                    lead_flow=True,
                    lead_step="name",
                    quick_replies=_merge_lead_slot_qrs([], txt),
                ),
                "doc_id": None,
            }
        name = accept_lead_name(q)
        if name:
            resume_lead_from_pause(sid)
            set_lead_pending_name(sid, name)
            set_lead_intent(sid, "confirming_name")
            return {
                "payload": service_payload(
                    txt["lead_name_confirm_tpl"].format(name=name),
                    sid,
                    client_id,
                    lead_flow=True,
                    lead_step="confirm_name",
                    quick_replies=_name_confirm_quick_replies(),
                ),
                "doc_id": None,
            }

    if resume_step == "collecting_name":
        name = accept_lead_name(q)
        if name:
            resume_lead_from_pause(sid)
            update_profile(sid, name=name)
            set_lead_intent(sid, "collecting_phone")
            return {
                "payload": service_payload(
                    txt["lead_phone_prompt_tpl"].format(name=name),
                    sid,
                    client_id,
                    lead_flow=True,
                    lead_step="phone",
                ),
                "doc_id": None,
            }

    if resume_step == "collecting_phone":
        phone = extract_phone(q)
        if phone:
            resume_lead_from_pause(sid)
            payload = _lead_flow_payload(
                sid, q, client_id, txt=txt, service_payload=service_payload
            )
            if payload is not None:
                return {"payload": payload, "doc_id": None}

    bind_lead_context_turn(interrupt_no_topic=True, interrupt_kind="generic")
    return None


def _handle_active_lead_turn(
    *,
    data: dict,
    sid: str,
    q: str,
    client_id: str | None,
    txt: dict,
    service_payload,
    st: dict,
) -> dict | None:
    ref = (data.get("ref") or "").strip()

    action, result = _try_lead_step_controls(
        ref=ref,
        q=q,
        sid=sid,
        st=st,
        client_id=client_id,
        txt=txt,
        service_payload=service_payload,
    )
    if action in {"cancelled", "paused_prompt", "defer", "unclear"}:
        return result
    if action == "paused_pipeline":
        return None

    if st.get("lead_intent") == "confirming_name":
        return _handle_lead_name_confirm(
            data=data,
            sid=sid,
            q=q,
            client_id=client_id,
            txt=txt,
            service_payload=service_payload,
        )

    payload = _lead_flow_payload(
        sid, q, client_id, txt=txt, service_payload=service_payload
    )
    if payload is not None:
        return {"payload": payload, "doc_id": None}
    return None


def _collecting_name_reply(
    sid: str,
    q: str,
    client_id: str | None,
    *,
    txt: dict,
    service_payload,
) -> dict | None:
    name = accept_lead_name(q)
    if not name:
        return _lead_unclear_reply(
            sid,
            client_id,
            txt=txt,
            service_payload=service_payload,
            lead_step="name",
        )
    update_profile(sid, name=name)
    set_lead_intent(sid, "collecting_phone")
    return service_payload(
        txt["lead_phone_prompt_tpl"].format(name=name),
        sid,
        client_id,
        lead_flow=True,
        lead_step="phone",
    )


def _handle_lead_name_confirm(
    *,
    data: dict,
    sid: str,
    q: str,
    client_id: str | None,
    txt: dict,
    service_payload,
) -> dict | None:
    ref = (data.get("ref") or "").strip()
    pending = get_lead_pending_name(sid)
    st = mem_get(sid)

    action, result = _try_lead_step_controls(
        ref=ref,
        q=q,
        sid=sid,
        st=st,
        client_id=client_id,
        txt=txt,
        service_payload=service_payload,
    )
    if action in {"cancelled", "paused_prompt", "defer", "unclear"}:
        return result
    if action == "paused_pipeline":
        return None

    yes = ref == _LEAD_NAME_CONFIRM_YES or parse_yes(q)
    no = ref == _LEAD_NAME_CONFIRM_NO or parse_no(q)

    if yes and pending:
        update_profile(sid, name=pending)
        set_lead_pending_name(sid, None)
        set_lead_intent(sid, "collecting_phone")
        return {
            "payload": service_payload(
                txt["lead_phone_prompt_tpl"].format(name=pending),
                sid,
                client_id,
                lead_flow=True,
                lead_step="phone",
            ),
            "doc_id": None,
        }

    if no:
        set_lead_pending_name(sid, None)
        set_lead_intent(sid, "collecting_name")
        return {
            "payload": service_payload(
                txt["lead_name_reenter"],
                sid,
                client_id,
                lead_flow=True,
                lead_step="name",
                quick_replies=_merge_lead_slot_qrs([], txt),
            ),
            "doc_id": None,
        }

    if q.strip() and len(q.strip()) > 1 and not yes:
        set_lead_pending_name(sid, None)
        set_lead_intent(sid, "collecting_name")
        payload = _collecting_name_reply(
            sid, q, client_id, txt=txt, service_payload=service_payload
        )
        if payload is not None:
            return {"payload": payload, "doc_id": None}

    if pending:
        return {
            "payload": service_payload(
                txt["lead_name_confirm_tpl"].format(name=pending),
                sid,
                client_id,
                lead_flow=True,
                lead_step="confirm_name",
                quick_replies=_merge_lead_slot_qrs(_name_confirm_quick_replies(), txt),
            ),
            "doc_id": None,
        }

    set_lead_intent(sid, "collecting_name")
    return {
        "payload": service_payload(
            txt["lead_name_prompt"],
            sid,
            client_id,
            lead_flow=True,
            lead_step="name",
        ),
        "doc_id": None,
    }


def _lead_flow_payload(
    sid: str,
    q: str,
    client_id: str | None,
    *,
    txt: dict,
    service_payload,
) -> dict | None:
    st = mem_get(sid)
    intent = (st.get("lead_intent") or "none").strip()

    if intent == "collecting_name":
        return _collecting_name_reply(sid, q, client_id, txt=txt, service_payload=service_payload)

    if intent == "collecting_phone":
        phone = extract_phone(q)
        if not phone:
            return service_payload(
                txt["lead_phone_retry"],
                sid,
                client_id,
                lead_flow=True,
                lead_step="phone",
                quick_replies=_merge_lead_slot_qrs([], txt),
            )
        update_profile(sid, phone=phone)
        st2 = mem_get(sid)
        prof = st2.get("profile") or {}
        lead_payload, lead_status = handle_lead(
            {
                "name": (prof.get("name") or "").strip(),
                "phone": (prof.get("phone") or "").strip(),
                "intent": "lead",
                "sid": sid,
                "client_id": client_id,
                "situation_note": (st2.get("situation_note") or "").strip(),
            }
        )
        if lead_status != 200:
            return service_payload(
                txt["lead_submit_error"],
                sid,
                client_id,
                lead_flow=True,
                lead_step="phone",
                lead_error=lead_payload.get("error_code") or lead_payload.get("error"),
            )
        set_lead_intent(sid, "submitted")
        set_situation_pending(sid, False)
        clear_lead_pii(sid)
        return service_payload(
            resolve_lead_submit_message(client_id, txt),
            sid,
            client_id,
            lead_flow=True,
            lead_step="done",
        )
    return None


def resume_active_lead_flow(
    *,
    data: dict,
    sid: str,
    q: str,
    client_id: str | None,
    txt: dict,
    service_payload,
) -> dict | None:
    """Повтор lead-flow, если оркестратор не должен уводить в content/guided."""
    st = mem_get(sid)
    if not is_active_lead_flow(st):
        return None
    if st.get("lead_intent") == "confirming_name":
        return _handle_lead_name_confirm(
            data=data,
            sid=sid,
            q=q,
            client_id=client_id,
            txt=txt,
            service_payload=service_payload,
        )
    payload = _lead_flow_payload(
        sid, q, client_id, txt=txt, service_payload=service_payload
    )
    if payload is not None:
        return {"payload": payload, "doc_id": None}
    set_lead_intent(sid, "collecting_name")
    return {
        "payload": service_payload(
            txt["lead_name_prompt"],
            sid,
            client_id,
            lead_flow=True,
            lead_step="name",
        ),
        "doc_id": None,
    }


def handle_flows(
    *,
    data: dict,
    st: dict,
    sid: str,
    q: str,
    client_id: str | None,
    txt: dict,
    service_payload,
    get_last_content_ui_payload,
    get_topic_state,
) -> dict | None:
    """Return {'payload': dict, 'doc_id': str|None} when flow handled."""
    if data.get("situation_action") == "back":
        set_situation_pending(sid, False)
        snap = get_last_content_ui_payload(sid)
        if isinstance(snap, dict) and snap.get("answer"):
            restored = {
                "answer": snap.get("answer") or "",
                "quick_replies": list(snap.get("quick_replies") or []),
                "cta": snap.get("cta"),
                "video": snap.get("video"),
                "situation": snap.get("situation") or {"show": False, "mode": "normal"},
                "offer": snap.get("offer"),
                "meta": dict(snap.get("meta") or {}),
            }
            doc_id_back = st.get("current_doc_id") or (
                (restored.get("meta") or {}).get("file")
                and os.path.splitext(
                    os.path.basename((restored.get("meta") or {}).get("file") or "")
                )[0]
            )
            if doc_id_back and get_topic_state(sid, doc_id_back).get("situation_offered"):
                restored["situation"] = {"show": False, "mode": "normal"}
            meta_r = restored.setdefault("meta", {})
            meta_r["situation_back"] = True
            meta_r.setdefault("sid", sid)
            meta_r.setdefault("client_id", client_id)
            return {"payload": restored, "doc_id": st.get("current_doc_id")}
        return {
            "payload": service_payload(
                txt["situation_back_fallback"],
                sid,
                client_id,
                situation_back=True,
            ),
            "doc_id": st.get("current_doc_id"),
            "service_route": "situation_back",
        }

    if (data.get("ref") or "").strip() == LEAD_BOOKING_REF:
        mark_booking_intent_ever(sid)
        set_lead_intent(sid, "collecting_name")
        return {
            "payload": service_payload(
                _lead_entry_name_prompt(
                    client_id, txt, cta_key=LEAD_BOOKING_CTA_KEY
                ),
                sid,
                client_id,
                lead_flow=True,
                lead_step="name",
            ),
            "doc_id": None,
        }

    if st.get("lead_intent") == "confirming_name":
        return _handle_lead_name_confirm(
            data=data,
            sid=sid,
            q=q,
            client_id=client_id,
            txt=txt,
            service_payload=service_payload,
        )

    if q and explicit_booking_intent(q) and not is_active_lead_flow(st):
        clear_pending_lead_offer(sid)
        mark_booking_intent_ever(sid)
        set_lead_intent(sid, "collecting_name")
        return {
            "payload": service_payload(
                _lead_entry_name_prompt(
                    client_id, txt, cta_key=LEAD_BOOKING_CTA_KEY
                ),
                sid,
                client_id,
                lead_flow=True,
                lead_step="name",
                booking_intent_flag=True,
            ),
            "doc_id": None,
        }

    pending_lead = bool(st.get("pending_lead_offer"))
    if pending_lead and q:
        if parse_lead_offer_yes(q):
            clear_pending_lead_offer(sid)
            mark_booking_intent_ever(sid)
            set_lead_intent(sid, "collecting_name")
            return {
                "payload": service_payload(
                    _lead_entry_name_prompt(
                        client_id, txt, cta_key=LEAD_BOOKING_CTA_KEY
                    ),
                    sid,
                    client_id,
                    lead_flow=True,
                    lead_step="name",
                ),
                "doc_id": None,
                "service_route": "lead_flow",
            }
        if parse_lead_offer_no(q):
            clear_pending_lead_offer(sid)
            return {
                "payload": service_payload(
                    txt.get(
                        "lead_offer_declined",
                        "Хорошо. Если появятся вопросы — спрашивайте.",
                    ),
                    sid,
                    client_id,
                ),
                "doc_id": None,
                "service_route": "lead_offer_declined",
            }
        clear_pending_lead_offer(sid)
        st = mem_get(sid)

    if (
        q
        and parse_lead_offer_yes(q)
        and not pending_lead
        and not is_active_lead_flow(st)
        and st.get("lead_intent") != "confirming_name"
    ):
        return {
            "payload": service_payload(
                txt.get(
                    "bare_affirmative_fallback",
                    "Напишите, пожалуйста, ваш вопрос — так будет проще подсказать.",
                ),
                sid,
                client_id,
            ),
            "doc_id": None,
            "service_route": "bare_affirmative",
        }

    if is_active_lead_flow(st) and ((q or "").strip() or (data.get("ref") or "").strip()):
        active_result = _handle_active_lead_turn(
            data=data,
            sid=sid,
            q=q,
            client_id=client_id,
            txt=txt,
            service_payload=service_payload,
            st=st,
        )
        if active_result is not None:
            return active_result

    if is_lead_paused(st) and (q or (data.get("ref") or "").strip()):
        paused_result = _handle_paused_lead_turn(
            data=data,
            sid=sid,
            q=q,
            client_id=client_id,
            txt=txt,
            service_payload=service_payload,
            st=st,
        )
        if paused_result is not None:
            return paused_result

    if st.get("situation_pending"):
        if not q or len(q.strip()) < 3:
            return {
                "payload": service_payload(
                    txt["situation_retry_short"],
                    sid,
                    client_id,
                    situation_mode="pending",
                    situation_collect=True,
                ),
                "doc_id": None,
            }
        set_situation_note(sid, q)
        set_situation_pending(sid, False)
        set_lead_intent(sid, "collecting_name")
        return {
            "payload": service_payload(
                txt["situation_to_lead_name"],
                sid,
                client_id,
                lead_flow=True,
                lead_step="name",
            ),
            "doc_id": None,
        }

    if data.get("cta_action") == "lead":
        mark_booking_intent_ever(sid)
        set_lead_intent(sid, "collecting_name")
        return {
            "payload": service_payload(
                _lead_entry_name_prompt(client_id, txt, data),
                sid,
                client_id,
                lead_flow=True,
                lead_step="name",
            ),
            "doc_id": None,
        }

    if data.get("situation_action") == "start" or data.get("action") == "situation":
        if not situation_enabled(client_id):
            return None
        set_situation_pending(sid, True)
        return {
            "payload": service_payload(
                txt["situation_prompt"],
                sid,
                client_id,
                situation_mode="pending",
                situation_collect=True,
            ),
            "doc_id": None,
        }

    return None
