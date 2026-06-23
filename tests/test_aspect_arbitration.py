"""Facet-aware catalog suppression (Retrieval 2.0 slice 1 — pain only)."""
from __future__ import annotations

from content_arbiter import collect_content_candidates
from arbiter import build_compact_content_candidates, decide_content_route
from core.aspect_arbitration import (
    filter_compact_for_facet_arbitration,
    is_catalog_service_overview,
    is_strong_facet_candidate,
)


def _catalog_overview_row() -> dict:
    return {
        "ref": "implantation__service__classic.md#korotko",
        "source_kind": "catalog",
        "score": 0.88,
        "doc_type": "catalog_md",
        "doc_id": "implantation__service__classic",
        "anchor": "korotko",
        "aspect": "overview",
    }


def _pain_alias_row(*, alias_decision: str = "exact", score: float = 0.837) -> dict:
    return {
        "ref": "implantation__faq__pain.md#korotko",
        "source_kind": "alias",
        "score": score,
        "doc_type": "faq",
        "doc_id": "implantation__faq__pain",
        "anchor": "korotko",
        "aspect": "pain",
        "alias_decision": alias_decision,
    }


def test_is_catalog_service_overview_positive() -> None:
    assert is_catalog_service_overview(_catalog_overview_row()) is True


def test_is_catalog_service_overview_negative_faq() -> None:
    row = _catalog_overview_row()
    row["doc_id"] = "implantation__faq__pain"
    row["ref"] = "implantation__faq__pain.md#korotko"
    assert is_catalog_service_overview(row) is False


def test_strong_facet_alias_exact() -> None:
    assert is_strong_facet_candidate(
        _pain_alias_row(),
        facet_aspect="pain",
        min_facet_score=0.72,
    )


def test_strong_facet_alias_weak_score_without_exact() -> None:
    assert not is_strong_facet_candidate(
        _pain_alias_row(alias_decision="embed_medium", score=0.65),
        facet_aspect="pain",
        min_facet_score=0.72,
    )


def test_filter_suppresses_catalog_when_pain_alias_exact() -> None:
    compact = [_catalog_overview_row(), _pain_alias_row()]
    kept, rejected, tel = filter_compact_for_facet_arbitration(
        compact,
        primary_aspect="pain",
        q="Больно ли ставить имплант?",
    )
    assert tel["facet_arbitration_applied"] is True
    assert len(rejected) == 1
    assert rejected[0]["ref"] == "implantation__service__classic.md#korotko"
    assert len(kept) == 1
    assert kept[0]["doc_id"] == "implantation__faq__pain"


def test_filter_skips_price_primary() -> None:
    compact = [_catalog_overview_row(), _pain_alias_row()]
    kept, rejected, tel = filter_compact_for_facet_arbitration(
        compact,
        primary_aspect="price",
        q="Сколько стоит имплант?",
    )
    assert tel["facet_arbitration_skipped"] == "aspect_not_in_scope"
    assert len(rejected) == 0
    assert len(kept) == 2


def test_filter_skips_without_strong_facet() -> None:
    compact = [
        _catalog_overview_row(),
        _pain_alias_row(alias_decision="embed_medium", score=0.65),
    ]
    kept, rejected, tel = filter_compact_for_facet_arbitration(
        compact,
        primary_aspect="pain",
        q="Больно ли ставить имплант?",
    )
    assert tel["facet_arbitration_skipped"] == "no_strong_facet_candidate"
    assert len(rejected) == 0
    assert len(kept) == 2


def test_decide_content_route_pain_picks_faq_not_catalog() -> None:
    """Smoke #16 path without pain overlay: arbiter must not shortcut to catalog."""
    q = "Больно ли ставить имплант?"
    cands = collect_content_candidates(q=q, sid="unit_pain_arb", client_id="demo")
    compact = build_compact_content_candidates(cands, client_id="demo")
    assert any(
        is_strong_facet_candidate(r, facet_aspect="pain", min_facet_score=0.72)
        for r in compact
        if isinstance(r, dict)
    ), "pain alias/faq must be present in compact for guard to work"
    result = decide_content_route(
        q=q,
        sid="unit_pain_arb",
        client_id="demo",
        candidates=cands,
    )
    assert result.selected_doc_id == "implantation__faq__pain"
    assert result.selected_route == "retrieval_chunk"
    assert result.debug_meta.get("facet_arbitration_applied") is True


def test_decide_content_route_price_does_not_suppress_catalog() -> None:
    """Smoke #11: price question must keep catalog classic candidate."""
    q = "Сколько стоит один имплант?"
    cands = collect_content_candidates(q=q, sid="unit_price_arb", client_id="demo")
    compact_before = build_compact_content_candidates(cands, client_id="demo")
    catalog_rows = [r for r in compact_before if r.get("source_kind") == "catalog"]
    assert catalog_rows, "catalog candidate expected for price query"
    result = decide_content_route(
        q=q,
        sid="unit_price_arb",
        client_id="demo",
        candidates=cands,
    )
    facet_applied = result.debug_meta.get("facet_arbitration_applied")
    assert facet_applied is not True
    assert result.selected_route in ("catalog_md_first", "retrieval_chunk", "guided")
