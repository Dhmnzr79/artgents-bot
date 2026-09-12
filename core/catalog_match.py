"""Catalog service containment: channel-aware scoring + topic tie-break."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import alias_lexical
from core.routing_loader import THRESHOLDS

_STOP = frozenset({
    "а", "в", "во", "на", "по", "за", "к", "ко", "с", "со", "из", "от", "до",
    "не", "ли", "бы", "же", "и", "или", "но", "что", "как", "это", "для",
    "при", "под", "над", "без", "то", "все", "мне", "мой", "моя", "моё",
    "вы", "вас", "вам", "нас", "нам", "их", "его", "её",
})

_TYPO_TOKEN_STOP = frozenset({
    "сколько", "стоит", "цена", "стоимость", "стоим", "рублей", "рубль", "руб",
})


def _norm(s: str) -> str:
    x = (s or "").strip().lower().replace("ё", "е")
    x = re.sub(r"[^\w\s]", " ", x, flags=re.U)
    return re.sub(r"\s+", " ", x, flags=re.U).strip()


def _token_set(s: str) -> set[str]:
    return {t for t in _norm(s).split() if len(t) >= 2 or t.isdigit()}


def _contains_token_phrase(query_norm: str, phrase_norm: str) -> bool:
    if not query_norm or not phrase_norm:
        return False
    pattern = r"(?<!\w)" + re.escape(phrase_norm) + r"(?!\w)"
    return bool(re.search(pattern, query_norm, flags=re.U))


def _core_tokens_catalog(text: str) -> list[str]:
    return [t for t in _norm(text).split() if (len(t) >= 2 or t.isdigit()) and t not in _STOP]


def match_score(query: str, phrase: str) -> float:
    qn = _norm(query)
    pn = _norm(phrase)
    if not qn or not pn:
        return 0.0
    if _contains_token_phrase(qn, pn):
        return 1.0
    qt = _token_set(qn)
    pt = _token_set(pn)
    if not qt or not pt:
        return 0.0
    inter = len(qt.intersection(pt))
    if inter == 0:
        return 0.0
    recall = inter / len(pt)
    precision = inter / len(qt)
    return round(max(recall, (recall + precision) / 2.0), 4)


def match_score_lemma(query: str, phrase: str) -> float:
    q_toks = _core_tokens_catalog(query)
    p_toks = _core_tokens_catalog(phrase)
    if not q_toks or not p_toks:
        return 0.0
    q_lem = set(alias_lexical.lemma_forms_for_tokens(q_toks))
    p_lem = set(alias_lexical.lemma_forms_for_tokens(p_toks))
    if not q_lem or not p_lem:
        return 0.0
    if p_lem <= q_lem:
        return 0.92
    if q_lem <= p_lem:
        return 0.88
    inter = len(q_lem & p_lem)
    if inter == 0:
        return 0.0
    recall = inter / len(p_lem)
    precision = inter / len(q_lem)
    return round(max(recall, (recall + precision) / 2.0), 4)


def _catalog_typo_stem_overlap(q_token: str, phrase_norm: str, *, min_stem: int = 7) -> float:
    qt = _norm(q_token)
    if len(qt) < min_stem + 1 or not phrase_norm:
        return 0.0
    for start in range(len(qt) - min_stem + 1):
        for length in range(len(qt) - start, min_stem - 1, -1):
            sub = qt[start : start + length]
            if len(sub) >= min_stem and sub in phrase_norm:
                return 0.78
    return 0.0


def match_score_catalog_typo(query: str, phrase: str) -> float:
    q_tokens = [
        t
        for t in _core_tokens_catalog(query)
        if len(t) >= 5 and t not in _TYPO_TOKEN_STOP
    ]
    if not q_tokens:
        return 0.0
    p_norm = _norm(phrase)
    p_tokens = [_norm(t) for t in _core_tokens_catalog(phrase) if len(t) >= 4]
    best = 0.0
    for qt in q_tokens:
        qt_n = _norm(qt)
        for pt in p_tokens:
            best = max(best, alias_lexical.trigram_alias_boost(qt_n, pt))
        if p_norm:
            best = max(best, alias_lexical.trigram_alias_boost(qt_n, p_norm))
            if len(qt_n) >= 8:
                trimmed = qt_n[:-1]
                best = max(best, alias_lexical.trigram_alias_boost(trimmed, p_norm))
            best = max(best, _catalog_typo_stem_overlap(qt_n, p_norm))
    return round(float(best), 4)


@dataclass(frozen=True)
class PhraseMatch:
    score: float
    channel: str
    containment_ok: bool


def _lemma_weak_containment_ok(query: str, phrase: str) -> bool:
    q_toks = _core_tokens_catalog(query)
    p_toks = _core_tokens_catalog(phrase)
    if not q_toks or not p_toks:
        return False
    q_lem = set(alias_lexical.lemma_forms_for_tokens(q_toks))
    p_lem = set(alias_lexical.lemma_forms_for_tokens(p_toks))
    if not q_lem <= p_lem:
        return False
    signal = [t for t in q_toks if t not in _TYPO_TOKEN_STOP]
    if not signal:
        return False
    signal_lem = set(alias_lexical.lemma_forms_for_tokens(signal))
    if not signal_lem & p_lem:
        return False
    min_recall = float(THRESHOLDS.catalog_match.lemma_weak_phrase_recall_min)
    return (len(q_lem & p_lem) / len(p_lem)) >= min_recall


def score_catalog_phrase(query: str, phrase: str) -> PhraseMatch:
    cm = THRESHOLDS.catalog_match
    s_exact = match_score(query, phrase)
    s_lemma = match_score_lemma(query, phrase)
    s_typo = match_score_catalog_typo(query, phrase)
    best = max(s_exact, s_lemma, s_typo)

    if s_exact >= best - 1e-9 and s_exact > 0:
        channel = "exact"
    elif s_lemma >= 0.92 - 1e-9 and s_lemma >= s_typo:
        channel = "lemma_strong"
    elif s_lemma >= 0.88 - 1e-9 and s_lemma >= s_typo:
        channel = "lemma_weak"
    elif s_typo >= best - 1e-9 and s_typo > 0:
        channel = "typo"
    else:
        channel = "overlap"

    containment_ok = False
    if best >= float(cm.containment_min):
        if channel in ("exact", "lemma_strong"):
            containment_ok = True
        elif channel == "lemma_weak":
            containment_ok = _lemma_weak_containment_ok(query, phrase)
        elif channel == "overlap":
            containment_ok = True
        elif channel == "typo":
            support = float(cm.typo_support_min)
            containment_ok = s_exact >= support or s_lemma >= support

    return PhraseMatch(score=best, channel=channel, containment_ok=containment_ok)


def _service_title(entry: dict[str, Any]) -> str:
    return str(entry.get("title") or entry.get("name") or "").strip()


def _service_content_ref(entry: dict[str, Any]) -> str:
    ref = str(entry.get("md_entry_ref") or entry.get("content_ref") or "").strip()
    return ref.removesuffix(".md")


def infer_catalog_service_topic(service_id: str, entry: dict[str, Any]) -> str | None:
    topic = entry.get("topic")
    if isinstance(topic, str) and topic.strip():
        return topic.strip().lower()
    md = _service_content_ref(entry)
    if md:
        head = md.split("__", 1)[0].strip().lower()
        if head:
            return head
    sid = str(service_id or "").strip().lower()
    if sid == "tomography":
        return "clinic"
    return None


@dataclass(frozen=True)
class ServiceMatchCandidate:
    service_id: str
    service: dict[str, Any]
    score: float
    channel: str
    containment_ok: bool
    matched_phrase: str
    catalog_topic: str | None


def _topic_confidence_ok(topic_confidence: float) -> bool:
    return float(topic_confidence or 0.0) >= float(
        THRESHOLDS.catalog_match.topic_tiebreak_min_confidence
    )


def rank_catalog_services(
    q: str,
    catalog: dict[str, Any],
    *,
    exclude_service_ids: frozenset[str] | None = None,
    service_topic: str | None = None,
    topic_confidence: float = 0.0,
) -> list[ServiceMatchCandidate]:
    cm = THRESHOLDS.catalog_match
    skip = {str(x).strip().lower() for x in (exclude_service_ids or frozenset()) if str(x).strip()}
    want_topic = str(service_topic or "").strip().lower() or None
    topic_ok = bool(want_topic) and _topic_confidence_ok(topic_confidence)

    ranked: list[ServiceMatchCandidate] = []
    for service_id, entry in catalog.items():
        if not isinstance(entry, dict) or not bool(entry.get("active", True)):
            continue
        sid = str(service_id).strip().lower()
        if sid in skip:
            continue
        phrases: list[str] = []
        title = _service_title(entry)
        if title:
            phrases.append(title)
        phrases.extend(str(x).strip() for x in (entry.get("aliases") or []) if str(x).strip())

        best_pm: PhraseMatch | None = None
        best_phrase = ""
        for ph in phrases:
            pm = score_catalog_phrase(q, ph)
            if best_pm is None or pm.score > best_pm.score:
                best_pm = pm
                best_phrase = ph
            elif best_pm is not None and pm.score == best_pm.score:
                channel_rank = {"exact": 0, "lemma_strong": 1, "lemma_weak": 2, "overlap": 3, "typo": 4}
                if channel_rank.get(pm.channel, 9) < channel_rank.get(best_pm.channel, 9):
                    best_pm = pm
                    best_phrase = ph

        if best_pm is None or best_pm.score <= 0:
            continue

        ranked.append(
            ServiceMatchCandidate(
                service_id=str(service_id),
                service=entry,
                score=float(best_pm.score),
                channel=str(best_pm.channel),
                containment_ok=bool(best_pm.containment_ok),
                matched_phrase=best_phrase,
                catalog_topic=infer_catalog_service_topic(str(service_id), entry),
            )
        )

    def _sort_key(row: ServiceMatchCandidate) -> tuple[float, int, str]:
        boost = 0.0
        if topic_ok and want_topic and row.catalog_topic == want_topic:
            boost = float(cm.topic_tiebreak_boost)
        channel_rank = {"exact": 0, "lemma_strong": 1, "lemma_weak": 2, "overlap": 3, "typo": 4}
        return (-(row.score + boost), channel_rank.get(row.channel, 9), row.service_id)

    ranked.sort(key=_sort_key)
    return ranked


def resolve_catalog_match(
    q: str,
    catalog: dict[str, Any],
    *,
    exclude_service_ids: frozenset[str] | None = None,
    service_topic: str | None = None,
    topic_confidence: float = 0.0,
    strong_match_min: float,
) -> dict[str, Any]:
    """Return catalog match dict (compatible with legacy match_service_from_catalog)."""
    cm = THRESHOLDS.catalog_match
    ranked = rank_catalog_services(
        q,
        catalog,
        exclude_service_ids=exclude_service_ids,
        service_topic=service_topic,
        topic_confidence=topic_confidence,
    )
    if not ranked:
        return {
            "matched_service_id": None,
            "service": None,
            "match_score": 0.0,
            "is_confident": False,
            "containment_eligible": False,
            "catalog_ambiguous": False,
            "match_channel": None,
        }

    top = ranked[0]
    ambiguous = False
    if len(ranked) >= 2:
        second = ranked[1]
        margin = float(cm.tie_score_margin)
        if (
            top.containment_ok
            and second.containment_ok
            and abs(top.score - second.score) <= margin
            and top.service_id != second.service_id
            and top.channel not in ("exact", "lemma_strong")
            and second.channel not in ("exact", "lemma_strong")
        ):
            ambiguous = True

    containment_eligible = bool(top.containment_ok and not ambiguous)
    if (
        containment_eligible
        and _topic_confidence_ok(topic_confidence)
        and str(service_topic or "").strip().lower()
        and top.catalog_topic
        and top.catalog_topic != str(service_topic or "").strip().lower()
        and top.channel in ("typo", "lemma_weak", "overlap")
    ):
        containment_eligible = False

    price_only_query = not [t for t in _core_tokens_catalog(q) if t not in _TYPO_TOKEN_STOP]
    if price_only_query and top.channel == "lemma_weak":
        containment_eligible = False

    is_confident = bool(top.score >= float(strong_match_min))
    if price_only_query and top.channel == "lemma_weak":
        is_confident = False

    return {
        "matched_service_id": top.service_id,
        "service": top.service,
        "match_score": round(float(top.score), 4),
        "is_confident": is_confident,
        "containment_eligible": containment_eligible,
        "catalog_ambiguous": ambiguous,
        "match_channel": top.channel,
        "matched_phrase": top.matched_phrase,
        "catalog_topic": top.catalog_topic,
    }
