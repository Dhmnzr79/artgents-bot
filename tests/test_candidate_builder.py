from __future__ import annotations

import pytest

from contracts.decision_frame import (
    DecisionFrame,
    DecisionFrameConfidence,
)
from core.candidate_builder import (
    MetadataRetrievalContext,
    apply_metadata_candidate_boosts,
    cap_alias_score_vs_semantic,
    effective_scope_topic_for_retrieval,
    metadata_context_from_decision,
)


def _frame(**kwargs) -> DecisionFrame:
    base = dict(
        route_intent="content",
        service_topic="implantation",
        service_id=None,
        query_mode="comparison",
        confidence=DecisionFrameConfidence(
            intent=0.9, topic=0.85, service=0.0, query_mode=0.8
        ),
        needs_clarification=False,
    )
    base.update(kwargs)
    return DecisionFrame(**base)


def test_comparison_disables_hard_scope() -> None:
    ctx = MetadataRetrievalContext(query_mode="comparison", service_topic="implantation")
    assert effective_scope_topic_for_retrieval("implantation", ctx) is None


def test_comparison_boost_ranks_comparison_doc() -> None:
    cands = [
        {"doc_type": "faq", "topic": "implantation", "_score": 0.75, "file": "a.md"},
        {"doc_type": "comparison", "topic": "implantation", "_score": 0.72, "file": "b.md"},
    ]
    ctx = MetadataRetrievalContext(query_mode="comparison", service_topic="implantation", service_topic_confidence=0.9)
    out, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="demo", corpus=cands
    )
    assert tel["comparison_prefer"] is True
    assert out[0]["doc_type"] == "comparison"


def test_comparison_fallback_when_no_comparison_docs() -> None:
    cands = [{"doc_type": "faq", "topic": "implantation", "_score": 0.8, "file": "a.md"}]
    ctx = MetadataRetrievalContext(
        query_mode="comparison",
        service_topic="implantation",
        service_topic_confidence=0.9,
    )
    _, tel = apply_metadata_candidate_boosts(cands, ctx=ctx, client_id="cesi", corpus=cands)
    assert tel["fallback_used"] is True
    assert tel.get("comparison_prefer") is False


def test_comparison_no_boost_when_only_wrong_topic_comparison_in_corpus() -> None:
    """demo has implant comparison only; orthodontics query must not boost it."""
    corpus = [
        {"doc_type": "comparison", "topic": "implantation", "_score": 0.9, "file": "cmp.md"},
    ]
    cands = [
        {"doc_type": "comparison", "topic": "implantation", "_score": 0.85, "file": "cmp.md"},
        {"doc_type": "service", "topic": "orthodontics", "_score": 0.80, "file": "ortho.md"},
    ]
    ctx = MetadataRetrievalContext(
        query_mode="comparison",
        service_topic="orthodontics",
        service_topic_confidence=0.9,
    )
    out, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="demo", corpus=corpus
    )
    assert tel["fallback_used"] is True
    assert tel.get("comparison_prefer") is False
    assert tel.get("comparison_miss_excluded") is True
    assert out[0]["topic"] == "orthodontics"
    assert not any(ch.get("doc_type") == "comparison" for ch in out)


def test_comparison_miss_excludes_wrong_topic_comparison_nikadent_like() -> None:
    """implant vs bridge on client without implant comparison — prosthetics comparison must not win."""
    corpus = [
        {"doc_type": "comparison", "topic": "prosthetics", "_score": 0.76, "file": "bugel.md"},
        {"doc_type": "faq", "topic": "implantation", "_score": 0.68, "file": "faq.md"},
        {"doc_type": "service", "topic": "implantation", "_score": 0.65, "file": "svc.md"},
    ]
    cands = list(corpus)
    ctx = MetadataRetrievalContext(
        query_mode="comparison",
        service_topic="implantation",
        service_topic_confidence=0.9,
    )
    out, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="nikadent", corpus=corpus
    )
    assert tel["fallback_used"] is True
    assert tel.get("comparison_miss_excluded") is True
    assert not any(ch.get("doc_type") == "comparison" for ch in out)
    assert out[0]["topic"] == "implantation"


def test_filter_alias_leader_on_comparison_miss() -> None:
    from core.candidate_builder import filter_alias_leader_on_comparison_miss

    bugel = {"doc_type": "comparison", "topic": "prosthetics", "file": "bugel.md"}
    ctx = MetadataRetrievalContext(
        query_mode="comparison",
        service_topic="implantation",
        service_topic_confidence=0.9,
    )
    corpus = [bugel, {"doc_type": "faq", "topic": "implantation", "file": "faq.md"}]
    leader, rejected = filter_alias_leader_on_comparison_miss(
        bugel, ctx=ctx, client_id="nikadent", corpus=corpus
    )
    assert rejected is True
    assert leader is None


def test_filter_alias_leader_keeps_comparison_on_hit() -> None:
    from core.candidate_builder import filter_alias_leader_on_comparison_miss

    cmp_doc = {"doc_type": "comparison", "topic": "implantation", "file": "cmp.md"}
    ctx = MetadataRetrievalContext(
        query_mode="comparison",
        service_topic="implantation",
        service_topic_confidence=0.9,
    )
    leader, rejected = filter_alias_leader_on_comparison_miss(
        cmp_doc, ctx=ctx, client_id="demo", corpus=[cmp_doc]
    )
    assert rejected is False
    assert leader is cmp_doc


def test_filter_alias_leader_on_topic_mismatch_embed_medium() -> None:
    from core.candidate_builder import filter_alias_leader_on_topic_mismatch

    chunk = {"doc_type": "service", "topic": "prosthetics", "file": "prost.md"}
    ctx = MetadataRetrievalContext(
        query_mode="specific",
        service_topic="implantation",
        service_topic_confidence=0.9,
    )
    leader, rejected = filter_alias_leader_on_topic_mismatch(
        chunk, ctx=ctx, alias_diag={"alias_decision": "embed_medium"}
    )
    assert rejected is True
    assert leader is None


def test_filter_alias_leader_on_topic_exact_exempt() -> None:
    from core.candidate_builder import filter_alias_leader_on_topic_mismatch

    chunk = {"doc_type": "service", "topic": "prosthetics", "file": "prost.md"}
    ctx = MetadataRetrievalContext(
        query_mode="specific",
        service_topic="implantation",
        service_topic_confidence=0.9,
    )
    leader, rejected = filter_alias_leader_on_topic_mismatch(
        chunk, ctx=ctx, alias_diag={"alias_decision": "exact"}
    )
    assert rejected is False
    assert leader is chunk


def test_filter_alias_leader_on_topic_skips_when_low_confidence() -> None:
    from core.candidate_builder import filter_alias_leader_on_topic_mismatch

    chunk = {"doc_type": "service", "topic": "prosthetics", "file": "prost.md"}
    ctx = MetadataRetrievalContext(
        query_mode="specific",
        service_topic="implantation",
        service_topic_confidence=0.4,
    )
    leader, rejected = filter_alias_leader_on_topic_mismatch(
        chunk, ctx=ctx, alias_diag={"alias_decision": "embed_medium"}
    )
    assert rejected is False
    assert leader is chunk


def test_resolve_alias_for_turn_applies_topic_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.candidate_builder import MetadataRetrievalContext, resolve_alias_for_turn

    wrong = {"doc_type": "service", "topic": "prosthetics", "file": "prost.md"}

    def _fake_leader(q: str, *, client_id: str | None = None):
        return wrong, 0.74, {"alias_decision": "embed_medium", "alias_similarity": 0.74}

    monkeypatch.setattr("retriever.corpus_alias_leader", _fake_leader)
    ctx = MetadataRetrievalContext(
        query_mode="specific",
        service_topic="implantation",
        service_topic_confidence=0.85,
    )
    leader, score, tel = resolve_alias_for_turn(
        "тест", ctx=ctx, client_id="demo", top_semantic_score=0.65
    )
    assert leader is None
    assert score == 0.0
    assert tel.get("alias_topic_guard_rejected") is True


def test_cap_alias_score_vs_semantic() -> None:
    capped, was = cap_alias_score_vs_semantic(0.95, 0.70)
    assert was is True
    assert capped <= 0.70 + 0.12 + 1e-6


def test_metadata_context_from_decision_frame() -> None:
    ctx = metadata_context_from_decision(
        _frame(service_topic="prosthetics", service_id="classic", confidence=DecisionFrameConfidence(
            intent=0.9, topic=0.85, service=0.88, query_mode=0.8
        ))
    )
    assert ctx is not None
    assert ctx.query_mode == "comparison"
    assert ctx.service_topic == "prosthetics"
    assert ctx.service_topic_confidence == 0.85
    assert ctx.service_id == "classic"
    assert ctx.service_id_confidence == 0.88


def test_service_id_match_boost_ranks_matching_subtopic() -> None:
    cands = [
        {
            "doc_type": "service",
            "topic": "implantation",
            "subtopic": "all_on_4",
            "_score": 0.74,
            "file": "implantation__service__all_on_4.md",
        },
        {
            "doc_type": "service",
            "topic": "implantation",
            "subtopic": "classic",
            "_score": 0.70,
            "file": "implantation__service__classic.md",
        },
    ]
    ctx = MetadataRetrievalContext(
        query_mode="specific",
        service_topic="implantation",
        service_topic_confidence=0.9,
        service_id="classic",
        service_id_confidence=0.85,
    )
    out, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="demo", corpus=cands
    )
    assert tel.get("metadata_service_id_match") is True
    assert out[0]["subtopic"] == "classic"


def test_service_id_match_boost_from_doc_id_pattern() -> None:
    cands = [
        {
            "doc_type": "service",
            "topic": "implantation",
            "_score": 0.74,
            "doc_id": "implantation__service__all_on_4",
            "file": "implantation__service__all_on_4.md",
        },
        {
            "doc_type": "service",
            "topic": "implantation",
            "_score": 0.70,
            "doc_id": "implantation__service__classic",
            "file": "implantation__service__classic.md",
        },
    ]
    ctx = MetadataRetrievalContext(
        query_mode="specific",
        service_topic="implantation",
        service_topic_confidence=0.9,
        service_id="classic",
        service_id_confidence=0.85,
    )
    out, _tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="demo", corpus=cands
    )
    assert out[0]["doc_id"] == "implantation__service__classic"


def test_service_id_boost_skipped_when_low_confidence() -> None:
    cands = [
        {
            "doc_type": "service",
            "topic": "implantation",
            "subtopic": "all_on_4",
            "_score": 0.74,
            "file": "a.md",
        },
        {
            "doc_type": "service",
            "topic": "implantation",
            "subtopic": "classic",
            "_score": 0.70,
            "file": "b.md",
        },
    ]
    ctx = MetadataRetrievalContext(
        query_mode="specific",
        service_topic="implantation",
        service_topic_confidence=0.9,
        service_id="classic",
        service_id_confidence=0.5,
    )
    out, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="demo", corpus=cands
    )
    assert tel.get("metadata_service_id_match") is not True
    assert out[0]["subtopic"] == "all_on_4"


def test_metadata_topic_soft_filter_drops_off_topic_service_only() -> None:
    cands = [
        {
            "doc_type": "service",
            "topic": "prosthetics",
            "_score": 0.82,
            "file": "prost.md",
        },
        {
            "doc_type": "faq",
            "topic": "implantation",
            "_score": 0.70,
            "file": "faq.md",
        },
    ]
    ctx = MetadataRetrievalContext(
        query_mode="specific",
        service_topic="implantation",
        service_topic_confidence=0.9,
    )
    out, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="demo", corpus=cands
    )
    assert tel.get("metadata_topic_soft_filter") is True
    assert tel.get("metadata_topic_excluded_count") == 1
    assert len(out) == 1
    assert out[0]["topic"] == "implantation"


def test_metadata_topic_soft_filter_keeps_off_topic_info_docs() -> None:
    cands = [
        {
            "doc_type": "info",
            "topic": "clinic",
            "_score": 0.78,
            "file": "clinic__info__warranty.md",
        },
        {
            "doc_type": "info",
            "topic": "implantation",
            "_score": 0.80,
            "file": "implantation__info__implant_systems.md",
        },
    ]
    ctx = MetadataRetrievalContext(
        query_mode="specific",
        service_topic="implantation",
        service_topic_confidence=0.9,
    )
    out, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="demo", corpus=cands
    )
    assert tel.get("metadata_topic_soft_filter") is not True
    assert len(out) == 2


def test_metadata_topic_soft_filter_fail_open_when_only_off_topic() -> None:
    cands = [
        {
            "doc_type": "service",
            "topic": "prosthetics",
            "_score": 0.82,
            "file": "prost.md",
        },
    ]
    ctx = MetadataRetrievalContext(
        query_mode="specific",
        service_topic="implantation",
        service_topic_confidence=0.9,
    )
    out, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="demo", corpus=cands
    )
    assert tel.get("metadata_topic_soft_filter") is not True
    assert len(out) == 1
    assert out[0]["topic"] == "prosthetics"


def test_metadata_topic_soft_filter_skipped_for_comparison_mode() -> None:
    corpus = [
        {"doc_type": "comparison", "topic": "implantation", "file": "cmp.md"},
    ]
    cands = [
        {"doc_type": "comparison", "topic": "implantation", "_score": 0.72, "file": "cmp.md"},
        {"doc_type": "service", "topic": "orthodontics", "_score": 0.80, "file": "ortho.md"},
    ]
    ctx = MetadataRetrievalContext(
        query_mode="comparison",
        service_topic="orthodontics",
        service_topic_confidence=0.9,
    )
    out, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="demo", corpus=corpus
    )
    assert tel.get("metadata_topic_soft_filter") is not True
    assert any(ch.get("topic") == "implantation" for ch in out) or len(out) >= 1


def test_metadata_context_from_decision_dict() -> None:
    ctx = metadata_context_from_decision(
        {"query_mode": "overview", "service_topic": "implantation", "confidence": {"topic": 0.7}}
    )
    assert ctx is not None
    assert ctx.query_mode == "overview"
    assert ctx.service_topic_confidence == 0.7


def test_service_topic_match_boost_ranks_same_topic() -> None:
    cands = [
        {"doc_type": "faq", "topic": "implantation", "_score": 0.70, "file": "faq.md"},
        {"doc_type": "faq", "topic": "prosthetics", "_score": 0.72, "file": "prost.md"},
    ]
    ctx = MetadataRetrievalContext(
        query_mode="specific",
        service_topic="implantation",
        service_topic_confidence=0.9,
    )
    out, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="demo", corpus=cands
    )
    assert tel["metadata_boost_applied"] is True
    assert out[0]["topic"] == "implantation"


def test_aspect_match_boost_ranks_matching_facet() -> None:
    cands = [
        {
            "doc_type": "faq",
            "topic": "implantation",
            "aspect": "overview",
            "_score": 0.70,
            "file": "methods.md",
        },
        {
            "doc_type": "info",
            "topic": "implantation",
            "aspect": "stages",
            "_score": 0.72,
            "file": "steps.md",
        },
    ]
    ctx = MetadataRetrievalContext(
        query_mode="overview",
        service_topic="implantation",
        service_topic_confidence=0.9,
        query_aspects=("overview",),
    )
    out, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="demo", corpus=cands
    )
    assert tel["metadata_boost_applied"] is True
    assert out[0]["aspect"] == "overview"


def test_low_topic_confidence_skips_comparison_boost() -> None:
    corpus = [
        {"doc_type": "comparison", "topic": "implantation", "file": "cmp.md"},
    ]
    cands = [
        {"doc_type": "comparison", "topic": "implantation", "_score": 0.72, "file": "cmp.md"},
        {"doc_type": "faq", "topic": "implantation", "_score": 0.75, "file": "faq.md"},
    ]
    ctx = MetadataRetrievalContext(
        query_mode="comparison",
        service_topic="implantation",
        service_topic_confidence=0.2,
    )
    out, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="demo", corpus=corpus
    )
    assert tel["fallback_used"] is True
    assert not any(ch.get("doc_type") == "comparison" for ch in out)
    assert out[0]["doc_type"] == "faq"


def test_corpus_comparison_filtered_by_client_id() -> None:
    corpus = [
        {
            "client_id": "demo",
            "doc_type": "comparison",
            "topic": "implantation",
            "file": "demo_cmp.md",
        },
    ]
    cands = [{"doc_type": "faq", "topic": "implantation", "_score": 0.8, "file": "faq.md"}]
    ctx = MetadataRetrievalContext(
        query_mode="comparison",
        service_topic="implantation",
        service_topic_confidence=0.9,
    )
    _, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="cesi", corpus=corpus
    )
    assert tel["comparison_docs_for_topic"] is False
    assert tel["fallback_used"] is True


def test_price_lookup_pricing_boost_ranks_pricing_over_service() -> None:
    cands = [
        {
            "doc_type": "service",
            "topic": "implantation",
            "_score": 0.80,
            "file": "implantation__service__classic.md",
        },
        {
            "doc_type": "pricing",
            "topic": "implantation",
            "_score": 0.72,
            "file": "implantation__pricing__implants.md",
        },
    ]
    ctx = MetadataRetrievalContext(
        query_mode="specific",
        service_topic="implantation",
        service_topic_confidence=0.9,
        route_intent="price_lookup",
    )
    out, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="cesi", corpus=cands
    )
    assert tel["price_lookup_prefer"] is True
    assert out[0]["doc_type"] == "pricing"


def test_price_lookup_excludes_service_when_pricing_present() -> None:
    cands = [
        {
            "doc_type": "service",
            "topic": "implantation",
            "_score": 0.80,
            "file": "implantation__service__classic.md",
        },
        {
            "doc_type": "pricing",
            "topic": "implantation",
            "_score": 0.72,
            "file": "implantation__pricing__implants.md",
        },
        {
            "doc_type": "faq",
            "topic": "implantation",
            "_score": 0.70,
            "file": "implantation__faq__cost.md",
        },
    ]
    ctx = MetadataRetrievalContext(
        query_mode="specific",
        service_topic="implantation",
        service_topic_confidence=0.9,
        route_intent="price_lookup",
    )
    out, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="cesi", corpus=cands
    )
    assert tel.get("price_service_excluded") is True
    assert tel.get("price_service_excluded_count") == 1
    assert not any(ch.get("doc_type") == "service" for ch in out)
    assert any(ch.get("doc_type") == "faq" for ch in out)


def test_price_lookup_keeps_service_when_no_pricing_in_pool() -> None:
    cands = [
        {
            "doc_type": "service",
            "topic": "implantation",
            "_score": 0.80,
            "file": "implantation__service__classic.md",
        },
        {
            "doc_type": "faq",
            "topic": "implantation",
            "_score": 0.70,
            "file": "implantation__faq__cost.md",
        },
    ]
    ctx = MetadataRetrievalContext(
        query_mode="specific",
        service_topic="implantation",
        service_topic_confidence=0.9,
        route_intent="price_lookup",
    )
    out, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="demo", corpus=cands
    )
    assert tel.get("price_service_excluded") is not True
    assert any(ch.get("doc_type") == "service" for ch in out)


def test_content_route_intent_skips_price_lookup_filter() -> None:
    cands = [
        {
            "doc_type": "service",
            "topic": "implantation",
            "_score": 0.80,
            "file": "implantation__service__classic.md",
        },
        {
            "doc_type": "pricing",
            "topic": "implantation",
            "_score": 0.72,
            "file": "implantation__pricing__implants.md",
        },
    ]
    ctx = MetadataRetrievalContext(
        query_mode="specific",
        service_topic="implantation",
        service_topic_confidence=0.9,
        route_intent="content",
        query_aspects=("price",),
    )
    out, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="cesi", corpus=cands
    )
    assert tel.get("price_lookup_prefer") is not True
    assert tel.get("price_service_excluded") is not True
    assert any(ch.get("doc_type") == "service" for ch in out)
