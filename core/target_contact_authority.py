"""Canonical clinic contact facts from clinic_policies.yaml only."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from core.client_config_loader import resolve_pack_client_id
from core.clinic_contact_policies import (
    ClinicContactBranch,
    ClinicContactFacts,
    branch_by_id,
    branch_selection_tokens,
    collect_manual_contact_phone_lines,
    format_manual_contact_phone_suffix,
    load_clinic_contact_facts_from_policies_path,
    parse_clinic_contact_facts_from_policies_raw,
    resolve_contact_branch_id_from_facts,
    selection_token_matches_hint,
    validate_clinic_contact_section,
)

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


def _policies_path(client_id: str | None) -> Path:
    pack = resolve_pack_client_id(client_id)
    return _REPO_ROOT / "clients" / pack / "clinic_policies.yaml"


def load_clinic_contact_facts(client_id: str | None) -> ClinicContactFacts:
    return load_clinic_contact_facts_from_policies_path(_policies_path(client_id))


def canonical_contact_phone(client_id: str | None) -> str:
    facts = load_clinic_contact_facts(client_id)
    if facts.branches:
        lines = collect_manual_contact_phone_lines(facts)
        if not lines:
            return ""
        return "; ".join(f"{label}: {phone}" for label, phone in lines)
    return facts.phone_display


def format_manual_contact_phone_suffix_for_client(
    client_id: str | None,
    *,
    branch_hint: str | None = None,
) -> str:
    return format_manual_contact_phone_suffix(
        load_clinic_contact_facts(client_id),
        branch_hint=branch_hint,
    )


def resolve_contact_branch_id(
    client_id: str | None,
    hint: str,
) -> str | None:
    return resolve_contact_branch_id_from_facts(load_clinic_contact_facts(client_id), hint)


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


def _branch_field_value(
    branch: ClinicContactBranch,
    field: ContactFieldKind,
) -> str | None:
    if field == "phone":
        return ", ".join(branch.phone_displays)
    if field == "address":
        return branch.address_display
    if field == "hours":
        return branch.hours_display
    if field == "parking":
        return branch.parking_display
    return None


def _legacy_field_value(facts: ClinicContactFacts, field: ContactFieldKind) -> str | None:
    if field == "phone" and facts.phone_display:
        return facts.phone_display
    if field == "whatsapp" and facts.whatsapp_display:
        return facts.whatsapp_display
    if field == "address" and facts.address_display:
        return facts.address_display
    if field == "hours" and facts.hours_display:
        return facts.hours_display
    if field == "parking" and facts.parking_display:
        return facts.parking_display
    return None


def _field_label(field: ContactFieldKind) -> str:
    labels = {
        "phone": "Телефон",
        "whatsapp": "WhatsApp",
        "address": "Адрес",
        "hours": "Режим работы",
        "parking": "Парковка",
    }
    return labels[field]


def _field_line(
    field: ContactFieldKind,
    facts: ClinicContactFacts,
    *,
    branch: ClinicContactBranch | None = None,
) -> str | None:
    if branch is not None:
        value = _branch_field_value(branch, field)
        if not value:
            return None
        return f"{branch.label}: {_field_label(field)}: {value}"
    value = _legacy_field_value(facts, field)
    if not value:
        return None
    return f"{_field_label(field)}: {value}"


def _contact_evidence_ref(
    field: ContactFieldKind,
    *,
    branch_id: str | None = None,
) -> str:
    if branch_id:
        return f"clinic_contact:branch:{branch_id}:{field}"
    return f"clinic_contact:{field}"


def materialize_clinic_contact_primary_evidence(
    client_id: str | None,
    *,
    fields: tuple[ContactFieldKind, ...] | None = None,
    aspect: str | None = None,
    branch_hint_text: str | None = None,
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
    if not facts.phone_display and not facts.branches and fields is None:
        return ()

    resolved_fields = fields or _GENERAL_CONTACT_FIELDS
    branch_id = resolve_contact_branch_id(client_id, branch_hint_text or "")
    blocks: list[TargetComposerEvidenceBlock] = []

    if facts.branches:
        selected_branches = facts.branches
        if branch_id is not None:
            branch = branch_by_id(facts, branch_id)
            selected_branches = (branch,) if branch is not None else facts.branches
        branch_fields = tuple(field for field in resolved_fields if field != "whatsapp")
        for branch in selected_branches:
            for field in branch_fields:
                if field == "parking" and branch.parking_display is None:
                    continue
                line = _field_line(field, facts, branch=branch)
                if not line:
                    continue
                blocks.append(
                    TargetComposerEvidenceBlock(
                        kind="clinic_contact",
                        ref=_contact_evidence_ref(field, branch_id=branch.branch_id),
                        topics=("clinic",),
                        fact_ids=(),
                        text=line,
                        must_preserve_exact=True,
                    )
                )
        if "whatsapp" in resolved_fields and facts.whatsapp_display:
            blocks.append(
                TargetComposerEvidenceBlock(
                    kind="clinic_contact",
                    ref=_contact_evidence_ref("whatsapp"),
                    topics=("clinic",),
                    fact_ids=(),
                    text=f"{_field_label('whatsapp')}: {facts.whatsapp_display}",
                    must_preserve_exact=True,
                )
            )
        return tuple(blocks)

    for field in resolved_fields:
        line = _field_line(field, facts)
        if not line:
            continue
        blocks.append(
            TargetComposerEvidenceBlock(
                kind="clinic_contact",
                ref=_contact_evidence_ref(field),
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


def parse_contact_evidence_ref(ref: str) -> tuple[ContactFieldKind | None, str | None]:
    if ref.startswith("clinic_contact:branch:"):
        suffix = ref.removeprefix("clinic_contact:branch:")
        branch_id, sep, field_name = suffix.rpartition(":")
        if not sep or field_name not in {
            "phone",
            "whatsapp",
            "address",
            "hours",
            "parking",
        }:
            return None, None
        return field_name, branch_id  # type: ignore[return-value]
    field = contact_field_from_evidence_ref(ref)
    return field, None


def contact_field_from_evidence_ref(ref: str) -> ContactFieldKind | None:
    if not ref.startswith("clinic_contact:"):
        return None
    if ref.startswith("clinic_contact:branch:"):
        suffix = ref.removeprefix("clinic_contact:branch:")
        field_name = suffix.rpartition(":")[2]
    else:
        field_name = ref.removeprefix("clinic_contact:")
    if field_name in {
        "phone",
        "whatsapp",
        "address",
        "hours",
        "parking",
    }:
        return field_name  # type: ignore[return-value]
    return None


def canonical_contact_scalar(
    field: ContactFieldKind,
    client_id: str | None,
    *,
    branch_id: str | None = None,
) -> str | None:
    facts = load_clinic_contact_facts(client_id)
    if facts.branches:
        if field == "whatsapp":
            return facts.whatsapp_display
        if branch_id is not None:
            branch = branch_by_id(facts, branch_id)
            if branch is None:
                return None
            return _branch_field_value(branch, field)
        if field == "phone":
            return canonical_contact_phone(client_id) or None
        return None
    return _legacy_field_value(facts, field)


def normalize_contact_scalar(text: str) -> str:
    import unicodedata

    return " ".join(unicodedata.normalize("NFC", text).split())


__all__ = [
    "ClinicContactBranch",
    "ClinicContactFacts",
    "ContactFieldKind",
    "branch_selection_tokens",
    "canonical_contact_phone",
    "canonical_contact_scalar",
    "collect_manual_contact_phone_lines",
    "contact_field_from_evidence_ref",
    "contact_fields_from_turn_aspects",
    "format_manual_contact_phone_suffix",
    "format_manual_contact_phone_suffix_for_client",
    "load_clinic_contact_facts",
    "load_clinic_contact_facts_from_policies_path",
    "materialize_clinic_contact_primary_evidence",
    "normalize_contact_scalar",
    "parse_clinic_contact_facts_from_policies_raw",
    "parse_contact_evidence_ref",
    "resolve_contact_branch_id",
    "resolve_contact_branch_id_from_facts",
    "selection_token_matches_hint",
    "validate_clinic_contact_section",
]
