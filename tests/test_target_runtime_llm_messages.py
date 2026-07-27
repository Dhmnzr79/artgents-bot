"""Unit tests for target runtime LLM message builders."""

from __future__ import annotations

from core.target_composer_executor import TargetComposerInvocation
from core.target_runtime_llm_messages import build_composer_sdk_messages

_JSON_CONTRACT_SNIPPET = (
    '{"answer":"<text>","source_identity":{"primary_content_ref":"<md or null>",'
    '"used_content_refs":["<md filenames>"]}}'
)


def _invocation(**overrides: object) -> TargetComposerInvocation:
    payload: dict[str, object] = {
        "system_policy": "policy",
        "cached_full_context": "corpus",
        "response_directives_json": "{}",
        "governed_action_context_json": "null",
        "primary_evidence_json": "[]",
        "user_message": "Вопрос пациента",
    }
    payload.update(overrides)
    return TargetComposerInvocation(**payload)  # type: ignore[arg-type]


def test_build_composer_sdk_messages_does_not_raise() -> None:
    messages = build_composer_sdk_messages(_invocation())
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_rendered_user_message_contains_json_output_contract() -> None:
    content = build_composer_sdk_messages(_invocation())[1]["content"]
    assert _JSON_CONTRACT_SNIPPET in content


def test_rendered_user_message_substitutes_all_placeholders() -> None:
    content = build_composer_sdk_messages(
        _invocation(
            cached_full_context="CTX_MARKER",
            response_directives_json='{"directive":1}',
            governed_action_context_json='{"action":"ui_scope"}',
            primary_evidence_json='[{"kind":"fact"}]',
            user_message="USER_MARKER",
        )
    )[1]["content"]
    assert "CTX_MARKER" in content
    assert '"directive":1' in content
    assert '"action":"ui_scope"' in content
    assert '"kind":"fact"' in content
    assert "USER_MARKER" in content
    assert "{cached_full_context}" not in content
    assert "{user_message}" not in content


def test_input_values_with_braces_are_not_corrupted() -> None:
    content = build_composer_sdk_messages(
        _invocation(
            cached_full_context='line with {"nested": true}',
            user_message='price {"min": 1000}',
        )
    )[1]["content"]
    assert 'line with {"nested": true}' in content
    assert 'price {"min": 1000}' in content
    assert _JSON_CONTRACT_SNIPPET in content
