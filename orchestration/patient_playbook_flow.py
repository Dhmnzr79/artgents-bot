"""Patient playbook overview route — LLM answer from marketing priority context."""

from __future__ import annotations

from typing import Any

from contracts.ask_orchestration import AskOrchestrationResult
from contracts.patient_situation import PatientSituationResult
from core.patient_playbook import (
    build_patient_options_llm_question,
    build_synthetic_patient_options_chunk,
    record_patient_options_ctx,
    select_patient_options,
    should_use_patient_options_overview,
)
from logging_setup import emit_bot_event, get_logger

logger = get_logger("bot")


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

    record_patient_options_ctx(options)
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
