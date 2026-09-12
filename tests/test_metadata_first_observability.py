from __future__ import annotations

from unittest.mock import patch

import pytest
from flask import Flask

from contracts.planner_attempt import PlannerAttempt
from contracts.turn_plan import TurnPlan
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
from core.turn_frame_from_raw import build_turn_frame_from_raw
from core.runtime_turn_frame import publish_planner_attempt_frame


def _record_a9_scope(patient_situation: object, *, partial: bool = False):
    from flask import request

    if not hasattr(request, "ctx"):
        request.ctx = {}
    aspects = [] if partial else ["overview"]
    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": aspects,
            "topic": "implantation",
            "topic_confidence": 0.9,
            "patient_situation": patient_situation,
        },
        allowed_topics=frozenset({"implantation"}),
    )
    attempt = PlannerAttempt(
        frame=frame,
        status="partial" if partial else "ok",
    )
    publish_planner_attempt_frame(attempt=attempt)
    return frame


def _record_native_a9_scope(
    patient_scope: object,
    *,
    shadow_status: str = "ok",
    raw_extra: dict | None = None,
):
    from flask import request

    if not hasattr(request, "ctx"):
        request.ctx = {}
    raw = {
        "route": "content",
        "aspects": ["overview"],
        "topic": "implantation",
        "topic_confidence": 0.9,
        "patient_situation": "one_tooth_missing",
        "patient_scope": patient_scope,
    }
    raw.update(raw_extra or {})
    frame = build_turn_frame_from_raw(
        raw,
        allowed_topics=frozenset({"implantation"}),
    )
    attempt = PlannerAttempt(
        frame=frame,
        status=shadow_status,
    )
    publish_planner_attempt_frame(attempt=attempt)
    return frame


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


def test_routing_provenance_gated_in_response_meta(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {
            "fallback_used": True,
            "turn_planner_used": True,
            "source_route_decision": {"source": "none"},
        }
        monkeypatch.delenv("E2E_USE_TEST_CLIENT", raising=False)
        meta = metadata_first_response_meta()
        assert "turn_planner_used" not in meta
        assert "source_route_decision" not in meta
        assert meta.get("fallback_used") is True

        monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
        meta_e2e = metadata_first_response_meta()
        assert meta_e2e.get("turn_planner_used") is True
        assert meta_e2e.get("source_route_decision") == {"source": "none"}


def test_routing_provenance_in_turn_details_for_logs() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {"route_intent": "content", "turn_planner_used": False}
        details = metadata_first_turn_details()
        assert details.get("turn_planner_used") is False
        assert details.get("route_intent") == "content"


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


def test_patient_situation_clarify_telemetry_removed_with_legacy_island() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        details = metadata_first_turn_details()
        for key in (
            "patient_situation_kind",
            "patient_situation_should_clarify",
            "patient_situation_clarify_question",
            "patient_situation_clarification_reason",
        ):
            assert key not in details


def test_turn_frame_shadow_keys_in_turn_details() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {
            "route_intent": "content",
            "turn_frame_shadow_status": "ok",
            "turn_frame_shadow": {"intent": "content", "aspects": ["overview"], "primary_aspect": "overview"},
        }
        details = metadata_first_turn_details()
        assert details["turn_frame_shadow_status"] == "ok"
        assert details["turn_frame_shadow"]["intent"] == "content"
        assert "turn_frame_shadow_reason" not in details


def test_a9_nested_scope_round_trips_through_turn_details_and_response_slice() -> None:
    app = Flask(__name__)
    with app.test_request_context("/"):
        frame = _record_a9_scope("bone_deficit_or_grafting")

        details = metadata_first_turn_details()
        response_slice = metadata_first_response_meta()

        assert details["turn_frame_shadow"] == frame.model_dump()
        assert response_slice["turn_frame_shadow"] == frame.model_dump()
        for payload in (details, response_slice):
            shadow = payload["turn_frame_shadow"]
            assert shadow["patient_scope"]["modifiers"] == ["reported_bone_deficit"]
            assert shadow["field_meta"]["patient_scope"]["modifiers"] == {
                "confidence": 0.0,
                "provenance": "turn_plan.patient_situation.modifiers",
                "status": "valid",
                "error": None,
            }
            assert shadow["field_meta"]["patient_scope"]["extent"]["status"] == "defaulted"


def test_native_a9_composite_round_trips_through_ctx_details_and_e2e_response(
    monkeypatch,
) -> None:
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    native_scope = {
        "extent": "full_arch",
        "jaw": "upper",
        "stage": "implant_placed",
        "modifiers": ["reported_bone_deficit"],
    }
    app = Flask(__name__)
    with app.test_request_context("/"):
        from flask import request
        from orchestration.finalize_turn import finalize_ask

        frame = _record_native_a9_scope(native_scope)
        details = metadata_first_turn_details()
        response_slice = metadata_first_response_meta()
        with patch("orchestration.finalize_turn.mem_get", return_value={"session_turn_count": 1}), patch(
            "orchestration.finalize_turn.record_last_bot_payload"
        ), patch("orchestration.finalize_turn.emit_bot_event"):
            out = finalize_ask(
                {"answer": "ответ", "meta": {}},
                "sid",
                "q",
                route="retrieval_chunk",
            )

        assert request.ctx["turn_frame_shadow"] == frame.model_dump()

    for payload in (
        details,
        response_slice,
        out["meta"]["metadata_first"],
    ):
        shadow = payload["turn_frame_shadow"]
        assert shadow == frame.model_dump()
        assert shadow["patient_scope"] == native_scope
        for field_name in ("extent", "jaw", "stage", "modifiers"):
            assert shadow["field_meta"]["patient_scope"][field_name] == {
                "confidence": 0.0,
                "provenance": f"turn_plan.raw.patient_scope.{field_name}",
                "status": "valid",
                "error": None,
            }


def test_turn_frame_shadow_reason_in_turn_details_when_present() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {
            "turn_frame_shadow_status": "not_available",
            "turn_frame_shadow_reason": "turn_plan_missing",
        }
        details = metadata_first_turn_details()
        assert details["turn_frame_shadow_status"] == "not_available"
        assert details["turn_frame_shadow_reason"] == "turn_plan_missing"


def test_turn_frame_shadow_keys_in_response_meta_slice(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {
            "turn_frame_shadow_status": "ok",
            "turn_frame_shadow": {"intent": "price_lookup", "aspects": ["price"], "primary_aspect": "price"},
        }
        monkeypatch.delenv("E2E_USE_TEST_CLIENT", raising=False)
        meta = metadata_first_response_meta()
        assert meta["turn_frame_shadow_status"] == "ok"
        assert meta["turn_frame_shadow"]["intent"] == "price_lookup"


def test_finalize_ask_includes_turn_frame_shadow_with_e2e_env(monkeypatch) -> None:
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        from orchestration.finalize_turn import finalize_ask

        request.ctx = {
            "turn_frame_shadow_status": "ok",
            "turn_frame_shadow": {
                "intent": "content",
                "aspects": ["overview"],
                "primary_aspect": "overview",
            },
        }
        with patch("orchestration.finalize_turn.mem_get", return_value={"session_turn_count": 1}), patch(
            "orchestration.finalize_turn.record_last_bot_payload"
        ), patch("orchestration.finalize_turn.emit_bot_event"):
            out = finalize_ask({"answer": "ответ", "meta": {}}, "sid", "q", route="retrieval_chunk")
    mf = out["meta"].get("metadata_first")
    assert isinstance(mf, dict)
    assert mf.get("turn_frame_shadow_status") == "ok"
    assert mf.get("turn_frame_shadow", {}).get("intent") == "content"


def test_finalize_ask_e2e_preserves_real_a9_nested_scope(monkeypatch) -> None:
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    app = Flask(__name__)
    with app.test_request_context("/"):
        from orchestration.finalize_turn import finalize_ask

        frame = _record_a9_scope("one_tooth_missing")
        with patch("orchestration.finalize_turn.mem_get", return_value={"session_turn_count": 1}), patch(
            "orchestration.finalize_turn.record_last_bot_payload"
        ), patch("orchestration.finalize_turn.emit_bot_event"):
            out = finalize_ask(
                {"answer": "ответ", "meta": {}},
                "sid",
                "q",
                route="retrieval_chunk",
            )

    shadow = out["meta"]["metadata_first"]["turn_frame_shadow"]
    assert shadow == frame.model_dump()
    assert shadow["patient_scope"]["extent"] == "one_tooth"
    assert shadow["field_meta"]["patient_scope"]["extent"] == {
        "confidence": 0.0,
        "provenance": "turn_plan.patient_situation.extent",
        "status": "valid",
        "error": None,
    }


def test_a9_partial_nested_scope_and_unrelated_error_survive_e2e(monkeypatch) -> None:
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    app = Flask(__name__)
    with app.test_request_context("/"):
        from orchestration.finalize_turn import finalize_ask

        frame = _record_a9_scope("one_tooth_missing", partial=True)
        with patch("orchestration.finalize_turn.mem_get", return_value={"session_turn_count": 1}), patch(
            "orchestration.finalize_turn.record_last_bot_payload"
        ), patch("orchestration.finalize_turn.emit_bot_event"):
            out = finalize_ask(
                {"answer": "ответ", "meta": {}},
                "sid",
                "q",
                route="retrieval_chunk",
            )

    metadata = out["meta"]["metadata_first"]
    assert metadata["turn_frame_shadow_status"] == "partial"
    shadow = metadata["turn_frame_shadow"]
    assert shadow == frame.model_dump()
    assert shadow["patient_scope"]["extent"] == "one_tooth"
    assert shadow["field_meta"]["patient_scope"]["extent"]["status"] == "valid"
    assert shadow["field_meta"]["aspects"]["error"] == "aspects_empty"


def test_a9_shadow_observability_does_not_leak_malformed_raw_secrets() -> None:
    app = Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        raw = {
            "route": "content",
            "aspects": [],
            "topic": "implantation",
            "topic_confidence": 0.9,
            "patient_situation": {"secret-kind": "secret-value"},
            "question": "secret-question",
            "history": ["secret-history"],
            "exception": "secret-exception",
        }
        frame = build_turn_frame_from_raw(
            raw,
            allowed_topics=frozenset({"implantation"}),
        )
        publish_planner_attempt_frame(
            attempt=PlannerAttempt(
        frame=frame,
                status="partial",
            )
        )
        observed = {
            "ctx": request.ctx,
            "details": metadata_first_turn_details(),
            "response_slice": metadata_first_response_meta(),
        }

    payload = str(observed)
    for secret in (
        "secret-kind",
        "secret-value",
        "secret-question",
        "secret-history",
        "secret-exception",
    ):
        assert secret not in payload


def test_native_a9_partial_scope_preserves_neighbors_without_raw_secret_leak() -> None:
    app = Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        frame = _record_native_a9_scope(
            {
                "extent": "few_teeth",
                "jaw": "lower",
                "stage": "extraction_context",
                "modifiers": [],
                "secret-native-key": "secret-native-value",
            },
            shadow_status="partial",
            raw_extra={
                "question": "secret-question",
                "history": ["secret-history"],
                "exception": "secret-exception",
            },
        )
        observed = {
            "ctx": request.ctx,
            "details": metadata_first_turn_details(),
            "response_slice": metadata_first_response_meta(),
        }

    assert observed["ctx"]["turn_frame_shadow_status"] == "partial"
    shadow = observed["ctx"]["turn_frame_shadow"]
    assert shadow == frame.model_dump()
    assert shadow["patient_scope"] == {
        "extent": "few_teeth",
        "jaw": "lower",
        "stage": "extraction_context",
        "modifiers": [],
    }
    assert shadow["field_meta"]["patient_scope"]["container"]["status"] == "invalid"
    assert (
        shadow["field_meta"]["patient_scope"]["container"]["error"]
        == "patient_scope_extra_field"
    )
    for field_name in ("extent", "jaw", "stage", "modifiers"):
        assert shadow["field_meta"]["patient_scope"][field_name]["status"] == "valid"
    serialized = str(observed)
    for secret in (
        "secret-native-key",
        "secret-native-value",
        "secret-question",
        "secret-history",
        "secret-exception",
    ):
        assert secret not in serialized


def test_finalize_ask_includes_partial_shadow_field_errors_only_in_e2e_meta(monkeypatch) -> None:
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        from orchestration.finalize_turn import finalize_ask

        request.ctx = {
            "turn_frame_shadow_status": "partial",
            "turn_frame_shadow": {
                "intent": "content",
                "topic": "doctors",
                "aspects": [],
                "primary_aspect": None,
                "field_meta": {
                    "topic": {
                        "confidence": 0.95,
                        "provenance": "turn_plan.raw.topic",
                        "status": "valid",
                        "error": None,
                    },
                    "aspects": {
                        "confidence": 0.0,
                        "provenance": "turn_plan.raw.aspects",
                        "status": "invalid",
                        "error": "aspects_empty",
                    },
                },
            },
        }
        with patch("orchestration.finalize_turn.mem_get", return_value={"session_turn_count": 1}), patch(
            "orchestration.finalize_turn.record_last_bot_payload"
        ), patch("orchestration.finalize_turn.emit_bot_event"):
            out = finalize_ask({"answer": "ответ", "meta": {}}, "sid", "q", route="retrieval_chunk")

    mf = out["meta"].get("metadata_first")
    assert mf["turn_frame_shadow_status"] == "partial"
    assert mf["turn_frame_shadow"]["topic"] == "doctors"
    assert mf["turn_frame_shadow"]["field_meta"]["aspects"]["error"] == "aspects_empty"
    assert "question" not in str(mf).lower()
    assert "exception" not in str(mf).lower()


def test_finalize_ask_omits_metadata_first_without_e2e_env(monkeypatch) -> None:
    monkeypatch.delenv("E2E_USE_TEST_CLIENT", raising=False)
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        from orchestration.finalize_turn import finalize_ask

        request.ctx = {
            "turn_frame_shadow_status": "ok",
            "turn_frame_shadow": {"intent": "content", "aspects": ["overview"], "primary_aspect": "overview"},
        }
        with patch("orchestration.finalize_turn.mem_get", return_value={"session_turn_count": 1}), patch(
            "orchestration.finalize_turn.record_last_bot_payload"
        ), patch("orchestration.finalize_turn.emit_bot_event"):
            out = finalize_ask({"answer": "x", "meta": {}}, "sid", "q", route="retrieval_chunk")
    assert "metadata_first" not in (out.get("meta") or {})


def test_finalize_ask_omits_real_a9_nested_scope_without_e2e_env(monkeypatch) -> None:
    monkeypatch.delenv("E2E_USE_TEST_CLIENT", raising=False)
    app = Flask(__name__)
    with app.test_request_context("/"):
        from orchestration.finalize_turn import finalize_ask

        _record_native_a9_scope(
            {
                "extent": "one_tooth",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            }
        )
        with patch("orchestration.finalize_turn.mem_get", return_value={"session_turn_count": 1}), patch(
            "orchestration.finalize_turn.record_last_bot_payload"
        ), patch("orchestration.finalize_turn.emit_bot_event"):
            out = finalize_ask(
                {"answer": "x", "meta": {}},
                "sid",
                "q",
                route="retrieval_chunk",
            )

    assert "metadata_first" not in (out.get("meta") or {})
    assert "patient_scope" not in str(out)
