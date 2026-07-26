"""A9 patient-scope shadow quality harness.

Deterministic bridge/field fixtures run locally. Semantic turns use the
existing /ask/stream transport by default and are dependency-injected in unit
tests, so harness verification never needs a live endpoint.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TextIO

_EVAL_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _EVAL_DIR.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from contracts.planner_attempt import turn_frame_has_invalid_or_missing
from contracts.turn_plan import TurnPlan
from core.turn_frame_from_raw import build_turn_frame_from_raw

MATRIX_PATH = _REPO_ROOT / "evals" / "v5" / "demo" / "patient_scope_shadow_matrix.json"
PRESERVATION_PATH = _REPO_ROOT / "evals" / "v5" / "demo" / "preservation.json"
TOPIC_MATRIX_PATH = _REPO_ROOT / "evals" / "v5" / "demo" / "topic_shadow_matrix.json"

MATRIX_HASH = "d459073bbf8767f7ff590ece2958f7aa8cb18b25"
PRESERVATION_HASH = "c2072ca74c2da73bf657d793195d2eb6c8ba7bd5"
TOPIC_MATRIX_HASH = "dc356c9c738fb80a10cf0035508d7e8c8247979d"
CLIENT_ID = "demo"

AXES = ("extent", "jaw", "stage", "modifiers")
STATUS_VALUES = frozenset({"valid", "defaulted", "missing", "invalid"})
ERROR_VALUES = frozenset(
    {
        "patient_extent_invalid_type",
        "patient_extent_not_allowed",
        "patient_jaw_invalid_type",
        "patient_jaw_not_allowed",
        "patient_stage_invalid_type",
        "patient_stage_not_allowed",
        "patient_modifiers_invalid_type",
        "patient_modifier_not_allowed",
    }
)

TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "client_id",
        "purpose",
        "authority_decision_allowed",
        "expected_scope_schema",
        "scoring_contract",
        "bridge_cases",
        "field_isolation_cases",
        "single_turn_cases",
        "multi_turn_cases",
    }
)
BRIDGE_KEYS = frozenset(
    {"id", "raw_patient_situation", "expected_scope", "expected_field_status", "rationale"}
)
FIELD_KEYS = frozenset(
    {
        "id",
        "raw_payload",
        "expected_scope",
        "expected_field_status",
        "expected_field_errors",
        "expected_attempt_status",
        "rationale",
    }
)
SINGLE_KEYS = frozenset(
    {"id", "category", "question", "expected_scope", "expected_field_status", "evidence_refs", "rationale"}
)
MULTI_KEYS = frozenset({"id", "category", "turns", "session_boundary", "rationale"})
TURN_KEYS = frozenset(
    {"turn", "question", "score_current_scope", "expected_current_scope", "expected_current_field_status"}
)
RAW_PAYLOAD_KEYS = frozenset(
    {
        "route",
        "aspects",
        "service_id",
        "followup_of",
        "needs_clarify",
        "patient_situation",
        "brand_filter",
        "topic",
        "topic_confidence",
        "patient_scope",
    }
)

EXPECTED_SCOPE_SCHEMA: dict[str, Any] = {
    "extent": ["unknown", "one_tooth", "few_teeth", "full_arch"],
    "jaw": ["unknown", "upper", "lower", "both"],
    "stage": ["unknown", "extraction_context", "implant_placed"],
    "modifiers": ["reported_bone_deficit"],
}
EXPECTED_SCORING: dict[str, Any] = {
    "scope_match": "per_field_exact_normalized",
    "metadata_match": "per_field_status_and_stable_error",
    "planner_availability_separate_from_semantic_mismatch": True,
    "current_frame_is_current_turn_only": True,
    "legacy_session_carry_scored_separately": True,
    "one_live_call_per_live_turn": True,
    "retry_failed_case": False,
    "confidence_is_descriptive_only": True,
    "confidence_pass_threshold": None,
    "authority_decision_allowed": False,
    "product_parity_source": "existing_regression_suites",
}

EXPECTED_BRIDGE_IDS = (
    "patient_scope_a9_bridge_01_one_tooth",
    "patient_scope_a9_bridge_02_few_teeth",
    "patient_scope_a9_bridge_03_full_arch",
    "patient_scope_a9_bridge_04_upper",
    "patient_scope_a9_bridge_05_implant_placed",
    "patient_scope_a9_bridge_06_extraction_context",
    "patient_scope_a9_bridge_07_bone_context",
    "patient_scope_a9_bridge_08_urgent_boundary",
    "patient_scope_a9_bridge_09_generic_interest",
    "patient_scope_a9_bridge_10_unknown",
)
EXPECTED_BRIDGE_KINDS = (
    "one_tooth_missing",
    "few_teeth_missing",
    "full_arch_missing",
    "upper_jaw_missing_or_complex",
    "existing_implant_prosthetic_stage",
    "extraction_then_implant",
    "bone_deficit_or_grafting",
    "urgent_problem",
    "generic_implant_interest",
    "unknown",
)
EXPECTED_FIELD_IDS = (
    "patient_scope_a9_field_01_invalid_jaw_keeps_extent",
    "patient_scope_a9_field_02_invalid_extent_keeps_modifier",
    "patient_scope_a9_field_03_invalid_modifier_keeps_stage",
    "patient_scope_a9_field_04_missing_stage_keeps_composite",
)
EXPECTED_SINGLE_IDS = (
    "patient_scope_a9_live_01_one_tooth",
    "patient_scope_a9_live_02_few_teeth",
    "patient_scope_a9_live_03_full_arch",
    "patient_scope_a9_live_04_upper_full_arch",
    "patient_scope_a9_live_05_lower_jaw",
    "patient_scope_a9_live_06_both_jaws",
    "patient_scope_a9_live_07_implant_placed",
    "patient_scope_a9_live_08_planned_extraction",
    "patient_scope_a9_live_09_already_removed",
    "patient_scope_a9_live_10_bone_context",
    "patient_scope_a9_live_11_full_composite",
    "patient_scope_a9_live_12_scoped_price",
    "patient_scope_a9_live_13_one_tooth_extraction",
    "patient_scope_a9_live_14_upper_bone",
    "patient_scope_a9_live_15_information",
    "patient_scope_a9_live_16_generic_price",
    "patient_scope_a9_live_17_urgent_only",
    "patient_scope_a9_live_18_named_service",
    "patient_scope_a9_live_19_other_dental",
    "patient_scope_a9_live_20_booking_complaint",
)
EXPECTED_MULTI_IDS = (
    "patient_scope_a9_multi_01_safe_vague_price",
    "patient_scope_a9_multi_02_stale_carry",
    "patient_scope_a9_multi_03_topic_replacement",
    "patient_scope_a9_multi_04_conflicting_current_value",
    "patient_scope_a9_multi_05_jaw_arrives_second",
)
EXPECTED_BOUNDARIES = (
    "legacy_carry_not_materialized_into_current_shadow",
    "expired_legacy_snapshot_not_materialized",
    "explicit_topic_replacement_clears_legacy_scope",
    "explicit_current_values_win_without_frame_merge",
    "prior_extent_remains_separate_from_current_observation",
)

CASE_RESULT_KEYS = frozenset(
    {
        "index",
        "group",
        "case_id",
        "expected_scope",
        "observed_scope",
        "expected_field_status",
        "observed_field_status",
        "expected_field_errors",
        "observed_field_errors",
        "shadow_status",
        "status",
        "reason",
    }
)
TURN_RESULT_KEYS = frozenset(
    {
        "scenario_index",
        "scenario_id",
        "turn",
        "expected_scope",
        "observed_scope",
        "expected_field_status",
        "observed_field_status",
        "expected_field_errors",
        "observed_field_errors",
        "shadow_status",
        "status",
        "reason",
    }
)
BOUNDARY_RESULT_KEYS = frozenset(
    {
        "scenario_index",
        "scenario_id",
        "session_boundary",
        "observed_carried",
        "observed_carry_age",
        "observed_snapshot_kind",
        "status",
        "reason",
    }
)
SUMMARY_KEYS = frozenset(
    {
        "schema_version",
        "matrix_hash",
        "authority_decision_allowed",
        "planned_live_calls",
        "executed_live_calls",
        "bridge",
        "field_isolation",
        "single_turn",
        "multi_turn",
        "boundaries",
        "per_axis",
        "field_status_counts",
        "planner_availability",
        "composite",
        "product_parity_source",
        "overall_exit_code",
    }
)

_NULL_ERRORS = {axis: None for axis in AXES}


class HarnessConfigError(Exception):
    """Frozen spec or CLI configuration error (exit 2)."""


PostTurnFn = Callable[[dict[str, Any]], dict[str, Any]]
ResetSessionFn = Callable[[str], None]
AgeSnapshotFn = Callable[[str], dict[str, Any]]
ReadSnapshotFn = Callable[[str], dict[str, Any] | None]


def git_blob_hash(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def canonical_git_blob_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def _validate_hash(path: Path, expected: str, label: str) -> None:
    if git_blob_hash(canonical_git_blob_bytes(path)) != expected:
        raise HarnessConfigError(f"{label} hash mismatch")


def _exact_keys(payload: dict[str, Any], expected: frozenset[str], label: str) -> None:
    if set(payload) != expected:
        raise HarnessConfigError(f"{label} key mismatch")


def _validate_scope(scope: Any, label: str) -> None:
    if not isinstance(scope, dict) or set(scope) != set(AXES):
        raise HarnessConfigError(f"{label} scope mismatch")
    if scope["extent"] not in EXPECTED_SCOPE_SCHEMA["extent"]:
        raise HarnessConfigError(f"{label} extent mismatch")
    if scope["jaw"] not in EXPECTED_SCOPE_SCHEMA["jaw"]:
        raise HarnessConfigError(f"{label} jaw mismatch")
    if scope["stage"] not in EXPECTED_SCOPE_SCHEMA["stage"]:
        raise HarnessConfigError(f"{label} stage mismatch")
    modifiers = scope["modifiers"]
    if not isinstance(modifiers, list):
        raise HarnessConfigError(f"{label} modifiers type mismatch")
    if modifiers != sorted(set(modifiers)):
        raise HarnessConfigError(f"{label} modifiers order mismatch")
    if any(item not in EXPECTED_SCOPE_SCHEMA["modifiers"] for item in modifiers):
        raise HarnessConfigError(f"{label} modifier mismatch")


def _validate_statuses(statuses: Any, label: str) -> None:
    if not isinstance(statuses, dict) or set(statuses) != set(AXES):
        raise HarnessConfigError(f"{label} status keys mismatch")
    if any(value not in STATUS_VALUES for value in statuses.values()):
        raise HarnessConfigError(f"{label} status mismatch")


def _validate_errors(errors: Any, label: str) -> None:
    if not isinstance(errors, dict) or set(errors) != set(AXES):
        raise HarnessConfigError(f"{label} error keys mismatch")
    if any(value is not None and value not in ERROR_VALUES for value in errors.values()):
        raise HarnessConfigError(f"{label} error mismatch")


def _validate_frozen_spec(spec: dict[str, Any]) -> None:
    _exact_keys(spec, TOP_LEVEL_KEYS, "top-level")
    if spec["schema_version"] != "a9.patient_scope_shadow_matrix.v1":
        raise HarnessConfigError("schema version mismatch")
    if spec["client_id"] != CLIENT_ID:
        raise HarnessConfigError("client mismatch")
    if not isinstance(spec["purpose"], str) or not spec["purpose"].strip():
        raise HarnessConfigError("purpose mismatch")
    if spec["authority_decision_allowed"] is not False:
        raise HarnessConfigError("authority mismatch")
    if spec["expected_scope_schema"] != EXPECTED_SCOPE_SCHEMA:
        raise HarnessConfigError("scope schema mismatch")
    if spec["scoring_contract"] != EXPECTED_SCORING:
        raise HarnessConfigError("scoring contract mismatch")

    groups = (
        ("bridge_cases", BRIDGE_KEYS, 10),
        ("field_isolation_cases", FIELD_KEYS, 4),
        ("single_turn_cases", SINGLE_KEYS, 20),
        ("multi_turn_cases", MULTI_KEYS, 5),
    )
    ids: list[str] = []
    for group_name, keys, count in groups:
        rows = spec[group_name]
        if not isinstance(rows, list) or len(rows) != count:
            raise HarnessConfigError(f"{group_name} count mismatch")
        for index, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                raise HarnessConfigError(f"{group_name} row type mismatch")
            _exact_keys(row, keys, f"{group_name}[{index}]")
            case_id = row.get("id")
            if not isinstance(case_id, str) or not case_id:
                raise HarnessConfigError(f"{group_name} id mismatch")
            ids.append(case_id)

    if len(ids) != 39 or len(set(ids)) != 39:
        raise HarnessConfigError("case ids mismatch")

    ordered_ids = (
        EXPECTED_BRIDGE_IDS,
        EXPECTED_FIELD_IDS,
        EXPECTED_SINGLE_IDS,
        EXPECTED_MULTI_IDS,
    )
    for group_name, expected_ids in zip(
        ("bridge_cases", "field_isolation_cases", "single_turn_cases", "multi_turn_cases"),
        ordered_ids,
        strict=True,
    ):
        if tuple(row["id"] for row in spec[group_name]) != expected_ids:
            raise HarnessConfigError(f"{group_name} order mismatch")
    if tuple(row["raw_patient_situation"] for row in spec["bridge_cases"]) != EXPECTED_BRIDGE_KINDS:
        raise HarnessConfigError("bridge kinds mismatch")
    if tuple(row["session_boundary"] for row in spec["multi_turn_cases"]) != EXPECTED_BOUNDARIES:
        raise HarnessConfigError("session boundary order mismatch")

    for index, row in enumerate(spec["bridge_cases"], 1):
        _validate_scope(row["expected_scope"], f"bridge[{index}]")
        _validate_statuses(row["expected_field_status"], f"bridge[{index}]")

    for index, row in enumerate(spec["field_isolation_cases"], 1):
        _validate_scope(row["expected_scope"], f"field[{index}]")
        _validate_statuses(row["expected_field_status"], f"field[{index}]")
        _validate_errors(row["expected_field_errors"], f"field[{index}]")
        for axis in AXES:
            status = row["expected_field_status"][axis]
            error = row["expected_field_errors"][axis]
            if (status == "invalid") != (error is not None):
                raise HarnessConfigError(f"field[{index}] status error invariant")
        if set(row["raw_payload"]) != RAW_PAYLOAD_KEYS:
            raise HarnessConfigError(f"field[{index}] raw keys mismatch")
        if row["expected_attempt_status"] != "partial":
            raise HarnessConfigError(f"field[{index}] attempt mismatch")

    for index, row in enumerate(spec["single_turn_cases"], 1):
        _validate_scope(row["expected_scope"], f"single[{index}]")
        _validate_statuses(row["expected_field_status"], f"single[{index}]")
        refs = row["evidence_refs"]
        if not isinstance(refs, list) or not refs:
            raise HarnessConfigError(f"single[{index}] evidence mismatch")
        for ref in refs:
            source = str(ref).split("#", 1)[0]
            if not source or not (_REPO_ROOT / source).is_file():
                raise HarnessConfigError(f"single[{index}] evidence missing")

    turns = 0
    for s_index, scenario in enumerate(spec["multi_turn_cases"], 1):
        rows = scenario["turns"]
        if not isinstance(rows, list) or len(rows) != 2:
            raise HarnessConfigError(f"multi[{s_index}] turns mismatch")
        if [row.get("turn") for row in rows] != [1, 2]:
            raise HarnessConfigError(f"multi[{s_index}] order mismatch")
        for t_index, row in enumerate(rows, 1):
            _exact_keys(row, TURN_KEYS, f"multi[{s_index}].turn[{t_index}]")
            if row["score_current_scope"] is not True:
                raise HarnessConfigError(f"multi[{s_index}] scoring mismatch")
            _validate_scope(row["expected_current_scope"], f"multi[{s_index}].turn[{t_index}]")
            _validate_statuses(
                row["expected_current_field_status"],
                f"multi[{s_index}].turn[{t_index}]",
            )
            turns += 1
    if turns != 10 or 20 + turns != 30:
        raise HarnessConfigError("planned live calls mismatch")

    forbidden = {
        "observed",
        "actual",
        "current_output",
        "planner_output",
        "passed",
        "accuracy",
        "authority_ready",
        "recommended_route",
        "service_choice",
        "price_choice",
        "diagnosis",
        "answer",
    }
    text = json.dumps(spec, ensure_ascii=False).lower()
    leaked = sorted(item for item in forbidden if item in text)
    if leaked:
        raise HarnessConfigError("forbidden frozen field")


def load_and_validate_spec(path: Path = MATRIX_PATH) -> dict[str, Any]:
    _validate_hash(path, MATRIX_HASH, "patient scope matrix")
    _validate_hash(PRESERVATION_PATH, PRESERVATION_HASH, "preservation")
    _validate_hash(TOPIC_MATRIX_PATH, TOPIC_MATRIX_HASH, "topic matrix")
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise HarnessConfigError("matrix parse error") from error
    if not isinstance(spec, dict):
        raise HarnessConfigError("matrix root mismatch")
    _validate_frozen_spec(spec)
    return spec


def _neutral_raw(patient_situation: str | None) -> dict[str, Any]:
    return {
        "route": "content",
        "aspects": ["overview"],
        "service_id": None,
        "followup_of": None,
        "needs_clarify": False,
        "patient_situation": patient_situation,
        "brand_filter": None,
        "topic": None,
        "topic_confidence": 0.0,
    }


def _frame_observation(frame: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    scope = frame.get("patient_scope")
    field_meta = frame.get("field_meta")
    patient_meta = field_meta.get("patient_scope") if isinstance(field_meta, dict) else None
    if not isinstance(scope, dict) or not isinstance(patient_meta, dict):
        raise ValueError("patient scope missing")
    statuses: dict[str, Any] = {}
    errors: dict[str, Any] = {}
    for axis in AXES:
        meta = patient_meta.get(axis)
        if not isinstance(meta, dict):
            raise ValueError("patient meta missing")
        statuses[axis] = meta.get("status")
        errors[axis] = meta.get("error")
    return dict(scope), statuses, errors


def _compare_observation(
    *,
    expected_scope: dict[str, Any],
    observed_scope: dict[str, Any] | None,
    expected_status: dict[str, Any],
    observed_status: dict[str, Any] | None,
    expected_errors: dict[str, Any],
    observed_errors: dict[str, Any] | None,
) -> tuple[str, str]:
    if observed_scope is None or observed_status is None or observed_errors is None:
        return "ERROR", "shadow_frame_missing"
    for axis in AXES:
        if observed_scope.get(axis) != expected_scope.get(axis):
            return "FAIL", f"scope_value_mismatch:{axis}"
    for axis in AXES:
        if observed_status.get(axis) != expected_status.get(axis):
            return "FAIL", f"scope_status_mismatch:{axis}"
    for axis in AXES:
        if observed_errors.get(axis) != expected_errors.get(axis):
            return "FAIL", f"scope_error_mismatch:{axis}"
    return "PASS", "exact"


def _case_result(
    *,
    index: int,
    group: str,
    case_id: str,
    expected_scope: dict[str, Any],
    observed_scope: dict[str, Any] | None,
    expected_status: dict[str, Any],
    observed_status: dict[str, Any] | None,
    expected_errors: dict[str, Any],
    observed_errors: dict[str, Any] | None,
    shadow_status: str,
    status: str,
    reason: str,
) -> dict[str, Any]:
    out = {
        "index": index,
        "group": group,
        "case_id": case_id,
        "expected_scope": expected_scope,
        "observed_scope": observed_scope,
        "expected_field_status": expected_status,
        "observed_field_status": observed_status,
        "expected_field_errors": expected_errors,
        "observed_field_errors": observed_errors,
        "shadow_status": shadow_status,
        "status": status,
        "reason": reason,
    }
    if set(out) != CASE_RESULT_KEYS:  # pragma: no cover - construction invariant
        raise AssertionError("case result schema drift")
    return out


def run_bridge_cases(spec: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, row in enumerate(spec["bridge_cases"], 1):
        observed_scope = observed_status = observed_errors = None
        status, reason = "ERROR", "bridge_builder_error"
        try:
            frame = build_turn_frame_from_raw(
                _neutral_raw(row["raw_patient_situation"]),
                allowed_topics=frozenset(),
            )
            observed_scope, observed_status, observed_errors = _frame_observation(frame.model_dump())
            status, reason = _compare_observation(
                expected_scope=row["expected_scope"],
                observed_scope=observed_scope,
                expected_status=row["expected_field_status"],
                observed_status=observed_status,
                expected_errors=dict(_NULL_ERRORS),
                observed_errors=observed_errors,
            )
        except Exception:
            pass
        results.append(
            _case_result(
                index=index,
                group="bridge",
                case_id=row["id"],
                expected_scope=row["expected_scope"],
                observed_scope=observed_scope,
                expected_status=row["expected_field_status"],
                observed_status=observed_status,
                expected_errors=dict(_NULL_ERRORS),
                observed_errors=observed_errors,
                shadow_status="deterministic",
                status=status,
                reason=reason,
            )
        )
    return results


def run_field_isolation_cases(spec: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, row in enumerate(spec["field_isolation_cases"], 1):
        observed_scope = observed_status = observed_errors = None
        attempt_status = "degraded"
        status, reason = "ERROR", "field_builder_error"
        try:
            frame = build_turn_frame_from_raw(
                dict(row["raw_payload"]),
                allowed_topics=frozenset(),
            )
            observed_scope, observed_status, observed_errors = _frame_observation(frame.model_dump())
            strict_valid = True
            try:
                TurnPlan.model_validate(row["raw_payload"])
            except Exception:
                strict_valid = False
            attempt_status = (
                "ok"
                if strict_valid and not turn_frame_has_invalid_or_missing(frame)
                else "partial"
            )
            status, reason = _compare_observation(
                expected_scope=row["expected_scope"],
                observed_scope=observed_scope,
                expected_status=row["expected_field_status"],
                observed_status=observed_status,
                expected_errors=row["expected_field_errors"],
                observed_errors=observed_errors,
            )
            if status == "PASS" and attempt_status != row["expected_attempt_status"]:
                status, reason = "FAIL", "attempt_status_mismatch"
        except Exception:
            pass
        results.append(
            _case_result(
                index=10 + index,
                group="field_isolation",
                case_id=row["id"],
                expected_scope=row["expected_scope"],
                observed_scope=observed_scope,
                expected_status=row["expected_field_status"],
                observed_status=observed_status,
                expected_errors=row["expected_field_errors"],
                observed_errors=observed_errors,
                shadow_status=attempt_status,
                status=status,
                reason=reason,
            )
        )
    return results


def _default_post_turn(payload: dict[str, Any]) -> dict[str, Any]:
    from evals.v5.smoke_case_runner import post_ask_stream

    bot_url = os.getenv("BOT_URL", "http://127.0.0.1:5000")
    timeout = float(os.getenv("A9_SCOPE_TIMEOUT_SEC", "120"))
    return post_ask_stream(bot_url, payload, timeout)


def _default_reset_session(sid: str) -> None:
    from session import mem_reset

    mem_reset(sid)


def _default_read_snapshot(sid: str) -> dict[str, Any] | None:
    return None


def _default_age_snapshot(sid: str) -> dict[str, Any]:
    return {"prepared": False, "reason": "legacy_session_carry_removed"}


def _extract_live_observation(
    response: dict[str, Any],
) -> tuple[
    str,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any],
    str | None,
]:
    meta = response.get("meta") if isinstance(response, dict) else None
    mf = meta.get("metadata_first") if isinstance(meta, dict) else None
    if not isinstance(mf, dict):
        return "missing", None, None, None, {}, "metadata_first_missing"
    shadow_status = str(mf.get("turn_frame_shadow_status") or "missing")
    if shadow_status == "not_available":
        return shadow_status, None, None, None, mf, "shadow_not_available"
    if shadow_status == "degraded":
        return shadow_status, None, None, None, mf, "shadow_degraded"
    frame = mf.get("turn_frame_shadow")
    if not isinstance(frame, dict):
        return shadow_status, None, None, None, mf, "shadow_frame_missing"
    try:
        scope, statuses, errors = _frame_observation(frame)
    except Exception:
        return shadow_status, None, None, None, mf, "shadow_frame_missing"
    return shadow_status, scope, statuses, errors, mf, None


def _run_live_turn(
    *,
    post_turn_fn: PostTurnFn,
    payload: dict[str, Any],
    expected_scope: dict[str, Any],
    expected_status: dict[str, Any],
) -> tuple[
    str,
    str,
    str,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any],
]:
    try:
        response = post_turn_fn(payload)
    except Exception:
        return "ERROR", "transport_error", "transport_error", None, None, None, {}
    shadow_status, scope, statuses, errors, mf, extraction_error = _extract_live_observation(response)
    if extraction_error:
        return "ERROR", extraction_error, shadow_status, scope, statuses, errors, mf
    status, reason = _compare_observation(
        expected_scope=expected_scope,
        observed_scope=scope,
        expected_status=expected_status,
        observed_status=statuses,
        expected_errors=dict(_NULL_ERRORS),
        observed_errors=errors,
    )
    return status, reason, shadow_status, scope, statuses, errors, mf


def _turn_result(
    *,
    scenario_index: int,
    scenario_id: str,
    turn: int,
    expected_scope: dict[str, Any],
    observed_scope: dict[str, Any] | None,
    expected_status: dict[str, Any],
    observed_status: dict[str, Any] | None,
    observed_errors: dict[str, Any] | None,
    shadow_status: str,
    status: str,
    reason: str,
) -> dict[str, Any]:
    out = {
        "scenario_index": scenario_index,
        "scenario_id": scenario_id,
        "turn": turn,
        "expected_scope": expected_scope,
        "observed_scope": observed_scope,
        "expected_field_status": expected_status,
        "observed_field_status": observed_status,
        "expected_field_errors": dict(_NULL_ERRORS),
        "observed_field_errors": observed_errors,
        "shadow_status": shadow_status,
        "status": status,
        "reason": reason,
    }
    if set(out) != TURN_RESULT_KEYS:  # pragma: no cover
        raise AssertionError("turn result schema drift")
    return out


def _snapshot_kind(snapshot: dict[str, Any] | None) -> str | None:
    if not isinstance(snapshot, dict):
        return None
    kind = snapshot.get("kind")
    return str(kind) if isinstance(kind, str) and kind else None


def _scope_is_default(scope: dict[str, Any] | None, statuses: dict[str, Any] | None) -> bool:
    return bool(
        scope == {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []}
        and statuses == {axis: "defaulted" for axis in AXES}
    )


def _boundary_result(
    *,
    scenario_index: int,
    scenario: dict[str, Any],
    mf: dict[str, Any],
    snapshot: dict[str, Any] | None,
    scope: dict[str, Any] | None,
    statuses: dict[str, Any] | None,
    stale_preparation: dict[str, Any] | None,
    snapshot_read_error: bool = False,
) -> dict[str, Any]:
    boundary = scenario["session_boundary"]
    carried = mf.get("patient_situation_carried")
    carry_age = mf.get("patient_situation_carry_age")
    kind = _snapshot_kind(snapshot)
    status, reason = "PASS", "exact"

    if snapshot_read_error:
        status, reason = "ERROR", "boundary_snapshot_read_error"
    elif boundary == "legacy_carry_not_materialized_into_current_shadow":
        if carried is not True:
            status, reason = "FAIL", "boundary_carried_mismatch"
        elif not _scope_is_default(scope, statuses):
            status, reason = "FAIL", "boundary_current_merge"
        elif kind != "one_tooth_missing":
            status, reason = "FAIL", "boundary_snapshot_mismatch"
    elif boundary == "expired_legacy_snapshot_not_materialized":
        if not stale_preparation or stale_preparation.get("prepared") is not True:
            status = "ERROR"
            reason = str((stale_preparation or {}).get("reason") or "snapshot_not_expired")
        elif carried is not False:
            status, reason = "FAIL", "boundary_carried_mismatch"
        elif not _scope_is_default(scope, statuses):
            status, reason = "FAIL", "boundary_current_merge"
        elif kind == "one_tooth_missing":
            status, reason = "FAIL", "boundary_snapshot_mismatch"
    elif boundary == "explicit_topic_replacement_clears_legacy_scope":
        if carried is not False:
            status, reason = "FAIL", "boundary_carried_mismatch"
        elif not _scope_is_default(scope, statuses):
            status, reason = "FAIL", "boundary_current_merge"
        elif kind is not None:
            status, reason = "FAIL", "boundary_snapshot_mismatch"
    elif boundary == "explicit_current_values_win_without_frame_merge":
        want_scope = {"extent": "few_teeth", "jaw": "lower", "stage": "unknown", "modifiers": []}
        if carried is not False:
            status, reason = "FAIL", "boundary_carried_mismatch"
        elif scope != want_scope:
            status, reason = "FAIL", "boundary_current_merge"
        elif kind != "few_teeth_missing":
            status, reason = "FAIL", "boundary_snapshot_mismatch"
    elif boundary == "prior_extent_remains_separate_from_current_observation":
        if carried is not False:
            status, reason = "FAIL", "boundary_carried_mismatch"
        elif not (
            isinstance(scope, dict)
            and isinstance(statuses, dict)
            and scope.get("extent") == "unknown"
            and statuses.get("extent") == "defaulted"
            and scope.get("jaw") == "lower"
            and statuses.get("jaw") == "valid"
        ):
            status, reason = "FAIL", "boundary_current_merge"
        elif kind not in {None, "few_teeth_missing"}:
            status, reason = "FAIL", "boundary_snapshot_mismatch"
    else:  # pragma: no cover - frozen preflight owns values
        status, reason = "ERROR", "boundary_snapshot_mismatch"

    out = {
        "scenario_index": scenario_index,
        "scenario_id": scenario["id"],
        "session_boundary": boundary,
        "observed_carried": carried,
        "observed_carry_age": carry_age,
        "observed_snapshot_kind": kind,
        "status": status,
        "reason": reason,
    }
    if set(out) != BOUNDARY_RESULT_KEYS:  # pragma: no cover
        raise AssertionError("boundary result schema drift")
    return out


def _group_counts(rows: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row["status"]) for row in rows)
    return {
        "total": len(rows),
        "passed": counts["PASS"],
        "failed": counts["FAIL"],
        "errors": counts["ERROR"],
    }


def _axis_token(value: Any) -> str:
    if isinstance(value, list):
        return "+".join(value) if value else "__none__"
    if value is None:
        return "__unavailable__"
    return str(value)


def _build_axis_metrics(rows: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, int]]:
    per_axis: dict[str, Any] = {}
    status_counts: Counter[str] = Counter()
    for axis in AXES:
        confusion: dict[str, Counter[str]] = defaultdict(Counter)
        scoreable = exact = unknown = defaulted = missing = invalid = 0
        for row in rows:
            expected_scope = row["expected_scope"]
            observed_scope = row["observed_scope"]
            expected_status = row["expected_field_status"]
            observed_status = row["observed_field_status"]
            expected_errors = row["expected_field_errors"]
            observed_errors = row["observed_field_errors"]
            want = expected_scope.get(axis)
            got = observed_scope.get(axis) if isinstance(observed_scope, dict) else None
            confusion[_axis_token(want)][_axis_token(got)] += 1
            if isinstance(observed_scope, dict) and isinstance(observed_status, dict):
                scoreable += 1
                got_status = observed_status.get(axis)
                status_counts[str(got_status)] += 1
                unknown += int(got in ("unknown", []))
                defaulted += int(got_status == "defaulted")
                missing += int(got_status == "missing")
                invalid += int(got_status == "invalid")
                if (
                    got == want
                    and got_status == expected_status.get(axis)
                    and isinstance(observed_errors, dict)
                    and observed_errors.get(axis) == expected_errors.get(axis)
                ):
                    exact += 1
        per_axis[axis] = {
            "scoreable": scoreable,
            "exact": exact,
            "unknown": unknown,
            "defaulted": defaulted,
            "missing": missing,
            "invalid": invalid,
            "confusion": {key: dict(value) for key, value in sorted(confusion.items())},
        }
    return per_axis, dict(sorted(status_counts.items()))


def _is_composite(scope: dict[str, Any]) -> bool:
    known = int(scope.get("extent") != "unknown")
    known += int(scope.get("jaw") != "unknown")
    known += int(scope.get("stage") != "unknown")
    known += int(bool(scope.get("modifiers")))
    return known >= 2


def build_summary(
    *,
    case_results: Sequence[dict[str, Any]],
    turn_results: Sequence[dict[str, Any]],
    boundary_results: Sequence[dict[str, Any]],
    executed_live_calls: int,
) -> dict[str, Any]:
    if len(case_results) != 34 or len(turn_results) != 10 or len(boundary_results) != 5:
        raise ValueError("result denominator mismatch")
    grouped = {
        name: [row for row in case_results if row["group"] == name]
        for name in ("bridge", "field_isolation", "single_turn")
    }
    all_scope_rows = [*case_results, *turn_results]
    per_axis, status_counts = _build_axis_metrics(all_scope_rows)
    availability = Counter()
    for row in all_scope_rows:
        shadow_status = str(row["shadow_status"])
        if shadow_status in {"deterministic", "ok", "partial"} and row["observed_scope"] is not None:
            availability["available"] += 1
        elif shadow_status == "not_available":
            availability["not_available"] += 1
        elif shadow_status == "degraded":
            availability["degraded"] += 1
        else:
            availability["transport_error"] += 1
    composites = [row for row in all_scope_rows if _is_composite(row["expected_scope"])]
    any_problem = any(row["status"] != "PASS" for row in [*all_scope_rows, *boundary_results])
    summary = {
        "schema_version": "a9.patient_scope_shadow_summary.v1",
        "matrix_hash": MATRIX_HASH,
        "authority_decision_allowed": False,
        "planned_live_calls": 30,
        "executed_live_calls": executed_live_calls,
        "bridge": _group_counts(grouped["bridge"]),
        "field_isolation": _group_counts(grouped["field_isolation"]),
        "single_turn": _group_counts(grouped["single_turn"]),
        "multi_turn": _group_counts(turn_results),
        "boundaries": _group_counts(boundary_results),
        "per_axis": per_axis,
        "field_status_counts": status_counts,
        "planner_availability": {
            "available": availability["available"],
            "not_available": availability["not_available"],
            "degraded": availability["degraded"],
            "transport_error": availability["transport_error"],
        },
        "composite": {
            "total": len(composites),
            "exact": sum(row["status"] == "PASS" for row in composites),
        },
        "product_parity_source": "existing_regression_suites",
        "overall_exit_code": 1 if any_problem else 0,
    }
    if set(summary) != SUMMARY_KEYS:  # pragma: no cover
        raise AssertionError("summary schema drift")
    return summary


def _emit(prefix: str, payload: dict[str, Any], output: TextIO) -> None:
    output.write(f"{prefix} {json.dumps(payload, ensure_ascii=False, sort_keys=True)}\n")


def run_harness(
    *,
    post_turn_fn: PostTurnFn | None = None,
    reset_session_fn: ResetSessionFn | None = None,
    age_snapshot_fn: AgeSnapshotFn | None = None,
    read_snapshot_fn: ReadSnapshotFn | None = None,
    output: TextIO | None = None,
    spec_path: Path = MATRIX_PATH,
) -> dict[str, Any]:
    spec = load_and_validate_spec(spec_path)
    if post_turn_fn is None and os.getenv("E2E_USE_TEST_CLIENT", "").strip() != "1":
        raise HarnessConfigError("E2E test client required")
    post = post_turn_fn or _default_post_turn
    reset = reset_session_fn or _default_reset_session
    age_snapshot = age_snapshot_fn or _default_age_snapshot
    read_snapshot = read_snapshot_fn or _default_read_snapshot
    stream = output or sys.stdout
    run_id = uuid.uuid4().hex[:10]
    executed_live_calls = 0

    bridge_results = run_bridge_cases(spec)
    field_results = run_field_isolation_cases(spec)
    single_results: list[dict[str, Any]] = []

    for index, row in enumerate(spec["single_turn_cases"], 1):
        sid = f"a9_scope_single_{index}_{run_id}"
        reset(sid)
        executed_live_calls += 1
        status, reason, shadow_status, scope, statuses, errors, _ = _run_live_turn(
            post_turn_fn=post,
            payload={"q": row["question"], "sid": sid, "client_id": spec["client_id"]},
            expected_scope=row["expected_scope"],
            expected_status=row["expected_field_status"],
        )
        single_results.append(
            _case_result(
                index=14 + index,
                group="single_turn",
                case_id=row["id"],
                expected_scope=row["expected_scope"],
                observed_scope=scope,
                expected_status=row["expected_field_status"],
                observed_status=statuses,
                expected_errors=dict(_NULL_ERRORS),
                observed_errors=errors,
                shadow_status=shadow_status,
                status=status,
                reason=reason,
            )
        )

    turn_results: list[dict[str, Any]] = []
    boundary_results: list[dict[str, Any]] = []
    for scenario_index, scenario in enumerate(spec["multi_turn_cases"], 1):
        sid = f"a9_scope_multi_{scenario_index}_{run_id}"
        reset(sid)
        stale_preparation: dict[str, Any] | None = None
        last_mf: dict[str, Any] = {}
        last_scope: dict[str, Any] | None = None
        last_statuses: dict[str, Any] | None = None
        for row in scenario["turns"]:
            if row["turn"] == 2 and scenario["session_boundary"] == "expired_legacy_snapshot_not_materialized":
                try:
                    stale_preparation = age_snapshot(sid)
                except Exception:
                    stale_preparation = {"prepared": False, "reason": "snapshot_not_expired"}
            executed_live_calls += 1
            status, reason, shadow_status, scope, statuses, errors, mf = _run_live_turn(
                post_turn_fn=post,
                payload={"q": row["question"], "sid": sid, "client_id": spec["client_id"]},
                expected_scope=row["expected_current_scope"],
                expected_status=row["expected_current_field_status"],
            )
            turn_results.append(
                _turn_result(
                    scenario_index=scenario_index,
                    scenario_id=scenario["id"],
                    turn=row["turn"],
                    expected_scope=row["expected_current_scope"],
                    observed_scope=scope,
                    expected_status=row["expected_current_field_status"],
                    observed_status=statuses,
                    observed_errors=errors,
                    shadow_status=shadow_status,
                    status=status,
                    reason=reason,
                )
            )
            last_mf, last_scope, last_statuses = mf, scope, statuses
        snapshot_read_error = False
        try:
            snapshot = read_snapshot(sid)
        except Exception:
            snapshot = None
            snapshot_read_error = True
        boundary_results.append(
            _boundary_result(
                scenario_index=scenario_index,
                scenario=scenario,
                mf=last_mf,
                snapshot=snapshot,
                scope=last_scope,
                statuses=last_statuses,
                stale_preparation=stale_preparation,
                snapshot_read_error=snapshot_read_error,
            )
        )

    case_results = [*bridge_results, *field_results, *single_results]
    summary = build_summary(
        case_results=case_results,
        turn_results=turn_results,
        boundary_results=boundary_results,
        executed_live_calls=executed_live_calls,
    )
    for row in case_results:
        _emit("A9_SCOPE_CASE", row, stream)
    for row in turn_results:
        _emit("A9_SCOPE_TURN", row, stream)
    for row in boundary_results:
        _emit("A9_SCOPE_BOUNDARY", row, stream)
    _emit("A9_SCOPE_SUMMARY", summary, stream)
    return {
        "case_results": case_results,
        "turn_results": turn_results,
        "boundary_results": boundary_results,
        "summary": summary,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        print("ERROR: unexpected CLI arguments", file=sys.stderr)
        return 2
    try:
        result = run_harness()
    except HarnessConfigError:
        print("ERROR: harness configuration error", file=sys.stderr)
        return 2
    return int(result["summary"]["overall_exit_code"])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
