"""Pure parse/validate for clinic_policies.yaml contact section (path-agnostic)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_BRANCH_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_LEGACY_LOCATION_SCALAR_KEYS = ("phone_display", "address_display", "hours_display", "parking_display")
_CONTACT_FIELD_NAMES = frozenset({"phone", "whatsapp", "address", "hours", "parking"})


@dataclass(frozen=True, slots=True)
class ClinicContactBranch:
    branch_id: str
    label: str
    aliases: tuple[str, ...]
    address_display: str
    phone_displays: tuple[str, ...]
    hours_display: str
    parking_display: str | None = None


@dataclass(frozen=True, slots=True)
class ClinicContactFacts:
    phone_display: str
    whatsapp_display: str | None
    address_display: str | None
    hours_display: str | None
    parking_display: str | None
    branches: tuple[ClinicContactBranch, ...] = ()


def _normalize_branch_hint(text: str) -> str:
    return (text or "").strip().lower().replace("ё", "е")


def _normalize_alias_token(text: str) -> str:
    return " ".join(_normalize_branch_hint(text).split())


def _normalize_phone_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


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


def _parse_phone_displays(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    phones = [str(item or "").strip() for item in raw]
    return tuple(phone for phone in phones if phone)


def _parse_aliases(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    aliases = [str(item or "").strip() for item in raw]
    return tuple(alias for alias in aliases if alias)


def _parse_branch_row(raw: object) -> ClinicContactBranch | None:
    if not isinstance(raw, dict):
        return None
    branch_id = str(raw.get("branch_id") or "").strip()
    if not branch_id or _BRANCH_ID_PATTERN.fullmatch(branch_id) is None:
        return None
    label = str(raw.get("label") or "").strip()
    address_display = str(raw.get("address_display") or "").strip()
    hours_display = str(raw.get("hours_display") or "").strip()
    phone_displays = _parse_phone_displays(raw.get("phone_displays"))
    if not label or not address_display or not hours_display or not phone_displays:
        return None
    parking_raw = str(raw.get("parking_display") or "").strip()
    return ClinicContactBranch(
        branch_id=branch_id,
        label=label,
        aliases=_parse_aliases(raw.get("aliases")),
        address_display=address_display,
        phone_displays=phone_displays,
        hours_display=hours_display,
        parking_display=parking_raw or None,
    )


def branch_selection_tokens(branch: ClinicContactBranch) -> tuple[str, ...]:
    tokens: list[str] = []
    seen: set[str] = set()
    for raw in (branch.branch_id.replace("_", " "), branch.label, *branch.aliases):
        token = _normalize_alias_token(raw)
        if not token or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tuple(tokens)


def selection_token_matches_hint(hint: str, token: str) -> bool:
    normalized_hint = _normalize_branch_hint(hint)
    normalized_token = _normalize_alias_token(token)
    if not normalized_token:
        return False
    escaped = re.escape(normalized_token).replace(r"\ ", r"\s+")
    pattern = rf"(?<!\w){escaped}(?!\w)"
    return re.search(pattern, normalized_hint, flags=re.UNICODE) is not None


def parse_clinic_contact_facts_from_policies_raw(raw: object) -> ClinicContactFacts:
    if not isinstance(raw, dict):
        raw = {}
    contact = raw.get("contact") if isinstance(raw.get("contact"), dict) else {}
    hours_raw = raw.get("hours") if isinstance(raw.get("hours"), dict) else {}
    weekly = hours_raw.get("weekly") if isinstance(hours_raw.get("weekly"), dict) else {}
    whatsapp_display = str(contact.get("whatsapp_display") or "").strip() or None
    parking_display = str(contact.get("parking_display") or "").strip() or None

    branches_raw = contact.get("branches")
    branches: tuple[ClinicContactBranch, ...] = ()
    if isinstance(branches_raw, list):
        parsed: list[ClinicContactBranch] = []
        for row in branches_raw:
            branch = _parse_branch_row(row)
            if branch is not None:
                parsed.append(branch)
        branches = tuple(parsed)

    if branches:
        return ClinicContactFacts(
            phone_display="",
            whatsapp_display=whatsapp_display,
            address_display=None,
            hours_display=None,
            parking_display=None,
            branches=branches,
        )

    hours_display = str(contact.get("hours_display") or "").strip() or _format_hours(weekly)
    return ClinicContactFacts(
        phone_display=str(contact.get("phone_display") or "").strip(),
        whatsapp_display=whatsapp_display,
        address_display=str(contact.get("address_display") or "").strip() or None,
        hours_display=hours_display,
        parking_display=parking_display,
    )


def load_clinic_contact_facts_from_policies_path(path: Path) -> ClinicContactFacts:
    if not path.is_file():
        return ClinicContactFacts(
            phone_display="",
            whatsapp_display=None,
            address_display=None,
            hours_display=None,
            parking_display=None,
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return parse_clinic_contact_facts_from_policies_raw(raw)


def validate_clinic_contact_section(
    contact: object,
    *,
    prefix: str = "clinic_policies.yaml: contact",
) -> list[str]:
    errors: list[str] = []
    if not isinstance(contact, dict):
        return [f"{prefix}: contact_section_invalid"]

    branches_raw = contact.get("branches")
    has_branches = isinstance(branches_raw, list) and len(branches_raw) > 0

    if branches_raw is not None and not isinstance(branches_raw, list):
        return [f"{prefix}: branches_invalid_type"]

    for scalar_key in _LEGACY_LOCATION_SCALAR_KEYS:
        if has_branches and str(contact.get(scalar_key) or "").strip():
            errors.append(f"{prefix}.{scalar_key}_forbidden_with_branches")

    branch_ids: set[str] = set()
    token_owner: dict[str, str] = {}

    if has_branches:
        for idx, row in enumerate(branches_raw):
            row_prefix = f"{prefix}.branches[{idx}]"
            if not isinstance(row, dict):
                errors.append(f"{row_prefix}:invalid_branch_row")
                continue
            branch_id = str(row.get("branch_id") or "").strip()
            if not branch_id or _BRANCH_ID_PATTERN.fullmatch(branch_id) is None:
                errors.append(f"{row_prefix}:branch_id_invalid")
            elif branch_id in branch_ids:
                errors.append(f"{row_prefix}:branch_id_duplicate")
            else:
                branch_ids.add(branch_id)

            label = str(row.get("label") or "").strip()
            address = str(row.get("address_display") or "").strip()
            hours = str(row.get("hours_display") or "").strip()
            phones_raw = row.get("phone_displays")
            if not isinstance(phones_raw, list):
                phones: list[str] = []
            else:
                phones = [str(p).strip() for p in phones_raw if str(p).strip()]
            if not label:
                errors.append(f"{row_prefix}:label_required")
            if not address:
                errors.append(f"{row_prefix}:address_display_required")
            if not hours:
                errors.append(f"{row_prefix}:hours_display_required")
            if not phones:
                errors.append(f"{row_prefix}:phone_displays_required")

            aliases_raw = row.get("aliases")
            if aliases_raw is not None and not isinstance(aliases_raw, list):
                errors.append(f"{row_prefix}:aliases_invalid_type")

            branch = _parse_branch_row(row)
            if branch is not None:
                for token in branch_selection_tokens(branch):
                    owner = token_owner.get(token)
                    if owner is not None and owner != branch.branch_id:
                        errors.append(f"{row_prefix}:selection_token_duplicate")
                    else:
                        token_owner[token] = branch.branch_id

    facts = parse_clinic_contact_facts_from_policies_raw({"contact": contact})
    if not facts.branches and not facts.phone_display.strip():
        errors.append(f"{prefix}: phone_display_required")
    if facts.branches and not any(branch.phone_displays for branch in facts.branches):
        errors.append(f"{prefix}: branch_phone_required")

    return errors


def resolve_contact_branch_id_from_facts(
    facts: ClinicContactFacts,
    hint: str,
) -> str | None:
    if not facts.branches:
        return None
    normalized_hint = _normalize_branch_hint(hint)
    if not normalized_hint:
        return None
    matched_ids: list[str] = []
    for branch in facts.branches:
        for token in branch_selection_tokens(branch):
            if selection_token_matches_hint(normalized_hint, token):
                matched_ids.append(branch.branch_id)
                break
    unique_ids = sorted(set(matched_ids))
    if len(unique_ids) == 1:
        return unique_ids[0]
    return None


def branch_by_id(
    facts: ClinicContactFacts,
    branch_id: str | None,
) -> ClinicContactBranch | None:
    if branch_id is None:
        return None
    for branch in facts.branches:
        if branch.branch_id == branch_id:
            return branch
    return None


def collect_manual_contact_phone_lines(
    facts: ClinicContactFacts,
    *,
    branch_hint: str | None = None,
    max_phones: int = 2,
) -> tuple[tuple[str, str], ...]:
    if not facts.branches:
        if facts.phone_display:
            return (("Клиника", facts.phone_display),)
        return ()

    selected_id = resolve_contact_branch_id_from_facts(facts, branch_hint or "")
    ordered_branches: list[ClinicContactBranch] = []
    if selected_id is not None:
        branch = branch_by_id(facts, selected_id)
        if branch is not None:
            ordered_branches = [branch]
    else:
        ordered_branches = list(facts.branches)

    lines: list[tuple[str, str]] = []
    seen_digits: set[str] = set()
    for branch in ordered_branches:
        for phone in branch.phone_displays:
            digits = _normalize_phone_digits(phone)
            if not digits or digits in seen_digits:
                continue
            seen_digits.add(digits)
            lines.append((branch.label, phone))
            if len(lines) >= max_phones:
                return tuple(lines)
    return tuple(lines)


def format_manual_contact_phone_suffix(
    facts: ClinicContactFacts,
    *,
    branch_hint: str | None = None,
) -> str:
    if not facts.branches:
        if facts.phone_display:
            return f" по номеру {facts.phone_display}"
        return ""
    phone_lines = collect_manual_contact_phone_lines(facts, branch_hint=branch_hint)
    if not phone_lines:
        return ""
    body = "\n".join(f"- {label}: {phone}" for label, phone in phone_lines)
    return f"\n{body}"
