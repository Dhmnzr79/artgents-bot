"""Bounded in-process cache for immutable ONE_CALL stable prefixes."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

from contracts.one_call_client_pack_identity import ClientPackIdentityKey
from contracts.target_cached_full_context import TargetCachedFullContext
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_exact_commercial_catalog import ExactCommercialCatalogSnapshot
from core.one_call_fullcontext_messages import build_one_call_stable_prefix
from core.one_call_prefix_input_fingerprint import prefix_cache_lookup_key
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot

_MAX_ENTRIES = 8
_LOCK = threading.Lock()
_CACHE: OrderedDict[str, _CachedStablePrefix] = OrderedDict()


@dataclass(frozen=True, slots=True)
class StablePrefixBundle:
    identity: ClientPackIdentityKey
    stable_prefix: str
    build_ms: int
    prefix_input_fingerprint: str


@dataclass(frozen=True, slots=True)
class _CachedStablePrefix:
    bundle: StablePrefixBundle


def clear_one_call_prefix_cache() -> None:
    with _LOCK:
        _CACHE.clear()


def get_or_build_stable_prefix(
    *,
    identity: ClientPackIdentityKey,
    cached_full_context: TargetCachedFullContext,
    active_service_catalog: ActiveServiceCatalogSnapshot,
    service_reference_catalog: ServiceReferenceCatalogSnapshot,
    exact_commercial_catalog: ExactCommercialCatalogSnapshot,
) -> tuple[StablePrefixBundle, bool]:
    """Return immutable stable prefix; second value is local_prefix_cache_hit."""

    lookup_key = prefix_cache_lookup_key(
        identity,
        cached_full_context,
        active_service_catalog,
        service_reference_catalog,
        exact_commercial_catalog,
    )
    with _LOCK:
        cached = _CACHE.get(lookup_key)
        if cached is not None:
            _CACHE.move_to_end(lookup_key)
            return cached.bundle, True

    started = time.monotonic()
    stable_prefix = build_one_call_stable_prefix(
        identity=identity,
        cached_full_context=cached_full_context,
        active_service_catalog=active_service_catalog,
        service_reference_catalog=service_reference_catalog,
        exact_commercial_catalog=exact_commercial_catalog,
    )
    build_ms = max(0, int((time.monotonic() - started) * 1000))
    fingerprint = lookup_key.rsplit(":pf", 1)[-1]
    bundle = StablePrefixBundle(
        identity=identity,
        stable_prefix=stable_prefix,
        build_ms=build_ms,
        prefix_input_fingerprint=fingerprint,
    )
    with _LOCK:
        _CACHE[lookup_key] = _CachedStablePrefix(bundle=bundle)
        _CACHE.move_to_end(lookup_key)
        while len(_CACHE) > _MAX_ENTRIES:
            _CACHE.popitem(last=False)
    return bundle, False
