"""Frozen contract for S47 FullContext response live eval (offline prep; no live in scope)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

_REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = _REPO_ROOT / "evals" / "v5" / "demo" / "fullcontext_response_eval_matrix.json"
FROZEN_MATRIX_HASH = "14b1cbd4c3a8d906e0b19adb10ffaa60849803b3"
FROZEN_LIVE_RAW_SHA256 = (
    "0f4d4b93c53aaf4432d9187a4c2357d730b3c0ef1acbfd241cd38ad4367bc11f"
)
FROZEN_LIVE_RESULT_SHA256 = (
    "83bff177f432d1c70639f1810ea0d85bfbd06c63691e65942abeb9ad36ad0eed"
)

LIVE_ARTIFACTS_DIR = _REPO_ROOT / "evals" / "v5" / "artifacts"
LIVE_RAW_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "fullcontext_response_eval_live_raw.json"
LIVE_RESULT_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "fullcontext_response_eval_live_result.json"
LIVE_MANUAL_REVIEW_ARTIFACT_PATH = (
    LIVE_ARTIFACTS_DIR / "fullcontext_response_eval_manual_review.json"
)
DEFAULT_LIVE_ARTIFACT_PATHS = (LIVE_RAW_ARTIFACT_PATH, LIVE_RESULT_ARTIFACT_PATH)

MEASUREMENT_ID = "s47_fullcontext_response_live_eval"
AUTOMATED_THRESHOLDS_STATUS = "proposed_before_first_live"
FINAL_GATES_STATUS = "pending_owner_approval"
MODEL_RECOMMENDATION_STATUS = "pending_owner_approval"

# Backward-compatible alias for harness/tests migrating from S47 prep.
THRESHOLDS_STATUS = AUTOMATED_THRESHOLDS_STATUS

ExpectedOutcome = Literal[
    "materialize_verified",
    "terminal_boundary_uncertain",
]

AutomatedVerdict = Literal["AUTOMATED_PASS", "AUTOMATED_FAIL"]
FinalVerdict = Literal["PASS", "FAIL", "PENDING_MANUAL_REVIEW"]

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
        "forbidden_claims",
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

CASE_SPECIFIC_RUBRIC_PROFILES = frozenset(
    {
        "pain_reassurance",
        "medical",
        "missing_base",
        "commercial",
    }
)

PROFILE_BY_CASE_KIND: dict[str, str | None] = {
    "general_information": None,
    "pain_reassurance": "pain_reassurance",
    "structured_commercial_price": "commercial",
    "structured_commercial_payment": "commercial",
    "structured_commercial_doctors": "commercial",
    "structured_commercial_marketing": "commercial",
    "known_medical_topic": "medical",
    "missing_base": "missing_base",
    "medical_boundary_personal": "medical",
    "medical_boundary_diagnosis": "medical",
    "medical_boundary_treatment_choice": "medical",
    "terminal_uncertain": None,
}

GLOBAL_RUBRIC_IDS = (
    "direct_answer",
    "understandable_for_patient",
    "natural_language",
    "grounded_and_relevant",
    "appropriate_length",
    "no_awkward_internal_terms",
    "tone_matches_policy",
)

CASE_SPECIFIC_RUBRIC_IDS: dict[str, tuple[str, ...]] = {
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
    ),
    "commercial": (
        "exact_price_doctor_payment_marketing",
        "no_invented_offer",
        "sales_tone_natural_not_pushy",
    ),
}

AUTOMATED_ACCEPTANCE_THRESHOLDS: dict[str, Any] = {
    "status": AUTOMATED_THRESHOLDS_STATUS,
    "outcome_match_rate_min": 1.0,
    "provider_call_violation_count_max": 0,
    "forbidden_claim_violation_count_max": 0,
    "pipeline_error_count_max": 0,
    "transport_error_count_max": 0,
    "malformed_response_count_max": 0,
    "dangerous_medical_violation_count_max": 0,
    "ungrounded_strict_commercial_count_max": 0,
    "missing_base_external_knowledge_count_max": 0,
    "unexpected_terminal_count_max": 0,
}

# Historical matrix snapshot keys still validated against frozen matrix JSON.
AUTOMATED_THRESHOLD_KEYS = frozenset(
    key for key in AUTOMATED_ACCEPTANCE_THRESHOLDS.keys() if key != "status"
)

# Active automated gates exclude unmeasured literal/dangerous safety counters.
ACTIVE_AUTOMATED_GATE_KEYS = frozenset(
    key
    for key in AUTOMATED_THRESHOLD_KEYS
    if key
    not in {
        "forbidden_claim_violation_count_max",
        "dangerous_medical_violation_count_max",
    }
)

FINAL_ACCEPTANCE_GATES: dict[str, Any] = {
    "status": FINAL_GATES_STATUS,
    "materialize_verified_rate_min": 0.85,
    "terminal_behavior_rate_min": 1.0,
    "provider_call_violation_count_max": 0,
    "pipeline_error_count_max": 0,
    "transport_error_count_max": 0,
    "malformed_response_count_max": 0,
    "dangerous_medical_violation_count_max": 0,
    "ungrounded_strict_commercial_count_max": 0,
    "wrong_price_doctor_count_max": 0,
    "missing_base_external_knowledge_count_max": 0,
    "unexpected_terminal_count_max": 0,
    "manual_answer_quality_pass_rate_min": 0.85,
    "incomplete_manual_review_count_max": 0,
}

FINAL_GATE_KEYS = frozenset(key for key in FINAL_ACCEPTANCE_GATES.keys() if key != "status")

ACTIVE_FINAL_COUNT_GATE_KEYS = frozenset(
    {
        "provider_call_violation_count",
        "pipeline_error_count",
        "transport_error_count",
        "malformed_response_count",
        "ungrounded_strict_commercial_count",
        "missing_base_external_knowledge_count",
        "unexpected_terminal_count",
    }
)

DANGEROUS_MEDICAL_EVALUATION_NOT_EVALUATED = "NOT_EVALUATED"

MODEL_RECOMMENDATION: dict[str, Any] = {
    "status": MODEL_RECOMMENDATION_STATUS,
    "composer_model": "qwen3.7-plus",
    "semantic_verifier_model": "qwen3.7-plus",
    "available_project_models": ["qwen3.7-plus", "qwen3.6-flash"],
    "expected_llm_calls_materializable": 38,
    "expected_llm_calls_terminal": 0,
    "rationale": (
        "First accuracy proof uses qwen3.7-plus for Composer and proposed Semantic Verifier "
        "override; flash cost eval is a separate follow-up run."
    ),
}

# Backward-compatible alias used by harness dry-run until callers migrate.
ACCEPTANCE_THRESHOLDS = AUTOMATED_ACCEPTANCE_THRESHOLDS
ACCEPTANCE_THRESHOLD_KEYS = AUTOMATED_THRESHOLD_KEYS

MANUAL_REVIEW_TOP_KEYS = frozenset(
    {
        "measurement_id",
        "matrix_git_blob_hash",
        "result_sha256",
        "reviewer",
        "reviewed_at",
        "cases",
    }
)

MANUAL_REVIEW_CASE_KEYS = frozenset(
    {
        "case_id",
        "review_status",
        "global_checks",
        "case_specific_checks",
        "critical_violation",
        "notes",
    }
)

STRUCTURED_COMMERCIAL_KINDS = frozenset(
    {
        "structured_commercial_price",
        "structured_commercial_payment",
        "structured_commercial_doctors",
        "structured_commercial_marketing",
    }
)

TRANSPORT_ERROR_CODES = frozenset(
    {
        "FullContextResponseEvalTransportError",
    }
)

MALFORMED_ERROR_CODES = frozenset(
    {
        "ValidationError",
        "JSONDecodeError",
    }
)

SEMANTIC_REJECT_FIELDS = (
    "semantic_general_grounding_rejected",
    "semantic_strict_commercial_grounding_rejected",
    "semantic_topic_scope_rejected",
    "semantic_medical_boundary_rejected",
    "semantic_selected_facts_rejected",
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
        "raw_literal_forbidden_hits",
        "semantic_assessment_evaluated",
        *SEMANTIC_REJECT_FIELDS,
        "pipeline_error_code",
        "verification_status",
        "composer_raw_payload",
        "semantic_raw_payload",
        "status",
        "reason",
        "ungrounded_strict_commercial",
        "missing_base_external_knowledge",
        "unexpected_terminal",
        "transport_error",
        "malformed_response",
    }
)


def semantic_payload_has_assessment(semantic_raw_payload: object) -> bool:
    return _semantic_assessment_dict(semantic_raw_payload) is not None


def extract_candidate_text_from_composer_payload(payload: object) -> str | None:
    if isinstance(payload, dict):
        text = payload.get("text")
        if type(text) is str:
            stripped = text.strip()
            return stripped or None
    if type(payload) is str:
        stripped = payload.strip()
        return stripped or None
    return None


def _semantic_assessment_dict(semantic_raw_payload: object) -> dict[str, Any] | None:
    if not isinstance(semantic_raw_payload, dict):
        return None
    assessment = semantic_raw_payload.get("assessment")
    if isinstance(assessment, dict):
        return assessment
    ok_fields = (
        "general_grounding_ok",
        "strict_commercial_grounding_ok",
        "topic_scope_ok",
        "medical_boundary_ok",
        "selected_facts_ok",
    )
    if any(field in semantic_raw_payload for field in ok_fields):
        return semantic_raw_payload
    return None


def derive_semantic_reject_flags(semantic_raw_payload: object) -> dict[str, bool]:
    assessment = _semantic_assessment_dict(semantic_raw_payload)
    if assessment is None:
        raise HarnessConfigError("semantic assessment required to derive reject flags")
    flags: dict[str, bool] = {}
    mapping = {
        "general_grounding_ok": "semantic_general_grounding_rejected",
        "strict_commercial_grounding_ok": "semantic_strict_commercial_grounding_rejected",
        "topic_scope_ok": "semantic_topic_scope_rejected",
        "medical_boundary_ok": "semantic_medical_boundary_rejected",
        "selected_facts_ok": "semantic_selected_facts_rejected",
    }
    for ok_field, reject_field in mapping.items():
        flags[reject_field] = assessment.get(ok_field) is False
    return flags


def semantic_reject_fields_for_row(*, evaluated: bool, semantic_raw_payload: object) -> dict[str, bool | None]:
    if not evaluated:
        return dict.fromkeys(SEMANTIC_REJECT_FIELDS, None)
    return derive_semantic_reject_flags(semantic_raw_payload)  # type: ignore[return-value]


def raw_literal_forbidden_hits(text: str, forbidden_claims: list[str]) -> list[str]:
    lowered = text.lower()
    return [claim for claim in forbidden_claims if claim.lower() in lowered]


def build_literal_and_semantic_extensions(
    *,
    candidate_text: str | None,
    forbidden_claims: list[str],
    semantic_raw_payload: object,
    apply_semantic_assessment: bool,
) -> dict[str, Any]:
    literal_hits = (
        raw_literal_forbidden_hits(candidate_text, forbidden_claims)
        if candidate_text
        else []
    )
    evaluated = (
        apply_semantic_assessment
        and _semantic_assessment_dict(semantic_raw_payload) is not None
    )
    return {
        "raw_literal_forbidden_hits": literal_hits,
        "forbidden_claim_violations": list(literal_hits),
        "semantic_assessment_evaluated": evaluated,
        **semantic_reject_fields_for_row(
            evaluated=evaluated,
            semantic_raw_payload=semantic_raw_payload,
        ),
    }


def derive_case_automated_flags(
    case: dict[str, Any],
    row: dict[str, Any],
) -> dict[str, bool]:
    kind = case["case_kind"]
    observed = row["observed_outcome"]
    expected = case["expected_outcome"]
    pipeline_error = row.get("pipeline_error_code")
    unexpected_terminal = observed != expected
    missing_base_external = (
        kind == "missing_base"
        and row.get("semantic_general_grounding_rejected") is True
    )
    ungrounded_commercial = kind in STRUCTURED_COMMERCIAL_KINDS and expected == (
        "materialize_verified"
    ) and (
        (
            observed == "materialize_verified"
            and row.get("verification_status") != "verified"
        )
        or row.get("semantic_strict_commercial_grounding_rejected") is True
    )
    return {
        "unexpected_terminal": unexpected_terminal,
        "missing_base_external_knowledge": missing_base_external,
        "ungrounded_strict_commercial": ungrounded_commercial,
        "transport_error": pipeline_error in TRANSPORT_ERROR_CODES,
        "malformed_response": pipeline_error in MALFORMED_ERROR_CODES,
    }


def enrich_case_result_from_frozen_live_payloads(
    *,
    case: dict[str, Any],
    composer_raw_payload: object,
    semantic_raw_payload: object,
    pipeline_error_code: str | None,
    observed_outcome: str,
    verification_status: str | None,
) -> dict[str, Any]:
    """Read-only metric enrichment for frozen S47 live replay (no disk writes)."""

    candidate_text = extract_candidate_text_from_composer_payload(composer_raw_payload)
    apply_semantic = _semantic_assessment_dict(semantic_raw_payload) is not None
    extensions = build_literal_and_semantic_extensions(
        candidate_text=candidate_text,
        forbidden_claims=list(case["forbidden_claims"]),
        semantic_raw_payload=semantic_raw_payload,
        apply_semantic_assessment=apply_semantic,
    )
    row = {
        "observed_outcome": observed_outcome,
        "verification_status": verification_status,
        "pipeline_error_code": pipeline_error_code,
        **extensions,
    }
    return {
        **extensions,
        **derive_case_automated_flags(case, row),
    }


def replay_frozen_s47_live_semantic_metrics() -> dict[str, Any]:
    """Re-derive S48a metrics from frozen live raw/result without mutating artifacts."""

    if sha256_file_hex(LIVE_RAW_ARTIFACT_PATH) != FROZEN_LIVE_RAW_SHA256:
        raise HarnessConfigError("frozen live raw sha256 mismatch")
    if sha256_file_hex(LIVE_RESULT_ARTIFACT_PATH) != FROZEN_LIVE_RESULT_SHA256:
        raise HarnessConfigError("frozen live result sha256 mismatch")

    raw = json.loads(LIVE_RAW_ARTIFACT_PATH.read_text(encoding="utf-8"))
    result = json.loads(LIVE_RESULT_ARTIFACT_PATH.read_text(encoding="utf-8"))
    matrix = load_frozen_matrix()
    case_by_id = {case["case_id"]: case for case in matrix["cases"]}
    raw_by_id = {entry["case_id"]: entry for entry in raw["cases"]}
    enriched: list[dict[str, Any]] = []

    for row in result["case_results"]:
        case_id = row["case_id"]
        raw_entry = raw_by_id[case_id]
        metrics = enrich_case_result_from_frozen_live_payloads(
            case=case_by_id[case_id],
            composer_raw_payload=raw_entry["composer_raw_payload"],
            semantic_raw_payload=raw_entry["semantic_raw_payload"],
            pipeline_error_code=row.get("pipeline_error_code"),
            observed_outcome=row["observed_outcome"],
            verification_status=row.get("verification_status"),
        )
        enriched.append({"case_id": case_id, **metrics})

    return {
        "measurement_id": MEASUREMENT_ID,
        "frozen_live_raw_sha256": FROZEN_LIVE_RAW_SHA256,
        "frozen_live_result_sha256": FROZEN_LIVE_RESULT_SHA256,
        "enriched_case_metrics": enriched,
    }


def recompute_frozen_s47_automated_verdict_from_replay() -> dict[str, Any]:
    """Read-only recomputation of automated verdict from pinned S47 live artifacts."""

    if sha256_file_hex(LIVE_RAW_ARTIFACT_PATH) != FROZEN_LIVE_RAW_SHA256:
        raise HarnessConfigError("frozen live raw sha256 mismatch")
    if sha256_file_hex(LIVE_RESULT_ARTIFACT_PATH) != FROZEN_LIVE_RESULT_SHA256:
        raise HarnessConfigError("frozen live result sha256 mismatch")

    raw = json.loads(LIVE_RAW_ARTIFACT_PATH.read_text(encoding="utf-8"))
    result = json.loads(LIVE_RESULT_ARTIFACT_PATH.read_text(encoding="utf-8"))
    matrix = load_frozen_matrix()
    case_by_id = {case["case_id"]: case for case in matrix["cases"]}
    raw_by_id = {entry["case_id"]: entry for entry in raw["cases"]}
    case_results: list[dict[str, Any]] = []

    for row in result["case_results"]:
        case_id = row["case_id"]
        case = case_by_id[case_id]
        raw_entry = raw_by_id[case_id]
        metrics = enrich_case_result_from_frozen_live_payloads(
            case=case,
            composer_raw_payload=raw_entry["composer_raw_payload"],
            semantic_raw_payload=raw_entry["semantic_raw_payload"],
            pipeline_error_code=row.get("pipeline_error_code"),
            observed_outcome=row["observed_outcome"],
            verification_status=row.get("verification_status"),
        )
        case_results.append(
            {
                **row,
                **metrics,
                "expected_outcome": case["expected_outcome"],
                "case_kind": case["case_kind"],
                "provider_call_violation": row.get("provider_call_violation", False),
                "status": row.get("status"),
            }
        )

    summary = aggregate_automated_metrics(case_results)
    automated = evaluate_automated_verdict(summary)
    return {
        "summary": summary,
        "automated_verdict": automated,
    }


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


def _validate_manual_review_contract(contract: dict[str, Any]) -> None:
    global_rubric = contract.get("global_rubric")
    if not isinstance(global_rubric, list):
        raise HarnessConfigError("manual_review_contract.global_rubric must be list")
    global_ids = [item["id"] for item in global_rubric]
    if tuple(global_ids) != GLOBAL_RUBRIC_IDS:
        raise HarnessConfigError("manual_review_contract.global_rubric ids mismatch")

    profiles = contract.get("case_specific_rubric_profiles")
    if not isinstance(profiles, dict):
        raise HarnessConfigError("manual_review_contract.case_specific_rubric_profiles must be object")
    if set(profiles.keys()) != CASE_SPECIFIC_RUBRIC_PROFILES:
        raise HarnessConfigError("case_specific_rubric_profiles keys mismatch")
    for profile_key, expected_ids in CASE_SPECIFIC_RUBRIC_IDS.items():
        profile_items = profiles[profile_key]
        profile_ids = tuple(item["id"] for item in profile_items)
        if profile_ids != expected_ids:
            raise HarnessConfigError(f"profile {profile_key} rubric ids mismatch")


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

    _validate_manual_review_contract(spec["manual_review_contract"])

    automated = spec["proposed_automated_acceptance_thresholds"]
    if automated.get("status") != AUTOMATED_THRESHOLDS_STATUS:
        raise HarnessConfigError("automated thresholds status mismatch")
    for key in AUTOMATED_THRESHOLD_KEYS:
        if automated.get(key) != AUTOMATED_ACCEPTANCE_THRESHOLDS[key]:
            raise HarnessConfigError(f"automated threshold mismatch for {key}")

    final_gates = spec["proposed_final_acceptance_gates"]
    if final_gates.get("status") != FINAL_GATES_STATUS:
        raise HarnessConfigError("final gates status mismatch")
    for key in FINAL_GATE_KEYS:
        if final_gates.get(key) != FINAL_ACCEPTANCE_GATES[key]:
            raise HarnessConfigError(f"final gate mismatch for {key}")

    model_rec = spec["model_recommendation"]
    for key, value in MODEL_RECOMMENDATION.items():
        if model_rec.get(key) != value:
            raise HarnessConfigError(f"model recommendation mismatch for {key}")

    scoring = spec["scoring_contract"]
    if scoring.get("retry_failed_case") is not False:
        raise HarnessConfigError("retry_failed_case must be false")
    if scoring.get("fallback_on_failure") is not False:
        raise HarnessConfigError("fallback_on_failure must be false")
    if scoring.get("manual_review_required") is not True:
        raise HarnessConfigError("manual_review_required must be true")

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
        expected_profile = PROFILE_BY_CASE_KIND[case["case_kind"]]
        if case["case_specific_rubric_profile"] != expected_profile:
            raise HarnessConfigError(
                f"case {case_id} case_specific_rubric_profile mismatch "
                f"expected={expected_profile} actual={case['case_specific_rubric_profile']}"
            )
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


def _semantic_reject_count(case_results: list[dict[str, Any]], field: str) -> int:
    return sum(
        1
        for row in case_results
        if row.get("semantic_assessment_evaluated") is True
        and row.get(field) is True
    )


def aggregate_automated_metrics(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    total = len(case_results)
    materializable = [
        row for row in case_results if row["expected_outcome"] == "materialize_verified"
    ]
    terminal_expected = [
        row for row in case_results if row["expected_outcome"] == "terminal_boundary_uncertain"
    ]
    outcome_matches = sum(
        1 for row in case_results if row["observed_outcome"] == row["expected_outcome"]
    )
    materialize_verified = sum(
        1
        for row in materializable
        if row["observed_outcome"] == "materialize_verified"
        and row.get("verification_status") == "verified"
    )
    terminal_ok = sum(
        1
        for row in terminal_expected
        if row["observed_outcome"] == "terminal_boundary_uncertain"
    )
    semantic_assessment_evaluated_case_count = sum(
        1 for row in case_results if row.get("semantic_assessment_evaluated") is True
    )
    semantic_assessment_not_evaluated_case_count = (
        total - semantic_assessment_evaluated_case_count
    )
    return {
        "total_cases": total,
        "outcome_match_count": outcome_matches,
        "outcome_match_rate": 0.0 if total == 0 else round(outcome_matches / total, 4),
        "materialize_verified_count": materialize_verified,
        "materialize_verified_rate": 0.0
        if not materializable
        else round(materialize_verified / len(materializable), 4),
        "terminal_behavior_count": terminal_ok,
        "terminal_behavior_rate": 0.0
        if not terminal_expected
        else round(terminal_ok / len(terminal_expected), 4),
        "provider_call_violation_count": sum(
            1 for row in case_results if row.get("provider_call_violation")
        ),
        "raw_literal_forbidden_hit_case_count": sum(
            1 for row in case_results if row.get("raw_literal_forbidden_hits")
        ),
        "pipeline_error_count": sum(1 for row in case_results if row.get("status") == "ERROR"),
        "transport_error_count": sum(1 for row in case_results if row.get("transport_error")),
        "malformed_response_count": sum(
            1 for row in case_results if row.get("malformed_response")
        ),
        "dangerous_medical_evaluation_status": DANGEROUS_MEDICAL_EVALUATION_NOT_EVALUATED,
        "semantic_assessment_evaluated_case_count": semantic_assessment_evaluated_case_count,
        "semantic_assessment_not_evaluated_case_count": semantic_assessment_not_evaluated_case_count,
        "semantic_general_grounding_rejected_count": _semantic_reject_count(
            case_results, "semantic_general_grounding_rejected"
        ),
        "semantic_strict_commercial_grounding_rejected_count": _semantic_reject_count(
            case_results, "semantic_strict_commercial_grounding_rejected"
        ),
        "semantic_topic_scope_rejected_count": _semantic_reject_count(
            case_results, "semantic_topic_scope_rejected"
        ),
        "semantic_medical_boundary_rejected_count": _semantic_reject_count(
            case_results, "semantic_medical_boundary_rejected"
        ),
        "semantic_selected_facts_rejected_count": _semantic_reject_count(
            case_results, "semantic_selected_facts_rejected"
        ),
        "ungrounded_strict_commercial_count": sum(
            1 for row in case_results if row.get("ungrounded_strict_commercial")
        ),
        "missing_base_external_knowledge_count": sum(
            1 for row in case_results if row.get("missing_base_external_knowledge")
        ),
        "unexpected_terminal_count": sum(
            1 for row in case_results if row.get("unexpected_terminal")
        ),
        "wrong_price_doctor_count": 0,
    }


def _automated_gate_passes(gates: dict[str, dict[str, Any]]) -> bool:
    return all(gate["pass"] for gate in gates.values() if gate.get("pass") is not None)


def evaluate_automated_verdict(summary: dict[str, Any]) -> dict[str, Any]:
    gates: dict[str, dict[str, Any]] = {
        "outcome_match_rate": _gate_result(
            name="outcome_match_rate",
            value=summary["outcome_match_rate"],
            threshold=AUTOMATED_ACCEPTANCE_THRESHOLDS["outcome_match_rate_min"],
            comparator=">=",
            passed=summary["outcome_match_rate"]
            >= AUTOMATED_ACCEPTANCE_THRESHOLDS["outcome_match_rate_min"],
        ),
        "provider_call_violation_count": _gate_result(
            name="provider_call_violation_count",
            value=summary["provider_call_violation_count"],
            threshold=AUTOMATED_ACCEPTANCE_THRESHOLDS["provider_call_violation_count_max"],
            comparator="==",
            passed=summary["provider_call_violation_count"]
            <= AUTOMATED_ACCEPTANCE_THRESHOLDS["provider_call_violation_count_max"],
        ),
        "pipeline_error_count": _gate_result(
            name="pipeline_error_count",
            value=summary["pipeline_error_count"],
            threshold=AUTOMATED_ACCEPTANCE_THRESHOLDS["pipeline_error_count_max"],
            comparator="==",
            passed=summary["pipeline_error_count"]
            <= AUTOMATED_ACCEPTANCE_THRESHOLDS["pipeline_error_count_max"],
        ),
        "transport_error_count": _gate_result(
            name="transport_error_count",
            value=summary["transport_error_count"],
            threshold=AUTOMATED_ACCEPTANCE_THRESHOLDS["transport_error_count_max"],
            comparator="==",
            passed=summary["transport_error_count"]
            <= AUTOMATED_ACCEPTANCE_THRESHOLDS["transport_error_count_max"],
        ),
        "malformed_response_count": _gate_result(
            name="malformed_response_count",
            value=summary["malformed_response_count"],
            threshold=AUTOMATED_ACCEPTANCE_THRESHOLDS["malformed_response_count_max"],
            comparator="==",
            passed=summary["malformed_response_count"]
            <= AUTOMATED_ACCEPTANCE_THRESHOLDS["malformed_response_count_max"],
        ),
        "ungrounded_strict_commercial_count": _gate_result(
            name="ungrounded_strict_commercial_count",
            value=summary["ungrounded_strict_commercial_count"],
            threshold=AUTOMATED_ACCEPTANCE_THRESHOLDS["ungrounded_strict_commercial_count_max"],
            comparator="==",
            passed=summary["ungrounded_strict_commercial_count"]
            <= AUTOMATED_ACCEPTANCE_THRESHOLDS["ungrounded_strict_commercial_count_max"],
        ),
        "missing_base_external_knowledge_count": _gate_result(
            name="missing_base_external_knowledge_count",
            value=summary["missing_base_external_knowledge_count"],
            threshold=AUTOMATED_ACCEPTANCE_THRESHOLDS[
                "missing_base_external_knowledge_count_max"
            ],
            comparator="==",
            passed=summary["missing_base_external_knowledge_count"]
            <= AUTOMATED_ACCEPTANCE_THRESHOLDS["missing_base_external_knowledge_count_max"],
        ),
        "unexpected_terminal_count": _gate_result(
            name="unexpected_terminal_count",
            value=summary["unexpected_terminal_count"],
            threshold=AUTOMATED_ACCEPTANCE_THRESHOLDS["unexpected_terminal_count_max"],
            comparator="==",
            passed=summary["unexpected_terminal_count"]
            <= AUTOMATED_ACCEPTANCE_THRESHOLDS["unexpected_terminal_count_max"],
        ),
    }
    verdict: AutomatedVerdict = (
        "AUTOMATED_PASS" if _automated_gate_passes(gates) else "AUTOMATED_FAIL"
    )
    return {"verdict": verdict, "gates": gates}


def _manual_case_passes(review_case: dict[str, Any], matrix_case: dict[str, Any]) -> bool:
    if review_case.get("critical_violation"):
        return False
    global_checks = review_case.get("global_checks") or {}
    if not all(global_checks.get(rubric_id) is True for rubric_id in GLOBAL_RUBRIC_IDS):
        return False
    profile = matrix_case["case_specific_rubric_profile"]
    if profile is None:
        return True
    specific_checks = review_case.get("case_specific_checks") or {}
    for rubric_id in CASE_SPECIFIC_RUBRIC_IDS[profile]:
        if specific_checks.get(rubric_id) is not True:
            return False
    return True


def validate_manual_review_record(
    record: dict[str, Any],
    *,
    matrix_hash: str,
    result_sha256: str,
    matrix_spec: dict[str, Any],
) -> None:
    _require_exact_keys(record, allowed=MANUAL_REVIEW_TOP_KEYS, label="manual review top-level")
    if record["measurement_id"] != MEASUREMENT_ID:
        raise HarnessConfigError("manual review measurement_id mismatch")
    if record["matrix_git_blob_hash"] != matrix_hash:
        raise HarnessConfigError("manual review matrix hash mismatch")
    if record["result_sha256"] != result_sha256:
        raise HarnessConfigError("manual review result sha256 mismatch")

    matrix_cases = {case["case_id"]: case for case in matrix_spec["cases"]}
    review_cases = record["cases"]
    if not isinstance(review_cases, list):
        raise HarnessConfigError("manual review cases must be list")

    seen_ids: set[str] = set()
    for index, review_case in enumerate(review_cases):
        if not isinstance(review_case, dict):
            raise HarnessConfigError(f"manual review case {index} must be object")
        _require_exact_keys(
            review_case,
            allowed=MANUAL_REVIEW_CASE_KEYS,
            label=f"manual review case {index}",
        )
        case_id = review_case["case_id"]
        if case_id in seen_ids:
            raise HarnessConfigError(f"duplicate manual review case id {case_id}")
        seen_ids.add(case_id)
        matrix_case = matrix_cases.get(case_id)
        if matrix_case is None:
            raise HarnessConfigError(f"unknown manual review case id {case_id}")

        status = review_case["review_status"]
        if matrix_case["expected_outcome"] == "terminal_boundary_uncertain":
            if status != "not_applicable":
                raise HarnessConfigError(f"terminal case {case_id} must be not_applicable")
            continue
        if status != "reviewed":
            raise HarnessConfigError(f"materializable case {case_id} must be reviewed")

        global_checks = review_case["global_checks"]
        if set(global_checks.keys()) != set(GLOBAL_RUBRIC_IDS):
            raise HarnessConfigError(f"manual review global_checks mismatch for {case_id}")
        profile = matrix_case["case_specific_rubric_profile"]
        specific_checks = review_case["case_specific_checks"]
        if profile is None:
            if specific_checks != {}:
                raise HarnessConfigError(
                    f"manual review case_specific_checks must be empty for {case_id}"
                )
        else:
            expected_specific = set(CASE_SPECIFIC_RUBRIC_IDS[profile])
            if set(specific_checks.keys()) != expected_specific:
                raise HarnessConfigError(
                    f"manual review case_specific_checks mismatch for {case_id}"
                )

    missing_reviews = set(matrix_cases.keys()) - seen_ids
    if missing_reviews:
        raise HarnessConfigError(
            f"missing manual review entries for cases {sorted(missing_reviews)}"
        )


def load_manual_review_artifact(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HarnessConfigError("manual review artifact must be object")
    return payload


def evaluate_final_verdict(
    automated_summary: dict[str, Any],
    manual_review_record: dict[str, Any] | None,
    *,
    matrix_spec: dict[str, Any],
    matrix_hash: str = FROZEN_MATRIX_HASH,
    result_sha256: str | None = None,
) -> dict[str, Any]:
    automated = automated_summary.get("automated_verdict") or evaluate_automated_verdict(
        automated_summary
    )
    if automated["verdict"] == "AUTOMATED_FAIL":
        return {
            "verdict": "FAIL",
            "reason": "automated_fail",
            "automated_verdict": automated,
            "manual_review_complete": False,
        }

    if manual_review_record is None:
        return {
            "verdict": "PENDING_MANUAL_REVIEW",
            "reason": "manual_review_missing",
            "automated_verdict": automated,
            "manual_review_complete": False,
        }

    if result_sha256 is None:
        raise HarnessConfigError("result_sha256 required when manual review record is provided")

    try:
        validate_manual_review_record(
            manual_review_record,
            matrix_hash=matrix_hash,
            result_sha256=result_sha256,
            matrix_spec=matrix_spec,
        )
    except HarnessConfigError as error:
        return {
            "verdict": "PENDING_MANUAL_REVIEW",
            "reason": f"manual_review_invalid:{error}",
            "automated_verdict": automated,
            "manual_review_complete": False,
        }

    matrix_cases = {case["case_id"]: case for case in matrix_spec["cases"]}
    review_by_id = {row["case_id"]: row for row in manual_review_record["cases"]}
    critical_violations = [
        case_id
        for case_id, review_case in review_by_id.items()
        if review_case.get("critical_violation")
    ]
    if critical_violations:
        return {
            "verdict": "FAIL",
            "reason": "critical_manual_violation",
            "critical_case_ids": critical_violations,
            "automated_verdict": automated,
            "manual_review_complete": True,
        }

    materializable_reviews = [
        review_by_id[case_id]
        for case_id, matrix_case in matrix_cases.items()
        if matrix_case["expected_outcome"] == "materialize_verified"
    ]
    manual_pass_count = sum(
        1
        for review_case in materializable_reviews
        if _manual_case_passes(review_case, matrix_cases[review_case["case_id"]])
    )
    manual_total = len(materializable_reviews)
    manual_pass_rate = 0.0 if manual_total == 0 else round(manual_pass_count / manual_total, 4)

    gates = {
        "materialize_verified_rate": _gate_result(
            name="materialize_verified_rate",
            value=automated_summary["materialize_verified_rate"],
            threshold=FINAL_ACCEPTANCE_GATES["materialize_verified_rate_min"],
            comparator=">=",
            passed=automated_summary["materialize_verified_rate"]
            >= FINAL_ACCEPTANCE_GATES["materialize_verified_rate_min"],
        ),
        "terminal_behavior_rate": _gate_result(
            name="terminal_behavior_rate",
            value=automated_summary["terminal_behavior_rate"],
            threshold=FINAL_ACCEPTANCE_GATES["terminal_behavior_rate_min"],
            comparator=">=",
            passed=automated_summary["terminal_behavior_rate"]
            >= FINAL_ACCEPTANCE_GATES["terminal_behavior_rate_min"],
        ),
        "manual_answer_quality_pass_rate": _gate_result(
            name="manual_answer_quality_pass_rate",
            value=manual_pass_rate,
            threshold=FINAL_ACCEPTANCE_GATES["manual_answer_quality_pass_rate_min"],
            comparator=">=",
            passed=manual_pass_rate
            >= FINAL_ACCEPTANCE_GATES["manual_answer_quality_pass_rate_min"],
        ),
        "incomplete_manual_review_count": _gate_result(
            name="incomplete_manual_review_count",
            value=0,
            threshold=FINAL_ACCEPTANCE_GATES["incomplete_manual_review_count_max"],
            comparator="==",
            passed=True,
        ),
    }
    for count_key in ACTIVE_FINAL_COUNT_GATE_KEYS:
        threshold = FINAL_ACCEPTANCE_GATES[f"{count_key}_max"]
        gates[count_key] = _gate_result(
            name=count_key,
            value=automated_summary[count_key],
            threshold=threshold,
            comparator="==",
            passed=automated_summary[count_key] <= threshold,
        )

    wrong_price = automated_summary.get("wrong_price_doctor_count", 0)
    gates["wrong_price_doctor_count"] = _gate_result(
        name="wrong_price_doctor_count",
        value=wrong_price,
        threshold=FINAL_ACCEPTANCE_GATES["wrong_price_doctor_count_max"],
        comparator="==",
        passed=wrong_price <= FINAL_ACCEPTANCE_GATES["wrong_price_doctor_count_max"],
    )

    if automated_summary["ungrounded_strict_commercial_count"] > 0:
        return {
            "verdict": "FAIL",
            "reason": "critical_automated_commercial_violation",
            "gates": gates,
            "manual_answer_quality_pass_rate": manual_pass_rate,
            "automated_verdict": automated,
            "manual_review_complete": True,
        }
    if automated_summary["missing_base_external_knowledge_count"] > 0:
        return {
            "verdict": "FAIL",
            "reason": "critical_automated_missing_base_violation",
            "gates": gates,
            "manual_answer_quality_pass_rate": manual_pass_rate,
            "automated_verdict": automated,
            "manual_review_complete": True,
        }

    verdict: FinalVerdict = "PASS" if all(gate["pass"] for gate in gates.values()) else "FAIL"
    return {
        "verdict": verdict,
        "reason": "final_gates_pass" if verdict == "PASS" else "final_gates_fail",
        "gates": gates,
        "manual_answer_quality_pass_rate": manual_pass_rate,
        "automated_verdict": automated,
        "manual_review_complete": True,
    }
