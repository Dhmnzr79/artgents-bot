"""Tests for chunk aspect inference (Retrieval 2.0 spike)."""
from __future__ import annotations

from core.aspect_metadata import infer_chunk_aspect


def test_infer_aspect_from_subtopic_duration() -> None:
    assert (
        infer_chunk_aspect(
            doc_id="implantation__faq__duration",
            doc_type="faq",
            subtopic="duration",
        )
        == "duration"
    )


def test_infer_aspect_comparison_doc() -> None:
    assert (
        infer_chunk_aspect(
            doc_id="comparison__classic_vs_one_stage",
            doc_type="comparison",
            subtopic="classic_vs_one_stage",
        )
        == "comparison"
    )


def test_frontmatter_aspect_override() -> None:
    assert (
        infer_chunk_aspect(
            doc_id="implantation__service__classic",
            doc_type="service",
            subtopic="classic",
            frontmatter_aspect="included",
        )
        == "included"
    )
