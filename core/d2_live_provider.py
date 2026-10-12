"""Bounded live provider for the isolated D2 CP3 A08 harness."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass

from config import DEFAULT_LLM_MODEL
from core import d2_diagnostics as diagnostics
from core.d2_full_audit import full_audit
from contracts.d2_dialogue import D2ProviderInput
from core.one_call_prompt_contract import (
    D2_KNOWN_TASK_INSTRUCTIONS,
    D2_OPERATIONS_INSTRUCTIONS,
    one_call_contract_header,
)
from llm import LLM_REQUEST_TIMEOUT_SEC, chat_completions_create


CP3_MAX_PROVIDER_CALLS = 2


def d2_strict_response_format(request: D2ProviderInput) -> dict:
    """Historical offline probe schema, never used by either native provider.

    Kept for archived strict-format experiments; not a response route or fallback.
    """
    from contracts.d2_dialogue_result import D2DialogueResult, D2ExplanationReply
    reply_type = D2ExplanationReply if request.known_task is not None else D2DialogueResult
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "d2_explanations" if request.known_task is not None else "d2_dialogue",
            "strict": True,
            "schema": reply_type.model_json_schema(),
        },
    }


class D2LiveProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class D2LiveCallObservation:
    call_index: int
    requested_model: str
    observed_model: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    duration_ms: int


def _usage_int(usage: object, key: str) -> int | None:
    value = getattr(usage, key, None)
    if value is None and isinstance(usage, dict):
        value = usage.get(key)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _approved_md_corpus_block(request: D2ProviderInput) -> str:
    """Serialize every tenant document in a stable FullContext form.

    Document boundaries bind a model-selected ``content_ref`` to the complete
    document body.  They are not a retrieval index: no document is selected,
    omitted, or fetched later.
    """
    corpus = request.model_view.approved_md_corpus
    if not corpus.strip():
        raise D2LiveProviderError("d2_prompt_fullcontext_empty")
    return "=== APPROVED_MD_CORPUS ===\n" + corpus


def _clinic_business_policies_block(request: D2ProviderInput) -> str:
    return (
        "=== CLINIC_BUSINESS_POLICIES ===\n"
        "Use these clinic facts as grounding for ordinary content_text answers. Price and booking constraints remain in their typed fields. contact_branches lists exact branch IDs for contact requests; select one only when the user names that branch.\n"
        + request.model_view.clinic_policy_catalog_json
    )


def build_d2_d1r_messages(request: D2ProviderInput) -> tuple[dict[str, str], dict[str, str]]:
    """Reuse the sole production D1R contract with the captured D2 input."""
    directions = [item.model_dump(mode="json") for item in request.model_view.direction_prices]
    history_contract = (
        "Completed dialogue pairs contain the published assistant text, with private intake omitted. "
        "Read the ordered conversation to understand continuation. Historical prices describe past answers; "
        "new price answers use the current approved price data."
    )
    if request.known_task is not None:
        system = "\n\n".join((
            one_call_contract_header(),
            D2_KNOWN_TASK_INSTRUCTIONS,
            history_contract,
            "=== CLINIC_BUSINESS_POLICIES ===\n" + request.model_view.clinic_policy_catalog_json,
            request.model_view.commercial_fact_catalog.block_text(),
            _approved_md_corpus_block(request),
        ))
        user = "\n\n".join((
            "=== D2_SESSION_CONTEXT ===\n" + request.context.model_dump_json(),
            "=== KNOWN_TASK ===\n" + request.known_task.model_dump_json(),
            "=== D2_SELECTED_DOCUMENT_ACTION ===\n" + json.dumps(
                request.selected_document_action.model_dump(mode="json")
                if request.selected_document_action else None, ensure_ascii=False,
            ),
            "=== USER_MESSAGE ===\n" + request.user_message,
        ))
        return {"role": "system", "content": system}, {"role": "user", "content": user}
    system = "\n\n".join((
        one_call_contract_header(),
        "=== D2_OPERATIONS_INSTRUCTIONS ===\n" + D2_OPERATIONS_INSTRUCTIONS,
        history_contract,
        request.model_view.service_reference_catalog.block_text(),
        request.model_view.active_service_catalog.block_text(),
        request.model_view.commercial_fact_catalog.block_text(),
        _clinic_business_policies_block(request),
        "=== D2_DIRECTION_PRICES ===\n" + json.dumps(
            directions, ensure_ascii=False, separators=(",", ":"),
        ),
        "=== BRAND_CATALOG ===\n" + request.model_view.brand_catalog.model_dump_json(),
        _approved_md_corpus_block(request),

    ))
    user = "\n\n".join((
        "=== D2_SESSION_CONTEXT ===\n" + request.context.model_dump_json(),
        "=== D2_SELECTED_UI_REF ===\n" + json.dumps(
            request.selected_ui_ref.model_dump(mode="json")
            if request.selected_ui_ref is not None
            else None,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "=== D2_SELECTED_DOCUMENT_ACTION ===\n" + json.dumps(
            request.selected_document_action.model_dump(mode="json")
            if request.selected_document_action is not None
            else None,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "=== USER_MESSAGE ===\n" + request.user_message,
    ))
    return {"role": "system", "content": system}, {"role": "user", "content": user}


class D2Cp3LiveProvider:
    """One shared two-call allowance for the two sequential CP3 A08 turns."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_LLM_MODEL,
        transport: Callable[..., object] = chat_completions_create,
        max_calls: int = CP3_MAX_PROVIDER_CALLS,
    ) -> None:
        if max_calls != CP3_MAX_PROVIDER_CALLS:
            raise ValueError("d2_cp3_exactly_two_calls_required")
        self.model = model
        self._transport = transport
        self._max_calls = max_calls
        self.observations: list[D2LiveCallObservation] = []

    @property
    def call_count(self) -> int:
        return len(self.observations)

    def generate(self, request: D2ProviderInput) -> str:
        if self.call_count >= self._max_calls:
            raise D2LiveProviderError("d2_cp3_provider_budget_exhausted")
        call_index = self.call_count + 1
        system, user = build_d2_d1r_messages(request)
        started = time.monotonic()
        response = self._transport(
            model=self.model,
            temperature=0,
            max_completion_tokens=1024,
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=(system, user),
            provider_call_source="d2_cp3_live",
        )
        choices = getattr(response, "choices", None) or ()
        if not choices:
            raise D2LiveProviderError("d2_cp3_response_choices_missing")
        reply = _plain_text_reply(choices[0].message)
        usage = getattr(response, "usage", None)
        observed = getattr(response, "model", None)
        self.observations.append(D2LiveCallObservation(
            call_index=call_index,
            requested_model=self.model,
            observed_model=str(observed) if observed is not None else None,
            prompt_tokens=_usage_int(usage, "prompt_tokens"),
            completion_tokens=_usage_int(usage, "completion_tokens"),
            duration_ms=max(0, int((time.monotonic() - started) * 1000)),
        ))
        return reply


class D2HttpProvider:
    """The HTTP turn's single raw D1R call using the existing D2 prompt."""

    def __init__(self, *, model: str = DEFAULT_LLM_MODEL,
                 transport: Callable[..., object] = chat_completions_create,
                 admission: Callable[[], None] | None = None) -> None:
        self.model = model
        self._transport = transport
        self._admission = admission

    def generate(self, request: D2ProviderInput) -> str:
        diagnostics.stage("prompt")
        system, user = build_d2_d1r_messages(request)
        full_audit(
            "provider_messages", model=self.model, system=system, user=user,
            temperature=0, max_completion_tokens=1024,
            timeout_seconds=LLM_REQUEST_TIMEOUT_SEC,
        )
        if self._admission is not None:
            self._admission()
        response = diagnostics.call_provider(self._transport,
            model=self.model, temperature=0, max_completion_tokens=1024,
            timeout=LLM_REQUEST_TIMEOUT_SEC, messages=(system, user),
            provider_call_source="d2_http",
        )
        diagnostics.stage("provider_response")
        choices = getattr(response, "choices", None) or ()
        if not choices:
            raise D2LiveProviderError("d2_http_response_choices_missing")
        reply = _plain_text_reply(choices[0].message)
        full_audit(
            "provider_response", model=getattr(response, "model", None),
            usage=getattr(response, "usage", None), raw=reply,
            choice_count=len(choices),
        )
        return reply


def _plain_text_reply(message) -> str:
    """Only the provider's ordinary text; no tool-channel adapter or repair."""
    text = getattr(message, "content", None)
    if not isinstance(text, str) or not text.strip():
        raise D2LiveProviderError("d2_text_response_empty")
    return text
