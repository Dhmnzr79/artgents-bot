"""Capture a clinic pack once and derive deterministic D2 model data from it."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

from contracts.d2_tenant_snapshot import (
    D2CommercialPack,
    D2DirectionPriceConfig,
    D2DirectionPricePack,
    D2ModelView,
    D2TenantSnapshot,
)
from contracts.response_schema import ResponseSchemaBundle
from contracts.response_plan_materialization import D2AuthoredContentAuthority, D2AuthoredContentSection
from core.d2_published_offer_terms import build_d2_published_offer_terms
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.response_schema_loader import ResponseSchemaLoadError, load_response_schema_bundle_from_texts
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot


class D2TenantSnapshotError(ValueError):
    pass


_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+\{#([^}]+)\})?\s*$")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_REQUIRED_TARGET = (
    "service_catalog.json", "brand_catalog.json", "clinic_strategy.yaml", "marketing.yaml",
    "pricebook/facts.json",
)


def _safe_client_root(clients_root: Path, client_id: str) -> Path:
    if not client_id or client_id != client_id.strip() or "/" in client_id or "\\" in client_id or ".." in client_id:
        raise D2TenantSnapshotError("client_id_invalid")
    root = clients_root.resolve()
    client = (root / client_id).resolve()
    if client.parent != root or not client.is_dir():
        raise D2TenantSnapshotError("tenant_not_found")
    return client


def _read_set(client_root: Path) -> tuple[tuple[str, bytes], ...]:
    target = client_root / "target_response"
    required_paths = [target / item for item in _REQUIRED_TARGET]
    required_paths.append(target / "pricebook" / "services")
    for path in required_paths:
        if not path.exists():
            raise D2TenantSnapshotError(f"required_path_missing:{path.name}")
    files: list[Path] = []
    for base, pattern in ((target, "*.json"), (target, "*.yaml"), (client_root / "md", "*.md")):
        if not base.is_dir():
            if base.name == "md":
                raise D2TenantSnapshotError("required_path_missing:md")
            continue
        files.extend(item for item in base.rglob(pattern) if item.is_file())
    for name in ("tone.yaml", "ui.yaml", "video_catalog.yaml", "doctor_catalog.json"):
        path = client_root / name
        if path.is_file():
            files.append(path)
    root = client_root.resolve()
    captured: list[tuple[str, bytes]] = []
    for path in sorted(set(files)):
        resolved = path.resolve()
        if root not in resolved.parents:
            raise D2TenantSnapshotError("tenant_path_escape")
        captured.append((path.relative_to(root).as_posix(), path.read_bytes()))
    return tuple(captured)


def _fingerprint(client_id: str, files: tuple[tuple[str, bytes], ...]) -> str:
    digest = hashlib.sha256()
    digest.update(b"d2-snapshot-v1\0" + client_id.encode() + b"\0")
    for path, body in files:
        digest.update(path.encode() + b"\0" + body + b"\0")
    return digest.hexdigest()


def _split_markdown(text: str) -> tuple[dict[str, object], str, tuple[D2AuthoredContentSection, ...], tuple[str, ...]]:
    metadata: dict[str, object] = {}
    match = _FRONTMATTER.match(text)
    body = text
    if match:
        raw = yaml.safe_load(match.group(1))
        metadata = raw if isinstance(raw, dict) else {}
        body = text[match.end():]
    clean = _COMMENT.sub("", body).strip()
    lines = clean.splitlines()
    headings: list[tuple[int, int, str | None]] = []
    in_fence = False
    for index, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        found = _HEADING.match(line)
        if found:
            headings.append((index, len(found.group(1)), found.group(3)))
    sections: list[D2AuthoredContentSection] = []
    diagnostics: list[str] = []
    used: set[str] = set()
    for ordinal, (start, level, explicit) in enumerate(headings, start=1):
        end = len(lines)
        for next_start, next_level, _ in headings[ordinal:]:
            if next_level <= level:
                end = next_start
                break
        section_text = "\n".join(lines[start:end]).strip()
        if not section_text:
            continue
        ref = f"a:{explicit}" if explicit else f"h:{ordinal}"
        if ref in used:
            diagnostics.append(f"duplicate_section_ref:{ref}")
            continue
        used.add(ref)
        sections.append(D2AuthoredContentSection(section_ref=ref, display_text=section_text))
    if not clean:
        diagnostics.append("content_empty")
    return metadata, clean, tuple(sections), tuple(diagnostics)


def load_d2_tenant_snapshot(client_id: str, *, clients_root: Path) -> D2TenantSnapshot:
    client_root = _safe_client_root(clients_root, client_id)
    first = _read_set(client_root)
    second = _read_set(client_root)
    if first != second:
        raise D2TenantSnapshotError("tenant_pack_changed_during_capture")
    texts = {path.removeprefix("target_response/"): data.decode("utf-8") for path, data in first if path.startswith("target_response/")}
    try:
        bundle = load_response_schema_bundle_from_texts(texts)
    except (UnicodeDecodeError, ResponseSchemaLoadError) as exc:
        raise D2TenantSnapshotError(f"schema_load_failed:{exc}") from exc
    _direction_prices(first, bundle)
    _commercial_contract(first, bundle, client_id)
    parsed_content: list[tuple[str, dict[str, object], str, tuple[D2AuthoredContentSection, ...]]] = []
    diagnostics: list[str] = []
    for path, data in first:
        if not path.startswith("md/"):
            continue
        metadata, body, sections, notes = _split_markdown(data.decode("utf-8"))
        diagnostics.extend(f"{path}:{note}" for note in notes)
        if not body:
            continue
        ref = Path(path).name
        parsed_content.append((ref, metadata, body, sections))
    metadata_by_ref = {ref: metadata for ref, metadata, _, _ in parsed_content}
    service_topics = {
        service_id: metadata_by_ref.get(service.content_ref, {}).get("topic")
        for service_id, service in bundle.services.items()
    }
    content: list[D2AuthoredContentAuthority] = []
    for ref, metadata, body, sections in parsed_content:
        direct = tuple(sorted(service_id for service_id, service in bundle.services.items() if service.content_ref == ref))
        topic = metadata.get("topic")
        # Topic FAQ documents receive only the exact services whose own
        # published service document declares that same topic.  An empty list
        # remains no relation, never an implicit wildcard.
        topical = tuple(sorted(service_id for service_id, service_topic in service_topics.items() if isinstance(topic, str) and service_topic == topic))
        content.append(D2AuthoredContentAuthority(
            source_client_id=client_id,
            content_ref=ref,
            display_text=body,
            allowed_service_ids=direct or topical,
            sections=sections,
        ))
    return D2TenantSnapshot(client_id=client_id, fingerprint=_fingerprint(client_id, first), bundle=bundle, files=first, content=tuple(content), diagnostics=tuple(diagnostics))


def build_d2_bundle(snapshot: D2TenantSnapshot):
    """Return a fresh validated bundle from captured bytes, never from the filesystem."""
    texts = {
        path.removeprefix("target_response/"): data.decode("utf-8")
        for path, data in snapshot.files
        if path.startswith("target_response/")
    }
    try:
        return load_response_schema_bundle_from_texts(texts)
    except (UnicodeDecodeError, ResponseSchemaLoadError) as exc:
        raise D2TenantSnapshotError(f"snapshot_bundle_invalid:{exc}") from exc


def build_d2_model_view(snapshot: D2TenantSnapshot) -> D2ModelView:
    bundle = build_d2_bundle(snapshot)
    return D2ModelView(
        client_id=snapshot.client_id,
        fingerprint=snapshot.fingerprint,
        active_service_catalog=ActiveServiceCatalogSnapshot.from_bundle(bundle),
        service_reference_catalog=ServiceReferenceCatalogSnapshot.from_bundle(bundle),
        commercial_fact_catalog=CommercialFactCatalogSnapshot.from_bundle(bundle),
        content=snapshot.content,
        published_terms=tuple(build_d2_published_offer_terms(offer=offer, source_client_id=snapshot.client_id) for offer in bundle.offers),
        direction_prices=_direction_prices(snapshot.files, bundle),
        commercial=_commercial_contract(snapshot.files, bundle, snapshot.client_id),
    )


def _direction_prices(
    files: tuple[tuple[str, bytes], ...], bundle: ResponseSchemaBundle,
) -> tuple[D2DirectionPriceConfig, ...]:
    raw = dict(files).get("target_response/d2_direction_prices.json")
    if raw is None:
        return ()
    try:
        pack = D2DirectionPricePack.model_validate_json(raw)
    except ValueError as exc:
        raise D2TenantSnapshotError("direction_price_config_invalid") from exc
    offers = {offer.offer_id: offer for offer in bundle.offers}
    for direction in pack.directions:
        for service_id in direction.service_ids:
            service = bundle.services.get(service_id)
            if service is None or not service.active:
                raise D2TenantSnapshotError("direction_price_service_unavailable")
        for offer_id in direction.offer_ids:
            offer = offers.get(offer_id)
            if offer is None or not offer.active or offer.service_id not in direction.service_ids:
                raise D2TenantSnapshotError("direction_price_offer_unavailable")
            service = bundle.services[offer.service_id]
            if offer.option_id is not None and not any(
                option.option_id == offer.option_id and option.active for option in service.options
            ):
                raise D2TenantSnapshotError("direction_price_option_unavailable")
        if {offers[ref].service_id for ref in direction.offer_ids} != set(direction.service_ids):
            raise D2TenantSnapshotError("direction_price_service_without_offer")
    return pack.directions


_COMMERCIAL_CODES = (
    "commercial_blank",
    "commercial_package_not_single",
    "commercial_promo_ref_cap",
    "commercial_promo_ref_duplicate",
    "commercial_promo_fact_duplicate",
    "commercial_package_duplicate",
    "commercial_profile_duplicate",
    "commercial_incompatibility_duplicate",
    "commercial_incompatibility_too_small",
    "commercial_incompatibility_duplicate_ref",
)


def _commercial_error_code(exc: Exception) -> str:
    text = str(exc)
    for code in _COMMERCIAL_CODES:
        if code in text:
            return code
    return "commercial_config_invalid"


def _commercial_texts(*values: str) -> tuple[str, ...]:
    return tuple(" ".join(value.split()) for value in values)


def _commercial_contract(
    files: tuple[tuple[str, bytes], ...], bundle: ResponseSchemaBundle, client_id: str,
) -> D2CommercialPack:
    raw = dict(files).get("target_response/d2_commercial.json")
    if raw is None:
        return D2CommercialPack(version=1)
    try:
        pack = D2CommercialPack.model_validate_json(raw)
    except ValueError as exc:
        raise D2TenantSnapshotError(_commercial_error_code(exc)) from exc
    if pack.client_id is not None and pack.client_id != client_id:
        raise D2TenantSnapshotError("commercial_tenant_mismatch")
    promos = {item.fact_id: item for item in pack.promo_facts}
    for promo in pack.promo_facts:
        fact = bundle.facts.get(promo.fact_id)
        if fact is None or not fact.active:
            raise D2TenantSnapshotError("commercial_fact_unavailable")
        if fact.kind != "promo":
            raise D2TenantSnapshotError("commercial_promo_kind_invalid")
        if fact.microfact_text is None:
            raise D2TenantSnapshotError("commercial_promo_short_missing")
        if promo.short_text != fact.microfact_text or promo.full_text != fact.text_fact:
            raise D2TenantSnapshotError("commercial_promo_forms_conflict")
    boosters = {item.package_id: item for item in pack.price_booster_packages}
    also_lists = {item.package_id: item for item in pack.also_list_packages}
    for profile in pack.service_profiles:
        service = bundle.services.get(profile.service_id)
        if service is None or not service.active:
            raise D2TenantSnapshotError("commercial_service_unavailable")
        owned: list[str] = []
        for fact_id in profile.promo_refs:
            promo = promos.get(fact_id)
            fact = bundle.facts.get(fact_id)
            if promo is None:
                raise D2TenantSnapshotError("commercial_promo_forms_missing")
            if fact is None or profile.service_id not in fact.allowed_service_ids or profile.service_id in fact.excluded_service_ids:
                raise D2TenantSnapshotError("commercial_promo_inapplicable")
            owned.extend(_commercial_texts(promo.short_text, promo.full_text))
        if profile.price_booster_id is not None:
            package = boosters.get(profile.price_booster_id)
            if package is None:
                raise D2TenantSnapshotError("commercial_package_unavailable")
            owned.append(_commercial_texts(package.body_text)[0])
        if profile.also_list_id is not None:
            package = also_lists.get(profile.also_list_id)
            if package is None:
                raise D2TenantSnapshotError("commercial_package_unavailable")
            owned.append(_commercial_texts(package.body_text)[0])
        if len(owned) != len(set(owned)):
            raise D2TenantSnapshotError("commercial_meaning_duplicate")
    offers = {offer.offer_id for offer in bundle.offers}
    for group in pack.incompatibility_groups:
        for ref in group.offer_or_fact_ids:
            fact = bundle.facts.get(ref)
            if ref not in offers and (fact is None or not fact.active):
                raise D2TenantSnapshotError("commercial_incompatibility_ref_unavailable")
    return pack
