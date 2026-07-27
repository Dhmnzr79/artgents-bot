"""Canonical clinic contact facts from clinic_policies.yaml only."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from core.client_config_loader import resolve_pack_client_id

_REPO_ROOT = Path(__file__).resolve().parents[1]


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


def materialize_clinic_contact_primary_evidence(
    client_id: str | None,
    *,
    aspect: str | None = None,
) -> tuple[object, ...]:
    from core.target_composer_request import TargetComposerEvidenceBlock

    facts = load_clinic_contact_facts(client_id)
    if not facts.phone_display:
        return ()
    lines = [f"Телефон: {facts.phone_display}"]
    if facts.whatsapp_display:
        lines.append(f"WhatsApp: {facts.whatsapp_display}")
    if facts.address_display and (aspect in {None, "contacts", "address"}):
        lines.append(f"Адрес: {facts.address_display}")
    if facts.hours_display and (aspect in {None, "contacts", "hours"}):
        lines.append(f"Режим работы: {facts.hours_display}")
    if facts.parking_display and aspect in {None, "contacts", "parking"}:
        lines.append(f"Парковка: {facts.parking_display}")
    text = "\n".join(lines)
    return (
        TargetComposerEvidenceBlock(
            kind="clinic_contact",
            ref="clinic_contact:canonical",
            topics=("clinic",),
            fact_ids=(),
            text=text,
            must_preserve_exact=True,
        ),
    )


def fallback_answer_with_phone(*, base_text: str, client_id: str | None) -> str:
    phone = canonical_contact_phone(client_id)
    if not phone:
        return base_text
    if phone in base_text:
        return base_text
    return f"{base_text.rstrip()} Пожалуйста, позвоните нам: {phone}."
