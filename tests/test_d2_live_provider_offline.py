from __future__ import annotations

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
