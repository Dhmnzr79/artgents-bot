"""Clinic business policy authority — D1R resolver adapter (no regex classifiers)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from contracts.request_understanding import RequestUnderstanding
from core.clinic_policies_loader import (
    ClinicPoliciesBundle,
    load_clinic_policies,
    policy_answer,
)
from core.client_config_loader import resolve_pack_client_id
from core.one_call_response_composition import compose_response_from_understanding

KNOWN_CLINIC_POLICY_KEYS: frozenset[str] = frozenset(
    {"no_pediatric_dentistry", "no_oms", "no_dms"}
)


class ClinicBusinessPolicyLoadError(ValueError):
    """Raised when authored business policies exist but are unusable at the D1 boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ClinicPolicyEnforcementResult:
    patient_text: str
    enforced: bool
    applicable_policy_keys: tuple[str, ...]
    suppress_forbidden_booking_cta: bool
    reason_code: str | None = None


def _policy_bundle(client_id: str) -> ClinicPoliciesBundle | None:
    pack = resolve_pack_client_id(client_id)
    return load_clinic_policies(pack)


def _policy_keys_for_pack(bundle: ClinicPoliciesBundle) -> frozenset[str]:
    return frozenset(p.key for p in bundle.policies)


def validate_connectable_business_policies(client_id: str) -> None:
    bundle = _policy_bundle(client_id)
    if bundle is None:
        return
    raw_path_policies = bundle.policies
    if not raw_path_policies:
        return
    usable = [p for p in raw_path_policies if p.answer.strip()]
    if not usable:
        raise ClinicBusinessPolicyLoadError("clinic_business_policies_unusable")


def build_clinic_business_policies_payload(client_id: str | None) -> dict[str, object]:
    raw = (client_id or "").strip()
    if not raw:
        return {"client_id": None, "policies_available": False}
    pack = resolve_pack_client_id(raw)
    bundle = load_clinic_policies(pack)
    if bundle is None or not bundle.policies:
        return {"client_id": pack, "policies_available": False}
    rows: list[dict[str, str]] = []
    for pol in bundle.policies:
        if not pol.answer.strip():
            continue
        rows.append(
            {
                "policy_key": pol.key,
                "answer": pol.answer.strip(),
                "scope_note": _scope_note_for_policy_key(pol.key),
            }
        )
    if not rows:
        return {"client_id": pack, "policies_available": False}
    return {
        "client_id": pack,
        "policies_available": True,
        "policies": rows,
    }


def serialize_clinic_business_policies_block(client_id: str | None) -> str:
    payload = build_clinic_business_policies_payload(client_id)
    if not payload.get("policies_available"):
        return ""
    return (
        "=== CLINIC_BUSINESS_POLICIES ===\n"
        "Authoritative clinic business constraints (not medical advice). "
        "Populate request_understanding.clinic_policy requests with policy_ids; "
        "code owns final policy/contact/price surfaces.\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _scope_note_for_policy_key(policy_key: str) -> str:
    if policy_key == "no_pediatric_dentistry":
        return (
            "Applies when the patient asks about treating or booking a child/by age. "
            "Not for adult self-identification, childhood history, or unrelated mentions of children."
        )
    if policy_key == "no_oms":
        return "Applies when the patient asks whether treatment is available under OMS."
    if policy_key == "no_dms":
        return "Applies when the patient asks whether treatment is billed via DMS."
    return "Apply only when the patient's question matches this business constraint."


def _policy_keys_from_understanding(understanding: RequestUnderstanding) -> tuple[str, ...]:
    keys: list[str] = []
    for req in understanding.requests:
        if req.kind == "clinic_policy":
            for key in req.policy_ids:
                if key not in keys:
                    keys.append(key)
    return tuple(keys)


def apply_clinic_business_policy_authority(
    *,
    client_id: str,
    user_message: str,
    dialog_history: str = "",
    model_patient_text: str,
    request_understanding: RequestUnderstanding | None = None,
    primary_price_request_id: str | None = None,
) -> ClinicPolicyEnforcementResult:
    try:
        validate_connectable_business_policies(client_id)
    except ClinicBusinessPolicyLoadError:
        return ClinicPolicyEnforcementResult(
            patient_text=(
                "Сейчас не могу надёжно ответить по правилам клиники по этому вопросу. "
                "Администратор поможет уточнить детали."
            ),
            enforced=True,
            applicable_policy_keys=(),
            suppress_forbidden_booking_cta=True,
            reason_code="clinic_business_policies_unusable",
        )

    if request_understanding is None or not request_understanding.requests:
        return ClinicPolicyEnforcementResult(
            patient_text=model_patient_text,
            enforced=False,
            applicable_policy_keys=(),
            suppress_forbidden_booking_cta=False,
        )

    composed = compose_response_from_understanding(
        client_id=client_id,
        understanding=request_understanding,
        model_patient_text=model_patient_text,
        primary_price_request_id=primary_price_request_id,
        user_message=user_message,
    )
    policy_keys = _policy_keys_from_understanding(request_understanding)
    enforced = bool(policy_keys) or composed.suppress_forbidden_booking_cta or composed.used_model_patient_text
    if composed.patient_text != model_patient_text.strip():
        enforced = True
    return ClinicPolicyEnforcementResult(
        patient_text=composed.patient_text,
        enforced=enforced,
        applicable_policy_keys=policy_keys,
        suppress_forbidden_booking_cta=composed.suppress_forbidden_booking_cta,
        reason_code="clinic_policy_d1r_composed" if enforced else None,
    )


def read_dialog_history_for_policy(sid: str) -> str:
    if not (sid or "").strip():
        return ""
    try:
        from session import mem_get

        return str(mem_get(sid).get("dialog_context") or "")
    except Exception:
        return ""
