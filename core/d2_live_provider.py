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
from contracts.d2_dialogue_result import D2DialogueResult
from core.one_call_prompt_contract import (
    ONE_CALL_KNOWN_TASK_INSTRUCTIONS,
    D2_OPERATIONS_INSTRUCTIONS,
    one_call_contract_header,
)
from llm import LLM_REQUEST_TIMEOUT_SEC, chat_completions_create


CP3_MAX_PROVIDER_CALLS = 2

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
        "Use exact policy_id values for clinic_policy requests. brand_policies lists exact brand_id values: when one applies, return that brand_id in the content request; code renders its approved answer. contact_branches lists exact branch IDs for contact requests; select one only when the user names that branch.\n"
        + request.model_view.clinic_policy_catalog_json
    )


def build_d2_d1r_messages(request: D2ProviderInput) -> tuple[dict[str, str], dict[str, str]]:
    """Reuse the sole production D1R contract with the captured D2 input."""
    directions = [item.model_dump(mode="json") for item in request.model_view.direction_prices]
    if request.known_task is not None:
        system = "\n\n".join((
            one_call_contract_header(),
            ONE_CALL_KNOWN_TASK_INSTRUCTIONS,
            "=== CLINIC_BUSINESS_POLICIES ===\n" + request.model_view.clinic_policy_catalog_json,
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
    price_catalog = json.loads(request.model_view.approved_price_catalog_json)
    facts = price_catalog.pop("facts")
    price_catalog["commercial"] = request.model_view.commercial.model_dump(mode="json")
    system = "\n\n".join((
        one_call_contract_header(),
        "=== D2_OPERATIONS_INSTRUCTIONS ===\n" + D2_OPERATIONS_INSTRUCTIONS,
        "=== D2_RESULT_SCHEMA ===\n" + json.dumps(
            D2DialogueResult.model_json_schema(), ensure_ascii=False, separators=(",", ":"),
        ),
        request.model_view.service_reference_catalog.block_text(),
        request.model_view.active_service_catalog.block_text(),
        "=== COMMERCIAL_FACT_CATALOG ===\n" + json.dumps(
            {"facts": facts}, ensure_ascii=False, separators=(",", ":"),
        ),
        "=== D2_APPROVED_PRICE_CATALOG ===\n" + json.dumps(
            price_catalog, ensure_ascii=False, separators=(",", ":"),
        ),
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
            response_format={"type": "json_object"},
            provider_call_source="d2_cp3_live",
        )
        choices = getattr(response, "choices", None) or ()
        if not choices:
            raise D2LiveProviderError("d2_cp3_response_choices_missing")
        content = getattr(getattr(choices[0], "message", None), "content", None)
        if not isinstance(content, str) or not content.strip():
            raise D2LiveProviderError("d2_cp3_response_content_missing")
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
        return content.strip()


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
            response_format={"type": "json_object"},
            provider_call_source="d2_http",
        )
        diagnostics.stage("provider_response")
        choices = getattr(response, "choices", None) or ()
        if not choices:
            raise D2LiveProviderError("d2_http_response_choices_missing")
        content = getattr(getattr(choices[0], "message", None), "content", None)
        if not isinstance(content, str) or not content.strip():
            raise D2LiveProviderError("d2_http_response_content_missing")
        full_audit(
            "provider_response", model=getattr(response, "model", None),
            usage=getattr(response, "usage", None), raw=content,
            choice_count=len(choices),
        )
        return content.strip()
