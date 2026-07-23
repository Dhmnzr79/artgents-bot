"""Map target runtime outcomes to existing widget payload shape (S61)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.target_medical_boundary import TargetMedicalBoundaryTerminalEnforcement
from contracts.target_turn_frame_dispatch import (
    TargetTurnFrameBoundMaterializeResponse,
    TargetTurnFrameBoundTerminalResponse,
)
from contracts.turn_frame import TurnFrame
from core.target_response_followup_materializer import (
    TargetContentFollowup,
    TargetPriceFollowup,
)
from core.target_response_verifier import TargetVerifiedComposedResponse
from core.target_runtime_client_context import TargetRuntimeClientContext
from core.client_config_loader import load_lead_cta_variants


@dataclass(frozen=True, slots=True)
class TargetRuntimeMaterializedPayload:
    kind: Literal["materialized"]
    payload: dict


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


def _base_meta(*, client_id: str, sid: str, route: str, **extra: object) -> dict:
    meta = {
        "client_id": client_id,
        "sid": sid,
        "intent": "content",
        "answer_path": "target_fullcontext",
        "service_route": route,
        "ui_source_family": "target_fullcontext",
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
) -> TargetRuntimeMaterializedPayload:
    followups = verified.selected_followups
    quick_replies = _followups_to_quick_replies(
        content=followups.content,
        price=followups.price,
    )
    meta = _base_meta(
        client_id=context.client_id,
        sid=sid,
        route="target_fullcontext_materialized",
        matched_service_id=turn_frame.service_id,
        service_topic=turn_frame.topic,
        followups=quick_replies,
    )
    if verified.selected_cta_key:
        meta["cta_key"] = verified.selected_cta_key
        meta["cta_action"] = "lead"
    cta = build_target_runtime_widget_cta(
        client_id=context.client_id,
        selected_cta_key=verified.selected_cta_key,
    )
    payload = {
        "answer": verified.text,
        "quick_replies": quick_replies,
        "cta": cta,
        "video": None,
        "situation": {"show": False, "mode": "normal"},
        "offer": None,
        "meta": meta,
    }
    return TargetRuntimeMaterializedPayload(kind="materialized", payload=payload)


def materialize_boundary_uncertain_payload(
    *,
    client_id: str,
    sid: str,
) -> TargetRuntimeTerminalPayload:
    payload = {
        "answer": _CONSULTATION_DEFER_TEXT,
        "quick_replies": [],
        "cta": None,
        "video": None,
        "situation": {"show": False, "mode": "normal"},
        "offer": None,
        "meta": _base_meta(
            client_id=client_id,
            sid=sid,
            route="target_fullcontext_boundary_uncertain",
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
        answer = _CLARIFY_TEXT
    elif mode == "defer":
        answer = _CONSULTATION_DEFER_TEXT
    else:
        answer = _CONSULTATION_DEFER_TEXT
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
            terminal_mode=mode,
        ),
    }
    return TargetRuntimeTerminalPayload(kind="terminal", payload=payload, terminal_mode=mode)


def materialize_target_error_payload(
    *,
    client_id: str,
    sid: str,
    error_code: str,
) -> TargetRuntimeErrorPayload:
    if error_code.startswith("target_verifier_"):
        answer = _VERIFIER_BLOCK_TEXT
        route = "target_fullcontext_verifier_blocked"
    else:
        answer = _TECHNICAL_ERROR_TEXT
        route = "target_fullcontext_error"
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
            target_error_code=error_code,
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
        )
    return materialize_target_error_payload(
        client_id=client_id,
        sid=sid,
        error_code="target_runtime_unknown_result",
    )
