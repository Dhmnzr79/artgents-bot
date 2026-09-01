"""Typed Composer input contracts for provider-neutral one-call invocation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from contracts.response_plan import SessionKey
from contracts.response_plan_composer import (
    ComposerDecisionAuthority,
    source_ref_invalid_reason,
)
from contracts.target_cached_full_context import TargetCachedFullContext

MAX_COMPOSER_HISTORY_TURNS = 6

ComposerDialogueRole = Literal["patient", "assistant"]
SessionValueProvenance = Literal["none", "session_active", "patient_explicit", "code_inferred"]
SessionValueFreshness = Literal["absent", "current", "stale"]

VALID_SESSION_PROVENANCES: frozenset[str] = frozenset(
    {"none", "session_active", "patient_explicit", "code_inferred"}
)
VALID_SESSION_FRESHNESS: frozenset[str] = frozenset({"absent", "current", "stale"})
MODEL_VISIBLE_SESSION_PROVENANCES: frozenset[str] = frozenset(
    {"session_active", "patient_explicit"}
)

ComposerInputErrorCode = Literal[
    "composer_input_blank_current_message",
    "composer_input_history_too_long",
    "composer_input_current_message_duplicated_in_history",
    "composer_input_history_count_mismatch",
    "composer_input_invalid_dialogue_role",
    "composer_input_blank_dialogue_text",
    "composer_input_client_mismatch",
    "composer_input_bypass_forbidden",
    "composer_input_hybrid_strategy_forbidden",
    "composer_input_source_refs_mismatch",
    "composer_input_corpus_hash_mismatch",
    "composer_input_prompt_hash_mismatch",
    "composer_input_prompt_hash_pair_mismatch",
    "composer_input_corpus_empty",
    "composer_input_active_service_mismatch",
    "composer_input_stale_session_service",
    "composer_input_authority_client_mismatch",
    "composer_input_session_provenance_invalid",
    "composer_input_session_freshness_invalid",
    "composer_input_session_state_incoherent",
]


class ComposerInputError(ValueError):
    """Typed validation error for Composer input assembly."""

    def __init__(self, code: ComposerInputErrorCode, detail: object = None) -> None:
        self.code = code
        self.detail = detail
        message = code if detail is None else f"{code}: {detail!r}"
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ComposerDialogueTurn:
    role: ComposerDialogueRole
    text: str

    def __post_init__(self) -> None:
        if self.role not in {"patient", "assistant"}:
            raise ComposerInputError("composer_input_invalid_dialogue_role", self.role)
        if not self.text or not self.text.strip():
            raise ComposerInputError("composer_input_blank_dialogue_text", self.role)


@dataclass(frozen=True, slots=True)
class ComposerSessionContext:
    session_key: SessionKey
    source_client_id: str
    active_service_id: str | None
    active_service_provenance: SessionValueProvenance
    active_service_freshness: SessionValueFreshness
    active_topic_id: str | None
    active_topic_provenance: SessionValueProvenance
    active_topic_freshness: SessionValueFreshness
    prior_patient_situation: str | None
    situation_provenance: SessionValueProvenance
    situation_freshness: SessionValueFreshness

    def __post_init__(self) -> None:
        if not self.source_client_id:
            raise ComposerInputError("composer_input_client_mismatch", "source_client_id_blank")
        if self.source_client_id != self.source_client_id.strip():
            raise ComposerInputError("composer_input_client_mismatch", "source_client_id_padded")
        if self.session_key.client_id != self.source_client_id:
            raise ComposerInputError(
                "composer_input_client_mismatch",
                (self.session_key.client_id, self.source_client_id),
            )
        _validate_session_provenance("active_service", self.active_service_provenance)
        _validate_session_provenance("active_topic", self.active_topic_provenance)
        _validate_session_provenance("situation", self.situation_provenance)
        _validate_session_freshness("active_service", self.active_service_freshness)
        _validate_session_freshness("active_topic", self.active_topic_freshness)
        _validate_session_freshness("situation", self.situation_freshness)
        _validate_session_lane_state(
            lane="active_service",
            value=self.active_service_id,
            provenance=self.active_service_provenance,
            freshness=self.active_service_freshness,
            id_field=True,
        )
        _validate_session_lane_state(
            lane="active_topic",
            value=self.active_topic_id,
            provenance=self.active_topic_provenance,
            freshness=self.active_topic_freshness,
            id_field=True,
        )
        _validate_session_lane_state(
            lane="prior_patient_situation",
            value=self.prior_patient_situation,
            provenance=self.situation_provenance,
            freshness=self.situation_freshness,
            id_field=False,
        )


@dataclass(frozen=True, slots=True)
class ComposerFullContextCorpus:
    source_client_id: str
    cached_full_context: TargetCachedFullContext

    def __post_init__(self) -> None:
        if not self.source_client_id:
            raise ComposerInputError("composer_input_client_mismatch", "corpus_client_blank")
        if self.source_client_id != self.source_client_id.strip():
            raise ComposerInputError("composer_input_client_mismatch", "corpus_client_padded")
        corpus = self.cached_full_context
        if not corpus.corpus_text.strip():
            raise ComposerInputError("composer_input_corpus_empty", "corpus_text")
        if corpus.document_count <= 0:
            raise ComposerInputError("composer_input_corpus_empty", "document_count")
        if corpus.document_count != len(corpus.document_paths):
            raise ComposerInputError(
                "composer_input_corpus_empty",
                (corpus.document_count, len(corpus.document_paths)),
            )
        expected_sha = hashlib.sha256(corpus.corpus_text.encode("utf-8")).hexdigest()
        if corpus.sha256 != expected_sha:
            raise ComposerInputError("composer_input_corpus_hash_mismatch", corpus.sha256)
        _validate_prompt_corpus_pair(corpus)
        seen_refs: set[str] = set()
        for ref in corpus.document_paths:
            invalid_reason = source_ref_invalid_reason(ref)
            if invalid_reason is not None:
                raise ComposerInputError("composer_input_source_refs_mismatch", (ref, invalid_reason))
            if ref in seen_refs:
                raise ComposerInputError("composer_input_source_refs_mismatch", (ref, "duplicate"))
            seen_refs.add(ref)


@dataclass(frozen=True, slots=True)
class ComposerInputContext:
    current_user_message: str
    recent_dialogue: tuple[ComposerDialogueTurn, ...]
    session_context: ComposerSessionContext
    full_context_corpus: ComposerFullContextCorpus
    decision_authority: ComposerDecisionAuthority


@dataclass(frozen=True, slots=True)
class ComposerModelCorpusAuthority:
    model_corpus_text: str
    source_corpus_sha256: str
    model_corpus_sha256: str


def validated_model_corpus_authority(
    corpus: TargetCachedFullContext,
) -> ComposerModelCorpusAuthority:
    """Return validated model-visible corpus text and both hash authorities."""

    source_corpus_sha256 = hashlib.sha256(corpus.corpus_text.encode("utf-8")).hexdigest()
    if corpus.sha256 != source_corpus_sha256:
        raise ComposerInputError("composer_input_corpus_hash_mismatch", corpus.sha256)

    prompt_text = corpus.prompt_corpus_text
    prompt_sha = corpus.prompt_sha256
    if prompt_text is None and prompt_sha is None:
        return ComposerModelCorpusAuthority(
            model_corpus_text=corpus.corpus_text,
            source_corpus_sha256=source_corpus_sha256,
            model_corpus_sha256=source_corpus_sha256,
        )
    if prompt_text is None or prompt_sha is None:
        raise ComposerInputError(
            "composer_input_prompt_hash_pair_mismatch",
            (prompt_text is not None, prompt_sha is not None),
        )
    if not prompt_text.strip():
        raise ComposerInputError(
            "composer_input_prompt_hash_pair_mismatch",
            "blank_prompt_corpus_text",
        )
    model_corpus_sha256 = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    if prompt_sha != model_corpus_sha256:
        raise ComposerInputError("composer_input_prompt_hash_mismatch", prompt_sha)
    return ComposerModelCorpusAuthority(
        model_corpus_text=prompt_text,
        source_corpus_sha256=source_corpus_sha256,
        model_corpus_sha256=model_corpus_sha256,
    )


def validate_composer_input_context(context: ComposerInputContext) -> None:
    """Validate full Composer input invariants before provider invocation."""

    if not context.current_user_message or not context.current_user_message.strip():
        raise ComposerInputError("composer_input_blank_current_message")
    if len(context.recent_dialogue) > MAX_COMPOSER_HISTORY_TURNS:
        raise ComposerInputError(
            "composer_input_history_too_long",
            len(context.recent_dialogue),
        )
    if context.recent_dialogue:
        last_turn = context.recent_dialogue[-1]
        if last_turn.role == "patient" and last_turn.text == context.current_user_message:
            raise ComposerInputError("composer_input_current_message_duplicated_in_history")

    authority = context.decision_authority
    if authority.bypass:
        raise ComposerInputError("composer_input_bypass_forbidden")
    if authority.context_strategy != "full_context":
        raise ComposerInputError("composer_input_hybrid_strategy_forbidden", authority.context_strategy)
    if authority.history_turn_count != len(context.recent_dialogue):
        raise ComposerInputError(
            "composer_input_history_count_mismatch",
            (authority.history_turn_count, len(context.recent_dialogue)),
        )

    session = context.session_context
    corpus = context.full_context_corpus
    client_ids = {
        session.source_client_id,
        session.session_key.client_id,
        corpus.source_client_id,
        authority.source_client_id,
    }
    if len(client_ids) != 1:
        raise ComposerInputError("composer_input_client_mismatch", tuple(sorted(client_ids)))

    if authority.source_client_id != session.source_client_id:
        raise ComposerInputError(
            "composer_input_authority_client_mismatch",
            (authority.source_client_id, session.source_client_id),
        )

    corpus_refs = tuple(corpus.cached_full_context.document_paths)
    if tuple(authority.allowed_source_refs) != corpus_refs:
        raise ComposerInputError(
            "composer_input_source_refs_mismatch",
            (authority.allowed_source_refs, corpus_refs),
        )

    if _session_service_is_stale_but_present(session):
        raise ComposerInputError("composer_input_stale_session_service", session.active_service_id)

    if authority.active_session_service_id != _model_visible_active_service_id(session):
        raise ComposerInputError(
            "composer_input_active_service_mismatch",
            (authority.active_session_service_id, session.active_service_id),
        )


def _validate_prompt_corpus_pair(corpus: TargetCachedFullContext) -> None:
    validated_model_corpus_authority(corpus)


def _validate_session_provenance(lane: str, value: str) -> None:
    if value not in VALID_SESSION_PROVENANCES:
        raise ComposerInputError("composer_input_session_provenance_invalid", (lane, value))


def _validate_session_freshness(lane: str, value: str) -> None:
    if value not in VALID_SESSION_FRESHNESS:
        raise ComposerInputError("composer_input_session_freshness_invalid", (lane, value))


def _validate_exact_nonblank_id(value: str, lane: str) -> None:
    if not value:
        raise ComposerInputError("composer_input_session_state_incoherent", (lane, "blank_id"))
    if value != value.strip():
        raise ComposerInputError("composer_input_session_state_incoherent", (lane, "padded_id"))


def _validate_session_lane_state(
    *,
    lane: str,
    value: str | None,
    provenance: str,
    freshness: str,
    id_field: bool,
) -> None:
    if value is None:
        if provenance != "none" or freshness != "absent":
            raise ComposerInputError(
                "composer_input_session_state_incoherent",
                (lane, "absent_value_requires_none_provenance_and_absent_freshness"),
            )
        return

    if id_field:
        _validate_exact_nonblank_id(value, lane)
    elif not value.strip():
        raise ComposerInputError(
            "composer_input_session_state_incoherent",
            (lane, "whitespace_only_value"),
        )

    if provenance == "none" or freshness == "absent":
        raise ComposerInputError(
            "composer_input_session_state_incoherent",
            (lane, "present_value_requires_non_none_provenance_and_non_absent_freshness"),
        )
    if freshness not in {"current", "stale"}:
        raise ComposerInputError("composer_input_session_freshness_invalid", (lane, freshness))


def _session_service_is_stale_but_present(session: ComposerSessionContext) -> bool:
    if session.active_service_id is None:
        return False
    return session.active_service_freshness == "stale"


def _model_visible_active_service_id(session: ComposerSessionContext) -> str | None:
    if session.active_service_id is None:
        return None
    if session.active_service_freshness != "current":
        return None
    if session.active_service_provenance not in MODEL_VISIBLE_SESSION_PROVENANCES:
        return None
    return session.active_service_id


def model_visible_session_context(session: ComposerSessionContext) -> dict[str, object]:
    """Serialize only current/fresh approved session values for model-visible dynamic prompt."""

    active_service_id = _model_visible_active_service_id(session)
    active_topic_id = (
        session.active_topic_id
        if session.active_topic_freshness == "current"
        and session.active_topic_provenance in MODEL_VISIBLE_SESSION_PROVENANCES
        else None
    )
    prior_situation = (
        session.prior_patient_situation
        if session.situation_freshness == "current"
        and session.situation_provenance in MODEL_VISIBLE_SESSION_PROVENANCES
        else None
    )
    return {
        "active_service_id": active_service_id,
        "active_service_freshness": session.active_service_freshness,
        "active_service_provenance": session.active_service_provenance,
        "active_topic_freshness": session.active_topic_freshness,
        "active_topic_id": active_topic_id,
        "active_topic_provenance": session.active_topic_provenance,
        "prior_patient_situation": prior_situation,
        "situation_freshness": session.situation_freshness,
        "situation_provenance": session.situation_provenance,
        "source_client_id": session.source_client_id,
    }
