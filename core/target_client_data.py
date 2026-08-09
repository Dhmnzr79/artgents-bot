"""Canonical cached loader for clients/{id}/target_response product readers."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import PRICE_SERVICE_MATCH_STRONG
from contracts.doctor_schema import TargetDoctorCatalog
from contracts.doctor_schema_refs import (
    DoctorCatalogExternalIndex,
    build_doctor_source_refs,
    validate_doctor_catalog_external_refs,
)
from contracts.response_schema import ResponseSchemaBundle, TargetService
from contracts.response_schema_refs import (
    ResponseSchemaExternalIndex,
    validate_response_schema_external_refs,
)
from core.catalog_match import resolve_catalog_match
from core.client_config_loader import resolve_pack_client_id
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.response_schema_loader import load_response_schema_bundle

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CACHE_LOCK = threading.Lock()
_DATA_CACHE: dict[str, "TargetClientData"] = {}


@dataclass(frozen=True, slots=True)
class TargetClientData:
    client_id: str
    pack_root: Path
    target_root: Path
    bundle: ResponseSchemaBundle


def _infer_brand_group_from_country(country: str) -> str | None:
    label = (country or "").lower()
    if "коре" in label:
        return "korean"
    if "герман" in label:
        return "german"
    if "швейц" in label:
        return "swiss"
    return None


def target_response_root(client_id: str | None) -> Path:
    pack = resolve_pack_client_id(client_id)
    return _REPO_ROOT / "clients" / pack / "target_response"


def client_pack_root(client_id: str | None) -> Path:
    pack = resolve_pack_client_id(client_id)
    return _REPO_ROOT / "clients" / pack


def _service_catalog_dict(bundle: ResponseSchemaBundle) -> dict[str, dict[str, Any]]:
    return {
        service_id: service.model_dump(mode="python")
        for service_id, service in bundle.services.items()
    }


def _validate_external_refs(
    *,
    client_id: str,
    bundle: ResponseSchemaBundle,
    md_root: Path,
) -> None:
    doctors = load_doctor_catalog(client_pack_root(client_id) / "doctor_catalog.json")
    kb_refs = build_response_schema_kb_refs(md_root)
    doctor_index = DoctorCatalogExternalIndex(
        service_ids=tuple(bundle.services),
        kb_refs=kb_refs,
    )
    validate_doctor_catalog_external_refs(doctors, doctor_index)
    external_index = ResponseSchemaExternalIndex(
        kb_refs=kb_refs,
        doctor_refs=build_doctor_source_refs(doctors),
    )
    validate_response_schema_external_refs(bundle, external_index)


def _data_cache_key(client_id: str, pack_hash: str | None = None) -> str:
    if pack_hash:
        return f"{client_id}:{pack_hash}"
    return client_id


def evict_target_client_data_cache_for_client(
    client_id: str | None,
    *,
    keep_pack_hash: str | None = None,
) -> None:
    """Drop stale pack-scoped target bundles; keep current identity when provided."""

    resolved = resolve_pack_client_id(client_id)
    keep_key = _data_cache_key(resolved, keep_pack_hash) if keep_pack_hash else None
    with _CACHE_LOCK:
        for key in list(_DATA_CACHE.keys()):
            if key != resolved and not key.startswith(f"{resolved}:"):
                continue
            if keep_key is not None and key == keep_key:
                continue
            del _DATA_CACHE[key]


def _build_target_client_data(client_id: str) -> TargetClientData:
    pack_root = client_pack_root(client_id)
    target_root = pack_root / "target_response"
    md_root = pack_root / "md"
    if not md_root.is_dir():
        raise FileNotFoundError(f"md_root_missing:{md_root}")
    if not target_root.is_dir():
        raise FileNotFoundError(f"target_root_missing:{target_root}")
    bundle = load_response_schema_bundle(target_root)
    _validate_external_refs(client_id=client_id, bundle=bundle, md_root=md_root)
    return TargetClientData(
        client_id=client_id,
        pack_root=pack_root,
        target_root=target_root,
        bundle=bundle,
    )


def load_target_client_data(
    client_id: str | None,
    *,
    pack_hash: str | None = None,
) -> TargetClientData:
    """Load and cache validated canonical target bundle for one client pack."""

    resolved = resolve_pack_client_id(client_id)
    key = _data_cache_key(resolved, pack_hash)
    with _CACHE_LOCK:
        cached = _DATA_CACHE.get(key)
        if cached is not None:
            return cached
        data = _build_target_client_data(resolved)
        _DATA_CACHE[key] = data
        return data


def clear_target_client_data_cache() -> None:
    with _CACHE_LOCK:
        _DATA_CACHE.clear()


def service_catalog_dict(
    client_id: str | None,
    *,
    pack_hash: str | None = None,
) -> dict[str, dict[str, Any]]:
    return _service_catalog_dict(load_target_client_data(client_id, pack_hash=pack_hash).bundle)


def catalog_service_label(client_id: str | None, service_id: str | None) -> str | None:
    sid = str(service_id or "").strip()
    if not sid:
        return None
    services = load_target_client_data(client_id).bundle.services
    entry = services.get(sid)
    if entry is None:
        return None
    name = str(entry.name or "").strip()
    return name or sid.replace("_", " ")


def _compact_service_about(service: TargetService) -> str:
    name = str(service.name or "").strip()
    family = str(service.family or "").strip()
    if family and family != name:
        return f"{name} ({family})"
    return name


def build_compact_service_catalog(client_id: str | None) -> list[dict[str, str]]:
    """Active target services for planner prompt: id, title, short metadata."""

    bundle = load_target_client_data(client_id).bundle
    rows: list[dict[str, str]] = []
    for service_id in sorted(bundle.services):
        service = bundle.services[service_id]
        if not service.active:
            continue
        title = str(service.name or service_id).strip()
        about = _compact_service_about(service)
        rows.append(
            {
                "service_id": str(service_id),
                "title": title,
                "about": about or title,
            }
        )
    return rows


def allowed_brand_filters(client_id: str | None) -> tuple[frozenset[str], frozenset[str]]:
    """Allowed planner brand_group and brand tokens from target offers/brands."""

    bundle = load_target_client_data(client_id).bundle
    groups: set[str] = set()
    brands: set[str] = set()
    brand_catalog = bundle.brands.brands
    for offer in bundle.offers:
        if not offer.active:
            continue
        brand_id = str(offer.brand_id or "").strip()
        if not brand_id:
            continue
        record = brand_catalog.get(brand_id)
        if record is None:
            continue
        group = _infer_brand_group_from_country(str(record.country or ""))
        if group:
            groups.add(group)
        canonical = str(record.canonical_name or "").strip().lower()
        if canonical:
            brands.add(canonical)
        brands.add(brand_id.lower())
        for alias in record.aliases:
            token = str(alias or "").strip().lower()
            if token:
                brands.add(token)
    return frozenset(groups), frozenset(brands)


def match_service_from_bundle(
    q: str,
    bundle: ResponseSchemaBundle,
    *,
    exclude_service_ids: frozenset[str] | None = None,
    service_topic: str | None = None,
    topic_confidence: float = 0.0,
) -> dict[str, Any]:
    return resolve_catalog_match(
        q,
        _service_catalog_dict(bundle),
        exclude_service_ids=exclude_service_ids,
        service_topic=service_topic,
        topic_confidence=topic_confidence,
        strong_match_min=float(PRICE_SERVICE_MATCH_STRONG),
    )


def match_service_from_target_catalog(
    q: str,
    *,
    client_id: str | None,
    pack_hash: str | None = None,
    exclude_service_ids: frozenset[str] | None = None,
    service_topic: str | None = None,
    topic_confidence: float = 0.0,
) -> dict[str, Any]:
    catalog = service_catalog_dict(client_id, pack_hash=pack_hash)
    return resolve_catalog_match(
        q,
        catalog,
        exclude_service_ids=exclude_service_ids,
        service_topic=service_topic,
        topic_confidence=topic_confidence,
        strong_match_min=float(PRICE_SERVICE_MATCH_STRONG),
    )
