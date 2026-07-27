"""Canonical clinic contact facts from clinic_policies.yaml only."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from core.client_config_loader import resolve_pack_client_id

_REPO_ROOT = Path(__file__).resolve().parents[1]

ContactFieldKind = Literal[
    "phone",
    "whatsapp",
    "address",
    "hours",
    "parking",
]

_CONTACT_ASPECT_TO_FIELD: dict[str, ContactFieldKind] = {
    "contact_phone": "phone",
    "contact_address": "address",
    "contact_parking": "parking",
    "contact_hours": "hours",
    "contact_whatsapp": "whatsapp",
}

_GENERAL_CONTACT_FIELDS: tuple[ContactFieldKind, ...] = (
    "phone",
    "whatsapp",
    "address",
    "hours",
    "parking",
)


@dataclass(frozen=True, slots=True)
class ClinicContactFacts:
    phone_display: str
    whatsapp_display: str | None
    address_display: str | None
    hours_display: str | None
    parking_display: str | None


def _policies_path(client_id: str | None) -> Path:
    pack = resolve_pack_client_id(client_id)
    return _REPO_ROOT / "clients" / pack / "clinic_policies.yaml"


def _format_hours(weekly: dict[str, Any]) -> str | None:
    labels = {
        "mon": "Пн",
        "tue": "Вт",
        "wed": "Ср",
        "thu": "Чт",
        "fri": "Пт",
        "sat": "Сб",
        "sun": "Вс",
    }
    parts: list[str] = []
    for key, label in labels.items():
        slot = weekly.get(key)
        if not isinstance(slot, dict):
            continue
        start = str(slot.get("start") or slot.get("open") or "").strip()
        end = str(slot.get("end") or slot.get("close") or "").strip()
        if not start or not end:
            continue
        if slot.get("closed") is True:
            parts.append(f"{label} — выходной")
        else:
            parts.append(f"{label} {start}–{end}")
    return "; ".join(parts) if parts else None


def load_clinic_contact_facts(client_id: str | None) -> ClinicContactFacts:
    path = _policies_path(client_id)
    if not path.is_file():
        return ClinicContactFacts(
            phone_display="",
            whatsapp_display=None,
            address_display=None,
            hours_display=None,
            parking_display=None,
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    contact = raw.get("contact") if isinstance(raw.get("contact"), dict) else {}
    hours_raw = raw.get("hours") if isinstance(raw.get("hours"), dict) else {}
    weekly = hours_raw.get("weekly") if isinstance(hours_raw.get("weekly"), dict) else {}
    hours_display = str(contact.get("hours_display") or "").strip() or _format_hours(weekly)
    return ClinicContactFacts(
        phone_display=str(contact.get("phone_display") or "").strip(),
        whatsapp_display=str(contact.get("whatsapp_display") or "").strip() or None,
        address_display=str(contact.get("address_display") or "").strip() or None,
        hours_display=hours_display,
        parking_display=str(contact.get("parking_display") or "").strip() or None,
    )


def canonical_contact_phone(client_id: str | None) -> str:
    return load_clinic_contact_facts(client_id).phone_display


def contact_fields_from_turn_aspects(
    aspects: tuple[str, ...],
    *,
    primary_aspect: str | None,
) -> tuple[ContactFieldKind, ...] | None:
    """Map planner-owned contact aspects to canonical contact fields."""

    ordered: list[ContactFieldKind] = []
    seen: set[ContactFieldKind] = set()
    candidates = tuple(aspects) + ((primary_aspect,) if primary_aspect else ())
    for aspect in candidates:
        if aspect == "contacts":
            return _GENERAL_CONTACT_FIELDS
        field = _CONTACT_ASPECT_TO_FIELD.get(aspect)
        if field is None:
            continue
        if field not in seen:
            seen.add(field)
            ordered.append(field)
    if not ordered:
        return None
    return tuple(ordered)


def _field_line(field: ContactFieldKind, facts: ClinicContactFacts) -> str | None:
    if field == "phone" and facts.phone_display:
        return f"Телефон: {facts.phone_display}"
    if field == "whatsapp" and facts.whatsapp_display:
        return f"WhatsApp: {facts.whatsapp_display}"
    if field == "address" and facts.address_display:
        return f"Адрес: {facts.address_display}"
    if field == "hours" and facts.hours_display:
        return f"Режим работы: {facts.hours_display}"
    if field == "parking" and facts.parking_display:
        return f"Парковка: {facts.parking_display}"
    return None


def materialize_clinic_contact_primary_evidence(
    client_id: str | None,
    *,
    fields: tuple[ContactFieldKind, ...] | None = None,
    aspect: str | None = None,
) -> tuple[object, ...]:
    from core.target_composer_request import TargetComposerEvidenceBlock

    if fields is None and aspect is not None:
        if aspect == "contacts":
            fields = _GENERAL_CONTACT_FIELDS
        elif aspect in _CONTACT_ASPECT_TO_FIELD:
            fields = (_CONTACT_ASPECT_TO_FIELD[aspect],)
        else:
            fields = ()

    facts = load_clinic_contact_facts(client_id)
    if not facts.phone_display and fields is None:
        return ()

    resolved_fields = fields or _GENERAL_CONTACT_FIELDS
    blocks: list[TargetComposerEvidenceBlock] = []
    for field in resolved_fields:
        line = _field_line(field, facts)
        if not line:
            continue
        blocks.append(
            TargetComposerEvidenceBlock(
                kind="clinic_contact",
                ref=f"clinic_contact:{field}",
                topics=("clinic",),
                fact_ids=(),
                text=line,
                must_preserve_exact=True,
            )
        )
    return tuple(blocks)


def fallback_answer_with_phone(*, base_text: str, client_id: str | None) -> str:
    phone = canonical_contact_phone(client_id)
    if not phone:
        return base_text
    if phone in base_text:
        return base_text
    return f"{base_text.rstrip()} Пожалуйста, позвоните нам: {phone}."
