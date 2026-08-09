"""Product runtime bootstrap for target FullContext client context (S61)."""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import NoReturn

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.doctor_schema_refs import (
    DoctorCatalogExternalIndex,
    build_doctor_source_refs,
    validate_doctor_catalog_external_refs,
)
from contracts.one_call_client_pack_identity import ClientPackIdentityKey
from contracts.response_schema import ResponseSchemaBundle
from contracts.response_schema_refs import (
    ResponseSchemaExternalIndex,
    validate_response_schema_external_refs,
)
from contracts.service_consultation import ServiceConsultationValue, validate_service_consultation_refs
from contracts.target_cached_full_context import TargetCachedFullContext
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.target_client_data import (
    evict_target_client_data_cache_for_client,
    load_target_client_data,
)
from core.service_consultation_source import build_service_consultation_values
from core.target_cached_full_context import (
    TargetCachedFullContextError,
    build_target_cached_full_context,
)
from core.target_composer_executor import TargetComposerTone
from core.one_call_client_pack_identity import build_client_pack_identity
from core.topic_taxonomy import evict_topic_taxonomy_cache_for_client, load_client_topic_taxonomy

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MAX_CONTEXT_ENTRIES = 8
_CACHE_LOCK = threading.Lock()
_CONTEXT_CACHE: OrderedDict[str, TargetRuntimeClientContext] = OrderedDict()


def _context_cache_key(identity: ClientPackIdentityKey) -> str:
    return identity.cache_key()


class TargetRuntimeClientContextError(ValueError):
    """Typed fail-closed target runtime bootstrap failure."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _fail(code: str, value: object, cause: BaseException | None = None) -> NoReturn:
    error = TargetRuntimeClientContextError(code, value)
    if cause is None:
        raise error
    raise error from cause


@dataclass(frozen=True, slots=True)
class TargetRuntimeClientContext:
    client_id: str
    md_root: Path
    target_root: Path
    bundle: ResponseSchemaBundle
    doctor_catalog: TargetDoctorCatalog
    external_index: ResponseSchemaExternalIndex
    consultation_values: tuple[ServiceConsultationValue, ...]
    cached_full_context: TargetCachedFullContext
    pack_identity: ClientPackIdentityKey
    allowed_topics: tuple[str, ...]
    tone: TargetComposerTone
    cta_capability: bool
    semantic_context: str
    include_initial_block: bool
    include_consultation_close: bool

    @property
    def cache_key(self) -> str:
        return self.pack_identity.cache_key()


def _client_paths(client_id: str) -> tuple[Path, Path]:
    if not client_id or client_id.strip() != client_id:
        _fail("target_runtime_client_id_invalid", client_id)
    demo_root = _REPO_ROOT / "clients" / client_id
    md_root = demo_root / "md"
    target_root = demo_root / "target_response"
    if not md_root.is_dir():
        _fail("target_runtime_md_root_invalid", md_root)
    if not target_root.is_dir():
        _fail("target_runtime_target_root_invalid", target_root)
    return md_root, target_root


def _build_context(
    client_id: str,
    *,
    pack_identity: ClientPackIdentityKey,
) -> TargetRuntimeClientContext:
    md_root, target_root = _client_paths(client_id)
    pack_hash = pack_identity.client_pack_hash
    try:
        bundle = load_target_client_data(client_id, pack_hash=pack_hash).bundle
    except Exception as exc:
        _fail("target_runtime_bundle_invalid", target_root, exc)
    try:
        doctors = load_doctor_catalog(_REPO_ROOT / "clients" / client_id / "doctor_catalog.json")
    except Exception as exc:
        _fail("target_runtime_doctor_catalog_invalid", client_id, exc)
    kb_refs = build_response_schema_kb_refs(md_root)
    doctor_index = DoctorCatalogExternalIndex(
        service_ids=tuple(bundle.services),
        kb_refs=kb_refs,
    )
    try:
        validate_doctor_catalog_external_refs(doctors, doctor_index)
    except Exception as exc:
        _fail("target_runtime_doctor_refs_invalid", client_id, exc)
    external_index = ResponseSchemaExternalIndex(
        kb_refs=kb_refs,
        doctor_refs=build_doctor_source_refs(doctors),
    )
    try:
        validate_response_schema_external_refs(bundle, external_index)
    except Exception as exc:
        _fail("target_runtime_schema_refs_invalid", client_id, exc)
    try:
        consultations = tuple(build_service_consultation_values(md_root))
    except Exception as exc:
        _fail("target_runtime_consultation_values_invalid", md_root, exc)
    try:
        validate_service_consultation_refs(consultations, bundle.services)
    except Exception as exc:
        _fail("target_runtime_consultation_refs_invalid", client_id, exc)
    try:
        cached = build_target_cached_full_context(md_root)
    except TargetCachedFullContextError as exc:
        _fail("target_runtime_fullcontext_invalid", md_root, exc)
    topics = tuple(sorted(load_client_topic_taxonomy(client_id, pack_hash=pack_hash)))
    if not topics:
        _fail("target_runtime_allowed_topics_empty", client_id)
    return TargetRuntimeClientContext(
        client_id=client_id,
        md_root=md_root,
        target_root=target_root,
        bundle=bundle,
        doctor_catalog=doctors,
        external_index=external_index,
        consultation_values=consultations,
        cached_full_context=cached,
        pack_identity=pack_identity,
        allowed_topics=topics,
        tone=TargetComposerTone(
            key="commercial_warm",
            instruction="Отвечай доброжелательно и без давления.",
        ),
        cta_capability=bool(bundle.marketing.cta_contexts),
        semantic_context="service",
        include_initial_block=False,
        include_consultation_close=True,
    )


def _evict_nested_pack_scoped_caches(
    client_id: str,
    *,
    keep_pack_hash: str,
) -> None:
    evict_target_client_data_cache_for_client(client_id, keep_pack_hash=keep_pack_hash)
    evict_topic_taxonomy_cache_for_client(client_id, keep_pack_hash=keep_pack_hash)


def _store_context_cache(context: TargetRuntimeClientContext) -> None:
    key = _context_cache_key(context.pack_identity)
    client_id = context.client_id
    keep_hash = context.pack_identity.client_pack_hash
    with _CACHE_LOCK:
        for existing_key in list(_CONTEXT_CACHE.keys()):
            if existing_key.startswith(f"{client_id}:") and existing_key != key:
                del _CONTEXT_CACHE[existing_key]
        _CONTEXT_CACHE[key] = context
        _CONTEXT_CACHE.move_to_end(key)
        while len(_CONTEXT_CACHE) > _MAX_CONTEXT_ENTRIES:
            _CONTEXT_CACHE.popitem(last=False)
    _evict_nested_pack_scoped_caches(client_id, keep_pack_hash=keep_hash)


def load_target_runtime_client_context(client_id: str) -> TargetRuntimeClientContext:
    """Load and cache validated target runtime context once per exact pack identity."""

    pack_root = _REPO_ROOT / "clients" / client_id

    for attempt in range(2):
        identity_before = build_client_pack_identity(client_id, pack_root)
        cache_key_before = _context_cache_key(identity_before)
        with _CACHE_LOCK:
            cached = _CONTEXT_CACHE.get(cache_key_before)
            if cached is not None:
                _CONTEXT_CACHE.move_to_end(cache_key_before)
                return cached

        context = _build_context(client_id, pack_identity=identity_before)
        identity_after = build_client_pack_identity(client_id, pack_root)

        if identity_before.cache_key() != identity_after.cache_key():
            if attempt == 0:
                continue
            _fail(
                "client_pack_changed_during_load",
                {
                    "client_id": client_id,
                    "before": identity_before.cache_key(),
                    "after": identity_after.cache_key(),
                },
            )

        if context.pack_identity.cache_key() != identity_after.cache_key():
            _fail("client_pack_changed_during_load", client_id)

        final_context = TargetRuntimeClientContext(
            client_id=context.client_id,
            md_root=context.md_root,
            target_root=context.target_root,
            bundle=context.bundle,
            doctor_catalog=context.doctor_catalog,
            external_index=context.external_index,
            consultation_values=context.consultation_values,
            cached_full_context=context.cached_full_context,
            pack_identity=identity_after,
            allowed_topics=context.allowed_topics,
            tone=context.tone,
            cta_capability=context.cta_capability,
            semantic_context=context.semantic_context,
            include_initial_block=context.include_initial_block,
            include_consultation_close=context.include_consultation_close,
        )
        _store_context_cache(final_context)
        return final_context

    _fail("client_pack_changed_during_load", client_id)


def clear_target_runtime_client_context_cache() -> None:
    """Test helper: drop cached client contexts."""

    with _CACHE_LOCK:
        _CONTEXT_CACHE.clear()


def runtime_today() -> date:
    return date.today()
