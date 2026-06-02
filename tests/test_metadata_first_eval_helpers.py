from __future__ import annotations

from core.candidate_builder import MetadataRetrievalContext, apply_metadata_candidate_boosts
from evals.v5.smoke_case_runner import doc_type_from_doc_id, expand_cases, validate_smoke_case


def test_doc_type_from_doc_id() -> None:
    assert doc_type_from_doc_id("implantation__faq__pain") == "faq"
    assert doc_type_from_doc_id("comparison__implant_vs_bridge") == "comparison"
    assert doc_type_from_doc_id("clinic__info__contacts") == "contacts"
    assert doc_type_from_doc_id("implantation__service__classic") == "service"


def test_expand_cases_clients() -> None:
    rows = [{"id": "mf_x", "clients": ["demo", "cesi"], "question": "q"}]
    out = expand_cases(rows)
    assert len(out) == 2
    assert {r["id"] for r in out} == {"mf_x@demo", "mf_x@cesi"}


def test_comparison_fallback_telemetry_cesi() -> None:
    """comparison miss on client without comparison md → fallback_used in builder telemetry."""
    corpus: list[dict] = [
        {"doc_type": "faq", "topic": "implantation", "file": "implantation__faq__cost.md"},
    ]
    cands = [
        {"doc_type": "faq", "topic": "implantation", "_score": 0.8, "file": "implantation__faq__cost.md"},
    ]
    ctx = MetadataRetrievalContext(
        query_mode="comparison",
        service_topic="implantation",
        service_topic_confidence=0.9,
    )
    _, tel = apply_metadata_candidate_boosts(
        cands, ctx=ctx, client_id="cesi", corpus=corpus
    )
    assert tel["fallback_used"] is True
    assert tel["comparison_docs_for_topic"] is False


def test_validate_expected_fallback_used_via_metadata_first_hook() -> None:
    row = {
        "id": "t_fallback",
        "expected_fallback_used": True,
    }
    resp = {
        "answer": "имплант или мост зависит от ситуации",
        "meta": {
            "file": "implantation__faq__cost.md",
            "metadata_first": {"fallback_used": True, "selected_doc_type": "faq"},
        },
    }
    result = validate_smoke_case(
        row=row,
        resp=resp,
        answer=str(resp["answer"]),
        route="retrieval_chunk",
    )
    assert result is None


def test_validate_expected_doc_type_prefers_metadata_first_selected() -> None:
    row = {
        "id": "t_doc_type",
        "expected_doc_type": "comparison",
    }
    resp = {
        "answer": "сравнение",
        "meta": {
            "file": "implantation__faq__cost.md",
            "metadata_first": {"selected_doc_type": "comparison"},
        },
    }
    result = validate_smoke_case(
        row=row,
        resp=resp,
        answer=str(resp["answer"]),
        route="retrieval_chunk",
    )
    assert result is None
