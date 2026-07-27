#!/usr/bin/env python3
"""Offline client pack validator — strict schema, refs, no network/LLM."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contracts.doctor_schema_refs import (  # noqa: E402
    DoctorCatalogExternalIndex,
    build_doctor_source_refs,
    validate_doctor_catalog_external_refs,
)
from contracts.response_schema_refs import (  # noqa: E402
    ResponseSchemaExternalIndex,
    validate_response_schema_external_refs,
)
from core.doctor_schema_loader import load_doctor_catalog  # noqa: E402
from core.response_schema_kb_index import build_response_schema_kb_refs  # noqa: E402
from core.response_schema_loader import (  # noqa: E402
    DuplicateKeyError,
    ResponseSchemaLoadError,
    load_response_schema_bundle,
)

LEGACY_MIRROR_RELATIVE = (
    "service_catalog.json",
    "marketing.yaml",
    "price_brand_aliases.json",
    "pricebook",
)

_CONTACT_MD_FORBIDDEN = re.compile(
    r"(\+7\s*\(|\+7\s*\d|"
    r"^\s*-\s*(адрес|телефон|whatsapp|время работы|парковка)\s*:)",
    re.IGNORECASE | re.MULTILINE,
)
_FRONTMATTER = re.compile(
    r"\A---[ \t]*\r?\n(?P<yaml>.*?)\r?\n---",
    re.DOTALL,
)
_PRESENTATION_KEYS = (
    "consultation_value",
    "suggest_h3",
    "situation_allowed",
    "video_key",
)


def _resolve_pack_root(client_id: str | None, pack_path: str | None) -> Path:
    if pack_path:
        root = Path(pack_path).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"pack_path_not_found:{root}")
        return root
    if not client_id:
        raise ValueError("client_id_or_pack_path_required")
    root = ROOT / "clients" / client_id
    if not root.is_dir():
        raise FileNotFoundError(f"client_pack_not_found:{root}")
    return root


def validate_client_pack(
    pack_root: Path,
    *,
    scaffold: bool = False,
) -> list[str]:
    errors: list[str] = []
    rel = lambda suffix: pack_root / suffix  # noqa: E731

    if not scaffold:
        for legacy in LEGACY_MIRROR_RELATIVE:
            path = rel(legacy)
            if path.exists():
                errors.append(f"{path.relative_to(pack_root).as_posix()}: legacy_mirror_forbidden")

    md_root = rel("md")
    if not md_root.is_dir():
        errors.append("md/: directory_missing")
    elif not any(md_root.glob("*.md")) and not scaffold:
        errors.append("md/: no_markdown_files")

    target_root = rel("target_response")
    if not target_root.is_dir():
        errors.append("target_response/: directory_missing")
        return errors

    required_target = (
        "service_catalog.json",
        "brand_catalog.json",
        "marketing.yaml",
        "clinic_strategy.yaml",
        "pricebook/facts.json",
    )
    for piece in required_target:
        path = target_root / piece
        if not path.is_file():
            errors.append(f"target_response/{piece}: file_missing")

    services_dir = target_root / "pricebook" / "services"
    if not services_dir.is_dir():
        errors.append("target_response/pricebook/services/: directory_missing")
    elif not list(services_dir.glob("*.json")) and not scaffold:
        errors.append("target_response/pricebook/services/: no_offer_files")

    doctor_path = rel("doctor_catalog.json")
    if not doctor_path.is_file():
        errors.append("doctor_catalog.json: file_missing")

    for operational in ("brand.yaml", "clinic_policies.yaml", "features.yaml", "lead_config.yaml", "tone.yaml", "widget_config.json"):
        if not rel(operational).is_file():
            errors.append(f"{operational}: file_missing")

    if errors:
        return errors

    try:
        bundle = load_response_schema_bundle(target_root)
    except (ResponseSchemaLoadError, DuplicateKeyError, ValueError) as exc:
        errors.append(f"target_response/: schema_load_failed:{exc}")
        return errors

    if not bundle.services:
        errors.append("target_response/service_catalog.json: empty_services")
    for service_id, service in bundle.services.items():
        if service.active is False and not str(service.name or "").strip():
            errors.append(
                f"target_response/service_catalog.json:{service_id}:inactive_service_name_required"
            )
    if not bundle.offers and not scaffold:
        errors.append("target_response/pricebook/services/: empty_offers")

    try:
        doctors = load_doctor_catalog(doctor_path)
    except Exception as exc:
        errors.append(f"doctor_catalog.json: schema_invalid:{exc}")
        return errors

    kb_refs = build_response_schema_kb_refs(md_root) if md_root.is_dir() else frozenset()
    doctor_index = DoctorCatalogExternalIndex(
        service_ids=tuple(bundle.services),
        kb_refs=kb_refs,
    )
    try:
        validate_doctor_catalog_external_refs(doctors, doctor_index)
    except Exception as exc:
        errors.append(f"doctor_catalog.json: external_ref_invalid:{exc}")

    external_index = ResponseSchemaExternalIndex(
        kb_refs=kb_refs,
        doctor_refs=build_doctor_source_refs(doctors),
    )
    try:
        validate_response_schema_external_refs(bundle, external_index)
    except Exception as exc:
        errors.append(f"target_response/: external_ref_invalid:{exc}")

    for scenario_name, rule in bundle.marketing.scenario_rules.items():
        if rule.allowed_topics and not rule.allowed_semantic_contexts:
            errors.append(
                f"target_response/marketing.yaml:{scenario_name}:"
                "allowed_topics_without_semantic_contexts"
            )

    policies_path = rel("clinic_policies.yaml")
    if policies_path.is_file():
        import yaml

        raw = yaml.safe_load(policies_path.read_text(encoding="utf-8")) or {}
        contact = raw.get("contact") if isinstance(raw.get("contact"), dict) else {}
        phone = str(contact.get("phone_display") or "").strip()
        if not phone:
            errors.append("clinic_policies.yaml: contact.phone_display_required")
    contacts_md = md_root / "clinic__info__contacts.md"
    if contacts_md.is_file():
        body = contacts_md.read_text(encoding="utf-8")
        if _CONTACT_MD_FORBIDDEN.search(body):
            errors.append(
                "md/clinic__info__contacts.md: duplicate_contact_facts_forbidden"
            )

    video_keys: set[str] = set()
    video_catalog = rel("video_catalog.yaml")
    if video_catalog.is_file():
        import yaml

        catalog_raw = yaml.safe_load(video_catalog.read_text(encoding="utf-8")) or {}
        videos = catalog_raw.get("videos") if isinstance(catalog_raw, dict) else {}
        if isinstance(videos, dict):
            video_keys = {str(key) for key in videos}

    for md_path in sorted(md_root.glob("*.md")) if md_root.is_dir() else []:
        text = md_path.read_text(encoding="utf-8")
        match = _FRONTMATTER.search(text)
        if not match:
            continue
        import yaml

        meta = yaml.safe_load(match.group("yaml")) or {}
        if not isinstance(meta, dict):
            continue
        rel_path = md_path.relative_to(pack_root).as_posix()
        for key in _PRESENTATION_KEYS:
            if key in meta and meta[key] is not None and meta[key] != "":
                if key == "situation_allowed" and not isinstance(meta[key], bool):
                    errors.append(f"{rel_path}: situation_allowed_invalid")
                if key == "video_key":
                    video_key = str(meta[key]).strip()
                    if video_keys and video_key not in video_keys:
                        errors.append(f"{rel_path}: video_key_missing_in_catalog")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate canonical client pack (offline).")
    parser.add_argument("--client-id", dest="client_id", default=None)
    parser.add_argument("--path", dest="pack_path", default=None)
    parser.add_argument(
        "--scaffold",
        action="store_true",
        help="Allow placeholder template packs with minimal offers.",
    )
    args = parser.parse_args(argv)

    try:
        pack_root = _resolve_pack_root(args.client_id, args.pack_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    errors = validate_client_pack(pack_root, scaffold=args.scaffold)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        print(f"\n{len(errors)} validation error(s)", file=sys.stderr)
        return 1

    label = pack_root.name
    print(f"OK: client pack valid ({label})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
