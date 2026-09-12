"""Eval-only live LLM delegates for S58 S57 quality eval (not product/runtime)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from core.target_composer_executor import TargetComposerInvocation
from core.target_response_verifier import TargetSemanticVerifierInvocation
from evals.v5.fullcontext_quality_eval_contract import (
    MEASUREMENT_ID,
    OWNER_APPROVED_COMPOSER_MODEL,
    OWNER_APPROVED_VERIFIER_MODEL,
    append_call_ledger_entry,
    record_provider_call_started,
)
from evals.v5.fullcontext_response_eval_backend import (
    FullContextResponseEvalComposerCapture,
    FullContextResponseEvalSemanticCapture,
    FullContextResponseEvalTransportError,
)
from evals.v5.fullcontext_response_eval_live_backend import (
    FullContextResponseEvalLiveComposerBackend,
    FullContextResponseEvalLiveSemanticBackend,
)


class FullContextQualityEvalLiveComposerBackend:
    """One-shot live composer with call ledger and budget enforcement."""

    def __init__(
        self,
        *,
        case_id: str,
        call_ledger_path: Path,
        attempt_marker_path: Path,
        model: str = OWNER_APPROVED_COMPOSER_MODEL,
        measurement_id: str = MEASUREMENT_ID,
    ) -> None:
        if model != OWNER_APPROVED_COMPOSER_MODEL:
            raise FullContextResponseEvalTransportError(
                "fullcontext_quality_eval_live_model_not_approved",
                model,
            )
        self.case_id = case_id
        self.model = model
        self.measurement_id = measurement_id
        self.call_ledger_path = call_ledger_path
        self.attempt_marker_path = attempt_marker_path
        self._delegate = FullContextResponseEvalLiveComposerBackend(model=model)
        self.call_count = 0
        self.captures: list[FullContextResponseEvalComposerCapture] = []

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        call_index = record_provider_call_started(
            self.attempt_marker_path,
            provider="composer",
        )
        append_call_ledger_entry(
            self.call_ledger_path,
            _ledger_entry(
                case_id=self.case_id,
                measurement_id=self.measurement_id,
                provider="composer",
                model=self.model,
                call_index=call_index,
                phase="call_start",
            ),
        )
        try:
            result = self._delegate.generate(invocation)
        except Exception as exc:
            append_call_ledger_entry(
                self.call_ledger_path,
                _ledger_entry(
                    case_id=self.case_id,
                    provider="composer",
                    call_index=call_index,
                    phase="call_error",
                    error=type(exc).__name__,
                ),
            )
            raise
        self.call_count = self._delegate.call_count
        self.captures = list(self._delegate.captures)
        append_call_ledger_entry(
            self.call_ledger_path,
            _ledger_entry(
                case_id=self.case_id,
                provider="composer",
                call_index=call_index,
                phase="call_complete",
            ),
        )
        return result


class FullContextQualityEvalLiveSemanticBackend:
    """One-shot live semantic verifier with call ledger and budget enforcement."""

    def __init__(
        self,
        *,
        case_id: str,
        call_ledger_path: Path,
        attempt_marker_path: Path,
        model: str = OWNER_APPROVED_VERIFIER_MODEL,
        measurement_id: str = MEASUREMENT_ID,
    ) -> None:
        if model != OWNER_APPROVED_VERIFIER_MODEL:
            raise FullContextResponseEvalTransportError(
                "fullcontext_quality_eval_live_model_not_approved",
                model,
            )
        self.case_id = case_id
        self.model = model
        self.measurement_id = measurement_id
        self.call_ledger_path = call_ledger_path
        self.attempt_marker_path = attempt_marker_path
        self._delegate = FullContextResponseEvalLiveSemanticBackend(model=model)
        self.call_count = 0
        self.captures: list[FullContextResponseEvalSemanticCapture] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        call_index = record_provider_call_started(
            self.attempt_marker_path,
            provider="semantic_verifier",
        )
        append_call_ledger_entry(
            self.call_ledger_path,
            _ledger_entry(
                case_id=self.case_id,
                measurement_id=self.measurement_id,
                provider="semantic_verifier",
                model=self.model,
                call_index=call_index,
                phase="call_start",
            ),
        )
        try:
            result = self._delegate.assess(invocation)
        except Exception as exc:
            append_call_ledger_entry(
                self.call_ledger_path,
                _ledger_entry(
                    case_id=self.case_id,
                    provider="semantic_verifier",
                    call_index=call_index,
                    phase="call_error",
                    error=type(exc).__name__,
                ),
            )
            raise
        self.call_count = self._delegate.call_count
        self.captures = list(self._delegate.captures)
        append_call_ledger_entry(
            self.call_ledger_path,
            _ledger_entry(
                case_id=self.case_id,
                provider="semantic_verifier",
                call_index=call_index,
                phase="call_complete",
            ),
        )
        return result


def _ledger_entry(
    *,
    case_id: str,
    provider: Literal["composer", "semantic_verifier"],
    phase: str,
    measurement_id: str | None = None,
    model: str | None = None,
    call_index: int | None = None,
    error: str | None = None,
) -> dict[str, object]:
    entry: dict[str, object] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "case_id": case_id,
        "provider": provider,
        "phase": phase,
    }
    if measurement_id is not None:
        entry["measurement_id"] = measurement_id
    if model is not None:
        entry["model"] = model
    if call_index is not None:
        entry["call_index"] = call_index
    if error is not None:
        entry["error"] = error
    return entry
