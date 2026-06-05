"""Service-scoped short follow-up helpers."""

from __future__ import annotations

from core.service_followup import (
    candidate_belongs_to_service,
    filter_compact_for_service_followup,
    is_generic_faq_candidate,
    is_short_attribute_followup,
    rewrite_overlaps_attribute_synonyms,
)


def test_short_attribute_followup_detects_duration_pronoun():
    assert is_short_attribute_followup("А долго это?")
    assert is_short_attribute_followup("А по времени это сколько?")
    assert not is_short_attribute_followup(
        "чем отличается имплантация от мостовидного протеза подробно"
    )


def test_duration_synonym_overlap():
    assert rewrite_overlaps_attribute_synonyms(
        "А долго это?",
        "All-on-6 длительность процедуры",
    )


def test_filter_removes_generic_faq_when_same_service_present():
    compact = [
        {
            "ref": "implantation__service__all_on_6.md#korotko",
            "doc_type": "catalog_md",
            "service_id": "all_on_6",
            "score": 0.88,
        },
        {
            "ref": "implantation__faq__duration.md#korotko",
            "doc_type": "faq",
            "service_id": None,
            "score": 0.45,
        },
        {
            "ref": "implantation__pricing__all_on_6.md#korotko",
            "doc_type": "pricing",
            "service_id": "all_on_6",
            "score": 0.33,
        },
    ]
    kept, rejected = filter_compact_for_service_followup(compact, service_id="all_on_6")
    assert len(kept) == 1
    assert kept[0]["ref"].startswith("implantation__service__all_on_6")
    assert len(rejected) == 2
    assert any(is_generic_faq_candidate(r) for r in rejected)


def test_candidate_belongs_to_service_by_doc_id():
    row = {"ref": "implantation__service__classic.md#korotko", "service_id": None}
    assert candidate_belongs_to_service(row, "classic")
    assert candidate_belongs_to_service(row, "all-on-6") is False
