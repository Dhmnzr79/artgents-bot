"""Fail-closed PII strip before pending lead question reaches One Call provider input."""

from __future__ import annotations

import re

from core.lead_dialog_excerpt import _EMAIL_RX
from name_gate import accept_lead_name

# Align with logging_setup phone detection (provider path removes phones entirely).
_PHONE_TEXT_RX = re.compile(r"(?<!\d)(?:\+?\d[\d\-\s().]{8,}\d)(?!\d)")

_INTRO_COMMA_RX = re.compile(r"^(.{2,60}?)[,\s]+(.+)$", re.U)
_GREETING_RX = re.compile(
    r"^(?:здравствуйте|добрый день|добрый вечер|привет)[,.\s]+",
    re.I,
)
_MENYA_ZOVUT_RX = re.compile(
    r"^(?:меня зовут|меня звать|мое имя)\s+(.+?)[,.]\s*(.+)$",
    re.I | re.S,
)
_YA_INTRO_RX = re.compile(r"^я\s+(.+?)[,\s]+(.+)$", re.I | re.S)


def _phone_digit_runs(raw: str) -> list[str]:
    runs: list[str] = []
    for match in _PHONE_TEXT_RX.finditer(raw or ""):
        digits = "".join(ch for ch in match.group() if ch.isdigit())
        if len(digits) >= 10:
            runs.append(digits)
    return runs


def _contains_leaked_phone_digits(cleaned: str, raw: str) -> bool:
    compact = re.sub(r"\D", "", cleaned or "")
    if not compact:
        return False
    for run in _phone_digit_runs(raw):
        for width in range(4, len(run) + 1):
            for idx in range(len(run) - width + 1):
                chunk = run[idx : idx + width]
                if chunk in compact:
                    return True
    return False


def _remove_emails(text: str) -> str:
    return _EMAIL_RX.sub(" ", text or "")


def _remove_phones(text: str) -> str:
    return _PHONE_TEXT_RX.sub(" ", text or "")


def _strip_name_intro(text: str, *, profile_name: str) -> str:
    s = (text or "").strip()
    if not s:
        return s
    s = _GREETING_RX.sub("", s).strip()
    prof = (profile_name or "").strip()

    match = _MENYA_ZOVUT_RX.match(s)
    if match:
        maybe = accept_lead_name(match.group(1).strip())
        rest = match.group(2).strip()
        if maybe and rest and (not prof or maybe.casefold() == prof.casefold()):
            return rest

    match = _YA_INTRO_RX.match(s)
    if match:
        maybe = accept_lead_name(match.group(1).strip())
        rest = match.group(2).strip()
        if maybe and rest and (not prof or maybe.casefold() == prof.casefold()):
            return rest

    intro = _INTRO_COMMA_RX.match(s)
    if intro:
        maybe_name = accept_lead_name(intro.group(1).strip())
        rest = intro.group(2).strip()
        if maybe_name and rest and (not prof or maybe_name.casefold() == prof.casefold()):
            return rest

    return s


def prepare_lead_pending_provider_question(
    raw: str,
    *,
    profile_name: str = "",
) -> str | None:
    source = (raw or "").strip()
    if not source:
        return None
    text = _remove_emails(source)
    text = _remove_phones(text)
    text = _strip_name_intro(text, profile_name=profile_name)
    text = re.sub(r"\s+", " ", text).strip(" ,.")
    had_phone = bool(_phone_digit_runs(source))
    if had_phone:
        lone_name = accept_lead_name(text)
        if lone_name and text.casefold() == lone_name.casefold():
            return None
    if len(text) < 3:        return None
    if re.fullmatch(r"[\d+\s().\-]+", text):
        return None
    if not re.search(r"[\u0400-\u04FFa-zA-Z]", text):
        return None
    if _contains_leaked_phone_digits(text, source):
        return None
    if "@" in text:
        return None
    if re.search(r"\*{2,}", text):
        return None
    return text
