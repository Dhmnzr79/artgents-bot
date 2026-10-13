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


def test_prompt_uses_current_schema_and_ordinary_prose_contract() -> None:
    import json
    from contracts.d2_dialogue_result import D2DialogueResult
    system, user = build_d2_d1r_messages(_request())
    prompt = system["content"]
    schema_text = prompt.split("=== D2_RESULT_SCHEMA ===\n", 1)[1]
    assert json.JSONDecoder().raw_decode(schema_text)[0] == D2DialogueResult.model_json_schema()
    assert "classic.one_tooth.impro" in prompt
    assert "Ordinary doctor, clinic-policy, brand and marketing questions" in prompt
    assert "code renders its approved answer" not in prompt
    assert "Use exact policy_id values for clinic_policy requests" not in prompt
    assert "D2_SESSION_CONTEXT" in user["content"]


def test_prompt_contains_the_complete_tenant_fullcontext_corpus_and_policies() -> None:
    request = _request()
    system, _ = build_d2_d1r_messages(request)
    prompt = system["content"]

    assert "=== APPROVED_MD_CORPUS ===" in prompt
    assert "DOCUMENT_INDEX" not in prompt
    assert "APPROVED_MD_CORPUS" in prompt and "content_ref" in prompt
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
    assert "Сколько стоит имплантация?" in user["content"]
    assert "D2_DIRECTION_PRICES" in prompt
    assert "A named direction" in prompt
    assert "is a valid price overview" in prompt
    assert "Preserve that direction as a topic target" in prompt
    assert "do not" in prompt
    assert "require service/extent merely because" in prompt
    assert "whether the data allow an overview, exact prices, a data gap or clarification" in prompt


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


def test_history_prompt_uses_published_text_not_catalog_reconstruction():
    system, _ = build_d2_d1r_messages(_request())
    assert "published assistant text" in system["content"]
    assert "Historical prices describe past answers" in system["content"]
    assert "matching catalog source" not in system["content"]
    assert "an empty assistant_text is not an unanswered turn" not in system["content"]
