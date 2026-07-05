"""Widget ref `price:{service_id}` → price_lookup (PriceBook v2 step 3.5d)."""
from __future__ import annotations

from typing import Any

from contracts.ask_orchestration import AskOrchestrationResult
from logging_setup import get_logger, log_json
from orchestration.price_flow import price_matched_from_route
from query_selector import build_price_route_for_service_id
from ux_builder import build_price_aspect_payload, build_price_group_overview_payload

logger = get_logger("bot")

PRICE_REF_PREFIX = "price:"
_PRICE_ASPECTS = frozenset({"stages", "includes", "excludes"})


def parse_price_widget_ref(ref: str) -> dict[str, str | None] | None:
    """Parse `price:classic`, `price:implantation/overview`, `price:all_on_4/includes`."""
    raw = (ref or "").strip()
    if not raw.lower().startswith(PRICE_REF_PREFIX):
        return None
    tail = raw[len(PRICE_REF_PREFIX) :].strip()
    if not tail:
        return None
    if "/" in tail:
        head, aspect = tail.split("/", 1)
        head = head.strip()
        aspect = aspect.strip().lower() or None
        if head.lower() == "implantation" and aspect == "overview":
            return {"service_id": None, "group_id": "implantation", "aspect": "overview"}
        if head:
            return {"service_id": head, "group_id": None, "aspect": aspect}
        return None
    return {"service_id": tail, "group_id": None, "aspect": None}


def orchestrate_price_widget_ref(
    ref: str,
    *,
    q: str,
    sid: str,
    client_id: str,
    decision_frame: dict[str, Any] | None = None,
) -> AskOrchestrationResult | None:
    parsed = parse_price_widget_ref(ref)
    if not parsed:
        return None

    if parsed.get("group_id") == "implantation" and parsed.get("aspect") == "overview":
        payload = build_price_group_overview_payload(
            sid=sid,
            client_id=client_id,
            group_id="implantation",
            match_score=1.0,
            q=q,
        )
        if not payload:
            return None
        log_json(
            logger,
            "price_ref_route",
            ref=ref,
            route="group_overview",
            client_id=client_id,
            sid=sid,
        )
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=payload,
            service_doc_id=None,
            service_track_user=True,
            service_route="price_lookup",
            decision_frame=decision_frame,
        )

    service_id = str(parsed.get("service_id") or "").strip()
    aspect = str(parsed.get("aspect") or "").strip().lower() or None
    if not service_id:
        return None

    if aspect in _PRICE_ASPECTS:
        payload = build_price_aspect_payload(
            sid=sid,
            client_id=client_id,
            service_id=service_id,
            aspect=aspect,
            match_score=1.0,
        )
        if not payload:
            log_json(logger, "price_ref_route_miss", ref=ref, service_id=service_id, aspect=aspect)
            return None
        log_json(
            logger,
            "price_ref_route",
            ref=ref,
            service_id=service_id,
            aspect=aspect,
            route="price_aspect",
            client_id=client_id,
            sid=sid,
        )
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=payload,
            service_doc_id=None,
            service_track_user=True,
            service_route="price_lookup",
            decision_frame=decision_frame,
        )

    price_route = build_price_route_for_service_id(
        service_id,
        client_id=client_id,
        sid=sid,
        q=q,
    )
    if not price_route:
        log_json(logger, "price_ref_route_miss", ref=ref, service_id=service_id, client_id=client_id, sid=sid)
        return None

    log_json(
        logger,
        "price_ref_route",
        ref=ref,
        service_id=service_id,
        route="price_lookup",
        client_id=client_id,
        sid=sid,
    )
    question = (q or "").strip() or f"Сколько стоит {service_id.replace('_', ' ')}?"
    return price_matched_from_route(
        q=question,
        sid=sid,
        client_id=client_id,
        price_route=price_route,
        decision=None,
        decision_frame=decision_frame,
    )
