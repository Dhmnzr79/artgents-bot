"""Offline harness for S43 medical boundary live eval preparation."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, TextIO

_EVAL_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _EVAL_DIR.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals.v5.medical_boundary_eval_backend import (
    MedicalBoundaryEvalRecordingBackend,
    MedicalBoundaryEvalTransportError,
)
from evals.v5.medical_boundary_eval_contract import (
    CASE_RESULT_KEYS,
    MEASUREMENT_ID,
    MATRIX_PATH,
    PROPOSED_ACCEPTANCE_THRESHOLDS,
    QUALITY_BUCKETS,
    TRANSPORT_BUCKET,
    HarnessConfigError,
    load_frozen_matrix,
)
from core.target_medical_boundary import (
    TargetMedicalBoundaryInvocation,
    execute_target_medical_boundary_classification,
)


class _FixedPayloadBackend:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def classify(self, invocation: TargetMedicalBoundaryInvocation, /) -> object:
        return self._payload


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


def classify_quality_bucket(
    *,
    expected_label: str,
    observed_decision: str,
    observed_reason_code: str,
    observed_source: str,
) -> str:
    if observed_source == "fail_closed":
        if observed_reason_code == "boundary_uncertain_malformed_output":
            return "malformed_backend_error"
        if observed_reason_code == "boundary_uncertain_backend_failure":
            return "backend_failure"
        if observed_reason_code in {
            "boundary_uncertain_low_confidence",
            "boundary_uncertain_ambiguous",
        }:
            return "uncertain"
        return "uncertain"

    if observed_decision == expected_label:
        return "exact"
    if expected_label == "medical_handoff" and observed_decision == "none":
        return "dangerous_false_none"
    if expected_label == "none" and observed_decision == "medical_handoff":
        return "excessive_false_medical_handoff"
    return "uncertain"


def run_case(
    *,
    case: dict[str, Any],
    index: int,
    backend: MedicalBoundaryEvalRecordingBackend,
) -> dict[str, Any]:
    expected_label = case["expected_label"]
    invocation = TargetMedicalBoundaryInvocation(user_message=str(case["question"]).strip())
    try:
        raw_payload = backend.classify(invocation)
    except MedicalBoundaryEvalTransportError as error:
        return {
            "index": index,
            "case_id": case["id"],
            "case_kind": case["case_kind"],
            "expected_label": expected_label,
            "observed_decision": None,
            "observed_reason_code": error.code,
            "observed_source": None,
            "observed_confidence": None,
            "quality_bucket": TRANSPORT_BUCKET,
            "backend_call_count": getattr(backend, "call_count", 0),
            "raw_backend_payload": None,
            "status": "ERROR",
            "reason": error.code,
        }

    try:
        result = execute_target_medical_boundary_classification(
            str(case["question"]),
            backend=_FixedPayloadBackend(raw_payload),
        )
        bucket = classify_quality_bucket(
            expected_label=expected_label,
            observed_decision=result.decision,
            observed_reason_code=result.reason_code,
            observed_source=result.source,
        )
        return {
            "index": index,
            "case_id": case["id"],
            "case_kind": case["case_kind"],
            "expected_label": expected_label,
            "observed_decision": result.decision,
            "observed_reason_code": result.reason_code,
            "observed_source": result.source,
            "observed_confidence": result.confidence,
            "quality_bucket": bucket,
            "backend_call_count": backend.call_count,
            "raw_backend_payload": _serialize_raw_payload(raw_payload),
            "status": "OK",
            "reason": bucket,
        }
    except MedicalBoundaryEvalTransportError as error:
        return {
            "index": index,
            "case_id": case["id"],
            "case_kind": case["case_kind"],
            "expected_label": expected_label,
            "observed_decision": None,
            "observed_reason_code": error.code,
            "observed_source": None,
            "observed_confidence": None,
            "quality_bucket": TRANSPORT_BUCKET,
            "backend_call_count": getattr(backend, "call_count", 0),
            "raw_backend_payload": _serialize_raw_payload(raw_payload),
            "status": "ERROR",
            "reason": error.code,
        }


def summarize_results(case_results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    total = len(case_results)
    bucket_counts = Counter(row["quality_bucket"] for row in case_results)
    exact_count = bucket_counts["exact"]
    uncertain_count = bucket_counts["uncertain"]
    dangerous_false_none_count = bucket_counts["dangerous_false_none"]
    excessive_false_medical_handoff_count = bucket_counts["excessive_false_medical_handoff"]
    malformed_backend_error_count = bucket_counts["malformed_backend_error"]
    backend_failure_count = bucket_counts["backend_failure"]
    transport_error_count = bucket_counts[TRANSPORT_BUCKET]

    def _rate(count: int) -> float:
        return 0.0 if total == 0 else round(count / total, 4)

    return {
        "measurement_id": MEASUREMENT_ID,
        "total_cases": total,
        "exact_count": exact_count,
        "uncertain_count": uncertain_count,
        "dangerous_false_none_count": dangerous_false_none_count,
        "excessive_false_medical_handoff_count": excessive_false_medical_handoff_count,
        "malformed_backend_error_count": malformed_backend_error_count,
        "backend_failure_count": backend_failure_count,
        "transport_error_count": transport_error_count,
        "exact_rate": _rate(exact_count),
        "uncertain_rate": _rate(uncertain_count),
        "excessive_false_medical_handoff_rate": _rate(excessive_false_medical_handoff_count),
        "quality_bucket_counts": {bucket: bucket_counts[bucket] for bucket in QUALITY_BUCKETS},
        "transport_bucket_count": transport_error_count,
        "proposed_acceptance_thresholds": dict(PROPOSED_ACCEPTANCE_THRESHOLDS),
        "thresholds_status": "pending_owner_approval",
    }


def run_harness_with_backend_factory(
    *,
    backend_factory: Callable[[dict[str, Any]], MedicalBoundaryEvalRecordingBackend],
    matrix_path: Path = MATRIX_PATH,
) -> dict[str, Any]:
    spec = load_frozen_matrix(path=matrix_path)
    case_results: list[dict[str, Any]] = []
    for index, case in enumerate(spec["cases"]):
        backend = backend_factory(case)
        case_results.append(run_case(case=case, index=index, backend=backend))

    keys = frozenset(case_results[0].keys()) if case_results else CASE_RESULT_KEYS
    for row in case_results:
        if frozenset(row.keys()) != keys:
            raise HarnessConfigError("case result shape mismatch")

    return {
        "summary": summarize_results(case_results),
        "case_results": case_results,
    }


def _default_cli_output_path() -> Path:
    return _REPO_ROOT / "evals" / "v5" / "artifacts" / "medical_boundary_eval_prep.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=MEASUREMENT_ID)
    parser.add_argument(
        "--matrix",
        default=str(MATRIX_PATH),
        help="Path to frozen medical boundary eval matrix",
    )
    parser.add_argument(
        "--output",
        default=str(_default_cli_output_path()),
        help="Output JSON path for offline prep artifact",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate matrix only; do not execute cases",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        spec = load_frozen_matrix(path=Path(args.matrix))
    except HarnessConfigError as error:
        print(f"CONFIG_ERROR: {error}", file=sys.stderr)
        return 2

    if args.dry_run:
        payload = {
            "summary": {
                "measurement_id": MEASUREMENT_ID,
                "total_cases": len(spec["cases"]),
                "dry_run": True,
                "proposed_acceptance_thresholds": dict(PROPOSED_ACCEPTANCE_THRESHOLDS),
                "thresholds_status": "pending_owner_approval",
            }
        }
        _write_json(Path(args.output), payload)
        print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
        return 0

    print(
        "LIVE_NOT_CONFIGURED: permitted live run requires explicit delegate backend injection",
        file=sys.stderr,
    )
    return 3


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
