"""Pure deterministic Composer prompt builder for provider-neutral invocation."""

from __future__ import annotations

import json
from dataclasses import dataclass

from contracts.response_plan import SessionKey
from contracts.response_plan_composer_input import (
    ComposerInputContext,
    validated_model_corpus_authority,
    model_visible_session_context,
    validate_composer_input_context,
)
from core.response_plan_composer_contract import (
    build_composer_policy_sidecar,
    build_static_composer_instructions,
    serialize_composer_policy_sidecar,
)


@dataclass(frozen=True, slots=True)
class ComposerDecisionInvocation:
    system_prompt: str
    user_prompt: str
    source_client_id: str
    session_key: SessionKey
    source_corpus_sha256: str
    model_corpus_sha256: str
    history_turn_count: int


def build_composer_decision_invocation(
    input_context: ComposerInputContext,
) -> ComposerDecisionInvocation:
    """Build stable system prompt and dynamic user prompt from validated input."""

    validate_composer_input_context(input_context)

    corpus = input_context.full_context_corpus.cached_full_context
    corpus_authority = validated_model_corpus_authority(corpus)
    static_instructions = build_static_composer_instructions()
    document_index = _document_index_block(corpus.document_paths)
    system_prompt = "\n\n".join(
        [
            static_instructions,
            "Current-client validated FullContext corpus:",
            corpus_authority.model_corpus_text,
            "Document index (corpus-relative POSIX paths):",
            document_index,
        ]
    )

    sidecar = build_composer_policy_sidecar(input_context.decision_authority)
    policy_payload = json.loads(serialize_composer_policy_sidecar(sidecar))
    dynamic_payload = {
        "current_user_message": input_context.current_user_message,
        "policy_control": policy_payload,
        "recent_dialogue": [
            {"role": turn.role, "text": turn.text}
            for turn in input_context.recent_dialogue
        ],
        "session_context": model_visible_session_context(input_context.session_context),
    }
    user_prompt = json.dumps(dynamic_payload, ensure_ascii=False, sort_keys=True)

    return ComposerDecisionInvocation(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        source_client_id=input_context.decision_authority.source_client_id,
        session_key=input_context.session_context.session_key,
        source_corpus_sha256=corpus_authority.source_corpus_sha256,
        model_corpus_sha256=corpus_authority.model_corpus_sha256,
        history_turn_count=len(input_context.recent_dialogue),
    )


def _document_index_block(document_paths: tuple[str, ...]) -> str:
    return "\n".join(f"- {path}" for path in document_paths)
