from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from contracts.d2_dialogue import D2ProviderInput
from contracts.d2_session_context import D2SessionContextProjection
from contracts.response_plan import SessionKey
from contracts.response_plan_session import PersistedShownCommercialIds
from core.d2_live_provider import (
    CP3_MAX_PROVIDER_CALLS,
    D2Cp3LiveProvider,
    D2LiveProviderError,
    build_d2_d1r_messages,
)
from core.d2_tenant_snapshot import build_d2_model_view, load_d2_tenant_snapshot


def _request() -> D2ProviderInput:
    snapshot = load_d2_tenant_snapshot("demo", clients_root=Path("clients"))
    return D2ProviderInput(
        user_message="Нет одного зуба, сколько стоит восстановить?",
        model_view=build_d2_model_view(snapshot),
        context=D2SessionContextProjection(
            session_key=SessionKey(client_id="demo", sid="cp3-offline"),
            source_revision=0,
            source_turn_index=0,
            freshness="unknown",
            retained_terminal_state="none",
            retained_shown_ids=PersistedShownCommercialIds(),
        ),
    )


def _response(content: str = "{}") -> object:
    return SimpleNamespace(
        model="qwen3.8-flash",
        usage=SimpleNamespace(prompt_tokens=12, completion_tokens=34),
        choices=(SimpleNamespace(message=SimpleNamespace(content=content)),),
    )


def test_cp3_prompt_reuses_v19_contract_and_typed_d2_snapshot() -> None:
    system, user = build_d2_d1r_messages(_request())
    assert "ONE_CALL_PROMPT_CONTRACT v19" in system["content"]
    assert "D2_DIRECTION_PRICES" in system["content"]
    assert "classic.one_tooth.impro" in system["content"]
    assert "=== D2_DIALOGUE_FOLLOW_UP ===" in system["content"]
    assert "topic_id to that direction id and service_id=null" in system["content"]
    assert "relation=self" in system["content"]
    assert "continuity:\"same\"" in system["content"]
    assert "sales_fast" not in system["content"]
    assert "D2_SESSION_CONTEXT" in user["content"]


def test_prompt_contains_the_complete_tenant_fullcontext_corpus_and_policies() -> None:
    request = _request()
    system, _ = build_d2_d1r_messages(request)
    prompt = system["content"]

    assert "=== APPROVED_MD_CORPUS ===" in prompt
    assert "DOCUMENT_INDEX" not in prompt
    assert "content_ref: exact filename from an APPROVED_MD_CORPUS document boundary or null." in prompt
    snapshot = load_d2_tenant_snapshot("demo", clients_root=Path("clients"))
    markdown_files = tuple((path, raw) for path, raw in snapshot.files if path.startswith("md/"))
    assert prompt.count("---BEGIN APPROVED MD:") == len(markdown_files)
    for path, raw in markdown_files:
        ref = path.removeprefix("md/")
        assert f"---BEGIN APPROVED MD:{ref}---" in prompt
        assert raw.decode("utf-8").rstrip("\n") in prompt
    assert "=== CLINIC_BUSINESS_POLICIES ===" in prompt
    assert '"policy_id":"no_oms"' in prompt
    assert '"client_id":"demo"' in prompt


def test_named_direction_price_uses_answer_overview_in_d2_prompt() -> None:
    request = replace(_request(), user_message="Сколько стоит имплантация?")
    system, user = build_d2_d1r_messages(request)
    prompt = system["content"]
    instruction = prompt.split("=== D2_DIRECTION_PRICE ===", 1)[1]

    assert "Сколько стоит имплантация?" in user["content"]
    assert "D2_DIRECTION_PRICES" in prompt
    assert "route=ANSWER" in instruction
    assert "kind=price" in instruction
    assert "topic_id=implantation" in instruction
    assert "service_id=null" in instruction
    assert "subjects=[{subject_id:s1,relation:self,age_group:unknown}]" in instruction
    assert "price request's subject_id=s1" in instruction
    assert "primary_price_request_id" in instruction
    assert "do not return CLARIFY merely because several services" in instruction
    assert "genuinely ambiguous question without a named direction" in instruction.lower()


def test_cp3_provider_has_one_shared_two_call_budget() -> None:
    calls: list[dict[str, object]] = []

    def transport(**kwargs: object) -> object:
        calls.append(dict(kwargs))
        return _response()

    provider = D2Cp3LiveProvider(transport=transport)
    assert provider.generate(_request()) == "{}"
    assert provider.generate(_request()) == "{}"
    assert len(calls) == CP3_MAX_PROVIDER_CALLS
    assert all(call["provider_call_source"] == "d2_cp3_live" for call in calls)
    with pytest.raises(D2LiveProviderError, match="budget_exhausted"):
        provider.generate(_request())


def test_cp3_provider_rejects_any_budget_other_than_two() -> None:
    with pytest.raises(ValueError, match="exactly_two"):
        D2Cp3LiveProvider(max_calls=1)
