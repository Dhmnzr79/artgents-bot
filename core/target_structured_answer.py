"""Deterministic structured-answer mode for exact external contracts (contacts first)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.target_response_policy import TargetResponsePolicyRequest
from contracts.target_turn_frame_dispatch import (
    TargetTurnFrameBoundMaterializeResponse,
    TargetTurnFrameMaterializeDispatch,
)
from contracts.turn_frame import TurnFrame
from core.target_contact_authority import (
    ContactFieldKind,
    materialize_clinic_contact_primary_evidence,
)
from core.target_presentation_turn_projection import contact_fields_from_turn_frame
from core.turn_frame_from_raw import service_availability_requested
from core.target_response_followup_policy import TargetResponseFollowupSelection
from core.target_response_policy import build_target_response_spec
from core.target_response_verifier import TargetVerifiedComposedResponse
from core.target_session_selection import TargetMaterializedSessionSelection

StructuredAnswerKind = Literal["clinic_contact", "service_availability"]


@dataclass(frozen=True, slots=True)
class StructuredAnswerCapability:
    kind: StructuredAnswerKind
    contact_fields: tuple[ContactFieldKind, ...] = ()
    service_id: str | None = None


def resolve_structured_answer_capability(turn_frame: TurnFrame) -> StructuredAnswerCapability | None:
    """Return structured-answer capability for contacts or service availability."""

    if turn_frame.needs_clarification:
        return None
    if turn_frame.field_meta.needs_clarification.status == "invalid":
        return None
    if turn_frame.field_meta.aspects.status == "invalid":
        return None
    fields = contact_fields_from_turn_frame(turn_frame)
    if fields is not None:
        return StructuredAnswerCapability(
            kind="clinic_contact",
            contact_fields=fields,
        )
    if service_availability_requested(turn_frame):
        return StructuredAnswerCapability(
            kind="service_availability",
            service_id=turn_frame.service_id,
        )
    return None


def materialize_structured_contact_answer_text(
    client_id: str,
    contact_fields: tuple[ContactFieldKind, ...],
) -> str:
    blocks = materialize_clinic_contact_primary_evidence(
        client_id,
        fields=contact_fields,
    )
    lines = [block.text for block in blocks if block.text.strip()]
    return "\n".join(lines)


def materialize_structured_contact_turn_response(
    *,
    client_id: str,
    turn_frame: TurnFrame,
    contact_fields: tuple[ContactFieldKind, ...],
    allowed_topics: tuple[str, ...],
) -> TargetTurnFrameBoundMaterializeResponse:
    """Build one verified structured contact response without Composer or Verifier."""

    answer = materialize_structured_contact_answer_text(client_id, contact_fields)
    if not answer.strip():
        raise ValueError("structured_contact_answer_empty")
    policy_request = TargetResponsePolicyRequest.model_validate(
        {
            "response_mode": "answer",
            "service_id": None,
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
    spec = build_target_response_spec(policy_request)
    verified = TargetVerifiedComposedResponse(
        text=answer,
        spec=spec,
        selected_followups=TargetResponseFollowupSelection((), (), ()),
        selected_cta_key=None,
        navigation_followups=(),
        primary_content_ref=None,
        used_content_refs=(),
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
