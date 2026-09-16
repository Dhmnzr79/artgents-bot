"""Mixed-request response composition from understanding ledger (D1R)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.clinic_policy_resolution import ClinicPolicyResolutionResult
from contracts.request_understanding import RequestUnderstanding
from core.clinic_policies_loader import policy_answer
from core.clinic_policy_resolver import resolve_clinic_policies
from core.client_config_loader import resolve_pack_client_id
from core.target_contact_authority import contact_fields_from_turn_aspects
from core.target_structured_answer import materialize_structured_contact_answer_text


@dataclass(frozen=True, slots=True)
class ResponseCompositionResult:
    patient_text: str
    resolution: ClinicPolicyResolutionResult
    suppress_forbidden_booking_cta: bool
    used_model_patient_text: bool


def _policy_segments(client_id: str, policy_ids: tuple[str, ...]) -> list[str]:
    pack = resolve_pack_client_id(client_id)
    segments: list[str] = []
    seen: set[str] = set()
    for key in policy_ids:
        if key in seen:
            continue
        answer = policy_answer(pack, key)
        if answer and answer.strip():
            segments.append(answer.strip())
            seen.add(key)
    return segments


def _contact_segment(
    *,
    client_id: str,
    contact_fields: tuple[str, ...],
    branch_hint: str,
) -> str | None:
    if not contact_fields:
        return None
    primary = contact_fields[0]
    aspects = contact_fields
    contact_fields_resolved = contact_fields_from_turn_aspects(aspects, primary_aspect=primary)
    if contact_fields_resolved is None:
        return None
    answer = materialize_structured_contact_answer_text(
        client_id,
        contact_fields=contact_fields_resolved,
        branch_hint_text=branch_hint,
    )
    text = (answer or "").strip()
    return text or None


def _blocked_pediatric_segment(client_id: str) -> str | None:
    pack = resolve_pack_client_id(client_id)
    text = policy_answer(pack, "no_pediatric_dentistry")
    return text.strip() if text and text.strip() else None


def compose_response_from_understanding(
    *,
    client_id: str,
    understanding: RequestUnderstanding,
    model_patient_text: str = "",
    primary_price_request_id: str | None = None,
    user_message: str = "",
    primary_price_text: str = "",
) -> ResponseCompositionResult:
    """Assemble visible patient text from ledger; ignore hostile model prose for code-owned blocks."""

    resolution = resolve_clinic_policies(client_id=client_id, understanding=understanding)
    segments: list[str] = []
    used_model = False
    blocked_request_ids = {
        entry.request_id
        for entry in resolution.ledger
        if entry.status == "blocked"
    }

    for req in understanding.requests:
        if req.request_id in blocked_request_ids:
            block_text = _blocked_pediatric_segment(client_id)
            if block_text and block_text not in segments:
                segments.append(block_text)
            continue

        if req.kind == "clinic_policy" and req.policy_ids:
            for part in _policy_segments(client_id, req.policy_ids):
                if part not in segments:
                    segments.append(part)
            continue

        if req.kind == "contact" and req.contact_fields:
            contact = _contact_segment(
                client_id=client_id,
                contact_fields=req.contact_fields,
                branch_hint=user_message,
            )
            if contact:
                segments.append(contact)
            continue

        if req.kind in {"content", "other"} and req.content_text and req.content_text.strip():
            segments.append(req.content_text.strip())
            continue

        if req.kind == "price" and primary_price_request_id == req.request_id:
            # Only the canonical commerce renderer supplies this block.
            supplement = primary_price_text.strip()
            if supplement:
                segments.append(supplement)

    patient_text = "\n\n".join(segments).strip()
    return ResponseCompositionResult(
        patient_text=patient_text,
        resolution=resolution,
        suppress_forbidden_booking_cta=resolution.suppress_forbidden_booking_cta,
        used_model_patient_text=used_model,
    )
