"""Mixed-request response composition from understanding ledger (D1R)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.clinic_policy_resolution import ClinicPolicyResolutionResult, RequestLedgerEntry
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


_UNCONFIRMED_POLICY_TEXT = (
    "Не могу подтвердить это условие по правилам клиники. "
    "Пожалуйста, уточните его у администратора."
)
_SECONDARY_PRICE_TEXT = "Стоимость остальных услуг уточним отдельно — укажите, какая услуга вас интересует."
_MISSING_CONTACT_TEXT = "Не могу подтвердить эти контактные данные. Пожалуйста, уточните их у администратора."
_MISSING_CONTENT_TEXT = "Не могу надёжно ответить на эту часть вопроса. Пожалуйста, уточните её."


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
    final_ledger: list[RequestLedgerEntry] = []
    used_model = False
    policy_keys_by_request: dict[str, list[str]] = {}
    blocked_request_ids = {entry.request_id for entry in resolution.ledger if entry.status == "blocked"}
    for decision in resolution.decisions:
        if decision.policy_key and decision.outcome in {"blocked", "allowed_by_known_rules"}:
            keys = policy_keys_by_request.setdefault(decision.request_id, [])
            if decision.policy_key not in keys:
                keys.append(decision.policy_key)
    unconfirmed_request_ids = {
        decision.request_id for decision in resolution.decisions
        if decision.outcome in {"no_applicable_rule", "needs_clarification"}
    }
    original_ledger = {entry.request_id: entry for entry in resolution.ledger}

    def record(req, status: str, text: str | None = None) -> None:
        original = original_ledger[req.request_id]
        final_ledger.append(original.model_copy(update={"status": status, "text": text}))

    for req in understanding.requests:
        if req.request_id in blocked_request_ids:
            block_parts = _policy_segments(client_id, tuple(policy_keys_by_request.get(req.request_id, ())))
            for block_text in block_parts:
                if block_text not in segments:
                    segments.append(block_text)
            record(req, "blocked", "\n\n".join(block_parts) or None)
            continue

        if req.request_id in unconfirmed_request_ids and req.kind in {"price", "booking"}:
            if _UNCONFIRMED_POLICY_TEXT not in segments:
                segments.append(_UNCONFIRMED_POLICY_TEXT)
            record(req, "clarification_needed", _UNCONFIRMED_POLICY_TEXT)
            continue

        if req.kind == "clinic_policy":
            parts = _policy_segments(client_id, tuple(policy_keys_by_request.get(req.request_id, ())))
            for part in parts:
                if part not in segments:
                    segments.append(part)
            if req.request_id in unconfirmed_request_ids or not parts:
                if _UNCONFIRMED_POLICY_TEXT not in segments:
                    segments.append(_UNCONFIRMED_POLICY_TEXT)
                parts.append(_UNCONFIRMED_POLICY_TEXT)
            record(req, "answered" if req.request_id not in unconfirmed_request_ids and len(parts) > 0 else "clarification_needed", "\n\n".join(parts))
            continue

        if req.kind == "contact":
            contact = _contact_segment(
                client_id=client_id,
                contact_fields=req.contact_fields,
                branch_hint=user_message,
            ) if req.contact_fields else None
            if contact:
                segments.append(contact)
                record(req, "answered", contact)
            else:
                segments.append(_MISSING_CONTACT_TEXT)
                record(req, "clarification_needed", _MISSING_CONTACT_TEXT)
            continue

        if req.kind in {"content", "other"}:
            content = (req.content_text or "").strip()
            if content:
                segments.append(content)
                record(req, "answered", content)
            else:
                segments.append(_MISSING_CONTENT_TEXT)
                record(req, "clarification_needed", _MISSING_CONTENT_TEXT)
            continue

        if req.kind == "price":
            if primary_price_request_id == req.request_id:
                # Only the canonical commerce renderer supplies this block.
                supplement = primary_price_text.strip()
                if supplement:
                    segments.append(supplement)
                record(req, "answered" if supplement else "deferred", supplement or None)
            else:
                if _SECONDARY_PRICE_TEXT not in segments:
                    segments.append(_SECONDARY_PRICE_TEXT)
                record(req, "clarification_needed", _SECONDARY_PRICE_TEXT)
            continue

        record(req, original_ledger[req.request_id].status)

    patient_text = "\n\n".join(segments).strip()
    return ResponseCompositionResult(
        patient_text=patient_text,
        resolution=resolution.model_copy(update={"ledger": tuple(final_ledger)}),
        suppress_forbidden_booking_cta=resolution.suppress_forbidden_booking_cta,
        used_model_patient_text=used_model,
    )
