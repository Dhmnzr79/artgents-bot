"""Planner-independent generic FullContext informational content authority."""

from __future__ import annotations

from contracts.target_response_policy import TargetResponsePolicyRequest
from contracts.target_response_spec import TargetResponseSpec
from contracts.target_turn_frame_policy_envelope import TargetTurnFramePolicyEnvelope
from contracts.turn_frame import TurnFrame
from core.attribute_followup import (
    detect_vague_attribute_kinds,
    is_vague_attribute_followup_any,
)
from core.turn_frame_from_raw import service_availability_requested
from core.target_fullcontext_content_package import (
    GENERIC_FULLCONTEXT_ALLOW_PRICE,
    is_fullcontext_content_only_spec,
)

GENERIC_FULLCONTEXT_CONTENT_CAPABILITY = "generic_fullcontext_content"

_PRICE_INTENTS = frozenset({"price_lookup", "price_concern"})
_STRUCTURED_PRICE_ASPECTS = frozenset({"price", "payment", "included", "comparison"})
_CONTACT_ASPECTS = frozenset(
    {
        "contacts",
        "contact_phone",
        "contact_address",
        "contact_parking",
        "contact_hours",
        "contact_whatsapp",
    }
)

_POLICY_REQUEST_MARKERS: dict[int, str] = {}


def mark_generic_fullcontext_content_policy_request(
    request: TargetResponsePolicyRequest,
) -> TargetResponsePolicyRequest:
    """Tag one policy request as generic_fullcontext_content for downstream audit."""

    _POLICY_REQUEST_MARKERS[id(request)] = GENERIC_FULLCONTEXT_CONTENT_CAPABILITY
    return request


def is_generic_fullcontext_content_policy_request(
    request: TargetResponsePolicyRequest,
) -> bool:
    return (
        _POLICY_REQUEST_MARKERS.get(id(request))
        == GENERIC_FULLCONTEXT_CONTENT_CAPABILITY
    )


def is_generic_fullcontext_content_spec(spec: TargetResponseSpec) -> bool:
    return is_fullcontext_content_only_spec(spec) and not GENERIC_FULLCONTEXT_ALLOW_PRICE


def _topic_is_usable(
    turn_frame: TurnFrame,
    envelope: TargetTurnFramePolicyEnvelope,
) -> bool:
    meta = turn_frame.field_meta.topic
    if meta.status != "valid" or turn_frame.topic is None:
        return False
    return meta.confidence >= envelope.min_topic_confidence


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


def _has_structured_contact_aspects(turn_frame: TurnFrame) -> bool:
    aspects = set(turn_frame.aspects)
    primary = turn_frame.primary_aspect
    return bool(aspects & _CONTACT_ASPECTS or primary in _CONTACT_ASPECTS)


def structured_clarification_required(
    turn_frame: TurnFrame,
    envelope: TargetTurnFramePolicyEnvelope,
) -> bool:
    """Terminal clarify only when a structured action still needs a missing parameter."""

    if not turn_frame.needs_clarification:
        return False
    if turn_frame.field_meta.needs_clarification.status != "valid":
        return False
    if turn_frame.intent in _PRICE_INTENTS and _intent_price_is_usable(
        turn_frame,
        envelope,
    ):
        return True
    if turn_frame.field_meta.aspects.status == "valid" and any(
        aspect in _STRUCTURED_PRICE_ASPECTS for aspect in turn_frame.aspects
    ):
        return True
    if _service_id_is_usable(turn_frame, envelope):
        return True
    if _topic_is_usable(turn_frame, envelope) and turn_frame.topic == "doctors":
        return True
    if _has_structured_contact_aspects(turn_frame):
        return True
    return False


def structured_route_blocks_generic(
    turn_frame: TurnFrame,
    envelope: TargetTurnFramePolicyEnvelope,
) -> bool:
    if turn_frame.intent in _PRICE_INTENTS and _intent_price_is_usable(
        turn_frame,
        envelope,
    ):
        return True
    if turn_frame.field_meta.aspects.status == "valid" and any(
        aspect in _STRUCTURED_PRICE_ASPECTS for aspect in turn_frame.aspects
    ):
        return True
    if _topic_is_usable(turn_frame, envelope) and turn_frame.topic == "doctors":
        return True
    if _has_structured_contact_aspects(turn_frame):
        return True
    return False


def generic_fullcontext_content_eligible(
    turn_frame: TurnFrame,
    envelope: TargetTurnFramePolicyEnvelope,
) -> bool:
    """True when ordinary FAQ/info may use cached FullContext without planner sufficiency."""

    if structured_clarification_required(turn_frame, envelope):
        return False
    if structured_route_blocks_generic(turn_frame, envelope):
        return False
    if turn_frame.field_meta.intent.status == "invalid":
        return False
    if turn_frame.field_meta.topic.status == "invalid":
        return False
    if turn_frame.service_id is not None and turn_frame.field_meta.service_id.status == "invalid":
        return False
    return True


def build_generic_fullcontext_content_policy_request(
    *,
    response_mode: str,
    envelope: TargetTurnFramePolicyEnvelope,
) -> TargetResponsePolicyRequest:
    if response_mode == "medical_handoff" and not envelope.forbidden_topics:
        raise ValueError("dispatch_medical_forbidden_empty")
    request = TargetResponsePolicyRequest.model_validate(
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
    return mark_generic_fullcontext_content_policy_request(request)


def should_skip_session_service_hydration(
    turn_frame: TurnFrame,
    *,
    user_message: str,
) -> bool:
    """Standalone informational turns must not inherit stale session service focus."""

    if service_availability_requested(turn_frame):
        return True
    if turn_frame.service_id is not None:
        return False
    if not is_vague_attribute_followup_any(user_message):
        return True
    kinds = set(detect_vague_attribute_kinds(user_message))
    if kinds & {"price", "payment", "doctor"}:
        return False
    aspect = str(turn_frame.primary_aspect or "").strip()
    if aspect in {"price", "payment"}:
        return False
    if any(item in {"price", "payment"} for item in turn_frame.aspects):
        return False
    if turn_frame.topic == "doctors":
        return False
    return True


def marketing_scenarios_allowed_for_turn(turn_frame: TurnFrame) -> bool:
    if turn_frame.field_meta.needs_clarification.status == "invalid":
        return False
    if not turn_frame.needs_clarification:
        return True
    if turn_frame.intent in _PRICE_INTENTS:
        return False
    if turn_frame.field_meta.aspects.status == "valid" and any(
        aspect in _STRUCTURED_PRICE_ASPECTS for aspect in turn_frame.aspects
    ):
        return False
    if _has_structured_contact_aspects(turn_frame):
        return False
    return True


def advisory_clarification_blocks_marketing(turn_frame: TurnFrame) -> bool:
    return turn_frame.needs_clarification and not marketing_scenarios_allowed_for_turn(
        turn_frame
    )
