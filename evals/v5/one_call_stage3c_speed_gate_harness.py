"""Offline production-faithful Speed Gate harness (Stage 3C)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import config

from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_fullcontext_messages import build_one_call_stable_prefix
from core.target_runtime_client_context import load_target_runtime_client_context
from evals.v5.one_call_stage3c_speed_gate_call_plan import (
    build_frozen_call_plan,
    prove_old_max_for_matrix_cases,
)
from evals.v5.one_call_stage3c_speed_gate_contract import (
    CLIENT_ID,
    LIVE_AUTHORIZED_ATTEMPT_ID,
    MEASUREMENT_ID,
    MODEL_SNAPSHOT,
    OLD_MAX_PROVIDER_CALLS_PER_TURN,
    ArmLabel,
    LatencyCategory,
)
from evals.v5.one_call_stage3c_speed_gate_fake_transport import (
    ProviderCallRecord,
    SpeedGateFakeTransport,
)
from evals.v5.one_call_stage3c_speed_gate_matrix import (
    FROZEN_SPEED_GATE_CASES,
    case_by_matrix_id,
    frozen_matrix_sha256,
    assert_frozen_matrix_unchanged,
)
from evals.v5.one_call_stage3c_speed_gate_patient_ttft import execute_stream_turn
from evals.v5.one_call_stage3c_speed_gate_speed_gate import evaluate_speed_gate
from session import mem_reset

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ARTIFACTS_ROOT = _REPO_ROOT / "evals" / "v5" / "artifacts"


class SpeedGateHarnessBlockedError(RuntimeError):
    """LIVE gate open while offline harness requested."""


def assert_offline_gate_closed() -> None:
    if LIVE_AUTHORIZED_ATTEMPT_ID is not None:
        raise SpeedGateHarnessBlockedError("stage3c_offline_live_gate_open")


def _git_head_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=_REPO_ROOT,
        text=True,
    ).strip()


def _stable_prefix_sha256() -> str:
    ctx = load_target_runtime_client_context(CLIENT_ID)
    catalog = ActiveServiceCatalogSnapshot.from_bundle(ctx.bundle)
    prefix = build_one_call_stable_prefix(
        identity=ctx.pack_identity,
        cached_full_context=ctx.cached_full_context,
        active_service_catalog=catalog,
    )
    return hashlib.sha256(prefix.encode("utf-8")).hexdigest()


def _deterministic_arm_order(case_index: int) -> tuple[ArmLabel, ArmLabel]:
    if case_index % 2 == 0:
        return ("NEW", "OLD")
    return ("OLD", "NEW")


def _sid_for(arm: ArmLabel, case_id: str) -> str:
    return f"stage3c-{arm.lower()}-{case_id}"


def _canned_answer(case_id: str) -> str:
    mapping = {
        "s01_microfact": "Да, у клиники есть городская парковка у здания; для пациентов — 2 часа бесплатно по пропуску на ресепшене.",
        "s02_service": "Имплантация зубов — лечение с восстановлением зуба коронкой на импланте.",
        "s03_exact_price": "Классическая имплантация Implantium — 76 200 ₽ за один зуб под ключ.",
        "s04_both_jaws": "Точную сумму All-on-4 на обе челюсти уточним на консультации с администратором.",
        "s05_doctor_trust": "Имплантацию выполняют врачи-имплантологи со стажем от 11 до 19 лет.",
        "s06_pain_fear": "Имплантация проходит под анестезией, лечение обычно безболезненное; на консультации врач всё объяснит.",
        "a01": "ignored",
        "a02": "ignored",
        "a03": "ignored",
    }
    return mapping.get(case_id, "Тестовый ответ Stage 3C.")


def _synthetic_timings_from_calls(
    calls: list[ProviderCallRecord],
    *,
    arm: ArmLabel,
) -> tuple[int | None, int]:
    """Offline dry-run only: supplement patient TTFT/total when Flask test client wall-clock is too coarse.

    LIVE runner and fake-transport LIVE path never call this — patient TTFT there comes only
    from SSE timing. Synthetic values are for offline harness math checks, not speed verdicts.
    """
    if not calls:
        return None, 0
    total_ms = sum(int(call.duration_ms) for call in calls)
    if arm == "NEW" and len(calls) == 1:
        return int(calls[0].duration_ms), total_ms
    return total_ms, total_ms


def _configure_arm(monkeypatch: Any, arm: ArmLabel) -> None:
    import app as app_module

    flag_on = arm == "NEW"
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", flag_on)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", flag_on)


def _evaluate_quality(
    case_id: str,
    *,
    arm: ArmLabel,
    http_result: dict[str, object],
    provider_call_count: int,
) -> dict[str, Any]:
    case = case_by_matrix_id(case_id)
    quality = case.quality
    answer = str(http_result.get("answer_text") or "").lower()
    meta = http_result.get("meta") or {}
    route = str(meta.get("service_route") or "")
    failures: list[str] = []

    if case.kind == "admin":
        if arm != "NEW":
            failures.append("admin_case_wrong_arm")
        if provider_call_count != 0:
            failures.append("admin_provider_calls_nonzero")
        if "sales_fast_admin" not in route and quality.expected_route == "admin":
            failures.append("admin_route_mismatch")
    else:
        allowed_calls = (
            OLD_MAX_PROVIDER_CALLS_PER_TURN
            if arm == "OLD"
            else quality.max_provider_calls
        )
        if provider_call_count > allowed_calls:
            failures.append("provider_call_budget_exceeded")
        if arm == "NEW" and provider_call_count > 1:
            failures.append("new_more_than_one_call")
        if quality.expected_route == "answer" and (
            "admin" in route
            or route.endswith("_error")
            or "verifier_blocked" in route
        ):
            failures.append(f"static_fallback_route:{route}")

    for token in quality.required_all:
        if token.lower() not in answer:
            failures.append(f"missing_required:{token}")

    for group in quality.required_any:
        if not any(term.lower() in answer for term in group):
            failures.append(f"missing_required_any:{','.join(group)}")

    for term in quality.forbidden_terms:
        if term.lower() in answer:
            failures.append(f"forbidden_term:{term}")

    normalized_answer = answer.replace(" ", "")
    for price_token in quality.forbidden_price_tokens:
        if price_token.replace(" ", "") in normalized_answer:
            failures.append(f"forbidden_price:{price_token}")

    if case.kind == "latency" and not http_result.get("widget_payload_ready"):
        failures.append("widget_payload_not_ready")

    return {
        "case_id": case_id,
        "arm": arm,
        "pass": not failures,
        "failures": failures,
        "provider_call_count": provider_call_count,
        "service_route": route,
    }


def run_offline_dry_run(
    monkeypatch: Any | None = None,
    *,
    attempt_id: str = "stage3c_offline_dry_run",
    write_artifacts: bool = True,
) -> dict[str, Any]:
    """Offline fake-transport harness via monkeypatch in parent process.

    Uses synthetic timing supplement (_synthetic_timings_from_calls) for offline math only.
    speed_gate verdict from this path is not a LIVE speed measurement.
    """
    assert_offline_gate_closed()
    assert_frozen_matrix_unchanged()

    if monkeypatch is None:
        import pytest

        monkeypatch = pytest.MonkeyPatch()
        ctx = monkeypatch.context()
        ctx.__enter__()
    else:
        ctx = None

    import ingress_gate
    import llm as llm_module
    from core import sales_one_plus_live_backend, target_runtime_llm_backends, turn_planner_llm

    transport = SpeedGateFakeTransport(answer_text="placeholder")

    def _budget_aware_fake_create(*, model: str, **kwargs: Any) -> Any:
        from core.provider_call_budget import record_provider_call_outcome, reserve_provider_call

        started = time.monotonic()
        call_index = reserve_provider_call(
            model=model,
            source=kwargs.get("provider_call_source"),
        )
        try:
            response = transport.chat_completions_create(model=model, **kwargs)
        except Exception:
            record_provider_call_outcome(
                call_index=call_index,
                outcome="error",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            raise
        record_provider_call_outcome(
            call_index=call_index,
            outcome="ok",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return response

    for module in (
        llm_module,
        ingress_gate,
        turn_planner_llm,
        target_runtime_llm_backends,
        sales_one_plus_live_backend,
    ):
        monkeypatch.setattr(module, "chat_completions_create", _budget_aware_fake_create)

    import app as app_module

    client = app_module.app.test_client()
    run_records: list[dict[str, Any]] = []
    old_calls_by_case: dict[str, int] = {}
    arm_cold_seen: dict[ArmLabel, bool] = {"OLD": False, "NEW": False}

    latency_cases = [case for case in FROZEN_SPEED_GATE_CASES if case.kind == "latency"]
    for case_index, case in enumerate(latency_cases):
        arm_order = _deterministic_arm_order(case_index)
        for arm in arm_order:
            transport.answer_text = _canned_answer(case.case_id)
            transport.reset_calls()
            _configure_arm(monkeypatch, arm)
            sid = _sid_for(arm, case.case_id)
            mem_reset(sid)
            latency_category: LatencyCategory = "cold" if not arm_cold_seen[arm] else "warm"
            arm_cold_seen[arm] = True

            http_result = execute_stream_turn(
                client,
                sid=sid,
                client_id=CLIENT_ID,
                body={"q": case.user_message},
            )
            provider_calls = len(transport.calls)
            synth_ttft, synth_total = _synthetic_timings_from_calls(
                transport.calls,
                arm=arm,
            )
            if synth_total > int(http_result.get("total_ms") or 0):
                http_result["total_ms"] = synth_total
            if synth_ttft is not None:
                current_ttft = http_result.get("patient_ttft_ms")
                if current_ttft is None or int(current_ttft) < synth_ttft:
                    http_result["patient_ttft_ms"] = synth_ttft
            if arm == "OLD":
                old_calls_by_case[case.case_id] = provider_calls

            quality = _evaluate_quality(
                case.case_id,
                arm=arm,
                http_result=http_result,
                provider_call_count=provider_calls,
            )
            run_records.append(
                {
                    "case_id": case.case_id,
                    "arm": arm,
                    "kind": case.kind,
                    "sid": sid,
                    "latency_category": latency_category,
                    "arm_order_index": case_index,
                    "requested_model": MODEL_SNAPSHOT,
                    "observed_models": [call.model for call in transport.calls],
                    "provider_call_count": provider_calls,
                    "provider_calls": [asdict(call) for call in transport.calls],
                    "patient_ttft_ms": http_result.get("patient_ttft_ms"),
                    "total_ms": http_result.get("total_ms"),
                    "patient_text_kind": http_result.get("patient_text_kind"),
                    "widget_payload_ready": http_result.get("widget_payload_ready"),
                    "quality": quality,
                    "meta": http_result.get("meta"),
                }
            )

    admin_records: list[dict[str, Any]] = []
    for case in FROZEN_SPEED_GATE_CASES:
        if case.kind != "admin":
            continue
        transport.reset_calls()
        _configure_arm(monkeypatch, "NEW")
        sid = _sid_for("NEW", case.case_id)
        mem_reset(sid)
        http_result = execute_stream_turn(
            client,
            sid=sid,
            client_id=CLIENT_ID,
            body={"q": case.user_message},
        )
        provider_calls = len(transport.calls)
        quality = _evaluate_quality(
            case.case_id,
            arm="NEW",
            http_result=http_result,
            provider_call_count=provider_calls,
        )
        admin_records.append(
            {
                "case_id": case.case_id,
                "arm": "NEW",
                "kind": "admin",
                "provider_call_count": provider_calls,
                "quality": quality,
                "meta": http_result.get("meta"),
            }
        )

    peak_old, old_proved = prove_old_max_for_matrix_cases(old_calls_by_case)
    call_plan = build_frozen_call_plan()

    warm_new_ttft = [
        int(row["patient_ttft_ms"])
        for row in run_records
        if row["arm"] == "NEW"
        and row["latency_category"] == "warm"
        and row["patient_ttft_ms"] is not None
    ]
    warm_old_ttft = [
        int(row["patient_ttft_ms"])
        for row in run_records
        if row["arm"] == "OLD"
        and row["latency_category"] == "warm"
        and row["patient_ttft_ms"] is not None
    ]
    warm_new_total = [
        int(row["total_ms"])
        for row in run_records
        if row["arm"] == "NEW" and row["latency_category"] == "warm"
    ]
    warm_old_total = [
        int(row["total_ms"])
        for row in run_records
        if row["arm"] == "OLD" and row["latency_category"] == "warm"
    ]

    all_quality = [row["quality"] for row in run_records] + [row["quality"] for row in admin_records]
    quality_pass = all(item.get("pass") for item in all_quality)
    new_calls_ok = all(
        int(row["provider_call_count"]) <= 1
        for row in run_records
        if row["arm"] == "NEW"
    ) and all(int(row["provider_call_count"]) == 0 for row in admin_records)

    speed_summary = evaluate_speed_gate(
        warm_new_ttft_ms=warm_new_ttft,
        warm_old_ttft_ms=warm_old_ttft,
        warm_new_total_ms=warm_new_total,
        warm_old_total_ms=warm_old_total,
        new_provider_calls_ok=new_calls_ok,
        quality_pass=quality_pass,
    )

    result = {
        "measurement_id": MEASUREMENT_ID,
        "attempt_id": attempt_id,
        "mode": "offline_fake_transport",
        "model_snapshot": MODEL_SNAPSHOT,
        "frozen_matrix_sha256": frozen_matrix_sha256(),
        "stable_fullcontext_prefix_sha256": _stable_prefix_sha256(),
        "baseline_commit": _git_head_commit(),
        "entry_points": {
            "http": "POST /ask/stream",
            "orchestration_old": "app._orchestrate_ask_turn with SALES_ONE_PLUS_ON=0",
            "orchestration_new": "orchestrate_sales_one_plus_ask_turn with SALES_ONE_PLUS_ON=1",
        },
        "call_plan": {
            "old_max_per_turn": call_plan.old_max_per_turn,
            "new_max_per_free_text": call_plan.new_max_per_free_text,
            "new_max_admin": call_plan.new_max_admin,
            "max_provider_calls_live": call_plan.max_provider_calls_live,
            "observed_old_peak_per_case": peak_old,
            "old_max_proved_offline": old_proved,
            "derivation_notes": list(call_plan.derivation_notes),
        },
        "latency_runs": run_records,
        "admin_runs": admin_records,
        "speed_gate": speed_summary,
        "live_gate": LIVE_AUTHORIZED_ATTEMPT_ID,
        "status": "completed",
    }

    if write_artifacts:
        artifact_dir = _ARTIFACTS_ROOT / attempt_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        result_path = artifact_dir / "result.json"
        serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        result_path.write_text(serialized, encoding="utf-8")

    if ctx is not None:
        ctx.__exit__(None, None, None)

    return result


def canned_answer_for_case(case_id: str) -> str:
    return _canned_answer(case_id)


def configure_arm_flags(arm: ArmLabel) -> None:
    import app as app_module

    flag_on = arm == "NEW"
    config.SALES_ONE_PLUS_ON = flag_on
    app_module.SALES_ONE_PLUS_ON = flag_on


def build_frozen_turn_plan() -> list[dict[str, object]]:
    turns: list[dict[str, object]] = []
    latency_cases = [case for case in FROZEN_SPEED_GATE_CASES if case.kind == "latency"]
    arm_cold_seen: dict[ArmLabel, bool] = {"OLD": False, "NEW": False}
    for case_index, case in enumerate(latency_cases):
        arm_order = _deterministic_arm_order(case_index)
        for arm in arm_order:
            latency_category: LatencyCategory = "cold" if not arm_cold_seen[arm] else "warm"
            arm_cold_seen[arm] = True
            turns.append(
                {
                    "case_id": case.case_id,
                    "arm": arm,
                    "kind": case.kind,
                    "user_message": case.user_message,
                    "latency_category": latency_category,
                    "arm_order_index": case_index,
                    "sid": _sid_for(arm, case.case_id),
                }
            )
    for case in FROZEN_SPEED_GATE_CASES:
        if case.kind != "admin":
            continue
        turns.append(
            {
                "case_id": case.case_id,
                "arm": "NEW",
                "kind": case.kind,
                "user_message": case.user_message,
                "latency_category": "warm",
                "arm_order_index": None,
                "sid": _sid_for("NEW", case.case_id),
            }
        )
    return turns


def evaluate_turn_quality(
    case_id: str,
    *,
    arm: ArmLabel,
    http_result: dict[str, object],
    provider_call_count: int,
) -> dict[str, Any]:
    return _evaluate_quality(
        case_id,
        arm=arm,
        http_result=http_result,
        provider_call_count=provider_call_count,
    )


def stable_prefix_sha256() -> str:
    return _stable_prefix_sha256()
