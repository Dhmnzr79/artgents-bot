from __future__ import annotations

import pytest

from core.metadata_first_observability import (
    merge_retrieval_debug_meta,
    metadata_first_response_meta,
    metadata_first_turn_details,
    record_decision_frame_ctx,
    record_selection_metadata,
    retrieval_pool_turn_details,
    should_expose_metadata_first_in_response,
    RETRIEVAL_POOL_CTX_KEYS,
)


def test_record_decision_frame_ctx_from_dict() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        record_decision_frame_ctx(
            {
                "route_intent": "content",
                "query_mode": "comparison",
                "service_topic": "implantation",
            }
        )
        assert request.ctx["route_intent"] == "content"
        assert request.ctx["query_mode"] == "comparison"
        assert request.ctx["service_topic"] == "implantation"


def test_record_decision_frame_ctx_unknown_topic_becomes_none() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        record_decision_frame_ctx({"service_topic": "unknown", "query_mode": "overview"})
        assert request.ctx["service_topic"] is None


def test_merge_retrieval_debug_meta_and_turn_details() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {"route_intent": "content"}
        merge_retrieval_debug_meta(
            {
                "candidate_pool_before": 8,
                "candidate_pool_after": 8,
                "fallback_used": True,
                "comparison_docs_for_topic": False,
                "alias_hit": True,
                "alias_boost": 0.64,
                "ignored_key": "skip",
            }
        )
        details = metadata_first_turn_details()
        assert details["candidate_pool_before"] == 8
        assert details["fallback_used"] is True
        assert details["comparison_docs_for_topic"] is False
        assert details["alias_hit"] is True
        assert details["alias_boost"] == 0.64
        assert "ignored_key" not in details


def test_record_selection_metadata_doc_type_and_topic() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        record_selection_metadata(
            selected_doc_id="comparison__implant_vs_bridge",
            selected_chunk={
                "doc_type": "comparison",
                "topic": "implantation",
                "file": "comparison__implant_vs_bridge.md",
            },
            selected_route="retrieval_chunk",
        )
        assert request.ctx["selected_doc_id"] == "comparison__implant_vs_bridge"
        assert request.ctx["selected_doc_type"] == "comparison"
        assert request.ctx["selected_topic"] == "implantation"
        assert request.ctx["selected_route"] == "retrieval_chunk"


def test_should_expose_metadata_first_gated_by_env(monkeypatch) -> None:
    monkeypatch.delenv("E2E_USE_TEST_CLIENT", raising=False)
    assert should_expose_metadata_first_in_response() is False
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    assert should_expose_metadata_first_in_response() is True


def test_metadata_first_response_meta_matches_turn_details() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {"fallback_used": True, "selected_doc_type": "comparison"}
        assert metadata_first_response_meta()["fallback_used"] is True
        assert metadata_first_response_meta()["selected_doc_type"] == "comparison"


def test_retrieval_pool_turn_details_slice() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {
            "route_intent": "content",
            "pool_sources": [{"ref": "a.md#korotko", "score": 0.64, "sources": ["semantic", "alias"]}],
            "alias_in_pool": True,
            "alias_pool_merged": True,
            "selected_source": "unified_pool",
            "pool_winner_ref": "a.md#korotko",
            "rerank_trigger_reason": "strong_alias_in_pool",
            "rerank_applied": False,
            "alias_channel_suppressed": True,
            "ignored": "skip",
        }
        pool = retrieval_pool_turn_details()
        assert set(pool.keys()).issubset(set(RETRIEVAL_POOL_CTX_KEYS))
        assert pool["alias_in_pool"] is True
        assert pool["selected_source"] == "unified_pool"
        assert pool["rerank_trigger_reason"] == "strong_alias_in_pool"
        assert "ignored" not in pool

        details = metadata_first_turn_details()
        assert details["route_intent"] == "content"
        assert isinstance(details.get("retrieval_pool"), dict)
        assert details["retrieval_pool"]["pool_winner_ref"] == "a.md#korotko"
        assert "ignored" not in details


def test_patient_situation_clarify_telemetry_in_turn_details() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        from core.patient_situation import detect_patient_situation, record_patient_situation_ctx

        request.ctx = {}
        record_patient_situation_ctx(detect_patient_situation("пустое место сбоку"))
        details = metadata_first_turn_details()
        assert details["patient_situation_kind"] == "unknown"
        assert details["patient_situation_should_clarify"] is True
        assert details["patient_situation_clarify_question"]
        assert details["patient_situation_clarification_reason"] == "vague_location"
