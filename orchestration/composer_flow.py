"""Composer overlay before price/content routing (composer roadmap phase 3a)."""

from __future__ import annotations

from typing import Any

from config import COMPOSER_ON, FULLCTX_ON
from contracts.answer_packet import MaterializedCard
from contracts.ask_orchestration import AskOrchestrationResult
from contracts.answer_plan import AnswerPlan
from contracts.source_route_result import SourceRouteResult
from core.answer_packet import assemble_answer_packet
from core.answer_packet_materialize import materialize_cards, materialize_deterministic_cards
from core.answer_packet_snapshot import publish_answer_packet
from core.answer_planner import _real_aspect_count
from core.claim_gate import detect_forbidden_claims
from core.knowledge_base import assemble_client_knowledge_base
from llm import generate_answer_from_packet, generate_answer_from_packet_fullctx

_GROUP_PRICE_DEFER_MODES = frozenset({"group_overview", "unit_clarify", "clarify"})
_SPECIFIC_IMPLANT_PROTOCOL_MARKERS = (
    "классическ",
    "одномомент",
    "all-on-4",
    "all on 4",
    "all-on-6",
    "all on 6",
    "скулов",
    "синус",
    "zygomatic",
)


def _query_names_specific_implant_protocol(q: str) -> bool:
    text = (q or "").strip().lower()
    if not text:
        return False
    return any(marker in text for marker in _SPECIFIC_IMPLANT_PROTOCOL_MARKERS)


def _composer_should_defer_group_price(q: str, pr: dict) -> bool:
    mode = str(pr.get("mode") or "")
    if mode in {"unit_clarify", "clarify"}:
        return True
    if mode != "group_overview":
        return False
    from core.price_offers import is_generic_implant_price_query

    return is_generic_implant_price_query(q) and not _query_names_specific_implant_protocol(q)


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
        if _real_aspect_count(plan.aspects) < 2:
            return None
        aspects = list(plan.aspects or [])
        if "price" in aspects or "included" in aspects:
            try:
                from query_selector import select_price_service_route

                pr = select_price_service_route(
                    q,
                    client_id=client_id,
                    sid=sid,
                    intent_override="price_lookup",
                )
                if _composer_should_defer_group_price(q, pr):
                    return None
            except Exception:
                pass
        service_id = (
            str(getattr(sr, "service_id", None) or plan.service_id or "").strip() or None
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
        hits = detect_forbidden_claims(answer)
        if hits:
            return None
        publish_answer_packet(packet)
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
