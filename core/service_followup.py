"""Short attribute follow-ups tied to an active catalog service in session."""

from __future__ import annotations

import re
from typing import Any

from session import mem_get

_PRONOUN_RE = re.compile(
    r"\b("
    r"он|она|оно|они|его|её|ее|их|ему|ей|им|этот|эта|это|эти|тот|та|то|те|"
    r"такой|такая|такое|такие|там|туда|оттуда|сюда|здесь|тут"
    r")\b",
    re.I | re.U,
)

_CONTINUATION_START_RE = re.compile(
    r"^(?:а|и|ну|так|ещё|еще|продолж|подробн|дальше|а\s+если|а\s+что)\b",
    re.I | re.U,
)

_ATTRIBUTE_MARKERS_RE = re.compile(
    r"\b("
    r"долго|длительн|сколько\s+времени|по\s+времени|срок|сроки|месяц|недел|"
    r"больно|болит|боль|анестез|обезбол|"
    r"гарант\w*|рассроч\w*|оплат\w*|адрес|контакт|"
    r"гарант|прижив|не\s+прижив"
    r")\b",
    re.I | re.U,
)

_ATTRIBUTE_SYNONYM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset(
        {
            "долго",
            "длительность",
            "длительн",
            "срок",
            "сроки",
            "время",
            "времени",
            "месяц",
            "месяцев",
            "недель",
            "недели",
        }
    ),
    frozenset({"больно", "болит", "боль", "анестез", "анестезия", "обезбол", "безболезнен"}),
    frozenset({"гарант", "гарантия", "гарантии"}),
    frozenset({"прижив", "приживется", "приживление", "приживаемость"}),
)

_SHORT_FOLLOWUP_MAX_TOKENS = 8


def _tokenize(q: str) -> list[str]:
    return [t for t in re.split(r"\s+", (q or "").strip(), flags=re.U) if t]


def normalize_service_id(raw: str | None) -> str:
    s = (raw or "").strip().lower().replace("-", "_")
    return re.sub(r"[^\w]", "_", s).strip("_")


def is_short_attribute_followup(q: str) -> bool:
    """Короткий вопрос про атрибут услуги или с указательным «это/такой»."""
    toks = _tokenize(q)
    if not (1 <= len(toks) <= _SHORT_FOLLOWUP_MAX_TOKENS):
        return False
    q0 = (q or "").strip()
    if _ATTRIBUTE_MARKERS_RE.search(q0):
        return True
    if _PRONOUN_RE.search(q0) and (
        _CONTINUATION_START_RE.search(q0) or len(toks) <= 5
    ):
        return True
    return False


def _norm_compare(s: str) -> str:
    x = (s or "").strip().lower().replace("ё", "е")
    x = re.sub(r"[^\w\s\-]", " ", x, flags=re.U)
    return re.sub(r"\s+", " ", x).strip()


def rewrite_overlaps_attribute_synonyms(q_user: str, q_rewrite: str) -> bool:
    """Связь по синонимичным атрибутам (долго ↔ длительность и т.п.)."""
    u = set(_norm_compare(q_user).split())
    r = set(_norm_compare(q_rewrite).split())
    for group in _ATTRIBUTE_SYNONYM_GROUPS:
        if (u & group) and (r & group):
            return True
        for ut in u:
            for rt in r:
                if len(ut) >= 4 and len(rt) >= 4 and ut[:4] == rt[:4] and ut[:4] in group:
                    return True
    return False


def rewrite_overlaps_context_anchors(model_out: str, anchors: list[str]) -> bool:
    """Rewrite содержит активную услугу/тему из сессии."""
    r = _norm_compare(model_out)
    if not r:
        return False
    r_tokens = set(r.split())
    for anchor in anchors:
        a = _norm_compare(anchor)
        if not a:
            continue
        if a in r:
            return True
        for tok in a.split():
            if len(tok) >= 3 and tok in r_tokens:
                return True
            if len(tok) >= 4 and tok[:4] in r:
                return True
        sid = normalize_service_id(anchor)
        if sid and sid.replace("_", " ") in r.replace("_", " "):
            return True
    return False


def rewrite_context_anchors_from_bits(topic_bits: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for bit in topic_bits:
        b = (bit or "").strip()
        if not b:
            continue
        key = b.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(b)
    return out


def _doc_id_from_ref(ref: str) -> str:
    fname = (ref or "").split("#", 1)[0].strip()
    base = fname.rsplit("/", 1)[-1]
    if base.lower().endswith(".md"):
        base = base[:-3]
    return base.strip().lower()


def candidate_belongs_to_service(row: dict[str, Any], service_id: str) -> bool:
    sid = normalize_service_id(service_id)
    if not sid:
        return False
    row_sid = normalize_service_id(str(row.get("service_id") or ""))
    if row_sid and row_sid == sid:
        return True
    doc_id = _doc_id_from_ref(str(row.get("ref") or ""))
    if not doc_id:
        return False
    doc_norm = doc_id.replace("-", "_")
    return f"__{sid}" in doc_norm or doc_norm.endswith(f"_{sid}") or doc_norm.endswith(sid)


def is_generic_faq_candidate(row: dict[str, Any]) -> bool:
    doc_type = str(row.get("doc_type") or "").strip().lower()
    if doc_type == "faq":
        return True
    doc_id = _doc_id_from_ref(str(row.get("ref") or ""))
    return "__faq__" in doc_id


def is_pricing_candidate(row: dict[str, Any]) -> bool:
    doc_type = str(row.get("doc_type") or "").strip().lower()
    if doc_type in ("pricing", "pricing_specific"):
        return True
    return "__pricing__" in _doc_id_from_ref(str(row.get("ref") or ""))


def resolve_active_service_id(
    *,
    decision_frame: Any | None,
    catalog_matched_service_id: str | None = None,
    session_last_service_id: str | None = None,
) -> str | None:
    if decision_frame is not None:
        if hasattr(decision_frame, "service_id"):
            raw = str(getattr(decision_frame, "service_id") or "").strip()
        elif isinstance(decision_frame, dict):
            raw = str(decision_frame.get("service_id") or "").strip()
        else:
            raw = ""
        if raw and raw.lower() not in ("unknown", "none", ""):
            return normalize_service_id(raw)
    for raw in (catalog_matched_service_id, session_last_service_id):
        r = (raw or "").strip()
        if r:
            return normalize_service_id(r)
    return None


def filter_compact_for_service_followup(
    compact: list[dict[str, Any]],
    *,
    service_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Убрать generic FAQ и pricing, если есть кандидат той же услуги."""
    same = [r for r in compact if candidate_belongs_to_service(r, service_id)]
    if not same:
        return compact, []
    rejected: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    for row in compact:
        if is_generic_faq_candidate(row) and not candidate_belongs_to_service(row, service_id):
            rejected.append(row)
            continue
        if is_pricing_candidate(row) and candidate_belongs_to_service(row, service_id):
            rejected.append(row)
            continue
        kept.append(row)
    if not kept:
        return compact, []
    return kept, rejected


def pick_preferred_same_service_row(
    compact: list[dict[str, Any]],
    *,
    service_id: str,
) -> dict[str, Any] | None:
    rows = [r for r in compact if candidate_belongs_to_service(r, service_id)]
    if not rows:
        return None
    rows = [r for r in rows if not is_pricing_candidate(r)]
    if not rows:
        return None

    def _rank(row: dict[str, Any]) -> tuple[int, float]:
        ref = str(row.get("ref") or "").lower()
        doc_id = _doc_id_from_ref(ref)
        kind = str(row.get("doc_type") or "").lower()
        score = float(row.get("score") or 0.0)
        priority = 0
        if kind == "catalog_md" or "__service__" in doc_id:
            priority = 3
        elif kind == "service":
            priority = 2
        elif "__info__" in doc_id:
            priority = 1
        return (priority, score)

    rows.sort(key=_rank, reverse=True)
    return rows[0]


def active_service_id_for_turn(
    *,
    sid: str | None,
    decision_frame: Any | None,
    catalog_matched_service_id: str | None = None,
) -> str | None:
    session_last = None
    if sid:
        st = mem_get(sid)
        session_last = str(st.get("last_catalog_service_id") or "").strip() or None
    return resolve_active_service_id(
        decision_frame=decision_frame,
        catalog_matched_service_id=catalog_matched_service_id,
        session_last_service_id=session_last,
    )
