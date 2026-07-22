"""Eval-only live LLM delegate for S43 medical boundary eval (not product/runtime)."""

from __future__ import annotations

import json
import os

from config import CHAT_MODEL, QWEN_FLASH_MODEL
from core.target_medical_boundary import (
    TARGET_MEDICAL_BOUNDARY_SYSTEM_POLICY,
    TargetMedicalBoundaryInvocation,
)
from evals.v5.medical_boundary_eval_backend import MedicalBoundaryEvalTransportError
from llm import LLM_REQUEST_TIMEOUT_SEC, chat_completions_create, log_llm_error, log_llm_usage
from logging_setup import get_logger

logger = get_logger("medical_boundary_eval")

_LIVE_USER_TEMPLATE = (
    "Classify this patient message for medical boundary.\n\n"
    "Return JSON with exactly two fields:\n"
    '- "decision": "none" or "medical_handoff"\n'
    '- "confidence": number from 0.0 to 1.0\n\n'
    "Patient message:\n{message}"
)


def medical_boundary_eval_live_model() -> str:
    return (os.getenv("MEDICAL_BOUNDARY_EVAL_LLM_MODEL") or "").strip() or QWEN_FLASH_MODEL or CHAT_MODEL


class MedicalBoundaryEvalLiveBackend:
    """One-shot live classifier backend for eval harness injection only."""

    def __init__(self) -> None:
        self.call_count = 0

    def classify(self, invocation: TargetMedicalBoundaryInvocation, /) -> object:
        self.call_count += 1
        if self.call_count > 1:
            raise MedicalBoundaryEvalTransportError(
                "medical_boundary_eval_retry_forbidden",
                self.call_count,
            )
        message = invocation.user_message.strip()
        model = medical_boundary_eval_live_model()
        try:
            response = chat_completions_create(
                model=model,
                temperature=0,
                max_completion_tokens=64,
                response_format={"type": "json_object"},
                timeout=LLM_REQUEST_TIMEOUT_SEC,
                messages=[
                    {"role": "system", "content": TARGET_MEDICAL_BOUNDARY_SYSTEM_POLICY},
                    {
                        "role": "user",
                        "content": _LIVE_USER_TEMPLATE.format(message=message[:900]),
                    },
                ],
            )
            log_llm_usage(
                logger,
                response,
                call_type="s43_medical_boundary_live_eval",
                model=model,
            )
            raw_text = (response.choices[0].message.content or "").strip()
            payload = json.loads(raw_text)
            if not isinstance(payload, dict):
                raise ValueError("medical_boundary_live_not_object")
            if set(payload.keys()) != {"decision", "confidence"}:
                raise ValueError("medical_boundary_live_extra_fields")
            return payload
        except MedicalBoundaryEvalTransportError:
            raise
        except Exception as exc:
            log_llm_error(
                logger,
                call_type="s43_medical_boundary_live_eval",
                err=str(exc),
                model=model,
            )
            raise MedicalBoundaryEvalTransportError(
                "medical_boundary_eval_live_backend_failure",
                exc,
            ) from exc
