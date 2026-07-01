"""Build answer_packet snapshot from AnswerPlan (composer roadmap phase 0)."""

from __future__ import annotations

from typing import Any

from contracts.answer_packet import AnswerPacketSnapshot, PacketCard, PacketCardKind
from contracts.answer_plan import AnswerPlan, AspectKind, PlanAppendKind
from core.answer_planner import payment_terms_ref, warranty_terms_ref

_APPEND_CARD: dict[PlanAppendKind, tuple[PacketCardKind, AspectKind, str]] = {
    "price_offer": ("price", "price", "plan_append:price_offer"),
    "payment_terms": ("payment", "payment", "plan_append:payment_terms"),
    "warranty_terms": ("warranty", "warranty", "plan_append:warranty_terms"),
    "boundary": ("content", "overview", "plan_append:boundary"),
}

def build_answer_packet_snapshot(
    plan: AnswerPlan,
    *,
    apply_meta: dict[str, Any] | None = None,
    primary_chunk_ref: str | None = None,
) -> AnswerPacketSnapshot:
    """Derive packet cards from planner output (no LLM, no marketing gate yet)."""
    append_covered: set[AspectKind] = set()
    cards: list[PacketCard] = []

    for append_kind in plan.append:
        spec = _APPEND_CARD.get(append_kind)
        if spec is None:
            continue
        kind, aspect, reason = spec
        source_ref: str | None = None
        fact_id: str | None = None
        if append_kind == "price_offer":
            fact_id = plan.service_id
        elif append_kind == "payment_terms":
            source_ref = payment_terms_ref()
        elif append_kind == "warranty_terms":
            source_ref = warranty_terms_ref()
        cards.append(
            PacketCard(
                aspect=aspect,
                kind=kind,
                source_ref=source_ref,
                fact_id=fact_id,
                included_reason=reason,
            )
        )
        append_covered.add(aspect)

    for aspect in plan.aspects:
        if aspect in append_covered:
            continue
        cards.append(
            PacketCard(
                aspect=aspect,
                kind="content",
                source_ref=primary_chunk_ref if aspect in {"overview", "comparison"} else None,
                included_reason="aspect_detected",
            )
        )

    suppressed = list(plan.suppressed_append)
    if isinstance(apply_meta, dict):
        for append_kind in apply_meta.get("suppressed") or []:
            ak = str(append_kind).strip()
            if ak and ak not in suppressed:
                suppressed.append(ak)  # type: ignore[arg-type]
        applied = {str(x).strip() for x in (apply_meta.get("applied") or []) if str(x).strip()}
        for card in cards:
            append_key = _card_append_kind(card)
            if append_key and append_key in applied:
                card.included_reason = "apply_applied"
            if append_key and append_key in {str(x) for x in (apply_meta.get("suppressed") or [])}:
                card.suppressed_reason = "apply_suppressed"

    stage = "apply" if apply_meta else "plan"
    return AnswerPacketSnapshot(
        cards=cards,
        service_id=plan.service_id,
        topic=plan.topic,
        primary_aspect=plan.primary_aspect,
        plan_reason=plan.plan_reason,
        snapshot_stage=stage,
        suppressed_append=suppressed,
    )


def _card_append_kind(card: PacketCard) -> str | None:
    if card.kind == "price":
        return "price_offer"
    if card.kind == "payment":
        return "payment_terms"
    if card.kind == "warranty":
        return "warranty_terms"
    return None


def publish_answer_packet(snapshot: AnswerPacketSnapshot) -> None:
    try:
        from flask import has_request_context, request

        if has_request_context():
            request.ctx["answer_packet"] = snapshot.model_dump()
    except Exception:
        pass


def answer_packet_from_ctx() -> AnswerPacketSnapshot | None:
    try:
        from flask import has_request_context, request

        if not has_request_context():
            return None
        raw = request.ctx.get("answer_packet")
        if not isinstance(raw, dict):
            return None
        return AnswerPacketSnapshot.model_validate(raw)
    except Exception:
        return None
