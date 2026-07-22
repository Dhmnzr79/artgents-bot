"""Provider-neutral target medical boundary classifier (S42, offline/unwired)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, NoReturn, Protocol

from contracts.target_medical_boundary import (
    TargetMedicalBoundaryBackendLabel,
    TargetMedicalBoundaryDecision,
    TargetMedicalBoundaryReasonCode,
    TargetMedicalBoundaryResult,
    TargetMedicalBoundarySource,
)

TARGET_MEDICAL_BOUNDARY_SYSTEM_POLICY = """1. Classify whether the user message requires a personal medical boundary.
2. Return only one backend label: none or medical_handoff.
3. none — confident ordinary informational or commercial clinic question without personal medical evaluation.
4. medical_handoff — personal medical evaluation, treatment choice, personal eligibility, current symptoms, complications, or similar medical-boundary cases.
5. Return structured output with decision and confidence from 0.0 to 1.0 only.
6. Do not include diagnosis, free-text medical reasoning, or user medical details in the output."""


@dataclass(frozen=True, slots=True)
class TargetMedicalBoundaryInvocation:
    user_message: str


class TargetMedicalBoundaryBackend(Protocol):
    def classify(self, invocation: TargetMedicalBoundaryInvocation, /) -> object: ...


class TargetMedicalBoundaryError(ValueError):
    """Typed fail-closed executor input failure before backend call."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _fail(code: str, value: object) -> NoReturn:
    raise TargetMedicalBoundaryError(code, value)


def _valid_user_message(user_message: str) -> bool:
    return type(user_message) is str and bool(user_message.strip())


def _valid_confidence_floor(value: float) -> bool:
    return isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0


def _mapping_get(payload: object, field_name: str) -> object | None:
    if isinstance(payload, dict):
        return payload.get(field_name)
    getter = getattr(payload, "__getitem__", None)
    if getter is None:
        return None
    try:
        return getter(field_name)
    except (KeyError, TypeError, IndexError):
        return None


def _read_field(payload: object, field_name: str) -> object | None | Literal["conflict"]:
    mapping_value = _mapping_get(payload, field_name)
    attr_value = getattr(payload, field_name, None) if hasattr(payload, field_name) else None
    if mapping_value is not None and attr_value is not None and mapping_value != attr_value:
        return "conflict"
    if mapping_value is not None:
        return mapping_value
    return attr_value


def _coerce_confidence(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        confidence = float(value)
        if 0.0 <= confidence <= 1.0:
            return confidence
    return None


def _coerce_backend_label(value: object) -> TargetMedicalBoundaryBackendLabel | Literal["ambiguous"] | None:
    if type(value) is not str:
        return None
    normalized = value.strip().lower()
    if normalized in {"none", "medical_handoff"}:
        return normalized  # type: ignore[return-value]
    if normalized in {"both", "ambiguous", "unknown", "uncertain", "conflict", "conflicting"}:
        return "ambiguous"
    return None


def _uncertain_result(
    *,
    reason_code: TargetMedicalBoundaryReasonCode,
) -> TargetMedicalBoundaryResult:
    return TargetMedicalBoundaryResult(
        decision="uncertain",
        confidence=0.0,
        reason_code=reason_code,
        source="fail_closed",
    )


def _validate_backend_payload(payload: object) -> tuple[TargetMedicalBoundaryBackendLabel, float] | TargetMedicalBoundaryReasonCode:
    if payload is None:
        return "boundary_uncertain_malformed_output"

    decision_raw = _read_field(payload, "decision")
    confidence_raw = _read_field(payload, "confidence")

    if decision_raw == "conflict" or confidence_raw == "conflict":
        return "boundary_uncertain_ambiguous"

    if decision_raw is None or confidence_raw is None:
        return "boundary_uncertain_malformed_output"

    label = _coerce_backend_label(decision_raw)
    if label == "ambiguous":
        return "boundary_uncertain_ambiguous"
    if label is None:
        return "boundary_uncertain_malformed_output"

    confidence = _coerce_confidence(confidence_raw)
    if confidence is None:
        return "boundary_uncertain_malformed_output"

    return label, confidence


def _normalize_validated_backend(
    label: TargetMedicalBoundaryBackendLabel,
    confidence: float,
    *,
    min_confidence_none: float,
    min_confidence_medical_handoff: float,
) -> TargetMedicalBoundaryResult:
    if label == "none":
        if confidence < min_confidence_none:
            return _uncertain_result(reason_code="boundary_uncertain_low_confidence")
        return TargetMedicalBoundaryResult(
            decision="none",
            confidence=confidence,
            reason_code="boundary_none_confident",
            source="backend",
        )

    if confidence < min_confidence_medical_handoff:
        return _uncertain_result(reason_code="boundary_uncertain_low_confidence")
    return TargetMedicalBoundaryResult(
        decision="medical_handoff",
        confidence=confidence,
        reason_code="boundary_medical_handoff_confident",
        source="backend",
    )


def execute_target_medical_boundary_classification(
    user_message: str,
    *,
    backend: TargetMedicalBoundaryBackend,
    min_confidence_none: float = 0.0,
    min_confidence_medical_handoff: float = 0.0,
) -> TargetMedicalBoundaryResult:
    """Classify one user message through an injected backend with fail-closed semantics."""

    if not _valid_user_message(user_message):
        _fail("medical_boundary_user_message_invalid", user_message)
    if not _valid_confidence_floor(min_confidence_none):
        _fail("medical_boundary_confidence_floor_invalid", min_confidence_none)
    if not _valid_confidence_floor(min_confidence_medical_handoff):
        _fail("medical_boundary_confidence_floor_invalid", min_confidence_medical_handoff)

    invocation = TargetMedicalBoundaryInvocation(user_message=user_message.strip())

    try:
        backend_payload = backend.classify(invocation)
    except Exception:
        return _uncertain_result(reason_code="boundary_uncertain_backend_failure")

    validated = _validate_backend_payload(backend_payload)
    if type(validated) is str:
        return _uncertain_result(reason_code=validated)  # type: ignore[arg-type]

    label, confidence = validated
    return _normalize_validated_backend(
        label,
        confidence,
        min_confidence_none=min_confidence_none,
        min_confidence_medical_handoff=min_confidence_medical_handoff,
    )
