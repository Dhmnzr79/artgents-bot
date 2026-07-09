"""Price gate: symptom-only price questions → pinned consult invitation (demo/medzone)."""
from __future__ import annotations

from typing import Any

from contracts.ask_orchestration import AskOrchestrationResult
from core.client_config_loader import load_ui_bundle, price_symptom_consult_enabled
from core.explicit_service import explicit_service_mentioned
from core.patient_scope_cues import has_price_intent
from logging_setup import get_logger, log_json
from query_selector import (
    _dialog_focus_allows_price_session_context,
    _dialog_focus_for_price_route,
    catalog_service_session_context,
    match_service_from_catalog,
    price_lookup_allows_session_context,
)
from ux_builder import build_price_symptom_consult_details_payload, build_price_symptom_consult_payload

logger = get_logger("bot")

CONSULT_SYMPTOM_DETAILS_REF = "consult:symptom_price_details"


def price_query_has_session_focus(
    *,
    q: str,
    sid: str | None,
    client_id: str | None,
) -> bool:
    ctx = catalog_service_session_context(sid, client_id)
    if ctx:
        match = match_service_from_catalog(q, client_id=client_id)
        focus = _dialog_focus_for_price_route(q, sid=sid, client_id=client_id)
        if price_lookup_allows_session_context(q, match, ctx) or (
            _dialog_focus_allows_price_session_context(focus, ctx)
        ):
            return True

    from core.patient_situation_routing import price_scope_from_situation
    from core.patient_situation_session import resolve_patient_situation_for_turn
    from core.price_scope import detect_price_scope

    situation, meta = resolve_patient_situation_for_turn(
        q, sid=sid, client_id=client_id
    )
    supplemented = price_scope_from_situation(
        situation,
        client_id=client_id,
        vague_price_carry=bool(meta.get("patient_situation_carried")),
    )
    if supplemented is None:
        return False
    return detect_price_scope(q, client_id=client_id).kind == "none"


def should_gate_price_to_consult(
    *,
    q: str,
    sid: str | None,
    client_id: str | None,
    price_route: dict[str, Any] | None = None,
) -> bool:
    if not price_symptom_consult_enabled(client_id):
        return False
    if not has_price_intent(q):
        return False
    if price_route is not None:
        intent = str(price_route.get("intent") or "")
        if intent != "price_lookup":
            return False
        mode = str(price_route.get("mode") or "")
        if mode in {"group_overview", "unit_clarify", "other"}:
            return False
    if explicit_service_mentioned(q, client_id) is not None:
        return False
    if price_query_has_session_focus(q=q, sid=sid, client_id=client_id):
        return False
    return True


def build_price_symptom_consult_orchestration(
    *,
    q: str,
    sid: str,
    client_id: str,
    decision_frame: dict[str, Any] | None,
    price_route: dict[str, Any] | None = None,
) -> AskOrchestrationResult:
    payload = build_price_symptom_consult_payload(sid=sid, client_id=client_id)
    log_json(
        logger,
        "price_symptom_consult",
        client_id=client_id,
        sid=sid,
        price_mode=str((price_route or {}).get("mode") or ""),
        matched_service_id=(price_route or {}).get("matched_service_id"),
    )
    return AskOrchestrationResult(
        kind="service_reply",
        q=q,
        sid=sid,
        client_id=client_id,
        service_payload=payload,
        service_doc_id=None,
        service_track_user=True,
        service_route="price_symptom_consult",
        decision_frame=decision_frame,
    )


def try_price_symptom_consult_orchestration(
    *,
    q: str,
    sid: str,
    client_id: str,
    decision_frame: dict[str, Any] | None,
    price_route: dict[str, Any] | None = None,
) -> AskOrchestrationResult | None:
    if not should_gate_price_to_consult(
        q=q,
        sid=sid,
        client_id=client_id,
        price_route=price_route,
    ):
        return None
    return build_price_symptom_consult_orchestration(
        q=q,
        sid=sid,
        client_id=client_id,
        decision_frame=decision_frame,
        price_route=price_route,
    )


def orchestrate_consult_symptom_ref(
    ref: str,
    *,
    q: str,
    sid: str,
    client_id: str,
    decision_frame: dict[str, Any] | None = None,
) -> AskOrchestrationResult | None:
    if (ref or "").strip() != CONSULT_SYMPTOM_DETAILS_REF:
        return None
    if not price_symptom_consult_enabled(client_id):
        return None
    _ = load_ui_bundle(client_id)
    payload = build_price_symptom_consult_details_payload(sid=sid, client_id=client_id)
    return AskOrchestrationResult(
        kind="service_reply",
        q=q,
        sid=sid,
        client_id=client_id,
        service_payload=payload,
        service_doc_id=None,
        service_track_user=True,
        service_route="price_symptom_consult",
        decision_frame=decision_frame,
    )


def should_defer_price_strict_service(
    *,
    q: str,
    sid: str | None,
    client_id: str | None,
    price_route: dict[str, Any] | None = None,
) -> bool:
    """True for a price question where NO service is explicitly named -> never quote a fuzzy price."""
    from config import PRICE_STRICT_SERVICE_ON

    if not PRICE_STRICT_SERVICE_ON:
        return False
    if not has_price_intent(q):
        return False
    if price_route is not None:
        intent = str(price_route.get("intent") or "")
        if intent not in ("price_lookup", "price_concern"):
            return False
        mode = str(price_route.get("mode") or "")
        if mode in {"group_overview", "unit_clarify", "clarify", "other", "unavailable"}:
            return False
    if explicit_service_mentioned(q, client_id) is not None:
        return False
    if price_query_has_session_focus(q=q, sid=sid, client_id=client_id):
        return False
    return True


def try_price_strict_service_defer(
    *,
    q: str,
    sid: str,
    client_id: str,
    decision_frame: dict[str, Any] | None,
    price_route: dict[str, Any] | None = None,
) -> AskOrchestrationResult | None:
    """Price question with no explicitly-named service -> honest defer (policy or stub), never a fuzzy price."""
    if not should_defer_price_strict_service(
        q=q, sid=sid, client_id=client_id, price_route=price_route
    ):
        return None
    from ux_builder import build_price_resolution_payload

    payload = build_price_resolution_payload(
        sid=sid,
        client_id=client_id,
        intent="price_lookup",
        resolution_reason="service_not_found",
        question=q,
    )
    log_json(
        logger,
        "price_strict_service_defer",
        client_id=client_id,
        sid=sid,
        fuzzy_service=(price_route or {}).get("matched_service_id"),
    )
    return AskOrchestrationResult(
        kind="service_reply",
        q=q,
        sid=sid,
        client_id=client_id,
        service_payload=payload,
        service_doc_id=None,
        service_track_user=True,
        service_route="price_strict_service_defer",
        decision_frame=decision_frame,
    )
