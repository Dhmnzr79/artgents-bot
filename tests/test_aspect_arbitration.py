"""Facet-aware catalog suppression (Retrieval 2.0 — pain + duration)."""
from __future__ import annotations

from content_arbiter import collect_content_candidates
from arbiter import build_compact_content_candidates, decide_content_route
from core.aspect_arbitration import (
    filter_compact_for_facet_arbitration,
    is_catalog_service_overview,
    is_compact_service_overview,
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


def _duration_faq_row(*, alias_decision: str = "exact", score: float = 0.82) -> dict:
    return {
        "ref": "implantation__faq__duration.md#korotko",
        "source_kind": "alias",
        "score": score,
        "doc_type": "faq",
        "doc_id": "implantation__faq__duration",
        "anchor": "korotko",
        "aspect": "duration",
        "alias_decision": alias_decision,
    }


def _duration_service_section_row(*, alias_decision: str = "exact", score: float = 0.85) -> dict:
    return {
        "ref": "implantation__service__temporary_teeth.md#kogda-stavyat-vremennye-zuby",
        "source_kind": "alias",
        "score": score,
        "doc_type": "service",
        "doc_id": "implantation__service__temporary_teeth",
        "anchor": "kogda-stavyat-vremennye-zuby",
        "aspect": "duration",
        "alias_decision": alias_decision,
    }


def _duration_service_overview_row(*, alias_decision: str = "exact", score: float = 0.88) -> dict:
    return {
        "ref": "implantation__service__temporary_teeth.md#korotko",
        "source_kind": "alias",
        "score": score,
        "doc_type": "service",
        "doc_id": "implantation__service__temporary_teeth",
        "anchor": "korotko",
        "aspect": "duration",
        "alias_decision": alias_decision,
    }


def _catalog_all_on_4_row() -> dict:
    return {
        "ref": "implantation__service__all_on_4.md#korotko",
        "source_kind": "catalog",
        "score": 1.0,
        "doc_type": "catalog_md",
        "doc_id": "implantation__service__all_on_4",
        "anchor": "korotko",
        "aspect": "overview",
    }


def _comparison_alias_row(*, alias_decision: str = "exact", score: float = 1.0) -> dict:
    return {
        "ref": "comparison__all_on_4_vs_all_on_6.md#korotko",
        "source_kind": "alias",
        "score": score,
        "doc_type": "comparison",
        "doc_id": "comparison__all_on_4_vs_all_on_6",
        "anchor": "korotko",
        "aspect": "comparison",
        "alias_decision": alias_decision,
    }


def _comparison_service_overview_alias_row() -> dict:
    row = _catalog_overview_row()
    row["source_kind"] = "alias"
    row["aspect"] = "comparison"
    row["alias_decision"] = "exact"
    return row


def test_is_catalog_service_overview_positive() -> None:
    assert is_catalog_service_overview(_catalog_overview_row()) is True


def test_is_catalog_service_overview_negative_faq() -> None:
    row = _catalog_overview_row()
    row["doc_id"] = "implantation__faq__pain"
    row["ref"] = "implantation__faq__pain.md#korotko"
    assert is_catalog_service_overview(row) is False


def test_is_compact_service_overview_section_not_overview() -> None:
    assert is_compact_service_overview(_duration_service_section_row()) is False


def test_is_compact_service_overview_korotko() -> None:
    assert is_compact_service_overview(_duration_service_overview_row()) is True


def test_strong_facet_duration_faq_alias() -> None:
    assert is_strong_facet_candidate(
        _duration_faq_row(),
        facet_aspect="duration",
        min_facet_score=0.72,
    )


def test_strong_facet_duration_service_section() -> None:
    assert is_strong_facet_candidate(
        _duration_service_section_row(),
        facet_aspect="duration",
        min_facet_score=0.72,
    )


def test_strong_facet_duration_service_overview_not_strong() -> None:
    assert not is_strong_facet_candidate(
        _duration_service_overview_row(),
        facet_aspect="duration",
        min_facet_score=0.72,
    )


def test_strong_facet_pain_service_section_not_strong() -> None:
    row = _duration_service_section_row()
    row["aspect"] = "pain"
    assert not is_strong_facet_candidate(
        row,
        facet_aspect="pain",
        min_facet_score=0.72,
    )


def test_strong_facet_comparison_doc_alias() -> None:
    assert is_strong_facet_candidate(
        _comparison_alias_row(),
        facet_aspect="comparison",
        min_facet_score=0.72,
    )


def test_strong_facet_comparison_service_overview_not_strong() -> None:
    assert not is_strong_facet_candidate(
        _comparison_service_overview_alias_row(),
        facet_aspect="comparison",
        min_facet_score=0.72,
    )


def test_filter_suppresses_catalog_when_comparison_alias() -> None:
    compact = [_catalog_all_on_4_row(), _comparison_alias_row()]
    kept, rejected, tel = filter_compact_for_facet_arbitration(
        compact,
        primary_aspect="comparison",
        q="All-on-4 или All-on-6 что выбрать?",
    )
    assert tel["facet_arbitration_applied"] is True
    assert len(rejected) == 1
    assert kept[0]["doc_id"] == "comparison__all_on_4_vs_all_on_6"


def test_filter_keeps_catalog_when_only_service_overview_as_comparison_aspect() -> None:
    compact = [_catalog_all_on_4_row(), _comparison_service_overview_alias_row()]
    kept, rejected, tel = filter_compact_for_facet_arbitration(
        compact,
        primary_aspect="comparison",
        q="классическая имплантация",
    )
    assert tel["facet_arbitration_skipped"] == "no_strong_facet_candidate"
    assert len(rejected) == 0
    assert len(kept) == 2


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


def test_filter_suppresses_catalog_when_duration_faq() -> None:
    compact = [_catalog_overview_row(), _duration_faq_row()]
    kept, rejected, tel = filter_compact_for_facet_arbitration(
        compact,
        primary_aspect="duration",
        q="Сколько длится имплантация?",
    )
    assert tel["facet_arbitration_applied"] is True
    assert len(rejected) == 1
    assert kept[0]["doc_id"] == "implantation__faq__duration"


def test_filter_suppresses_catalog_when_duration_service_section() -> None:
    compact = [_catalog_overview_row(), _duration_service_section_row()]
    kept, rejected, tel = filter_compact_for_facet_arbitration(
        compact,
        primary_aspect="duration",
        q="Когда поставят коронку после импланта?",
    )
    assert tel["facet_arbitration_applied"] is True
    assert len(rejected) == 1
    assert kept[0]["doc_id"] == "implantation__service__temporary_teeth"


def test_filter_keeps_catalog_when_only_duration_service_overview() -> None:
    compact = [_catalog_overview_row(), _duration_service_overview_row()]
    kept, rejected, tel = filter_compact_for_facet_arbitration(
        compact,
        primary_aspect="duration",
        q="временные зубы на имплантах",
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


def test_decide_content_route_duration_picks_faq_not_catalog() -> None:
    """Golden #3: duration faq must beat catalog service overview."""
    q = "Сколько длится имплантация?"
    cands = collect_content_candidates(q=q, sid="unit_duration_arb", client_id="demo")
    result = decide_content_route(
        q=q,
        sid="unit_duration_arb",
        client_id="demo",
        candidates=cands,
    )
    assert result.selected_doc_id == "implantation__faq__duration"
    assert result.selected_doc_id != "implantation__service__classic"


def test_decide_content_route_duration_facet_suppresses_catalog() -> None:
    """Golden #4: when catalog overview is in pool, duration facet drops it."""
    q = "Сколько по времени ставят один имплант?"
    cands = collect_content_candidates(q=q, sid="unit_duration_arb4", client_id="demo")
    compact = build_compact_content_candidates(cands, client_id="demo")
    assert any(r.get("source_kind") == "catalog" for r in compact), "catalog expected in compact"
    result = decide_content_route(
        q=q,
        sid="unit_duration_arb4",
        client_id="demo",
        candidates=cands,
    )
    assert result.debug_meta.get("facet_arbitration_applied") is True
    assert result.selected_doc_id == "implantation__faq__duration"


def test_decide_content_route_pain_still_works_with_duration_enabled() -> None:
    """Risk r17 / smoke #16: pain path unchanged after duration facet scope."""
    q = "Больно ли ставить имплант?"
    result = decide_content_route(
        q=q,
        sid="unit_pain_after_duration",
        client_id="demo",
        candidates=collect_content_candidates(
            q=q, sid="unit_pain_after_duration", client_id="demo"
        ),
    )
    assert result.selected_doc_id == "implantation__faq__pain"
    assert result.debug_meta.get("facet_arbitration_applied") is True


def test_decide_content_route_comparison_suppresses_catalog() -> None:
    """All-on-4 vs All-on-6: comparison doc must win over catalog service overview."""
    q = "All-on-4 или All-on-6 что выбрать?"
    cands = collect_content_candidates(q=q, sid="unit_cmp_arb", client_id="demo")
    compact = build_compact_content_candidates(cands, client_id="demo")
    assert any(r.get("source_kind") == "catalog" for r in compact)
    result = decide_content_route(
        q=q,
        sid="unit_cmp_arb",
        client_id="demo",
        candidates=cands,
    )
    assert result.debug_meta.get("facet_arbitration_applied") is True
    assert result.selected_doc_id == "comparison__all_on_4_vs_all_on_6"


def test_decide_content_route_r14_not_comparison_facet() -> None:
    """Risk r14: bone graft question must not misfire comparison facet."""
    q = "Можно поставить импланты без костной пластики?"
    result = decide_content_route(
        q=q,
        sid="unit_r14_cmp",
        client_id="demo",
        candidates=collect_content_candidates(q=q, sid="unit_r14_cmp", client_id="demo"),
    )
    assert result.debug_meta.get("facet_arbitration_primary_aspect") != "comparison"
    assert result.selected_doc_id in (
        "implantation__info__bone_graft",
        "comparison__bone_graft_vs_all_on_4",
        "implantation__service__zygomatic_implants",
        "implantation__service__pterygoid_implants",
    )
