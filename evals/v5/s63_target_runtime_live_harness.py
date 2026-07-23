"""HTTP harness for S63 target FullContext delta live runtime eval."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from evals.v5.fullcontext_response_eval_contract import (
    HarnessConfigError,
    prepare_json_artifact_payload,
    sha256_file_hex,
)
from evals.v5.s63_target_runtime_live_contract import (
    ALLOWED_PROVIDER_ROLES,
    CLIENT_ID,
    DEFAULT_LIVE_ARTIFACT_PATHS,
    FROZEN_TURNS_HASH,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_AUDIT_LOG_PATH,
    LIVE_CALL_LEDGER_PATH,
    LIVE_MANIFEST_ARTIFACT_PATH,
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
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
    build_attempt_marker_payload,
    build_manual_review_seed,
    create_attempt_marker_exclusive,
    finalize_attempt_marker,
    ledger_entries_balanced,
    load_attempt_marker,
    load_frozen_turns,
    persist_attempt_marker,
)
from evals.v5.s63_target_runtime_live_provider_audit import (
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
    os.environ["TARGET_FULLCONTEXT_DEV"] = "1"
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


def _session_snapshot(sid: str) -> dict[str, Any]:
    from core.target_runtime_session import read_target_runtime_session

    state = read_target_runtime_session(sid)
    return {
        "last_service_id": state.last_service_id,
        "shown_fact_ids": list(state.shown_fact_ids),
        "shown_amplifier_refs": list(state.shown_amplifier_refs),
        "shown_consultation_value_refs": list(state.shown_consultation_value_refs),
        "followups": [{"ref": item.ref, "label": item.label} for item in state.followups],
    }


def pick_displayed_followup(quick_replies: list[dict[str, Any]]) -> dict[str, str] | None:
    for item in quick_replies:
        if not isinstance(item, dict):
            continue
        ref = str(item.get("ref") or "").strip()
        label = str(item.get("label") or "").strip()
        if ref and label:
            return {"ref": ref, "label": label}
    return None


def install_legacy_guards(monkeypatch: Any | None = None) -> None:
    def guard(name: str):
        def _forbidden(*args: object, **kwargs: object) -> object:
            record_legacy_hit(name)
            raise RuntimeError(f"s63_legacy_path_forbidden:{name}")

        return _forbidden

    targets = {
        "orchestration.ask_turn": "orchestrate_routing_after_resolver",
        "orchestration.pre_resolver_turn": (
            "get_chunk_by_ref",
            "orchestrate_price_widget_ref",
            "orchestrate_consult_symptom_ref",
            "build_promo_overview_payload",
        ),
        "core.md_chunks": "get_chunk_by_ref",
        "core.price_ref_routing": "orchestrate_price_widget_ref",
        "core.price_symptom_consult": "orchestrate_consult_symptom_ref",
        "core.promo_overview": "build_promo_overview_payload",
    }
    for module_name, attrs in targets.items():
        attr_names = attrs if isinstance(attrs, tuple) else (attrs,)
        for attr in attr_names:
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


def _execute_http_turn(
    client: Any,
    *,
    endpoint: str,
    sid: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    if endpoint != "/ask":
        raise RuntimeError(f"unsupported endpoint: {endpoint}")
    response = client.post(endpoint, json={**body, "sid": sid, "client_id": CLIENT_ID})
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


def _is_failure_route(route: str) -> bool:
    return any(marker in route for marker in _ERROR_ROUTE_MARKERS + _TERMINAL_ROUTE_MARKERS)


def evaluate_turn_gates(turn_result: dict[str, Any]) -> dict[str, Any]:
    flags: dict[str, bool] = {}
    route = _route_name(turn_result)
    meta = turn_result.get("meta") or {}
    answer_path = str(meta.get("answer_path") or meta.get("ui_source_family") or "")
    flags["http_completed"] = turn_result.get("status_code") == 200
    flags["target_answer_path"] = (
        "target_fullcontext" in answer_path or route.startswith("target_fullcontext")
    )
    flags["no_legacy_route"] = "retrieval_chunk" not in route and "legacy" not in route
    flags["materialized"] = _is_materialized(route)
    flags["no_error_route"] = not any(marker in route for marker in _ERROR_ROUTE_MARKERS)
    flags["no_terminal_defer"] = "target_fullcontext_terminal_defer" not in route

    turn_id = str(turn_result.get("turn_id") or "")
    if turn_id == "s63_turn_01_all_on_4_info":
        cta_key = str(meta.get("cta_key") or "").strip()
        flags["cta_widget_present"] = not cta_key or turn_result.get("cta") is not None
        flags["followup_visible"] = bool(turn_result.get("quick_replies"))
    if turn_id == "s63_turn_02_followup_ref":
        flags["followup_ref_used"] = bool(turn_result.get("followup_ref_used"))
        flags["target_nav_no_legacy"] = flags["target_answer_path"] and flags["no_legacy_route"]
    if turn_id == "s63_turn_03_doctors":
        flags["doctors_materialized"] = flags["materialized"]
        session_before = turn_result.get("session_before") or {}
        flags["session_service_all_on_4"] = (
            str(session_before.get("last_service_id") or "") == "all_on_4"
        )

    verdict = "PASS" if all(flags.values()) else "FAIL"
    return {"flags": flags, "automated_turn_verdict": verdict}


def ledger_role_totals_complete(role_totals: dict[str, int]) -> bool:
    return all(int(role_totals.get(role, 0)) > 0 for role in ALLOWED_PROVIDER_ROLES)


def evaluate_summary(
    turn_results: list[dict[str, Any]],
    audit: Any,
    *,
    ledger_balanced: bool = True,
) -> dict[str, Any]:
    turn1 = next(
        (row for row in turn_results if row.get("turn_id") == "s63_turn_01_all_on_4_info"),
        None,
    )
    turn2 = next(
        (row for row in turn_results if row.get("turn_id") == "s63_turn_02_followup_ref"),
        None,
    )
    turn3 = next(
        (row for row in turn_results if row.get("turn_id") == "s63_turn_03_doctors"),
        None,
    )

    followup_ref_pass = bool(turn2 and turn2.get("followup_ref_used"))
    turn1_followup_visible = bool(turn1 and turn1.get("quick_replies"))
    cta_widget_ok = True
    if turn1 is not None:
        meta = turn1.get("meta") or {}
        cta_key = str(meta.get("cta_key") or "").strip()
        cta_widget_ok = not cta_key or turn1.get("cta") is not None

    doctors_materialized = bool(
        turn3 and _is_materialized(_route_name(turn3))
    )
    session_continuity_ok = bool(
        turn3
        and str((turn3.get("session_before") or {}).get("last_service_id") or "") == "all_on_4"
    )
    all_materialized = all(
        _is_materialized(_route_name(row)) for row in turn_results
    )
    no_failure_routes = all(not _is_failure_route(_route_name(row)) for row in turn_results)

    technical = {
        "http_turns_completed": sum(
            1 for row in turn_results if row["gates"]["flags"]["http_completed"]
        ),
        "target_answer_path": sum(
            1 for row in turn_results if row["gates"]["flags"].get("target_answer_path")
        ),
        "legacy_hits": list(audit.legacy_hits),
        "fullcontext_build_count": audit.fullcontext_build_count,
        "followup_ref_pass": followup_ref_pass,
        "turn1_followup_visible": turn1_followup_visible,
        "cta_widget_ok": cta_widget_ok,
        "doctors_materialized": doctors_materialized,
        "session_continuity_ok": session_continuity_ok,
        "all_materialized": all_materialized,
        "no_failure_routes": no_failure_routes,
    }
    provider = {
        "total_calls": audit.total_started,
        "role_totals": dict(audit.role_totals),
        "retries": 0,
        "ledger_complete": ledger_role_totals_complete(dict(audit.role_totals)),
        "ledger_balanced": ledger_balanced,
    }
    automated_fail = (
        technical["http_turns_completed"] != MAX_HTTP_TURNS
        or technical["target_answer_path"] != MAX_HTTP_TURNS
        or technical["legacy_hits"]
        or technical["fullcontext_build_count"] != 1
        or not followup_ref_pass
        or not turn1_followup_visible
        or not cta_widget_ok
        or not doctors_materialized
        or not session_continuity_ok
        or not all_materialized
        or not no_failure_routes
        or provider["total_calls"] > MAX_PROVIDER_CALLS
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
) -> None:
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
            assert_attempt_marker_absent(
                attempt_marker_path,
                owner_override=False,
            )
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
            turns_hash=FROZEN_TURNS_HASH,
        ),
    )


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
    configure_process_env()
    turns_spec = load_frozen_turns()
    baseline_commit = _git_head_commit()
    sid = f"s63-live-{uuid.uuid4().hex[:12]}"

    if live and not skip_live_prepare:
        prepare_live_run(
            attempt_marker_path=attempt_marker_path,
            artifact_paths=artifact_paths,
            owner_override_attempt_marker=owner_override_attempt_marker,
            baseline_commit=baseline_commit,
        )

    import importlib

    import config

    importlib.reload(config)
    install_fullcontext_build_counter(monkeypatch)
    install_legacy_guards(monkeypatch)

    from core.target_runtime_client_context import clear_target_runtime_client_context_cache

    clear_target_runtime_client_context_cache()

    import app as app_module
    from orchestration.ask_turn import orchestrate_routing_after_resolver

    importlib.reload(app_module)
    install_legacy_guards(monkeypatch)
    setattr(app_module, "orchestrate_routing_after_resolver", orchestrate_routing_after_resolver)

    turn_results: list[dict[str, Any]] = []
    turn1_quick_replies: list[dict[str, Any]] = []

    with provider_audit_context(
        attempt_marker_path=attempt_marker_path,
        call_ledger_path=call_ledger_path,
    ) as audit:
        client = app_module.app.test_client()
        for spec in turns_spec["turns"]:
            turn_number = int(spec["turn"])
            set_current_turn(turn_number)
            endpoint = str(spec["endpoint"])
            request_body: dict[str, Any]
            followup_meta: dict[str, Any] = {"followup_ref_used": False}
            if spec.get("request_kind") == "followup_ref_from_turn_1":
                picked = pick_displayed_followup(turn1_quick_replies)
                if picked is not None:
                    request_body = {"q": "", "ref": picked["ref"]}
                    followup_meta = {
                        "followup_ref_used": True,
                        "followup_ref": picked["ref"],
                        "followup_label": picked["label"],
                    }
                else:
                    request_body = dict(spec["fallback_request"])
                    followup_meta = {
                        "followup_ref_used": False,
                        "followup_criterion": "FAIL_NO_DISPLAYED_FOLLOWUP",
                    }
            else:
                request_body = dict(spec["request"])

            session_before = _session_snapshot(sid)
            http_result = _execute_http_turn(
                client,
                endpoint=endpoint,
                sid=sid,
                body=request_body,
            )
            session_after = _session_snapshot(sid)
            if turn_number == 1:
                turn1_quick_replies = list(http_result.get("quick_replies") or [])

            turn_row = {
                "turn": turn_number,
                "turn_id": spec["turn_id"],
                "endpoint": endpoint,
                "request": request_body,
                **followup_meta,
                **http_result,
                "session_before": session_before,
                "session_after": session_after,
            }
            gates = evaluate_turn_gates(turn_row)
            turn_row["gates"] = gates
            turn_row["automated_turn_verdict"] = gates["automated_turn_verdict"]
            turn_row["recommended_manual_review"] = "PENDING"
            turn_results.append(turn_row)

        ledger_balanced = ledger_entries_balanced(call_ledger_path)
        summary = evaluate_summary(
            turn_results,
            audit,
            ledger_balanced=ledger_balanced,
        )
        summary["baseline_live_commit"] = baseline_commit
        summary["sid"] = sid
        summary["live_run"] = live
        payload = {"summary": summary, "turn_results": turn_results}

        if live:
            write_json_exclusive(raw_path, prepare_json_artifact_payload(payload))
            write_json_exclusive(result_path, prepare_json_artifact_payload(payload))
            result_sha256 = sha256_file_hex(result_path)
            ledger_sha256 = sha256_file_hex(call_ledger_path)
            manual_seed = build_manual_review_seed(
                turn_results=turn_results,
                result_sha256=result_sha256,
                baseline_commit=baseline_commit,
                provider_ledger_sha256=ledger_sha256,
            )
            write_json_exclusive(manual_review_path, manual_seed)
            manifest = prepare_json_artifact_payload(
                {
                    "measurement_id": MEASUREMENT_ID,
                    "baseline_live_commit": baseline_commit,
                    "turns_git_blob_hash": FROZEN_TURNS_HASH,
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
