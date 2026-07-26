"""Offline tests for FINAL scope/widget E2E retry1 live harness."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from contracts.ask_orchestration import AskOrchestrationResult
from contracts.planner_attempt import PlannerAttempt
from contracts.ui_scope_action import build_ui_scope_ref
from contracts.ui_stage_action import build_ui_stage_ref
from evals.v5.final_scope_widget_e2e_live_contract import (
    FROZEN_TURNS_HASH,
    MAX_HTTP_TURNS,
    MAX_PROVIDER_CALLS,
    OWNER_APPROVED_PLANNER_MODEL,
    create_attempt_marker_exclusive,
)
from evals.v5.final_scope_widget_e2e_live_harness import (
    configure_process_env,
    run_non_network_preflight,
    validate_runtime_seams,
    _scope_nav_refs,
)
from evals.v5.final_scope_widget_e2e_live_provider_audit import (
    get_audit_state,
    install_provider_audit,
    reset_audit_state,
    uninstall_provider_audit,
)
from evals.v5.final_scope_widget_e2e_retry1_live_contract import (
    DEFAULT_LIVE_ARTIFACT_PATHS,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_CALL_LEDGER_PATH,
    LIVE_RAW_ARTIFACT_PATH,
    MEASUREMENT_ID,
    S69_DELETED_LEGACY_MODULES,
    S69_FORBIDDEN_HARNESS_IMPORT_PATTERNS,
    assert_frozen_preflight_abort_artifacts_unchanged,
    assert_frozen_s62_live_artifacts_unchanged,
    assert_frozen_s63_live_artifacts_unchanged,
    build_retry1_attempt_marker_payload,
    load_frozen_turns,
)
from evals.v5.final_scope_widget_e2e_retry1_live_harness import (
    _assert_frozen_neighbors,
    prepare_retry1_live_run,
    run_http_harness,
)
from tests.test_w1_family_price_overview_offline import _family_overview_frame

_REPO_ROOT = Path(__file__).resolve().parents[1]

_RETRY1_HARNESS_FILES = (
    _REPO_ROOT / "evals" / "v5" / "final_scope_widget_e2e_live_harness.py",
    _REPO_ROOT / "evals" / "v5" / "final_scope_widget_e2e_retry1_live_harness.py",
    _REPO_ROOT / "evals" / "v5" / "run_final_scope_widget_e2e_retry1_live.py",
)


def _turn_frame_for_number(turn_number: int):
    if turn_number == 1:
        return _family_overview_frame(
            patient_scope={
                "extent": "unknown",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            }
        )
    if turn_number == 2:
        return _family_overview_frame(
            route="price_lookup",
            needs_clarify=True,
            patient_scope={
                "extent": "full_arch",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            },
        )
    if turn_number == 3:
        return _family_overview_frame(
            patient_scope={
                "extent": "one_tooth",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            }
        )
    if turn_number == 4:
        return _family_overview_frame(
            patient_scope={
                "extent": "full_arch",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            }
        )
    if turn_number == 5:
        return _family_overview_frame(
            topic="prosthetics",
            needs_clarify=True,
            patient_scope={
                "extent": "unknown",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            },
        )
    if turn_number == 6:
        return _family_overview_frame(
            topic="prosthetics",
            route="price_lookup",
            patient_scope={
                "extent": "one_tooth",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            },
        )
    if turn_number == 7:
        return _family_overview_frame(
            topic="prosthetics",
            route="price_lookup",
            patient_scope={
                "extent": "one_tooth",
                "jaw": "unknown",
                "stage": "implant_placed",
                "modifiers": [],
            },
        )
    if turn_number == 8:
        return _family_overview_frame(
            topic="prosthetics",
            patient_scope={
                "extent": "one_tooth",
                "jaw": "unknown",
                "stage": "implant_placed",
                "modifiers": [],
            }
        )
    return _family_overview_frame(
        patient_scope={
            "extent": "unknown",
            "jaw": "unknown",
            "stage": "unknown",
            "modifiers": [],
        }
    )



class _GroundedEvidenceComposerBackend:
    """Composer stub that echoes only evidence-grounded offer prices for verifier parity."""

    def __init__(self) -> None:
        self.invocations: list[object] = []

    def generate(self, invocation: object, /) -> str:
        self.invocations.append(invocation)
        import json

        blocks = json.loads(str(getattr(invocation, "primary_evidence_json", "[]")))
        parts = ["Стоимость зависит от метода лечения."]
        for block in blocks:
            if not isinstance(block, dict) or block.get("kind") != "offer":
                continue
            inner_raw = block.get("text")
            if not isinstance(inner_raw, str) or not inner_raw.strip():
                continue
            try:
                inner = json.loads(inner_raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(inner, dict):
                continue
            price = inner.get("price")
            if not isinstance(price, dict):
                continue
            service_id = str(inner.get("service_id") or "услуга")
            mode = str(price.get("mode") or "")
            if mode == "fixed":
                amount = int(price.get("amount") or 0)
                parts.append(f"от {amount:,} ₽".replace(",", " "))
            elif mode == "from":
                amount = int(price.get("min_amount") or 0)
                parts.append(f"от {amount:,} ₽".replace(",", " "))
            elif mode == "range":
                lo = int(price.get("min_amount") or 0)
                hi = int(price.get("max_amount") or 0)
                parts.append(f"от {lo:,} до {hi:,} ₽".replace(",", " "))
        if len(parts) == 1:
            return "Краткий обзор цен."
        return " ".join(parts)


def _install_retry1_http_fakes(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    import importlib
    import app as app_module
    import core.target_cached_full_context as cached_module
    import core.target_runtime_client_context as runtime_context_module
    from evals.v5 import final_scope_widget_e2e_live_harness as harness_module
    from evals.v5.final_scope_widget_e2e_live_provider_audit import record_fullcontext_build
    from ingress_gate import IngressRouteResult
    from core.target_runtime_client_context import clear_target_runtime_client_context_cache
    from orchestration.target_fullcontext_turn import orchestrate_target_fullcontext_turn as real_orchestrate
    from tests.test_s61_correction_target_runtime import (
        BackendPayload,
        RecordingBoundaryBackend,
        RecordingSemanticBackend,
    )

    cached_module = importlib.reload(cached_module)
    runtime_context_module = importlib.reload(runtime_context_module)
    original_fullcontext_build = cached_module.build_target_cached_full_context
    original_resolve = harness_module._resolve_request_body

    def fake_resolve_request_body(
        spec: dict[str, object],
        *,
        turn_outputs: dict[int, dict[str, object]],
    ) -> tuple[dict[str, object], dict[str, object]]:
        kind = spec.get("request_kind")
        if kind == "ui_scope_ref_from_turn":
            ref = build_ui_scope_ref(
                topic=str(spec["pick_topic"]),
                extent=str(spec["pick_extent"]),  # type: ignore[arg-type]
            )
            label = {
                "one_tooth": "Один зуб",
                "few_teeth": "Несколько зубов",
                "full_arch": "Вся челюсть",
            }[str(spec["pick_extent"])]
            return {"q": "", "ref": ref}, {"ui_ref_used": True, "ref": ref, "label": label}
        if kind == "ui_stage_ref_from_turn":
            ref = build_ui_stage_ref(
                topic=str(spec["pick_topic"]),
                stage=str(spec["pick_stage"]),  # type: ignore[arg-type]
            )
            label = {
                "implant_placed": "Имплант установлен",
                "natural_tooth_present": "Свой зуб сохранился",
            }[str(spec["pick_stage"])]
            return {"q": "", "ref": ref}, {"ui_ref_used": True, "ref": ref, "label": label}
        return original_resolve(spec, turn_outputs=turn_outputs)

    def fake_classify_ingress(q: str, **kwargs: object) -> IngressRouteResult:
        return IngressRouteResult(
            route="normal",
            confidence=1.0,
            reason="test",
            policy_key=None,
            requested_service=None,
            source="skipped",
            is_urgent=False,
        )

    def fake_plan_turn_attempt(q: str, sid: str, client_id: str) -> PlannerAttempt:
        turn_number = get_audit_state().current_turn or 1
        frame = _turn_frame_for_number(turn_number)
        return PlannerAttempt(frame=frame, status="ok")

    fullcontext_cache: dict[str, object] = {"value": None}
    clear_target_runtime_client_context_cache()

    def cached_fullcontext_build(*args: object, **kwargs: object):
        if fullcontext_cache["value"] is None:
            record_fullcontext_build()
            fullcontext_cache["value"] = original_fullcontext_build(*args, **kwargs)
        return fullcontext_cache["value"]

    def orchestrate_with_fakes(**kwargs: object) -> AskOrchestrationResult:
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
            composer_backend=_GroundedEvidenceComposerBackend(),
            semantic_backend=RecordingSemanticBackend(),
            boundary_backend=boundary,
        )

    monkeypatch.setattr("ingress_gate.classify_ingress", fake_classify_ingress)
    monkeypatch.setattr("orchestration.pre_resolver_turn.classify_ingress", fake_classify_ingress)
    monkeypatch.setattr("core.turn_planner_llm.plan_turn_attempt", fake_plan_turn_attempt)
    monkeypatch.setattr("orchestration.planner_turn.plan_turn_attempt", fake_plan_turn_attempt)
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", orchestrate_with_fakes)
    monkeypatch.setattr(cached_module, "build_target_cached_full_context", cached_fullcontext_build)
    monkeypatch.setattr(
        runtime_context_module,
        "build_target_cached_full_context",
        cached_fullcontext_build,
    )
    monkeypatch.setattr(harness_module, "_resolve_request_body", fake_resolve_request_body)

    return {"orchestrate_with_fakes": orchestrate_with_fakes}


@pytest.fixture(autouse=True)
def _retry1_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TURN_PLANNER_LLM_MODEL", OWNER_APPROVED_PLANNER_MODEL)
    monkeypatch.setenv("MODEL_INGRESS_CLASSIFY", "qwen3.6-flash")
    monkeypatch.setenv("TARGET_FULLCONTEXT_BOUNDARY_MODEL", OWNER_APPROVED_PLANNER_MODEL)
    monkeypatch.setenv("TARGET_FULLCONTEXT_COMPOSER_MODEL", OWNER_APPROVED_PLANNER_MODEL)
    monkeypatch.setenv("TARGET_FULLCONTEXT_VERIFIER_MODEL", OWNER_APPROVED_PLANNER_MODEL)


def test_frozen_preflight_abort_artifacts_unchanged() -> None:
    assert_frozen_preflight_abort_artifacts_unchanged()


def test_frozen_s62_s63_neighbors_unchanged() -> None:
    assert_frozen_s62_live_artifacts_unchanged()
    assert_frozen_s63_live_artifacts_unchanged()


def test_retry1_budget_constants() -> None:
    assert MAX_PROVIDER_CALLS == 40
    assert MAX_HTTP_TURNS == 8
    load_frozen_turns()


def test_s69_deleted_modules_not_importable() -> None:
    for module_name in S69_DELETED_LEGACY_MODULES:
        assert importlib.util.find_spec(module_name) is None, module_name


def test_harness_ast_firewall_forbids_deleted_s69_imports() -> None:
    patterns = [re.compile(p) for p in S69_FORBIDDEN_HARNESS_IMPORT_PATTERNS]
    offenders: list[str] = []
    for path in _RETRY1_HARNESS_FILES:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for pattern in patterns:
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(_REPO_ROOT)}:{lineno}:{line.strip()}")
    assert not offenders, offenders


def test_fresh_subprocess_post_s69_preflight_passes() -> None:
    repo = str(_REPO_ROOT).replace("\\", "\\\\")
    script = f"""
import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, r"{repo}")
os.environ["TURN_PLANNER_LLM_MODEL"] = "qwen3.7-plus"
os.environ["MODEL_INGRESS_CLASSIFY"] = "qwen3.6-flash"
os.environ["TARGET_FULLCONTEXT_BOUNDARY_MODEL"] = "qwen3.7-plus"
os.environ["TARGET_FULLCONTEXT_COMPOSER_MODEL"] = "qwen3.7-plus"
os.environ["TARGET_FULLCONTEXT_VERIFIER_MODEL"] = "qwen3.7-plus"
from evals.v5.final_scope_widget_e2e_retry1_live_harness import run_non_network_preflight, _assert_frozen_neighbors
from evals.v5.final_scope_widget_e2e_retry1_live_contract import DEFAULT_LIVE_ARTIFACT_PATHS
with tempfile.TemporaryDirectory() as td:
    marker = Path(td) / "attempt.json"
    artifacts = tuple(Path(td) / f"a{{i}}.json" for i in range(3))
    run_non_network_preflight(
        attempt_marker_path=marker,
        artifact_paths=artifacts,
        assert_frozen_neighbors=_assert_frozen_neighbors,
    )
assert not marker.exists()
raise SystemExit(0)
"""
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(_REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_validate_runtime_seams_exposes_target_only_client() -> None:
    configure_process_env()
    seam = validate_runtime_seams()
    assert hasattr(seam["app_module"], "_orchestrate_ask_turn")
    assert not hasattr(seam["app_module"], "orchestrate_routing_after_resolver")
    client = seam["client"]
    assert client is not None


def test_preflight_failure_leaves_retry1_marker_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "attempt.json"
    artifacts = tuple(tmp_path / f"artifact_{i}.json" for i in range(3))

    def broken_validate(_mp: object | None = None) -> dict[str, object]:
        raise RuntimeError("seam validation failed")

    monkeypatch.setattr(
        "evals.v5.final_scope_widget_e2e_live_harness.validate_runtime_seams",
        broken_validate,
    )
    with pytest.raises(RuntimeError, match="seam validation failed"):
        run_non_network_preflight(
            attempt_marker_path=marker,
            artifact_paths=artifacts,
            monkeypatch=monkeypatch,
            assert_frozen_neighbors=_assert_frozen_neighbors,
        )
    assert not marker.exists()


def test_marker_created_after_seam_validation_before_provider_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "attempt.json"
    ledger = tmp_path / "ledger.jsonl"
    artifacts = tuple(tmp_path / f"artifact_{i}.json" for i in range(3))
    events: list[str] = []

    original_validate = validate_runtime_seams

    def tracked_validate(mp: object | None = None) -> dict[str, object]:
        events.append("seams_validated")
        return original_validate(mp)

    def tracked_create(path: Path, payload: dict[str, object]) -> None:
        events.append("marker_created")
        create_attempt_marker_exclusive(path, payload)

    monkeypatch.setattr(
        "evals.v5.final_scope_widget_e2e_live_harness.validate_runtime_seams",
        tracked_validate,
    )
    monkeypatch.setattr(
        "evals.v5.final_scope_widget_e2e_live_harness.create_attempt_marker_exclusive",
        tracked_create,
    )
    prepare_retry1_live_run(
        attempt_marker_path=marker,
        artifact_paths=artifacts,
        baseline_commit="retry1-test",
        monkeypatch=monkeypatch,
    )
    assert events == ["seams_validated", "marker_created"]
    reset_audit_state()
    uninstall_provider_audit()
    install_provider_audit(attempt_marker_path=marker, call_ledger_path=ledger)
    assert get_audit_state().total_started == 0
    uninstall_provider_audit()


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
        build_retry1_attempt_marker_payload(baseline_commit="retry1-offline"),
    )
    _install_retry1_http_fakes(monkeypatch)

    payload = run_http_harness(
        live=False,
        skip_live_prepare=True,
        attempt_marker_path=marker,
        call_ledger_path=ledger,
        artifact_paths=artifacts,
        monkeypatch=monkeypatch,
    )

    assert len(payload["turn_results"]) == MAX_HTTP_TURNS
    assert all(row["status_code"] == 200 for row in payload["turn_results"])
    assert all(row["automated_turn_verdict"] == "PASS" for row in payload["turn_results"])
    assert payload["summary"]["technical"]["turn_automated_pass"] == MAX_HTTP_TURNS
    assert payload["summary"]["technical"]["all_materialized"] is True
    assert payload["summary"]["technical"]["fullcontext_build_count"] == 1
    turn2 = payload["turn_results"][1]
    assert "terminal" not in str((turn2.get("meta") or {}).get("service_route") or "")
    turn5 = payload["turn_results"][4]
    assert len(_scope_nav_refs(list(turn5.get("quick_replies") or []))) == 3
    assert "₽" in str(turn5.get("answer_text") or "")
    stream_turns = [row for row in payload["turn_results"] if row["endpoint"] == "/ask/stream"]
    assert len(stream_turns) == 2
    assert all("event: ui" in str(row.get("stream_text") or "") for row in stream_turns)
    assert get_audit_state().total_started == 0


def test_ask_and_stream_invoke_target_only_orchestration(
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
        build_retry1_attempt_marker_payload(baseline_commit="retry1-route"),
    )
    _install_retry1_http_fakes(monkeypatch)
    payload = run_http_harness(
        live=False,
        skip_live_prepare=True,
        attempt_marker_path=marker,
        call_ledger_path=ledger,
        artifact_paths=artifacts,
        monkeypatch=monkeypatch,
    )
    ask_count = sum(1 for row in payload["turn_results"] if row["endpoint"] == "/ask")
    stream_count = sum(1 for row in payload["turn_results"] if row["endpoint"] == "/ask/stream")
    assert ask_count == 6
    assert stream_count == 2
    assert all(row["automated_turn_verdict"] == "PASS" for row in payload["turn_results"])


def test_retry1_dry_run_cli() -> None:
    if LIVE_RAW_ARTIFACT_PATH.exists():
        pytest.skip("retry1 live artifacts present; dry-run blocked until artifacts removed")
    proc = subprocess.run(
        [sys.executable, "evals/v5/run_final_scope_widget_e2e_retry1_live.py", "--dry-run"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    idx = proc.stdout.rfind('"measurement_id"')
    start = proc.stdout.rfind("{", 0, idx)
    payload = json.loads(proc.stdout[start:])
    assert payload["measurement_id"] == MEASUREMENT_ID
    assert payload["dry_run"] is True
    assert payload["live_blocked"] is True
    assert payload["max_http_turns"] == MAX_HTTP_TURNS


def test_retry1_runner_has_no_deleted_module_imports() -> None:
    source = (_REPO_ROOT / "evals/v5/run_final_scope_widget_e2e_retry1_live.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert "orchestration.ask_turn" not in imported
