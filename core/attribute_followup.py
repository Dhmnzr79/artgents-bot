"""Vague attribute follow-ups: session context before weak catalog marker matches."""

from __future__ import annotations

import re
from typing import Any, Literal

from config import PRICE_LOOKUP_RE
from policy import continuation_only_phrase

AttributeFollowupKind = Literal[
    "price",
    "duration",
    "pain",
    "warranty",
    "doctor",
    "payment",
    "included",
]

_ASPECT_TO_KIND: dict[str, AttributeFollowupKind] = {
    "price": "price",
    "duration": "duration",
    "pain": "pain",
    "warranty": "warranty",
    "payment": "payment",
    "included": "included",
}

_STRONG_CATALOG_CHANNELS = frozenset({"exact", "lemma_strong"})

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

_ATTRIBUTE_STOP: dict[AttributeFollowupKind, frozenset[str]] = {
    "price": _PRICE_STOP,
    "duration": frozenset({
        "долго",
        "длительн",
        "время",
        "времени",
        "срок",
        "сроки",
        "месяц",
        "месяцев",
        "недель",
        "недели",
        "сколько",
    }),
    "pain": frozenset({
        "больно",
        "болит",
        "боль",
        "анестез",
        "анестезия",
        "обезбол",
        "безболезнен",
        "боюсь",
        "страш",
        "страх",
    }),
    "warranty": frozenset({
        "гарант",
        "гарантия",
        "гарантии",
        "гарантий",
        "гарантийный",
        "какая",
        "какой",
        "какие",
        "какое",
    }),
    "doctor": frozenset({
        "врач",
        "врача",
        "врачи",
        "доктор",
        "доктора",
        "специалист",
        "специалиста",
        "хирург",
        "имплантолог",
        "делает",
        "делают",
        "кто",
        "какой",
        "какая",
        "какие",
    }),
    "payment": frozenset({
        "рассроч",
        "оплат",
        "кредит",
        "платеж",
        "платёж",
    }),
    "included": frozenset({
        "входит",
        "включено",
        "ключ",
        "состав",
    }),
}

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
    "такой",
    "такая",
    "такое",
    "такие",
    "это",
    "эта",
    "этот",
    "эти",
})

_DOCTOR_MARKERS_RE = re.compile(
    r"\b("
    r"врач\w*|доктор\w*|специалист\w*|хирург\w*|имплантолог\w*|"
    r"кто\s+делает|какой\s+врач"
    r")\b",
    re.I | re.U,
)

_KIND_MARKER_RES: dict[AttributeFollowupKind, re.Pattern[str]] = {
    "price": PRICE_LOOKUP_RE,
    "duration": re.compile(
        r"\b("
        r"долго|длительн|сколько\s+времени|по\s+времени|срок\w*|месяц\w*|недел\w*"
        r")\b",
        re.I | re.U,
    ),
    "pain": re.compile(
        r"\b(больно|болит|боль|анестез\w*|обезбол\w*|безболезнен\w*|боюсь|страш\w*)\b",
        re.I | re.U,
    ),
    "warranty": re.compile(r"\bгарант\w*\b", re.I | re.U),
    "doctor": _DOCTOR_MARKERS_RE,
    "payment": re.compile(r"\b(рассроч\w*|оплат\w*|кредит\w*)\b", re.I | re.U),
    "included": re.compile(
        r"\b(под\s+ключ|что\s+входит|входит\s+в|не\s+входит)\b",
        re.I | re.U,
    ),
}

_VAGUE_ATTRIBUTE_MAX_TOKENS = 10


def _tokenize(q: str) -> list[str]:
    return [t for t in re.split(r"\s+", (q or "").strip(), flags=re.U) if t]


def _aspect_kinds_for_query(q: str) -> list[AttributeFollowupKind]:
    from core.answer_planner import detect_aspects

    q0 = (q or "").strip()
    if not q0:
        return []
    kinds: list[AttributeFollowupKind] = []
    for aspect in detect_aspects(q0):
        kind = _ASPECT_TO_KIND.get(aspect)
        if kind and kind not in kinds:
            kinds.append(kind)
    for kind, pattern in _KIND_MARKER_RES.items():
        if kind not in kinds and pattern.search(q0):
            kinds.append(kind)
    return kinds


def _strip_aspect_markers(q: str, kind: AttributeFollowupKind) -> str:
    qn = re.sub(r"\s+", " ", (q or "").strip(), flags=re.U)
    if kind == "price":
        qn = PRICE_LOOKUP_RE.sub("", qn).strip()
    stops = _ATTRIBUTE_STOP.get(kind, frozenset())
    tokens = [
        t
        for t in re.findall(r"[0-9a-zа-яё]{2,}", qn, flags=re.I | re.U)
        if t.lower().replace("ё", "е") not in stops
    ]
    return " ".join(tokens)


def _service_signal_tokens(q: str, *, kind: AttributeFollowupKind | None = None) -> list[str]:
    qn = re.sub(r"\s+", " ", (q or "").strip(), flags=re.U)
    if kind == "price" or kind is None:
        stripped = PRICE_LOOKUP_RE.sub("", qn).strip()
    elif kind is not None:
        stripped = _strip_aspect_markers(qn, kind)
    else:
        stripped = qn
    stripped = re.sub(r"^(?:а|и|ну)\s+", "", stripped, flags=re.I | re.U).strip()
    stripped = re.sub(r"^[\s?.!,;:—\-]+", "", stripped).strip()
    tokens = [
        t.lower().replace("ё", "е")
        for t in re.findall(r"[0-9a-zа-яё]{2,}", stripped, flags=re.I | re.U)
    ]
    filler = _QUERY_FILLER_STOP
    if kind is not None:
        filler = filler | _ATTRIBUTE_STOP.get(kind, frozenset())
    return [t for t in tokens if t not in filler]


def query_has_explicit_service_object(
    q: str,
    *,
    kind: AttributeFollowupKind | None = None,
) -> bool:
    """True when the question names a service/topic, not only an attribute marker."""
    if continuation_only_phrase(q):
        return False
    return bool(_service_signal_tokens(q, kind=kind))


def _query_matches_kind(q: str, kind: AttributeFollowupKind) -> bool:
    return kind in _aspect_kinds_for_query(q)


def is_vague_attribute_followup(q: str, kind: AttributeFollowupKind) -> bool:
    """Short attribute question without an explicit service object."""
    q0 = (q or "").strip()
    if not q0 or not _query_matches_kind(q0, kind):
        return False
    toks = _tokenize(q0)
    if len(toks) > _VAGUE_ATTRIBUTE_MAX_TOKENS:
        return False
    return not query_has_explicit_service_object(q0, kind=kind)


def detect_vague_attribute_kinds(q: str) -> list[AttributeFollowupKind]:
    """All vague attribute kinds detected in a short follow-up query."""
    kinds = _aspect_kinds_for_query(q)
    return [k for k in kinds if is_vague_attribute_followup(q, k)]


def is_vague_attribute_followup_any(q: str) -> bool:
    return bool(detect_vague_attribute_kinds(q))


def catalog_match_is_authoritative(match: dict[str, Any], q: str) -> bool:
    """Catalog may set service_id only on explicit object or strong/exact/containment match."""
    if not (match.get("matched_service_id") or "").strip():
        return False
    channel = str(match.get("match_channel") or "")
    if detect_vague_attribute_kinds(q):
        if channel in _STRONG_CATALOG_CHANNELS and match.get("is_confident"):
            return True
        if match.get("containment_eligible") and match.get("is_confident"):
            return True
        return False
    if query_has_explicit_service_object(q):
        return bool(match.get("is_confident"))
    if channel in _STRONG_CATALOG_CHANNELS and match.get("is_confident"):
        return True
    if match.get("containment_eligible") and match.get("is_confident"):
        return True
    return False


def is_weak_catalog_match_for_vague_attribute(
    match: dict[str, Any],
    q: str,
    kind: AttributeFollowupKind,
) -> bool:
    if not is_vague_attribute_followup(q, kind):
        return False
    if not (match.get("matched_service_id") or "").strip():
        return False
    return not catalog_match_is_authoritative(match, q)
