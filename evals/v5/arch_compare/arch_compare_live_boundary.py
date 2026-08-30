"""Public response-boundary capture for architecture comparison LIVE prep (eval-only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from contracts.one_call_presentation_result import OneCallPresentationResult
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundTerminalResponse
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.one_call_envelope_protocol import parse_production_envelope_json
from core.one_call_presentation_pass import build_one_call_presentation_result
from core.sales_fast_presentation import (
    materialize_sales_fast_admin_payload,
    materialize_sales_fast_terminal_from_dispatch,
    static_sales_fast_admin_handoff,
)
from core.sales_fast_strict_evidence import (
    assemble_stage51b_availability_bound_package,
    effective_scope_from_semantic_frame,
    exact_sales_resolution_from_semantic_frame,
    resolve_sales_fast_bound_package,
)
from core.sales_fast_turn_frame import build_turn_frame_from_semantic_frame
from core.sales_one_plus_semantic_authority import bind_semantic_frame, governed_ui_authority_from_resolution
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.target_contact_authority import (
    contact_fields_from_turn_aspects,
    materialize_clinic_contact_primary_evidence,
)
from core.target_presentation_decision import TargetPresentationCadenceState
from core.target_runtime_client_context import TargetRuntimeClientContext, load_target_runtime_client_context
from core.target_runtime_strategy import resolve_target_runtime_strategy_context
from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage
from core.target_strategy_context import strategy_match_from_effective_scope
from evals.v5.arch_compare.arch_compare_contract import CLIENT_ID, FROZEN_COMMERCIAL_AS_OF
from evals.v5.arch_compare.arch_compare_matrix import ArchCompareScenarioSpec, ArchCompareTurnSpec
from evals.v5.arch_compare.arch_compare_prompt_build import (
    governed_resolution_for_turn,
    resolve_precomposer_for_turn,
)

PresentationCaptureStatus = Literal["full", "terminal_boundary_full", "code_only_boundary_full"]


@dataclass(frozen=True, slots=True)
class ArchCompareBoundaryCapture:
    visible_answer: str
    presentation_capture_status: PresentationCaptureStatus
    patient_text: str | None
    route: str | None
    presentation: OneCallPresentationResult | None
    promo_fact_ids: tuple[str, ...]
    promo_fact_texts: tuple[str, ...]
    amplifier_fact_ids: tuple[str, ...]
    amplifier_fact_texts: tuple[str, ...]
    canonical_price_block: str | None
    service_value_id: str | None
    service_value_text: str | None
    cta_ui_metadata: dict[str, Any]

    def to_structured_fields(self) -> dict[str, Any]:
        return {
            "visible_answer": self.visible_answer,
            "presentation_capture_status": self.presentation_capture_status,
            "patient_text": self.patient_text,
            "route": self.route,
            "promo_fact_ids": self.promo_fact_ids,
            "promo_fact_texts": self.promo_fact_texts,
            "amplifier_fact_ids": self.amplifier_fact_ids,
            "amplifier_fact_texts": self.amplifier_fact_texts,
            "canonical_price_block": self.canonical_price_block,
            "service_value_id": self.service_value_id,
            "service_value_text": self.service_value_text,
            "cta_ui_metadata": self.cta_ui_metadata,
        }


def _empty_structured_defaults() -> dict[str, Any]:
    return {
        "promo_fact_ids": (),
        "promo_fact_texts": (),
        "amplifier_fact_ids": (),
        "amplifier_fact_texts": (),
        "canonical_price_block": None,
        "service_value_id": None,
        "service_value_text": None,
        "cta_ui_metadata": {},
    }


def _extract_service_value(
    presentation: OneCallPresentationResult,
) -> tuple[str | None, str | None]:
    service_value_id = None
    service_value_text = None
    if presentation.pending_session_delta and presentation.pending_session_delta.shown_service_value_ids:
        service_value_id = presentation.pending_session_delta.shown_service_value_ids[0]
    for slot in presentation.secondary_content_slots:
        if slot.ref.startswith("service_value:"):
            service_value_id = slot.ref.split(":", 1)[1]
            service_value_text = slot.label
            break
    return service_value_id, service_value_text


def _presentation_fields(presentation: OneCallPresentationResult) -> dict[str, Any]:
    service_value_id, service_value_text = _extract_service_value(presentation)
    canonical_price_block = None
    if presentation.authoritative_commerce is not None:
        commerce = presentation.authoritative_commerce
        canonical_price_block = getattr(commerce, "canonical_price_block", None) or getattr(
            commerce, "price_block_text", None
        )
    return {
        "promo_fact_ids": tuple(presentation.rendered_promo_fact_ids),
        "promo_fact_texts": (),
        "amplifier_fact_ids": tuple(presentation.rendered_amplifier_refs),
        "amplifier_fact_texts": (),
        "canonical_price_block": canonical_price_block,
        "service_value_id": service_value_id,
        "service_value_text": service_value_text,
        "cta_ui_metadata": {
            "selected_cta_key": presentation.selected_cta_key,
            "quick_replies": [
                {"label": row.label, "ref": row.ref} for row in presentation.quick_replies
            ],
            "secondary_content_slots": [
                {"label": row.label, "ref": row.ref}
                for row in presentation.secondary_content_slots
            ],
            "video": presentation.video,
            "situation": presentation.situation,
        },
    }


def _build_presentation_from_bound(
    *,
    bound: TargetSpecBoundOfflineResponsePackage,
    ctx: TargetRuntimeClientContext,
    turn: ArchCompareTurnSpec,
    semantic,
    turn_frame,
    strategy_context,
    patient_text: str,
) -> OneCallPresentationResult:
    resolution = exact_sales_resolution_from_semantic_frame(semantic)
    precomposer = resolve_precomposer_for_turn(ctx, turn)
    return build_one_call_presentation_result(
        bound_package=bound,
        context=ctx,
        turn_frame=turn_frame,
        semantic=semantic,
        patient_text=patient_text,
        user_message=turn.user_message,
        cadence=TargetPresentationCadenceState(),
        allow_situation=False,
        resolution=resolution,
        strategy_context=strategy_context,
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
        shown_service_value_ids=(),
        today=FROZEN_COMMERCIAL_AS_OF,
        precomposer_selected_offer=precomposer,
    )


def _terminal_visible_from_dispatch(
    *,
    terminal: TargetTurnFrameBoundTerminalResponse,
    session_id: str,
) -> str:
    payload = materialize_sales_fast_terminal_from_dispatch(
        terminal=terminal,
        client_id=CLIENT_ID,
        sid=session_id,
    )
    answer = payload.payload.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("terminal_boundary_answer_missing")
    return answer


def capture_provider_turn_boundary(
    *,
    envelope_json: str,
    scenario: ArchCompareScenarioSpec,
    turn: ArchCompareTurnSpec,
    patient_text: str,
    session_id: str,
    ctx: TargetRuntimeClientContext | None = None,
) -> ArchCompareBoundaryCapture:
    runtime_ctx = ctx or load_target_runtime_client_context(CLIENT_ID)
    active_service_catalog = ActiveServiceCatalogSnapshot.from_bundle(runtime_ctx.bundle)
    service_reference_catalog = ServiceReferenceCatalogSnapshot.from_bundle(runtime_ctx.bundle)
    commercial_fact_catalog = CommercialFactCatalogSnapshot.from_bundle(runtime_ctx.bundle)
    envelope = parse_production_envelope_json(
        envelope_json,
        active_service_catalog=active_service_catalog,
        service_reference_catalog=service_reference_catalog,
        commercial_fact_catalog=commercial_fact_catalog,
    )
    governed_ui = governed_ui_authority_from_resolution(governed_resolution_for_turn(turn))
    semantic = bind_semantic_frame(
        envelope=envelope,
        governed_ui=governed_ui,
        active_service_catalog=active_service_catalog,
        service_reference_catalog=service_reference_catalog,
    )
    turn_frame = build_turn_frame_from_semantic_frame(
        semantic=semantic,
        user_message=turn.user_message,
        bundle=runtime_ctx.bundle,
    )
    effective_scope = effective_scope_from_semantic_frame(
        semantic,
        current_ui_action=None,
        current_ui_stage_action=None,
    )
    strategy_context = strategy_match_from_effective_scope(
        effective_scope,
        service_family=resolve_target_runtime_strategy_context(
            runtime_ctx.bundle,
            service_id=turn_frame.service_id,
        ).family,
    )
    bound = resolve_sales_fast_bound_package(
        turn_frame=turn_frame,
        semantic=semantic,
        bundle=runtime_ctx.bundle,
        doctor_catalog=runtime_ctx.doctor_catalog,
        external_index=runtime_ctx.external_index,
        consultation_values=runtime_ctx.consultation_values,
        strategy_context=strategy_context,
        effective_scope=effective_scope,
        allowed_topics=runtime_ctx.allowed_topics,
        today=FROZEN_COMMERCIAL_AS_OF,
        md_root=runtime_ctx.md_root,
        client_id=CLIENT_ID,
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
    )

    if isinstance(bound, TargetSpecBoundOfflineResponsePackage):
        presentation = _build_presentation_from_bound(
            bound=bound,
            ctx=runtime_ctx,
            turn=turn,
            semantic=semantic,
            turn_frame=turn_frame,
            strategy_context=strategy_context,
            patient_text=patient_text,
        )
        fields = _presentation_fields(presentation)
        return ArchCompareBoundaryCapture(
            visible_answer=presentation.final_patient_text,
            presentation_capture_status="full",
            patient_text=patient_text,
            route=str(envelope.route),
            presentation=presentation,
            **fields,
        )

    if not isinstance(bound, TargetTurnFrameBoundTerminalResponse):
        raise RuntimeError("unknown_bound_package_kind")

    if turn.commercial_intent == "price":
        stage51b_bound = assemble_stage51b_availability_bound_package(
            turn_frame=turn_frame,
            bundle=runtime_ctx.bundle,
            doctor_catalog=runtime_ctx.doctor_catalog,
            external_index=runtime_ctx.external_index,
            consultation_values=runtime_ctx.consultation_values,
            strategy_context=strategy_context,
            effective_scope=effective_scope,
            allowed_topics=runtime_ctx.allowed_topics,
            today=FROZEN_COMMERCIAL_AS_OF,
            md_root=runtime_ctx.md_root,
            client_id=CLIENT_ID,
        )
        presentation = _build_presentation_from_bound(
            bound=stage51b_bound,
            ctx=runtime_ctx,
            turn=turn,
            semantic=semantic,
            turn_frame=turn_frame,
            strategy_context=strategy_context,
            patient_text=patient_text,
        )
        fields = _presentation_fields(presentation)
        return ArchCompareBoundaryCapture(
            visible_answer=presentation.final_patient_text,
            presentation_capture_status="terminal_boundary_full",
            patient_text=patient_text,
            route=str(envelope.route),
            presentation=presentation,
            **fields,
        )

    visible = _terminal_visible_from_dispatch(terminal=bound, session_id=session_id)
    return ArchCompareBoundaryCapture(
        visible_answer=visible,
        presentation_capture_status="terminal_boundary_full",
        patient_text=patient_text,
        route=str(envelope.route),
        presentation=None,
        **_empty_structured_defaults(),
    )


def capture_code_only_boundary(
    *,
    turn: ArchCompareTurnSpec,
    session_id: str,
) -> ArchCompareBoundaryCapture:
    if turn.expected_route_class == "ADMIN":
        handoff = static_sales_fast_admin_handoff(client_id=CLIENT_ID)
        payload = materialize_sales_fast_admin_payload(
            client_id=CLIENT_ID,
            sid=session_id,
            handoff_text=handoff,
        )
        visible = str(payload.payload.get("answer") or "")
        if not visible.strip():
            raise RuntimeError("admin_boundary_answer_missing")
        return ArchCompareBoundaryCapture(
            visible_answer=visible,
            presentation_capture_status="code_only_boundary_full",
            patient_text=None,
            route="ADMIN",
            presentation=None,
            **_empty_structured_defaults(),
        )

    if turn.expected_route_class == "LOCAL":
        fields = contact_fields_from_turn_aspects(("contacts",), primary_aspect="contacts")
        blocks = materialize_clinic_contact_primary_evidence(CLIENT_ID, fields=fields or ())
        visible = "\n\n".join(block.text for block in blocks).strip()
        if not visible:
            raise RuntimeError("contacts_boundary_answer_missing")
        return ArchCompareBoundaryCapture(
            visible_answer=visible,
            presentation_capture_status="code_only_boundary_full",
            patient_text=None,
            route="LOCAL",
            presentation=None,
            **_empty_structured_defaults(),
        )

    raise RuntimeError(f"code_only_boundary_unsupported_route:{turn.expected_route_class}")


def drain_fake_streaming_boundary(*, transport, **kwargs: Any) -> str:
    """Drain fake SSE deltas into a single public response string."""

    stream = transport.chat_completions_create(stream=True, **kwargs)
    parts: list[str] = []
    for chunk in stream:
        choices = getattr(chunk, "choices", None) or ()
        if not choices:
            continue
        delta = getattr(choices[0], "delta", None)
        text = getattr(delta, "content", None) if delta is not None else None
        if text:
            parts.append(str(text))
    return "".join(parts)
