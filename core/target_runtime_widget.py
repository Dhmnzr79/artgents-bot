"""Map target runtime outcomes to existing widget payload shape (S61)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.target_medical_boundary import TargetMedicalBoundaryTerminalEnforcement
from contracts.target_response_spec import TargetResponseSpec
from contracts.target_turn_frame_dispatch import (
    TargetTurnFrameBoundMaterializeResponse,
    TargetTurnFrameBoundTerminalResponse,
)
from contracts.turn_frame import TurnFrame
from core.target_client_ui_nav import TargetNavigationFollowup
from core.target_scope_aware_price_package import is_scope_aware_price_spec
from core.target_response_followup_materializer import (
    TargetContentFollowup,
    TargetPriceFollowup,
)
from core.target_response_verifier import TargetVerifiedComposedResponse
from core.target_presentation_decision import (
    TargetPresentationCadenceState,
    TargetPresentationCadenceUpdate,
    decide_target_presentation,
)
from core.target_runtime_client_context import TargetRuntimeClientContext
from core.client_config_loader import load_lead_cta_variants
from core.target_contact_authority import fallback_answer_with_phone

AttributionKind = Literal["content", "plain", "lead"]


@dataclass(frozen=True, slots=True)
class TargetRuntimeMaterializedPayload:
    kind: Literal["materialized"]
    payload: dict
    presentation_cadence_update: TargetPresentationCadenceUpdate | None = None


@dataclass(frozen=True, slots=True)
class TargetRuntimeTerminalPayload:
    kind: Literal["terminal"]
    payload: dict
    terminal_mode: str


@dataclass(frozen=True, slots=True)
class TargetRuntimeErrorPayload:
    kind: Literal["error"]
    payload: dict
    error_code: str


TargetRuntimeWidgetPayload = (
    TargetRuntimeMaterializedPayload
    | TargetRuntimeTerminalPayload
    | TargetRuntimeErrorPayload
)

_CONSULTATION_DEFER_TEXT = (
    "Чтобы ответить точнее по вашей ситуации, лучше обсудить это на консультации "
    "с администратором клиники."
)
_TECHNICAL_ERROR_TEXT = (
    "Сейчас не удалось подготовить ответ автоматически. "
    "Пожалуйста, свяжитесь с администратором клиники — он поможет."
)
_VERIFIER_BLOCK_TEXT = (
    "Сейчас я не могу надёжно сформулировать ответ по этому вопросу. "
    "Лучше уточнить детали на консультации — администратор клиники поможет."
)
_CLARIFY_TEXT = (
    "Чтобы ответить точнее, уточните, пожалуйста, о какой услуге или ситуации идёт речь."
)


def _materialized_ui_source_family(spec: TargetResponseSpec) -> str:
    if "doctors" in spec.required_components and spec.required_components == ("doctors",):
        return "doctor_navigation"
    if "price" in spec.required_components:
        return "price_navigation"
    return "md_navigation"


def _base_meta(
    *,
    client_id: str,
    sid: str,
    route: str,
    attribution_kind: AttributionKind,
    ui_source_family: str,
    **extra: object,
) -> dict:
    meta = {
        "client_id": client_id,
        "sid": sid,
        "intent": "content",
        "answer_path": "target_fullcontext",
        "service_route": route,
        "ui_source_family": ui_source_family,
        "attribution_kind": attribution_kind,
    }
    meta.update(extra)
    return meta


def _followups_to_quick_replies(
    *,
    content: tuple[TargetContentFollowup, ...],
    price: tuple[TargetPriceFollowup, ...],
) -> list[dict[str, str]]:
    quick: list[dict[str, str]] = []
    for item in content:
        quick.append({"label": item.label, "ref": item.ref})
    for item in price:
        quick.append({"label": item.label, "ref": item.ref})
    return quick


def _navigation_to_quick_replies(
    navigation: tuple[TargetNavigationFollowup, ...],
) -> list[dict[str, str]]:
    return [{"label": item.label, "ref": item.ref} for item in navigation if item.ref]


def _merge_quick_replies(
    *,
    navigation: tuple[TargetNavigationFollowup, ...],
    content: tuple[TargetContentFollowup, ...],
    price: tuple[TargetPriceFollowup, ...],
) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in _navigation_to_quick_replies(navigation):
        ref = item["ref"]
        if ref in seen:
            continue
        seen.add(ref)
        merged.append(item)
    for item in _followups_to_quick_replies(content=content, price=price):
        ref = item["ref"]
        if ref in seen:
            continue
        seen.add(ref)
        merged.append(item)
    return merged


def build_target_runtime_widget_cta(
    *,
    client_id: str,
    selected_cta_key: str | None,
) -> dict[str, str] | None:
    """Map selected target CTA key to authored client lead variant (fail-closed)."""

    key = str(selected_cta_key or "").strip()
    if not key:
        return None
    variants = {variant.key: variant for variant in load_lead_cta_variants(client_id)}
    if key not in variants:
        return None
    variant = variants[key]
    return {"text": variant.label, "action": "lead", "key": variant.key}


def materialize_verified_widget_payload(
    *,
    context: TargetRuntimeClientContext,
    sid: str,
    verified: TargetVerifiedComposedResponse,
    turn_frame: TurnFrame,
    cadence: TargetPresentationCadenceState | None = None,
    allow_situation: bool = True,
) -> TargetRuntimeMaterializedPayload:
    followups = verified.selected_followups
    presentation = decide_target_presentation(
        client_id=context.client_id,
        md_root=getattr(context, "md_root", None),
        spec=verified.spec,
        navigation_followups=verified.navigation_followups,
        selected_followups=followups,
        primary_content_ref=verified.primary_content_ref,
        cadence=cadence or TargetPresentationCadenceState(),
        allow_situation=allow_situation,
    )
    quick_replies = list(presentation.quick_replies)
    spec = verified.spec
    ui_family = _materialized_ui_source_family(spec)
    meta = _base_meta(
        client_id=context.client_id,
        sid=sid,
        route="target_fullcontext_materialized",
        attribution_kind="content",
        ui_source_family=ui_family,
        matched_service_id=turn_frame.service_id or spec.service_id,
        service_topic=turn_frame.topic or spec.scope_price_topic,
        followup_count=len(quick_replies),
        followup_source="quick_replies",
    )
    if is_scope_aware_price_spec(spec):
        meta["response_stage"] = spec.response_stage
        if spec.scope_price_topic:
            meta["scope_price_topic"] = spec.scope_price_topic
    if verified.primary_content_ref:
        meta["primary_content_ref"] = verified.primary_content_ref
    if verified.used_content_refs:
        meta["used_content_refs"] = list(verified.used_content_refs)
    if presentation.dropped:
        meta["presentation_dropped"] = list(presentation.dropped)
    cta = build_target_runtime_widget_cta(
        client_id=context.client_id,
        selected_cta_key=verified.selected_cta_key,
    )
    if verified.selected_cta_key:
        meta["cta_key"] = verified.selected_cta_key
        meta["cta_action"] = "lead"
    payload = {
        "answer": verified.text,
        "quick_replies": quick_replies,
        "cta": cta,
        "video": presentation.video,
        "situation": presentation.situation,
        "offer": None,
        "meta": meta,
    }
    return TargetRuntimeMaterializedPayload(
        kind="materialized",
        payload=payload,
        presentation_cadence_update=presentation.cadence_update,
    )


def _terminal_answer_with_phone(*, base_text: str, client_id: str) -> str:
    return fallback_answer_with_phone(base_text=base_text, client_id=client_id)


def materialize_boundary_uncertain_payload(
    *,
    client_id: str,
    sid: str,
) -> TargetRuntimeTerminalPayload:
    answer = _terminal_answer_with_phone(
        base_text=_CONSULTATION_DEFER_TEXT,
        client_id=client_id,
    )
    payload = {
        "answer": answer,
        "quick_replies": [],
        "cta": None,
        "video": None,
        "situation": {"show": False, "mode": "normal"},
        "offer": None,
        "meta": _base_meta(
            client_id=client_id,
            sid=sid,
            route="target_fullcontext_boundary_uncertain",
            attribution_kind="plain",
            ui_source_family="guided_fallback",
            terminal_mode="defer",
        ),
    }
    return TargetRuntimeTerminalPayload(
        kind="terminal",
        payload=payload,
        terminal_mode="defer",
    )


def materialize_s41_terminal_payload(
    *,
    client_id: str,
    sid: str,
    terminal: TargetTurnFrameBoundTerminalResponse,
) -> TargetRuntimeTerminalPayload:
    mode = terminal.dispatch.terminal_mode
    if mode == "clarify":
        base_answer = _CLARIFY_TEXT
    elif mode == "defer":
        base_answer = _CONSULTATION_DEFER_TEXT
    else:
        base_answer = _CONSULTATION_DEFER_TEXT
    answer = _terminal_answer_with_phone(base_text=base_answer, client_id=client_id)
    payload = {
        "answer": answer,
        "quick_replies": [],
        "cta": None,
        "video": None,
        "situation": {"show": False, "mode": "normal"},
        "offer": None,
        "meta": _base_meta(
            client_id=client_id,
            sid=sid,
            route=f"target_fullcontext_terminal_{mode}",
            attribution_kind="plain",
            ui_source_family="guided_fallback",
            terminal_mode=mode,
        ),
    }
    return TargetRuntimeTerminalPayload(kind="terminal", payload=payload, terminal_mode=mode)


def materialize_target_error_payload(
    *,
    client_id: str,
    sid: str,
    error_code: str,
    pipeline_stage: str | None = None,
    pipeline_value: object | None = None,
) -> TargetRuntimeErrorPayload:
    if error_code.startswith("target_verifier_"):
        answer = fallback_answer_with_phone(
            base_text=_VERIFIER_BLOCK_TEXT,
            client_id=client_id,
        )
        route = "target_fullcontext_verifier_blocked"
    else:
        answer = fallback_answer_with_phone(
            base_text=_TECHNICAL_ERROR_TEXT,
            client_id=client_id,
        )
        route = "target_fullcontext_error"
    meta_extra: dict[str, object] = {"target_error_code": error_code}
    if pipeline_stage is not None:
        meta_extra["pipeline_failure_stage"] = pipeline_stage
    if pipeline_value is not None:
        meta_extra["pipeline_failure_value"] = pipeline_value
    payload = {
        "answer": answer,
        "quick_replies": [],
        "cta": None,
        "video": None,
        "situation": {"show": False, "mode": "normal"},
        "offer": None,
        "meta": _base_meta(
            client_id=client_id,
            sid=sid,
            route=route,
            attribution_kind="plain",
            ui_source_family="guided_fallback",
            **meta_extra,
        ),
    }
    return TargetRuntimeErrorPayload(kind="error", payload=payload, error_code=error_code)


def widget_payload_from_runtime_result(
    *,
    client_id: str,
    sid: str,
    context: TargetRuntimeClientContext,
    result: object,
    turn_frame: TurnFrame,
    cadence: TargetPresentationCadenceState | None = None,
    allow_situation: bool = True,
) -> TargetRuntimeWidgetPayload:
    if type(result) is TargetMedicalBoundaryTerminalEnforcement:
        return materialize_boundary_uncertain_payload(client_id=client_id, sid=sid)
    if isinstance(result, TargetTurnFrameBoundTerminalResponse):
        return materialize_s41_terminal_payload(
            client_id=client_id,
            sid=sid,
            terminal=result,
        )
    if isinstance(result, TargetTurnFrameBoundMaterializeResponse):
        return materialize_verified_widget_payload(
            context=context,
            sid=sid,
            verified=result.verified,
            turn_frame=turn_frame,
            cadence=cadence,
            allow_situation=allow_situation,
        )
    return materialize_target_error_payload(
        client_id=client_id,
        sid=sid,
        error_code="target_runtime_unknown_result",
    )
