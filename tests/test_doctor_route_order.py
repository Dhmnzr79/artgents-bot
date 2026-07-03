"""Doctor route must win over composer overlay (FULLCONTEXT roadmap 3.1c)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from flask import Flask

from contracts.source_route_result import SourceRouteResult
from session import mem_reset

_app = Flask(__name__)


@pytest.fixture
def sid():
    s = f"doctor-route-{uuid.uuid4().hex[:8]}"
    mem_reset(s)
    return s


def test_doctor_source_runs_before_composer(sid: str) -> None:
    from orchestration.ask_turn import orchestrate_routing_after_resolver

    doctor_result = type(
        "R",
        (),
        {
            "kind": "chunk",
            "chunk_route": "doctors_list",
            "chosen_chunk": {"file": "doctors.md"},
        },
    )()
    composer_called = {"value": False}

    def _composer(**_kw):
        composer_called["value"] = True
        return None

    sr = SourceRouteResult(
        source="doctor",
        service_id=None,
        ref="doctors__doctor__overview.md#korotko",
        match_score=0.95,
        match_method="doctors_lookup",
        payload={"doctor": {"routing": "overview", "matching_doctors_total": 2}},
    )
    situation = type("S", (), {"kind": "unknown", "confidence": 0.0})()

    with _app.test_request_context():
        from flask import request

        request.ctx = {}
        with patch("orchestration.ask_turn.route_source", return_value=sr):
            with patch("orchestration.ask_turn.build_answer_plan") as plan_mock:
                plan_mock.return_value = type(
                    "P",
                    (),
                    {
                        "aspects": ["overview"],
                        "service_id": None,
                        "model_dump": lambda self: {},
                    },
                )()
                with patch("orchestration.ask_turn.publish_answer_plan"):
                    with patch("orchestration.ask_turn.build_and_publish_answer_packet"):
                        with patch(
                            "orchestration.ask_turn.resolve_patient_situation_for_turn",
                            return_value=(situation, {}),
                        ):
                            with patch("orchestration.ask_turn.record_patient_situation_ctx"):
                                with patch("orchestration.ask_turn.persist_patient_situation_after_turn"):
                                    with patch("orchestration.ask_turn.record_dialog_focus_ctx"):
                                        with patch(
                                            "orchestration.ask_turn.try_a3_doctor_route",
                                            return_value=doctor_result,
                                        ):
                                            with patch(
                                                "orchestration.ask_turn.try_composer_overlay",
                                                side_effect=_composer,
                                            ):
                                                result = orchestrate_routing_after_resolver(
                                                    q="Кто у вас занимается имплантацией?",
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

    assert composer_called["value"] is False
    assert result is doctor_result
