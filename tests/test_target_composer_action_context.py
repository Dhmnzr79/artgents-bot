"""Unit tests for governed UI Composer action context (POST_RETRY3)."""

from __future__ import annotations

import json

import pytest

from contracts.target_composer_action_context import TargetComposerActionContext
from contracts.ui_scope_action import UiScopeAction
from contracts.ui_stage_action import UiStageAction
from core.target_composer_action_context import (
    bind_pending_ui_actions_for_composer,
    build_target_composer_action_context,
    composer_action_context_payload,
    reset_pending_ui_actions_for_composer,
    resolve_target_composer_action_context,
)
from core.target_composer_executor import (
    TargetComposerInvocation,
    TargetComposerTone,
    execute_target_composer,
)
from core.target_composer_request import TargetComposerRequest
from core.target_response_followup_policy import TargetResponseFollowupSelection
from contracts.target_response_spec import TargetResponseSpec
from tests.test_target_composer_executor import RecordingBackend, _cached_context, _spec


def test_build_scope_action_context() -> None:
    action = UiScopeAction(
        extent="full_arch",
        topic="implantation",
        ref="target:ui_scope/implantation/full_arch",
    )
    ctx = build_target_composer_action_context(
        scope_action=action,
        stage_action=None,
        response_stage="scoped_family_price",
    )
    assert ctx is not None
    assert ctx.action_kind == "ui_scope"
    assert ctx.extent == "full_arch"
    assert ctx.stage is None
    assert ctx.governed_ref == action.ref


def test_build_stage_action_context() -> None:
    action = UiStageAction(
        stage="implant_placed",
        topic="prosthetics",
        ref="target:ui_stage/prosthetics/implant_placed",
    )
    ctx = build_target_composer_action_context(
        scope_action=None,
        stage_action=action,
        response_stage="concrete_service_price",
    )
    assert ctx is not None
    assert ctx.action_kind == "ui_stage"
    assert ctx.stage == "implant_placed"


def test_resolve_from_pending_binding() -> None:
    scope = UiScopeAction(
        extent="one_tooth",
        topic="prosthetics",
        ref="target:ui_scope/prosthetics/one_tooth",
    )
    tokens = bind_pending_ui_actions_for_composer(scope_action=scope, stage_action=None)
    try:
        ctx = resolve_target_composer_action_context(response_stage="stage_clarify")
    finally:
        reset_pending_ui_actions_for_composer(tokens)
    assert ctx is not None
    assert ctx.response_stage == "stage_clarify"
    assert ctx.extent == "one_tooth"


def test_composer_invocation_includes_governed_action_context() -> None:
    action = TargetComposerActionContext(
        action_kind="ui_scope",
        topic="implantation",
        governed_ref="target:ui_scope/implantation/full_arch",
        response_stage="stage_clarify",
        extent="one_tooth",
        stage=None,
    )
    request = TargetComposerRequest(
        user_message="продолжить",
        spec=_spec(
            response_stage="stage_clarify",
            service_id=None,
            followup_source=None,
            scope_price_topic="prosthetics",
            required_components=("price",),
            allow_marketing_facts=False,
            allow_cta=False,
        ),
        evidence_blocks=(),
        selected_followups=TargetResponseFollowupSelection(source=None, content=(), price=()),
        selected_cta_key=None,
        action_context=action,
    )
    backend = RecordingBackend(output="Цены на всю челюсть.")
    execute_target_composer(
        request,
        backend,
        tone=TargetComposerTone(key="commercial_warm", instruction="warm"),
        cached_full_context=_cached_context(),
    )
    invocation = backend.invocations[0]
    assert isinstance(invocation, TargetComposerInvocation)
    assert invocation.governed_action_context_json is not None
    payload = json.loads(invocation.governed_action_context_json)
    assert payload["action_kind"] == "ui_scope"
    assert payload["extent"] == "one_tooth"
    directives = json.loads(invocation.response_directives_json)
    assert directives["governed_action"]["governed_ref"] == action.governed_ref
    assert "GOVERNED_ACTION_CONTEXT_JSON" in (
        __import__(
            "core.target_runtime_llm_messages",
            fromlist=["build_composer_sdk_messages"],
        ).build_composer_sdk_messages(invocation)[1]["content"]
    )


def test_broad_family_directives_attached() -> None:
    from core.target_response_policy import broad_family_price_directive_overlay

    directives = broad_family_price_directive_overlay("broad_family_price")
    assert directives["broad_family_price_compact"] is True
    assert directives["max_price_anchors"] == 4
    assert broad_family_price_directive_overlay("scoped_family_price") == {}


def test_invalid_price_followup_ref_rejected_by_policy() -> None:
    from core.target_response_followup_materializer import TargetPriceFollowup
    from core.target_response_followup_policy import select_target_response_followups
    from core.target_response_followup_materializer import TargetResponseFollowups

    followups = TargetResponseFollowups(
        content=(),
        price=(
            TargetPriceFollowup(
                id="stages",
                label="Оплата",
                ref="price:None/stages",
                action="navigate",
                source_offer_ids=("offer.one",),
            ),
        ),
    )
    selection = select_target_response_followups(followups, source="price")
    assert selection.source is None
    assert selection.price == ()
