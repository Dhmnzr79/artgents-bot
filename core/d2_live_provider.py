"""Bounded live provider for the isolated D2 CP3 A08 harness."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, replace

from config import DEFAULT_LLM_MODEL
from core import d2_diagnostics as diagnostics
from core.d2_full_audit import full_audit
from contracts.d2_dialogue import D2ProviderInput, D2PriceToolReply
from contracts.d2_dialogue_result import (
    PriceOperation, D2ParsedDialogueResult, D2RejectedOperation,
    parse_d2_text_reply, split_d2_text_reply,
)
from core.one_call_envelope_protocol import _loads_strict_json_object
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
    directions = [item.model_dump(mode="json", exclude={"introduction_text", "unknown_extent_text"})
                  for item in request.model_view.direction_prices]
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
        *(("=== ENTRY_PAGE_CONTEXT (starting page only; not a stated patient need) ===\n" + request.entry_page_context.model_dump_json(),) if request.entry_page_context is not None else ()) ,
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
    """Ordinary text, or one native price round followed by grounded final prose."""

    def __init__(self, *, model: str = DEFAULT_LLM_MODEL,
                 transport: Callable[..., object] = chat_completions_create,
                 admission: Callable[[], None] | None = None) -> None:
        self.model = model
        self._transport = transport
        self._admission = admission

    def generate(self, request: D2ProviderInput) -> str | D2PriceToolReply:
        diagnostics.stage("prompt")
        system, user = build_d2_d1r_messages(request)
        full_audit(
            "provider_messages", model=self.model, system=system, user=user,
            temperature=0, max_completion_tokens=1536,
            timeout_seconds=LLM_REQUEST_TIMEOUT_SEC,
        )
        options = {} if request.known_task is not None else {
            "tools": [price_tool()], "tool_choice": "auto",
        }
        response = self._call((system, user), **options)
        diagnostics.stage("provider_response")
        choices = getattr(response, "choices", None) or ()
        if not choices:
            raise D2LiveProviderError("d2_http_response_choices_missing")
        message = choices[0].message
        calls = getattr(message, "tool_calls", None) or ()
        if calls:
            if request.known_task is not None:
                raise D2LiveProviderError("d2_known_task_tool_forbidden")
            # Prose before a tool call is planning; existing non-price actions
            # retain their owner even when requested alongside a native price.
            siblings = ()
            _, metadata = split_d2_text_reply(message.content or "")
            if metadata and metadata.get("actions"):
                parsed = parse_d2_text_reply(message.content,
                    active_service_ids=request.model_view.active_service_catalog.active_service_ids)
                if parsed.outcome == "admin":
                    return message.content  # Existing exclusive medical handoff.
                siblings = tuple(p for p in parsed.blocks if p.kind != "content")
            operations, wire_calls = [], []
            for index, call in enumerate(calls, 2):
                if call.function.name != "show_price":
                    raise D2LiveProviderError("d2_price_tool_unknown")
                args = _loads_strict_json_object(call.function.arguments)
                if {"kind", "request_id", "content_text"}.intersection(args):
                    raise D2LiveProviderError("d2_price_tool_server_fields")
                operation = PriceOperation.model_validate(dict(args, kind="price", request_id=f"r{index}"))
                if operation.clarification is not None and any(
                    choice not in request.model_view.active_service_catalog.active_service_ids
                    for choice in operation.clarification.choices
                ):
                    raise D2LiveProviderError("d2_price_tool_inactive_clarification")
                operations.append(operation)
                wire_calls.append({"id": call.id, "type": "function", "function": {
                    "name": "show_price", "arguments": call.function.arguments,
                }})
            for sibling in siblings:
                identity = f"r{len(operations)+2}"
                operations.append(replace(sibling, request_id=identity) if isinstance(sibling, D2RejectedOperation)
                                  else sibling.model_copy(update={"request_id": identity}))
            # Preserve the API transcript only inside this turn; never publish planning prose.
            assistant = {"role": "assistant", "content": message.content, "tool_calls": wire_calls}
            full_audit("price_tool_response", response=assistant, usage=getattr(response, "usage", None))
            return D2PriceToolReply(D2ParsedDialogueResult("dialogue", tuple(operations)),
                                   (system, user, assistant), tuple(wire_calls))
        reply = _plain_text_reply(message)
        full_audit(
            "provider_response", model=getattr(response, "model", None),
            usage=getattr(response, "usage", None), raw=reply,
            choice_count=len(choices),
        )
        return reply

    def _call(self, messages, **options):
        if self._admission is not None:
            self._admission()
        return diagnostics.call_provider(self._transport,
            model=self.model, temperature=0, max_completion_tokens=1536,
            timeout=LLM_REQUEST_TIMEOUT_SEC, messages=messages,
            provider_call_source="d2_http", **options)

    def complete_price(self, reply: D2PriceToolReply, outcome: dict) -> str:
        messages = (*reply.messages, *({
            "role": "tool", "tool_call_id": call["id"],
            "content": json.dumps(outcome, ensure_ascii=False, separators=(",", ":")),
        } for call in reply.tool_calls), {"role": "user", "content": PRICE_COMPLETION_INSTRUCTIONS})
        response = self._call(messages, tools=[price_tool()], tool_choice="none")
        choices = getattr(response, "choices", None) or ()
        if not choices:
            raise D2LiveProviderError("d2_http_response_choices_missing")
        if getattr(choices[0].message, "tool_calls", None):
            raise D2LiveProviderError("d2_completion_action_forbidden")
        return _plain_text_reply(choices[0].message)


def price_tool() -> dict:
    """Ordinary (non-strict) API schema derived from the sole price operation."""
    schema = PriceOperation.model_json_schema()
    definitions = schema.pop("$defs", {})
    def expand(node):
        if isinstance(node, list):
            return [expand(value) for value in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return {**expand(definitions[node["$ref"].split("/")[-1]]),
                    **expand({k: v for k, v in node.items() if k != "$ref"})}
        return {k: expand(v) for k, v in node.items() if k != "discriminator"}
    schema = expand(schema)
    for key in ("kind", "request_id"):
        schema["properties"].pop(key)
    schema["required"] = [k for k in schema.get("required", ()) if k not in {"kind", "request_id"}]
    # Domain accepts omission, but explicitly rejects clarification:null.
    clarification = schema["properties"]["clarification"]
    clarification["anyOf"] = [v for v in clarification["anyOf"] if v.get("type") != "null"]
    clarification.pop("default", None)
    return {"type": "function", "function": {"name": "show_price",
        "description": "Show catalog prices for a requested service or direction; an unknown method/extent does not prevent a direction overview.",
        "parameters": schema}}


PRICE_COMPLETION_INSTRUCTIONS = """Write the sole final prose in the user's language using the full clinic base and original question.
The tool result is frozen: do not change its service, brand, prices, inclusion or availability.
The card and its introduction/terms and any clarification prompt are shown separately by code.
Existing contact blocks and booking actions are also handled by code; do not repeat them.
Do not repeat prices, the card introduction, terms, or promise another card.
Answer ONLY the independent informational part of the original question.
For a price-only question with an available card, return exactly <NO_TEXT>.
For a price refusal, explain the supplied refusal once; its explanatory text will not be separately published.
Do not invent an alternative price. Preserve medical caveats. A clarification without an
independent informational question also needs exactly <NO_TEXT>.
Otherwise write the actual answer, not a plan. Optional <D2_META> sources are allowed after prose;
no actions, new tool calls, JSON wrapper or additional price selection."""


def _plain_text_reply(message) -> str:
    """Only the provider's ordinary text; no tool-channel adapter or repair."""
    text = getattr(message, "content", None)
    if not isinstance(text, str) or not text.strip():
        raise D2LiveProviderError("d2_text_response_empty")
    return text
