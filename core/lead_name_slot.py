"""Lead name slot: permissive ACCEPT vs PENDING (structural rules + unambiguous INTJ only)."""

from __future__ import annotations

import re
from typing import Literal

from alias_lexical import morph_analyzer
from name_gate import (
    hard_reject_lead_name,
    is_lead_name_reject_token,
    is_plausible_name_token,
    matches_lead_name_token_shape,
    normalize_lead_name_input,
)

_MULTI_SPACE = re.compile(r"\s+")

LeadNameSlotKind = Literal["accept", "pending"]


def _format_single_name_token(tok: str) -> str:
    t = (tok or "").strip()
    if len(t) > 1:
        return t[:1].upper() + t[1:].lower()
    return t.capitalize()


def _unambiguous_single_word_intj(word: str) -> bool:
    """
    True only when every pymorphy parse is INTJ (e.g. unambiguous interjection).

    Mixed parses (Name + VERB, etc.) → False → ACCEPT path for ambiguous tokens.
    """
    if is_lead_name_reject_token(word):
        return True
    morph = morph_analyzer()
    if morph is None:
        return False
    wl = normalize_lead_name_input(word).lower().replace("ё", "е")
    if not wl:
        return False
    try:
        parses = morph.parse(wl)
    except Exception:
        return False
    if not parses:
        return False
    return all(getattr(p.tag, "POS", None) == "INTJ" for p in parses)


def _text_structurally_obvious_non_name(text: str) -> bool:
    """Morph supplement: only unambiguous one-word INTJ; phrases use hard_reject."""
    words = _MULTI_SPACE.split((text or "").strip())
    words = [w for w in words if w]
    if len(words) != 1:
        return False
    return _unambiguous_single_word_intj(words[0])


def evaluate_lead_name_slot(text: str) -> tuple[LeadNameSlotKind, str | None]:
    """
    ACCEPT by default for ambiguous/unknown short tokens.

    PENDING: hard_reject (questions, phrases, medical intents) or unambiguous INTJ.
    """
    raw = (text or "").strip()
    if not raw:
        return "pending", None
    if hard_reject_lead_name(raw):
        return "pending", None
    if _text_structurally_obvious_non_name(raw):
        return "pending", None

    from session import extract_name

    name = extract_name(raw)
    if name:
        return "accept", name

    normalized = normalize_lead_name_input(raw)
    parts = _MULTI_SPACE.split(normalized)
    if len(parts) == 1:
        tok = parts[0]
        if matches_lead_name_token_shape(tok) and not _unambiguous_single_word_intj(tok):
            if is_plausible_name_token(tok) or len(tok) <= 14:
                return "accept", _format_single_name_token(tok)

    return "pending", None


def accept_lead_name_for_slot(text: str) -> str | None:
    kind, name = evaluate_lead_name_slot(text)
    return name if kind == "accept" else None
