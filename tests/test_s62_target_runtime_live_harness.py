"""Offline tests for S62 target runtime live harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.v5.fullcontext_response_eval_contract import HarnessConfigError
from evals.v5.s62_target_runtime_live_contract import (
    MAX_PROVIDER_CALLS,
    build_attempt_marker_payload,
    create_attempt_marker_exclusive,
    load_frozen_turns,
)
from evals.v5.s62_target_runtime_live_provider_audit import (
    install_provider_audit,
    set_current_turn,
    uninstall_provider_audit,
)
from evals.v5.s62_target_runtime_live_harness import (
    _pick_price_followup,
    prepare_live_run,
)


def test_frozen_turns_has_four_exact_turns() -> None:
    spec = load_frozen_turns()
    assert len(spec["turns"]) == 4
    assert spec["turns"][0]["request"]["q"] == "Что такое All-on-4?"
    assert spec["turns"][3]["request"]["q"] == "Можно ли ставить импланты при волчанке?"


def test_attempt_marker_exclusive_create(tmp_path: Path) -> None:
    marker = tmp_path / "attempt.json"
    create_attempt_marker_exclusive(marker, build_attempt_marker_payload(baseline_commit="abc"))
    with pytest.raises(Exception):
        create_attempt_marker_exclusive(marker, build_attempt_marker_payload(baseline_commit="abc"))


def test_provider_audit_blocks_call_21(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "attempt.json"
    ledger = tmp_path / "ledger.jsonl"
    create_attempt_marker_exclusive(marker, build_attempt_marker_payload(baseline_commit="x"))
    import llm
    from evals.v5 import s62_target_runtime_live_provider_audit as audit_module

    def fake_chat(*, model: str, **kwargs: object):
        class _Msg:
            content = "ok"

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]
            usage = None

        return _Resp()

    monkeypatch.setattr(llm, "chat_completions_create", fake_chat)
    install_provider_audit(attempt_marker_path=marker, call_ledger_path=ledger)
    monkeypatch.setattr(audit_module, "_infer_provider_role", lambda: "planner")

    roles = [
        "ingress",
        "planner",
        "medical_boundary",
        "composer",
        "semantic_verifier",
    ]
    for index in range(MAX_PROVIDER_CALLS):
        turn = index // len(roles) + 1
        role = roles[index % len(roles)]
        set_current_turn(turn)
        monkeypatch.setattr(
            audit_module,
            "_infer_provider_role",
            lambda captured_role=role: captured_role,
        )
        llm.chat_completions_create(model="qwen3.6-flash", messages=[])
    set_current_turn(4)
    monkeypatch.setattr(audit_module, "_infer_provider_role", lambda: "ingress")
    with pytest.raises(HarnessConfigError, match="provider call budget exceeded"):
        llm.chat_completions_create(model="qwen3.6-flash", messages=[])
    uninstall_provider_audit()


def test_pick_price_followup_prefers_price_ref() -> None:
    picked = _pick_price_followup(
        [
            {"label": "Подробнее", "ref": "kb:foo.md#bar"},
            {"label": "Стоимость", "ref": "price:all_on_4/stages"},
        ]
    )
    assert picked is not None
    assert picked["ref"] == "price:all_on_4/stages"


def test_prepare_live_run_creates_marker(tmp_path: Path) -> None:
    marker = tmp_path / "attempt.json"
    prepare_live_run(attempt_marker_path=marker, artifact_paths=())
    assert marker.exists()
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["status"] == "attempt_started"
