from __future__ import annotations

from unittest.mock import patch

import pytest


def test_finalize_ask_applies_lead_paused_overlay() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    sid = "overlay_sid"
    with app.test_request_context("/"):
        from flask import request

        from orchestration.finalize_turn import finalize_ask

        request.ctx = {"client_id": "demo"}
        st = {
            "session_turn_count": 1,
            "lead_intent": "paused",
            "lead_resume_step": "collecting_name",
            "lead_paused_answer_count": 0,
        }
        with patch("orchestration.finalize_turn.mem_get", return_value=st), patch(
            "orchestration.finalize_turn.record_last_bot_payload"
        ), patch("orchestration.finalize_turn.emit_bot_event"), patch(
            "orchestration.finalize_turn.apply_lead_paused_overlay",
            side_effect=lambda payload, _sid, _cid: {
                **payload,
                "quick_replies": [{"label": "Продолжить запись", "ref": "lead:resume"}],
                "meta": {**(payload.get("meta") or {}), "lead_paused": True},
            },
        ) as overlay:
            out = finalize_ask(
                {"answer": "Ответ по теме.", "meta": {}},
                sid,
                "вопрос",
                route="price_lookup",
                client_id="demo",
            )
    overlay.assert_called_once()
    assert any(qr.get("ref") == "lead:resume" for qr in (out.get("quick_replies") or []))
    assert (out.get("meta") or {}).get("lead_paused") is True
