"""Offline tests for S66 default authority live harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.v5.fullcontext_response_eval_contract import HarnessConfigError
from evals.v5.s66_default_authority_live_contract import (
    DefaultAuthorityEnvError,
    MAX_PROVIDER_CALLS,
    assert_frozen_s62_live_artifacts_unchanged,
    assert_frozen_s63_live_artifacts_unchanged,
    assert_target_fullcontext_env_absent,
    build_attempt_marker_payload,
    create_attempt_marker_exclusive,
    ledger_entries_balanced,
    resolve_default_authority_proof,
)
from evals.v5.s66_default_authority_live_harness import (
    evaluate_summary,
    evaluate_turn_gates,
    prepare_live_run,
)
from evals.v5.s66_default_authority_live_provider_audit import (
    ProviderAuditState,
    install_provider_audit,
    reset_audit_state,
    set_current_turn,
    uninstall_provider_audit,
)


def test_frozen_s62_artifacts_unchanged() -> None:
    assert_frozen_s62_live_artifacts_unchanged()


def test_frozen_s63_artifacts_unchanged() -> None:
    assert_frozen_s63_live_artifacts_unchanged()


def test_env_guard_fails_when_target_flag_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARGET_FULLCONTEXT_DEV", "1")
    with pytest.raises(DefaultAuthorityEnvError):
        assert_target_fullcontext_env_absent()


def test_env_guard_fails_when_kill_switch_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARGET_FULLCONTEXT_DEV", "0")
    with pytest.raises(DefaultAuthorityEnvError):
        assert_target_fullcontext_env_absent()


def test_resolve_default_authority_proof_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TARGET_FULLCONTEXT_DEV", raising=False)
    proof = resolve_default_authority_proof()
    assert proof == {
        "env_present": False,
        "config_default_resolved": True,
        "authority_source": "config_default",
    }


def test_attempt_marker_exclusive_create(tmp_path: Path) -> None:
    marker = tmp_path / "attempt.json"
    proof = {
        "env_present": False,
        "config_default_resolved": True,
        "authority_source": "config_default",
    }
    create_attempt_marker_exclusive(
        marker,
        build_attempt_marker_payload(baseline_commit="abc", authority_proof=proof),
    )
    with pytest.raises(Exception):
        create_attempt_marker_exclusive(
            marker,
            build_attempt_marker_payload(baseline_commit="abc", authority_proof=proof),
        )


def test_evaluate_turn_gates_pass_materialized_with_cta() -> None:
    gates = evaluate_turn_gates(
        {
            "status_code": 200,
            "meta": {
                "service_route": "target_fullcontext_materialized",
                "answer_path": "target_fullcontext",
                "cta_key": "plan",
            },
            "cta": {"text": "Составить план лечения", "action": "lead", "key": "plan"},
            "answer_text": "All-on-4 — это протокол...",
        }
    )
    assert gates["automated_turn_verdict"] == "PASS"
    assert gates["flags"]["cta_authored_match"] is True


def test_evaluate_turn_gates_fail_wrong_cta() -> None:
    gates = evaluate_turn_gates(
        {
            "status_code": 200,
            "meta": {
                "service_route": "target_fullcontext_materialized",
                "answer_path": "target_fullcontext",
                "cta_key": "plan",
            },
            "cta": {"text": "wrong", "action": "lead", "key": "plan"},
            "answer_text": "answer",
        }
    )
    assert gates["automated_turn_verdict"] == "FAIL"


def test_evaluate_summary_automated_pass_shape() -> None:
    turn_result = {
        "meta": {"service_route": "target_fullcontext_materialized"},
        "gates": {
            "flags": {
                "http_completed": True,
                "target_answer_path": True,
                "cta_authored_match": True,
                "target_widget_present": True,
            }
        },
    }
    audit = ProviderAuditState()
    audit.total_started = 5
    audit.fullcontext_build_count = 1
    audit.role_totals.update(
        {
            "ingress": 1,
            "planner": 1,
            "medical_boundary": 1,
            "composer": 1,
            "semantic_verifier": 1,
        }
    )
    proof = {
        "env_present": False,
        "config_default_resolved": True,
        "authority_source": "config_default",
    }
    summary = evaluate_summary(turn_result, audit, authority_proof=proof, ledger_balanced=True)
    assert summary["automated_verdict"] == "AUTOMATED_PASS"
    assert summary["final_verdict"] == "PENDING_MANUAL_REVIEW"


def test_evaluate_summary_automated_fail_on_legacy_hit() -> None:
    turn_result = {
        "meta": {"service_route": "target_fullcontext_materialized"},
        "gates": {
            "flags": {
                "http_completed": True,
                "target_answer_path": True,
                "cta_authored_match": True,
                "target_widget_present": True,
            }
        },
    }
    audit = ProviderAuditState()
    audit.legacy_hits.append("orchestration.ask_turn.orchestrate_routing_after_resolver")
    audit.total_started = 5
    audit.fullcontext_build_count = 1
    audit.role_totals.update({role: 1 for role in audit.role_totals})
    proof = {
        "env_present": False,
        "config_default_resolved": True,
        "authority_source": "config_default",
    }
    summary = evaluate_summary(turn_result, audit, authority_proof=proof, ledger_balanced=True)
    assert summary["automated_verdict"] == "AUTOMATED_FAIL"


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


def test_provider_audit_blocks_call_6(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "attempt.json"
    ledger = tmp_path / "ledger.jsonl"
    reset_audit_state()
    uninstall_provider_audit()
    proof = {
        "env_present": False,
        "config_default_resolved": True,
        "authority_source": "config_default",
    }
    create_attempt_marker_exclusive(
        marker,
        build_attempt_marker_payload(baseline_commit="x", authority_proof=proof),
    )
    import llm
    from evals.v5 import s66_default_authority_live_provider_audit as audit_module

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
    for index, role in enumerate(roles):
        set_current_turn(1)
        monkeypatch.setattr(
            audit_module,
            "_infer_provider_role",
            lambda captured_role=role: captured_role,
        )
        llm.chat_completions_create(model="qwen3.6-flash", messages=[])
    set_current_turn(1)
    monkeypatch.setattr(audit_module, "_infer_provider_role", lambda: "ingress")
    with pytest.raises(HarnessConfigError, match="provider call budget exceeded"):
        llm.chat_completions_create(model="qwen3.6-flash", messages=[])
    uninstall_provider_audit()


def test_prepare_live_run_creates_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TARGET_FULLCONTEXT_DEV", raising=False)
    marker = tmp_path / "attempt.json"
    proof = prepare_live_run(attempt_marker_path=marker, artifact_paths=())
    assert marker.exists()
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["status"] == "attempt_started"
    assert payload["max_provider_calls"] == 5
    assert proof["authority_source"] == "config_default"
