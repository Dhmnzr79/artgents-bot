"""Deterministic lead-flow interrupt detection (pause / cancel during booking)."""
from __future__ import annotations

import re

from name_gate import accept_lead_name
from policy import contacts_intent, price_intent
from session import extract_phone, normalize_phone

LEAD_RESUME_REF = "lead:resume"
LEAD_CANCEL_REF = "lead:cancel"
LEAD_PAUSE_REF = "lead:pause"

_LEAD_CANCEL_RX = re.compile(
    r"^(?:"
    r"нет"
    r"|неа"
    r"|не\s+надо"
    r"|не\s+нужно"
    r"|no"
    r"|пока\s+не\s+хочу"
    r"|не\s+сейчас"
    r"|отмен(?:ить|а|ить\s+запись|я)?"
    r"|передумал(?:а)?"
    r")\W*$",
    re.I | re.U,
)

_AMBIGUOUS_RX = re.compile(
    r"^(?:"
    r"да"
    r"|ага"
    r"|угу"
    r"|ок(?:ей)?"
    r"|ok"
    r"|не\s+знаю"
    r"|может\s+быть"
    r"|пока"
    r"|хм+"
    r"|эм+"
    r")\W*$",
    re.I | re.U,
)

_QUESTION_PREFIX_RX = re.compile(
    r"^(?:"
    r"подскажите\b"
    r"|скажите\b"
    r"|расскажите\b"
    r"|объясните\b"
    r"|уточните\b"
    r"|интересует\b"
    r"|хочу\s+узнать\b"
    r")",
    re.I | re.U,
)

_A_STRONG_QUESTION_RX = re.compile(
    r"^а\s+(?:"
    r"как\b"
    r"|где\b"
    r"|сколько\b"
    r"|что\b"
    r"|когда\b"
    r"|можно\b"
    r"|есть\b"
    r"|больно\b"
    r"|почему\b"
    r")",
    re.I | re.U,
)


def parse_lead_cancel(text: str) -> bool:
    """Explicit cancel / change-of-mind during active or paused lead."""
    return bool(_LEAD_CANCEL_RX.fullmatch((text or "").strip()))


def is_ambiguous_short_reply(text: str) -> bool:
    return bool(_AMBIGUOUS_RX.fullmatch((text or "").strip()))


def starts_with_question_prefix(text: str) -> bool:
    return bool(_QUESTION_PREFIX_RX.match((text or "").strip()))


def looks_like_slot_answer(q: str, resume_step: str) -> bool:
    """True if message should be treated as slot input, not an interrupt."""
    s = (q or "").strip()
    if not s:
        return False
    step = (resume_step or "").strip()
    if step == "collecting_phone":
        return bool(extract_phone(s) or normalize_phone(s))
    if step in {"collecting_name", "confirming_name"}:
        if contacts_intent(s) or price_intent(s):
            return False
        if accept_lead_name(s):
            return True
    return False


def looks_like_generic_question(q: str) -> bool:
    s = (q or "").strip()
    if not s:
        return False
    if "?" in s:
        return True
    if starts_with_question_prefix(s):
        return True
    if _A_STRONG_QUESTION_RX.match(s):
        return True
    return False


def detect_lead_interrupt(q: str, *, resume_step: str) -> str | None:
    """
    Return interrupt kind for pause, or None (slot / ambiguous / not a question).
    kinds: contacts | price | generic
    """
    s = (q or "").strip()
    if not s:
        return None
    if looks_like_slot_answer(s, resume_step):
        return None
    if is_ambiguous_short_reply(s):
        return None
    if contacts_intent(s):
        return "contacts"
    if price_intent(s):
        return "price"
    if looks_like_generic_question(s):
        return "generic"
    return None
