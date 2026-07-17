"""Tests for lead-flow pause / interrupt during booking."""
from __future__ import annotations

import uuid

from core.observability_pii import observability_user_texts
from core.lead_paused_overlay import finish_lead_paused_payload
from flow_handlers import (
    LEAD_BOOKING_REF,
    _collecting_name_reply,
    _try_lead_step_controls,
    handle_flows,
)
from lead_interrupt import (
    LEAD_PAUSE_REF,
    detect_lead_interrupt,
    is_ambiguous_short_reply,
    looks_like_slot_answer,
    parse_lead_cancel,
    parse_lead_defer,
    parse_lead_meta_pause,
)
from session import (
    is_lead_context,
    is_lead_paused,
    mem_add_user,
    mem_get,
    mem_reset,
    pause_lead_flow,
    resume_lead_from_pause,
    set_lead_intent,
)


def test_detect_lead_interrupt_contacts_price_generic() -> None:
    assert detect_lead_interrupt("А какой адрес?", resume_step="collecting_name") == "contacts"
    assert detect_lead_interrupt("Сколько стоит имплант?", resume_step="collecting_name") == "price"
    assert detect_lead_interrupt("А больно ли?", resume_step="collecting_name") == "pain"
    assert detect_lead_interrupt("расскажите про all-on-4", resume_step="collecting_name") == "generic"


def test_slot_answer_not_interrupt() -> None:
    assert detect_lead_interrupt("Мария", resume_step="collecting_name") is None
    assert detect_lead_interrupt("Мария?", resume_step="collecting_name") is None
    assert looks_like_slot_answer("Мария?", "collecting_name")
    assert detect_lead_interrupt("+79991234567", resume_step="collecting_phone") is None


def test_ambiguous_not_interrupt() -> None:
    assert is_ambiguous_short_reply("не знаю")
    assert detect_lead_interrupt("не знаю", resume_step="collecting_name") is None
    assert detect_lead_interrupt("all-on-4", resume_step="collecting_name") is None


def test_parse_lead_cancel_includes_ne_seychas() -> None:
    assert parse_lead_cancel("не надо")
    assert parse_lead_cancel("отменить запись")
    assert parse_lead_cancel("не сейчас")
    assert parse_lead_cancel("не хочу")
    assert parse_lead_cancel("Не хочу")
    assert parse_lead_cancel("не хочу записываться")
    assert parse_lead_cancel("передумал")
    assert parse_lead_cancel("Я передумал")
    assert parse_lead_cancel("Не, я передумал")
    assert not parse_lead_cancel("я не буду")
    assert not parse_lead_cancel("Мария")


def test_parse_lead_meta_pause_and_defer() -> None:
    assert parse_lead_meta_pause("задать вопрос")
    assert parse_lead_meta_pause("хочу задать вопрос")
    assert parse_lead_defer("надо подумать")
    assert not parse_lead_meta_pause("Я боюсь боли")


def test_detect_lead_interrupt_pain() -> None:
    assert detect_lead_interrupt("Я боюсь боли", resume_step="collecting_name") == "pain"
    assert detect_lead_interrupt("А больно ли?", resume_step="collecting_name") == "pain"


def test_pause_and_resume_session_fields() -> None:
    sid = uuid.uuid4().hex
    mem_reset(sid)
    pause_lead_flow(
        sid,
        resume_step="collecting_name",
        return_doc_id="implantation__faq__pain",
        interrupt_kind="contacts",
    )
    st = mem_get(sid)
    assert is_lead_paused(st)
    assert is_lead_context(st)
    assert st["lead_resume_step"] == "collecting_name"
    pause_lead_flow(sid, resume_step="collecting_name", interrupt_kind="generic")
    assert is_lead_paused(mem_get(sid))
    assert int(mem_get(sid).get("lead_paused_answer_count") or 0) == 0
    step = resume_lead_from_pause(sid)
    assert step == "collecting_name"
    assert not is_lead_paused(mem_get(sid))


def test_mem_add_user_skips_hist_in_lead_context() -> None:
    sid = uuid.uuid4().hex
    mem_reset(sid)
    pause_lead_flow(sid, resume_step="collecting_name", interrupt_kind="contacts")
    mem_add_user(sid, "А какой адрес?")
    st = mem_get(sid)
    assert not st["hist"]
    assert int(st["session_turn_count"]) == 1


def test_finish_lead_paused_payload_bridge_once() -> None:
    sid = uuid.uuid4().hex
    mem_reset(sid)
    pause_lead_flow(sid, resume_step="collecting_name", interrupt_kind="contacts")
    txt = {
        "lead_paused_bridge_name": "Продолжим запись — напишите имя.",
    }
    out1 = finish_lead_paused_payload(
        {"answer": "Мы на ул. Примерная, 1.", "quick_replies": []},
        sid,
        "demo",
        txt,
    )
    assert "Продолжим запись" in (out1.get("answer") or "")
    assert any(qr.get("ref") == "lead:resume" for qr in (out1.get("quick_replies") or []))
    assert any(qr.get("label") == "Отменить запись" for qr in (out1.get("quick_replies") or []))

    out2 = finish_lead_paused_payload(
        {"answer": "Ещё ответ.", "quick_replies": []},
        sid,
        "demo",
        txt,
    )
    assert "Продолжим запись" not in (out2.get("answer") or "")
    assert "Ещё ответ." in (out2.get("answer") or "")


def test_finish_lead_paused_payload_strips_topic_ui() -> None:
    sid = uuid.uuid4().hex
    mem_reset(sid)
    pause_lead_flow(sid, resume_step="collecting_name", interrupt_kind="generic")
    out = finish_lead_paused_payload(
        {
            "answer": "Ответ по теме.",
            "quick_replies": [{"label": "Подробнее", "ref": "doc#section"}],
            "cta": {"text": "Записаться", "action": "lead", "key": "booking"},
            "video": {"key": "v1", "src": "https://example.com/v.mp4"},
            "situation": {"show": True, "mode": "normal"},
            "meta": {"followups": [{"label": "Цены", "ref": "doc#prices"}]},
        },
        sid,
        "demo",
        {},
    )
    refs = {(qr.get("ref") or "").strip() for qr in (out.get("quick_replies") or [])}
    assert refs == {"lead:resume", "lead:cancel"}
    assert out.get("cta") is None
    assert out.get("video") is None
    assert (out.get("situation") or {}).get("show") is False
    assert (out.get("meta") or {}).get("followups") == []


def test_first_lead_prompt_has_no_ask_question_qr() -> None:
    sid = uuid.uuid4().hex
    mem_reset(sid)
    txt = {
        "lead_ask_question_label": "Задать вопрос",
        "lead_name_prompt": "Как к вам можно обращаться?",
    }

    def _sp(answer, sid, client_id, **kwargs):
        return {
            "answer": answer,
            "quick_replies": list(kwargs.get("quick_replies") or []),
            "meta": {"sid": sid, "client_id": client_id},
        }

    result = handle_flows(
        data={"ref": LEAD_BOOKING_REF},
        st=mem_get(sid),
        sid=sid,
        q="",
        client_id="demo",
        txt=txt,
        service_payload=_sp,
        get_last_content_ui_payload=lambda _sid: None,
        get_topic_state=lambda _sid, _doc: {},
    )
    assert result is not None
    qrs = (result.get("payload") or {}).get("quick_replies") or []
    assert not any((qr.get("ref") or "") == LEAD_PAUSE_REF for qr in qrs)


def test_lead_invalid_name_gets_unclear_with_ask_question_qr() -> None:
    sid = uuid.uuid4().hex
    mem_reset(sid)
    set_lead_intent(sid, "collecting_name")
    txt = {
        "lead_ask_question_label": "Задать вопрос",
        "lead_unclear_retry": "Напишите имя или задайте вопрос.",
    }

    def _sp(answer, sid, client_id, **kwargs):
        return {
            "answer": answer,
            "quick_replies": list(kwargs.get("quick_replies") or []),
            "meta": {"sid": sid, "client_id": client_id},
        }

    payload = _collecting_name_reply(
        sid, "12345", "demo", txt=txt, service_payload=_sp
    )
    assert payload is not None
    qrs = payload.get("quick_replies") or []
    assert any((qr.get("ref") or "") == LEAD_PAUSE_REF for qr in qrs)
    assert any((qr.get("label") or "") == "Задать вопрос" for qr in qrs)


def test_lead_pause_ref_prompt() -> None:
    sid = uuid.uuid4().hex
    mem_reset(sid)
    set_lead_intent(sid, "collecting_name")
    st = mem_get(sid)
    txt = {
        "lead_ask_question_prompt": "Задайте вопрос.",
        "lead_ask_question_label": "Задать вопрос",
    }

    def _sp(answer, sid, client_id, **kwargs):
        meta = {"sid": sid, "client_id": client_id}
        if kwargs.get("lead_flow"):
            meta["lead_flow"] = True
        if kwargs.get("lead_step"):
            meta["lead_step"] = kwargs["lead_step"]
        return {
            "answer": answer,
            "quick_replies": list(kwargs.get("quick_replies") or []),
            "cta": kwargs.get("cta"),
            "meta": meta,
        }

    action, result = _try_lead_step_controls(
        ref=LEAD_PAUSE_REF,
        q="",
        sid=sid,
        st=st,
        client_id="demo",
        txt=txt,
        service_payload=_sp,
    )
    assert action == "paused_prompt"
    assert result is not None
    assert is_lead_paused(mem_get(sid))
    assert "Задайте вопрос" in (result.get("payload") or {}).get("answer", "")


def test_observability_withheld_on_paused_retrieval_route() -> None:
    user, preview, withheld = observability_user_texts(
        "А больно ли?",
        route="retrieval_chunk",
        meta={"lead_flow": True, "lead_paused": True, "lead_step": "paused"},
    )
    assert withheld is True
    assert user != "А больно ли?"
