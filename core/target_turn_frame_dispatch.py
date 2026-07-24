"""Deterministic TurnFrame response dispatch (S41, offline/unwired)."""

from __future__ import annotations

from typing import Literal, NoReturn

from contracts.answer_plan import AspectKind
from contracts.effective_scope import EffectiveScope
from contracts.target_response_policy import TargetResponsePolicyRequest
from contracts.target_response_spec import TargetResponseComponent, TargetResponseMode
from contracts.turn_frame import FieldMeta, TurnFrame
from contracts.target_turn_frame_dispatch import (
    TargetTurnFrameMaterializeDispatch,
    TargetTurnFrameTerminalDispatch,
    TargetTurnFrameTerminalMode,
)
from contracts.target_turn_frame_policy_envelope import TargetTurnFramePolicyEnvelope
from core.target_response_policy import build_target_response_spec

_ASPECT_TO_COMPONENT: dict[AspectKind, TargetResponseComponent] = {
    "price": "price",
    "payment": "price",
    "included": "price",
    "stages": "content",
    "warranty": "content",
    "comparison": "content",
    "duration": "content",
    "pain": "content",
    "overview": "content",
}
_COMPONENT_ORDER: tuple[TargetResponseComponent, ...] = ("content", "price", "doctors")
_PRICE_INTENTS = frozenset({"price_lookup", "price_concern"})


class TargetTurnFrameDispatchError(ValueError):
    """Typed fail-closed TurnFrame dispatch failure."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _fail(code: str, value: object) -> NoReturn:
    raise TargetTurnFrameDispatchError(code, value)


def _reject_invalid(meta: FieldMeta, field_name: str) -> None:
    if meta.status == "invalid":
        _fail("dispatch_field_invalid", field_name)


def _topic_is_usable(turn_frame: TurnFrame, envelope: TargetTurnFramePolicyEnvelope) -> bool:
    meta = turn_frame.field_meta.topic
    if meta.status != "valid" or turn_frame.topic is None:
        return False
    return meta.confidence >= envelope.min_topic_confidence


def _assert_topic_scope_compatible(
    topic: str,
    envelope: TargetTurnFramePolicyEnvelope,
) -> None:
    if topic in envelope.forbidden_topics:
        _fail("dispatch_topic_scope_incompatible", topic)
    if topic not in envelope.allowed_topics:
        _fail("dispatch_topic_scope_incompatible", topic)


def _service_id_is_usable(
    turn_frame: TurnFrame,
    envelope: TargetTurnFramePolicyEnvelope,
) -> bool:
    meta = turn_frame.field_meta.service_id
    if meta.status != "valid" or turn_frame.service_id is None:
        return False
    return meta.confidence >= envelope.min_service_confidence


def _intent_price_is_usable(
    turn_frame: TurnFrame,
    envelope: TargetTurnFramePolicyEnvelope,
) -> bool:
    meta = turn_frame.field_meta.intent
    if meta.status != "valid":
        return False
    return meta.confidence >= envelope.min_intent_confidence


def _price_component_requested(
    turn_frame: TurnFrame,
    envelope: TargetTurnFramePolicyEnvelope,
) -> bool:
    components = _components_from_turn_frame(turn_frame, envelope)
    if "price" in components:
        return True
    return (
        turn_frame.intent in _PRICE_INTENTS
        and _intent_price_is_usable(turn_frame, envelope)
    )


def _scope_price_topic(
    turn_frame: TurnFrame,
    envelope: TargetTurnFramePolicyEnvelope,
) -> str | None:
    if not _price_component_requested(turn_frame, envelope):
        return None
    if not _topic_is_usable(turn_frame, envelope):
        return None
    return turn_frame.topic  # type: ignore[return-value]


def _initial_scope_price_stage(
    effective_scope: EffectiveScope | None,
) -> str | None:
    if effective_scope is None or effective_scope.extent == "unknown":
        return "broad_family_price"
    return None


def _components_from_turn_frame(
    turn_frame: TurnFrame,
    envelope: TargetTurnFramePolicyEnvelope,
) -> tuple[TargetResponseComponent, ...]:
    selected: set[TargetResponseComponent] = set()
    _reject_invalid(turn_frame.field_meta.aspects, "aspects")
    if _topic_is_usable(turn_frame, envelope):
        _assert_topic_scope_compatible(turn_frame.topic, envelope)  # type: ignore[arg-type]
    for aspect in turn_frame.aspects:
        if aspect == "overview" and turn_frame.topic == "doctors":
            continue
        selected.add(_ASPECT_TO_COMPONENT[aspect])

    if turn_frame.intent in _PRICE_INTENTS and _intent_price_is_usable(
        turn_frame, envelope
    ):
        selected.add("price")

    if _topic_is_usable(turn_frame, envelope):
        if turn_frame.topic == "doctors":
            selected.add("doctors")

    return tuple(component for component in _COMPONENT_ORDER if component in selected)


def _primary_component_from_aspect(
    aspect: AspectKind,
) -> TargetResponseComponent:
    if aspect in {"price", "payment", "included"}:
        return "price"
    return "content"


def _resolve_primary_component(
    components: tuple[TargetResponseComponent, ...],
    turn_frame: TurnFrame,
) -> TargetResponseComponent | None:
    if "content" in components and "price" in components:
        if turn_frame.primary_aspect is None:
            _fail("dispatch_followup_ambiguous", components)
        _reject_invalid(turn_frame.field_meta.primary_aspect, "primary_aspect")
        primary = _primary_component_from_aspect(turn_frame.primary_aspect)
        if primary not in components:
            _fail("dispatch_primary_component_missing", (turn_frame.primary_aspect, components))
        return primary
    return None


def _terminal_spec(
    *,
    response_mode: Literal["clarify", "defer", "medical_handoff"],
    envelope: TargetTurnFramePolicyEnvelope,
) -> TargetTurnFrameTerminalDispatch:
    if response_mode == "medical_handoff" and not envelope.forbidden_topics:
        _fail("dispatch_medical_forbidden_empty", envelope.forbidden_topics)
    request = TargetResponsePolicyRequest.model_validate(
        {
            "response_mode": response_mode,
            "service_id": None,
            "tone_key": envelope.tone_key,
            "allowed_topics": envelope.allowed_topics,
            "forbidden_topics": envelope.forbidden_topics,
            "required_fact_ids": (),
            "requested_components": (),
            "primary_component": None,
            "allow_marketing_facts": False,
            "allow_consultation_close": False,
            "allow_cta": False,
        }
    )
    terminal_mode: TargetTurnFrameTerminalMode
    if response_mode == "clarify":
        terminal_mode = "clarify"
    elif response_mode == "defer":
        terminal_mode = "defer"
    else:
        terminal_mode = "medical_handoff_nonmaterializable"
    return TargetTurnFrameTerminalDispatch(
        kind="terminal",
        terminal_mode=terminal_mode,
        spec=build_target_response_spec(request),
    )


def _materialize_fullcontext_content_policy_request(
    *,
    response_mode: TargetResponseMode,
    envelope: TargetTurnFramePolicyEnvelope,
) -> TargetResponsePolicyRequest:
    if response_mode == "medical_handoff" and not envelope.forbidden_topics:
        _fail("dispatch_medical_forbidden_empty", envelope.forbidden_topics)
    return TargetResponsePolicyRequest.model_validate(
        {
            "response_mode": response_mode,
            "service_id": None,
            "tone_key": envelope.tone_key,
            "allowed_topics": envelope.allowed_topics,
            "forbidden_topics": envelope.forbidden_topics,
            "required_fact_ids": (),
            "requested_components": ("content",),
            "primary_component": None,
            "allow_marketing_facts": False,
            "allow_consultation_close": envelope.allow_consultation_close,
            "allow_cta": False,
        }
    )


def _materialize_scope_price_policy_request(
    *,
    response_mode: TargetResponseMode,
    turn_topic: str,
    effective_scope: EffectiveScope | None,
    envelope: TargetTurnFramePolicyEnvelope,
) -> TargetResponsePolicyRequest:
    if response_mode == "medical_handoff" and not envelope.forbidden_topics:
        _fail("dispatch_medical_forbidden_empty", envelope.forbidden_topics)
    stage = _initial_scope_price_stage(effective_scope)
    allow_marketing = stage == "broad_family_price" and envelope.allow_marketing_facts
    allow_cta = stage == "broad_family_price" and envelope.allow_cta
    return TargetResponsePolicyRequest.model_validate(
        {
            "response_mode": response_mode,
            "service_id": None,
            "response_stage": stage,
            "scope_price_topic": turn_topic,
            "tone_key": envelope.tone_key,
            "allowed_topics": envelope.allowed_topics,
            "forbidden_topics": envelope.forbidden_topics,
            "required_fact_ids": (),
            "requested_components": ("price",),
            "primary_component": None,
            "allow_marketing_facts": allow_marketing,
            "allow_consultation_close": False,
            "allow_cta": allow_cta,
        }
    )


def _materialize_policy_request(
    *,
    response_mode: TargetResponseMode,
    service_id: str | None,
    components: tuple[TargetResponseComponent, ...],
    primary_component: TargetResponseComponent | None,
    envelope: TargetTurnFramePolicyEnvelope,
) -> TargetResponsePolicyRequest:
    if response_mode == "medical_handoff" and not envelope.forbidden_topics:
        _fail("dispatch_medical_forbidden_empty", envelope.forbidden_topics)
    return TargetResponsePolicyRequest.model_validate(
        {
            "response_mode": response_mode,
            "service_id": service_id,
            "tone_key": envelope.tone_key,
            "allowed_topics": envelope.allowed_topics,
            "forbidden_topics": envelope.forbidden_topics,
            "required_fact_ids": envelope.required_fact_ids,
            "requested_components": components,
            "primary_component": primary_component,
            "allow_marketing_facts": envelope.allow_marketing_facts,
            "allow_consultation_close": envelope.allow_consultation_close,
            "allow_cta": envelope.allow_cta,
        }
    )


def _is_fullcontext_content_only_components(
    components: tuple[TargetResponseComponent, ...],
    response_mode: TargetResponseMode,
) -> bool:
    return response_mode in {"answer", "medical_handoff"} and components == ("content",)


def dispatch_target_turn_frame_response(
    turn_frame: TurnFrame,
    envelope: TargetTurnFramePolicyEnvelope,
    *,
    effective_scope: EffectiveScope | None = None,
) -> TargetTurnFrameMaterializeDispatch | TargetTurnFrameTerminalDispatch:
    """Map one TurnFrame and explicit envelope to materialize or terminal dispatch."""

    if type(turn_frame) is not TurnFrame:
        _fail("dispatch_turn_frame_invalid", turn_frame)
    if type(envelope) is not TargetTurnFramePolicyEnvelope:
        _fail("dispatch_envelope_invalid", envelope)

    _reject_invalid(turn_frame.field_meta.intent, "intent")
    _reject_invalid(turn_frame.field_meta.topic, "topic")
    if turn_frame.needs_clarification:
        _reject_invalid(turn_frame.field_meta.needs_clarification, "needs_clarification")
    if turn_frame.service_id is not None:
        _reject_invalid(turn_frame.field_meta.service_id, "service_id")

    if envelope.boundary_decision == "medical_handoff":
        response_mode: TargetResponseMode = "medical_handoff"
    elif (
        turn_frame.needs_clarification
        and turn_frame.field_meta.needs_clarification.status == "valid"
    ):
        return _terminal_spec(response_mode="clarify", envelope=envelope)
    else:
        response_mode = "answer"

    components = _components_from_turn_frame(turn_frame, envelope)
    if not components:
        return _terminal_spec(response_mode="defer", envelope=envelope)

    if not _service_id_is_usable(turn_frame, envelope):
        if _is_fullcontext_content_only_components(components, response_mode):
            policy_request = _materialize_fullcontext_content_policy_request(
                response_mode=response_mode,
                envelope=envelope,
            )
            return TargetTurnFrameMaterializeDispatch(
                kind="materialize",
                policy_request=policy_request,
            )
        scope_topic = _scope_price_topic(turn_frame, envelope)
        if scope_topic is not None and response_mode == "answer":
            policy_request = _materialize_scope_price_policy_request(
                response_mode=response_mode,
                turn_topic=scope_topic,
                effective_scope=effective_scope,
                envelope=envelope,
            )
            return TargetTurnFrameMaterializeDispatch(
                kind="materialize",
                policy_request=policy_request,
            )
        if response_mode == "medical_handoff":
            return _terminal_spec(response_mode="medical_handoff", envelope=envelope)
        return _terminal_spec(response_mode="defer", envelope=envelope)

    primary_component = _resolve_primary_component(components, turn_frame)
    policy_request = _materialize_policy_request(
        response_mode=response_mode,
        service_id=turn_frame.service_id,  # type: ignore[arg-type]
        components=components,
        primary_component=primary_component,
        envelope=envelope,
    )
    return TargetTurnFrameMaterializeDispatch(
        kind="materialize",
        policy_request=policy_request,
    )
