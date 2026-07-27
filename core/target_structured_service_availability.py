"""Deterministic structured service availability answers from canonical service catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.response_schema import TargetService
from contracts.target_response_policy import TargetResponsePolicyRequest
from contracts.target_response_spec import TargetResponseSpec
from contracts.target_turn_frame_dispatch import (
    TargetTurnFrameBoundMaterializeResponse,
    TargetTurnFrameMaterializeDispatch,
)
from core.turn_frame_from_raw import service_availability_requested
from core.target_client_data import load_target_client_data
from core.target_response_followup_policy import TargetResponseFollowupSelection
from core.target_response_policy import build_target_response_spec
from core.target_response_verifier import TargetVerifiedComposedResponse
from core.target_session_selection import TargetMaterializedSessionSelection

PROVENANCE = "target_response.service_catalog"
ATTRIBUTION_KIND = "structured_service_availability"

_POLICY_REQUEST_MARKERS: dict[int, str] = {}
_SPEC_MARKERS: dict[int, str] = {}


@dataclass(frozen=True, slots=True)
class TargetStructuredServiceAvailabilityAnswer:
    client_id: str
    service_id: str
    service_name: str
    active: bool
    provenance: Literal["target_response.service_catalog"] = PROVENANCE
    attribution_kind: str = ATTRIBUTION_KIND
    content_ref: str | None = None


def mark_structured_service_availability_policy_request(
    request: TargetResponsePolicyRequest,
) -> TargetResponsePolicyRequest:
    _POLICY_REQUEST_MARKERS[id(request)] = "structured_service_availability"
    return request


def is_structured_service_availability_policy_request(
    request: TargetResponsePolicyRequest,
) -> bool:
    return (
        _POLICY_REQUEST_MARKERS.get(id(request))
        == "structured_service_availability"
    )


def mark_structured_service_availability_spec(spec: TargetResponseSpec) -> TargetResponseSpec:
    _SPEC_MARKERS[id(spec)] = "structured_service_availability"
    return spec


def is_structured_service_availability_spec(spec: TargetResponseSpec) -> bool:
    return _SPEC_MARKERS.get(id(spec)) == "structured_service_availability"



def lookup_catalog_service(
    client_id: str,
    service_id: str,
) -> TargetService | None:
    bundle = load_target_client_data(client_id).bundle
    return bundle.services.get(service_id)


def build_structured_service_availability_answer(
    *,
    client_id: str,
    service_id: str,
) -> TargetStructuredServiceAvailabilityAnswer:
    service = lookup_catalog_service(client_id, service_id)
    if service is None:
        raise ValueError("structured_service_availability_unknown_service")
    content_ref = str(service.content_ref).strip() if service.content_ref else None
    return TargetStructuredServiceAvailabilityAnswer(
        client_id=client_id,
        service_id=service_id,
        service_name=str(service.name or service_id).strip(),
        active=bool(service.active),
        content_ref=content_ref or None,
    )


def materialize_structured_service_availability_answer_text(
    answer: TargetStructuredServiceAvailabilityAnswer,
) -> str:
    name = answer.service_name.strip()
    if answer.active:
        return f"Да, клиника оказывает услугу «{name}»."
    return f"Сейчас услуга «{name}» в клинике не оказывается."


def build_structured_service_availability_policy_request(
    *,
    service_id: str,
    allowed_topics: tuple[str, ...],
) -> TargetResponsePolicyRequest:
    request = TargetResponsePolicyRequest.model_validate(
        {
            "response_mode": "answer",
            "service_id": service_id,
            "tone_key": "commercial_warm",
            "allowed_topics": allowed_topics,
            "forbidden_topics": ("diagnosis", "personal_eligibility"),
            "required_fact_ids": (),
            "requested_components": ("content",),
            "primary_component": None,
            "allow_marketing_facts": False,
            "allow_consultation_close": False,
            "allow_cta": False,
        }
    )
    return mark_structured_service_availability_policy_request(request)


def materialize_structured_service_availability_turn_response(
    *,
    client_id: str,
    turn_frame: TurnFrame,
    service_id: str,
    allowed_topics: tuple[str, ...],
) -> TargetTurnFrameBoundMaterializeResponse:
    availability = build_structured_service_availability_answer(
        client_id=client_id,
        service_id=service_id,
    )
    answer = materialize_structured_service_availability_answer_text(availability)
    policy_request = build_structured_service_availability_policy_request(
        service_id=service_id,
        allowed_topics=allowed_topics,
    )
    spec = mark_structured_service_availability_spec(
        build_target_response_spec(policy_request)
    )
    verified = TargetVerifiedComposedResponse(
        text=answer,
        spec=spec,
        selected_followups=TargetResponseFollowupSelection((), (), ()),
        selected_cta_key=None,
        navigation_followups=(),
        primary_content_ref=availability.content_ref,
        used_content_refs=(
            (availability.content_ref,) if availability.content_ref else ()
        ),
    )
    dispatch = TargetTurnFrameMaterializeDispatch(
        kind="materialize",
        policy_request=policy_request,
    )
    return TargetTurnFrameBoundMaterializeResponse(
        kind="materialize",
        dispatch=dispatch,
        verified=verified,
        session_selection=TargetMaterializedSessionSelection((), (), ()),
    )
