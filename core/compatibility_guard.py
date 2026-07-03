"""Follow-up compatibility guard: relevance to rewritten query + explicit service conflict."""

from __future__ import annotations

import re
from typing import Any

from core.routing_loader import THRESHOLDS
from core.service_followup import candidate_belongs_to_service, normalize_service_id

_CLINIC_TOPICS = frozenset({"clinic", "contacts"})
_CLINIC_DOC_MARKERS = (
    "__info__",
    "__contacts__",
    "__payment__",
    "warranty",
    "__faq__",
)
_CLINIC_DOC_TYPES = frozenset({"info", "contacts", "payment", "faq"})


def _doc_id_from_ref(ref: str) -> str:
    fname = (ref or "").split("#", 1)[0].strip()
    base = fname.rsplit("/", 1)[-1]
    if base.lower().endswith(".md"):
        base = base[:-3]
    return base.strip().lower()


def _norm_tokens(s: str) -> set[str]:
    x = (s or "").strip().lower().replace("ё", "е")
    x = re.sub(r"[^\w\s]", " ", x, flags=re.U)
    return {t for t in x.split() if len(t) >= 3}


def is_clinic_cross_cutting(row: dict[str, Any]) -> bool:
    topic = str(row.get("topic") or "").strip().lower()
    if topic in _CLINIC_TOPICS:
        return True
    doc_id = _doc_id_from_ref(str(row.get("ref") or ""))
    if any(marker in doc_id for marker in _CLINIC_DOC_MARKERS):
        return True
    dt = str(row.get("doc_type") or "").strip().lower()
    return dt in _CLINIC_DOC_TYPES


def has_service_conflict(row: dict[str, Any], focus: dict[str, str]) -> bool:
    focus_sid = normalize_service_id(focus.get("service_id"))
    if not focus_sid:
        return False
    if is_clinic_cross_cutting(row):
        return False
    if candidate_belongs_to_service(row, focus_sid):
        return False

    row_sid = normalize_service_id(str(row.get("service_id") or ""))
    if row_sid and row_sid != focus_sid:
        return True

    doc_id = _doc_id_from_ref(str(row.get("ref") or ""))
    if not doc_id or doc_id.startswith("clinic__"):
        return False
    parts = doc_id.split("__")
    if len(parts) >= 3 and parts[1] in ("service", "pricing"):
        slug = normalize_service_id(parts[-1])
        if slug and slug != focus_sid:
            return True
    return False


def lexical_overlap(rewritten_query: str, row: dict[str, Any]) -> float:
    q_tokens = _norm_tokens(rewritten_query)
    if not q_tokens:
        return 0.0
    ref = str(row.get("ref") or "")
    snip = str(row.get("snippet") or "")
    row_tokens = _norm_tokens(ref + " " + snip)
    if not row_tokens:
        return 0.0
    hit = len(q_tokens & row_tokens)
    return hit / max(len(q_tokens), 1)


def doc_type_aspect_boost(row: dict[str, Any], rewritten_query: str) -> float:
    boost = float(THRESHOLDS.follow_up.doc_type_boost)
    q = (rewritten_query or "").lower()
    doc_id = _doc_id_from_ref(str(row.get("ref") or ""))
    total = 0.0
    if "гарант" in q and ("warranty" in doc_id or "гарант" in doc_id):
        total += boost
    if any(x in q for x in ("больно", "болит", "боль", "анестез")) and (
        "pain" in doc_id or "faq" in doc_id or "anest" in doc_id
    ):
        total += boost
    if any(x in q for x in ("оплат", "рассроч", "цен")) and (
        "payment" in doc_id or "pricing" in doc_id or "price" in doc_id
    ):
        total += boost
    if any(x in q for x in ("адрес", "контакт", "телефон")) and (
        "contact" in doc_id or doc_id.startswith("clinic__")
    ):
        total += boost
    return total


def relevance_score(row: dict[str, Any], rewritten_query: str) -> float:
    base = float(row.get("score") or 0.0)
    lex = lexical_overlap(rewritten_query, row)
    boost = doc_type_aspect_boost(row, rewritten_query)
    return base + lex * 0.12 + boost


def evaluate_candidate(
    row: dict[str, Any],
    *,
    rewritten_query: str,
    focus: dict[str, str],
) -> tuple[bool, str, float]:
    if has_service_conflict(row, focus):
        return False, "service_conflict", 0.0
    score = relevance_score(row, rewritten_query)
    if score < float(THRESHOLDS.follow_up.min_compat_score):
        return False, "low_relevance", score
    return True, "pass", score


def filter_compact_by_compatibility_guard(
    compact: list[dict[str, Any]],
    *,
    rewritten_query: str,
    focus: dict[str, str],
    client_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    del client_id  # reserved for future aspect_routing overrides
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    pass_reasons: dict[str, int] = {}
    best_score = 0.0

    for row in compact:
        if not isinstance(row, dict):
            continue
        ok, reason, score = evaluate_candidate(
            row, rewritten_query=rewritten_query, focus=focus
        )
        if ok:
            out = dict(row)
            out["compat_score"] = round(score, 4)
            kept.append(out)
            pass_reasons[reason] = pass_reasons.get(reason, 0) + 1
            best_score = max(best_score, score)
        else:
            rejected.append(
                {
                    **row,
                    "compat_reject_reason": reason,
                    "compat_score": round(score, 4),
                }
            )

    guard_pass_reason = "pass" if kept else "all_rejected"
    tel: dict[str, Any] = {
        "compat_guard_enabled": True,
        "compat_guard_kept": len(kept),
        "compat_guard_rejected": len(rejected),
        "guard_pass_reason": guard_pass_reason,
        "compat_score": round(best_score, 4) if kept else None,
    }
    if pass_reasons:
        tel["compat_pass_breakdown"] = pass_reasons
    return kept, rejected, tel
