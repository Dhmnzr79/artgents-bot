"""Offline acceptance tests for the FullContext speed optimization layer."""

from __future__ import annotations

from types import SimpleNamespace

from contracts.target_composer_action_context import TargetComposerActionContext
from core.target_composer_executor import TargetComposerInvocation
from core.target_composer_request import TargetComposerRequest
from core.target_response_followup_policy import TargetResponseFollowupSelection
from core.target_runtime_llm_backends import TargetRuntimeLiveComposerBackend
from core.target_versioned_answer_cache import build_versioned_answer_cache_key
from tests.test_target_composer_executor import _cached_context, _spec


def test_qwen_live_composer_backend_uses_real_sdk_stream_and_returns_strict_json(
    monkeypatch,
) -> None:
    import core.target_runtime_llm_backends as backend_module

    captured: dict[str, object] = {}
    chunks = (
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content='{"answer":"Hello '))],
            usage=None,
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content='world","source_identity":'))],
            usage=None,
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content='{"primary_content_ref":null,'))],
            usage=None,
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content='"used_content_refs":[]}}'))],
            usage=None,
        ),
    )

    def _fake_create(**kwargs):
        captured.update(kwargs)
        return iter(chunks)

    monkeypatch.setattr(backend_module, "chat_completions_create", _fake_create)
    backend = TargetRuntimeLiveComposerBackend(model="qwen3.7-plus")
    invocation = TargetComposerInvocation(
        system_policy="Policy",
        cached_full_context="Context",
        response_directives_json="{}",
        primary_evidence_json="[]",
        user_message="Question",
    )
    deltas: list[str] = []

    raw = backend.generate_stream(invocation, deltas.append)

    assert raw == (
        '{"answer":"Hello world","source_identity":'
        '{"primary_content_ref":null,"used_content_refs":[]}}'
    )
    assert deltas == ["Hello ", "world"]
    assert captured["stream"] is True
    assert captured["stream_options"] == {"include_usage": True}
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["model"] == "qwen3.7-plus"


def test_versioned_cache_key_serializes_governed_pydantic_action_context() -> None:
    action = TargetComposerActionContext(
        action_kind="ui_scope",
        topic="implantation",
        governed_ref="target:ui_scope/implantation/full_arch",
        response_stage="stage_clarify",
        extent="full_arch",
        stage=None,
    )
    request = TargetComposerRequest(
        user_message="continue",
        spec=_spec(
            response_stage="stage_clarify",
            service_id=None,
            followup_source=None,
            scope_price_topic="implantation",
            required_components=("price",),
            allow_marketing_facts=False,
            allow_cta=False,
        ),
        evidence_blocks=(),
        selected_followups=TargetResponseFollowupSelection(
            source=None,
            content=(),
            price=(),
        ),
        selected_cta_key=None,
        action_context=action,
    )
    backend = SimpleNamespace(model="qwen3.7-plus")

    key = build_versioned_answer_cache_key(
        request,
        _cached_context(),
        client_id="demo",
        composer_backend=backend,
        semantic_backend=backend,
    )

    assert len(key) == 64
