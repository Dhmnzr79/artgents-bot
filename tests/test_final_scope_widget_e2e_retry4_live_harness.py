"""Offline tests for FINAL scope/widget E2E retry4 live harness."""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from contracts.planner_attempt import PlannerAttempt
from evals.v5.final_scope_widget_e2e_live_contract import (
    MAX_HTTP_TURNS,
    OWNER_APPROVED_PLANNER_MODEL,
    create_attempt_marker_exclusive,
)
from evals.v5.final_scope_widget_e2e_live_harness import (
    configure_process_env,
    run_non_network_preflight,
    validate_runtime_seams,
    _scope_nav_refs,
)
from evals.v5.final_scope_widget_e2e_retry4_live_provider_audit import get_audit_state
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    EXPECTED_FREE_TEXT_PLANNER_CALLS,
    MANUAL_REVIEW_RUBRIC,
    MAX_PROVIDER_CALLS,
    MEASUREMENT_ID,
    RETRY_COUNT_MAX,
    S69_DELETED_LEGACY_MODULES,
    S69_FORBIDDEN_HARNESS_IMPORT_PATTERNS,
    TYPED_UI_TURNS_NO_PLANNER,
    assert_frozen_preflight_abort_artifacts_unchanged,
    assert_frozen_retry1_live_artifacts_unchanged,
    assert_frozen_retry2_live_artifacts_unchanged,
    assert_frozen_retry3_live_artifacts_unchanged,
    assert_frozen_s62_live_artifacts_unchanged,
    assert_frozen_s63_live_artifacts_unchanged,
    build_retry4_attempt_marker_payload,
    load_frozen_turns,
)
from evals.v5.final_scope_widget_e2e_retry4_live_harness import (
    _assert_frozen_neighbors,
    prepare_retry4_live_run,
    run_http_harness,
)
from tests.test_final_scope_widget_e2e_retry1_live_harness import (
    _GroundedEvidenceComposerBackend,
    _install_retry1_http_fakes,
    _turn_frame_for_number,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

_RETRY4_HARNESS_FILES = (
    _REPO_ROOT / "evals" / "v5" / "final_scope_widget_e2e_live_harness.py",
    _REPO_ROOT / "evals" / "v5" / "final_scope_widget_e2e_retry4_live_harness.py",
    _REPO_ROOT / "evals" / "v5" / "run_final_scope_widget_e2e_retry4_live.py",
)

_T1_VERBOSE_WALL_MARKERS = (
    "бонус",
    "этап оплаты",
    "рассрочк",
    "пакет включает",
)


class _ActionAwareGroundedComposerBackend(_GroundedEvidenceComposerBackend):
    """Composer stub that honors governed UI action context for typed clicks."""

    def generate(self, invocation: object, /) -> str:
        import json

        governed_raw = getattr(invocation, "governed_action_context_json", None)
        if isinstance(governed_raw, str) and governed_raw.strip():
            governed = json.loads(governed_raw)
            response_stage = str(governed.get("response_stage") or "")
            if response_stage == "stage_clarify":
                return (
                    "Подскажите, на каком этапе вы сейчас — "
                    "свой зуб, удаление или имплант уже установлен?"
                )
        text = super().generate(invocation)
        if isinstance(governed_raw, str) and governed_raw.strip():
            if text == "Краткий обзор цен.":
                action_kind = json.loads(governed_raw).get("action_kind")
                if action_kind == "ui_stage":
                    return "Стоимость коронки на имплант от 31 000 ₽."
        return text


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


@pytest.fixture(autouse=True)
def _retry4_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A9_PATIENT_SCOPE_AUTHORITY", "1")
    monkeypatch.setenv("TURN_PLANNER_LLM_MODEL", OWNER_APPROVED_PLANNER_MODEL)
    monkeypatch.setenv("MODEL_INGRESS_CLASSIFY", "qwen3.6-flash")
    monkeypatch.setenv("TARGET_FULLCONTEXT_BOUNDARY_MODEL", OWNER_APPROVED_PLANNER_MODEL)
    monkeypatch.setenv("TARGET_FULLCONTEXT_COMPOSER_MODEL", OWNER_APPROVED_PLANNER_MODEL)
    monkeypatch.setenv("TARGET_FULLCONTEXT_VERIFIER_MODEL", OWNER_APPROVED_PLANNER_MODEL)


def _install_retry4_http_fakes(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    from evals.v5.final_scope_widget_e2e_retry4_live_provider_audit import (
        record_fullcontext_build as retry4_record_fullcontext_build,
        set_current_turn as retry4_set_current_turn,
    )
    import app as app_module
    from orchestration.target_fullcontext_turn import orchestrate_target_fullcontext_turn as real_orchestrate
    from tests.test_s61_correction_target_runtime import (
        BackendPayload,
        RecordingBoundaryBackend,
        RecordingSemanticBackend,
    )

    monkeypatch.setattr(
        "evals.v5.final_scope_widget_e2e_live_provider_audit.record_fullcontext_build",
        retry4_record_fullcontext_build,
    )
    monkeypatch.setattr(
        "evals.v5.final_scope_widget_e2e_live_provider_audit.set_current_turn",
        retry4_set_current_turn,
    )
    state = _install_retry1_http_fakes(monkeypatch)
    planner_calls_by_turn: dict[int, int] = {}
    composer_backend = _ActionAwareGroundedComposerBackend()

    def counting_plan_turn_attempt(q: str, sid: str, client_id: str) -> PlannerAttempt:
        turn_number = get_audit_state().current_turn or 0
        planner_calls_by_turn[turn_number] = planner_calls_by_turn.get(turn_number, 0) + 1
        frame = _turn_frame_for_number(turn_number)
        return PlannerAttempt(frame=frame, status="ok")

    monkeypatch.setattr("core.turn_planner_llm.plan_turn_attempt", counting_plan_turn_attempt)
    monkeypatch.setattr("orchestration.planner_turn.plan_turn_attempt", counting_plan_turn_attempt)

    def orchestrate_with_action_aware(**kwargs: object):
        turn_number = get_audit_state().current_turn or 1
        if turn_number == 2:
            boundary = RecordingBoundaryBackend(BackendPayload("medical_handoff", 0.9))
        else:
            boundary = RecordingBoundaryBackend(BackendPayload("none", 0.95))
        return real_orchestrate(
            q=str(kwargs["q"]),
            sid=str(kwargs["sid"]),
            client_id=str(kwargs["client_id"]),
            data=kwargs.get("data") if isinstance(kwargs.get("data"), dict) else None,
            composer_backend=composer_backend,
            semantic_backend=RecordingSemanticBackend(),
            boundary_backend=boundary,
        )

    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", orchestrate_with_action_aware)
    state["planner_calls_by_turn"] = planner_calls_by_turn
    state["composer_backend"] = composer_backend
    return state


def test_frozen_retry1_retry2_retry3_neighbors_unchanged() -> None:
    assert_frozen_preflight_abort_artifacts_unchanged()
    assert_frozen_s62_live_artifacts_unchanged()
    assert_frozen_s63_live_artifacts_unchanged()
    assert_frozen_retry1_live_artifacts_unchanged()
    assert_frozen_retry2_live_artifacts_unchanged()
    assert_frozen_retry3_live_artifacts_unchanged()


def test_retry4_budget_constants() -> None:
    assert MAX_PROVIDER_CALLS == 34
    assert MAX_HTTP_TURNS == 8
    assert RETRY_COUNT_MAX == 0
    assert EXPECTED_FREE_TEXT_PLANNER_CALLS == 5
    assert TYPED_UI_TURNS_NO_PLANNER == frozenset({2, 6, 7})
    assert MANUAL_REVIEW_RUBRIC[1] == "compact_overview"
    assert MANUAL_REVIEW_RUBRIC[2] == "full_arch_prices"
    assert MANUAL_REVIEW_RUBRIC[6] == "concise_stage_clarification"
    assert MANUAL_REVIEW_RUBRIC[7] == "crown_price"
    load_frozen_turns()


def test_s69_deleted_modules_not_importable() -> None:
    for module_name in S69_DELETED_LEGACY_MODULES:
        assert importlib.util.find_spec(module_name) is None, module_name


def test_harness_ast_firewall_forbids_deleted_s69_imports() -> None:
    patterns = [re.compile(p) for p in S69_FORBIDDEN_HARNESS_IMPORT_PATTERNS]
    offenders: list[str] = []
    for path in _RETRY4_HARNESS_FILES:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for pattern in patterns:
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(_REPO_ROOT)}:{lineno}:{line.strip()}")
    assert not offenders, offenders


def test_validate_runtime_seams_exposes_target_only_client() -> None:
    configure_process_env()
    seam = validate_runtime_seams()
    assert hasattr(seam["app_module"], "_orchestrate_ask_turn")
    assert not hasattr(seam["app_module"], "orchestrate_routing_after_resolver")
    assert seam["client"] is not None


def test_fake_provider_executes_all_eight_http_turns_without_network(
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
        build_retry4_attempt_marker_payload(baseline_commit="retry4-offline"),
    )
    fake_state = _install_retry4_http_fakes(monkeypatch)
    planner_calls_by_turn: dict[int, int] = fake_state["planner_calls_by_turn"]  # type: ignore[assignment]
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
    assert all(row["status_code"] == 200 for row in turns)
    assert all(row["automated_turn_verdict"] == "PASS" for row in turns)
    assert payload["summary"]["technical"]["turn_automated_pass"] == MAX_HTTP_TURNS
    assert payload["summary"]["technical"]["all_materialized"] is True
    assert payload["summary"]["technical"]["fullcontext_build_count"] == 1

    for row in turns:
        assert not any(ref.startswith("price:None/") for ref in _quick_reply_refs(row))

    turn1 = turns[0]
    turn1_text = str(turn1.get("answer_text") or "")
    assert len(_scope_nav_refs(list(turn1.get("quick_replies") or []))) == 3
    assert "₽" in turn1_text
    assert len(turn1_text) <= 700
    assert not any(marker in turn1_text.lower() for marker in _T1_VERBOSE_WALL_MARKERS)

    turn2 = turns[1]
    turn2_text = str(turn2.get("answer_text") or "")
    assert "₽" in turn2_text
    assert "terminal" not in str((turn2.get("meta") or {}).get("service_route") or "")

    turn6 = turns[5]
    turn6_text = str(turn6.get("answer_text") or "")
    assert "этап" in turn6_text.lower()
    assert len(turn6_text) <= 250

    turn7 = turns[6]
    turn7_text = str(turn7.get("answer_text") or "")
    assert "₽" in turn7_text
    assert "корон" in turn7_text.lower() or "31 000" in turn7_text

    governed = _governed_invocations(composer)
    governed_by_ref = {str(item.get("governed_ref")): item for item in governed}
    assert "target:ui_scope/implantation/full_arch" in governed_by_ref
    assert (
        governed_by_ref["target:ui_scope/implantation/full_arch"]["response_stage"]
        == "scoped_family_price"
    )
    assert governed_by_ref["target:ui_scope/implantation/full_arch"]["extent"] == "full_arch"
    assert "target:ui_stage/prosthetics/implant_placed" in governed_by_ref
    assert governed_by_ref["target:ui_stage/prosthetics/implant_placed"]["action_kind"] == "ui_stage"

    for invocation in composer.invocations:
        content = __import__(
            "core.target_runtime_llm_messages",
            fromlist=["build_composer_sdk_messages"],
        ).build_composer_sdk_messages(invocation)[1]["content"]
        assert "GOVERNED_ACTION_CONTEXT_JSON" in content

    turn5 = turns[4]
    assert len(_scope_nav_refs(list(turn5.get("quick_replies") or []))) == 3
    assert "₽" in str(turn5.get("answer_text") or "")
    stream_turns = [row for row in turns if row["endpoint"] == "/ask/stream"]
    assert len(stream_turns) == 2
    assert all("event: ui" in str(row.get("stream_text") or "") for row in stream_turns)

    assert sum(planner_calls_by_turn.values()) == EXPECTED_FREE_TEXT_PLANNER_CALLS
    for turn_number in TYPED_UI_TURNS_NO_PLANNER:
        assert planner_calls_by_turn.get(turn_number, 0) == 0
    for turn_number in (1, 3, 4, 5, 8):
        assert planner_calls_by_turn.get(turn_number, 0) == 1


def test_retry4_dry_run_cli() -> None:
    from evals.v5.final_scope_widget_e2e_retry4_live_contract import LIVE_ATTEMPT_MARKER_PATH

    proc = subprocess.run(
        [sys.executable, "evals/v5/run_final_scope_widget_e2e_retry4_live.py", "--dry-run"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if LIVE_ATTEMPT_MARKER_PATH.exists():
        assert proc.returncode == 2, proc.stderr
        assert "CONFIG_ERROR" in proc.stderr
        return
    assert proc.returncode == 0, proc.stderr
    idx = proc.stdout.rfind('"measurement_id"')
    start = proc.stdout.rfind("{", 0, idx)
    payload = json.loads(proc.stdout[start:])
    assert payload["measurement_id"] == MEASUREMENT_ID
    assert payload["dry_run"] is True
    assert payload["live_blocked"] is True
    assert payload["max_provider_calls"] == MAX_PROVIDER_CALLS
    assert payload["role_budget_caps"]["planner"] == 5
    assert payload["manual_review_rubric"]["1"] == "compact_overview"
    assert payload["manual_review_rubric"]["2"] == "full_arch_prices"
    assert payload["manual_review_rubric"]["6"] == "concise_stage_clarification"
    assert payload["manual_review_rubric"]["7"] == "crown_price"


def test_marker_created_after_seam_validation_before_provider_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "attempt.json"
    artifacts = tuple(tmp_path / f"artifact_{i}.json" for i in range(3))
    events: list[str] = []

    def tracked_validate(mp: object | None = None) -> dict[str, object]:
        events.append("seams_validated")
        return validate_runtime_seams(mp)

    def tracked_create(path: Path, payload: dict[str, object]) -> None:
        events.append("marker_created")
        create_attempt_marker_exclusive(path, payload)

    monkeypatch.setattr(
        "evals.v5.final_scope_widget_e2e_retry4_live_harness.assert_retry4_live_artifacts_absent",
        lambda: None,
    )
    monkeypatch.setattr(
        "evals.v5.final_scope_widget_e2e_live_harness.validate_runtime_seams",
        tracked_validate,
    )
    monkeypatch.setattr(
        "evals.v5.final_scope_widget_e2e_live_harness.create_attempt_marker_exclusive",
        tracked_create,
    )
    prepare_retry4_live_run(
        attempt_marker_path=marker,
        artifact_paths=artifacts,
        baseline_commit="retry4-test",
        monkeypatch=monkeypatch,
    )
    assert events == ["seams_validated", "marker_created"]
