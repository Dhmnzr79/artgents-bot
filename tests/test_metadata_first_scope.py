from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.candidate_builder import (
    MetadataRetrievalContext,
    apply_metadata_candidate_boosts,
)
from orchestration.helpers import apply_content_retrieval_scope_ctx


def test_soft_scope_disables_hard_topic_filter() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        with patch("orchestration.helpers.THRESHOLDS") as thr:
            thr.metadata_first.soft_scope_enabled = True
            thr.catalog_match.containment_min = 0.88
            thr.alias.scope_guard_min = 0.85
            with patch(
                "orchestration.helpers.compute_retrieval_scope_with_conflict_guard",
                return_value=("implantation", "none"),
            ):
                eff = apply_content_retrieval_scope_ctx(
                    "implantation", "тест", "demo"
                )
        assert eff is None
        assert request.ctx["retrieval_scope_guard_reason"] == "metadata_first_soft"
        assert request.ctx["retrieval_scope_topic_candidate"] == "implantation"


def test_comparison_wrong_topic_in_pool_gets_no_comparison_boost() -> None:
    corpus = [{"doc_type": "comparison", "topic": "implantation", "file": "c.md"}]
    cands = [
        {"doc_type": "comparison", "topic": "implantation", "_score": 0.9, "file": "c.md"},
        {"doc_type": "service", "topic": "orthodontics", "_score": 0.7, "file": "o.md"},
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
    assert not any(ch.get("_metadata_boost") for ch in out if ch.get("doc_type") == "comparison")
