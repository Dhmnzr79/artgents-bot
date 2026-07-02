"""Composer overlay before price/content routing (composer roadmap phase 3a)."""

from __future__ import annotations

from typing import Any

from config import COMPOSER_ON
from contracts.answer_packet import MaterializedCard
from contracts.ask_orchestration import AskOrchestrationResult
from contracts.answer_plan import AnswerPlan
from contracts.source_route_result import SourceRouteResult
from core.answer_packet import assemble_answer_packet
from core.answer_packet_materialize import materialize_cards
from core.answer_packet_snapshot import publish_answer_packet
from core.answer_planner import _real_aspect_count
from core.claim_gate import detect_forbidden_claims
from llm import generate_answer_from_packet


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
