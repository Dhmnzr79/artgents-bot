"""Aspect-aware catalog suppression for A5 arbiter (Retrieval 2.0).

When the question has a clear facet (e.g. pain, duration) and a strong faq/alias candidate exists,
service-overview catalog matches must not win via score / shortcut_single_candidate.

Duration slice: strong candidates include faq/info and service *sections* (non-overview), not
another service overview (e.g. temporary_teeth#korotko must not trigger suppression).

Canon: PRODUCT_WORK_PLAN.md stage 6; no regex→md routes.
"""
from __future__ import annotations

import os
from typing import Any

from contracts.answer_plan import AspectKind
from core.routing_loader import THRESHOLDS

_STRONG_ALIAS_TIERS: frozenset[str] = frozenset({"exact", "near_exact"})
_OVERVIEW_ANCHORS: frozenset[str] = frozenset({"", "korotko", "overview"})


def doc_id_anchor_from_ref(ref: str) -> tuple[str | None, str]:
    """`implantation__service__classic.md#korotko` → doc_id + anchor."""
    r = (ref or "").strip()
    if not r:
        return None, ""
    left, _, right = r.partition("#")
    base = os.path.basename(left.strip())
    if base.lower().endswith(".md"):
        base = base[:-3]
    return (base.strip() or None), (right or "").strip().lower()


def is_compact_service_overview(row: dict[str, Any]) -> bool:
    """Service doc pointing at overview anchor (#korotko / empty / overview)."""
    doc_id = str(row.get("doc_id") or "").strip().lower()
    if "__service__" not in doc_id:
        return False
    anchor = str(row.get("anchor") or "").strip().lower()
    if anchor not in _OVERVIEW_ANCHORS:
        _, anchor2 = doc_id_anchor_from_ref(str(row.get("ref") or ""))
        anchor = anchor or anchor2
    return anchor in _OVERVIEW_ANCHORS


def is_catalog_service_overview(row: dict[str, Any]) -> bool:
    """Catalog md_first pointing at a service overview chunk."""
    if str(row.get("source_kind") or "").strip().lower() != "catalog":
        return False
    return is_compact_service_overview(row)


def _facet_row_doc_kind_allowed(row: dict[str, Any], facet_aspect: str) -> bool:
    """Which compact row doc types count as strong facet evidence."""
    dt = str(row.get("doc_type") or "").strip().lower()
    if dt in ("faq", "info"):
        return True
    if facet_aspect == "duration" and dt == "service":
        return not is_compact_service_overview(row)
    return False


def is_strong_facet_candidate(
    row: dict[str, Any],
    *,
    facet_aspect: str,
    min_facet_score: float,
) -> bool:
    """Strong faq/info (and duration service-section) row matching the query facet."""
    if str(row.get("aspect") or "").strip().lower() != facet_aspect:
        return False
    sk = str(row.get("source_kind") or "").strip().lower()
    if sk not in ("alias", "retrieval"):
        return False
    if not _facet_row_doc_kind_allowed(row, facet_aspect):
        return False
    if sk == "alias":
        tier = str(row.get("alias_decision") or "").strip().lower()
        if tier in _STRONG_ALIAS_TIERS:
            return True
    try:
        score = float(row.get("score"))
    except (TypeError, ValueError):
        score = 0.0
    return score >= float(min_facet_score)


def filter_compact_for_facet_arbitration(
    compact: list[dict[str, Any]],
    *,
    primary_aspect: AspectKind | None,
    q: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Drop catalog service-overview rows when a strong facet candidate exists."""
    tel: dict[str, Any] = {
        "facet_arbitration_applied": False,
        "facet_arbitration_primary_aspect": primary_aspect,
    }
    fa = THRESHOLDS.facet_arbitration
    if not fa.enabled:
        tel["facet_arbitration_skipped"] = "disabled"
        return compact, [], tel

    aspect = str(primary_aspect or "").strip().lower()
    allowed = {str(a).strip().lower() for a in (fa.aspects or []) if str(a).strip()}
    if not aspect or aspect not in allowed:
        tel["facet_arbitration_skipped"] = "aspect_not_in_scope"
        return compact, [], tel

    if aspect == "price":
        tel["facet_arbitration_skipped"] = "price_primary"
        return compact, [], tel

    min_score = float(fa.min_facet_score)
    strong = [
        row
        for row in compact
        if isinstance(row, dict) and is_strong_facet_candidate(row, facet_aspect=aspect, min_facet_score=min_score)
    ]
    if not strong:
        tel["facet_arbitration_skipped"] = "no_strong_facet_candidate"
        tel["facet_arbitration_strong_count"] = 0
        return compact, [], tel

    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in compact:
        if not isinstance(row, dict):
            continue
        if is_catalog_service_overview(row):
            rejected.append(
                {
                    "ref": row.get("ref"),
                    "source_kind": row.get("source_kind"),
                    "score": row.get("score"),
                    "reason": f"facet_arbitration_suppress_catalog_overview:{aspect}",
                }
            )
            continue
        kept.append(row)

    if rejected:
        tel["facet_arbitration_applied"] = True
        tel["facet_arbitration_suppressed_count"] = len(rejected)
        tel["facet_arbitration_strong_refs"] = [
            str(r.get("ref") or "") for r in strong if str(r.get("ref") or "").strip()
        ]
    else:
        tel["facet_arbitration_skipped"] = "no_catalog_overview_to_suppress"

    return kept, rejected, tel
