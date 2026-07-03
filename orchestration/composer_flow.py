"""Composer overlay before price/content routing (composer roadmap phase 3a)."""

from __future__ import annotations

from typing import Any

from config import CLARIFY_STATE_ON, COMPOSER_ON, FULLCTX_ON, SERVICE_SELECT_LLM_ON
from contracts.answer_packet import MaterializedCard
from contracts.ask_orchestration import AskOrchestrationResult
from contracts.answer_plan import AnswerPlan
from contracts.source_route_result import SourceRouteResult
from core.answer_packet import assemble_answer_packet
from core.answer_packet_materialize import materialize_cards, materialize_deterministic_cards
from core.answer_packet_snapshot import publish_answer_packet
from core.answer_planner import _real_aspect_count
from core.knowledge_base import assemble_client_knowledge_base
from core.service_selector_llm import classify_service
from core.turn_planner_llm import turn_plan_from_ctx
from llm import generate_answer_from_packet, generate_answer_from_packet_fullctx
from ux_builder import build_clarify_payload

_GROUP_PRICE_DEFER_MODES = frozenset({"group_overview", "unit_clarify", "clarify"})
_JAW_GROUP_PATIENT_SCOPES = frozenset({"full_jaw", "upper_jaw"})


def _query_names_specific_implant_protocol(q: str) -> bool:
    from core.patient_scope_cues import query_names_specific_implant_protocol

    return query_names_specific_implant_protocol(q)


def _composer_should_defer_group_price(q: str, pr: dict) -> bool:
    mode = str(pr.get("mode") or "")
    if mode in {"unit_clarify", "clarify"}:
        return True
    if mode != "group_overview":
        return False
    from core.price_offers import is_generic_implant_price_query

    return is_generic_implant_price_query(q) and not _query_names_specific_implant_protocol(q)


def _defer_group_price_via_price_route(
    *,
    q: str,
    client_id: str,
    sid: str,
) -> bool:
    try:
        from query_selector import select_price_service_route

        pr = select_price_service_route(
            q,
            client_id=client_id,
            sid=sid,
            intent_override="price_lookup",
        )
        return _composer_should_defer_group_price(q, pr)
    except Exception:
        return False


def _patient_scope_from_request_ctx() -> str | None:
    try:
        from flask import has_request_context, request

        if not has_request_context() or not hasattr(request, "ctx"):
            return None
        raw = request.ctx.get("patient_situation_result")
        if isinstance(raw, dict):
            scope = str(raw.get("patient_scope") or "").strip()
            return scope or None
    except Exception:
        return None
    return None


def _query_indicates_jaw_group_price_scope(q: str) -> bool:
    text = (q or "").strip()
    if not text:
        return False
    from core import patient_scope_cues as psc
    from core.price_offers import (
        is_full_jaw_implant_price_query,
        is_upper_jaw_restoration_price_query,
    )

    if is_full_jaw_implant_price_query(text) or is_upper_jaw_restoration_price_query(text):
        return True
    if not psc.has_price_intent(text):
        return False
    jaw_cue = bool(
        psc.UPPER_JAW_RX.search(text)
        or psc.FULL_ARCH_RX.search(text)
        or psc.ALL_TEETH_MISSING_RX.search(text)
        or psc.JAW_EXPLICIT_RX.search(text)
    )
    if not jaw_cue:
        return False
    return bool(psc.IMPLANT_PRICE_RX.search(text) or psc.JAW_RESTORATION_RX.search(text))


def _composer_should_defer_jaw_scope_price(q: str) -> bool:
    """Jaw/full-arch price without named protocol → price-route group overview (before LLM selector)."""
    if _query_names_specific_implant_protocol(q):
        return False
    scope = _patient_scope_from_request_ctx()
    if scope in _JAW_GROUP_PATIENT_SCOPES:
        return True
    return _query_indicates_jaw_group_price_scope(q)


def try_composer_overlay(
    *,
    q: str,
    sid: str,
    client_id: str,
    intent: str,
    plan: AnswerPlan,
    sr: SourceRouteResult,
    decision: Any,
    decision_frame: dict[str, Any] | None,
    meta: dict[str, Any] | None = None,
) -> AskOrchestrationResult | None:
    """Return composer orchestration result or None (fail-open → normal routing)."""
    _ = decision
    try:
        if not COMPOSER_ON:
            return None
        aspects = list(plan.aspects or [])
        if not FULLCTX_ON and _real_aspect_count(aspects) < 2:
            return None
        has_price_aspect = "price" in aspects or "included" in aspects
        service_id_override: str | None = None
        llm_selection_applied = False
        turn_plan = turn_plan_from_ctx()
        if turn_plan is not None:
            llm_selection_applied = True
            service_id_override = str(turn_plan.service_id or "").strip() or None
            # Только чистый price требует услугу (цена = карточка из pricebook);
            # included без услуги композер отвечает из базы (what_included FAQ).
            if "price" in aspects and service_id_override is None:
                # needs_clarify уступает defer только там, где у прайса НЕТ
                # детерминированного группового ответа (обзор имплант-протоколов
                # для «сколько стоит имплантация?» неприкосновенен — D1).
                clarify_may_ask = (
                    CLARIFY_STATE_ON
                    and bool(turn_plan.needs_clarify)
                    and not _defer_group_price_via_price_route(
                        q=q, client_id=client_id, sid=sid
                    )
                )
                if not clarify_may_ask:
                    return None

        if has_price_aspect and _composer_should_defer_jaw_scope_price(q):
            return None

        if has_price_aspect and SERVICE_SELECT_LLM_ON and turn_plan is None:
            sel = classify_service(q, client_id=client_id, sid=sid)
            if sel is not None:
                llm_selection_applied = True
                if sel.service_id is None:
                    return None
                service_id_override = str(sel.service_id).strip() or None

        if has_price_aspect and not llm_selection_applied:
            if _defer_group_price_via_price_route(q=q, client_id=client_id, sid=sid):
                return None

        if turn_plan is not None:
            # Решение планировщика окончательно: None значит «без конкретной
            # услуги», fuzzy-фолбэк не применяется (иначе возвращается баг
            # «имплантация → случайный дорогой протокол»).
            service_id = service_id_override
        else:
            service_id = (
                service_id_override
                or str(getattr(sr, "service_id", None) or plan.service_id or "").strip()
                or None
            )
        primary_chunk_ref = str(getattr(sr, "ref", None) or "").strip() or None
        route_hint = str(intent or "content").strip() or "content"
        gate_meta: dict[str, Any] = dict(meta) if isinstance(meta, dict) else {}
        gate_meta["client_id"] = client_id
        if service_id:
            gate_meta["matched_service_id"] = service_id

        packet = assemble_answer_packet(
            plan,
            client_id=client_id,
            route=route_hint,
            service_id=service_id,
            primary_chunk_ref=primary_chunk_ref,
        )
        if FULLCTX_ON:
            materialized: list[MaterializedCard] = materialize_deterministic_cards(
                packet, client_id=client_id
            )
            knowledge_base = assemble_client_knowledge_base(client_id)
            answer, profile = generate_answer_from_packet_fullctx(
                q,
                knowledge_base,
                aspects,
                materialized,
                gate_meta,
                sid,
            )
        else:
            materialized = materialize_cards(packet, client_id=client_id)
            if len(materialized) < 2:
                return None
            answer, profile = generate_answer_from_packet(q, materialized, gate_meta, sid)
        if not profile.get("composer_used"):
            return None
        publish_answer_packet(packet)
        clarify = profile.get("clarify")
        if isinstance(clarify, dict):
            question = str(clarify.get("question") or answer or "").strip()
            option_service_ids = [
                str(x or "").strip()
                for x in list(clarify.get("option_service_ids") or [])
                if str(x or "").strip()
            ]
            if question and option_service_ids:
                return AskOrchestrationResult(
                    kind="service_reply",
                    q=q,
                    sid=sid,
                    client_id=client_id,
                    service_payload=build_clarify_payload(
                        question=question,
                        option_service_ids=option_service_ids,
                        sid=sid,
                        client_id=client_id,
                    ),
                    service_doc_id=None,
                    service_track_user=True,
                    service_route="composer_clarify",
                    decision_frame=decision_frame,
                )
        return AskOrchestrationResult(
            kind="composer",
            q=q,
            sid=sid,
            client_id=client_id,
            composed_answer=answer,
            materialized_cards=materialized,
            matched_service_id=service_id,
            chunk_route=route_hint,
            decision_frame=decision_frame,
            composer_primary_chunk_ref=primary_chunk_ref,
        )
    except Exception:
        return None
