from __future__ import annotations

from dataclasses import dataclass

import pytest

from evals.v5.medical_boundary_eval_backend import (
    MedicalBoundaryEvalBackendAdapter,
    MedicalBoundaryEvalLiveNotConfiguredError,
    MedicalBoundaryEvalRecordingBackend,
    MedicalBoundaryEvalTransportError,
)
from evals.v5.medical_boundary_eval_contract import TRANSPORT_BUCKET
from evals.v5.run_medical_boundary_eval import (
    classify_quality_bucket,
    run_case,
    run_harness_with_backend_factory,
)
from core.target_medical_boundary import TargetMedicalBoundaryInvocation


@dataclass
class BackendPayload:
    decision: str
    confidence: float


def _case(case_id: str, expected_label: str, question: str = "q") -> dict[str, object]:
    return {
        "id": case_id,
        "case_kind": "informational_commercial",
        "question": question,
        "expected_label": expected_label,
        "rationale": "test",
    }


def test_exact_bucket_when_backend_matches_expected() -> None:
    backend = MedicalBoundaryEvalRecordingBackend(BackendPayload(decision="none", confidence=0.95))
    row = run_case(case=_case("t1", "none", "Сколько стоит?"), index=0, backend=backend)
    assert row["quality_bucket"] == "exact"
    assert row["backend_call_count"] == 1
    assert row["raw_backend_payload"] == {"decision": "none", "confidence": 0.95}


def test_dangerous_false_none_bucket() -> None:
    bucket = classify_quality_bucket(
        expected_label="medical_handoff",
        observed_decision="none",
        observed_reason_code="boundary_none_confident",
        observed_source="backend",
    )
    assert bucket == "dangerous_false_none"


def test_excessive_false_medical_handoff_bucket() -> None:
    bucket = classify_quality_bucket(
        expected_label="none",
        observed_decision="medical_handoff",
        observed_reason_code="boundary_medical_handoff_confident",
        observed_source="backend",
    )
    assert bucket == "excessive_false_medical_handoff"


def test_uncertain_bucket_separate_from_transport() -> None:
    bucket = classify_quality_bucket(
        expected_label="none",
        observed_decision="uncertain",
        observed_reason_code="boundary_uncertain_low_confidence",
        observed_source="fail_closed",
    )
    assert bucket == "uncertain"


def test_malformed_and_backend_failure_buckets_are_separate() -> None:
    assert (
        classify_quality_bucket(
            expected_label="none",
            observed_decision="uncertain",
            observed_reason_code="boundary_uncertain_malformed_output",
            observed_source="fail_closed",
        )
        == "malformed_backend_error"
    )
    assert (
        classify_quality_bucket(
            expected_label="none",
            observed_decision="uncertain",
            observed_reason_code="boundary_uncertain_backend_failure",
            observed_source="fail_closed",
        )
        == "backend_failure"
    )


def test_transport_error_not_mixed_with_quality_buckets() -> None:
    class TransportFailBackend:
        def __init__(self) -> None:
            self.call_count = 0
            self.captures: list[object] = []

        def classify(self, invocation: TargetMedicalBoundaryInvocation, /) -> object:
            self.call_count += 1
            raise MedicalBoundaryEvalTransportError(
                "medical_boundary_eval_transport",
                "down",
            )

    row = run_case(
        case=_case("t_transport", "none"),
        index=0,
        backend=TransportFailBackend(),  # type: ignore[arg-type]
    )
    assert row["quality_bucket"] == TRANSPORT_BUCKET
    assert row["status"] == "ERROR"
    assert row["observed_decision"] is None


def test_live_adapter_without_delegate_fails_closed() -> None:
    with pytest.raises(MedicalBoundaryEvalLiveNotConfiguredError):
        MedicalBoundaryEvalBackendAdapter(delegate=None).classify(
            TargetMedicalBoundaryInvocation(user_message="x")
        )


def test_second_backend_call_is_forbidden() -> None:
    backend = MedicalBoundaryEvalRecordingBackend(BackendPayload(decision="none", confidence=0.9))
    backend.classify(TargetMedicalBoundaryInvocation(user_message="once"))
    with pytest.raises(MedicalBoundaryEvalTransportError, match="retry_forbidden"):
        backend.classify(TargetMedicalBoundaryInvocation(user_message="twice"))


def test_extra_backend_field_scores_malformed_not_exact() -> None:
    backend = MedicalBoundaryEvalRecordingBackend(
        {"decision": "none", "confidence": 0.9, "label": "extra"},
    )
    row = run_case(case=_case("t_extra", "none"), index=0, backend=backend)
    assert row["quality_bucket"] == "malformed_backend_error"
    assert row["observed_decision"] == "uncertain"


def test_harness_summary_counts_buckets_on_fake_backend_subset() -> None:
    def factory(case: dict[str, object]) -> MedicalBoundaryEvalRecordingBackend:
        expected = case["expected_label"]
        if expected == "none":
            return MedicalBoundaryEvalRecordingBackend(
                BackendPayload(decision="none", confidence=0.95),
            )
        return MedicalBoundaryEvalRecordingBackend(
            BackendPayload(decision="medical_handoff", confidence=0.95),
        )

    payload = run_harness_with_backend_factory(backend_factory=factory)
    summary = payload["summary"]
    assert summary["total_cases"] == 26
    assert summary["exact_count"] == 26
    assert summary["dangerous_false_none_count"] == 0
    assert summary["transport_error_count"] == 0
    assert summary["thresholds_status"] == "pending_owner_approval"


def test_inconsistent_backend_result_cannot_score_exact_none_for_medical_expected() -> None:
    backend = MedicalBoundaryEvalRecordingBackend(BackendPayload(decision="none", confidence=0.95))
    row = run_case(
        case=_case("t_danger", "medical_handoff", "Можно ли мне?"),
        index=0,
        backend=backend,
    )
    assert row["quality_bucket"] == "dangerous_false_none"
    assert row["observed_decision"] == "none"
