from __future__ import annotations

from unittest.mock import patch

import pytest


def test_finalize_ask_attaches_metadata_first_when_e2e_env(monkeypatch) -> None:
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        from orchestration.finalize_turn import finalize_ask

        request.ctx = {
            "fallback_used": True,
            "comparison_docs_for_topic": False,
            "query_mode": "comparison",
            "service_topic": "implantation",
            "selected_doc_type": "service",
        }
        with patch("orchestration.finalize_turn.mem_get", return_value={"session_turn_count": 1}), patch(
            "orchestration.finalize_turn.record_last_bot_payload"
        ), patch("orchestration.finalize_turn.emit_bot_event"):
            out = finalize_ask(
                {"answer": "ответ", "meta": {"file": "implantation__faq__pain.md"}},
                "test_sid",
                "вопрос",
                route="retrieval_chunk",
                turn_meta={"interaction": "user_message", "question_len": 6, "preview": "вопрос"},
            )
    mf = out["meta"].get("metadata_first")
    assert isinstance(mf, dict)
    assert mf.get("fallback_used") is True
    assert mf.get("comparison_docs_for_topic") is False
    assert mf.get("selected_doc_type") == "service"


def test_finalize_ask_omits_metadata_first_without_e2e_env(monkeypatch) -> None:
    monkeypatch.delenv("E2E_USE_TEST_CLIENT", raising=False)
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        from orchestration.finalize_turn import finalize_ask

        request.ctx = {"fallback_used": True}
        with patch("orchestration.finalize_turn.mem_get", return_value={"session_turn_count": 1}), patch(
            "orchestration.finalize_turn.record_last_bot_payload"
        ), patch("orchestration.finalize_turn.emit_bot_event"):
            out = finalize_ask({"answer": "x", "meta": {}}, "sid", "q", route="retrieval_chunk")
    assert "metadata_first" not in (out.get("meta") or {})
