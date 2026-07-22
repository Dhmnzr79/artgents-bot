"""Offline harness for S47 FullContext response live eval preparation."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, is_dataclass
from datetime import date
from pathlib import Path
from typing import Any

_EVAL_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _EVAL_DIR.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from contracts.doctor_schema_refs import (
    DoctorCatalogExternalIndex,
    build_doctor_source_refs,
    validate_doctor_catalog_external_refs,
)
from contracts.response_schema import TargetStrategyMatch
from contracts.response_schema_refs import (
    ResponseSchemaExternalIndex,
    validate_response_schema_external_refs,
)
from contracts.service_consultation import validate_service_consultation_refs
from contracts.target_medical_boundary import (
    TargetMedicalBoundaryResult,
    TargetMedicalBoundaryTerminalEnforcement,
)
from contracts.target_turn_frame_dispatch import (
    TargetTurnFrameBoundMaterializeResponse,
    TargetTurnFrameBoundTerminalResponse,
)
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.response_schema_loader import load_response_schema_bundle
from core.service_consultation_source import build_service_consultation_values
from core.target_boundary_enforced_fullcontext_response import (
    run_target_offline_boundary_enforced_fullcontext_response,
)
from core.target_cached_full_context import build_target_cached_full_context
from core.target_composer_executor import TargetComposerTone
from core.turn_frame_from_raw import build_turn_frame_from_raw
from evals.v5.fullcontext_response_eval_backend import (
    FullContextResponseEvalComposerAdapter,
    FullContextResponseEvalLiveNotConfiguredError,
    FullContextResponseEvalRecordingComposerBackend,
    FullContextResponseEvalRecordingSemanticBackend,
    FullContextResponseEvalSemanticAdapter,
    FullContextResponseEvalTransportError,
)
from evals.v5.fullcontext_response_eval_contract import (
    AUTOMATED_ACCEPTANCE_THRESHOLDS,
    AUTOMATED_THRESHOLDS_STATUS,
    CASE_RESULT_KEYS,
    DEFAULT_LIVE_ARTIFACT_PATHS,
    FINAL_ACCEPTANCE_GATES,
    FINAL_GATES_STATUS,
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    MALFORMED_ERROR_CODES,
    MEASUREMENT_ID,
    MATRIX_PATH,
    MODEL_RECOMMENDATION,
    STRUCTURED_COMMERCIAL_KINDS,
    TRANSPORT_ERROR_CODES,
    HarnessConfigError,
    LiveArtifactWriteError,
    aggregate_automated_metrics,
    assert_live_artifacts_absent,
    evaluate_automated_verdict,
    evaluate_final_verdict,
    load_frozen_matrix,
)


def _serialize_raw_payload(payload: object) -> object:
    if is_dataclass(payload):
        return asdict(payload)
    if isinstance(payload, dict):
        return dict(payload)
    if hasattr(payload, "__dict__") and isinstance(payload.__dict__, dict):
        return {
            key: value
            for key, value in payload.__dict__.items()
            if not key.startswith("_")
        }
    return repr(payload)


def _load_pipeline_context(spec: dict[str, Any]) -> dict[str, object]:
    defaults = spec["pipeline_defaults"]
    demo_root = _REPO_ROOT / "clients" / "demo"
    md_root = _REPO_ROOT / str(defaults["md_root"])
    target_root = _REPO_ROOT / str(defaults["target_root"])
    bundle = load_response_schema_bundle(target_root)
    doctors = load_doctor_catalog(demo_root / "doctor_catalog.json")
    kb_refs = build_response_schema_kb_refs(md_root)
    doctor_index = DoctorCatalogExternalIndex(
        service_ids=tuple(bundle.services),
        kb_refs=kb_refs,
    )
    validate_doctor_catalog_external_refs(doctors, doctor_index)
    external_index = ResponseSchemaExternalIndex(
        kb_refs=kb_refs,
        doctor_refs=build_doctor_source_refs(doctors),
    )
    validate_response_schema_external_refs(bundle, external_index)
    consultations = build_service_consultation_values(md_root)
    validate_service_consultation_refs(consultations, bundle.services)
    return {
        "bundle": bundle,
        "doctor_catalog": doctors,
        "external_index": external_index,
        "consultation_values": consultations,
        "md_root": md_root,
        "cached_full_context": build_target_cached_full_context(md_root),
        "brand_term": None,
        "strategy_context": TargetStrategyMatch(
            family="implantology",
            extent="full_arch",
        ),
        "semantic_context": str(defaults["semantic_context"]),
        "today": date(2026, 7, 22),
        "include_initial_block": bool(defaults["include_initial_block"]),
        "include_consultation_close": bool(defaults["include_consultation_close"]),
        "include_cta": bool(defaults["include_cta"]),
        "tone": TargetComposerTone(
            key="commercial_warm",
            instruction="Отвечай доброжелательно и без давления.",
        ),
    }


def classify_observed_outcome(result: object) -> tuple[str, str | None, str | None]:
    if type(result) is TargetMedicalBoundaryTerminalEnforcement:
        return "terminal_boundary_uncertain", None, None
    if isinstance(result, TargetTurnFrameBoundMaterializeResponse):
        return (
            "materialize_verified",
            result.dispatch.policy_request.response_mode,
            result.verified.verification_status,
        )
    if isinstance(result, TargetTurnFrameBoundTerminalResponse):
        return f"terminal_s41_{result.dispatch.terminal_mode}", None, None
    return "unknown", None, None


def provider_call_violation(
    *,
    expected_outcome: str,
    composer_calls: int,
    semantic_calls: int,
) -> bool:
    if expected_outcome == "terminal_boundary_uncertain":
        return composer_calls != 0 or semantic_calls != 0
    if expected_outcome == "materialize_verified":
        return composer_calls != 1 or semantic_calls != 1
    return True


def forbidden_claim_violations(text: str, forbidden_claims: Sequence[str]) -> list[str]:
    lowered = text.lower()
    return [claim for claim in forbidden_claims if claim.lower() in lowered]


def derive_case_automated_flags(
    case: dict[str, Any],
    row: dict[str, Any],
) -> dict[str, bool]:
    kind = case["case_kind"]
    medical = case["medical_safety"]
    forbidden = row["forbidden_claim_violations"]
    observed = row["observed_outcome"]
    expected = case["expected_outcome"]
    pipeline_error = row.get("pipeline_error_code")
    unexpected_terminal = observed != expected
    missing_base_external = kind == "missing_base" and bool(forbidden)
    medical_kinds = {
        "known_medical_topic",
        "medical_boundary_personal",
        "medical_boundary_diagnosis",
        "medical_boundary_treatment_choice",
        "pain_reassurance",
    }
    dangerous_medical = bool(forbidden) and (
        kind in medical_kinds
        or bool(medical.get("no_diagnosis"))
        or bool(medical.get("no_personal_eligibility"))
    )
    ungrounded_commercial = (
        kind in STRUCTURED_COMMERCIAL_KINDS
        and expected == "materialize_verified"
        and observed == "materialize_verified"
        and row.get("verification_status") != "verified"
    )
    return {
        "unexpected_terminal": unexpected_terminal,
        "missing_base_external_knowledge": missing_base_external,
        "dangerous_medical_violation": dangerous_medical and not missing_base_external,
        "ungrounded_strict_commercial": ungrounded_commercial,
        "transport_error": pipeline_error in TRANSPORT_ERROR_CODES,
        "malformed_response": pipeline_error in MALFORMED_ERROR_CODES,
    }


def run_case(
    *,
    case: dict[str, Any],
    index: int,
    spec: dict[str, Any],
    context: dict[str, object],
    composer_backend: FullContextResponseEvalRecordingComposerBackend,
    semantic_backend: FullContextResponseEvalRecordingSemanticBackend,
) -> dict[str, Any]:
    allowlist = spec["turn_frame_allowlist"]
    turn_frame = build_turn_frame_from_raw(
        case["turn_frame_raw"],
        allowed_topics=frozenset(allowlist["allowed_topics"]),
        allowed_service_ids=frozenset(allowlist["allowed_service_ids"]),
    )
    boundary = TargetMedicalBoundaryResult.model_validate(case["boundary_result"])
    policy = case["policy_envelope"]
    try:
        result = run_target_offline_boundary_enforced_fullcontext_response(
            turn_frame,
            boundary,
            context["bundle"],  # type: ignore[arg-type]
            context["doctor_catalog"],  # type: ignore[arg-type]
            context["external_index"],  # type: ignore[arg-type]
            context["consultation_values"],  # type: ignore[arg-type]
            tone_key=policy["tone_key"],
            allowed_topics=tuple(policy["allowed_topics"]),
            forbidden_topics=tuple(policy["forbidden_topics"]),
            required_fact_ids=tuple(policy["required_fact_ids"]),
            allow_marketing_facts=bool(policy["allow_marketing_facts"]),
            allow_consultation_close=bool(policy["allow_consultation_close"]),
            allow_cta=bool(policy["allow_cta"]),
            min_topic_confidence=float(policy["min_topic_confidence"]),
            min_service_confidence=float(policy["min_service_confidence"]),
            min_intent_confidence=float(policy["min_intent_confidence"]),
            brand_term=context["brand_term"],  # type: ignore[arg-type]
            strategy_context=context["strategy_context"],  # type: ignore[arg-type]
            semantic_context=str(context["semantic_context"]),
            today=context["today"],  # type: ignore[arg-type]
            md_root=context["md_root"],  # type: ignore[arg-type]
            cached_full_context=context["cached_full_context"],  # type: ignore[arg-type]
            include_initial_block=bool(context["include_initial_block"]),
            include_consultation_close=bool(context["include_consultation_close"]),
            include_cta=bool(context["include_cta"]),
            user_message=str(case["user_message"]).strip(),
            tone=context["tone"],  # type: ignore[arg-type]
            composer_backend=composer_backend,
            semantic_backend=semantic_backend,
        )
    except Exception as error:
        row = {
            "index": index,
            "case_id": case["case_id"],
            "case_kind": case["case_kind"],
            "expected_outcome": case["expected_outcome"],
            "observed_outcome": "pipeline_error",
            "expected_response_mode": case["expected_response_mode"],
            "observed_response_mode": None,
            "response_text": None,
            "composer_call_count": composer_backend.call_count,
            "semantic_call_count": semantic_backend.call_count,
            "provider_call_violation": provider_call_violation(
                expected_outcome=case["expected_outcome"],
                composer_calls=composer_backend.call_count,
                semantic_calls=semantic_backend.call_count,
            ),
            "forbidden_claim_violations": [],
            "pipeline_error_code": type(error).__name__,
            "verification_status": None,
            "composer_raw_payload": _serialize_raw_payload(
                composer_backend.captures[-1].raw_backend_payload
                if composer_backend.captures
                else None
            ),
            "semantic_raw_payload": _serialize_raw_payload(
                semantic_backend.captures[-1].raw_backend_payload
                if semantic_backend.captures
                else None
            ),
            "status": "ERROR",
            "reason": getattr(error, "code", type(error).__name__),
        }
        row.update(derive_case_automated_flags(case, row))
        return row

    observed_outcome, observed_mode, verification_status = classify_observed_outcome(result)
    response_text: str | None
    if isinstance(result, TargetTurnFrameBoundMaterializeResponse):
        response_text = result.verified.text
    else:
        response_text = None

    violations = (
        forbidden_claim_violations(response_text or "", case["forbidden_claims"])
        if response_text
        else []
    )
    call_violation = provider_call_violation(
        expected_outcome=case["expected_outcome"],
        composer_calls=composer_backend.call_count,
        semantic_calls=semantic_backend.call_count,
    )
    outcome_match = observed_outcome == case["expected_outcome"]
    mode_match = (
        case["expected_response_mode"] is None
        or observed_mode == case["expected_response_mode"]
    )
    status = "OK" if outcome_match and mode_match and not call_violation and not violations else "REVIEW"

    row = {
        "index": index,
        "case_id": case["case_id"],
        "case_kind": case["case_kind"],
        "expected_outcome": case["expected_outcome"],
        "observed_outcome": observed_outcome,
        "expected_response_mode": case["expected_response_mode"],
        "observed_response_mode": observed_mode,
        "response_text": response_text,
        "composer_call_count": composer_backend.call_count,
        "semantic_call_count": semantic_backend.call_count,
        "provider_call_violation": call_violation,
        "forbidden_claim_violations": violations,
        "pipeline_error_code": None,
        "verification_status": verification_status,
        "composer_raw_payload": _serialize_raw_payload(
            composer_backend.captures[-1].raw_backend_payload
            if composer_backend.captures
            else None
        ),
        "semantic_raw_payload": _serialize_raw_payload(
            semantic_backend.captures[-1].raw_backend_payload
            if semantic_backend.captures
            else None
        ),
        "status": status,
        "reason": "outcome_match" if status == "OK" else "manual_or_metric_review",
    }
    row.update(derive_case_automated_flags(case, row))
    return row


def summarize_results(
    case_results: Sequence[dict[str, Any]],
    *,
    matrix_spec: dict[str, Any] | None = None,
    manual_review_record: dict[str, Any] | None = None,
    result_sha256: str | None = None,
) -> dict[str, Any]:
    summary = {
        "measurement_id": MEASUREMENT_ID,
        **aggregate_automated_metrics(list(case_results)),
        "proposed_automated_acceptance_thresholds": dict(AUTOMATED_ACCEPTANCE_THRESHOLDS),
        "automated_thresholds_status": AUTOMATED_THRESHOLDS_STATUS,
        "proposed_final_acceptance_gates": dict(FINAL_ACCEPTANCE_GATES),
        "final_gates_status": FINAL_GATES_STATUS,
        "model_recommendation": dict(MODEL_RECOMMENDATION),
    }
    automated = evaluate_automated_verdict(summary)
    summary["automated_verdict"] = automated
    spec = matrix_spec or load_frozen_matrix()
    summary["final_verdict"] = evaluate_final_verdict(
        summary,
        manual_review_record,
        matrix_spec=spec,
        result_sha256=result_sha256,
    )
    return summary


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except FileExistsError as error:
        raise LiveArtifactWriteError(
            f"live artifact already exists; silent overwrite forbidden: {path}"
        ) from error


def run_harness_with_backend_factory(
    *,
    backend_factory: Callable[
        [dict[str, Any]],
        tuple[
            FullContextResponseEvalRecordingComposerBackend,
            FullContextResponseEvalRecordingSemanticBackend,
        ],
    ],
    matrix_path: Path = MATRIX_PATH,
    artifact_paths: Sequence[Path] | None = None,
) -> dict[str, Any]:
    spec = load_frozen_matrix(path=matrix_path)
    context = _load_pipeline_context(spec)
    if artifact_paths is not None:
        assert_live_artifacts_absent(tuple(artifact_paths))

    case_results: list[dict[str, Any]] = []
    for index, case in enumerate(spec["cases"]):
        composer, semantic = backend_factory(case)
        case_results.append(
            run_case(
                case=case,
                index=index,
                spec=spec,
                context=context,
                composer_backend=composer,
                semantic_backend=semantic,
            )
        )

    keys = frozenset(case_results[0].keys()) if case_results else CASE_RESULT_KEYS
    for row in case_results:
        if frozenset(row.keys()) != keys:
            raise HarnessConfigError("case result shape mismatch")

    spec = load_frozen_matrix(path=matrix_path)
    return {
        "summary": summarize_results(case_results, matrix_spec=spec),
        "case_results": case_results,
    }


def _offline_backend_factory(
    case: dict[str, Any],
) -> tuple[
    FullContextResponseEvalRecordingComposerBackend,
    FullContextResponseEvalRecordingSemanticBackend,
]:
    return (
        FullContextResponseEvalRecordingComposerBackend(
            str(case["offline_composer_stub"])
        ),
        FullContextResponseEvalRecordingSemanticBackend(),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=MEASUREMENT_ID)
    parser.add_argument("--matrix", default=str(MATRIX_PATH))
    parser.add_argument("--output", default=str(LIVE_RESULT_ARTIFACT_PATH))
    parser.add_argument("--raw-output", default=str(LIVE_RAW_ARTIFACT_PATH))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate matrix only; do not execute cases",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Reserved for future permitted live eval (blocked in S47)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        spec = load_frozen_matrix(path=Path(args.matrix))
    except HarnessConfigError as error:
        print(f"CONFIG_ERROR: {error}", file=sys.stderr)
        return 2

    if args.dry_run:
        payload = {
            "measurement_id": MEASUREMENT_ID,
            "total_cases": len(spec["cases"]),
            "dry_run": True,
            "proposed_automated_acceptance_thresholds": dict(AUTOMATED_ACCEPTANCE_THRESHOLDS),
            "automated_thresholds_status": AUTOMATED_THRESHOLDS_STATUS,
            "proposed_final_acceptance_gates": dict(FINAL_ACCEPTANCE_GATES),
            "final_gates_status": FINAL_GATES_STATUS,
            "model_recommendation": dict(MODEL_RECOMMENDATION),
            "manual_review_required": spec["scoring_contract"]["manual_review_required"],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.live:
        print(
            "LIVE_NOT_CONFIGURED: S47 prepared harness only; live delegate not implemented",
            file=sys.stderr,
        )
        return 3

    print(
        "LIVE_NOT_CONFIGURED: permitted live run requires explicit delegate backend injection",
        file=sys.stderr,
    )
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
