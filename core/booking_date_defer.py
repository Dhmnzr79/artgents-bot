"""Lead-flow gate: accept preferred date/time without confirming slot availability."""
from __future__ import annotations

import re
from typing import Callable

from core.client_config_loader import booking_date_defer_enabled
from lead_interrupt import looks_like_pain_fear_concern
from policy import contacts_intent, explicit_booking_intent, price_intent
from session import extract_phone, normalize_phone

_DAY_MONTH_WORD_RX = re.compile(
    r"\b\d{1,2}\s+"
    r"(?:"
    r"январ[ьяе]?"
    r"|феврал[ьяе]?"
    r"|март[ае]?"
    r"|апрел[ьяе]?"
    r"|ма[йяе]"
    r"|июн[ьяе]?"
    r"|июл[ьяе]?"
    r"|август[ае]?"
    r"|сентябр[ьяе]?"
    r"|октябр[ьяе]?"
    r"|ноябр[ьяе]?"
    r"|декабр[ьяе]?"
    r")\w*",
    re.I | re.U,
)

_DAY_DOT_MONTH_RX = re.compile(r"\b\d{1,2}\s*[\./]\s*\d{1,2}(?:\s*[\./]\s*\d{2,4})?\b", re.U)

_RELATIVE_DAY_RX = re.compile(r"\b(?:завтра|послезавтра)\b", re.I | re.U)

_WEEKDAY_RX = re.compile(
    r"\b(?:"
    r"в\s+)?(?:"
    r"понедельник(?:а|у)?"
    r"|вторник(?:а|у)?"
    r"|сред[уа]"
    r"|четверг(?:а|у)?"
    r"|пятниц[уае]"
    r"|суббот[уае]"
    r"|воскресень[еяю]"
    r")\b",
    re.I | re.U,
)

_TIME_RX = re.compile(r"\b\d{1,2}[:.]\d{2}\b", re.U)

_BOOKING_ON_DATE_RX = re.compile(
    r"(?:"
    r"на\s+(?:\d|завтра|послезавтра|понедельник|вторник|сред|четверг|пятниц|суббот|воскресень)"
    r"|можно\s+на\b"
    r"|запис(?:аться|ать)\s+на\b"
    r"|при(?:ём|ем)\s+на\b"
    r"|время\s+на\b"
    r")",
    re.I | re.U,
)

_BARE_DAY_ON_RX = re.compile(
    r"(?:"
    r"на\s+\d{1,2}(?:\s*[-–]?(?:е|го|ое))?\b"
    r"|\d{1,2}\s*[-–](?:е|го|ое)\b"
    r")",
    re.I | re.U,
)

_BARE_DAY_WITH_MOGNO_RX = re.compile(
    r"\b\d{1,2}\b(?=[\s\S]*\b(?:можно|удобно|получится|запис)\b)",
    re.I | re.U,
)


def _bare_day_with_mogno(s: str) -> bool:
    if not re.search(r"\b(?:можно|удобно|получится|запис)\b", s, re.I | re.U):
        return False
    return bool(_BARE_DAY_WITH_MOGNO_RX.search(s))

_DATE_CHANGE_RX = re.compile(
    r"(?:"
    r"другой\s+день"
    r"|передумал"
    r"|поменя(?:ть|йте)\s+дат"
    r"|(?:а\s+)?раньше\s+можно"
    r"|на\s+друг(?:ой|ую)\b"
    r")",
    re.I | re.U,
)


def _is_phone_like(q: str) -> bool:
    s = (q or "").strip()
    if not s:
        return False
    return bool(extract_phone(s) or normalize_phone(s))


def _has_strong_date_cue(s: str) -> bool:
    return bool(
        _DAY_MONTH_WORD_RX.search(s)
        or _DAY_DOT_MONTH_RX.search(s)
        or _RELATIVE_DAY_RX.search(s)
        or _WEEKDAY_RX.search(s)
        or _TIME_RX.search(s)
    )


def extract_booking_datetime_preference(q: str) -> str | None:
    """Return a short date/time snippet for admin handoff (never shown to user)."""
    s = (q or "").strip()
    if not s:
        return None
    for rx in (
        _DAY_MONTH_WORD_RX,
        _DAY_DOT_MONTH_RX,
        _RELATIVE_DAY_RX,
        _WEEKDAY_RX,
        _BARE_DAY_ON_RX,
        _TIME_RX,
    ):
        m = rx.search(s)
        if m:
            return m.group(0).strip()
    if _bare_day_with_mogno(s):
        m = _BARE_DAY_WITH_MOGNO_RX.search(s)
        if m:
            return m.group(0).strip()
    if _DATE_CHANGE_RX.search(s):
        return s
    return None


def looks_like_booking_datetime_signal(
    q: str,
    *,
    in_lead_flow: bool = False,
    has_prior_preference: bool = False,
) -> bool:
    """True when user mentions or renegotiates a booking date/time."""
    s = (q or "").strip()
    if not s or _is_phone_like(s):
        return False

    strong = _has_strong_date_cue(s)
    bare_on = bool(_BARE_DAY_ON_RX.search(s))
    bare_with_mogno = _bare_day_with_mogno(s) and (
        in_lead_flow or has_prior_preference or bool(_BOOKING_ON_DATE_RX.search(s))
    )
    date_change = bool(_DATE_CHANGE_RX.search(s)) and (
        in_lead_flow or has_prior_preference or strong or bare_on or bare_with_mogno
    )

    if not (strong or bare_on or bare_with_mogno or date_change):
        return False

    if not strong and not date_change:
        if price_intent(s) or contacts_intent(s) or looks_like_pain_fear_concern(s):
            return False

    if strong or bare_on or date_change:
        return True

    if bare_with_mogno:
        return True

    if _TIME_RX.search(s) and (in_lead_flow or has_prior_preference or _BOOKING_ON_DATE_RX.search(s)):
        return True

    return False


def should_defer_booking_date_confirmation(
    *,
    q: str,
    client_id: str | None,
    resume_step: str,
    sid: str | None = None,
) -> bool:
    step = (resume_step or "").strip()
    if step not in {"collecting_name", "confirming_name", "collecting_phone"}:
        return False
    if not booking_date_defer_enabled(client_id):
        return False
    has_prior = False
    if sid:
        from session import get_lead_preferred_datetime

        has_prior = bool(get_lead_preferred_datetime(sid))
    return looks_like_booking_datetime_signal(
        q,
        in_lead_flow=True,
        has_prior_preference=has_prior,
    )


def should_defer_booking_date_at_entry(*, q: str, client_id: str | None) -> bool:
    if not booking_date_defer_enabled(client_id):
        return False
    if not explicit_booking_intent(q):
        return False
    return looks_like_booking_datetime_signal(q, in_lead_flow=True, has_prior_preference=False)


def build_booking_date_defer_answer(*, txt: dict, resume_step: str) -> str:
    step = (resume_step or "").strip()
    body = (
        txt.get("lead_booking_date_defer")
        or "Приняла запрос — по дате с вами свяжется и уточнит администратор."
    ).strip()
    if step == "collecting_phone":
        phone = (
            txt.get("lead_booking_date_defer_phone")
            or "Оставьте, пожалуйста, номер телефона — администратор свяжется с вами."
        ).strip()
        return f"{body} {phone}".strip()
    prompt = (txt.get("lead_name_prompt") or "Как к вам можно обращаться?").strip()
    return f"{body} {prompt}".strip()


def _store_preference_if_any(
    *,
    q: str,
    sid: str,
    store_preference: Callable[[str, str], None],
) -> None:
    preference = extract_booking_datetime_preference(q)
    if preference:
        store_preference(sid, preference)


def try_booking_date_defer_flow_result(
    *,
    q: str,
    sid: str,
    client_id: str | None,
    txt: dict,
    service_payload: Callable[..., dict],
    resume_step: str,
    store_preference: Callable[[str, str], None],
) -> dict | None:
    if not should_defer_booking_date_confirmation(
        q=q,
        client_id=client_id,
        resume_step=resume_step,
        sid=sid,
    ):
        return None
    _store_preference_if_any(q=q, sid=sid, store_preference=store_preference)
    answer = build_booking_date_defer_answer(txt=txt, resume_step=resume_step)
    lead_step = "phone" if resume_step == "collecting_phone" else "name"
    return {
        "payload": service_payload(
            answer,
            sid,
            client_id,
            lead_flow=True,
            lead_step=lead_step,
            quick_replies=[],
        ),
        "doc_id": None,
        "service_route": "lead_booking_date_defer",
    }


def try_booking_date_defer_at_entry(
    *,
    q: str,
    sid: str,
    client_id: str | None,
    txt: dict,
    service_payload: Callable[..., dict],
    store_preference: Callable[[str, str], None],
    set_lead_intent: Callable[[str, str], None],
) -> dict | None:
    if not should_defer_booking_date_at_entry(q=q, client_id=client_id):
        return None
    set_lead_intent(sid, "collecting_name")
    _store_preference_if_any(q=q, sid=sid, store_preference=store_preference)
    answer = build_booking_date_defer_answer(txt=txt, resume_step="collecting_name")
    return {
        "payload": service_payload(
            answer,
            sid,
            client_id,
            lead_flow=True,
            lead_step="name",
            quick_replies=[],
        ),
        "doc_id": None,
        "service_route": "lead_booking_date_defer",
    }
