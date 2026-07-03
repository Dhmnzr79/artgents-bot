"""Contacts routing — deterministic ref, no embed search."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from flask import Flask

from session import mem_reset

_app = Flask(__name__)


@pytest.fixture
def sid():
    s = f"contacts-route-{uuid.uuid4().hex[:8]}"
    mem_reset(s)
    return s


def test_contacts_route_uses_direct_chunk_ref(sid: str) -> None:
    from orchestration.ask_turn import orchestrate_routing_after_resolver

    chunk = {
        "file": "clinic__info__contacts.md",
        "h3_id": "korotko",
        "text": "Адрес: Москва",
        "doc_type": "contacts",
    }
    situation = type("S", (), {"kind": "unknown", "confidence": 0.0})()

    with _app.test_request_context():
        from flask import request

        request.ctx = {}
        with patch("orchestration.ask_turn.get_chunk_by_ref", return_value=chunk) as ref_mock:
            with patch("orchestration.ask_turn.resolve_patient_situation_for_turn", return_value=(situation, {})):
                with patch("orchestration.ask_turn.record_patient_situation_ctx"):
                    with patch("orchestration.ask_turn.persist_patient_situation_after_turn"):
                        with patch("orchestration.ask_turn.record_dialog_focus_ctx"):
                            result = orchestrate_routing_after_resolver(
                                q="А где вы находитесь?",
                                sid=sid,
                                client_id="demo",
                                intent="content",
                                decision=None,
                                scope_topic_candidate=None,
                                resolver_bypassed_env=False,
                                data={},
                                client_txt=lambda _c: {},
                                service_payload=lambda **_k: {},
                                lead_flow_from_result=lambda **_k: None,
                                apply_response_policy=lambda p, **_k: p,
                            )

    ref_mock.assert_called_once()
    assert ref_mock.call_args.kwargs.get("client_id") == "demo"
    assert "contacts.md#korotko" in str(ref_mock.call_args.args[0])
    assert result.kind == "chunk"
    assert result.chunk_route == "contacts_chunk"
    assert result.chosen_chunk == chunk
