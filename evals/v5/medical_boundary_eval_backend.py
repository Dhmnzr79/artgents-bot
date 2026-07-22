"""Eval-only backend adapter for S43 medical boundary live eval (no live LLM in scope)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.target_medical_boundary import TargetMedicalBoundaryBackend, TargetMedicalBoundaryInvocation


class MedicalBoundaryEvalTransportError(RuntimeError):
    """Eval transport failure before structured payload reaches S42 executor."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


class MedicalBoundaryEvalLiveNotConfiguredError(MedicalBoundaryEvalTransportError):
    """Live delegate was not injected; eval refuses to call LLM implicitly."""


@dataclass(frozen=True, slots=True)
class MedicalBoundaryEvalBackendCapture:
    invocation: TargetMedicalBoundaryInvocation
    raw_backend_payload: object


class MedicalBoundaryEvalRecordingBackend:
    """Fake/test backend that records one immutable raw payload per classify call."""

    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.call_count = 0
        self.captures: list[MedicalBoundaryEvalBackendCapture] = []

    def classify(self, invocation: TargetMedicalBoundaryInvocation, /) -> object:
        self.call_count += 1
        if self.call_count > 1:
            raise MedicalBoundaryEvalTransportError(
                "medical_boundary_eval_retry_forbidden",
                self.call_count,
            )
        self.captures.append(
            MedicalBoundaryEvalBackendCapture(
                invocation=invocation,
                raw_backend_payload=self.payload,
            )
        )
        return self.payload


class MedicalBoundaryEvalBackendAdapter:
    """Requires an explicit delegate; never calls LLM by itself."""

    def __init__(self, delegate: TargetMedicalBoundaryBackend | None = None) -> None:
        self._delegate = delegate
        self.call_count = 0

    def classify(self, invocation: TargetMedicalBoundaryInvocation, /) -> object:
        if self._delegate is None:
            raise MedicalBoundaryEvalLiveNotConfiguredError(
                "medical_boundary_eval_live_not_configured",
                None,
            )
        self.call_count += 1
        if self.call_count > 1:
            raise MedicalBoundaryEvalTransportError(
                "medical_boundary_eval_retry_forbidden",
                self.call_count,
            )
        return self._delegate.classify(invocation)
