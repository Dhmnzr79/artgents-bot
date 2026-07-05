"""Patient playbook overview route — LLM answer from marketing priority context."""

from __future__ import annotations

from typing import Any

from config import SITUATION_PRICE_ON
from contracts.ask_orchestration import AskOrchestrationResult
from contracts.patient_situation import PatientSituationResult
from core import answer_lens
from core.patient_playbook import (
    build_patient_options_llm_question,
    build_synthetic_patient_options_chunk,
    record_patient_options_ctx,
    select_patient_options,
    should_use_patient_options_overview,
)
from core.price_offers import format_rub
from logging_setup import emit_bot_event, get_logger, log_json

logger = get_logger("bot")


def _is_situation_price_intent(*, intent: str, decision: Any, situation: PatientSituationResult) -> bool:
    return (
        str(intent or "").strip() == "price_lookup"
        or str(getattr(decision, "route_intent", "") or "").strip() == "price_lookup"
        or str(getattr(getattr(situation, "cues", None), "intent", "") or "").strip() == "price"
    )


def _situation_price_quick_replies(view: answer_lens.SituationView) -> list[dict[str, str]]:
    return [
        {"label": item.node.title, "ref": f"price:{item.node.service_id}"}
        for item in view.items
        if item.node.service_id
    ]


def _build_situation_price_answer(
    *,
    hero_title: str,
    hero_price: int,
) -> str:
    return (
        "По вашей ситуации обычно сравнивают несколько вариантов лечения.\n\n"
        f"Ориентир по первому варианту — от **{format_rub(hero_price)}** ({hero_title}).\n\n"
        "Ниже можно выбрать вариант и посмотреть цену подробнее; точный план врач подтвердит на консультации."
    )


def try_patient_options_price_overview(
    *,
    q: str,
    sid: str,
    client_id: str,
    intent: str,
    decision: Any,
    situation: PatientSituationResult,
    decision_frame: dict[str, Any] | None,
) -> AskOrchestrationResult | None:
    try:
        if not SITUATION_PRICE_ON:
            return None
        if not _is_situation_price_intent(intent=intent, decision=decision, situation=situation):
            return None

        options = select_patient_options(situation, q, client_id)
        if options is None:
            return None
        view = answer_lens.situation_view(options, client_id)
        if not view.items:
            return None

        hero = view.items[0]
        hero_price_view = answer_lens.price_view(hero.node)
        hero_price = hero_price_view.min_total
        if hero_price is None:
            return None

        quick = _situation_price_quick_replies(view)
        payload = {
            "answer": _build_situation_price_answer(
                hero_title=hero.node.title,
                hero_price=hero_price,
            ),
            "quick_replies": quick,
            "cta": None,
            "video": None,
            "situation": {"show": False, "mode": "normal"},
            "offer": None,
            "meta": {
                "sid": sid,
                "client_id": client_id,
                "intent": "price_lookup",
                "matched_service_id": hero.node.service_id,
                "route_source": "patient_playbook",
                "fallback_reason": None,
                "price_status": "situation_overview",
                "pricebook_applied": True,
                "situation_kind": view.situation_kind,
                "patient_scope": view.patient_scope,
                "primary_cta": view.primary_cta,
                "strategy": view.strategy,
                "option_service_ids": [item.node.service_id for item in view.items],
                "followups": [],
                "ui_source_family": "price_navigation",
            },
        }
        log_json(
            logger,
            "situation_price_overview",
            sid=sid,
            client_id=client_id,
            situation_kind=view.situation_kind,
            patient_scope=view.patient_scope,
            hero_service_id=hero.node.service_id,
            option_service_ids=[item.node.service_id for item in view.items],
        )
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=payload,
            service_doc_id=None,
            service_track_user=True,
            service_route="situation_price_overview",
            decision_frame=decision_frame,
        )
    except Exception as exc:
        log_json(
            logger,
            "situation_price_overview_failed",
            sid=sid,
            client_id=client_id,
            err=str(exc)[:300],
        )
        return None


def try_patient_options_overview(
    *,
    q: str,
    sid: str,
    client_id: str,
    intent: str,
    decision: Any,
    situation: PatientSituationResult,
    md_catalog_priority_ref: str | None,
    decision_frame: dict[str, Any] | None,
) -> AskOrchestrationResult | None:
    if not should_use_patient_options_overview(
        q,
        situation,
        decision=decision,
        intent=intent,
        client_id=client_id,
    ):
        return None

    options = select_patient_options(situation, q, client_id)
    if options is None:
        return None

    record_patient_options_ctx(options, client_id=client_id)
    emit_bot_event(
        logger,
        "patient_options_overview",
        status="ok",
        details={
            "situation_kind": options.situation_kind,
            "patient_scope": options.patient_scope,
            "strategy": options.strategy,
            "option_service_ids": options.option_service_ids,
            "skipped_options": options.skipped_options,
            "question_preview": (q or "")[:200],
        },
    )
    return AskOrchestrationResult(
        kind="chunk",
        q=q,
        sid=sid,
        client_id=client_id,
        chosen_chunk=build_synthetic_patient_options_chunk(options, client_id=client_id),
        llm_question=build_patient_options_llm_question(user_question=q, result=options),
        log_event="Answer generated from patient_playbook (LLM options overview)",
        chunk_route="patient_options_overview",
        decision_frame=decision_frame,
    )
