"""Stable FullContext prefix vs dynamic suffix assembly (Stage 3A)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.one_call_client_pack_identity import ClientPackIdentityKey
from contracts.target_cached_full_context import TargetCachedFullContext
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_prompt_contract import (
    ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS,
    one_call_contract_header,
)
from core.sales_one_plus_protocol import (
    SALES_ONE_PLUS_SYSTEM_POLICY,
    build_sales_one_plus_dynamic_suffix,
)


@dataclass(frozen=True, slots=True)
class OneCallPromptAssembly:
    stable_prefix: str
    dynamic_suffix: str
    identity: ClientPackIdentityKey

    @property
    def system_prompt(self) -> str:
        return self.stable_prefix

    @property
    def user_prompt(self) -> str:
        return self.dynamic_suffix


def _pack_identity_block(identity: ClientPackIdentityKey) -> str:
    return "\n".join(
        (
            "=== CLIENT_PACK_IDENTITY ===",
            f"client_id: {identity.client_id}",
            f"client_pack_hash: {identity.client_pack_hash}",
            f"prompt_contract_version: {identity.prompt_contract_version}",
            f"model_snapshot: {identity.model_snapshot}",
        )
    )


def build_one_call_stable_prefix(
    *,
    identity: ClientPackIdentityKey,
    cached_full_context: TargetCachedFullContext,
    active_service_catalog: ActiveServiceCatalogSnapshot,
) -> str:
    """Byte-stable prefix: contract, envelope instructions, catalog, corpus, pack identity."""

    corpus = cached_full_context.model_corpus_text
    sections = (
        one_call_contract_header(),
        "=== SYSTEM_POLICY ===\n" + SALES_ONE_PLUS_SYSTEM_POLICY,
        "=== TYPED_ENVELOPE_INSTRUCTIONS ===\n" + ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS,
        _pack_identity_block(identity),
        active_service_catalog.block_text(),
        "=== APPROVED_MD_CORPUS ===\n" + corpus,
        "=== DOCUMENT_INDEX ===\n" + "\n".join(cached_full_context.document_paths),
    )
    return "\n\n".join(sections)


def build_one_call_prompt_assembly(
    *,
    identity: ClientPackIdentityKey,
    cached_full_context: TargetCachedFullContext,
    active_service_catalog: ActiveServiceCatalogSnapshot,
    exact_sales_resolution,
    current_strict_facts,
    sales_context,
    user_message: str,
) -> OneCallPromptAssembly:
    dynamic_suffix = build_sales_one_plus_dynamic_suffix(
        exact_sales_resolution=exact_sales_resolution,
        current_strict_facts=current_strict_facts,
        sales_context=sales_context,
        user_message=user_message,
    )
    stable_prefix = build_one_call_stable_prefix(
        identity=identity,
        cached_full_context=cached_full_context,
        active_service_catalog=active_service_catalog,
    )
    return OneCallPromptAssembly(
        stable_prefix=stable_prefix,
        dynamic_suffix=dynamic_suffix,
        identity=identity,
    )
