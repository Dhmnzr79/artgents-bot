from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import ValidationError

import core.target_medical_boundary as boundary_module
from contracts.target_medical_boundary import TargetMedicalBoundaryResult
from core.target_medical_boundary import (
    TargetMedicalBoundaryError,
    TargetMedicalBoundaryInvocation,
    execute_target_medical_boundary_classification,
)


@dataclass
class BackendPayload:
    decision: str
    confidence: float


class RecordingBackend:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.invocations: list[TargetMedicalBoundaryInvocation] = []

    def classify(self, invocation: TargetMedicalBoundaryInvocation, /) -> object:
        self.invocations.append(invocation)
        return self.payload


class FailingBackend:
    def classify(self, invocation: TargetMedicalBoundaryInvocation, /) -> object:
        raise RuntimeError("backend_down")


def test_confident_none_returns_none_reason_code() -> None:
    backend = RecordingBackend(BackendPayload(decision="none", confidence=0.95))
    result = execute_target_medical_boundary_classification(
        "Сколько стоит All-on-4?",
        backend=backend,
        min_confidence_none=0.5,
    )
    assert result == TargetMedicalBoundaryResult(
        decision="none",
        confidence=0.95,
        reason_code="boundary_none_confident",
        source="backend",
    )
    assert backend.invocations[0].user_message == "Сколько стоит All-on-4?"


def test_confident_medical_handoff_returns_expected_reason_code() -> None:
    result = execute_target_medical_boundary_classification(
        "Можно ли мне имплант при диабете?",
        backend=RecordingBackend(BackendPayload(decision="medical_handoff", confidence=0.91)),
        min_confidence_medical_handoff=0.5,
    )
    assert result.decision == "medical_handoff"
    assert result.reason_code == "boundary_medical_handoff_confident"
    assert result.source == "backend"


def test_low_confidence_none_becomes_uncertain_not_none() -> None:
    result = execute_target_medical_boundary_classification(
        "Сколько стоит имплант?",
        backend=RecordingBackend(BackendPayload(decision="none", confidence=0.2)),
        min_confidence_none=0.5,
    )
    assert result.decision == "uncertain"
    assert result.reason_code == "boundary_uncertain_low_confidence"
    assert result.source == "fail_closed"


def test_low_confidence_medical_handoff_becomes_uncertain() -> None:
    result = execute_target_medical_boundary_classification(
        "Можно ли мне?",
        backend=RecordingBackend(BackendPayload(decision="medical_handoff", confidence=0.1)),
        min_confidence_medical_handoff=0.5,
    )
    assert result.decision == "uncertain"
    assert result.reason_code == "boundary_uncertain_low_confidence"


def test_malformed_backend_payload_becomes_uncertain_not_none() -> None:
    result = execute_target_medical_boundary_classification(
        "Сколько стоит?",
        backend=RecordingBackend({"decision": "none"}),
    )
    assert result.decision == "uncertain"
    assert result.reason_code == "boundary_uncertain_malformed_output"


def test_backend_failure_becomes_uncertain_not_none() -> None:
    result = execute_target_medical_boundary_classification(
        "Болит зуб",
        backend=FailingBackend(),
    )
    assert result.decision == "uncertain"
    assert result.reason_code == "boundary_uncertain_backend_failure"


def test_ambiguous_backend_label_becomes_uncertain_not_none() -> None:
    result = execute_target_medical_boundary_classification(
        "Не знаю как спросить",
        backend=RecordingBackend(BackendPayload(decision="ambiguous", confidence=0.9)),
    )
    assert result.decision == "uncertain"
    assert result.reason_code == "boundary_uncertain_ambiguous"


def test_invalid_user_message_raises_before_backend() -> None:
    backend = RecordingBackend(BackendPayload(decision="none", confidence=0.9))
    with pytest.raises(TargetMedicalBoundaryError) as caught:
        execute_target_medical_boundary_classification("   ", backend=backend)
    assert caught.value.code == "medical_boundary_user_message_invalid"
    assert backend.invocations == []


def test_invalid_confidence_floor_raises_before_backend() -> None:
    backend = RecordingBackend(BackendPayload(decision="none", confidence=0.9))
    with pytest.raises(TargetMedicalBoundaryError) as caught:
        execute_target_medical_boundary_classification(
            "Сколько стоит?",
            backend=backend,
            min_confidence_none=1.5,
        )
    assert caught.value.code == "medical_boundary_confidence_floor_invalid"
    assert backend.invocations == []


def test_backend_dict_payload_is_supported() -> None:
    result = execute_target_medical_boundary_classification(
        "Сроки лечения?",
        backend=RecordingBackend({"decision": "none", "confidence": 0.88}),
    )
    assert result.decision == "none"
    assert result.reason_code == "boundary_none_confident"


def test_backend_payload_with_extra_field_becomes_malformed_not_none() -> None:
    result = execute_target_medical_boundary_classification(
        "Сколько стоит?",
        backend=RecordingBackend(
            {"decision": "none", "confidence": 0.9, "label": "extra"},
        ),
    )
    assert result.decision == "uncertain"
    assert result.reason_code == "boundary_uncertain_malformed_output"


class ExplodingPayload:
    decision = "none"
    confidence = 0.9

    def __getitem__(self, key: str) -> object:
        raise RuntimeError("payload_read_failed")


def test_payload_read_exception_becomes_uncertain_backend_failure() -> None:
    result = execute_target_medical_boundary_classification(
        "Сколько стоит?",
        backend=RecordingBackend(ExplodingPayload()),
    )
    assert result.decision == "uncertain"
    assert result.reason_code == "boundary_uncertain_backend_failure"


def test_boolean_confidence_floor_is_rejected_before_backend() -> None:
    backend = RecordingBackend(BackendPayload(decision="none", confidence=0.9))
    with pytest.raises(TargetMedicalBoundaryError) as caught:
        execute_target_medical_boundary_classification(
            "Сколько стоит?",
            backend=backend,
            min_confidence_none=True,  # type: ignore[arg-type]
        )
    assert caught.value.code == "medical_boundary_confidence_floor_invalid"
    assert backend.invocations == []


def test_inconsistent_none_reason_rejected_by_result_contract() -> None:
    with pytest.raises(ValidationError):
        TargetMedicalBoundaryResult.model_validate(
            {
                "decision": "none",
                "confidence": 0.9,
                "reason_code": "boundary_medical_handoff_confident",
                "source": "backend",
            }
        )


def test_inconsistent_none_source_rejected_by_result_contract() -> None:
    with pytest.raises(ValidationError):
        TargetMedicalBoundaryResult.model_validate(
            {
                "decision": "none",
                "confidence": 0.9,
                "reason_code": "boundary_none_confident",
                "source": "fail_closed",
            }
        )


def test_aggregate_boundary_uncertain_rejected_in_detector_result() -> None:
    with pytest.raises(ValidationError):
        TargetMedicalBoundaryResult.model_validate(
            {
                "decision": "uncertain",
                "confidence": 0.0,
                "reason_code": "boundary_uncertain",
                "source": "fail_closed",
            }
        )


def test_uncertain_requires_granular_reason_and_fail_closed_source() -> None:
    with pytest.raises(ValidationError):
        TargetMedicalBoundaryResult.model_validate(
            {
                "decision": "uncertain",
                "confidence": 0.0,
                "reason_code": "boundary_none_confident",
                "source": "fail_closed",
            }
        )


class ConflictPayload:
    decision = "medical_handoff"
    confidence = 0.9

    def __getitem__(self, key: str) -> object:
        if key == "decision":
            return "none"
        if key == "confidence":
            return self.confidence
        raise KeyError(key)


def test_conflicting_mapping_and_attribute_becomes_ambiguous_not_none() -> None:
    result = execute_target_medical_boundary_classification(
        "Сколько стоит?",
        backend=RecordingBackend(ConflictPayload()),
    )
    assert result.decision == "uncertain"
    assert result.reason_code == "boundary_uncertain_ambiguous"


def test_import_firewall_has_no_legacy_runtime_reads() -> None:
    source = Path(inspect.getfile(boundary_module)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {
        "ingress_gate",
        "turn_frame",
        "patient_scope",
        "llm",
        "flask",
        "app",
        "orchestration",
        "chunk_responder",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert module.split(".")[0] not in forbidden


def test_executor_has_no_try_except_that_maps_failure_to_none() -> None:
    source = Path(inspect.getfile(boundary_module)).read_text(encoding="utf-8")
    assert 'decision="none"' in source
    assert "boundary_uncertain_backend_failure" in source
    assert "return _uncertain_result" in source
