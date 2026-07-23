"""HTTP harness for S62 target FullContext live runtime eval."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from evals.v5.fullcontext_response_eval_contract import prepare_json_artifact_payload, sha256_file_hex
from evals.v5.s62_target_runtime_live_contract import (
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
    assert_attempt_marker_absent,
    assert_frozen_suite_unchanged,
    assert_live_artifacts_absent,
    build_attempt_marker_payload,
    build_manual_review_seed,
    create_attempt_marker_exclusive,
    finalize_attempt_marker,
    load_frozen_turns,
)
from evals.v5.s62_target_runtime_live_provider_audit import (
    get_audit_state,
    provider_audit_context,
    record_fullcontext_build,
    record_legacy_hit,
    set_current_turn,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PRICE_REF_RE = re.compile(r"(цен|стоим|price)", re.I)


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


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value


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


def _pick_price_followup(quick_replies: list[dict[str, Any]]) -> dict[str, str] | None:
    for item in quick_replies:
        if not isinstance(item, dict):
            continue
        ref = str(item.get("ref") or "").strip()
        label = str(item.get("label") or "").strip()
        if not ref:
            continue
        if ref.startswith("price:") or _PRICE_REF_RE.search(label):
            return {"ref": ref, "label": label}
    return None


def install_legacy_guards(monkeypatch: Any | None = None) -> None:
    def guard(name: str):
        def _forbidden(*args: object, **kwargs: object) -> object:
            record_legacy_hit(name)
            raise RuntimeError(f"s62_legacy_path_forbidden:{name}")

        return _forbidden

    targets = {
        "orchestration.routing_after_resolver": "orchestrate_routing_after_resolver",
        "core.md_chunks": "get_chunk_by_ref",
        "core.price_ref_routing": "orchestrate_price_widget_ref",
        "core.price_symptom_consult": "orchestrate_consult_symptom_ref",
        "core.promo_overview": "build_promo_overview_payload",
    }
    for module_name, attr in targets.items():
        replacement = guard(attr)
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
    if endpoint == "/ask":
        response = client.post(endpoint, json={**body, "sid": sid, "client_id": CLIENT_ID})
        payload = response.get_json()
        return {
            "status_code": response.status_code,
            "body": payload,
            "answer_text": str((payload or {}).get("answer") or ""),
            "meta": (payload or {}).get("meta") if isinstance((payload or {}).get("meta"), dict) else {},
            "quick_replies": list((payload or {}).get("quick_replies") or []),
            "cta": (payload or {}).get("cta"),
            "stream_text": None,
        }
    if endpoint == "/ask/stream":
        response = client.post(endpoint, json={**body, "sid": sid, "client_id": CLIENT_ID})
        text = response.data.decode("utf-8")
        return {
            "status_code": response.status_code,
            "body": None,
            "answer_text": text,
            "meta": {},
            "quick_replies": [],
            "cta": None,
            "stream_text": text,
        }
    raise RuntimeError(f"unsupported endpoint: {endpoint}")


def _evaluate_turn_gates(turn_result: dict[str, Any]) -> dict[str, Any]:
    flags: dict[str, bool] = {}
    meta = turn_result.get("meta") or {}
    route = str(meta.get("service_route") or "")
    answer_path = str(meta.get("answer_path") or meta.get("ui_source_family") or "")
    flags["http_completed"] = turn_result.get("status_code") == 200
    flags["target_answer_path"] = (
        "target_fullcontext" in answer_path
        or route.startswith("target_fullcontext")
        or "target_fullcontext" in str(turn_result.get("stream_text") or "")
    )
    flags["no_legacy_route"] = "retrieval_chunk" not in route and "legacy" not in route
    flags["no_terminal_error"] = "target_fullcontext_error" not in route
    if turn_result.get("endpoint") == "/ask/stream":
        stream = str(turn_result.get("stream_text") or "")
        flags["stream_ui_done"] = "event: ui" in stream and "event: done" in stream
    verdict = "PASS" if all(flags.values()) else "FAIL"
    return {"flags": flags, "automated_turn_verdict": verdict}


def _evaluate_summary(turn_results: list[dict[str, Any]], audit: Any) -> dict[str, Any]:
    technical = {
        "http_turns_completed": sum(1 for row in turn_results if row["gates"]["flags"]["http_completed"]),
        "target_answer_path": sum(
            1 for row in turn_results if row["gates"]["flags"].get("target_answer_path")
        ),
        "legacy_hits": list(audit.legacy_hits),
        "fullcontext_build_count": audit.fullcontext_build_count,
        "followup_ref_pass": any(row.get("followup_ref_used") for row in turn_results),
    }
    provider = {
        "total_calls": audit.total_started,
        "role_totals": dict(audit.role_totals),
        "retries": 0,
    }
    automated_fail = (
        technical["http_turns_completed"] != MAX_HTTP_TURNS
        or technical["target_answer_path"] != MAX_HTTP_TURNS
        or technical["legacy_hits"]
        or technical["fullcontext_build_count"] != 1
        or provider["total_calls"] > MAX_PROVIDER_CALLS
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
    sid = f"s62-live-{uuid.uuid4().hex[:12]}"

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

    importlib.reload(app_module)

    turn_results: list[dict[str, Any]] = []
    followup_ref_used = False
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
                picked = _pick_price_followup(turn1_quick_replies)
                if picked is not None:
                    request_body = {"q": "", "ref": picked["ref"]}
                    followup_meta = {
                        "followup_ref_used": True,
                        "followup_ref": picked["ref"],
                        "followup_label": picked["label"],
                    }
                    followup_ref_used = True
                else:
                    request_body = dict(spec["fallback_request"])
                    followup_meta = {
                        "followup_ref_used": False,
                        "followup_criterion": "FAIL_NO_PRICE_FOLLOWUP",
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

            gates = _evaluate_turn_gates(
                {
                    **http_result,
                    "endpoint": endpoint,
                    "turn": turn_number,
                }
            )
            turn_results.append(
                {
                    "turn": turn_number,
                    "turn_id": spec["turn_id"],
                    "endpoint": endpoint,
                    "request": request_body,
                    **followup_meta,
                    **http_result,
                    "session_before": session_before,
                    "session_after": session_after,
                    "gates": gates,
                    "recommended_manual_review": "PENDING",
                }
            )

        summary = _evaluate_summary(turn_results, audit)
        summary["followup_ref_pass"] = followup_ref_used
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
