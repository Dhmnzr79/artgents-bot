"""Offline tests for S63 target runtime live harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.v5.fullcontext_response_eval_contract import HarnessConfigError
from evals.v5.s63_target_runtime_live_contract import (
    MAX_PROVIDER_CALLS,
    assert_frozen_s62_live_artifacts_unchanged,
    build_attempt_marker_payload,
    create_attempt_marker_exclusive,
    ledger_entries_balanced,
    load_frozen_turns,
)
from evals.v5.s63_target_runtime_live_harness import (
    evaluate_summary,
    evaluate_turn_gates,
    pick_displayed_followup,
    prepare_live_run,
)
from evals.v5.s63_target_runtime_live_provider_audit import (
    ProviderAuditState,
    install_provider_audit,
    reset_audit_state,
    set_current_turn,
    uninstall_provider_audit,
)


def test_frozen_turns_has_three_exact_turns() -> None:
    spec = load_frozen_turns()
    assert len(spec["turns"]) == 3
    assert spec["turns"][0]["request"]["q"] == "Что такое All-on-4?"
    assert spec["turns"][1]["request_kind"] == "followup_ref_from_turn_1"
    assert spec["turns"][2]["request"]["q"] == "А кто делает?"


def test_frozen_s62_artifacts_unchanged() -> None:
    assert_frozen_s62_live_artifacts_unchanged()


def test_attempt_marker_exclusive_create(tmp_path: Path) -> None:
    marker = tmp_path / "attempt.json"
    create_attempt_marker_exclusive(marker, build_attempt_marker_payload(baseline_commit="abc"))
    with pytest.raises(Exception):
        create_attempt_marker_exclusive(marker, build_attempt_marker_payload(baseline_commit="abc"))


def test_pick_displayed_followup_first_visible() -> None:
    picked = pick_displayed_followup(
        [{"label": "Кому подходит All-on-4", "ref": "implantation__service__all_on_4.md#x"}]
    )
    assert picked == {
        "ref": "implantation__service__all_on_4.md#x",
        "label": "Кому подходит All-on-4",
    }


def test_evaluate_summary_automated_fail_on_missing_doctors() -> None:
    turn_results = [
        {
            "turn_id": "s63_turn_01_all_on_4_info",
            "meta": {"service_route": "target_fullcontext_materialized", "cta_key": "plan"},
            "cta": {"text": "Составить план лечения"},
            "quick_replies": [{"ref": "r1", "label": "l1"}],
            "gates": {"flags": {"http_completed": True, "target_answer_path": True}},
        },
        {
            "turn_id": "s63_turn_02_followup_ref",
            "followup_ref_used": True,
            "meta": {"service_route": "target_fullcontext_materialized"},
            "gates": {"flags": {"http_completed": True, "target_answer_path": True}},
        },
        {
            "turn_id": "s63_turn_03_doctors",
            "meta": {"service_route": "target_fullcontext_terminal_defer"},
            "session_before": {"last_service_id": "all_on_4"},
            "gates": {"flags": {"http_completed": True, "target_answer_path": True}},
        },
    ]
    audit = ProviderAuditState()
    audit.total_started = 15
    audit.fullcontext_build_count = 1
    audit.role_totals.update(
        {
            "ingress": 3,
            "planner": 3,
            "medical_boundary": 3,
            "composer": 3,
            "semantic_verifier": 3,
        }
    )
    summary = evaluate_summary(turn_results, audit, ledger_balanced=True)
    assert summary["automated_verdict"] == "AUTOMATED_FAIL"
    assert summary["technical"]["doctors_materialized"] is False


def test_evaluate_summary_automated_pass_shape() -> None:
    turn_results = [
        {
            "turn_id": "s63_turn_01_all_on_4_info",
            "meta": {"service_route": "target_fullcontext_materialized", "cta_key": "plan"},
            "cta": {"text": "Составить план лечения"},
            "quick_replies": [{"ref": "r1", "label": "l1"}],
            "gates": {"flags": {"http_completed": True, "target_answer_path": True}},
        },
        {
            "turn_id": "s63_turn_02_followup_ref",
            "followup_ref_used": True,
            "meta": {"service_route": "target_fullcontext_materialized"},
            "gates": {"flags": {"http_completed": True, "target_answer_path": True}},
        },
        {
            "turn_id": "s63_turn_03_doctors",
            "meta": {"service_route": "target_fullcontext_materialized"},
            "session_before": {"last_service_id": "all_on_4"},
            "gates": {"flags": {"http_completed": True, "target_answer_path": True}},
        },
    ]
    audit = ProviderAuditState()
    audit.total_started = 15
    audit.fullcontext_build_count = 1
    audit.role_totals.update(
        {
            "ingress": 3,
            "planner": 3,
            "medical_boundary": 3,
            "composer": 3,
            "semantic_verifier": 3,
        }
    )
    summary = evaluate_summary(turn_results, audit, ledger_balanced=True)
    assert summary["automated_verdict"] == "AUTOMATED_PASS"
    assert summary["final_verdict"] == "PENDING_MANUAL_REVIEW"


def test_turn_gates_fail_without_cta_widget() -> None:
    gates = evaluate_turn_gates(
        {
            "turn_id": "s63_turn_01_all_on_4_info",
            "status_code": 200,
            "meta": {"service_route": "target_fullcontext_materialized", "cta_key": "plan"},
            "cta": None,
            "quick_replies": [{"ref": "r", "label": "l"}],
        }
    )
    assert gates["automated_turn_verdict"] == "FAIL"
    assert gates["flags"]["cta_widget_present"] is False


def test_ledger_entries_balanced(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        "\n".join(
            [
                json.dumps({"sequence": 1, "phase": "call_start"}),
                json.dumps({"sequence": 1, "phase": "call_complete"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert ledger_entries_balanced(ledger) is True


def test_provider_audit_blocks_call_16(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "attempt.json"
    ledger = tmp_path / "ledger.jsonl"
    reset_audit_state()
    uninstall_provider_audit()
    create_attempt_marker_exclusive(marker, build_attempt_marker_payload(baseline_commit="x"))
    import llm
    from evals.v5 import s63_target_runtime_live_provider_audit as audit_module

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


def test_prepare_live_run_creates_marker(tmp_path: Path) -> None:
    marker = tmp_path / "attempt.json"
    prepare_live_run(attempt_marker_path=marker, artifact_paths=())
    assert marker.exists()
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["status"] == "attempt_started"
    assert payload["max_provider_calls"] == 15
