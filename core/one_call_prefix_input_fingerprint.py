"""Immutable prefix-input fingerprint — internal cache integrity guard (Stage 3A)."""

from __future__ import annotations

import hashlib

from contracts.one_call_client_pack_identity import ClientPackIdentityKey
from contracts.target_cached_full_context import TargetCachedFullContext
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_exact_commercial_catalog import ExactCommercialCatalogSnapshot
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.one_call_prompt_contract import (
    ONE_CALL_PROMPT_CONTRACT_VERSION,
    ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS,
)
from core.sales_one_plus_protocol import SALES_ONE_PLUS_SYSTEM_POLICY


def _digest_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def compute_prefix_input_fingerprint(
    identity: ClientPackIdentityKey,
    cached_full_context: TargetCachedFullContext,
    active_service_catalog: ActiveServiceCatalogSnapshot,
    service_reference_catalog: ServiceReferenceCatalogSnapshot,
    exact_commercial_catalog: ExactCommercialCatalogSnapshot,
) -> str:
    """Fingerprint stable prefix inputs — independent of production pack identity key."""

    digest = hashlib.sha256()
    digest.update(identity.cache_key().encode("utf-8"))
    digest.update(_digest_hex(cached_full_context.model_corpus_text).encode("ascii"))
    digest.update(_digest_hex("\n".join(cached_full_context.document_paths)).encode("ascii"))
    digest.update(_digest_hex(service_reference_catalog.canonical_json).encode("ascii"))
    digest.update(_digest_hex(active_service_catalog.canonical_json).encode("ascii"))
    digest.update(_digest_hex(exact_commercial_catalog.canonical_json).encode("ascii"))
    digest.update(str(ONE_CALL_PROMPT_CONTRACT_VERSION).encode("utf-8"))
    digest.update(_digest_hex(SALES_ONE_PLUS_SYSTEM_POLICY).encode("ascii"))
    digest.update(_digest_hex(ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS).encode("ascii"))
    return digest.hexdigest()


def prefix_cache_lookup_key(
    identity: ClientPackIdentityKey,
    cached_full_context: TargetCachedFullContext,
    active_service_catalog: ActiveServiceCatalogSnapshot,
    service_reference_catalog: ServiceReferenceCatalogSnapshot,
    exact_commercial_catalog: ExactCommercialCatalogSnapshot,
) -> str:
    fingerprint = compute_prefix_input_fingerprint(
        identity,
        cached_full_context,
        active_service_catalog,
        service_reference_catalog,
        exact_commercial_catalog,
    )
    return f"{identity.cache_key()}:pf{fingerprint}"
