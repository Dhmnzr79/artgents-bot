"""Chunk aspect inference for Retrieval 2.0 (stage 6 spike).

Aspect is stored in corpus at build_index time; runtime uses soft boost only (no hard route).
Canon: PRODUCT_WORK_PLAN.md §3.1, contracts/answer_plan.py AspectKind.
"""
from __future__ import annotations

from typing import Any

from contracts.answer_plan import AspectKind

_ASPECT_KINDS: frozenset[str] = frozenset(
    {
        "price",
        "payment",
        "warranty",
        "pain",
        "included",
        "duration",
        "comparison",
        "stages",
        "overview",
    }
)

_SUBTOPIC_ASPECT: dict[str, AspectKind] = {
    "pain": "pain",
    "duration": "duration",
    "tooth_one_day": "duration",
    "tooth_loss": "overview",
    "osseointegration": "overview",
    "cost": "price",
    "what_included": "included",
    "steps": "stages",
    "methods_overview": "overview",
    "aftercare": "duration",
    "bone_graft": "overview",
    "contraindications": "overview",
    "technology": "overview",
    "temporary_teeth": "duration",
    "one_stage": "overview",
    "classic": "overview",
}


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def infer_chunk_aspect(
    *,
    doc_id: str,
    doc_type: str | None,
    subtopic: str | None,
    frontmatter_aspect: Any = None,
) -> AspectKind | None:
    """Infer canonical aspect for a corpus row. Frontmatter `aspect:` wins."""
    raw_fm = _norm(str(frontmatter_aspect or "")) if frontmatter_aspect is not None else ""
    if raw_fm in _ASPECT_KINDS:
        return raw_fm  # type: ignore[return-value]

    did = _norm(doc_id)
    dt = _norm(doc_type)
    st = _norm(subtopic)

    if did.startswith("comparison__") or dt == "comparison":
        return "comparison"
    if "__pricing__" in did or dt == "pricing":
        return "price"
    if did == "clinic__info__payment_terms" or st == "payment_terms":
        return "payment"
    if did == "clinic__info__warranty" or st == "warranty":
        return "warranty"
    if dt == "faq" and st in _SUBTOPIC_ASPECT:
        return _SUBTOPIC_ASPECT[st]
    if st in _SUBTOPIC_ASPECT:
        return _SUBTOPIC_ASPECT[st]
    if dt in ("info", "service"):
        return "overview"
    return None
