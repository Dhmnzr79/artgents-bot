"""Eval-only live semantic backend for S53 verifier-only replay (not product/runtime)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.target_response_verifier import TargetSemanticVerifierInvocation
from evals.v5.fullcontext_response_eval_live_backend import (
    FullContextResponseEvalLiveSemanticBackend,
    fullcontext_response_eval_live_model,
)
from evals.v5.fullcontext_verifier_replay_backend import (
    FullContextVerifierReplaySemanticCapture,
    FullContextVerifierReplayTransportError,
)
from evals.v5.fullcontext_verifier_replay_contract import (
    OWNER_APPROVED_SEMANTIC_MODEL,
    append_call_ledger_entry,
    record_replay_provider_call_started,
)


class FullContextVerifierReplayLiveSemanticBackend:
    """One-shot live semantic verifier for S53 replay; Composer remains frozen."""

    def __init__(
        self,
        *,
        case_id: str,
        model: str | None = None,
        call_ledger_path: Path,
        attempt_marker_path: Path,
    ) -> None:
        resolved_model = model or fullcontext_response_eval_live_model()
        if resolved_model != OWNER_APPROVED_SEMANTIC_MODEL:
            raise FullContextVerifierReplayTransportError(
                "fullcontext_verifier_replay_live_model_not_approved",
                resolved_model,
            )
        self.case_id = case_id
        self.model = resolved_model
        self.call_ledger_path = call_ledger_path
        self.attempt_marker_path = attempt_marker_path
        self._delegate = FullContextResponseEvalLiveSemanticBackend(model=self.model)
        self.invocation_count = 0
        self.provider_call_count = 0
        self.captures: list[FullContextVerifierReplaySemanticCapture] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.invocation_count += 1
        if self.invocation_count > 1:
            raise FullContextVerifierReplayTransportError(
                "fullcontext_verifier_replay_semantic_retry_forbidden",
                self.invocation_count,
            )
        call_index = record_replay_provider_call_started(self.attempt_marker_path)
        append_call_ledger_entry(
            self.call_ledger_path,
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "measurement_id": "s53_fullcontext_verifier_replay_live",
                "case_id": self.case_id,
                "provider": "semantic_verifier",
                "model": self.model,
                "call_index": call_index,
                "phase": "call_start",
            },
        )
        try:
            assessment = self._delegate.assess(invocation)
        except Exception as exc:
            append_call_ledger_entry(
                self.call_ledger_path,
                {
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "case_id": self.case_id,
                    "provider": "semantic_verifier",
                    "phase": "call_error",
                    "error": type(exc).__name__,
                },
            )
            raise
        self.provider_call_count = self._delegate.call_count
        if self._delegate.captures:
            last = self._delegate.captures[-1]
            self.captures.append(
                FullContextVerifierReplaySemanticCapture(
                    invocation=last.invocation,
                    raw_backend_payload=last.raw_backend_payload,
                )
            )
        append_call_ledger_entry(
            self.call_ledger_path,
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "case_id": self.case_id,
                "provider": "semantic_verifier",
                "phase": "call_complete",
                "call_index": call_index,
            },
        )
        return assessment


def replay_live_model() -> str:
    return OWNER_APPROVED_SEMANTIC_MODEL
