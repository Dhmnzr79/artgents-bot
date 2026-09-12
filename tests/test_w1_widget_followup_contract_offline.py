from __future__ import annotations

import json
import subprocess
import types
from pathlib import Path

import pytest

from contracts.ask_orchestration import AskOrchestrationResult
from contracts.target_response_spec import TargetResponseSpec
from contracts.target_turn_frame_dispatch import (
    TargetTurnFrameBoundTerminalResponse,
    TargetTurnFrameTerminalDispatch,
)
from contracts.turn_frame import TurnFrame
from core.target_response_followup_materializer import TargetPriceFollowup
from core.target_response_followup_policy import TargetResponseFollowupSelection
from core.target_response_verifier import TargetVerifiedComposedResponse
from core.target_runtime_followup_nav import build_target_unknown_ref_clarify_payload
from core.target_runtime_widget import (
    materialize_boundary_uncertain_payload,
    materialize_s41_terminal_payload,
    materialize_target_error_payload,
    materialize_verified_widget_payload,
)
from orchestration.planner_turn import PlannerTurnOutcome
from policy import apply_ui_source_policy, infer_ui_source_family
from ux_builder import normalize_policy_payload


def test_target_price_payload_uses_single_quick_replies_channel() -> None:
    followups = TargetResponseFollowupSelection(
        source="price",
        content=(),
        price=(
            TargetPriceFollowup(
                id="stages",
                label="Оплата по этапам",
                ref="price:all_on_4/stages",
                action="stages",
                source_offer_ids=("all_on_4.jaw.impro",),
            ),
            TargetPriceFollowup(
                id="included",
                label="Что входит",
                ref="price:all_on_4/included",
                action="included",
                source_offer_ids=("all_on_4.jaw.impro",),
            ),
        ),
    )
    spec = TargetResponseSpec(
        response_mode="answer",
        service_id="all_on_4",
        tone_key="commercial_warm",
        allowed_topics=("implantation",),
        required_components=("price",),
        followup_source="price",
    )
    verified = TargetVerifiedComposedResponse(
        text="Цена All-on-4 от 318 000 рублей.",
        spec=spec,
        selected_followups=followups,
        selected_cta_key=None,
    )
    frame = build_turn_frame_for_widget()
    widget = materialize_verified_widget_payload(
        context=types.SimpleNamespace(client_id="demo"),
        sid="sid-w1",
        verified=verified,
        turn_frame=frame,
    )
    payload = widget.payload
    quick = payload["quick_replies"]
    meta = payload["meta"]
    assert len(quick) == 2
    assert "followups" not in meta
    assert meta["followup_count"] == 2
    assert meta["ui_source_family"] == "price_navigation"
    assert meta["attribution_kind"] == "content"
    apply_ui_source_policy(payload)
    normalize_policy_payload(payload)
    assert infer_ui_source_family(payload) == "price_navigation"
    assert len(payload["quick_replies"]) == 2
    refs = [item["ref"] for item in payload["quick_replies"]]
    assert len(refs) == len(set(refs))


def build_turn_frame_for_widget() -> TurnFrame:
    from core.turn_frame_from_raw import build_turn_frame_from_raw

    return build_turn_frame_from_raw(
        {
            "route": "content",
            "topic": "implantation",
            "topic_confidence": 0.9,
            "service_id": "all_on_4",
            "aspects": ["price"],
            "primary_aspect": "price",
        },
        allowed_topics=frozenset({"implantation"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )


def test_merge_followup_controls_dedup_behavior() -> None:
    script = Path("static/widget/followup_controls.js")
    node_code = f"""
import {{ mergeFollowupControls }} from {json.dumps(script.as_posix())};
const items = mergeFollowupControls(
  [{{ label: "Оплата по этапам", ref: "price:all_on_4/stages" }}],
  [
    {{ label: "Оплата по этапам", ref: "price:all_on_4/stages" }},
    {{ label: "Что входит", ref: "price:all_on_4/included" }},
  ],
);
console.log(JSON.stringify(items));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", node_code],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"node unavailable: {result.stderr}")
    items = json.loads(result.stdout.strip())
    assert len(items) == 2
    assert items[0]["ref"] == "price:all_on_4/stages"
    assert items[1]["ref"] == "price:all_on_4/included"


def test_terminal_and_error_payloads_use_plain_attribution() -> None:
    terminal = TargetTurnFrameBoundTerminalResponse(
        kind="terminal",
        dispatch=TargetTurnFrameTerminalDispatch(
            kind="terminal",
            terminal_mode="defer",
            spec=TargetResponseSpec(
                response_mode="defer",
                tone_key="commercial_warm",
                allowed_topics=("implantation",),
                required_components=(),
            ),
        ),
    )
    defer_payload = materialize_s41_terminal_payload(
        client_id="demo",
        sid="sid",
        terminal=terminal,
    ).payload
    assert defer_payload["meta"]["attribution_kind"] == "plain"
    assert defer_payload["meta"]["ui_source_family"] == "guided_fallback"
    assert defer_payload["meta"].get("followups") is None

    uncertain = materialize_boundary_uncertain_payload(client_id="demo", sid="sid").payload
    assert uncertain["meta"]["attribution_kind"] == "plain"

    error = materialize_target_error_payload(
        client_id="demo",
        sid="sid",
        error_code="target_verifier_numeric_ungrounded",
    ).payload
    assert error["meta"]["attribution_kind"] == "plain"
    assert error["meta"]["service_route"] == "target_fullcontext_verifier_blocked"

    unknown = build_target_unknown_ref_clarify_payload(client_id="demo", sid="sid")
    assert unknown["meta"]["attribution_kind"] == "plain"
