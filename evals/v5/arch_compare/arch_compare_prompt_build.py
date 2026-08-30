"""Prompt assembly and parity capture for architecture comparison (eval-only)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Any

from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.precomposer_selected_offer import PrecomposerSelectedOfferResult
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_exact_commercial_catalog import ExactCommercialCatalogSnapshot
from core.one_call_fullcontext_messages import build_one_call_stable_prefix
from core.one_call_prefix_input_fingerprint import compute_prefix_input_fingerprint
from core.one_call_prompt_contract import ONE_CALL_PROMPT_CONTRACT_VERSION
from core.resolve_precomposer_selected_offer import resolve_precomposer_selected_offer
from core.sales_one_plus_protocol import AUTHORITY_CLIENT_ID_HINT_KEY, build_sales_one_plus_dynamic_suffix
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.target_runtime_client_context import TargetRuntimeClientContext, load_target_runtime_client_context
from evals.v5.arch_compare.arch_compare_configs import ArchCompareConfig
from evals.v5.arch_compare.arch_compare_context import (
    cached_context_for_mode,
    content_context_hash_for,
    load_demo_full_cached_context,
)
from evals.v5.arch_compare.arch_compare_contract import CLIENT_ID, FROZEN_COMMERCIAL_AS_OF
from evals.v5.arch_compare.arch_compare_matrix import ArchCompareScenarioSpec, ArchCompareTurnSpec


def _digest_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _authority(source: str) -> ExactSalesFieldAuthority:
    return ExactSalesFieldAuthority(authority=source, provenance=source)  # type: ignore[arg-type]


def governed_resolution_for_turn(turn: ArchCompareTurnSpec) -> ExactSalesResolution:
    gov = _authority("governed_ui")
    unk = _authority("unknown")
    service_id = turn.expected_service_id
    return ExactSalesResolution(
        service_id=service_id,
        aspect="price" if turn.commercial_intent == "price" else "none",
        extent="full_arch" if service_id in {"all_on_4", "all_on_6"} else None,
        jaw=None,
        stage=None,
        service_id_authority=gov if service_id else unk,
        aspect_authority=gov if turn.commercial_intent == "price" else unk,
        extent_authority=gov if service_id in {"all_on_4", "all_on_6"} else unk,
        jaw_authority=unk,
        stage_authority=unk,
    )


def resolve_precomposer_for_turn(
    ctx: TargetRuntimeClientContext,
    turn: ArchCompareTurnSpec,
) -> PrecomposerSelectedOfferResult:
    resolution = governed_resolution_for_turn(turn)
    brand_id = None
    if turn.expected_brand and turn.expected_brand != "MegaImplant X":
        for bid, brand in ctx.bundle.brands.brands.items():
            if brand.canonical_name == turn.expected_brand:
                brand_id = bid
                break
    return resolve_precomposer_selected_offer(
        bundle=ctx.bundle,
        doctor_catalog=ctx.doctor_catalog,
        resolution=resolution,
        selected_brand_id=brand_id,
        brand_id_authoritative=brand_id is not None,
    )


def build_dialog_history(
    *,
    scenario: ArchCompareScenarioSpec,
    turn: ArchCompareTurnSpec,
    prior_turns: dict[str, str],
) -> str:
    if not turn.dialog_history_turn_ids:
        return ""
    lines: list[str] = []
    for prior_id in turn.dialog_history_turn_ids:
        prior = next(t for t in scenario.turns if t.turn_id == prior_id)
        fake_answer = prior_turns.get(prior_id, "")
        lines.append(f"Пациент: {prior.user_message}")
        if fake_answer:
            lines.append(f"Ассистент: {fake_answer}")
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class ArchComparePromptCapture:
    stable_prefix: str
    dynamic_suffix: str
    stable_prefix_hash: str
    dynamic_suffix_hash: str
    prefix_input_fingerprint: str
    content_context_hash: str
    full_context_size: int
    curated_context_size: int | None
    exact_catalog_hash: str
    service_reference_catalog_hash: str
    commercial_as_of: str
    ordered_source_refs: tuple[str, ...]
    resolved_source_refs: tuple[str, ...]
    missing_source_refs: tuple[str, ...]
    selected_offer_ids: tuple[str, ...]
    precomposer_availability: str
    provider_model_id: str | None
    provider_model_id_status: str
    prompt_contract_version: int


def build_prompt_capture(
    *,
    config: ArchCompareConfig,
    scenario: ArchCompareScenarioSpec,
    turn: ArchCompareTurnSpec,
    dialog_history: str,
    ctx: TargetRuntimeClientContext | None = None,
    full_context=None,
    as_of_date: date | None = None,
) -> ArchComparePromptCapture:
    runtime_ctx = ctx or load_target_runtime_client_context(CLIENT_ID)
    full = full_context or load_demo_full_cached_context()
    cached, curated_resolution = cached_context_for_mode(
        context_mode=config.context_mode,
        full_context=full,
        curated_source_refs=scenario.relevant_source_refs,
    )
    catalog = ActiveServiceCatalogSnapshot.from_bundle(runtime_ctx.bundle)
    service_reference_catalog = ServiceReferenceCatalogSnapshot.from_bundle(runtime_ctx.bundle)
    exact_commercial_catalog = ExactCommercialCatalogSnapshot.from_bundle(runtime_ctx.bundle)
    stable_prefix = build_one_call_stable_prefix(
        identity=runtime_ctx.pack_identity,
        cached_full_context=cached,
        active_service_catalog=catalog,
        service_reference_catalog=service_reference_catalog,
        exact_commercial_catalog=exact_commercial_catalog,
    )
    precomposer = resolve_precomposer_for_turn(runtime_ctx, turn)
    offer_ids: tuple[str, ...] = ()
    if precomposer.offer is not None:
        offer_ids = (str(precomposer.offer.offer_id),)
    elif precomposer.offers:
        offer_ids = tuple(str(row.offer_id) for row in precomposer.offers)
    effective_as_of = as_of_date or FROZEN_COMMERCIAL_AS_OF
    sales_context: dict[str, Any] = {
        AUTHORITY_CLIENT_ID_HINT_KEY: CLIENT_ID,
        "commercial_intent": turn.commercial_intent,
        "promotion_scope": turn.promotion_scope,
    }
    dynamic_suffix = build_sales_one_plus_dynamic_suffix(
        exact_sales_resolution=governed_resolution_for_turn(turn),
        current_strict_facts=(),
        sales_context=sales_context,
        user_message=turn.user_message,
        dialog_history=dialog_history,
        exact_commercial_catalog=exact_commercial_catalog,
        as_of_date=effective_as_of,
        precomposer_selected_offer=precomposer,
        response_schema_bundle=runtime_ctx.bundle,
    )
    return ArchComparePromptCapture(
        stable_prefix=stable_prefix,
        dynamic_suffix=dynamic_suffix,
        stable_prefix_hash=_digest_hex(stable_prefix),
        dynamic_suffix_hash=_digest_hex(dynamic_suffix),
        prefix_input_fingerprint=compute_prefix_input_fingerprint(
            runtime_ctx.pack_identity,
            cached,
            catalog,
            service_reference_catalog,
            exact_commercial_catalog,
        ),
        content_context_hash=content_context_hash_for(cached),
        full_context_size=len(full.model_corpus_text),
        curated_context_size=(
            curated_resolution.curated_context_size if curated_resolution else None
        ),
        exact_catalog_hash=_digest_hex(exact_commercial_catalog.canonical_json),
        service_reference_catalog_hash=_digest_hex(service_reference_catalog.canonical_json),
        commercial_as_of=effective_as_of.isoformat(),
        ordered_source_refs=scenario.relevant_source_refs,
        resolved_source_refs=(
            curated_resolution.resolved_source_refs
            if curated_resolution
            else scenario.relevant_source_refs
        ),
        missing_source_refs=(
            curated_resolution.missing_source_refs if curated_resolution else ()
        ),
        selected_offer_ids=offer_ids,
        precomposer_availability=str(precomposer.availability),
        provider_model_id=config.provider_model_id,
        provider_model_id_status=config.provider_model_id_status,
        prompt_contract_version=ONE_CALL_PROMPT_CONTRACT_VERSION,
    )
