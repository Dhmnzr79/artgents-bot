"""HTTP harness for FINAL scope/widget E2E live runtime eval."""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from contracts.ui_scope_action import build_ui_scope_ref, is_ui_scope_ref
from contracts.ui_stage_action import build_ui_stage_ref, is_ui_stage_ref
from evals.v5.fullcontext_response_eval_contract import (
    HarnessConfigError,
    prepare_json_artifact_payload,
    sha256_file_hex,
)
from evals.v5.final_scope_widget_e2e_live_contract import (
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
    assert_authority_env_before_import,
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
    planner_models_from_ledger,
)
from evals.v5.final_scope_widget_e2e_live_provider_audit import (
    provider_audit_context,
    record_fullcontext_build,
    record_legacy_hit,
    set_current_turn,
)
from evals.v5.smoke_case_runner import parse_sse_ui_payload

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

S69_FORBIDDEN_APP_SYMBOLS = frozenset(
    {
        "orchestrate_routing_after_resolver",
        "TARGET_FULLCONTEXT_DEV",
    }
)

_LEGACY_GUARD_TARGETS = {
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


def _git_head_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=_REPO_ROOT,
        text=True,
    ).strip()


def configure_process_env() -> None:
    """Authority env must be set before any config import in live path."""

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    os.environ["A9_PATIENT_SCOPE_AUTHORITY"] = "1"
    os.environ["MODEL_INGRESS_CLASSIFY"] = OWNER_APPROVED_INGRESS_MODEL
    os.environ["TURN_PLANNER_LLM_MODEL"] = OWNER_APPROVED_PLANNER_MODEL
    os.environ["TARGET_FULLCONTEXT_BOUNDARY_MODEL"] = OWNER_APPROVED_BOUNDARY_MODEL
    os.environ["TARGET_FULLCONTEXT_COMPOSER_MODEL"] = OWNER_APPROVED_COMPOSER_MODEL
    os.environ["TARGET_FULLCONTEXT_VERIFIER_MODEL"] = OWNER_APPROVED_VERIFIER_MODEL
    assert_authority_env_before_import()


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
    facts = state.patient_facts
    return {
        "last_service_id": state.last_service_id,
        "shown_fact_ids": list(state.shown_fact_ids),
        "shown_amplifier_refs": list(state.shown_amplifier_refs),
        "shown_consultation_value_refs": list(state.shown_consultation_value_refs),
        "followups": [{"ref": item.ref, "label": item.label} for item in state.followups],
        "patient_facts": (
            {
                "extent": facts.extent,
                "topic": facts.topic,
                "stage": facts.stage,
                "jaw": facts.jaw,
                "provenance": facts.provenance,
                "ref": facts.ref,
            }
            if facts is not None
            else None
        ),
    }


def _scope_nav_refs(quick_replies: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for item in quick_replies:
        if not isinstance(item, dict):
            continue
        ref = str(item.get("ref") or "").strip()
        if ref and is_ui_scope_ref(ref):
            refs.append(ref)
    return refs


def _stage_nav_refs(quick_replies: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for item in quick_replies:
        if not isinstance(item, dict):
            continue
        ref = str(item.get("ref") or "").strip()
        if ref and is_ui_stage_ref(ref):
            refs.append(ref)
    return refs


def _price_followup_refs(quick_replies: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for item in quick_replies:
        if not isinstance(item, dict):
            continue
        ref = str(item.get("ref") or "").strip()
        if ref.startswith("price:"):
            refs.append(ref)
    return refs


def _payment_stage_followup_refs(quick_replies: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for item in quick_replies:
        if not isinstance(item, dict):
            continue
        ref = str(item.get("ref") or "").strip()
        if "/stages" in ref:
            refs.append(ref)
    return refs


def _quick_reply_refs_unique(quick_replies: list[dict[str, Any]]) -> bool:
    refs = [str(item.get("ref") or "").strip() for item in quick_replies if isinstance(item, dict)]
    refs = [ref for ref in refs if ref]
    return len(refs) == len(set(refs))


def pick_scope_ref(
    quick_replies: list[dict[str, Any]],
    *,
    topic: str,
    extent: str,
) -> dict[str, str] | None:
    target = build_ui_scope_ref(topic=topic, extent=extent)  # type: ignore[arg-type]
    for item in quick_replies:
        if not isinstance(item, dict):
            continue
        ref = str(item.get("ref") or "").strip()
        label = str(item.get("label") or "").strip()
        if ref == target and label:
            return {"ref": ref, "label": label}
    return None


def pick_stage_ref(
    quick_replies: list[dict[str, Any]],
    *,
    topic: str,
    stage: str,
) -> dict[str, str] | None:
    target = build_ui_stage_ref(topic=topic, stage=stage)  # type: ignore[arg-type]
    for item in quick_replies:
        if not isinstance(item, dict):
            continue
        ref = str(item.get("ref") or "").strip()
        label = str(item.get("label") or "").strip()
        if ref == target and label:
            return {"ref": ref, "label": label}
    return None


def install_legacy_guards(monkeypatch: Any | None = None) -> None:
    def guard(name: str):
        def _forbidden(*args: object, **kwargs: object) -> object:
            record_legacy_hit(name)
            raise RuntimeError(f"fsw_legacy_path_forbidden:{name}")

        return _forbidden

    for module_name, attrs in _LEGACY_GUARD_TARGETS.items():
        if importlib.util.find_spec(module_name) is None:
            continue
        attr_names = attrs if isinstance(attrs, tuple) else (attrs,)
        for attr in attr_names:
            replacement = guard(f"{module_name}.{attr}")
            if monkeypatch is not None:
                module = importlib.import_module(module_name)
                if not hasattr(module, attr):
                    continue
                monkeypatch.setattr(module, attr, replacement)
            else:
                module = importlib.import_module(module_name)
                if hasattr(module, attr):
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


def _assert_post_s69_target_only_app(app_module: Any) -> None:
    if not hasattr(app_module, "_orchestrate_ask_turn"):
        raise HarnessConfigError("app._orchestrate_ask_turn missing (post-S69 target-only required)")
    for symbol in S69_FORBIDDEN_APP_SYMBOLS:
        if hasattr(app_module, symbol):
            raise HarnessConfigError(f"forbidden legacy app symbol present: {symbol}")
    app_path = Path(app_module.__file__).resolve()
    app_source = app_path.read_text(encoding="utf-8")
    if "orch_r = _orchestrate_ask_turn(data)" not in app_source:
        raise HarnessConfigError("/ask must dispatch via _orchestrate_ask_turn")
    if app_source.count("orch_r = _orchestrate_ask_turn(data)") < 2:
        raise HarnessConfigError("/ask and /ask/stream must both call _orchestrate_ask_turn")


def validate_runtime_seams(
    monkeypatch: Any | None = None,
    *,
    reload_runtime: bool = True,
) -> dict[str, Any]:
    """Import runtime, verify post-S69 target-only seams, return app client."""

    import config

    if reload_runtime:
        importlib.reload(config)
    elif not config.A9_PATIENT_SCOPE_AUTHORITY:
        importlib.reload(config)
    if not config.A9_PATIENT_SCOPE_AUTHORITY:
        raise HarnessConfigError("A9_PATIENT_SCOPE_AUTHORITY must be enabled for FINAL E2E")
    if config.TURN_PLANNER_LLM_MODEL != OWNER_APPROVED_PLANNER_MODEL:
        raise HarnessConfigError(
            f"planner model must be {OWNER_APPROVED_PLANNER_MODEL}; got {config.TURN_PLANNER_LLM_MODEL}"
        )

    install_fullcontext_build_counter(monkeypatch)
    install_legacy_guards(monkeypatch)

    from core.target_runtime_client_context import clear_target_runtime_client_context_cache

    clear_target_runtime_client_context_cache()

    import app as app_module

    if reload_runtime:
        importlib.reload(app_module)
    _assert_post_s69_target_only_app(app_module)
    install_legacy_guards(monkeypatch)

    return {
        "app_module": app_module,
        "client": app_module.app.test_client(),
        "config": config,
    }


def run_non_network_preflight(
    *,
    attempt_marker_path: Path,
    artifact_paths: tuple[Path, ...],
    monkeypatch: Any | None = None,
    assert_frozen_neighbors: Any | None = None,
) -> dict[str, Any]:
    configure_process_env()
    if assert_frozen_neighbors is not None:
        assert_frozen_neighbors()
    else:
        assert_frozen_suite_unchanged()
    load_frozen_turns()
    excluded = {attempt_marker_path.resolve()}
    preflight_paths = tuple(
        path for path in artifact_paths if path.resolve() not in excluded
    )
    assert_live_artifacts_absent(preflight_paths)
    assert_attempt_marker_absent(attempt_marker_path, owner_override=False)
    return validate_runtime_seams(monkeypatch)


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
        payload = parse_sse_ui_payload(text)
        return {
            "status_code": response.status_code,
            "body": payload,
            "answer_text": str(payload.get("answer") or ""),
            "meta": payload.get("meta") if isinstance(payload.get("meta"), dict) else {},
            "quick_replies": list(payload.get("quick_replies") or []),
            "cta": payload.get("cta"),
            "stream_text": text,
        }
    raise RuntimeError(f"unsupported endpoint: {endpoint}")


def _route_name(turn_result: dict[str, Any]) -> str:
    meta = turn_result.get("meta") or {}
    return str(meta.get("service_route") or "")


def _is_materialized(route: str) -> bool:
    return _MATERIALIZED_ROUTE in route


def _is_failure_route(route: str) -> bool:
    return any(marker in route for marker in _ERROR_ROUTE_MARKERS + _TERMINAL_ROUTE_MARKERS)


def _effective_scope_from_ctx() -> dict[str, Any] | None:
    try:
        from flask import request

        raw = request.ctx.get("effective_scope")
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def evaluate_turn_gates(turn_result: dict[str, Any]) -> dict[str, Any]:
    flags: dict[str, bool] = {}
    route = _route_name(turn_result)
    meta = turn_result.get("meta") or {}
    answer_path = str(meta.get("answer_path") or meta.get("ui_source_family") or "")
    expect = turn_result.get("expect") if isinstance(turn_result.get("expect"), dict) else {}
    quick = list(turn_result.get("quick_replies") or [])

    flags["http_completed"] = turn_result.get("status_code") == 200
    flags["target_answer_path"] = (
        "target_fullcontext" in answer_path or route.startswith("target_fullcontext")
    )
    flags["no_legacy_route"] = "retrieval_chunk" not in route and "w1" not in route.lower()
    flags["materialized"] = _is_materialized(route)
    flags["no_error_route"] = not any(marker in route for marker in _ERROR_ROUTE_MARKERS)
    flags["no_terminal_route"] = not any(marker in route for marker in _TERMINAL_ROUTE_MARKERS)
    flags["quick_refs_unique"] = _quick_reply_refs_unique(quick)

    if expect.get("stream_required"):
        stream = str(turn_result.get("stream_text") or "")
        flags["stream_ui_done"] = "event: ui" in stream and "event: done" in stream

    if "scope_nav_count" in expect:
        flags["scope_nav_count"] = len(_scope_nav_refs(quick)) == int(expect["scope_nav_count"])
    if "stage_nav_count" in expect:
        flags["stage_nav_count"] = len(_stage_nav_refs(quick)) == int(expect["stage_nav_count"])
    if "stage_nav_min" in expect:
        flags["stage_nav_min"] = len(_stage_nav_refs(quick)) >= int(expect["stage_nav_min"])
    if "max_price_followups" in expect:
        flags["max_price_followups"] = len(_price_followup_refs(quick)) <= int(
            expect["max_price_followups"]
        )
    if "max_payment_stage_followups" in expect:
        flags["max_payment_stage_followups"] = len(_payment_stage_followup_refs(quick)) <= int(
            expect["max_payment_stage_followups"]
        )
    if expect.get("ui_ref_used"):
        flags["ui_ref_used"] = bool(turn_result.get("ui_ref_used"))

    session_after = turn_result.get("session_after") or {}
    facts = session_after.get("patient_facts")
    if "session_extent" in expect and isinstance(facts, dict):
        flags["session_extent"] = facts.get("extent") == expect["session_extent"]
    if "session_stage" in expect and isinstance(facts, dict):
        flags["session_stage"] = facts.get("stage") == expect["session_stage"]

    scope = turn_result.get("effective_scope")
    if isinstance(scope, dict):
        if "effective_extent" in expect:
            flags["effective_extent"] = scope.get("extent") == expect["effective_extent"]
        if "effective_extent_source" in expect:
            axis = scope.get("extent_axis") if isinstance(scope.get("extent_axis"), dict) else {}
            flags["effective_extent_source"] = axis.get("source") == expect["effective_extent_source"]
        if "effective_stage" in expect:
            flags["effective_stage"] = scope.get("stage") == expect["effective_stage"]
        if "effective_topic" in expect:
            flags["effective_topic"] = scope.get("topic") == expect["effective_topic"]
        if expect.get("reported_context_absent", True):
            flags["reported_context_absent"] = scope.get("reported_context") is None

    response_stage = str(meta.get("response_stage") or "")
    if expect.get("response_stage"):
        flags["response_stage"] = response_stage == expect["response_stage"]

    verdict = "PASS" if all(flags.values()) else "FAIL"
    return {"flags": flags, "automated_turn_verdict": verdict}


def ledger_role_totals_complete(role_totals: dict[str, int]) -> bool:
    return all(int(role_totals.get(role, 0)) > 0 for role in ALLOWED_PROVIDER_ROLES)


def evaluate_summary(
    turn_results: list[dict[str, Any]],
    audit: Any,
    *,
    ledger_balanced: bool = True,
    call_ledger_path: Path = LIVE_CALL_LEDGER_PATH,
) -> dict[str, Any]:
    all_materialized = all(_is_materialized(_route_name(row)) for row in turn_results)
    no_failure_routes = all(not _is_failure_route(_route_name(row)) for row in turn_results)
    planner_models = planner_models_from_ledger(call_ledger_path)
    planner_plus_ok = bool(planner_models) and all(
        model == OWNER_APPROVED_PLANNER_MODEL for model in planner_models
    )

    technical = {
        "http_turns_completed": sum(
            1 for row in turn_results if row["gates"]["flags"]["http_completed"]
        ),
        "target_answer_path": sum(
            1 for row in turn_results if row["gates"]["flags"].get("target_answer_path")
        ),
        "legacy_hits": list(audit.legacy_hits),
        "fullcontext_build_count": audit.fullcontext_build_count,
        "all_materialized": all_materialized,
        "no_failure_routes": no_failure_routes,
        "turn_automated_pass": sum(
            1 for row in turn_results if row.get("automated_turn_verdict") == "PASS"
        ),
        "planner_model_plus_verified": planner_plus_ok,
        "planner_models_observed": planner_models,
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
        or not all_materialized
        or not no_failure_routes
        or technical["turn_automated_pass"] != MAX_HTTP_TURNS
        or not planner_plus_ok
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
        "manual_review_required": True,
    }


def prepare_live_run(
    *,
    attempt_marker_path: Path = LIVE_ATTEMPT_MARKER_PATH,
    artifact_paths: tuple[Path, ...] = DEFAULT_LIVE_ARTIFACT_PATHS,
    owner_override_attempt_marker: bool = False,
    baseline_commit: str | None = None,
    build_marker_payload: Any | None = None,
    assert_frozen_neighbors: Any | None = None,
    monkeypatch: Any | None = None,
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
            assert_attempt_marker_absent(attempt_marker_path, owner_override=False)
    else:
        assert_attempt_marker_absent(
            attempt_marker_path,
            owner_override=owner_override_attempt_marker,
        )
    run_non_network_preflight(
        attempt_marker_path=attempt_marker_path,
        artifact_paths=artifact_paths,
        monkeypatch=monkeypatch,
        assert_frozen_neighbors=assert_frozen_neighbors,
    )
    marker_builder = build_marker_payload or (
        lambda *, baseline_commit, turns_hash: build_attempt_marker_payload(
            baseline_commit=baseline_commit,
            turns_hash=turns_hash,
        )
    )
    create_attempt_marker_exclusive(
        attempt_marker_path,
        marker_builder(
            baseline_commit=baseline_commit or _git_head_commit(),
            turns_hash=FROZEN_TURNS_HASH,
        ),
    )


def _resolve_request_body(
    spec: dict[str, Any],
    *,
    turn_outputs: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    meta: dict[str, Any] = {"ui_ref_used": False}
    kind = spec.get("request_kind")
    if kind == "ui_scope_ref_from_turn":
        from_turn = int(spec["from_turn"])
        prior = turn_outputs[from_turn]
        picked = pick_scope_ref(
            list(prior.get("quick_replies") or []),
            topic=str(spec["pick_topic"]),
            extent=str(spec["pick_extent"]),
        )
        if picked is None:
            raise HarnessConfigError(
                f"missing scope ref from_turn={from_turn} extent={spec['pick_extent']}"
            )
        meta.update({"ui_ref_used": True, **picked})
        return {"q": "", "ref": picked["ref"]}, meta
    if kind == "ui_stage_ref_from_turn":
        from_turn = int(spec["from_turn"])
        prior = turn_outputs[from_turn]
        picked = pick_stage_ref(
            list(prior.get("quick_replies") or []),
            topic=str(spec["pick_topic"]),
            stage=str(spec["pick_stage"]),
        )
        if picked is None:
            raise HarnessConfigError(
                f"missing stage ref from_turn={from_turn} stage={spec['pick_stage']}"
            )
        meta.update({"ui_ref_used": True, **picked})
        return {"q": "", "ref": picked["ref"]}, meta
    return dict(spec["request"]), meta


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
    measurement_id: str = MEASUREMENT_ID,
    build_marker_payload: Any | None = None,
    assert_frozen_neighbors: Any | None = None,
) -> dict[str, Any]:
    configure_process_env()
    turns_spec = load_frozen_turns()
    baseline_commit = _git_head_commit()
    sid = f"fsw-live-{uuid.uuid4().hex[:12]}"

    if live and not skip_live_prepare:
        prepare_live_run(
            attempt_marker_path=attempt_marker_path,
            artifact_paths=artifact_paths,
            owner_override_attempt_marker=owner_override_attempt_marker,
            baseline_commit=baseline_commit,
            build_marker_payload=build_marker_payload,
            assert_frozen_neighbors=assert_frozen_neighbors,
            monkeypatch=monkeypatch,
        )
        seam_ctx = validate_runtime_seams(monkeypatch)
    elif skip_live_prepare and attempt_marker_path.exists():
        configure_process_env()
        if assert_frozen_neighbors is not None:
            assert_frozen_neighbors()
        else:
            assert_frozen_suite_unchanged()
        load_frozen_turns()
        seam_ctx = validate_runtime_seams(monkeypatch, reload_runtime=False)
    else:
        seam_ctx = run_non_network_preflight(
            attempt_marker_path=attempt_marker_path,
            artifact_paths=artifact_paths,
            monkeypatch=monkeypatch,
            assert_frozen_neighbors=assert_frozen_neighbors,
        )

    app_module = seam_ctx["app_module"]
    client = seam_ctx["client"]

    turn_results: list[dict[str, Any]] = []
    turn_outputs: dict[int, dict[str, Any]] = {}

    with provider_audit_context(
        attempt_marker_path=attempt_marker_path,
        call_ledger_path=call_ledger_path,
    ) as audit:
        for spec in turns_spec["turns"]:
            turn_number = int(spec["turn"])
            if spec.get("fresh_sid"):
                sid = f"fsw-live-{uuid.uuid4().hex[:12]}"
            set_current_turn(turn_number)
            endpoint = str(spec["endpoint"])
            request_body, ref_meta = _resolve_request_body(spec, turn_outputs=turn_outputs)
            session_before = _session_snapshot(sid)
            http_result = _execute_http_turn(
                client,
                endpoint=endpoint,
                sid=sid,
                body=request_body,
            )
            session_after = _session_snapshot(sid)
            turn_row = {
                "turn": turn_number,
                "turn_id": spec["turn_id"],
                "endpoint": endpoint,
                "sid": sid,
                "request": request_body,
                "expect": dict(spec.get("expect") or {}),
                "effective_scope": _effective_scope_from_ctx(),
                **ref_meta,
                **http_result,
                "session_before": session_before,
                "session_after": session_after,
            }
            gates = evaluate_turn_gates(turn_row)
            turn_row["gates"] = gates
            turn_row["automated_turn_verdict"] = gates["automated_turn_verdict"]
            turn_row["recommended_manual_review"] = "PENDING"
            turn_results.append(turn_row)
            turn_outputs[turn_number] = turn_row

        ledger_balanced = ledger_entries_balanced(call_ledger_path)
        summary = evaluate_summary(
            turn_results,
            audit,
            ledger_balanced=ledger_balanced,
            call_ledger_path=call_ledger_path,
        )
        summary["baseline_live_commit"] = baseline_commit
        summary["primary_sid"] = sid
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
                    "measurement_id": measurement_id,
                    "baseline_live_commit": baseline_commit,
                    "turns_git_blob_hash": FROZEN_TURNS_HASH,
                    "result_sha256": result_sha256,
                    "provider_ledger_sha256": ledger_sha256,
                    "attempt_marker_path": str(attempt_marker_path),
                    "call_ledger_path": str(call_ledger_path),
                    "a9_patient_scope_authority": "1",
                    "planner_model": OWNER_APPROVED_PLANNER_MODEL,
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


__all__ = [
    "configure_process_env",
    "evaluate_summary",
    "evaluate_turn_gates",
    "pick_scope_ref",
    "pick_stage_ref",
    "prepare_live_run",
    "run_http_harness",
    "run_non_network_preflight",
    "validate_runtime_seams",
]
