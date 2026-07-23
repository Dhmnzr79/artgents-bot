"""HTTP harness for S66 default FullContext authority live verification."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from core.target_runtime_widget import build_target_runtime_widget_cta
from evals.v5.fullcontext_response_eval_contract import (
    HarnessConfigError,
    prepare_json_artifact_payload,
    sha256_file_hex,
)
from evals.v5.s66_default_authority_live_contract import (
    ALLOWED_PROVIDER_ROLES,
    CLIENT_ID,
    DEFAULT_LIVE_ARTIFACT_PATHS,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_AUDIT_LOG_PATH,
    LIVE_CALL_LEDGER_PATH,
    LIVE_ENDPOINT,
    LIVE_MANIFEST_ARTIFACT_PATH,
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    LIVE_QUESTION,
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    MAX_HTTP_TURNS,
    MAX_PROVIDER_CALLS,
    MEASUREMENT_ID,
    OWNER_APPROVED_BOUNDARY_MODEL,
    OWNER_APPROVED_COMPOSER_MODEL,
    OWNER_APPROVED_INGRESS_MODEL,
    OWNER_APPROVED_PLANNER_MODEL,
    OWNER_APPROVED_VERIFIER_MODEL,
    AttemptMarkerExistsError,
    assert_attempt_marker_absent,
    assert_frozen_suite_unchanged,
    assert_live_artifacts_absent,
    assert_target_fullcontext_env_absent,
    build_attempt_marker_payload,
    build_manual_review_seed,
    create_attempt_marker_exclusive,
    finalize_attempt_marker,
    ledger_entries_balanced,
    load_attempt_marker,
    persist_attempt_marker,
    resolve_default_authority_proof,
)
from evals.v5.s66_default_authority_live_provider_audit import (
    provider_audit_context,
    record_fullcontext_build,
    record_legacy_hit,
    set_current_turn,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MATERIALIZED_ROUTE = "target_fullcontext_materialized"
_ERROR_ROUTE_MARKERS = (
    "target_fullcontext_error",
    "target_fullcontext_verifier_blocked",
)
_TERMINAL_ROUTE_MARKERS = (
    "target_fullcontext_terminal_defer",
    "target_fullcontext_terminal_clarify",
    "target_fullcontext_boundary_uncertain",
)


def _git_head_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=_REPO_ROOT,
        text=True,
    ).strip()


def configure_process_env() -> None:
    """Set approved model env vars only. Never set TARGET_FULLCONTEXT_DEV."""

    assert_target_fullcontext_env_absent()
    os.environ["MODEL_INGRESS_CLASSIFY"] = OWNER_APPROVED_INGRESS_MODEL
    os.environ["TURN_PLANNER_LLM_MODEL"] = OWNER_APPROVED_PLANNER_MODEL
    os.environ["TARGET_FULLCONTEXT_BOUNDARY_MODEL"] = OWNER_APPROVED_BOUNDARY_MODEL
    os.environ["TARGET_FULLCONTEXT_COMPOSER_MODEL"] = OWNER_APPROVED_COMPOSER_MODEL
    os.environ["TARGET_FULLCONTEXT_VERIFIER_MODEL"] = OWNER_APPROVED_VERIFIER_MODEL


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    serialized = prepare_json_artifact_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(serialized, ensure_ascii=False, indent=2) + "\n")
    except FileExistsError as exc:
        raise RuntimeError(f"artifact already exists: {path}") from exc


def install_legacy_guards(monkeypatch: Any | None = None) -> None:
    def guard(name: str):
        def _forbidden(*args: object, **kwargs: object) -> object:
            record_legacy_hit(name)
            raise RuntimeError(f"s66_legacy_path_forbidden:{name}")

        return _forbidden

    targets = {
        "orchestration.ask_turn": ("orchestrate_routing_after_resolver",),
        "orchestration.pre_resolver_turn": (
            "get_chunk_by_ref",
            "orchestrate_price_widget_ref",
            "orchestrate_consult_symptom_ref",
            "build_promo_overview_payload",
        ),
        "core.md_chunks": ("get_chunk_by_ref",),
        "core.price_ref_routing": ("orchestrate_price_widget_ref",),
        "core.price_symptom_consult": ("orchestrate_consult_symptom_ref",),
        "core.promo_overview": ("build_promo_overview_payload",),
        "source_routing": ("route_source",),
        "orchestration.composer_flow": ("try_composer_overlay",),
    }
    for module_name, attrs in targets.items():
        for attr in attrs:
            replacement = guard(f"{module_name}.{attr}")
            if monkeypatch is not None:
                monkeypatch.setattr(module_name, attr, replacement)
            else:
                module = __import__(module_name, fromlist=[attr])
                setattr(module, attr, replacement)


def install_fullcontext_build_counter(monkeypatch: Any | None = None) -> None:
    import core.target_cached_full_context as cached_module

    original = cached_module.build_target_cached_full_context

    def counted_build(*args: object, **kwargs: object):
        record_fullcontext_build()
        return original(*args, **kwargs)

    if monkeypatch is not None:
        monkeypatch.setattr(cached_module, "build_target_cached_full_context", counted_build)
    else:
        cached_module.build_target_cached_full_context = counted_build


def _execute_http_turn(client: Any, *, sid: str) -> dict[str, Any]:
    response = client.post(
        LIVE_ENDPOINT,
        json={"q": LIVE_QUESTION, "sid": sid, "client_id": CLIENT_ID},
    )
    payload = response.get_json()
    return {
        "status_code": response.status_code,
        "body": payload,
        "answer_text": str((payload or {}).get("answer") or ""),
        "meta": (payload or {}).get("meta") if isinstance((payload or {}).get("meta"), dict) else {},
        "quick_replies": list((payload or {}).get("quick_replies") or []),
        "cta": (payload or {}).get("cta"),
    }


def _route_name(turn_result: dict[str, Any]) -> str:
    meta = turn_result.get("meta") or {}
    return str(meta.get("service_route") or "")


def _is_materialized(route: str) -> bool:
    return _MATERIALIZED_ROUTE in route


def _cta_matches_authored(meta: dict[str, Any], cta: dict[str, Any] | None) -> bool:
    cta_key = str(meta.get("cta_key") or "").strip()
    if not cta_key:
        return True
    if not isinstance(cta, dict):
        return False
    expected = build_target_runtime_widget_cta(client_id=CLIENT_ID, selected_cta_key=cta_key)
    if expected is None:
        return False
    return (
        cta.get("key") == expected.get("key")
        and cta.get("text") == expected.get("text")
        and cta.get("action") == expected.get("action")
    )


def evaluate_turn_gates(turn_result: dict[str, Any]) -> dict[str, Any]:
    flags: dict[str, bool] = {}
    route = _route_name(turn_result)
    meta = turn_result.get("meta") or {}
    answer_path = str(meta.get("answer_path") or meta.get("ui_source_family") or "")
    flags["http_completed"] = turn_result.get("status_code") == 200
    flags["single_http_response"] = True
    flags["target_answer_path"] = (
        "target_fullcontext" in answer_path or route.startswith("target_fullcontext")
    )
    flags["no_legacy_route"] = "retrieval_chunk" not in route and "legacy" not in route
    flags["materialized"] = _is_materialized(route)
    flags["verified_materialized"] = flags["materialized"]
    flags["no_error_route"] = not any(marker in route for marker in _ERROR_ROUTE_MARKERS)
    flags["no_terminal_defer"] = not any(marker in route for marker in _TERMINAL_ROUTE_MARKERS)
    flags["cta_authored_match"] = _cta_matches_authored(meta, turn_result.get("cta"))
    flags["target_widget_present"] = bool(turn_result.get("answer_text"))
    verdict = "PASS" if all(flags.values()) else "FAIL"
    return {"flags": flags, "automated_turn_verdict": verdict}


def ledger_role_totals_complete(role_totals: dict[str, int]) -> bool:
    return all(int(role_totals.get(role, 0)) == 1 for role in ALLOWED_PROVIDER_ROLES)


def evaluate_summary(
    turn_result: dict[str, Any],
    audit: Any,
    *,
    authority_proof: dict[str, Any],
    ledger_balanced: bool = True,
) -> dict[str, Any]:
    route = _route_name(turn_result)
    technical = {
        "authority_proof": authority_proof,
        "http_turns_completed": 1 if turn_result["gates"]["flags"]["http_completed"] else 0,
        "target_answer_path": 1 if turn_result["gates"]["flags"].get("target_answer_path") else 0,
        "legacy_hits": list(audit.legacy_hits),
        "fullcontext_build_count": audit.fullcontext_build_count,
        "materialized": _is_materialized(route),
        "cta_authored_match": turn_result["gates"]["flags"].get("cta_authored_match"),
        "target_widget_present": turn_result["gates"]["flags"].get("target_widget_present"),
    }
    provider = {
        "total_calls": audit.total_started,
        "role_totals": dict(audit.role_totals),
        "retries": 0,
        "transport_errors": audit.transport_errors,
        "ledger_complete": ledger_role_totals_complete(dict(audit.role_totals)),
        "ledger_balanced": ledger_balanced,
    }
    automated_fail = (
        authority_proof.get("env_present") is not False
        or not authority_proof.get("config_default_resolved")
        or authority_proof.get("authority_source") != "config_default"
        or technical["http_turns_completed"] != MAX_HTTP_TURNS
        or technical["target_answer_path"] != MAX_HTTP_TURNS
        or technical["legacy_hits"]
        or technical["fullcontext_build_count"] != 1
        or not technical["materialized"]
        or not technical["cta_authored_match"]
        or not technical["target_widget_present"]
        or provider["total_calls"] > MAX_PROVIDER_CALLS
        or provider["transport_errors"] > 0
        or not provider["ledger_complete"]
        or not provider["ledger_balanced"]
    )
    automated_verdict = "AUTOMATED_FAIL" if automated_fail else "AUTOMATED_PASS"
    return {
        "technical": technical,
        "provider": provider,
        "automated_verdict": automated_verdict,
        "final_verdict": "PENDING_MANUAL_REVIEW" if automated_verdict == "AUTOMATED_PASS" else "FAIL",
        "rerun_blocked_without_owner_approval": True,
    }


def prepare_live_run(
    *,
    attempt_marker_path: Path = LIVE_ATTEMPT_MARKER_PATH,
    artifact_paths: tuple[Path, ...] = DEFAULT_LIVE_ARTIFACT_PATHS,
    owner_override_attempt_marker: bool = False,
    baseline_commit: str | None = None,
    authority_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    proof = authority_proof or resolve_default_authority_proof()
    if attempt_marker_path.exists():
        marker = load_attempt_marker(attempt_marker_path)
        started_calls = int(marker.get("started_provider_calls", 0))
        if started_calls > 0:
            raise AttemptMarkerExistsError(
                "attempt marker exists with started provider calls; rerun blocked"
            )
        if owner_override_attempt_marker and started_calls == 0:
            marker["status"] = "attempt_aborted_preflight"
            marker["abort_reason"] = "preflight_failure_before_first_provider_call"
            persist_attempt_marker(attempt_marker_path, marker)
            attempt_marker_path.unlink()
        else:
            assert_attempt_marker_absent(attempt_marker_path, owner_override=False)
    else:
        assert_attempt_marker_absent(
            attempt_marker_path,
            owner_override=owner_override_attempt_marker,
        )
    excluded = {attempt_marker_path.resolve()}
    preflight_paths = tuple(
        path for path in artifact_paths if path.resolve() not in excluded
    )
    assert_live_artifacts_absent(preflight_paths)
    create_attempt_marker_exclusive(
        attempt_marker_path,
        build_attempt_marker_payload(
            baseline_commit=baseline_commit or _git_head_commit(),
            authority_proof=proof,
        ),
    )
    return proof


def run_http_harness(
    *,
    live: bool,
    attempt_marker_path: Path = LIVE_ATTEMPT_MARKER_PATH,
    call_ledger_path: Path = LIVE_CALL_LEDGER_PATH,
    raw_path: Path = LIVE_RAW_ARTIFACT_PATH,
    result_path: Path = LIVE_RESULT_ARTIFACT_PATH,
    manifest_path: Path = LIVE_MANIFEST_ARTIFACT_PATH,
    manual_review_path: Path = LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    audit_log_path: Path = LIVE_AUDIT_LOG_PATH,
    artifact_paths: tuple[Path, ...] = DEFAULT_LIVE_ARTIFACT_PATHS,
    owner_override_attempt_marker: bool = False,
    monkeypatch: Any | None = None,
    skip_live_prepare: bool = False,
) -> dict[str, Any]:
    assert_frozen_suite_unchanged()
    authority_proof = resolve_default_authority_proof()
    configure_process_env()
    baseline_commit = _git_head_commit()
    sid = f"s66-live-{uuid.uuid4().hex[:12]}"

    if live and not skip_live_prepare:
        authority_proof = prepare_live_run(
            attempt_marker_path=attempt_marker_path,
            artifact_paths=artifact_paths,
            owner_override_attempt_marker=owner_override_attempt_marker,
            baseline_commit=baseline_commit,
            authority_proof=authority_proof,
        )

    import importlib

    import config

    importlib.reload(config)
    if not config.TARGET_FULLCONTEXT_DEV:
        raise HarnessConfigError("config must resolve default authority ON for S66")

    install_fullcontext_build_counter(monkeypatch)
    install_legacy_guards(monkeypatch)

    from core.target_runtime_client_context import clear_target_runtime_client_context_cache

    clear_target_runtime_client_context_cache()

    import app as app_module
    from orchestration.ask_turn import orchestrate_routing_after_resolver

    importlib.reload(app_module)
    if not app_module.TARGET_FULLCONTEXT_DEV:
        raise HarnessConfigError("app must import default authority ON for S66")
    install_legacy_guards(monkeypatch)
    setattr(app_module, "orchestrate_routing_after_resolver", orchestrate_routing_after_resolver)

    turn_results: list[dict[str, Any]] = []

    with provider_audit_context(
        attempt_marker_path=attempt_marker_path,
        call_ledger_path=call_ledger_path,
    ) as audit:
        client = app_module.app.test_client()
        set_current_turn(1)
        http_result = _execute_http_turn(client, sid=sid)
        turn_row = {
            "turn": 1,
            "turn_id": "s66_turn_01_default_authority_all_on_4",
            "endpoint": LIVE_ENDPOINT,
            "request": {"q": LIVE_QUESTION},
            **http_result,
        }
        gates = evaluate_turn_gates(turn_row)
        turn_row["gates"] = gates
        turn_row["automated_turn_verdict"] = gates["automated_turn_verdict"]
        turn_row["recommended_manual_review"] = "PENDING"
        turn_results.append(turn_row)

        ledger_balanced = ledger_entries_balanced(call_ledger_path)
        summary = evaluate_summary(
            turn_row,
            audit,
            authority_proof=authority_proof,
            ledger_balanced=ledger_balanced,
        )
        summary["baseline_live_commit"] = baseline_commit
        summary["sid"] = sid
        summary["live_run"] = live
        payload = {
            "summary": summary,
            "authority_proof": authority_proof,
            "turn_results": turn_results,
        }

        if live:
            write_json_exclusive(raw_path, prepare_json_artifact_payload(payload))
            write_json_exclusive(result_path, prepare_json_artifact_payload(payload))
            result_sha256 = sha256_file_hex(result_path)
            ledger_sha256 = sha256_file_hex(call_ledger_path)
            manual_seed = build_manual_review_seed(
                turn_result=turn_row,
                result_sha256=result_sha256,
                baseline_commit=baseline_commit,
                authority_proof=authority_proof,
                provider_ledger_sha256=ledger_sha256,
            )
            write_json_exclusive(manual_review_path, manual_seed)
            manifest = prepare_json_artifact_payload(
                {
                    "measurement_id": MEASUREMENT_ID,
                    "baseline_live_commit": baseline_commit,
                    "authority_proof": authority_proof,
                    "result_sha256": result_sha256,
                    "provider_ledger_sha256": ledger_sha256,
                    "attempt_marker_path": str(attempt_marker_path),
                    "call_ledger_path": str(call_ledger_path),
                    "rerun_blocked_without_owner_approval": True,
                }
            )
            write_json_exclusive(manifest_path, manifest)
            finalize_attempt_marker(
                attempt_marker_path,
                status="attempt_completed",
                total_provider_calls=audit.total_started,
                role_counts=dict(audit.role_totals),
            )
            audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with audit_log_path.open("x", encoding="utf-8") as handle:
                    handle.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
            except FileExistsError as exc:
                raise RuntimeError(f"artifact already exists: {audit_log_path}") from exc
        return payload
