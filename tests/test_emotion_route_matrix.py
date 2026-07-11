"""Live routing matrix for emotion/fear family (eval-net, full pipeline).

Requires real LLM + E2E_USE_TEST_CLIENT=1 + TURN_PLANNER_ON=1.
Asserts live provenance == ``current`` (baseline freeze). ``target`` is P1 goal only.
"""
from __future__ import annotations

import json
import os
import uuid

import pytest

from evals.v5.smoke_case_runner import (
    extract_routing_provenance,
    here,
    load_json,
    post_ask_json,
    reset_smoke_session,
    validate_routing_provenance,
)


def _emotion_cases() -> list[dict]:
    spec = load_json(here("demo", "emotion.json"))
    cases = spec.get("cases")
    if not isinstance(cases, list):
        pytest.fail("emotion.json: cases must be a non-empty array")
    return [c for c in cases if isinstance(c, dict)]


def _live_pipeline_env() -> bool:
    return (os.getenv("E2E_USE_TEST_CLIENT") or "").strip().lower() in {"1", "true", "yes"}


@pytest.fixture(scope="module")
def _require_live_pipeline() -> None:
    if not _live_pipeline_env():
        pytest.skip("emotion routing matrix requires E2E_USE_TEST_CLIENT=1 (full Flask pipeline)")
    if (os.getenv("TURN_PLANNER_ON") or "1").strip().lower() in {"0", "false", "no"}:
        pytest.skip("emotion routing matrix requires TURN_PLANNER_ON=1")


@pytest.mark.parametrize("case_row", _emotion_cases(), ids=lambda r: str(r.get("id") or "?"))
def test_emotion_routing_matrix_current_baseline(case_row: dict, _require_live_pipeline: None) -> None:
    case_id = str(case_row.get("id") or "").strip()
    question = str(case_row.get("question") or "").strip()
    assert question, f"{case_id}: missing question"

    sid = f"emotion_matrix_{case_id}_{uuid.uuid4().hex[:8]}"
    reset_smoke_session(sid)
    resp = post_ask_json(
        "http://localhost:5000/ask",
        {"q": question, "sid": sid, "client_id": "demo"},
        timeout_sec=float(os.getenv("BOT_TIMEOUT_SEC") or "60"),
    )
    provenance = extract_routing_provenance(resp)
    reason = validate_routing_provenance(row=case_row, provenance=provenance, baseline=True)
    if reason:
        current = case_row.get("current")
        pytest.fail(
            f"{case_id}: {reason}\n"
            f"live provenance: {json.dumps(provenance, ensure_ascii=False)}\n"
            f"documented current: {json.dumps(current, ensure_ascii=False)}"
        )


def test_emotion_matrix_spec_has_current_and_target() -> None:
    for row in _emotion_cases():
        case_id = str(row.get("id") or "").strip()
        current = row.get("current")
        assert isinstance(current, dict), f"{case_id}: missing current (stable route)"
        for field in ("route_intent", "source", "answer_path", "orch_route"):
            assert field in current, f"{case_id}: current missing stable field {field!r}"
        assert isinstance(row.get("target"), dict), f"{case_id}: missing target provenance"
        diag = row.get("current_diagnostic")
        if isinstance(diag, dict):
            assert "turn_planner_used" in diag, f"{case_id}: diagnostic should record turn_planner_used"


def test_emotion_matrix_not_stubbed_route_source() -> None:
    """Guard: matrix must not import route_source with hand-built DecisionFrame."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    for path in (root / "evals" / "v5" / "smoke_case_runner.py", Path(__file__)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "source_routing":
                offenders.append(f"{path.name}: imports source_routing")
            if isinstance(node, ast.ImportFrom) and node.module == "contracts.decision_frame":
                offenders.append(f"{path.name}: imports DecisionFrame stub path")
    assert not offenders, "emotion harness must use full /ask pipeline: " + "; ".join(offenders)
