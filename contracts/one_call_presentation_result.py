"""Unified post-Flash presentation result (Stage 5.1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from contracts.authored_service_alternative import AuthoredServiceAlternative
from contracts.service_reference import AvailabilityStatus, PriceCoverageKind

if TYPE_CHECKING:
    from core.target_response_verifier import TargetVerifiedComposedResponse

PresentationStatus = Literal["ok", "fail_closed"]


@dataclass(frozen=True, slots=True)
class PresentationQuickReply:
    label: str
    ref: str


@dataclass(frozen=True, slots=True)
class PresentationRenderedIds:
    marketing_fact_ids: tuple[str, ...]
    promo_fact_ids: tuple[str, ...]
    amplifier_refs: tuple[str, ...]
    followup_refs: tuple[str, ...]
    video_id: str | None
    situation_shown: bool


@dataclass(frozen=True, slots=True)
class PresentationCadenceDelta:
    shown_video_ids: tuple[str, ...] = ()
    shown_content_followup_refs: tuple[str, ...] = ()
    shown_price_followup_refs: tuple[str, ...] = ()
    situation_offered: bool = False


@dataclass(frozen=True, slots=True)
class PresentationSessionDelta:
    shown_fact_ids: tuple[str, ...]
    shown_amplifier_refs: tuple[str, ...]
    shown_consultation_value_refs: tuple[str, ...]
    last_rendered_promo_fact_id: str | None
    cadence_update: PresentationCadenceDelta


@dataclass(frozen=True, slots=True)
class OneCallPresentationResult:
    status: PresentationStatus
    reason_code: str | None
    final_patient_text: str
    authoritative_commerce: object | None
    rendered_marketing_fact_ids: tuple[str, ...]
    rendered_promo_fact_ids: tuple[str, ...]
    rendered_amplifier_refs: tuple[str, ...]
    selected_cta_key: str | None
    quick_replies: tuple[PresentationQuickReply, ...]
    secondary_content_slots: tuple[PresentationQuickReply, ...]
    video: dict[str, str] | None
    situation: dict[str, bool | str]
    presentation_channel: str
    rendered_ids: PresentationRenderedIds
    pending_session_delta: PresentationSessionDelta | None
    verified_for_session: TargetVerifiedComposedResponse | None = None
    offer_fact_refs: tuple[str, ...] = ()
    availability_status: AvailabilityStatus = "none"
    requested_service_id: str | None = None
    authored_alternatives: tuple[AuthoredServiceAlternative, ...] = ()
    price_coverage_kind: PriceCoverageKind = "none"
    family_price_context: str | None = None
    alternative_price_lines: tuple[str, ...] = ()
    rendered_alternative_service_ids: tuple[str, ...] = ()
    rendered_alternative_refs: tuple[str, ...] = ()
