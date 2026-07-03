from __future__ import annotations

from unittest.mock import patch

import pytest

from core.dialog_focus_observability import slim_dialog_focus_payload


def test_slim_dialog_focus_payload_keeps_safe_fields() -> None:
    raw = {
        "focus_service_id": "classic",
        "focus_label": "Классическая имплантация",
        "focus_topic": "implantation",
        "attribute": "general",
        "explicit_topic_change": False,
        "resolved_service_id": "classic",
        "source": "llm_gray",
        "used_llm": True,
        "confidence": 0.86,
        "reason": "llm_gray",
        "query_rewrite": "подойдет ли классическая имплантация пациенту",
    }

    slim = slim_dialog_focus_payload(raw)

    assert slim["focus_service_id"] == "classic"
    assert slim["attribute"] == "general"
    assert slim["query_rewrite"] == "подойдет ли классическая имплантация пациенту"
    assert "focus_label" not in slim


def test_finalize_ask_attaches_dialog_focus_when_e2e_env(monkeypatch) -> None:
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        from orchestration.finalize_turn import finalize_ask

        request.ctx = {
            "dialog_focus_decision": {
                "focus_service_id": "classic",
                "focus_topic": "implantation",
                "attribute": "general",
                "explicit_topic_change": False,
                "resolved_service_id": "classic",
                "source": "llm_gray",
                "used_llm": True,
                "confidence": 0.86,
                "reason": "llm_gray",
                "query_rewrite": "подойдет ли классическая имплантация пациенту",
            }
        }
        with patch("orchestration.finalize_turn.mem_get", return_value={"session_turn_count": 1}), patch(
            "orchestration.finalize_turn.record_last_bot_payload"
        ), patch("orchestration.finalize_turn.emit_bot_event"):
            out = finalize_ask({"answer": "ответ", "meta": {}}, "sid", "вопрос")

    df = out["meta"].get("dialog_focus")
    assert isinstance(df, dict)
    assert df["focus_service_id"] == "classic"
    assert df["attribute"] == "general"
    assert df["used_llm"] is True
