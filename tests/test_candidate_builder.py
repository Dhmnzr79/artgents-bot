from __future__ import annotations

from contracts.decision_frame import (
    DecisionFrame,
    DecisionFrameConfidence,
)
from core.candidate_builder import (
    MetadataRetrievalContext,
    apply_metadata_candidate_boosts,
    cap_alias_score_vs_semantic,
    effective_scope_topic_for_retrieval,
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
    assert out[0]["topic"] == "orthodontics"


def test_cap_alias_score_vs_semantic() -> None:
    capped, was = cap_alias_score_vs_semantic(0.95, 0.70)
    assert was is True
    assert capped <= 0.70 + 0.12 + 1e-6
