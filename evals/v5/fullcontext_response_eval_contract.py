"""Frozen contract for S47 FullContext response live eval (offline prep; no live in scope)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

_REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = _REPO_ROOT / "evals" / "v5" / "demo" / "fullcontext_response_eval_matrix.json"
FROZEN_MATRIX_HASH = "79baaa077bc5dcc0b7ecef4d0f5081d400e58f69"

LIVE_ARTIFACTS_DIR = _REPO_ROOT / "evals" / "v5" / "artifacts"
LIVE_RAW_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "fullcontext_response_eval_live_raw.json"
LIVE_RESULT_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "fullcontext_response_eval_live_result.json"
DEFAULT_LIVE_ARTIFACT_PATHS = (LIVE_RAW_ARTIFACT_PATH, LIVE_RESULT_ARTIFACT_PATH)

MEASUREMENT_ID = "s47_fullcontext_response_live_eval"
THRESHOLDS_STATUS = "proposed_before_first_live"

ExpectedOutcome = Literal[
    "materialize_verified",
    "terminal_boundary_uncertain",
]

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
        "proposed_acceptance_thresholds",
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
        "forbidden_claims",
        "medical_safety",
        "consultation_expectation",
        "cta_followup_expectation",
        "manual_review_rubric",
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
    }
)

REQUIRED_CASE_KINDS = frozenset(
    {
        "general_information",
        "pain_reassurance",
        "structured_commercial_price",
        "structured_commercial_payment",
        "structured_commercial_doctors",
        "structured_commercial_marketing",
        "known_medical_topic",
        "missing_base",
        "medical_boundary_personal",
        "medical_boundary_diagnosis",
        "medical_boundary_treatment_choice",
        "terminal_uncertain",
    }
)

ACCEPTANCE_THRESHOLDS: dict[str, Any] = {
    "status": THRESHOLDS_STATUS,
    "outcome_match_rate_min": 1.0,
    "provider_call_violation_count_max": 0,
    "forbidden_claim_violation_count_max": 0,
    "pipeline_error_count_max": 0,
}

ACCEPTANCE_THRESHOLD_KEYS = frozenset(
    key for key in ACCEPTANCE_THRESHOLDS.keys() if key != "status"
)

CASE_RESULT_KEYS = frozenset(
    {
        "index",
        "case_id",
        "case_kind",
        "expected_outcome",
        "observed_outcome",
        "expected_response_mode",
        "observed_response_mode",
        "response_text",
        "composer_call_count",
        "semantic_call_count",
        "provider_call_violation",
        "forbidden_claim_violations",
        "pipeline_error_code",
        "verification_status",
        "composer_raw_payload",
        "semantic_raw_payload",
        "status",
        "reason",
    }
)


class HarnessConfigError(Exception):
    """Frozen spec/hash/CLI configuration error."""


class LiveArtifactExistsError(HarnessConfigError):
    """Target live artifact already exists; backend call blocked."""


class LiveArtifactWriteError(HarnessConfigError):
    """Exclusive live artifact write failed."""


def git_blob_hash(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def sha256_file_hex(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def canonical_git_blob_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def validate_frozen_matrix_hash(*, path: Path = MATRIX_PATH) -> None:
    actual = git_blob_hash(canonical_git_blob_bytes(path))
    if actual != FROZEN_MATRIX_HASH:
        raise HarnessConfigError(
            f"matrix hash mismatch expected={FROZEN_MATRIX_HASH} actual={actual}"
        )


def _require_exact_keys(payload: dict[str, Any], *, allowed: frozenset[str], label: str) -> None:
    keys = set(payload.keys())
    if keys != allowed:
        missing = sorted(allowed - keys)
        extra = sorted(keys - allowed)
        raise HarnessConfigError(f"{label} key mismatch missing={missing} extra={extra}")


def validate_matrix_spec(spec: dict[str, Any]) -> None:
    _require_exact_keys(spec, allowed=TOP_LEVEL_KEYS, label="matrix top-level")
    if spec["schema_version"] != 1:
        raise HarnessConfigError("schema_version mismatch")
    if spec["suite_id"] != "s47_fullcontext_response_live_eval_matrix":
        raise HarnessConfigError("suite_id mismatch")
    if spec["client_id"] != "demo":
        raise HarnessConfigError("client_id mismatch")
    if spec["execution_mode"] != "s46_one_pipeline_per_case":
        raise HarnessConfigError("execution_mode mismatch")
    if spec["authority"] is not False:
        raise HarnessConfigError("authority must be false")
    if spec["frozen_before_first_live"] is not True:
        raise HarnessConfigError("frozen_before_first_live must be true")

    thresholds = spec["proposed_acceptance_thresholds"]
    if thresholds.get("status") != THRESHOLDS_STATUS:
        raise HarnessConfigError("thresholds status mismatch")
    for key in ACCEPTANCE_THRESHOLD_KEYS:
        if thresholds.get(key) != ACCEPTANCE_THRESHOLDS[key]:
            raise HarnessConfigError(f"acceptance threshold mismatch for {key}")

    scoring = spec["scoring_contract"]
    if scoring.get("retry_failed_case") is not False:
        raise HarnessConfigError("retry_failed_case must be false")
    if scoring.get("fallback_on_failure") is not False:
        raise HarnessConfigError("fallback_on_failure must be false")

    cases = spec["cases"]
    if not isinstance(cases, list) or len(cases) != 20:
        raise HarnessConfigError("cases must contain exactly 20 entries")

    seen_ids: set[str] = set()
    seen_kinds: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise HarnessConfigError(f"case {index} must be object")
        forbidden = set(case.keys()) & FORBIDDEN_CASE_KEYS
        if forbidden:
            raise HarnessConfigError(f"case {index} forbidden keys {sorted(forbidden)}")
        _require_exact_keys(case, allowed=CASE_KEYS, label=f"case {index}")
        case_id = case["case_id"]
        if case_id in seen_ids:
            raise HarnessConfigError(f"duplicate case id {case_id}")
        seen_ids.add(case_id)
        if case["expected_outcome"] not in {"materialize_verified", "terminal_boundary_uncertain"}:
            raise HarnessConfigError(f"case {case_id} invalid expected_outcome")
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


def evaluate_threshold_verdict(summary: dict[str, Any]) -> dict[str, Any]:
    gates = {
        "outcome_match_rate": {
            "pass": summary["outcome_match_rate"] >= ACCEPTANCE_THRESHOLDS["outcome_match_rate_min"],
            "value": summary["outcome_match_rate"],
            "threshold": ACCEPTANCE_THRESHOLDS["outcome_match_rate_min"],
            "comparator": ">=",
        },
        "provider_call_violation_count": {
            "pass": summary["provider_call_violation_count"]
            <= ACCEPTANCE_THRESHOLDS["provider_call_violation_count_max"],
            "value": summary["provider_call_violation_count"],
            "threshold": ACCEPTANCE_THRESHOLDS["provider_call_violation_count_max"],
            "comparator": "==",
        },
        "forbidden_claim_violation_count": {
            "pass": summary["forbidden_claim_violation_count"]
            <= ACCEPTANCE_THRESHOLDS["forbidden_claim_violation_count_max"],
            "value": summary["forbidden_claim_violation_count"],
            "threshold": ACCEPTANCE_THRESHOLDS["forbidden_claim_violation_count_max"],
            "comparator": "==",
        },
        "pipeline_error_count": {
            "pass": summary["pipeline_error_count"]
            <= ACCEPTANCE_THRESHOLDS["pipeline_error_count_max"],
            "value": summary["pipeline_error_count"],
            "threshold": ACCEPTANCE_THRESHOLDS["pipeline_error_count_max"],
            "comparator": "==",
        },
    }
    verdict = "PASS" if all(gate["pass"] for gate in gates.values()) else "FAIL"
    return {"verdict": verdict, "gates": gates}
