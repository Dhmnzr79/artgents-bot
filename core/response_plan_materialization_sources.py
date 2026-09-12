"""Public preparation of ResponsePlanMaterializationSources for data-backed response-plan turns."""

from __future__ import annotations

from contracts.response_plan import ContextStrategy, SessionKey, TransportKind
from contracts.response_plan_adapter import (
    ResponsePlanAdapterTerminalAuthority,
    ResponsePlanAdapterTextualCtaAuthority,
    ResponsePlanAdapterUiAuthority,
)
from contracts.response_plan_materialization import ResponsePlanMaterializationSources
from contracts.response_plan_post_composer import PostComposerMaterialAuthority
from core.response_plan_condition_evidence import build_condition_evidence_by_offer


def build_response_plan_materialization_sources(
    *,
    session_key: SessionKey,
    material: PostComposerMaterialAuthority,
    context_strategy: ContextStrategy = "full_context",
    transport_kind: TransportKind = "blocking",
    terminal_authorities: tuple[ResponsePlanAdapterTerminalAuthority, ...] = (),
    ui_authority: ResponsePlanAdapterUiAuthority | None = None,
    textual_cta_authority: ResponsePlanAdapterTextualCtaAuthority | None = None,
    shown_requested_fact_ids: tuple[str, ...] = (),
    shown_promo_fact_ids: tuple[str, ...] = (),
    shown_amplifier_fact_ids: tuple[str, ...] = (),
    shown_service_value_ids: tuple[str, ...] = (),
) -> ResponsePlanMaterializationSources:
    return ResponsePlanMaterializationSources(
        session_key=session_key,
        context_strategy=context_strategy,
        transport_kind=transport_kind,
        material_authority=material,
        condition_evidence_by_offer=build_condition_evidence_by_offer(material),
        terminal_authorities=terminal_authorities,
        ui_authority=ui_authority,
        textual_cta_authority=textual_cta_authority,
        shown_requested_fact_ids=shown_requested_fact_ids,
        shown_promo_fact_ids=shown_promo_fact_ids,
        shown_amplifier_fact_ids=shown_amplifier_fact_ids,
        shown_service_value_ids=shown_service_value_ids,
    )
