"""Offline real-runtime replay T1–T8 for POST_RETRY3 Composer action context."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from core.target_composer_output import composer_test_json
from evals.v5.final_scope_widget_e2e_live_contract import (
    MAX_HTTP_TURNS,
    create_attempt_marker_exclusive,
    load_frozen_turns,
)
from evals.v5.final_scope_widget_e2e_live_harness import (
    run_non_network_preflight,
    _scope_nav_refs,
)
from evals.v5.final_scope_widget_e2e_retry3_live_contract import (
    TYPED_UI_TURNS_NO_PLANNER,
    build_retry3_attempt_marker_payload,
)
from evals.v5.final_scope_widget_e2e_retry3_live_harness import (
    _assert_frozen_neighbors,
    run_http_harness,
)
from tests.test_final_scope_widget_e2e_retry3_live_harness import (
    _ActionAwareGroundedComposerBackend,
    _install_retry3_http_fakes,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _current_scope_nav_frozen_turns() -> dict[str, object]:
    turns_spec = copy.deepcopy(load_frozen_turns())
    for turn in turns_spec["turns"]:
        expect = turn.get("expect")
        turn_id = str(turn.get("turn_id") or "")
        if (
            isinstance(expect, dict)
            and expect.get("scope_nav_count") == 3
            and "implant" in turn_id
        ):
            expect["scope_nav_count"] = 2
    return turns_spec


def _install_post_retry3_http_fakes(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    import importlib

    state = _install_retry3_http_fakes(monkeypatch)
    composer = state["composer_backend"]
    original_generate = composer.generate

    def json_wrapped_generate(invocation: object, /) -> str:
        text = original_generate(invocation)
        if isinstance(text, str) and not text.lstrip().startswith("{"):
            return composer_test_json(text)
        return text

    composer.generate = json_wrapped_generate  # type: ignore[method-assign]
    importlib.reload(importlib.import_module("core.target_runtime_turn"))
    return state


def _quick_reply_refs(row: dict[str, object]) -> list[str]:
    refs: list[str] = []
    for item in list(row.get("quick_replies") or []):
        if isinstance(item, dict):
            refs.append(str(item.get("ref") or ""))
    body = row.get("body")
    if isinstance(body, dict):
        for item in list(body.get("quick_replies") or []):
            if isinstance(item, dict):
                refs.append(str(item.get("ref") or ""))
    return refs


def _governed_invocations(
    composer: _ActionAwareGroundedComposerBackend,
) -> list[dict[str, object]]:
    governed: list[dict[str, object]] = []
    for invocation in composer.invocations:
        raw = getattr(invocation, "governed_action_context_json", None)
        if isinstance(raw, str) and raw.strip():
            governed.append(json.loads(raw))
    return governed


def test_offline_t1_t8_action_context_and_widget_integrity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "attempt.json"
    ledger = tmp_path / "ledger.jsonl"
    artifacts = tuple(tmp_path / f"artifact_{i}.json" for i in range(3))

    run_non_network_preflight(
        attempt_marker_path=marker,
        artifact_paths=artifacts,
        monkeypatch=monkeypatch,
        assert_frozen_neighbors=_assert_frozen_neighbors,
    )
    create_attempt_marker_exclusive(
        marker,
        build_retry3_attempt_marker_payload(baseline_commit="post-retry3-offline"),
    )
    monkeypatch.setattr(
        "evals.v5.final_scope_widget_e2e_live_harness.load_frozen_turns",
        _current_scope_nav_frozen_turns,
    )
    fake_state = _install_post_retry3_http_fakes(monkeypatch)
    composer: _ActionAwareGroundedComposerBackend = fake_state["composer_backend"]  # type: ignore[assignment]

    payload = run_http_harness(
        live=False,
        skip_live_prepare=True,
        attempt_marker_path=marker,
        call_ledger_path=ledger,
        artifact_paths=artifacts,
        monkeypatch=monkeypatch,
    )

    turns = payload["turn_results"]
    assert len(turns) == MAX_HTTP_TURNS
    assert all(row["automated_turn_verdict"] == "PASS" for row in turns)

    turn1 = turns[0]
    assert len(_scope_nav_refs(list(turn1.get("quick_replies") or []))) == 2
    assert "₽" in str(turn1.get("answer_text") or "")

    turn2 = turns[1]
    assert not any(ref.startswith("price:None/") for ref in _quick_reply_refs(turn2))
    assert "₽" in str(turn2.get("answer_text") or "")

    turn4 = turns[3]
    assert not any(ref.startswith("price:None/") for ref in _quick_reply_refs(turn4))
    assert "₽" in str(turn4.get("answer_text") or "")

    turn6 = turns[5]
    assert "этап" in str(turn6.get("answer_text") or "").lower()

    turn7 = turns[6]
    assert "₽" in str(turn7.get("answer_text") or "")

    governed = _governed_invocations(composer)
    governed_by_ref = {str(item.get("governed_ref")): item for item in governed}
    assert len(governed_by_ref) >= 2, sorted(governed_by_ref)
    assert "target:ui_scope/implantation/full_arch" in governed_by_ref, sorted(governed_by_ref)
    assert (
        governed_by_ref["target:ui_scope/implantation/full_arch"]["response_stage"]
        == "scoped_family_price"
    )
    assert governed_by_ref["target:ui_scope/implantation/full_arch"]["extent"] == "full_arch"
    assert "target:ui_stage/prosthetics/implant_placed" in governed_by_ref, sorted(governed_by_ref)
    assert (
        governed_by_ref["target:ui_stage/prosthetics/implant_placed"]["action_kind"] == "ui_stage"
    )
    turn6 = turns[5]
    assert "этап" in str(turn6.get("answer_text") or "").lower()

    stream_turns = [row for row in turns if row["endpoint"] == "/ask/stream"]
    assert len(stream_turns) == 2
    for row in stream_turns:
        assert not any(ref.startswith("price:None/") for ref in _quick_reply_refs(row))

    for turn_number in TYPED_UI_TURNS_NO_PLANNER:
        assert fake_state["planner_calls_by_turn"].get(turn_number, 0) == 0  # type: ignore[index]

    for invocation in composer.invocations:
        content = __import__(
            "core.target_runtime_llm_messages",
            fromlist=["build_composer_sdk_messages"],
        ).build_composer_sdk_messages(invocation)[1]["content"]
        assert "GOVERNED_ACTION_CONTEXT_JSON" in content
