from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import core.target_turn_frame_dispatch as dispatch_module
from contracts.target_turn_frame_policy_envelope import TargetTurnFramePolicyEnvelope
from core.target_turn_frame_dispatch import (
    TargetTurnFrameDispatchError,
    dispatch_target_turn_frame_response,
)
from core.turn_frame_from_raw import build_turn_frame_from_raw


def _envelope(**overrides: object) -> TargetTurnFramePolicyEnvelope:
    payload: dict[str, object] = {
        "boundary_decision": "none",
        "tone_key": "commercial_warm",
        "allowed_topics": ("implantation", "doctors"),
        "forbidden_topics": ("diagnosis", "personal_eligibility"),
        "required_fact_ids": ("free_implant_consult",),
        "allow_marketing_facts": True,
        "allow_consultation_close": True,
        "allow_cta": True,
        "min_topic_confidence": 0.5,
        "min_service_confidence": 0.0,
        "min_intent_confidence": 0.0,
    }
    payload.update(overrides)
    return TargetTurnFramePolicyEnvelope.model_validate(payload)


def _frame(**overrides: object):
    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["price"],
        "primary_aspect": "price",
        "service_id": "all_on_4",
        "topic": "implantation",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=frozenset({"implantation", "doctors"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )


def test_payment_aspect_maps_to_price_component() -> None:
    result = dispatch_target_turn_frame_response(
        _frame(aspects=["payment"], primary_aspect=None, route="content"),
        _envelope(),
    )
    assert result.kind == "materialize"
    assert result.policy_request.requested_components == ("price",)  # type: ignore[union-attr]


def test_price_and_stages_map_to_content_and_price() -> None:
    result = dispatch_target_turn_frame_response(
        _frame(aspects=["price", "stages"], primary_aspect="price"),
        _envelope(),
    )
    assert result.kind == "materialize"
    assert result.policy_request.requested_components == ("content", "price")  # type: ignore[union-attr]
    assert result.policy_request.primary_component == "price"  # type: ignore[union-attr]


def test_doctors_topic_with_overview_requests_doctors_only() -> None:
    result = dispatch_target_turn_frame_response(
        _frame(
            route="content",
            topic="doctors",
            topic_confidence=0.95,
            aspects=["overview"],
            primary_aspect="overview",
            service_id="all_on_4",
        ),
        _envelope(),
    )
    assert result.kind == "materialize"
    assert result.policy_request.requested_components == ("doctors",)  # type: ignore[union-attr]
    assert result.policy_request.primary_component is None  # type: ignore[union-attr]


def test_clinic_wide_doctors_topic_with_empty_aspects_requests_doctors_only() -> None:
    result = dispatch_target_turn_frame_response(
        _frame(
            route="content",
            topic="doctors",
            topic_confidence=0.95,
            aspects=[],
            primary_aspect=None,
            service_id=None,
        ),
        _envelope(),
    )
    assert result.kind == "materialize"
    assert result.policy_request.requested_components == ("doctors",)  # type: ignore[union-attr]
    assert result.policy_request.service_id is None  # type: ignore[union-attr]


def test_empty_aspects_for_non_doctors_topic_remains_fail_closed() -> None:
    with pytest.raises(TargetTurnFrameDispatchError) as caught:
        dispatch_target_turn_frame_response(
            _frame(
                route="content",
                topic="implantation",
                topic_confidence=0.95,
                aspects=[],
                primary_aspect=None,
                service_id=None,
            ),
            _envelope(),
        )
    assert caught.value.code == "dispatch_field_invalid"
    assert caught.value.value == "aspects"


def test_incompatible_topic_raises_typed_error() -> None:
    with pytest.raises(TargetTurnFrameDispatchError) as caught:
        dispatch_target_turn_frame_response(
            _frame(topic="doctors", topic_confidence=0.95, aspects=["overview"]),
            _envelope(allowed_topics=("implantation",)),
        )
    assert caught.value.code == "dispatch_topic_scope_incompatible"


def test_invalid_topic_metadata_raises_typed_error() -> None:
    frame = _frame(topic="implantation", topic_confidence=0.9)
    broken = frame.model_copy(
        update={
            "field_meta": frame.field_meta.model_copy(
                update={
                    "topic": frame.field_meta.topic.model_copy(
                        update={"status": "invalid", "error": "topic_not_allowed"}
                    )
                }
            )
        }
    )
    with pytest.raises(TargetTurnFrameDispatchError) as caught:
        dispatch_target_turn_frame_response(broken, _envelope())
    assert caught.value.code == "dispatch_field_invalid"


def test_needs_clarification_returns_terminal_clarify_without_materialize() -> None:
    result = dispatch_target_turn_frame_response(
        _frame(needs_clarify=True),
        _envelope(),
    )
    assert result.kind == "terminal"
    assert result.terminal_mode == "clarify"
    assert result.spec.response_mode == "clarify"
    assert result.spec.required_components == ()


def test_needs_clarification_broad_prosthetics_price_materializes() -> None:
    from contracts.effective_scope import EffectiveScope

    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "primary_aspect": "price",
            "service_id": None,
            "topic": "prosthetics",
            "topic_confidence": 0.9,
            "needs_clarify": True,
        },
        allowed_topics=frozenset({"implantation", "prosthetics", "doctors"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )
    result = dispatch_target_turn_frame_response(
        frame,
        _envelope(allowed_topics=("implantation", "prosthetics", "doctors")),
        effective_scope=EffectiveScope(
            extent="unknown",
            topic="prosthetics",
            source="unknown",
            provenance="unknown",
        ),
    )
    assert result.kind == "materialize"
    assert result.policy_request.response_stage == "broad_family_price"
    assert result.policy_request.scope_price_topic == "prosthetics"


def test_ui_scope_click_with_medical_handoff_materializes_scoped_price() -> None:
    from contracts.effective_scope import EffectiveScope

    result = dispatch_target_turn_frame_response(
        _frame(
            needs_clarify=True,
            service_id=None,
            route="price_lookup",
            aspects=["price"],
            primary_aspect="price",
        ),
        _envelope(boundary_decision="medical_handoff"),
        effective_scope=EffectiveScope(
            extent="full_arch",
            topic="implantation",
            source="ui_action",
            provenance="target:ui_scope/implantation/full_arch",
        ),
    )
    assert result.kind == "materialize"
    assert result.policy_request.response_mode == "answer"
    assert result.policy_request.scope_price_topic == "implantation"
    assert result.policy_request.response_stage is None


def test_medical_handoff_price_without_ui_scope_stays_terminal() -> None:
    result = dispatch_target_turn_frame_response(
        _frame(
            service_id=None,
            aspects=["price"],
            primary_aspect="price",
            needs_clarify=False,
        ),
        _envelope(boundary_decision="medical_handoff"),
        effective_scope=None,
    )
    assert result.kind == "terminal"
    assert result.terminal_mode == "medical_handoff_nonmaterializable"


def test_missing_service_id_with_price_intent_materializes_scope_price() -> None:
    result = dispatch_target_turn_frame_response(
        _frame(service_id=None, aspects=["price"], primary_aspect="price"),
        _envelope(),
    )
    assert result.kind == "materialize"
    assert result.policy_request.service_id is None
    assert result.policy_request.response_stage == "broad_family_price"
    assert result.policy_request.scope_price_topic == "implantation"
    assert result.policy_request.requested_components == ("price",)


def test_known_extent_materializes_scoped_family_price() -> None:
    from contracts.effective_scope import EffectiveScope

    result = dispatch_target_turn_frame_response(
        _frame(service_id=None, aspects=["price"], primary_aspect="price"),
        _envelope(),
        effective_scope=EffectiveScope(
            extent="one_tooth",
            topic="implantation",
            source="session",
            provenance="target:ui_scope/implantation/one_tooth",
        ),
    )
    assert result.kind == "materialize"
    assert result.policy_request.response_stage is None
    assert result.policy_request.scope_price_topic == "implantation"


def test_missing_service_id_without_usable_topic_and_price_returns_defer() -> None:
    result = dispatch_target_turn_frame_response(
        _frame(
            service_id=None,
            aspects=["price"],
            primary_aspect="price",
            topic_confidence=0.2,
        ),
        _envelope(),
    )
    assert result.kind == "terminal"
    assert result.terminal_mode == "defer"
    assert result.spec.response_mode == "defer"


def test_missing_service_id_content_overview_materializes_content_only() -> None:
    result = dispatch_target_turn_frame_response(
        _frame(
            service_id=None,
            aspects=["overview"],
            primary_aspect="overview",
            route="content",
        ),
        _envelope(),
    )
    assert result.kind == "materialize"
    assert result.policy_request.requested_components == ("content",)
    assert result.policy_request.service_id is None


def test_content_and_price_without_primary_raises_ambiguous_error() -> None:
    frame = _frame(aspects=["price", "overview"], primary_aspect="price")
    ambiguous = frame.model_copy(update={"primary_aspect": None})
    with pytest.raises(TargetTurnFrameDispatchError) as caught:
        dispatch_target_turn_frame_response(ambiguous, _envelope())
    assert caught.value.code == "dispatch_followup_ambiguous"


def test_medical_boundary_without_forbidden_topics_raises_error() -> None:
    with pytest.raises(TargetTurnFrameDispatchError) as caught:
        dispatch_target_turn_frame_response(
            _frame(),
            _envelope(boundary_decision="medical_handoff", forbidden_topics=()),
        )
    assert caught.value.code == "dispatch_medical_forbidden_empty"


def test_medical_handoff_without_service_id_materializes_content_only() -> None:
    result = dispatch_target_turn_frame_response(
        _frame(service_id=None, aspects=["pain"], primary_aspect=None, route="content"),
        _envelope(boundary_decision="medical_handoff"),
    )
    assert result.kind == "materialize"
    assert result.policy_request.response_mode == "medical_handoff"  # type: ignore[union-attr]
    assert result.policy_request.service_id is None  # type: ignore[union-attr]
    assert result.policy_request.requested_components == ("content",)  # type: ignore[union-attr]
    assert result.policy_request.required_fact_ids == ()  # type: ignore[union-attr]
    assert result.policy_request.allow_marketing_facts is False  # type: ignore[union-attr]
    assert result.policy_request.allow_cta is False  # type: ignore[union-attr]


def test_public_dispatch_signature_is_single_entrypoint() -> None:
    assert list(inspect.signature(dispatch_target_turn_frame_response).parameters) == [
        "turn_frame",
        "envelope",
        "effective_scope",
    ]


def test_import_firewall_excludes_runtime_patient_scope_and_legacy_hooks() -> None:
    source = Path("core/target_turn_frame_dispatch.py").read_text(encoding="utf-8")
    import_lines = "\n".join(
        line for line in source.splitlines() if line.startswith(("import ", "from "))
    ).lower()
    forbidden = (
        "patient_scope",
        "turn_frame_shadow",
        "ingress_gate",
        "openai",
        "router",
        "session",
        "cache",
        "search",
        "llm",
    )
    assert all(token not in import_lines for token in forbidden)
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "dispatch_target_turn_frame_response"
    )
    assert not any(
        isinstance(node, ast.Try)
        for node in ast.walk(function)
    )
    assert "pytest.skip" not in source
    assert "xfail" not in source
