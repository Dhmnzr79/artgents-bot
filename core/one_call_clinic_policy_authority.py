"""Clinic business policy authority for the sales-fast / one-call path (Demo D1)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

from core.clinic_policies_loader import (
    ClinicPoliciesBundle,
    load_clinic_policies,
    policy_answer,
)
from core.client_config_loader import resolve_pack_client_id

KNOWN_CLINIC_POLICY_KEYS: frozenset[str] = frozenset(
    {"no_pediatric_dentistry", "no_oms", "no_dms"}
)

_PEDIATRIC_FALSE_POSITIVE_RE = re.compile(
    r"(?:"
    r"\b(?:я\s+)?(?:взросл\w*|совершеннолет\w*)\b"
    r"|\bне\s+(?:ребен\w*|ребён\w*|дет\w*)\b"
    r"|\bв\s+детств\w*\b"
    r"|\b(?:когда|когда\s+я)\s+(?:был\w*|была)\s+(?:ребен\w*|ребён\w*|мален\w*)\b"
    r"|\b(?:в\s+детстве|в\s+школ\w*)\s+(?:лечил\w*|лечили|был\w*)\b"
    r")",
    re.I | re.U,
)

_PEDIATRIC_INTENT_RE = re.compile(
    r"(?:"
    r"(?:лечит\w*|принимает\w*|вед(?:ё|е)т\w*)\s+(?:ли\s+)?(?:у\s+вас\s+)?(?:дет\w*|ребен\w*|ребён\w*)"
    r"|(?:детск\w*\s+стоматолог\w*)"
    r"|(?:ребен\w*|ребён\w*)\s+\d+\s*(?:лет|год)"
    r"|(?:можно|можете)\s+(?:ли\s+)?(?:привест\w*|запис\w*)\s+(?:ребен\w*|ребён\w*|дет\w*)"
    r"|(?:запис\w*|при(?:вест|вед)\w*)\s+(?:ребен\w*|ребён\w*|дет\w*)"
    r"|(?:принимает\w*|работает\w*)\s+(?:ли\s+)?(?:с\s+)?(?:дет\w*|ребен\w*|ребён\w*)"
    r")",
    re.I | re.U,
)

_OMS_INTENT_RE = re.compile(
    r"(?:\b(?:по\s+)?омс\b|\bполис\w*\s+омс\b|\b(?:лечит\w*|работ\w*|приним\w*).{0,40}\bомс\b)",
    re.I | re.U,
)

_DMS_INTENT_RE = re.compile(
    r"(?:\b(?:по\s+)?дмс\b|\bполис\w*\s+дмс\b|\b(?:лечит\w*|работ\w*|приним\w*).{0,40}\bдмс\b)",
    re.I | re.U,
)

_CONTRADICTION_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "no_pediatric_dentistry": (
        re.compile(
            r"(?:"
            r"принима\w*\s+(?:дет\w*|ребен\w*|ребён\w*)"
            r"|лечим\s+(?:дет\w*|ребен\w*|ребён\w*)"
            r"|работа\w*\s+с\s+(?:дет\w*|ребен\w*|ребён\w*)"
            r"|детск\w*\s+стоматолог\w*\s+(?:вед\w*|есть|оказыва\w*)"
            r"|мож\w*\s+запис\w*\s+(?:ребен\w*|ребён\w*|дет\w*)"
            r"|при(?:вод|вед)\w*\s+(?:ребен\w*|ребён\w*|дет\w*)"
            r")",
            re.I | re.U,
        ),
    ),
    "no_oms": (
        re.compile(
            r"(?:"
            r"(?:работ\w*|леч\w*|приним\w*).{0,30}\bомс\b"
            r"|\bомс\b.{0,20}(?:можно|работ\w*|приним\w*|леч\w*)"
            r"|(?:лечение|при(?:ё|e)м).{0,30}\bомс\b"
            r")",
            re.I | re.U,
        ),
    ),
    "no_dms": (
        re.compile(
            r"(?:"
            r"(?:работ\w*|леч\w*|приним\w*).{0,30}\bдмс\b"
            r"|\bдмс\b.{0,20}(?:можно|работ\w*|приним\w*|леч\w*)"
            r"|(?:лечение|при(?:ё|e)м).{0,30}\bдмс\b"
            r")",
            re.I | re.U,
        ),
    ),
}


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


def _norm(text: str) -> str:
    return (text or "").strip().lower().replace("ё", "е")


def _policy_bundle(client_id: str) -> ClinicPoliciesBundle | None:
    pack = resolve_pack_client_id(client_id)
    return load_clinic_policies(pack)


def _policy_keys_for_pack(bundle: ClinicPoliciesBundle) -> frozenset[str]:
    return frozenset(p.key for p in bundle.policies)


def validate_connectable_business_policies(client_id: str) -> None:
    """Fail closed when a pack declares policies but none are loadable."""

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
        "When a policy applies to the patient's question, patient_text must align with "
        "the authored answer and must not promise care or payment the policy forbids.\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _scope_note_for_policy_key(policy_key: str) -> str:
    if policy_key == "no_pediatric_dentistry":
        return (
            "Applies only when the patient asks about treating or booking a child/by age. "
            "Not for adult self-identification, childhood history, or unrelated mentions of children."
        )
    if policy_key == "no_oms":
        return "Applies when the patient asks whether treatment is available under OMS."
    if policy_key == "no_dms":
        return "Applies when the patient asks whether treatment is billed via DMS."
    return "Apply only when the patient's question matches this business constraint."


def assess_applicable_clinic_policies(
    *,
    user_message: str,
    dialog_history: str = "",
    client_id: str,
) -> tuple[str, ...]:
    bundle = _policy_bundle(client_id)
    if bundle is None or not bundle.policies:
        return ()
    allowed = _policy_keys_for_pack(bundle)
    combined = _norm(f"{dialog_history}\n{user_message}")
    msg = _norm(user_message)
    keys: list[str] = []

    if "no_pediatric_dentistry" in allowed and _pediatric_policy_applies(msg, combined):
        keys.append("no_pediatric_dentistry")
    if "no_oms" in allowed and _OMS_INTENT_RE.search(msg):
        keys.append("no_oms")
    if "no_dms" in allowed and _DMS_INTENT_RE.search(msg):
        keys.append("no_dms")
    return tuple(keys)


def _pediatric_policy_applies(user_message: str, combined_context: str) -> bool:
    msg = _norm(user_message)
    if _PEDIATRIC_FALSE_POSITIVE_RE.search(msg):
        return False
    if _PEDIATRIC_INTENT_RE.search(msg):
        return True
    if any(
        trig in msg
        for trig in ("детск", "ребен", "ребён", "детей", "детям", "малыш", "несовершеннолет")
    ) and _looks_like_pediatric_service_question(msg):
        return True
    if re.search(r"(?:лечит\w*|приним\w*)\s+.*(?:дет|ребен|ребён)", msg):
        return True
    return False


def _looks_like_pediatric_service_question(msg: str) -> bool:
    return bool(
        re.search(
            r"(?:лечит\w*|приним\w*|запис\w*|мож\w*|есть\s+ли|работает\w*)",
            msg,
            re.I | re.U,
        )
    )


def model_text_contradicts_clinic_policy(*, patient_text: str, policy_key: str) -> bool:
    if policy_key not in _CONTRADICTION_PATTERNS:
        return False
    body = _norm(patient_text)
    if not body:
        return False
    return any(pattern.search(body) for pattern in _CONTRADICTION_PATTERNS[policy_key])


def _authored_policy_segments(
    client_id: str,
    policy_keys: Iterable[str],
) -> list[str]:
    pack = resolve_pack_client_id(client_id)
    segments: list[str] = []
    for key in policy_keys:
        answer = policy_answer(pack, key)
        if answer and answer.strip():
            segments.append(answer.strip())
    return segments


def _contact_supplement_for_mixed_turn(*, client_id: str, user_message: str) -> str | None:
    aspects = _contact_aspects_from_message(user_message)
    if not aspects:
        return None
    from core.target_contact_authority import contact_fields_from_turn_aspects
    from core.target_structured_answer import materialize_structured_contact_answer_text

    contact_fields = contact_fields_from_turn_aspects(aspects, primary_aspect=aspects[0])
    if contact_fields is None:
        return None
    answer = materialize_structured_contact_answer_text(
        client_id,
        contact_fields=contact_fields,
        branch_hint_text=user_message,
    )
    text = (answer or "").strip()
    return text or None


def _contact_aspects_from_message(q: str) -> tuple[str, ...] | None:
    from config import CONTACTS_RE
    from core.user_text_privacy import EMAIL_PLACEHOLDER, PHONE_PLACEHOLDER

    if not q:
        return None
    scan_q = (q or "").replace(PHONE_PLACEHOLDER, " ").replace(EMAIL_PLACEHOLDER, " ")
    aspects: list[str] = []
    seen: set[str] = set()
    for match in CONTACTS_RE.finditer(scan_q):
        token = match.group(0).lower()
        aspect: str | None = None
        if "парков" in token:
            aspect = "contact_parking"
        elif "телефон" in token:
            aspect = "contact_phone"
        elif "whatsapp" in token:
            aspect = "contact_whatsapp"
        elif "график" in token or "время" in token or "суббот" in token or "воскресен" in token:
            aspect = "contact_hours"
        elif any(
            part in token
            for part in (
                "адрес",
                "наход",
                "доехать",
                "проехать",
                "клиник",
                "метро",
                "располож",
                "карт",
            )
        ):
            aspect = "contact_address"
        if aspect is None:
            return None
        if aspect not in seen:
            seen.add(aspect)
            aspects.append(aspect)
    if aspects:
        return tuple(aspects)
    low = q.lower()
    if "контакт" in low:
        return ("contacts",)
    if any(
        hint in low
        for hint in (
            "где наход",
            "как доехать",
            "как проехать",
            "ваш адрес",
            "адрес клиник",
        )
    ):
        return ("contact_address",)
    return None


def _safe_supplement_from_model(
    *,
    model_patient_text: str,
    policy_keys: tuple[str, ...],
    user_message: str,
) -> str:
    """Keep non-contradicting model prose for explicit secondary asks (e.g. adult price)."""

    if not model_patient_text.strip():
        return ""
    if not policy_keys:
        return model_patient_text.strip()
    if "no_pediatric_dentistry" in policy_keys and not re.search(
        r"(?:чистк|стоим|сколько\s+стоит|цен\w*)",
        _norm(user_message),
    ):
        return ""
    parts: list[str] = []
    for chunk in re.split(r"(?<=[.!?])\s+", model_patient_text.strip()):
        chunk = chunk.strip()
        if not chunk:
            continue
        if any(model_text_contradicts_clinic_policy(patient_text=chunk, policy_key=k) for k in policy_keys):
            continue
        parts.append(chunk)
    return " ".join(parts).strip()


def clinic_policy_turn_prefers_model(user_message: str, policy_keys: tuple[str, ...]) -> bool:
    """True when a mixed turn still needs the one-call model (e.g. adult price after OMS)."""

    if not policy_keys:
        return False
    msg = _norm(user_message)
    if _contact_aspects_from_message(user_message):
        return False
    if not re.search(r"(?:чистк|стоим|сколько\s+стоит|цен\w*)", msg):
        return False
    if _PEDIATRIC_FALSE_POSITIVE_RE.search(msg):
        return True
    return "no_oms" in policy_keys or "no_dms" in policy_keys


def _turn_requests_model_supplement(user_message: str, policy_keys: tuple[str, ...]) -> bool:
    return clinic_policy_turn_prefers_model(user_message, policy_keys)


def compose_clinic_policy_patient_text(
    *,
    client_id: str,
    user_message: str,
    policy_keys: tuple[str, ...],
    model_patient_text: str = "",
) -> str:
    segments = _authored_policy_segments(client_id, policy_keys)
    contact = _contact_supplement_for_mixed_turn(client_id=client_id, user_message=user_message)
    if contact:
        segments.append(contact)
    if _turn_requests_model_supplement(user_message, policy_keys):
        supplement = _safe_supplement_from_model(
            model_patient_text=model_patient_text,
            policy_keys=policy_keys,
            user_message=user_message,
        )
        if supplement:
            segments.append(supplement)
    if not segments:
        return model_patient_text.strip()
    return "\n\n".join(segments)


def apply_clinic_business_policy_authority(
    *,
    client_id: str,
    user_message: str,
    dialog_history: str = "",
    model_patient_text: str,
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

    applicable = assess_applicable_clinic_policies(
        user_message=user_message,
        dialog_history=dialog_history,
        client_id=client_id,
    )
    contradictions = tuple(
        key
        for key in applicable
        if model_text_contradicts_clinic_policy(patient_text=model_patient_text, policy_key=key)
    )
    also_detect = tuple(
        key
        for key in KNOWN_CLINIC_POLICY_KEYS
        if key not in applicable
        and model_text_contradicts_clinic_policy(patient_text=model_patient_text, policy_key=key)
    )
    effective_keys = tuple(dict.fromkeys((*applicable, *also_detect)))

    if not effective_keys and not contradictions:
        return ClinicPolicyEnforcementResult(
            patient_text=model_patient_text,
            enforced=False,
            applicable_policy_keys=(),
            suppress_forbidden_booking_cta=False,
        )

    composed = compose_clinic_policy_patient_text(
        client_id=client_id,
        user_message=user_message,
        policy_keys=effective_keys or applicable,
        model_patient_text=model_patient_text,
    )
    suppress_booking = "no_pediatric_dentistry" in effective_keys
    return ClinicPolicyEnforcementResult(
        patient_text=composed,
        enforced=True,
        applicable_policy_keys=effective_keys or applicable,
        suppress_forbidden_booking_cta=suppress_booking,
        reason_code="clinic_policy_authority_enforced",
    )


def read_dialog_history_for_policy(sid: str) -> str:
    if not (sid or "").strip():
        return ""
    try:
        from session import mem_get

        return str(mem_get(sid).get("dialog_context") or "")
    except Exception:
        return ""
