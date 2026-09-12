"""Frozen contract for S57 compact FullContext quality eval (offline prep; no live)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from evals.v5.fullcontext_response_eval_contract import (
    AUTOMATED_THRESHOLDS_STATUS,
    AttemptMarkerExistsError,
    FINAL_GATES_STATUS,
    HarnessConfigError,
    LiveArtifactExistsError,
    LiveArtifactWriteError,
    aggregate_automated_metrics,
    build_literal_and_semantic_extensions,
    canonical_git_blob_bytes,
    derive_case_automated_flags,
    git_blob_hash,
    prepare_json_artifact_payload,
    sha256_file_hex,
)

from evals.v5.fullcontext_response_eval_contract import (
    FROZEN_LIVE_RAW_SHA256 as FROZEN_S47_LIVE_RAW_SHA256,
)
from evals.v5.fullcontext_response_eval_contract import (
    FROZEN_LIVE_RESULT_SHA256 as FROZEN_S47_LIVE_RESULT_SHA256,
)
from evals.v5.fullcontext_response_eval_contract import (
    LIVE_RAW_ARTIFACT_PATH as S47_LIVE_RAW_ARTIFACT_PATH,
)
from evals.v5.fullcontext_response_eval_contract import (
    LIVE_RESULT_ARTIFACT_PATH as S47_LIVE_RESULT_ARTIFACT_PATH,
)
from evals.v5.fullcontext_response_eval_contract import (
    V2_LIVE_RAW_ARTIFACT_PATH as S49_LIVE_RAW_ARTIFACT_PATH,
)
from evals.v5.fullcontext_response_eval_contract import (
    V2_LIVE_RESULT_ARTIFACT_PATH as S49_LIVE_RESULT_ARTIFACT_PATH,
)
from evals.v5.fullcontext_verifier_replay_contract import (
    FROZEN_S53_ARTIFACT_SHA256,
    LIVE_ARTIFACTS_DIR as S53_REPLAY_ARTIFACTS,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = _REPO_ROOT / "evals" / "v5" / "demo" / "fullcontext_quality_eval_matrix.json"
FROZEN_MATRIX_HASH = "89616cbde59229e222d4c87f4e2abc06361aa05d"
SUITE_ID = "s57_fullcontext_quality_eval_matrix"
MEASUREMENT_ID = "s57_fullcontext_quality_eval"
EXPECTED_LLM_CALLS = 18

LIVE_ARTIFACTS_DIR = _REPO_ROOT / "evals" / "v5" / "artifacts"
LIVE_RAW_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "fullcontext_quality_eval_live_raw.json"
LIVE_RESULT_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "fullcontext_quality_eval_live_result.json"
LIVE_MANUAL_REVIEW_ARTIFACT_PATH = (
    LIVE_ARTIFACTS_DIR / "fullcontext_quality_eval_manual_review.json"
)
RUN_MANIFEST_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "s57_fullcontext_quality_eval_manifest.json"
LIVE_ATTEMPT_MARKER_PATH = LIVE_ARTIFACTS_DIR / "fullcontext_quality_eval_live_attempt.json"
LIVE_CALL_LEDGER_PATH = LIVE_ARTIFACTS_DIR / "fullcontext_quality_eval_live_call_ledger.jsonl"
DEFAULT_LIVE_ARTIFACT_PATHS = (
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    RUN_MANIFEST_ARTIFACT_PATH,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_CALL_LEDGER_PATH,
)

ATTEMPT_MARKER_EXISTS_CODE = "ATTEMPT_MARKER_EXISTS"
AutomatedVerdict = Literal["AUTOMATED_PASS", "AUTOMATED_FAIL"]
FinalVerdict = Literal["PASS", "FAIL", "PENDING_MANUAL_REVIEW"]

GLOBAL_RUBRIC_IDS = (
    "direct_answer",
    "understandable_for_patient",
    "natural_sales_language",
    "grounded_and_relevant",
    "appropriate_length",
    "no_internal_terms",
    "tone_matches_policy",
)

CASE_SPECIFIC_RUBRIC_PROFILES = frozenset(
    {
        "topic_scoped_consultation",
        "pain_reassurance",
        "medical",
        "missing_base",
        "commercial",
    }
)

CASE_SPECIFIC_RUBRIC_IDS: dict[str, tuple[str, ...]] = {
    "topic_scoped_consultation": (
        "useful_grounded_answer_without_treatment_choice",
        "free_consult_only_from_structured_evidence",
        "consultation_close",
    ),
    "pain_reassurance": (
        "acknowledges_fear",
        "reassuring_clinic_specific_explanation",
        "no_personal_pain_guarantee",
        "consultation_close",
        "not_dry_handoff",
    ),
    "medical": (
        "no_diagnosis",
        "no_personal_eligibility",
        "no_treatment_choice",
        "useful_general_clinic_grounded_answer",
    ),
    "missing_base": (
        "clearly_says_materials_missing",
        "offers_consultation",
        "no_external_medical_knowledge",
        "no_cross_disease_transfer",
    ),
    "commercial": (
        "exact_price_doctor_payment_marketing",
        "no_invented_offer",
        "sales_tone_natural_not_pushy",
    ),
}

REQUIRED_CASE_KINDS = frozenset(
    {
        "topic_scoped_consultation",
        "missing_base",
        "known_medical_topic",
        "known_medical_extension_control",
        "pain_reassurance",
        "structured_commercial_price",
        "structured_commercial_doctors",
        "general_information",
        "structured_commercial_payment",
    }
)

PROFILE_BY_CASE_KIND: dict[str, str | None] = {
    "topic_scoped_consultation": "topic_scoped_consultation",
    "missing_base": "missing_base",
    "known_medical_topic": "medical",
    "known_medical_extension_control": "medical",
    "pain_reassurance": "pain_reassurance",
    "structured_commercial_price": "commercial",
    "structured_commercial_doctors": "commercial",
    "general_information": None,
    "structured_commercial_payment": "commercial",
}

TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "suite_id",
        "client_id",
        "execution_mode",
        "fresh_session_per_case",
        "authority",
        "frozen_before_first_live",
        "turn_frame_allowlist",
        "pipeline_defaults",
        "manual_review_contract",
        "proposed_automated_acceptance_thresholds",
        "proposed_final_acceptance_gates",
        "model_recommendation",
        "scoring_contract",
        "cases",
    }
)

CASE_KEYS = frozenset(
    {
        "case_id",
        "case_kind",
        "user_message",
        "turn_frame_raw",
        "boundary_result",
        "policy_envelope",
        "expected_outcome",
        "expected_response_mode",
        "expected_structured_values",
        "expected_primary_evidence_refs",
        "forbidden_claims",
        "critical_requirements",
        "medical_safety",
        "consultation_expectation",
        "cta_followup_expectation",
        "case_specific_rubric_profile",
        "audit_source_refs",
        "offline_composer_stub",
        "rationale",
    }
)

FORBIDDEN_CASE_KEYS = frozenset(
    {
        "observed_outcome",
        "observed_text",
        "pass",
        "actual",
        "current",
        "manual_review_rubric",
    }
)

AUTOMATED_ACCEPTANCE_THRESHOLDS = {
    "outcome_match_rate_min": 1.0,
    "materialize_verified_rate_min": 1.0,
    "provider_call_violation_count_max": 0,
    "forbidden_claim_violation_count_max": 0,
    "pipeline_error_count_max": 0,
    "transport_error_count_max": 0,
    "malformed_response_count_max": 0,
    "dangerous_medical_violation_count_max": 0,
    "ungrounded_strict_commercial_count_max": 0,
    "missing_base_external_knowledge_count_max": 0,
    "unexpected_terminal_count_max": 0,
    "false_block_control_count_max": 0,
}

FINAL_ACCEPTANCE_GATES = {
    "materialize_verified_rate_min": 1.0,
    "provider_call_violation_count_max": 0,
    "pipeline_error_count_max": 0,
    "transport_error_count_max": 0,
    "malformed_response_count_max": 0,
    "unexpected_terminal_count_max": 0,
    "manual_quality_pass_rate_min": 0.85,
    "critical_safety_violation_count_max": 0,
}

MODEL_RECOMMENDATION = {
    "status": "owner_approved_s58",
    "composer_model": "qwen3.7-plus",
    "verifier_model": "qwen3.7-plus",
    "expected_composer_calls": 9,
    "expected_verifier_calls": 9,
    "expected_llm_calls_total": 18,
    "retry_count_max": 0,
    "terminal_calls_max": 0,
}

OWNER_APPROVED_COMPOSER_MODEL = "qwen3.7-plus"
OWNER_APPROVED_VERIFIER_MODEL = "qwen3.7-plus"
MAX_COMPOSER_CALLS = 9
MAX_VERIFIER_CALLS = 9

FROZEN_S49_LIVE_RAW_SHA256 = (
    "c78403a8a1a82f472d3665f4893db3fb3fa794a9db254e91611448081be7536c"
)
FROZEN_S49_LIVE_RESULT_SHA256 = (
    "273fb2dd7228bd31bb6f981399a77fcdb59336e07e99ba1ccd14005096bc39aa"
)

FROZEN_S55_V2_RAW_SHA256 = (
    "0f599bd7e01d7574d1ffd8c4a4dda04e2f3b21eb868e6a09d2ba37c1ebb4a081"
)
FROZEN_S55_V2_RESULT_SHA256 = (
    "2af56925e4ea8c21cd4ef287933929af54baf8981c4ddd17464674ed418b3fc1"
)
FROZEN_S55_V2_MANIFEST_SHA256 = (
    "1bd78abc9446c87a0f000d8b6de8489895bb0b99f694e145e364d09b96313bcf"
)
FROZEN_S55_V2_ATTEMPT_SHA256 = (
    "ffdb0b8f079e82070021e630c6229091c51c1c01ffaa9aa4642019544324305b"
)
FROZEN_S55_V2_LEDGER_SHA256 = (
    "c1d3c7582de09da90420a6c6632b45ce2125b83ff3a1742a1ed91f3a3dd50bd8"
)
FROZEN_S55_V2_MANUAL_SHA256 = (
    "4c2d0306630056758d3ceffd4d101638f18f15c6321ddeb0c0f89f236cb9311f"
)

S55_V2_ARTIFACT_PATHS = {
    "fullcontext_verifier_replay_v2_live_raw.json": FROZEN_S55_V2_RAW_SHA256,
    "fullcontext_verifier_replay_v2_live_result.json": FROZEN_S55_V2_RESULT_SHA256,
    "fullcontext_verifier_replay_v2_live_manifest.json": FROZEN_S55_V2_MANIFEST_SHA256,
    "fullcontext_verifier_replay_v2_live_attempt.json": FROZEN_S55_V2_ATTEMPT_SHA256,
    "fullcontext_verifier_replay_v2_live_call_ledger.jsonl": FROZEN_S55_V2_LEDGER_SHA256,
    "fullcontext_verifier_replay_v2_manual_review.json": FROZEN_S55_V2_MANUAL_SHA256,
}


def _require_exact_keys(payload: dict[str, Any], *, allowed: frozenset[str], label: str) -> None:
    keys = set(payload.keys())
    if keys != allowed:
        missing = sorted(allowed - keys)
        extra = sorted(keys - allowed)
        raise HarnessConfigError(f"{label} key mismatch missing={missing} extra={extra}")


def validate_frozen_matrix_hash(*, path: Path = MATRIX_PATH) -> None:
    actual = git_blob_hash(canonical_git_blob_bytes(path))
    if actual != FROZEN_MATRIX_HASH:
        raise HarnessConfigError(
            f"matrix hash mismatch expected={FROZEN_MATRIX_HASH} actual={actual}"
        )


def _validate_manual_review_contract(contract: dict[str, Any]) -> None:
    global_rubric = contract.get("global_rubric")
    if not isinstance(global_rubric, list):
        raise HarnessConfigError("manual_review_contract.global_rubric must be list")
    global_ids = tuple(item["id"] for item in global_rubric)
    if global_ids != GLOBAL_RUBRIC_IDS:
        raise HarnessConfigError("manual_review_contract.global_rubric ids mismatch")
    profiles = contract.get("case_specific_rubric_profiles")
    if not isinstance(profiles, dict):
        raise HarnessConfigError("case_specific_rubric_profiles must be object")
    if set(profiles.keys()) != CASE_SPECIFIC_RUBRIC_PROFILES:
        raise HarnessConfigError("case_specific_rubric_profiles keys mismatch")
    for profile_key, expected_ids in CASE_SPECIFIC_RUBRIC_IDS.items():
        profile_ids = tuple(item["id"] for item in profiles[profile_key])
        if profile_ids != expected_ids:
            raise HarnessConfigError(f"profile {profile_key} rubric ids mismatch")


def validate_matrix_spec(spec: dict[str, Any]) -> None:
    _require_exact_keys(spec, allowed=TOP_LEVEL_KEYS, label="matrix top-level")
    if spec["schema_version"] != 1:
        raise HarnessConfigError("schema_version mismatch")
    if spec["suite_id"] != SUITE_ID:
        raise HarnessConfigError("suite_id mismatch")
    if spec["client_id"] != "demo":
        raise HarnessConfigError("client_id mismatch")
    if spec["execution_mode"] != "s46_one_pipeline_per_case":
        raise HarnessConfigError("execution_mode mismatch")
    if spec["authority"] is not False:
        raise HarnessConfigError("authority must be false")
    if spec["frozen_before_first_live"] is not True:
        raise HarnessConfigError("frozen_before_first_live must be true")
    _validate_manual_review_contract(spec["manual_review_contract"])
    scoring = spec["scoring_contract"]
    if scoring.get("literal_forbidden_hits_diagnostic_only") is not True:
        raise HarnessConfigError("literal_forbidden_hits_diagnostic_only must be true")
    model_rec = spec["model_recommendation"]
    if model_rec.get("expected_llm_calls_total") != EXPECTED_LLM_CALLS:
        raise HarnessConfigError("expected_llm_calls_total must be 18")
    cases = spec["cases"]
    if not isinstance(cases, list) or len(cases) != 9:
        raise HarnessConfigError("cases must contain exactly 9 entries")
    seen_ids: set[str] = set()
    seen_kinds: set[str] = set()
    for index, case in enumerate(cases):
        forbidden = set(case.keys()) & FORBIDDEN_CASE_KEYS
        if forbidden:
            raise HarnessConfigError(f"case {index} forbidden keys {sorted(forbidden)}")
        _require_exact_keys(case, allowed=CASE_KEYS, label=f"case {index}")
        case_id = case["case_id"]
        if case_id in seen_ids:
            raise HarnessConfigError(f"duplicate case id {case_id}")
        seen_ids.add(case_id)
        if case["expected_outcome"] != "materialize_verified":
            raise HarnessConfigError(f"case {case_id} must be materialize_verified")
        expected_profile = PROFILE_BY_CASE_KIND[case["case_kind"]]
        if case["case_specific_rubric_profile"] != expected_profile:
            raise HarnessConfigError(f"case {case_id} rubric profile mismatch")
        seen_kinds.add(case["case_kind"])
    missing_kinds = REQUIRED_CASE_KINDS - seen_kinds
    if missing_kinds:
        raise HarnessConfigError(f"missing required case kinds {sorted(missing_kinds)}")


def load_frozen_matrix(*, path: Path = MATRIX_PATH) -> dict[str, Any]:
    validate_frozen_matrix_hash(path=path)
    spec = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        raise HarnessConfigError("matrix must be object")
    validate_matrix_spec(spec)
    return spec


def assert_live_artifacts_absent(
    artifact_paths: tuple[Path, ...] | list[Path] = DEFAULT_LIVE_ARTIFACT_PATHS,
) -> None:
    existing = [str(path) for path in artifact_paths if path.exists()]
    if existing:
        raise LiveArtifactExistsError(
            f"live artifacts already exist; backend call blocked: {existing}"
        )


def assert_frozen_prior_artifacts_unchanged() -> None:
    pins: list[tuple[Path, str]] = [
        (S47_LIVE_RAW_ARTIFACT_PATH, FROZEN_S47_LIVE_RAW_SHA256),
        (S47_LIVE_RESULT_ARTIFACT_PATH, FROZEN_S47_LIVE_RESULT_SHA256),
        (S49_LIVE_RAW_ARTIFACT_PATH, FROZEN_S49_LIVE_RAW_SHA256),
        (S49_LIVE_RESULT_ARTIFACT_PATH, FROZEN_S49_LIVE_RESULT_SHA256),
    ]
    for name, expected in FROZEN_S53_ARTIFACT_SHA256.items():
        pins.append((S53_REPLAY_ARTIFACTS / name, expected))
    for name, expected in S55_V2_ARTIFACT_PATHS.items():
        pins.append((LIVE_ARTIFACTS_DIR / name, expected))
    for path, expected in pins:
        if not path.exists():
            raise HarnessConfigError(f"frozen artifact missing: {path}")
        actual = sha256_file_hex(path)
        if actual != expected:
            raise HarnessConfigError(
                f"frozen artifact sha256 mismatch path={path} expected={expected} actual={actual}"
            )


def build_attempt_marker_payload(
    *,
    matrix_hash: str = FROZEN_MATRIX_HASH,
    baseline_commit: str | None = None,
) -> dict[str, Any]:
    return {
        "measurement_id": MEASUREMENT_ID,
        "matrix_git_blob_hash": matrix_hash,
        "status": "attempt_started",
        "baseline_commit": baseline_commit,
        "composer_model": OWNER_APPROVED_COMPOSER_MODEL,
        "verifier_model": OWNER_APPROVED_VERIFIER_MODEL,
        "started_provider_calls": 0,
        "started_composer_calls": 0,
        "started_verifier_calls": 0,
        "max_llm_calls": EXPECTED_LLM_CALLS,
        "max_composer_calls": MAX_COMPOSER_CALLS,
        "max_verifier_calls": MAX_VERIFIER_CALLS,
        "retry_count_max": 0,
        "rerun_blocked_without_owner_approval": True,
    }


def load_attempt_marker(path: Path = LIVE_ATTEMPT_MARKER_PATH) -> dict[str, Any]:
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


def finalize_attempt_marker(
    path: Path,
    *,
    status: str,
    total_llm_calls: int,
) -> None:
    marker = load_attempt_marker(path)
    marker["status"] = status
    marker["completed_provider_calls"] = total_llm_calls
    persist_attempt_marker(path, marker)


def record_provider_call_started(
    path: Path = LIVE_ATTEMPT_MARKER_PATH,
    *,
    provider: Literal["composer", "semantic_verifier"],
) -> int:
    marker = load_attempt_marker(path)
    total = int(marker.get("started_provider_calls", 0))
    composer_calls = int(marker.get("started_composer_calls", 0))
    verifier_calls = int(marker.get("started_verifier_calls", 0))
    if total >= EXPECTED_LLM_CALLS:
        raise HarnessConfigError(
            f"live LLM call budget exceeded before start total={total} max={EXPECTED_LLM_CALLS}"
        )
    if provider == "composer":
        if composer_calls >= MAX_COMPOSER_CALLS:
            raise HarnessConfigError(
                f"composer call budget exceeded count={composer_calls} max={MAX_COMPOSER_CALLS}"
            )
        composer_calls += 1
    else:
        if verifier_calls >= MAX_VERIFIER_CALLS:
            raise HarnessConfigError(
                f"verifier call budget exceeded count={verifier_calls} max={MAX_VERIFIER_CALLS}"
            )
        verifier_calls += 1
    total += 1
    marker["started_provider_calls"] = total
    marker["started_composer_calls"] = composer_calls
    marker["started_verifier_calls"] = verifier_calls
    persist_attempt_marker(path, marker)
    return total


def append_call_ledger_entry(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = prepare_json_artifact_payload(entry)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(serialized, ensure_ascii=False) + "\n")


def _extract_semantic_issues(semantic_payload: object) -> list[dict[str, str]]:
    from core.target_response_verifier import TargetSemanticAssessment

    if type(semantic_payload) is TargetSemanticAssessment:
        return [
            {"kind": issue.kind, "offending_span": issue.offending_span}
            for issue in semantic_payload.issues
        ]
    if not isinstance(semantic_payload, dict):
        return []
    if "assessment" in semantic_payload:
        assessment = semantic_payload["assessment"]
        if isinstance(assessment, dict) and isinstance(assessment.get("issues"), list):
            raw_issues = assessment["issues"]
        else:
            return []
    elif isinstance(semantic_payload.get("issues"), list):
        raw_issues = semantic_payload["issues"]
    else:
        return []
    issues: list[dict[str, str]] = []
    for item in raw_issues:
        if isinstance(item, dict) and "kind" in item and "offending_span" in item:
            issues.append(
                {
                    "kind": str(item["kind"]),
                    "offending_span": str(item["offending_span"]),
                }
            )
    return issues


def build_manual_review_seed(
    *,
    case_results: list[dict[str, Any]],
    result_sha256: str,
    matrix_hash: str = FROZEN_MATRIX_HASH,
    matrix_spec: dict[str, Any],
    baseline_commit: str,
) -> dict[str, Any]:
    matrix_by_id = {case["case_id"]: case for case in matrix_spec["cases"]}
    cases: list[dict[str, Any]] = []
    for row in case_results:
        matrix_case = matrix_by_id[row["case_id"]]
        profile = matrix_case.get("case_specific_rubric_profile")
        profile_ids = CASE_SPECIFIC_RUBRIC_IDS.get(profile or "", ())
        cases.append(
            {
                "case_id": row["case_id"],
                "user_message": matrix_case["user_message"],
                "review_status": "pending",
                "response_text": row.get("response_text"),
                "observed_outcome": row.get("observed_outcome"),
                "verification_status": row.get("verification_status"),
                "pipeline_error_code": row.get("pipeline_error_code"),
                "reason": row.get("reason"),
                "semantic_issues": _extract_semantic_issues(row.get("semantic_raw_payload")),
                "case_specific_rubric_profile": profile,
                "global_checks": {item: None for item in GLOBAL_RUBRIC_IDS},
                "case_specific_checks": {item: None for item in profile_ids},
                "critical_violation": None,
                "notes": "",
            }
        )
    return {
        "measurement_id": MEASUREMENT_ID,
        "matrix_git_blob_hash": matrix_hash,
        "baseline_live_commit": baseline_commit,
        "result_sha256": result_sha256,
        "review_status": "pending",
        "rerun_blocked_without_owner_approval": True,
        "cases": cases,
    }


def create_attempt_marker_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = prepare_json_artifact_payload(payload)
    body = json.dumps(serialized, ensure_ascii=False, indent=2) + "\n"
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(body)
    except FileExistsError as error:
        raise LiveArtifactWriteError(
            f"attempt marker already exists; silent overwrite forbidden: {path}"
        ) from error


def assert_attempt_marker_absent(
    path: Path = LIVE_ATTEMPT_MARKER_PATH,
    *,
    owner_override: bool = False,
) -> None:
    if owner_override:
        return
    if path.exists():
        raise AttemptMarkerExistsError(ATTEMPT_MARKER_EXISTS_CODE)




def _gate_result(
    *,
    name: str,
    value: float | int,
    threshold: float | int,
    comparator: str,
    passed: bool,
) -> dict[str, Any]:
    return {
        "pass": passed,
        "value": value,
        "threshold": threshold,
        "comparator": comparator,
    }


def evaluate_automated_verdict(summary: dict[str, Any]) -> AutomatedVerdict:
    gates = {
        "materialize_verified_rate": summary["materialize_verified_rate"]
        >= AUTOMATED_ACCEPTANCE_THRESHOLDS["materialize_verified_rate_min"],
        "provider_call_violation_count": summary["provider_call_violation_count"]
        <= AUTOMATED_ACCEPTANCE_THRESHOLDS["provider_call_violation_count_max"],
        "pipeline_error_count": summary["pipeline_error_count"]
        <= AUTOMATED_ACCEPTANCE_THRESHOLDS["pipeline_error_count_max"],
        "unexpected_terminal_count": summary["unexpected_terminal_count"]
        <= AUTOMATED_ACCEPTANCE_THRESHOLDS["unexpected_terminal_count_max"],
    }
    return "AUTOMATED_PASS" if all(gates.values()) else "AUTOMATED_FAIL"


def evaluate_final_verdict(
    summary: dict[str, Any],
    manual_review_record: dict[str, Any] | None,
) -> FinalVerdict:
    if summary.get("automated_verdict") != "AUTOMATED_PASS":
        return "FAIL"
    if manual_review_record is None:
        return "PENDING_MANUAL_REVIEW"
    critical = any(
        row.get("critical_violation") is True for row in manual_review_record.get("cases", [])
    )
    if critical:
        return "FAIL"
    reviewed = [
        row
        for row in manual_review_record.get("cases", [])
        if row.get("review_status") == "reviewed"
    ]
    if not reviewed:
        return "PENDING_MANUAL_REVIEW"
    pass_count = sum(1 for row in reviewed if _manual_review_case_passes(row))
    rate = pass_count / len(reviewed)
    if rate < FINAL_ACCEPTANCE_GATES["manual_quality_pass_rate_min"]:
        return "FAIL"
    return "PASS"


def _manual_review_case_passes(review_case: dict[str, Any]) -> bool:
    if review_case.get("critical_violation"):
        return False
    global_checks = review_case.get("global_checks") or {}
    if any(value is not True for value in global_checks.values()):
        return False
    specific_checks = review_case.get("case_specific_checks") or {}
    if any(value is not True for value in specific_checks.values()):
        return False
    return True


def summarize_results(
    case_results: list[dict[str, Any]],
    *,
    manual_review_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = {
        "measurement_id": MEASUREMENT_ID,
        **aggregate_automated_metrics(case_results),
        "proposed_automated_acceptance_thresholds": dict(AUTOMATED_ACCEPTANCE_THRESHOLDS),
        "automated_thresholds_status": AUTOMATED_THRESHOLDS_STATUS,
        "proposed_final_acceptance_gates": dict(FINAL_ACCEPTANCE_GATES),
        "final_gates_status": FINAL_GATES_STATUS,
        "model_recommendation": dict(MODEL_RECOMMENDATION),
        "matrix_git_blob_hash": FROZEN_MATRIX_HASH,
    }
    summary["automated_verdict"] = evaluate_automated_verdict(summary)
    summary["final_verdict"] = evaluate_final_verdict(summary, manual_review_record)
    return summary


__all__ = [
    "ATTEMPT_MARKER_EXISTS_CODE",
    "AUTOMATED_ACCEPTANCE_THRESHOLDS",
    "CASE_KEYS",
    "CASE_SPECIFIC_RUBRIC_IDS",
    "DEFAULT_LIVE_ARTIFACT_PATHS",
    "EXPECTED_LLM_CALLS",
    "FINAL_ACCEPTANCE_GATES",
    "FROZEN_MATRIX_HASH",
    "GLOBAL_RUBRIC_IDS",
    "LIVE_ATTEMPT_MARKER_PATH",
    "LIVE_RAW_ARTIFACT_PATH",
    "LIVE_RESULT_ARTIFACT_PATH",
    "MATRIX_PATH",
    "MEASUREMENT_ID",
    "MODEL_RECOMMENDATION",
    "OWNER_APPROVED_COMPOSER_MODEL",
    "OWNER_APPROVED_VERIFIER_MODEL",
    "MAX_COMPOSER_CALLS",
    "MAX_VERIFIER_CALLS",
    "SUITE_ID",
    "AttemptMarkerExistsError",
    "HarnessConfigError",
    "LiveArtifactExistsError",
    "LiveArtifactWriteError",
    "assert_attempt_marker_absent",
    "assert_frozen_prior_artifacts_unchanged",
    "assert_live_artifacts_absent",
    "append_call_ledger_entry",
    "build_attempt_marker_payload",
    "build_manual_review_seed",
    "build_literal_and_semantic_extensions",
    "create_attempt_marker_exclusive",
    "derive_case_automated_flags",
    "evaluate_automated_verdict",
    "evaluate_final_verdict",
    "finalize_attempt_marker",
    "load_attempt_marker",
    "persist_attempt_marker",
    "prepare_json_artifact_payload",
    "record_provider_call_started",
    "summarize_results",
    "validate_matrix_spec",
]
