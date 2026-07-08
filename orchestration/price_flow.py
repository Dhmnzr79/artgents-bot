from __future__ import annotations

from typing import Any

from flask import request

from contracts.ask_orchestration import AskOrchestrationResult
from contracts.source_route_result import SourceRouteResult
from logging_setup import get_logger, log_json
from core.md_chunks import get_chunk_by_ref
from session import set_last_catalog_service
from core.price_offers import (
    build_price_answer_for_lookup,
    build_price_append_for_lookup,
    price_append_llm_hint,
)
from ux_builder import (
    build_price_concern_payload,
    build_price_lookup_payload,
    build_price_resolution_payload,
    build_price_unit_clarify_payload,
)

logger = get_logger("bot")


def _service_reply_from_price_route(
    *,
    q: str,
    sid: str,
    client_id: str,
    price_route: dict,
    decision_frame: dict[str, Any] | None,
    service_route: str,
) -> AskOrchestrationResult:
    from core.price_symptom_consult import try_price_symptom_consult_orchestration

    intent = str(price_route.get("intent") or "price_lookup")
    if intent == "price_lookup" and str(price_route.get("mode") or "") == "clarify":
        gated = try_price_symptom_consult_orchestration(
            q=q,
            sid=sid,
            client_id=client_id,
            decision_frame=decision_frame,
            price_route=price_route,
        )
        if gated is not None:
            return gated
    request.ctx["effective_intent"] = intent
    service_id = str(price_route.get("matched_service_id") or "") or None
    service = price_route.get("service") if isinstance(price_route.get("service"), dict) else {}
    if service_id:
        set_last_catalog_service(sid, service_id)
    payload = build_price_resolution_payload(
        sid=sid,
        client_id=client_id,
        intent=intent,
        resolution_reason=str(price_route.get("fallback_reason") or "service_not_found"),
        service_id=service_id,
        service=service,
        match_score=float(price_route.get("match_score") or 0.0),
        question=q,
        route_source=str(price_route.get("route_source") or "catalog"),
        price_key=price_route.get("price_key"),
        price_ref=price_route.get("price_ref"),
    )
    log_json(logger, "price_route", **payload.get("meta") or {})
    return AskOrchestrationResult(
        kind="service_reply",
        q=q,
        sid=sid,
        client_id=client_id,
        service_payload=payload,
        service_doc_id=None,
        service_track_user=True,
        service_route=service_route,
        decision_frame=decision_frame,
    )


def price_matched_from_route(
    *,
    q: str,
    sid: str,
    client_id: str,
    price_route: dict,
    decision,
    decision_frame: dict[str, Any] | None,
) -> AskOrchestrationResult:
    from core.price_symptom_consult import try_price_symptom_consult_orchestration

    gated = try_price_symptom_consult_orchestration(
        q=q,
        sid=sid,
        client_id=client_id,
        decision_frame=decision_frame,
        price_route=price_route,
    )
    if gated is not None:
        return gated
    intent = str(price_route.get("intent") or "other")
    request.ctx["effective_intent"] = str(intent)
    service = price_route.get("service") or {}
    service_id = str(price_route.get("matched_service_id") or "")
    match_score = float(price_route.get("match_score") or 0.0)
    route_source = str(price_route.get("route_source") or "catalog")
    if service_id:
        set_last_catalog_service(sid, service_id)
    if intent == "price_concern":
        concern_ref = str(service.get("concern_ref") or "").strip()
        if concern_ref:
            ch = get_chunk_by_ref(concern_ref, client_id=client_id)
            if ch:
                log_json(
                    logger,
                    "price_route",
                    intent="price_concern",
                    matched_service_id=service_id,
                    match_score=round(match_score, 4),
                    route_source="concern_ref",
                    concern_ref=concern_ref,
                    fallback_reason=None,
                )
                return AskOrchestrationResult(
                    kind="chunk",
                    q=q,
                    sid=sid,
                    client_id=client_id,
                    chosen_chunk=ch,
                    llm_question=q,
                    log_event="Answer generated from concern_ref",
                    chunk_route="price_concern",
                    matched_service_id=service_id or None,
                    decision_frame=decision_frame,
                )
        payload = build_price_concern_payload(
            sid=sid,
            client_id=client_id,
            service_id=service_id,
            service=service,
            match_score=match_score,
        )
        log_json(logger, "price_route", **payload.get("meta") or {})
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=payload,
            service_doc_id=None,
            service_track_user=True,
            service_route="price_concern",
            decision_frame=decision_frame,
        )
    if route_source == "price_ref" and price_route.get("price_ref"):
        ref_px = str(price_route.get("price_ref") or "").strip()
        price_append, offer_meta = build_price_answer_for_lookup(
            client_id=client_id,
            service_id=service_id,
            q=q,
        )
        ctx_offer_meta: dict[str, Any] | None = offer_meta if offer_meta else None
        if price_append:
            if ctx_offer_meta:
                try:
                    request.ctx["price_offer_meta"] = ctx_offer_meta
                except Exception:
                    pass
            log_json(
                logger,
                "price_route",
                intent="price_lookup",
                matched_service_id=service_id,
                match_score=round(match_score, 4),
                route_source="price_offers",
                price_key=price_route.get("price_key"),
                price_ref=ref_px,
                fallback_reason=price_route.get("fallback_reason"),
                price_answer_mode="offers_only",
                **offer_meta,
            )
            payload = build_price_lookup_payload(
                sid=sid,
                client_id=client_id,
                service_id=service_id,
                service=service if isinstance(service, dict) else {},
                match_score=match_score,
                route_source="price_offers",
                price_key=price_route.get("price_key"),
                price_ref=ref_px,
                price_item=price_route.get("price_item"),
                question=q,
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
                price_offer_meta=ctx_offer_meta,
                decision_frame=decision_frame,
            )
        ch = get_chunk_by_ref(ref_px, client_id=client_id)
        if ch:
            q0 = (q or "").strip()
            llmq = (
                f"{q0}\n\n"
                "Ответь по смыслу цены из материала ниже: что входит, этапы, от чего зависит. "
                "Без вступлений вроде «такая услуга есть», «стоимость составляет». "
                "Сразу по сути; если ниже будет блок «Точные цены» — итоговые суммы не дублируй в своём тексте."
            )
            if str(price_route.get("fallback_reason") or "") == "context_session":
                svc_ctx = price_route.get("service") if isinstance(price_route.get("service"), dict) else {}
                ttl = str(svc_ctx.get("title") or price_route.get("matched_service_id") or "").strip()
                if ttl:
                    llmq = (
                        f"{llmq}\n\n"
                        f"Контекст: пользователь продолжает вопрос об услуге «{ttl}». "
                        "Упомяни в ответе это название или короткий синоним из каталога "
                        "(например all-on-4), чтобы было ясно, о какой услуге речь."
                    )
            price_append, offer_meta = build_price_append_for_lookup(
                client_id=client_id,
                service_id=service_id,
                q=q,
            )
            ctx_offer_meta = offer_meta if offer_meta else None
            if price_append:
                llmq += price_append_llm_hint()
                if ctx_offer_meta:
                    try:
                        request.ctx["price_offer_meta"] = ctx_offer_meta
                    except Exception:
                        pass
            log_json(
                logger,
                "price_route",
                intent="price_lookup",
                matched_service_id=service_id,
                match_score=round(match_score, 4),
                route_source="price_ref",
                price_key=price_route.get("price_key"),
                price_ref=ref_px,
                fallback_reason=price_route.get("fallback_reason"),
                **offer_meta,
            )
            return AskOrchestrationResult(
                kind="chunk",
                q=q,
                sid=sid,
                client_id=client_id,
                chosen_chunk=ch,
                llm_question=llmq,
                log_event="Answer generated from price_ref",
                chunk_route="price_lookup",
                matched_service_id=service_id or None,
                generator_append_text=price_append,
                price_offer_meta=ctx_offer_meta,
                decision_frame=decision_frame,
            )
    payload = build_price_lookup_payload(
        sid=sid,
        client_id=client_id,
        service_id=service_id,
        service=service,
        match_score=match_score,
        route_source=route_source,
        price_key=price_route.get("price_key"),
        price_ref=price_route.get("price_ref"),
        price_item=price_route.get("price_item"),
        question=q,
    )
    log_json(logger, "price_route", **payload.get("meta") or {})
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


def try_a3_price_route(
    *,
    q: str,
    sid: str,
    client_id: str,
    sr: SourceRouteResult,
    decision,
    decision_frame: dict[str, Any] | None,
) -> AskOrchestrationResult | None:
    if sr.source in ("price_card", "price_ref"):
        pr_inner = (sr.payload or {}).get("price_route") if isinstance(sr.payload, dict) else None
        if isinstance(pr_inner, dict):
            return price_matched_from_route(
                q=q,
                sid=sid,
                client_id=client_id,
                price_route=pr_inner,
                decision=decision,
                decision_frame=decision_frame,
            )
    if sr.source == "price_concern" and sr.ref:
        ch = get_chunk_by_ref(sr.ref, client_id=client_id)
        if ch:
            log_json(
                logger,
                "price_route",
                intent="price_concern",
                matched_service_id=sr.service_id,
                match_score=round(float(sr.match_score or 0.0), 4),
                route_source="concern_ref",
                concern_ref=str(sr.concern_ref or sr.ref),
                fallback_reason=str(sr.match_method),
            )
            return AskOrchestrationResult(
                kind="chunk",
                q=q,
                sid=sid,
                client_id=client_id,
                chosen_chunk=ch,
                llm_question=q,
                log_event="Answer generated from concern_ref",
                chunk_route="price_concern",
                matched_service_id=sr.service_id,
                decision_frame=decision_frame,
            )
    if sr.source == "price_unavailable" and isinstance(sr.payload, dict):
        pr_uv = sr.payload.get("price_route")
        if isinstance(pr_uv, dict):
            return _service_reply_from_price_route(
                q=q,
                sid=sid,
                client_id=client_id,
                price_route=pr_uv,
                decision_frame=decision_frame,
                service_route="price_unavailable",
            )
    if sr.source == "price_lookup_clarify" and isinstance(sr.payload, dict):
        pr_cl = sr.payload.get("price_route")
        if isinstance(pr_cl, dict):
            if pr_cl.get("mode") in ("unit_clarify", "group_overview"):
                payload = build_price_unit_clarify_payload(
                    sid=sid,
                    client_id=client_id,
                    match_score=float(pr_cl.get("match_score") or 0.0),
                    group_id=str(pr_cl.get("group_id") or "implantation"),
                    q=q,
                )
                log_json(logger, "price_route", **payload.get("meta") or {})
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
            return _service_reply_from_price_route(
                q=q,
                sid=sid,
                client_id=client_id,
                price_route=pr_cl,
                decision_frame=decision_frame,
                service_route="price_lookup",
            )
    return None


def price_lookup_intent_fallback(
    *,
    q: str,
    sid: str,
    client_id: str,
    decision,
    decision_frame: dict[str, Any] | None,
    select_price_service_route,
) -> AskOrchestrationResult | None:
    price_route = select_price_service_route(
        q, client_id=client_id, sid=sid, intent_override="price_lookup"
    )
    if price_route.get("mode") in ("unit_clarify", "group_overview"):
        payload = build_price_unit_clarify_payload(
            sid=sid,
            client_id=client_id,
            match_score=float(price_route.get("match_score") or 0.0),
            group_id=str(price_route.get("group_id") or "implantation"),
            q=q,
        )
        log_json(logger, "price_route", **payload.get("meta") or {})
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
    if price_route.get("mode") == "clarify":
        return _service_reply_from_price_route(
            q=q,
            sid=sid,
            client_id=client_id,
            price_route=price_route,
            decision_frame=decision_frame,
            service_route="price_lookup",
        )
    if price_route.get("mode") == "unavailable":
        return _service_reply_from_price_route(
            q=q,
            sid=sid,
            client_id=client_id,
            price_route=price_route,
            decision_frame=decision_frame,
            service_route="price_unavailable",
        )
    if price_route.get("mode") == "matched":
        return price_matched_from_route(
            q=q,
            sid=sid,
            client_id=client_id,
            price_route=price_route,
            decision=decision,
            decision_frame=decision_frame,
        )
    return None
