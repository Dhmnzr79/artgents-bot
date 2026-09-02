from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from contracts.response_plan_composer import ComposerDecision
from contracts.response_plan_composer_input import (
    ComposerConfirmedShownOptions,
    ComposerFullContextCorpus,
    ComposerInputContext,
    ComposerInputError,
    ComposerSessionContext,
)
from contracts.response_plan_dialogue_context import (
    ShownOptionsFreshnessPolicy,
    ShownServiceOptionsSnapshot,
)
from contracts.target_cached_full_context import TargetCachedFullContext
from core.response_plan_composer_executor import (
    ComposerExecutorError,
    ComposerOutputError,
    execute_composer_decision,
)
from tests.test_response_plan_composer_input import _authority, _demo_corpus, _input_context, _session_context
from tests.test_response_plan_contract import session


def _confirmed_shown_options(
    *,
    service_ids: tuple[str, ...] = ("all_on_4",),
    shown_at_turn: int = 1,
    max_age_turns: int = 3,
    current_turn_index: int = 2,
    client_id: str = "demo",
    sid: str = "s1",
) -> ComposerConfirmedShownOptions:
    return ComposerConfirmedShownOptions(
        snapshot=ShownServiceOptionsSnapshot(
            session_key=session(client_id=client_id, sid=sid),
            topic_id="implantation",
            service_ids=service_ids,
            shown_at_turn=shown_at_turn,
        ),
        freshness_policy=ShownOptionsFreshnessPolicy(max_age_turns=max_age_turns),
        current_turn_index=current_turn_index,
    )


def _dynamic_payload_from_backend_call(backend: RecordingBackend) -> dict[str, object]:
    invocation = backend.calls[0]
    return json.loads(invocation.user_prompt)  # type: ignore[union-attr]


class RecordingBackend:
    def __init__(self, response: object, *, should_raise: Exception | None = None) -> None:
        self.response = response
        self.should_raise = should_raise
        self.calls: list[object] = []

    def generate(self, invocation, /) -> str:
        self.calls.append(invocation)
        if self.should_raise is not None:
            raise self.should_raise
        if not isinstance(self.response, str):
            return self.response  # type: ignore[return-value]
        return self.response


def _answer_json(**overrides: object) -> str:
    payload: dict[str, object] = {
        "route": "ANSWER",
        "mode": "standard",
        "patient_text": "Ответ пациенту.",
        "service_reference_kind": "none",
        "option_reference_kind": "none",
        "topic_id": None,
        "explicit_service_id": None,
        "requested_aspect_ids": [],
        "patient_situation": {
            "extent": "unknown",
            "jaw": "unknown",
            "stage": "unknown",
            "modifiers": [],
        },
        "requested_fact_ids": [],
        "source_identity": None,
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def test_valid_answer_exactly_one_backend_call() -> None:
    backend = RecordingBackend(_answer_json())
    result = execute_composer_decision(_input_context(), backend)
    assert result.provider_call_count == 1
    assert len(backend.calls) == 1
    assert isinstance(result.adapted_decision.decision, ComposerDecision)
    assert result.adapted_decision.decision.route == "ANSWER"


def test_valid_clarify_exactly_one_backend_call() -> None:
    backend = RecordingBackend(
        _answer_json(route="CLARIFY", mode="standard", patient_text="Уточните.")
    )
    result = execute_composer_decision(_input_context(), backend)
    assert result.provider_call_count == 1
    assert result.adapted_decision.decision.route == "CLARIFY"


def test_model_selected_admin_exactly_one_call_and_normalized_terminal_fields() -> None:
    backend = RecordingBackend(
        _answer_json(
            route="ADMIN",
            mode="standard",
            patient_text=None,
            topic_id="implantation",
            service_reference_kind="explicit_current",
            explicit_service_id="all_on_4",
            requested_aspect_ids=["price"],
        )
    )
    result = execute_composer_decision(_input_context(), backend)
    assert result.provider_call_count == 1
    assert result.adapted_decision.decision.route == "ADMIN"
    assert result.adapted_decision.decision.patient_text is None
    assert result.adapted_decision.decision.requested_fact_ids == ()
    assert any(
        item.code == "terminal_fields_normalized"
        for item in result.adapted_decision.diagnostics
    )


def test_backend_exception_one_attempt_no_retry() -> None:
    backend = RecordingBackend(
        _answer_json(),
        should_raise=RuntimeError("backend failed"),
    )
    with pytest.raises(ComposerExecutorError) as exc:
        execute_composer_decision(_input_context(), backend)
    assert exc.value.code == "composer_backend_exception"
    assert len(backend.calls) == 1


def test_malformed_json_one_call_typed_error() -> None:
    backend = RecordingBackend("{not json")
    with pytest.raises(ComposerOutputError) as exc:
        execute_composer_decision(_input_context(), backend)
    assert exc.value.code == "json_invalid"
    assert len(backend.calls) == 1


def test_duplicate_json_key_one_call_typed_error() -> None:
    raw = (
        '{"route":"ANSWER","route":"ADMIN","mode":"standard","patient_text":"x",'
        '"service_reference_kind":"none","option_reference_kind":"none","topic_id":null,"explicit_service_id":null,'
        '"requested_aspect_ids":[],"patient_situation":{"extent":"unknown","jaw":"unknown",'
        '"stage":"unknown","modifiers":[]},"requested_fact_ids":[],"source_identity":null}'
    )
    backend = RecordingBackend(raw)
    with pytest.raises(ComposerOutputError) as exc:
        execute_composer_decision(_input_context(), backend)
    assert exc.value.code == "json_duplicate_key"
    assert len(backend.calls) == 1


def test_unknown_topic_service_fact_one_call_fail_open() -> None:
    backend = RecordingBackend(
        _answer_json(
            patient_text="Сохранить текст.",
            topic_id="foreign_topic",
            service_reference_kind="explicit_current",
            explicit_service_id="foreign_service",
            requested_fact_ids=["unknown_fact"],
        )
    )
    result = execute_composer_decision(_input_context(), backend)
    assert result.provider_call_count == 1
    assert result.adapted_decision.decision.patient_text == "Сохранить текст."
    codes = {item.code for item in result.adapted_decision.diagnostics}
    assert "topic_id_not_allowed" in codes
    assert "service_id_not_allowed" in codes
    assert "requested_fact_unknown" in codes


def test_source_identity_foreign_ref_one_call_filtered() -> None:
    context = _input_context()
    allowed_ref = context.full_context_corpus.cached_full_context.document_paths[0]
    backend = RecordingBackend(
        _answer_json(
            source_identity={
                "primary_content_ref": allowed_ref,
                "used_content_refs": [allowed_ref, "foreign.md"],
            }
        )
    )
    result = execute_composer_decision(context, backend)
    assert result.provider_call_count == 1
    assert result.adapted_decision.source_identity is not None
    assert result.adapted_decision.source_identity.used_content_refs == (allowed_ref,)
    assert any(item.code == "source_ref_not_allowed" for item in result.adapted_decision.diagnostics)


def test_backend_returns_non_string_typed_error() -> None:
    backend = RecordingBackend({"route": "ANSWER"})
    with pytest.raises(ComposerExecutorError) as exc:
        execute_composer_decision(_input_context(), backend)
    assert exc.value.code == "composer_backend_non_string_output"
    assert len(backend.calls) == 1


def test_bypass_zero_backend_calls() -> None:
    corpus = _demo_corpus()
    context = ComposerInputContext(
        current_user_message="вопрос",
        recent_dialogue=(),
        session_context=_session_context(),
        full_context_corpus=corpus,
        decision_authority=_authority(
            bypass=True,
            allowed_source_refs=corpus.cached_full_context.document_paths,
        ),
    )
    backend = RecordingBackend(_answer_json())
    with pytest.raises(ComposerExecutorError) as exc:
        execute_composer_decision(context, backend)
    assert exc.value.code == "composer_bypass_forbidden"
    assert backend.calls == []


def test_invalid_input_zero_backend_calls() -> None:
    backend = RecordingBackend(_answer_json())
    with pytest.raises(ComposerInputError):
        execute_composer_decision(_input_context(current_user_message=""), backend)
    assert backend.calls == []


def test_no_composer_result_returned() -> None:
    result = execute_composer_decision(_input_context(), RecordingBackend(_answer_json()))
    assert not hasattr(result, "composer_result")
    assert hasattr(result, "adapted_decision")


def test_executor_has_no_provider_runtime_imports() -> None:
    source = Path("core/response_plan_composer_executor.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    forbidden = {"llm", "openai", "session", "app", "httpx", "requests"}
    assert imported.isdisjoint(forbidden)


def test_real_demo_full_context_executor_wiring() -> None:
    backend = RecordingBackend(_answer_json(patient_text="Demo wiring."))
    context = _input_context(current_user_message="Расскажите о клинике.")
    result = execute_composer_decision(context, backend)
    assert result.provider_call_count == 1
    assert result.source_corpus_sha256 == context.full_context_corpus.cached_full_context.sha256
    assert result.model_corpus_sha256 == context.full_context_corpus.cached_full_context.prompt_sha256
    assert "Current-client validated FullContext corpus:" in backend.calls[0].system_prompt  # type: ignore[index]


def test_whitespace_only_current_message_zero_backend_calls() -> None:
    backend = RecordingBackend(_answer_json())
    with pytest.raises(ComposerInputError):
        execute_composer_decision(_input_context(current_user_message="   "), backend)
    assert backend.calls == []


def test_invalid_session_provenance_zero_backend_calls() -> None:
    backend = RecordingBackend(_answer_json())
    with pytest.raises(ComposerInputError) as exc:
        ComposerSessionContext(
            session_key=session(),
            source_client_id="demo",
            active_service_id="all_on_4",
            active_service_provenance="BROKEN",  # type: ignore[arg-type]
            active_service_freshness="current",
            active_topic_id=None,
            active_topic_provenance="none",
            active_topic_freshness="absent",
            prior_patient_situation=None,
            situation_provenance="none",
            situation_freshness="absent",
        )
    assert exc.value.code == "composer_input_session_provenance_invalid"
    assert backend.calls == []


def test_invalid_corpus_pair_zero_backend_calls() -> None:
    base = _demo_corpus().cached_full_context
    broken = TargetCachedFullContext(
        corpus_text=base.corpus_text,
        document_count=base.document_count,
        document_paths=base.document_paths,
        sha256=base.sha256,
        prompt_corpus_text="orphan prompt",
        prompt_sha256=None,
    )
    backend = RecordingBackend(_answer_json())
    with pytest.raises(ComposerInputError) as exc:
        ComposerFullContextCorpus(source_client_id="demo", cached_full_context=broken)
    assert exc.value.code == "composer_input_prompt_hash_pair_mismatch"
    assert backend.calls == []


def test_stale_snapshot_removed_catalog_id_one_backend_call_no_shown_options() -> None:
    backend = RecordingBackend(_answer_json())
    context = _input_context(
        confirmed_shown_options=_confirmed_shown_options(
            service_ids=("removed_from_catalog",),
            shown_at_turn=1,
            max_age_turns=1,
            current_turn_index=5,
        ),
    )
    result = execute_composer_decision(context, backend)
    assert result.provider_call_count == 1
    assert len(backend.calls) == 1
    assert "shown_service_options" not in _dynamic_payload_from_backend_call(backend)


def test_fresh_snapshot_unknown_catalog_id_zero_backend_calls() -> None:
    backend = RecordingBackend(_answer_json())
    context = _input_context(
        confirmed_shown_options=_confirmed_shown_options(
            service_ids=("removed_from_catalog",),
            shown_at_turn=1,
            max_age_turns=3,
            current_turn_index=2,
        ),
    )
    with pytest.raises(ComposerInputError) as exc:
        execute_composer_decision(context, backend)
    assert exc.value.code == "composer_input_shown_options_catalog_mismatch"
    assert backend.calls == []


def test_stale_snapshot_foreign_session_zero_backend_calls() -> None:
    backend = RecordingBackend(_answer_json())
    context = _input_context(
        sid="s1",
        confirmed_shown_options=_confirmed_shown_options(
            service_ids=("all_on_4",),
            shown_at_turn=1,
            max_age_turns=1,
            current_turn_index=5,
            sid="foreign_sid",
        ),
    )
    with pytest.raises(ComposerInputError) as exc:
        execute_composer_decision(context, backend)
    assert exc.value.code == "composer_input_shown_options_session_mismatch"
    assert backend.calls == []


def test_snapshot_future_turn_zero_backend_calls() -> None:
    backend = RecordingBackend(_answer_json())
    context = _input_context(
        confirmed_shown_options=_confirmed_shown_options(
            service_ids=("all_on_4",),
            shown_at_turn=5,
            max_age_turns=3,
            current_turn_index=2,
        ),
    )
    with pytest.raises(ComposerInputError) as exc:
        execute_composer_decision(context, backend)
    assert exc.value.code == "composer_input_shown_options_future_turn"
    assert backend.calls == []
