"""Catalog-based explicit service / scope detection for price gating."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import alias_lexical
from core.catalog_match import _core_tokens_catalog, _norm, rank_catalog_services
from query_selector import _client_json_path, _read_json_dict

VOLUME_SCOPE_MARKER = "__volume_scope__"

_GENERIC_TOOTH = frozenset({
    "зуб",
    "зуба",
    "зубов",
    "зубы",
    "зубом",
    "зубе",
    "зубной",
    "зубная",
    "зубные",
    "зубную",
    "зубного",
    "зубное",
    "зубных",
    "зубам",
    "зубами",
})

_PRICE_ONLY = frozenset({
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

_STOP = frozenset({
    "а", "в", "во", "на", "по", "за", "к", "ко", "с", "со", "из", "от", "до",
    "не", "ли", "бы", "же", "и", "или", "но", "что", "как", "это", "для",
    "при", "под", "над", "без", "то", "все", "мне", "мой", "моя", "моё",
    "вы", "вас", "вам", "нас", "нам", "их", "его", "её", "будет",
})

_EXPLICIT_CHANNELS = frozenset({"exact", "lemma_strong", "lemma_weak", "overlap", "typo"})


def _norm_client_id(client_id: str | None) -> str:
    return (client_id or "demo").strip() or "demo"


@lru_cache(maxsize=8)
def _load_catalog(client_id: str) -> dict[str, Any]:
    raw = _read_json_dict(_client_json_path(client_id, "service_catalog.json"))
    return raw if isinstance(raw, dict) else {}


def _query_for_match(q: str) -> str:
    from config import PRICE_LOOKUP_RE

    qn = re.sub(r"\s+", " ", (q or "").strip(), flags=re.U)
    qn = PRICE_LOOKUP_RE.sub("", qn).strip()
    qn = re.sub(r"^(?:а|и|ну)\s+", "", qn, flags=re.I | re.U).strip()
    qn = re.sub(r"^[\s?.!,;:—\-]+", "", qn).strip()
    qn = re.sub(r"[\s?.!,;:—\-]+$", "", qn).strip()
    return qn


def _generic_implant_scope_only(q: str) -> bool:
    from core import patient_scope_cues as psc

    stripped = _query_for_match(q)
    if not stripped:
        return False
    if psc.query_names_specific_implant_protocol(stripped):
        return False
    return bool(psc.IMPLANT_PRICE_RX.search(stripped))


def _signal_tokens(text: str) -> list[str]:
    return [
        t
        for t in _core_tokens_catalog(text)
        if t not in _GENERIC_TOOTH and t not in _PRICE_ONLY and t not in _STOP
    ]


def _lemma_forms(tokens: list[str]) -> set[str]:
    if not tokens:
        return set()
    return {str(x).lower().replace("ё", "е") for x in alias_lexical.lemma_forms_for_tokens(tokens)}


def _phrase_signals_in_query(query: str, phrase: str) -> bool:
    q_tokens = _signal_tokens(_query_for_match(query))
    if not q_tokens:
        return False
    phrase_tokens = _signal_tokens(phrase)
    if not phrase_tokens:
        return False
    q_lem = _lemma_forms(q_tokens)
    p_lem = _lemma_forms(phrase_tokens)
    if q_lem & p_lem:
        return True
    q_norm = _norm(_query_for_match(query))
    p_norm = _norm(phrase)
    if len(p_norm) >= 4 and p_norm in q_norm:
        return True
    return False


def _phrase_has_explicit_tokens(phrase: str) -> bool:
    return bool(_signal_tokens(phrase))


def _candidate_is_explicit(
    query: str,
    *,
    matched_phrase: str,
    channel: str,
    containment_ok: bool,
) -> bool:
    if channel not in _EXPLICIT_CHANNELS:
        return False
    if not _phrase_has_explicit_tokens(matched_phrase):
        return False
    if not _phrase_signals_in_query(query, matched_phrase):
        return False
    if channel in ("exact", "lemma_strong"):
        return True
    if channel == "lemma_weak":
        return True
    return bool(containment_ok)


def _pick_best_candidate(
    query: str,
    ranked: list[Any],
) -> Any | None:
    explicit = [
        cand
        for cand in ranked
        if _candidate_is_explicit(
            query,
            matched_phrase=cand.matched_phrase,
            channel=cand.channel,
            containment_ok=cand.containment_ok,
        )
    ]
    if not explicit:
        return None
    if len(explicit) == 1:
        return explicit[0]

    cleaned = _query_for_match(query)
    cleaned_tokens = set(_signal_tokens(cleaned))
    cleaned_joined = " ".join(cleaned_tokens)

    def _rank_key(cand: Any) -> tuple[float, float, float, float, int, str]:
        phrase_tokens = set(_signal_tokens(cand.matched_phrase))
        overlap = len(cleaned_tokens & phrase_tokens)
        recall = overlap / len(phrase_tokens) if phrase_tokens else 0.0
        precision = overlap / len(cleaned_tokens) if cleaned_tokens else 0.0
        topic_boost = 0.0
        if "удал" in cleaned_joined and "нерв" not in cleaned_joined:
            if str(cand.catalog_topic or "") == "extraction":
                topic_boost = 1.0
        if "лечен" in cleaned_joined and "пульп" not in cleaned_joined and "нерв" not in cleaned_joined:
            if cand.service_id == "teeth_treatment":
                topic_boost = 1.0
        channel_rank = {
            "exact": 0,
            "lemma_strong": 1,
            "lemma_weak": 2,
            "overlap": 3,
            "typo": 4,
        }.get(str(cand.channel), 9)
        return (topic_boost, float(overlap), recall, precision, -channel_rank, str(cand.service_id))

    explicit.sort(key=_rank_key, reverse=True)
    return explicit[0]


def _has_explicit_volume_scope(q: str) -> bool:
    from core import patient_scope_cues as psc

    text = (q or "").strip()
    if not text:
        return False
    if psc.query_names_specific_implant_protocol(text):
        return True
    if psc.IMPLANT_PRICE_RX.search(text):
        return True
    if (
        psc.JAW_EXPLICIT_RX.search(text)
        or psc.FULL_ARCH_RX.search(text)
        or psc.UPPER_JAW_RX.search(text)
        or psc.ONE_TOOTH_EXPLICIT_RX.search(text)
        or psc.ALL_TEETH_MISSING_RX.search(text)
    ):
        return True
    if re.search(r"нижн\w*\s+челюст", text, flags=re.I | re.U):
        return True
    return False


def _query_only_generic_tooth_or_price(q: str) -> bool:
    tokens = _signal_tokens(_query_for_match(q))
    if not tokens:
        return True
    return all(t in _GENERIC_TOOTH for t in tokens)


def explicit_service_mentioned(q: str, client_id: str | None) -> str | None:
    """Return service_id, volume marker, or None when service/scope not named explicitly."""
    q0 = (q or "").strip()
    if not q0:
        return None
    if _query_only_generic_tooth_or_price(q0):
        return None

    if _generic_implant_scope_only(q0):
        return VOLUME_SCOPE_MARKER

    cid = _norm_client_id(client_id)
    catalog = _load_catalog(cid)
    cleaned = _query_for_match(q0)
    ranked = rank_catalog_services(cleaned or q0, catalog)
    best = _pick_best_candidate(q0, ranked)
    if best is not None:
        return str(best.service_id)

    if _has_explicit_volume_scope(q0):
        return VOLUME_SCOPE_MARKER
    return None


def explicit_service_mentioned_bool(q: str, client_id: str | None) -> bool:
    return explicit_service_mentioned(q, client_id) is not None
