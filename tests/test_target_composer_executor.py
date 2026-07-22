from __future__ import annotations

import hashlib
import inspect
import json
import re
from dataclasses import MISSING, FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

from contracts.target_cached_full_context import TargetCachedFullContext
from contracts.target_response_spec import TargetResponseSpec
from core.target_composer_executor import (
    TARGET_COMPOSER_SYSTEM_POLICY,
    TargetComposerExecutorError,
    TargetComposerInvocation,
    TargetComposerTone,
    TargetUnverifiedComposedResponse,
    execute_target_composer,
)
from core.target_composer_request import (
    TargetComposerEvidenceBlock,
    TargetComposerRequest,
)
from core.target_response_followup_materializer import TargetContentFollowup
from core.target_response_followup_policy import TargetResponseFollowupSelection


class RecordingBackend:
    def __init__(self, output: object = "  Готовый ответ.  ") -> None:
        self.output = output
        self.invocations: list[TargetComposerInvocation] = []

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.invocations.append(invocation)
        return self.output


class FailingBackend:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.calls += 1
        raise RuntimeError("provider detail must not become fallback text")


def _cached_context(
    text: str = (
        "---BEGIN DOC:service_one.md---\n"
        "---\n"
        "id: service_one\n"
        "title: Service\n"
        "---\n\n"
        "# Service\n"
        "Corpus background.\n"
        "---END DOC:service_one.md---"
    ),
) -> TargetCachedFullContext:
    return TargetCachedFullContext(
        corpus_text=text,
        document_count=1,
        document_paths=("service_one.md",),
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _spec(**updates: object) -> TargetResponseSpec:
    payload: dict[str, object] = {
        "response_mode": "answer",
        "service_id": "service_one",
        "tone_key": "commercial_warm",
        "allowed_topics": ("implantation",),
        "forbidden_topics": ("diagnosis",),
        "required_fact_ids": ("fact_one",),
        "required_components": ("content",),
        "followup_source": "content",
        "allow_marketing_facts": True,
        "allow_consultation_close": False,
        "allow_cta": True,
    }
    payload.update(updates)
    return TargetResponseSpec.model_validate(payload)


def _request(**updates: object) -> TargetComposerRequest:
    content = TargetComposerEvidenceBlock(
        kind="content",
        ref="content:service_one.md",
        topics=("implantation",),
        fact_ids=(),
        text="Описание услуги с буквой ё.",
        must_preserve_exact=False,
    )
    fact = TargetComposerEvidenceBlock(
        kind="commercial_fact",
        ref="fact:fact_one",
        topics=("implantation",),
        fact_ids=("fact_one",),
        text="Точный коммерческий факт.",
        must_preserve_exact=True,
    )
    followup = TargetContentFollowup(
        id="details",
        label="Подробнее",
        ref="service_one.md#details",
        source_content_ref="service_one.md",
    )
    values: dict[str, object] = {
        "user_message": "Расскажите об услуге",
        "spec": _spec(),
        "evidence_blocks": (content, fact),
        "selected_followups": TargetResponseFollowupSelection(
            source="content",
            content=(followup,),
            price=(),
        ),
        "selected_cta_key": "plan",
    }
    values.update(updates)
    return TargetComposerRequest(**values)  # type: ignore[arg-type]


def _tone() -> TargetComposerTone:
    return TargetComposerTone(
        key="commercial_warm",
        instruction="Отвечай доброжелательно и без давления.",
    )


def _error(callable_) -> TargetComposerExecutorError:
    with pytest.raises(TargetComposerExecutorError) as caught:
        callable_()
    return caught.value


def test_contract_shapes_signature_policy_and_exact_error_codes() -> None:
    assert [(field.name, field.default) for field in fields(TargetComposerTone)] == [
        ("key", MISSING),
        ("instruction", MISSING),
    ]
    assert [field.name for field in fields(TargetComposerInvocation)] == [
        "system_policy",
        "cached_full_context",
        "response_directives_json",
        "primary_evidence_json",
        "user_message",
    ]
    assert [field.name for field in fields(TargetUnverifiedComposedResponse)] == [
        "text",
        "spec",
        "selected_followups",
        "selected_cta_key",
        "verification_status",
    ]
    assert list(inspect.signature(execute_target_composer).parameters) == [
        "request",
        "backend",
        "tone",
        "cached_full_context",
    ]
    source = Path("core/target_composer_executor.py").read_text(encoding="utf-8")
    assert set(re.findall(r'"(composer_executor_[a-z_]+)"', source)) == {
        "composer_executor_request_invalid",
        "composer_executor_tone_invalid",
        "composer_executor_full_context_invalid",
        "composer_executor_backend_invalid",
        "composer_executor_backend_failed",
        "composer_executor_output_invalid",
    }
    policy_positions = [
        TARGET_COMPOSER_SYSTEM_POLICY.index(f"{number}.") for number in range(1, 10)
    ]
    assert policy_positions == sorted(policy_positions)
    assert "CACHED_FULL_CONTEXT" in TARGET_COMPOSER_SYSTEM_POLICY
    assert "dry refusal" in TARGET_COMPOSER_SYSTEM_POLICY
    assert "allow_cta" in TARGET_COMPOSER_SYSTEM_POLICY


def test_executor_serializes_one_exact_immutable_invocation_and_keeps_sidecars_out() -> None:
    request = _request()
    backend = RecordingBackend()

    result = execute_target_composer(
        request, backend, tone=_tone(), cached_full_context=_cached_context()
    )

    assert result.text == "Готовый ответ."
    assert result.spec is request.spec
    assert result.selected_followups is request.selected_followups
    assert result.selected_cta_key is request.selected_cta_key
    assert result.verification_status == "unverified"
    assert len(backend.invocations) == 1
    invocation = backend.invocations[0]
    assert invocation.system_policy is TARGET_COMPOSER_SYSTEM_POLICY
    assert invocation.cached_full_context == _cached_context().corpus_text
    assert invocation.user_message is request.user_message
    assert invocation.response_directives_json == (
        '{"response_mode":"answer","tone_key":"commercial_warm",'
        '"tone_instruction":"Отвечай доброжелательно и без давления.",'
        '"allowed_topics":["implantation"],"forbidden_topics":["diagnosis"],'
        '"required_fact_ids":["fact_one"],'
        '"allow_marketing_facts":true,'
        '"allow_consultation_close":false,'
        '"allow_cta":true}'
    )
    evidence = json.loads(invocation.primary_evidence_json)
    assert list(evidence[0]) == [
        "kind",
        "ref",
        "topics",
        "fact_ids",
        "text",
        "must_preserve_exact",
    ]
    assert "ё" in invocation.primary_evidence_json
    assert "Подробнее" not in invocation.cached_full_context
    assert '"plan"' not in invocation.cached_full_context
    combined = (
        invocation.response_directives_json
        + invocation.primary_evidence_json
        + invocation.cached_full_context
    )
    assert "Подробнее" not in combined
    assert '"plan"' not in combined
    assert "selected_followups" not in combined
    assert "selected_cta_key" not in combined
    assert "unverified" not in combined
    with pytest.raises(FrozenInstanceError):
        invocation.user_message = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("candidate", "marker"),
    [
        (object(), "request_type"),
        (_request(spec=object()), "request_spec"),
        (
            _request(spec=_spec().model_copy(update={"response_mode": "clarify"})),
            "request_mode",
        ),
        (_request(user_message=" bad "), "request_message"),
        (_request(evidence_blocks=[]), "request_evidence"),
        (
            _request(
                evidence_blocks=(
                    replace(_request().evidence_blocks[0], topics=("diagnosis",)),
                    _request().evidence_blocks[1],
                )
            ),
            "request_topic_scope",
        ),
        (
            _request(
                spec=_spec().model_copy(update={"required_fact_ids": ("missing",)})
            ),
            "request_required_facts",
        ),
        (
            _request(
                selected_followups=TargetResponseFollowupSelection(
                    source=None,
                    content=_request().selected_followups.content,
                    price=(),
                )
            ),
            "request_followups",
        ),
        (
            _request(spec=_spec().model_copy(update={"allow_cta": False})),
            "request_cta",
        ),
    ],
)
def test_request_validation_fails_closed_with_stable_markers(
    candidate: object,
    marker: str,
) -> None:
    error = _error(
        lambda: execute_target_composer(
            candidate, RecordingBackend(), tone=_tone(), cached_full_context=_cached_context()
        )
    )
    assert (error.code, error.value, str(error)) == (
        "composer_executor_request_invalid",
        marker,
        f"composer_executor_request_invalid: {marker!r}",
    )


def test_nested_block_invariants_are_checked_before_backend() -> None:
    valid = _request()
    invalid_blocks = (
        replace(valid.evidence_blocks[0], must_preserve_exact=True),
        valid.evidence_blocks[1],
    )
    backend = RecordingBackend()
    error = _error(
        lambda: execute_target_composer(
            replace(valid, evidence_blocks=invalid_blocks),
            backend,
            tone=_tone(),
            cached_full_context=_cached_context(),
        )
    )
    assert (error.code, error.value, backend.invocations) == (
        "composer_executor_request_invalid",
        "request_evidence",
        [],
    )


def test_hostile_spec_field_fails_with_typed_request_error_before_backend() -> None:
    spec = _spec().model_copy(update={"followup_source": []})
    backend = RecordingBackend()
    error = _error(
        lambda: execute_target_composer(
            _request(spec=spec),
            backend,
            tone=_tone(),
            cached_full_context=_cached_context(),
        )
    )
    assert (error.code, error.value, backend.invocations) == (
        "composer_executor_request_invalid",
        "request_spec",
        [],
    )


def test_duplicate_ref_precedes_topic_scope_error() -> None:
    valid = _request()
    duplicate_with_forbidden_topic = replace(
        valid.evidence_blocks[0],
        topics=("diagnosis",),
    )
    backend = RecordingBackend()
    error = _error(
        lambda: execute_target_composer(
            replace(
                valid,
                evidence_blocks=(valid.evidence_blocks[0], duplicate_with_forbidden_topic),
            ),
            backend,
            tone=_tone(),
            cached_full_context=_cached_context(),
        )
    )
    assert (error.code, error.value, backend.invocations) == (
        "composer_executor_request_invalid",
        "request_evidence",
        [],
    )


@pytest.mark.parametrize(
    ("tone", "marker"),
    [
        (object(), "tone_type"),
        (TargetComposerTone(" bad ", "instruction"), "tone_key"),
        (TargetComposerTone("commercial_warm", ""), "tone_instruction"),
        (TargetComposerTone("neutral", "instruction"), "tone_key_mismatch"),
    ],
)
def test_tone_validation_has_stable_markers(tone: object, marker: str) -> None:
    error = _error(
        lambda: execute_target_composer(
            _request(),
            RecordingBackend(),
            tone=tone,  # type: ignore[arg-type]
            cached_full_context=_cached_context(),
        )
    )
    assert (error.code, error.value) == ("composer_executor_tone_invalid", marker)


def test_backend_validation_failure_and_output_failure_have_no_retry_or_fallback() -> None:
    invalid = _error(
        lambda: execute_target_composer(
            _request(),
            object(),
            tone=_tone(),  # type: ignore[arg-type]
            cached_full_context=_cached_context(),
        )
    )
    assert (invalid.code, invalid.value) == (
        "composer_executor_backend_invalid",
        "backend_generate",
    )

    failing = FailingBackend()
    failed = _error(
        lambda: execute_target_composer(
            _request(), failing, tone=_tone(), cached_full_context=_cached_context()
        )
    )
    assert (failed.code, failed.value, failing.calls) == (
        "composer_executor_backend_failed",
        "RuntimeError",
        1,
    )
    assert isinstance(failed.__cause__, RuntimeError)

    for output in (None, 1, " \n "):
        backend = RecordingBackend(output)
        error = _error(
            lambda: execute_target_composer(
                _request(), backend, tone=_tone(), cached_full_context=_cached_context()
            )
        )
        assert error.code == "composer_executor_output_invalid"
        assert error.value is output
        assert len(backend.invocations) == 1


def test_medical_handoff_reaches_policy_but_remains_unverified() -> None:
    spec = _spec(
        response_mode="medical_handoff",
        required_fact_ids=(),
        required_components=(),
        followup_source=None,
        allow_marketing_facts=False,
        allow_cta=False,
    )
    request = _request(
        spec=spec,
        evidence_blocks=(_request().evidence_blocks[0],),
        selected_followups=TargetResponseFollowupSelection(source=None, content=(), price=()),
        selected_cta_key=None,
    )
    backend = RecordingBackend("Общая информация и рекомендация обратиться к врачу.")
    result = execute_target_composer(
        request,
        backend,
        tone=_tone(),
        cached_full_context=_cached_context(),
    )
    assert json.loads(backend.invocations[0].response_directives_json)[
        "response_mode"
    ] == "medical_handoff"
    assert "dry refusal" in backend.invocations[0].system_policy
    assert result.verification_status == "unverified"


def test_medical_handoff_directives_include_cta_policy_flags() -> None:
    spec = _spec(
        response_mode="medical_handoff",
        required_fact_ids=(),
        required_components=(),
        followup_source=None,
        allow_marketing_facts=False,
        allow_consultation_close=True,
        allow_cta=False,
    )
    request = _request(
        spec=spec,
        evidence_blocks=(_request().evidence_blocks[0],),
        selected_followups=TargetResponseFollowupSelection(source=None, content=(), price=()),
        selected_cta_key=None,
    )
    backend = RecordingBackend("Ответ.")
    execute_target_composer(
        request,
        backend,
        tone=_tone(),
        cached_full_context=_cached_context(),
    )
    directives = json.loads(backend.invocations[0].response_directives_json)
    assert directives["allow_cta"] is False
    assert directives["allow_consultation_close"] is True
    assert directives["allow_marketing_facts"] is False


def test_full_context_validation_fails_closed_before_backend() -> None:
    broken = TargetCachedFullContext(
        corpus_text="---BEGIN DOC:a.md---\nbody\n---END DOC:a.md---",
        document_count=1,
        document_paths=("a.md",),
        sha256="deadbeef",
    )
    backend = RecordingBackend()
    error = _error(
        lambda: execute_target_composer(
            _request(),
            backend,
            tone=_tone(),
            cached_full_context=broken,
        )
    )
    assert (error.code, error.value, backend.invocations) == (
        "composer_executor_full_context_invalid",
        "full_context_sha256",
        [],
    )


def test_import_firewall_has_no_provider_legacy_runtime_or_live_hooks() -> None:
    source = Path("core/target_composer_executor.py").read_text(encoding="utf-8")
    forbidden = (
        "openai",
        "anthropic",
        "generate_answer_from_packet_fullctx",
        "llm.py",
        "retriev",
        "router",
        "session",
        "requests",
        "httpx",
    )
    import_lines = "\n".join(
        line for line in source.splitlines() if line.startswith(("import ", "from "))
    ).lower()
    assert all(token not in import_lines for token in forbidden)
    assert " import cache" not in import_lines
    assert " from cache" not in import_lines
    assert "pytest.skip" not in source
    assert "xfail" not in source
