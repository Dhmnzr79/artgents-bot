"""Materialize sales-fast widget payloads with the existing presentation layer."""

from __future__ import annotations

from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundTerminalResponse
from contracts.turn_frame import TurnFrame
from core.target_contact_authority import fallback_answer_with_phone
from core.target_presentation_decision import TargetPresentationCadenceState
from core.target_response_verifier import TargetVerifiedComposedResponse
from core.target_runtime_client_context import TargetRuntimeClientContext
from core.target_runtime_widget import (
    TargetRuntimeMaterializedPayload,
    TargetRuntimeTerminalPayload,
    build_target_runtime_widget_cta,
    materialize_s41_terminal_payload,
    materialize_verified_widget_payload,
)
from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage
from core.target_verified_primary_content_cta_projection import (
    project_verified_primary_content_cta,
)
from core.target_verified_response_pipeline import _used_content_refs_from_package
from core.target_composer_request import materialize_target_composer_request
from core.target_response_policy import select_target_response_length_profile
from core.target_session_selection import extract_target_session_selection


def supplement_sales_fast_patient_text_with_marketing(
    *,
    patient_text: str,
    bound_package: TargetSpecBoundOfflineResponsePackage,
) -> str:
    """Append selected clinic-authored marketing facts once when absent from model text."""

    facts_by_id = {
        fact.id: fact for fact in bound_package.package.materials.commercial_facts
    }
    selected_fact_ids = tuple(
        ref.removeprefix("fact:")
        for ref in bound_package.package.materials.marketing_selection.selected_refs
        if ref.startswith("fact:")
    )
    if not selected_fact_ids:
        return patient_text

    text = patient_text
    for fact_id in selected_fact_ids:
        fact = facts_by_id.get(fact_id)
        if fact is None:
            continue
        fact_text = str(fact.text_fact).strip()
        if not fact_text or fact_text in text:
            continue
        separator = "\n\n" if text.strip() else ""
        text = f"{text.rstrip()}{separator}{fact_text}"
    return text


def static_sales_fast_admin_handoff(*, client_id: str) -> str:
    return fallback_answer_with_phone(
        base_text="Пожалуйста, позвоните в клинику: администратор поможет дальше.",
        client_id=client_id,
    )


def materialize_sales_fast_admin_payload(
    *,
    client_id: str,
    sid: str,
    handoff_text: str,
) -> TargetRuntimeTerminalPayload:
    return TargetRuntimeTerminalPayload(
        kind="terminal",
        payload={
            "answer": handoff_text,
            "quick_replies": [],
            "cta": None,
            "video": None,
            "situation": {"show": False, "mode": "normal"},
            "offer": None,
            "meta": {
                "client_id": client_id,
                "sid": sid,
                "intent": "content",
                "answer_path": "sales_fast",
                "service_route": "sales_fast_admin",
                "ui_source_family": "guided_fallback",
                "attribution_kind": "plain",
                "terminal_mode": "admin",
            },
        },
        terminal_mode="admin",
    )


def materialize_sales_fast_spam_payload(*, client_id: str, sid: str) -> TargetRuntimeTerminalPayload:
    return TargetRuntimeTerminalPayload(
        kind="terminal",
        payload={
            "answer": "",
            "quick_replies": [],
            "cta": None,
            "video": None,
            "situation": {"show": False, "mode": "normal"},
            "offer": None,
            "meta": {
                "client_id": client_id,
                "sid": sid,
                "intent": "content",
                "answer_path": "sales_fast",
                "service_route": "sales_fast_spam",
                "ui_source_family": "guided_fallback",
                "attribution_kind": "plain",
                "terminal_mode": "spam",
            },
        },
        terminal_mode="spam",
    )


def build_sales_fast_verified_response(
    *,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    context: TargetRuntimeClientContext,
    turn_frame: TurnFrame,
    patient_text: str,
    user_message: str,
) -> TargetVerifiedComposedResponse:
    request = materialize_target_composer_request(
        bound_package,
        context.bundle,
        context.doctor_catalog,
        context.consultation_values,
        user_message=user_message,
        md_root=context.md_root,
        client_id=context.client_id,
        response_length_profile=select_target_response_length_profile(
            bound_package.spec,
            aspects=tuple(turn_frame.aspects),
            aspects_valid=turn_frame.field_meta.aspects.status == "valid",
            marketing_scenarios=tuple(turn_frame.marketing_scenarios),
            needs_clarification=turn_frame.needs_clarification,
        ),
    )
    package_primary = bound_package.package.plan.primary_content_ref
    package_used = _used_content_refs_from_package(bound_package, request)
    verified = TargetVerifiedComposedResponse(
        text=patient_text,
        spec=bound_package.spec,
        selected_followups=bound_package.package.selected_followups,
        selected_cta_key=bound_package.selected_cta_key,
        navigation_followups=bound_package.package.navigation_followups,
        primary_content_ref=package_primary,
        used_content_refs=package_used,
    )
    return project_verified_primary_content_cta(
        verified,
        client_id=context.client_id,
        md_root=context.md_root,
    )


def materialize_sales_fast_answer_payload(
    *,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    context: TargetRuntimeClientContext,
    turn_frame: TurnFrame,
    patient_text: str,
    user_message: str,
    sid: str,
    cadence: TargetPresentationCadenceState,
    allow_situation: bool,
) -> TargetRuntimeMaterializedPayload:
    final_patient_text = supplement_sales_fast_patient_text_with_marketing(
        patient_text=patient_text,
        bound_package=bound_package,
    )
    verified = build_sales_fast_verified_response(
        bound_package=bound_package,
        context=context,
        turn_frame=turn_frame,
        patient_text=final_patient_text,
        user_message=user_message,
    )
    widget = materialize_verified_widget_payload(
        context=context,
        sid=sid,
        verified=verified,
        turn_frame=turn_frame,
        cadence=cadence,
        allow_situation=allow_situation,
    )
    payload = dict(widget.payload)
    meta = dict(payload.get("meta") or {})
    meta["answer_path"] = "sales_fast"
    meta["service_route"] = "sales_fast_materialized"
    payload["meta"] = meta
    offer = None
    materials = bound_package.package.materials
    if materials.offers:
        offer = {
            "fact_refs": list(offer_fact_refs(bound_package)),
            "amount": (
                int(materials.offers[0].price.amount)
                if materials.offers[0].price.mode == "fixed"
                and materials.offers[0].price.amount is not None
                else None
            ),
        }
    payload["offer"] = offer
    cta = build_target_runtime_widget_cta(
        client_id=context.client_id,
        selected_cta_key=verified.selected_cta_key,
    )
    if cta is not None:
        payload["cta"] = cta
    return TargetRuntimeMaterializedPayload(
        kind="materialized",
        payload=payload,
        presentation_cadence_update=widget.presentation_cadence_update,
    )


def materialize_sales_fast_terminal_from_dispatch(
    *,
    terminal: TargetTurnFrameBoundTerminalResponse,
    client_id: str,
    sid: str,
) -> TargetRuntimeTerminalPayload:
    return materialize_s41_terminal_payload(
        client_id=client_id,
        sid=sid,
        terminal=terminal,
    )


def offer_fact_refs(bound_package: TargetSpecBoundOfflineResponsePackage) -> tuple[str, ...]:
    refs: list[str] = []
    for ref in bound_package.package.materials.marketing_selection.selected_refs:
        if ref.startswith("fact:"):
            refs.append(ref)
    return tuple(refs)


def sales_fast_session_selection(
    *,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    patient_text: str,
    used_content_refs: tuple[str, ...],
) -> object:
    return extract_target_session_selection(
        bound_package,
        rendered_text=patient_text,
        used_content_refs=used_content_refs,
    )
