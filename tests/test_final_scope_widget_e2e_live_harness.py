"""Offline tests for FINAL scope/widget E2E live harness."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from evals.v5.final_scope_widget_e2e_live_contract import (
    FROZEN_TURNS_HASH,
    MAX_HTTP_TURNS,
    MAX_PROVIDER_CALLS,
    OWNER_APPROVED_PLANNER_MODEL,
    assert_frozen_s62_live_artifacts_unchanged,
    assert_frozen_s63_live_artifacts_unchanged,
    build_attempt_marker_payload,
    create_attempt_marker_exclusive,
    ledger_entries_balanced,
    load_frozen_turns,
)
from evals.v5.final_scope_widget_e2e_live_harness import (
    configure_process_env,
    evaluate_summary,
    evaluate_turn_gates,
    pick_scope_ref,
    pick_stage_ref,
    prepare_live_run,
)
from evals.v5.final_scope_widget_e2e_live_provider_audit import ProviderAuditState

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_frozen_turns_has_eight_exact_turns() -> None:
    spec = load_frozen_turns()
    assert spec["suite_id"] == "final_scope_widget_e2e"
    assert len(spec["turns"]) == MAX_HTTP_TURNS
    assert spec["turns"][0]["request"]["q"] == "Сколько стоит имплантация?"
    assert spec["turns"][3]["endpoint"] == "/ask/stream"
    assert spec["turns"][3].get("fresh_sid") is True


def test_frozen_turns_hash_matches_contract() -> None:
    path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    import hashlib

    assert hashlib.sha256(path.read_bytes()).hexdigest() == FROZEN_TURNS_HASH


def test_frozen_s62_s63_artifacts_unchanged() -> None:
    assert_frozen_s62_live_artifacts_unchanged()
    assert_frozen_s63_live_artifacts_unchanged()


def test_configure_process_env_sets_plus_planner() -> None:
    configure_process_env()
    import importlib

    import config

    importlib.reload(config)
    assert config.TURN_PLANNER_LLM_MODEL == OWNER_APPROVED_PLANNER_MODEL


def test_attempt_marker_exclusive_create(tmp_path: Path) -> None:
    marker = tmp_path / "attempt.json"
    create_attempt_marker_exclusive(marker, build_attempt_marker_payload(baseline_commit="abc"))
    with pytest.raises(Exception):
        create_attempt_marker_exclusive(marker, build_attempt_marker_payload(baseline_commit="abc"))


def test_pick_scope_and_stage_refs() -> None:
    scope = pick_scope_ref(
        [{"label": "Вся челюсть", "ref": "target:ui_scope/implantation/full_arch"}],
        topic="implantation",
        extent="full_arch",
    )
    assert scope is not None
    stage = pick_stage_ref(
        [{"label": "Имплант установлен", "ref": "target:ui_stage/prosthetics/implant_placed"}],
        topic="prosthetics",
        stage="implant_placed",
    )
    assert stage is not None


def test_evaluate_turn_gates_broad_implantation_shape() -> None:
    gates = evaluate_turn_gates(
        {
            "turn_id": "fsw_turn_01_implant_broad",
            "status_code": 200,
            "meta": {
                "service_route": "target_fullcontext_materialized",
                "response_stage": "broad_family_price",
                "answer_path": "target_fullcontext",
            },
            "quick_replies": [
                {"ref": "target:ui_scope/implantation/one_tooth", "label": "Один зуб"},
                {"ref": "target:ui_scope/implantation/few_teeth", "label": "Несколько зубов"},
                {"ref": "target:ui_scope/implantation/full_arch", "label": "Вся челюсть"},
            ],
            "expect": {
                "response_stage": "broad_family_price",
                "scope_nav_count": 3,
                "max_price_followups": 0,
                "max_payment_stage_followups": 0,
            },
        }
    )
    assert gates["automated_turn_verdict"] == "PASS"


def test_evaluate_summary_automated_pass_shape() -> None:
    turn_results = []
    for turn in range(1, MAX_HTTP_TURNS + 1):
        turn_results.append(
            {
                "turn": turn,
                "turn_id": f"t{turn}",
                "meta": {"service_route": "target_fullcontext_materialized"},
                "gates": {"flags": {"http_completed": True, "target_answer_path": True}},
                "automated_turn_verdict": "PASS",
            }
        )
    audit = ProviderAuditState()
    audit.total_started = 40
    audit.fullcontext_build_count = 1
    audit.role_totals.update(
        {
            "ingress": 8,
            "planner": 8,
            "medical_boundary": 8,
            "composer": 8,
            "semantic_verifier": 8,
        }
    )
    ledger = _REPO_ROOT / "evals" / "v5" / "artifacts" / "_test_fsw_ledger.jsonl"
    ledger.write_text(
        "\n".join(
            json.dumps(
                {
                    "sequence": i,
                    "role": "planner",
                    "phase": "call_start",
                    "model": OWNER_APPROVED_PLANNER_MODEL,
                }
            )
            for i in range(1, 9)
        )
        + "\n",
        encoding="utf-8",
    )
    summary = evaluate_summary(
        turn_results,
        audit,
        ledger_balanced=True,
        call_ledger_path=ledger,
    )
    ledger.unlink(missing_ok=True)
    assert summary["automated_verdict"] == "AUTOMATED_PASS"
    assert summary["final_verdict"] == "PENDING_MANUAL_REVIEW"


def test_provider_call_budget_constants() -> None:
    assert MAX_PROVIDER_CALLS == 40
    assert MAX_HTTP_TURNS == 8


def test_dry_run_cli() -> None:
    proc = subprocess.run(
        [sys.executable, "evals/v5/run_final_scope_widget_e2e_live.py", "--dry-run"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["dry_run"] is True
    assert payload["max_http_turns"] == MAX_HTTP_TURNS


def test_prepare_live_run_creates_exclusive_marker(tmp_path: Path) -> None:
    marker = tmp_path / "attempt.json"
    artifacts = tuple(tmp_path / f"artifact_{i}.json" for i in range(3))
    prepare_live_run(
        attempt_marker_path=marker,
        artifact_paths=artifacts,
        baseline_commit="test",
    )
    assert marker.exists()
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["planner_model"] == OWNER_APPROVED_PLANNER_MODEL
    assert payload["a9_patient_scope_authority"] == "1"


def test_ledger_balance_helper(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        '{"sequence":1,"phase":"call_start"}\n{"sequence":1,"phase":"call_complete"}\n',
        encoding="utf-8",
    )
    assert ledger_entries_balanced(ledger) is True
