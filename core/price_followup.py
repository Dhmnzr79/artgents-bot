"""Vague price follow-up: session context before weak catalog price-token matches."""
from __future__ import annotations

import re
from typing import Any

from config import PRICE_LOOKUP_RE
from policy import continuation_only_phrase

_PRICE_STOP = frozenset({
    "сколько",
    "стоит",
    "цена",
    "ценам",
    "цене",
    "цену",
    "ценой",
    "стоимость",
    "стоим",
    "рублей",
    "рубль",
    "руб",
    "прайс",
    "расценк",
    "обойдется",
    "обойдётся",
})

_QUERY_FILLER_STOP = _PRICE_STOP | frozenset({
    "а",
    "и",
    "ну",
    "так",
    "ещё",
    "еще",
    "что",
    "как",
    "это",
    "ли",
    "же",
    "бы",
    "по",
    "за",
    "на",
    "в",
    "во",
    "у",
    "о",
    "об",
    "от",
    "до",
    "для",
    "про",
    "мне",
})

_VAGUE_PRICE_MAX_TOKENS = 10


def _service_signal_tokens(q: str) -> list[str]:
    qn = re.sub(r"\s+", " ", (q or "").strip(), flags=re.U)
    stripped = PRICE_LOOKUP_RE.sub("", qn).strip()
    stripped = re.sub(r"^(?:а|и|ну)\s+", "", stripped, flags=re.I | re.U).strip()
    stripped = re.sub(r"^[\s?.!,;:—\-]+", "", stripped).strip()
    tokens = [
        t.lower().replace("ё", "е")
        for t in re.findall(r"[0-9a-zа-яё]{2,}", stripped, flags=re.I | re.U)
    ]
    return [t for t in tokens if t not in _QUERY_FILLER_STOP]


def price_query_has_explicit_service_object(q: str) -> bool:
    """True when a price question names a service, not only «сколько стоит» / «по ценам»."""
    if continuation_only_phrase(q):
        return False
    return bool(_service_signal_tokens(q))


def is_vague_price_followup(q: str) -> bool:
    q0 = (q or "").strip()
    if not q0 or not PRICE_LOOKUP_RE.search(q0):
        return False
    toks = [t for t in re.split(r"\s+", q0, flags=re.U) if t]
    if len(toks) > _VAGUE_PRICE_MAX_TOKENS:
        return False
    return not price_query_has_explicit_service_object(q0)


def is_weak_catalog_price_token_match(match: dict[str, Any], q: str) -> bool:
    if not is_vague_price_followup(q):
        return False
    if not (match.get("matched_service_id") or "").strip():
        return False
    return str(match.get("match_channel") or "") == "lemma_weak"
