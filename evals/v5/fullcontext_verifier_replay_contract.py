"""Frozen contract for S52 FullContext verifier-only replay (offline prep; no live)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from evals.v5.fullcontext_response_eval_contract import (
    HarnessConfigError,
    LiveArtifactExistsError,
    LiveArtifactWriteError,
    V2_MATRIX_HASH,
    V2_MATRIX_PATH,
    assert_live_artifacts_absent,
    canonical_git_blob_bytes,
    git_blob_hash,
    prepare_json_artifact_payload,
    sha256_file_hex,
    validate_v2_matrix_hash,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
REPLAY_MATRIX_PATH = (
    _REPO_ROOT / "evals" / "v5" / "demo" / "fullcontext_verifier_replay_matrix.json"
)
REPLAY_MATRIX_HASH = "a273a58d96b00a76fd22b4d6fc9b97791df4f6d1"

FROZEN_SOURCE_RESULT_PATH = (
    _REPO_ROOT / "evals" / "v5" / "artifacts" / "fullcontext_response_eval_v2_live_result.json"
)
FROZEN_SOURCE_RESULT_SHA256 = (
    "273fb2dd7228bd31bb6f981399a77fcdb59336e07e99ba1ccd14005096bc39aa"
)

LIVE_ARTIFACTS_DIR = _REPO_ROOT / "evals" / "v5" / "artifacts"
LIVE_RAW_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "fullcontext_verifier_replay_live_raw.json"
LIVE_RESULT_ARTIFACT_PATH = (
    LIVE_ARTIFACTS_DIR / "fullcontext_verifier_replay_live_result.json"
)
LIVE_ATTEMPT_MARKER_PATH = (
    LIVE_ARTIFACTS_DIR / "fullcontext_verifier_replay_live_attempt.json"
)
LIVE_CALL_LEDGER_PATH = (
    LIVE_ARTIFACTS_DIR / "fullcontext_verifier_replay_live_call_ledger.jsonl"
)
LIVE_MANIFEST_ARTIFACT_PATH = (
    LIVE_ARTIFACTS_DIR / "fullcontext_verifier_replay_live_manifest.json"
)
LIVE_MANUAL_REVIEW_ARTIFACT_PATH = (
    LIVE_ARTIFACTS_DIR / "fullcontext_verifier_replay_manual_review.json"
)
DEFAULT_LIVE_ARTIFACT_PATHS = (
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_CALL_LEDGER_PATH,
    LIVE_MANIFEST_ARTIFACT_PATH,
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
)

MEASUREMENT_ID = "s52_fullcontext_verifier_replay"
MEASUREMENT_ID_LIVE = "s53_fullcontext_verifier_replay_live"
SUITE_ID = "s52_fullcontext_verifier_replay"
OWNER_APPROVED_SEMANTIC_MODEL = "qwen3.7-plus"
TERMINAL_CONTROL_CASE_ID = "fc_terminal_01"

ExpectedDecision = Literal["pass", "block"]
ObservedDecision = Literal["pass", "block", "error"]
AutomatedVerdict = Literal["AUTOMATED_PASS", "AUTOMATED_FAIL"]
FinalVerdict = Literal["PASS", "FAIL", "PENDING_MANUAL_REVIEW"]

BLOCKING_ISSUE_KINDS = frozenset(
    {
        "unsupported_clinic_claim",
        "personal_medical_conclusion",
        "material_external_medical_claim",
    }
)
NONBLOCKING_ISSUE_KINDS = frozenset({"minor_external_detail"})

BLAST_RADIUS_GROUPS = (
    "general_information",
    "pain_reassurance",
    "price",
    "payment",
    "doctor",
    "marketing",
    "commercial_answer",
    "grounded_medical",
)

MATERIALIZABLE_CASE_IDS = (
    "fc_info_01",
    "fc_info_02",
    "fc_info_03",
    "fc_pain_01",
    "fc_price_01",
    "fc_price_02",
    "fc_payment_01",
    "fc_commercial_02",
    "fc_doctor_01",
    "fc_marketing_01",
    "fc_medical_01",
    "fc_medical_02",
    "fc_medical_03",
    "fc_missing_01",
    "fc_missing_02",
    "fc_boundary_01",
    "fc_boundary_02",
    "fc_boundary_03",
    "fc_boundary_04",
)

EXPECTED_BLOCK_CASE_IDS = frozenset({"fc_medical_03", "fc_missing_01", "fc_missing_02"})

TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "suite_id",
        "measurement_id",
        "client_id",
        "frozen_before_first_live",
        "source_matrix_v2_path",
        "source_matrix_v2_git_blob_hash",
        "source_result_path",
        "source_result_sha256",
        "terminal_control_case_id",
        "model_recommendation",
        "proposed_automated_acceptance_gates",
        "final_verdict_contract",
        "cases",
    }
)

CASE_KEYS = frozenset(
    {
        "case_id",
        "source_matrix_v2_case_id",
        "source_result_sha256",
        "candidate_text_sha256",
        "expected_decision",
        "required_blocking_issue_kinds",
        "allowed_nonblocking_issue_kinds",
        "blast_radius_group",
        "rationale",
        "audit_source_refs",
    }
)

AUTOMATED_ACCEPTANCE_GATES = {
    "status": "owner_approved",
    "decision_match_rate_min": 1.0,
    "false_block_count_max": 0,
    "missed_block_count_max": 0,
    "verifier_provider_call_count_expected": 19,
    "composer_provider_call_count_max": 0,
    "retry_count_max": 0,
    "malformed_count_max": 0,
    "transport_error_count_max": 0,
    "backend_failure_count_max": 0,
    "invalid_offending_span_count_max": 0,
    "terminal_control_match_required": True,
}

MODEL_RECOMMENDATION = {
    "status": "owner_approved",
    "semantic_verifier_model": "qwen3.7-plus",
    "expected_verifier_provider_calls_materializable": 19,
    "expected_composer_provider_calls_materializable": 0,
    "expected_provider_calls_terminal": 0,
    "no_retry": True,
    "no_repair": True,
    "no_voting": True,
    "no_second_pass": True,
}

ATTEMPT_MARKER_EXISTS_CODE = "ATTEMPT_MARKER_EXISTS"


class AttemptMarkerExistsError(HarnessConfigError):
    """Replay live attempt marker already exists."""


def validate_replay_matrix_hash(*, path: Path = REPLAY_MATRIX_PATH) -> None:
    actual = git_blob_hash(canonical_git_blob_bytes(path))
    if actual != REPLAY_MATRIX_HASH:
        raise HarnessConfigError(
            f"replay matrix hash mismatch expected={REPLAY_MATRIX_HASH} actual={actual}"
        )


def validate_frozen_source_pins() -> None:
    validate_v2_matrix_hash(path=V2_MATRIX_PATH)
    actual = sha256_file_hex(FROZEN_SOURCE_RESULT_PATH)
    if actual != FROZEN_SOURCE_RESULT_SHA256:
        raise HarnessConfigError(
            "frozen source result sha mismatch "
            f"expected={FROZEN_SOURCE_RESULT_SHA256} actual={actual}"
        )


def _require_exact_keys(payload: dict[str, Any], *, allowed: frozenset[str], label: str) -> None:
    keys = set(payload.keys())
    if keys != allowed:
        missing = sorted(allowed - keys)
        extra = sorted(keys - allowed)
        raise HarnessConfigError(f"{label} key mismatch missing={missing} extra={extra}")


def _validate_replay_case(case: dict[str, Any]) -> None:
    _require_exact_keys(case, allowed=CASE_KEYS, label=f"replay case {case.get('case_id')}")
    if case["expected_decision"] not in {"pass", "block"}:
        raise HarnessConfigError(f"invalid expected_decision for {case['case_id']}")
    if case["source_result_sha256"] != FROZEN_SOURCE_RESULT_SHA256:
        raise HarnessConfigError(f"source_result_sha256 mismatch for {case['case_id']}")
    required = case["required_blocking_issue_kinds"]
    if case["expected_decision"] == "pass":
        if required:
            raise HarnessConfigError(f"pass case must not require blocking kinds: {case['case_id']}")
    else:
        if required != ["material_external_medical_claim"]:
            raise HarnessConfigError(
                f"block case must require material_external_medical_claim: {case['case_id']}"
            )
    if case["allowed_nonblocking_issue_kinds"] != ["minor_external_detail"]:
        raise HarnessConfigError(
            f"allowed_nonblocking_issue_kinds mismatch for {case['case_id']}"
        )
    if case["blast_radius_group"] not in BLAST_RADIUS_GROUPS and case["blast_radius_group"] not in {
        "missing_base",
        "medical_boundary",
    }:
        raise HarnessConfigError(f"unknown blast_radius_group for {case['case_id']}")


def validate_replay_matrix_spec(spec: dict[str, Any]) -> None:
    _require_exact_keys(spec, allowed=TOP_LEVEL_KEYS, label="replay matrix top-level")
    if spec["schema_version"] != 1:
        raise HarnessConfigError("schema_version mismatch")
    if spec["suite_id"] != SUITE_ID:
        raise HarnessConfigError("suite_id mismatch")
    if spec["measurement_id"] != MEASUREMENT_ID:
        raise HarnessConfigError("measurement_id mismatch")
    if spec["source_matrix_v2_git_blob_hash"] != V2_MATRIX_HASH:
        raise HarnessConfigError("source_matrix_v2_git_blob_hash mismatch")
    if spec["source_result_sha256"] != FROZEN_SOURCE_RESULT_SHA256:
        raise HarnessConfigError("source_result_sha256 mismatch")
    if spec["terminal_control_case_id"] != TERMINAL_CONTROL_CASE_ID:
        raise HarnessConfigError("terminal_control_case_id mismatch")
    cases = spec["cases"]
    if not isinstance(cases, list):
        raise HarnessConfigError("cases must be list")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise HarnessConfigError("case must be object")
        case_id = case.get("case_id")
        if not isinstance(case_id, str):
            raise HarnessConfigError("case_id must be string")
        if case_id in seen:
            raise HarnessConfigError(f"duplicate case_id: {case_id}")
        seen.add(case_id)
    if len(cases) != 19:
        raise HarnessConfigError(f"expected 19 materializable cases, got {len(cases)}")
    pass_count = 0
    block_count = 0
    for case in cases:
        _validate_replay_case(case)
        current_case_id = case["case_id"]
        if current_case_id != case["source_matrix_v2_case_id"]:
            raise HarnessConfigError(
                f"source_matrix_v2_case_id mismatch for {current_case_id}"
            )
        if case["expected_decision"] == "pass":
            pass_count += 1
        else:
            block_count += 1
    if seen != frozenset(MATERIALIZABLE_CASE_IDS):
        missing = sorted(frozenset(MATERIALIZABLE_CASE_IDS) - seen)
        extra = sorted(seen - frozenset(MATERIALIZABLE_CASE_IDS))
        raise HarnessConfigError(f"case_id set mismatch missing={missing} extra={extra}")
    if pass_count != 16 or block_count != 3:
        raise HarnessConfigError(
            f"expected 16 pass / 3 block, got pass={pass_count} block={block_count}"
        )


def load_replay_matrix(*, path: Path = REPLAY_MATRIX_PATH) -> dict[str, Any]:
    validate_frozen_source_pins()
    spec = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        raise HarnessConfigError("replay matrix must be object")
    validate_replay_matrix_spec(spec)
    validate_replay_matrix_hash(path=path)
    return spec


def _load_frozen_source_result() -> dict[str, Any]:
    validate_frozen_source_pins()
    payload = json.loads(FROZEN_SOURCE_RESULT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HarnessConfigError("frozen source result must be object")
    return payload


def load_candidate_text(*, case_id: str, replay_case: dict[str, Any] | None = None) -> str:
    if replay_case is not None and replay_case["case_id"] != case_id:
        raise HarnessConfigError("replay_case case_id mismatch")
    payload = _load_frozen_source_result()
    rows = payload.get("case_results")
    if not isinstance(rows, list):
        raise HarnessConfigError("frozen source result missing case_results")
    by_id = {row["case_id"]: row for row in rows if isinstance(row, dict) and "case_id" in row}
    if case_id not in by_id:
        raise HarnessConfigError(f"unknown case_id in frozen source result: {case_id}")
    text = by_id[case_id].get("response_text")
    if not isinstance(text, str) or not text.strip():
        raise HarnessConfigError(f"missing response_text for {case_id}")
    expected_sha = (
        replay_case["candidate_text_sha256"]
        if replay_case is not None
        else hashlib.sha256(text.encode("utf-8")).hexdigest()
    )
    actual_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if actual_sha != expected_sha:
        raise HarnessConfigError(
            f"candidate_text_sha256 mismatch for {case_id} expected={expected_sha} actual={actual_sha}"
        )
    return text


def load_v2_case(case_id: str) -> dict[str, Any]:
    from evals.v5.fullcontext_response_eval_contract import load_v2_matrix

    spec = load_v2_matrix()
    for case in spec["cases"]:
        if case["case_id"] == case_id:
            return case
    raise HarnessConfigError(f"v2 matrix missing case_id: {case_id}")


def replay_case_by_id(spec: dict[str, Any], case_id: str) -> dict[str, Any]:
    for case in spec["cases"]:
        if case["case_id"] == case_id:
            return case
    raise HarnessConfigError(f"unknown replay case_id: {case_id}")


def assert_replay_live_artifacts_absent(
    paths: tuple[Path, ...] = DEFAULT_LIVE_ARTIFACT_PATHS,
) -> None:
    assert_live_artifacts_absent(paths)


def build_attempt_marker_payload(*, matrix_hash: str = REPLAY_MATRIX_HASH) -> dict[str, Any]:
    return {
        "measurement_id": MEASUREMENT_ID,
        "matrix_git_blob_hash": matrix_hash,
        "source_result_sha256": FROZEN_SOURCE_RESULT_SHA256,
        "status": "in_progress",
        "started_provider_calls": 0,
        "max_verifier_provider_calls": 19,
        "max_composer_provider_calls": 0,
        "rerun_blocked_without_owner_approval": True,
    }


def create_attempt_marker_exclusive(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = prepare_json_artifact_payload(payload)
    body = json.dumps(serialized, ensure_ascii=False, indent=2) + "\n"
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(body)
    except FileExistsError as error:
        raise LiveArtifactWriteError(
            f"live attempt marker already exists; silent overwrite forbidden: {path}"
        ) from error


def assert_attempt_marker_absent(
    path: Path = LIVE_ATTEMPT_MARKER_PATH,
    *,
    owner_override: bool = False,
) -> None:
    if owner_override:
        return
    if path.exists():
        raise AttemptMarkerExistsError(
            f"{ATTEMPT_MARKER_EXISTS_CODE}: replay live attempt marker already exists: {path}"
        )


def load_attempt_marker(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HarnessConfigError("attempt marker must be object")
    return payload


def persist_attempt_marker(path: Path, payload: dict[str, Any]) -> None:
    serialized = prepare_json_artifact_payload(payload)
    path.write_text(
        json.dumps(serialized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def record_replay_provider_call_started(path: Path) -> int:
    marker = load_attempt_marker(path)
    started = int(marker.get("started_provider_calls", 0)) + 1
    marker["started_provider_calls"] = started
    persist_attempt_marker(path, marker)
    return started


def append_call_ledger_entry(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = prepare_json_artifact_payload(entry)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(serialized, ensure_ascii=False) + "\n")


def prepare_replay_live_run(
    *,
    attempt_marker_path: Path = LIVE_ATTEMPT_MARKER_PATH,
    artifact_paths: tuple[Path, ...] = DEFAULT_LIVE_ARTIFACT_PATHS,
    owner_override_attempt_marker: bool = False,
    matrix_hash: str = REPLAY_MATRIX_HASH,
) -> None:
    assert_attempt_marker_absent(
        attempt_marker_path,
        owner_override=owner_override_attempt_marker,
    )
    assert_replay_live_artifacts_absent(artifact_paths)
    create_attempt_marker_exclusive(
        attempt_marker_path,
        build_attempt_marker_payload(matrix_hash=matrix_hash),
    )


def _extract_semantic_issues(semantic_payload: object) -> list[dict[str, Any]]:
    if not isinstance(semantic_payload, dict):
        return []
    assessment_payload = semantic_payload.get("assessment")
    if isinstance(assessment_payload, dict):
        raw_issues = assessment_payload.get("issues")
    else:
        raw_issues = semantic_payload.get("issues")
    if isinstance(raw_issues, (list, tuple)):
        return [issue for issue in raw_issues if isinstance(issue, dict)]
    return []


def build_manual_review_seed(
    *,
    case_results: list[dict[str, Any]],
    result_sha256: str,
    matrix_hash: str = REPLAY_MATRIX_HASH,
) -> dict[str, Any]:
    cases = []
    for row in case_results:
        if row.get("terminal_control"):
            cases.append(
                {
                    "case_id": row["case_id"],
                    "review_status": "not_applicable",
                    "expected_decision": None,
                    "observed_decision": row.get("observed_decision"),
                    "semantic_issues": [],
                    "blocking_issue_kinds": [],
                    "offending_spans": [],
                    "decision_match": row.get("decision_match"),
                    "notes": "terminal control",
                }
            )
            continue
        semantic_payload = row.get("semantic_raw_payload")
        issues = _extract_semantic_issues(semantic_payload)
        blocking_kinds = [
            issue.get("kind")
            for issue in issues
            if issue.get("kind")
            in {
                "unsupported_clinic_claim",
                "personal_medical_conclusion",
                "material_external_medical_claim",
            }
        ]
        spans = [str(issue.get("offending_span", "")) for issue in issues if issue.get("offending_span")]
        cases.append(
            {
                "case_id": row["case_id"],
                "review_status": "pending",
                "expected_decision": row.get("expected_decision"),
                "observed_decision": row.get("observed_decision"),
                "semantic_issues": issues,
                "blocking_issue_kinds": blocking_kinds,
                "offending_spans": spans,
                "decision_match": row.get("decision_match"),
                "blocking_kind_match": row.get("blocking_kind_match"),
                "notes": "",
            }
        )
    return {
        "measurement_id": MEASUREMENT_ID_LIVE,
        "matrix_git_blob_hash": matrix_hash,
        "source_result_sha256": FROZEN_SOURCE_RESULT_SHA256,
        "result_sha256": result_sha256,
        "reviewer": "pending",
        "reviewed_at": None,
        "cases": cases,
    }


def replay_provider_call_violation(
    *,
    is_terminal: bool,
    composer_provider_calls: int,
    verifier_provider_calls: int,
    composer_invocations: int = 0,
    verifier_invocations: int = 0,
    offline_mode: bool = True,
) -> bool:
    if is_terminal:
        return composer_provider_calls != 0 or verifier_provider_calls != 0
    if offline_mode:
        return (
            composer_provider_calls != 0
            or verifier_provider_calls != 0
            or composer_invocations != 1
            or verifier_invocations != 1
        )
    return composer_provider_calls != 0 or verifier_provider_calls != 1


@dataclass(frozen=True, slots=True)
class ReplayDecisionMetrics:
    decision_match: bool
    false_block: bool
    missed_block: bool


def classify_replay_decision(
    *,
    observed: ObservedDecision,
    expected: ExpectedDecision,
) -> ReplayDecisionMetrics:
    decision_match = (
        (expected == "pass" and observed == "pass")
        or (expected == "block" and observed == "block")
    )
    false_block = expected == "pass" and observed == "block"
    missed_block = expected == "block" and observed != "block"
    return ReplayDecisionMetrics(
        decision_match=decision_match,
        false_block=false_block,
        missed_block=missed_block,
    )


def build_blast_radius_summary(case_rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for group in BLAST_RADIUS_GROUPS:
        rows = [row for row in case_rows if row.get("blast_radius_group") == group]
        false_blocks = [row["case_id"] for row in rows if row.get("false_block")]
        summary[group] = {
            "case_count": len(rows),
            "false_block_count": len(false_blocks),
            "false_block_case_ids": false_blocks,
            "all_expected_pass": all(row.get("expected_decision") == "pass" for row in rows),
        }
    return summary


def aggregate_replay_metrics(case_rows: list[dict[str, Any]]) -> dict[str, Any]:
    materializable = [row for row in case_rows if not row.get("terminal_control")]
    terminal_rows = [row for row in case_rows if row.get("terminal_control")]
    decision_matches = sum(1 for row in materializable if row.get("decision_match"))
    false_blocks = sum(1 for row in materializable if row.get("false_block"))
    missed_blocks = sum(1 for row in materializable if row.get("missed_block"))
    total_materializable = len(materializable)
    decision_match_rate = (
        decision_matches / total_materializable if total_materializable else 0.0
    )
    terminal_control_match = (
        len(terminal_rows) == 1
        and terminal_rows[0].get("observed_outcome") == "terminal_boundary_uncertain"
        and terminal_rows[0].get("composer_provider_call_count") == 0
        and terminal_rows[0].get("verifier_provider_call_count") == 0
    )
    return {
        "total_cases": len(case_rows),
        "materializable_case_count": total_materializable,
        "decision_match_count": decision_matches,
        "decision_match_rate": decision_match_rate,
        "false_block_count": false_blocks,
        "missed_block_count": missed_blocks,
        "verifier_provider_call_count": sum(
            row.get("verifier_provider_call_count", 0) for row in materializable
        ),
        "composer_provider_call_count": sum(
            row.get("composer_provider_call_count", 0) for row in case_rows
        ),
        "retry_count": sum(row.get("retry_count", 0) for row in case_rows),
        "malformed_count": sum(1 for row in case_rows if row.get("malformed")),
        "transport_error_count": sum(1 for row in case_rows if row.get("transport_error")),
        "backend_failure_count": sum(1 for row in case_rows if row.get("backend_failure")),
        "invalid_offending_span_count": sum(
            1 for row in case_rows if row.get("invalid_offending_span")
        ),
        "terminal_control_match": terminal_control_match,
        "blast_radius_summary": build_blast_radius_summary(materializable),
    }


def evaluate_automated_verdict(summary: dict[str, Any]) -> dict[str, Any]:
    gates = AUTOMATED_ACCEPTANCE_GATES
    checks = {
        "decision_match_rate": summary["decision_match_rate"] >= gates["decision_match_rate_min"],
        "false_block_count": summary["false_block_count"] <= gates["false_block_count_max"],
        "missed_block_count": summary["missed_block_count"] <= gates["missed_block_count_max"],
        "verifier_provider_call_count": summary["verifier_provider_call_count"]
        == gates["verifier_provider_call_count_expected"],
        "composer_provider_call_count": summary["composer_provider_call_count"]
        <= gates["composer_provider_call_count_max"],
        "retry_count": summary["retry_count"] <= gates["retry_count_max"],
        "malformed_count": summary["malformed_count"] <= gates["malformed_count_max"],
        "transport_error_count": summary["transport_error_count"]
        <= gates["transport_error_count_max"],
        "backend_failure_count": summary["backend_failure_count"]
        <= gates["backend_failure_count_max"],
        "invalid_offending_span_count": summary["invalid_offending_span_count"]
        <= gates["invalid_offending_span_count_max"],
        "terminal_control_match": summary["terminal_control_match"]
        if gates["terminal_control_match_required"]
        else True,
    }
    verdict: AutomatedVerdict = "AUTOMATED_PASS" if all(checks.values()) else "AUTOMATED_FAIL"
    return {"verdict": verdict, "gates": checks}


def evaluate_final_verdict(automated: dict[str, Any]) -> FinalVerdict:
    if automated["verdict"] != "AUTOMATED_PASS":
        return "FAIL"
    return "PENDING_MANUAL_REVIEW"
