"""Shared living intro/closer frame around deterministic answer cards."""
from __future__ import annotations

import re

from logging_setup import get_logger, log_json

logger = get_logger("bot")

_NUMERIC_OR_MONEY_RX = re.compile(r"[\d%₽]|руб\.?", re.I | re.U)


def _strip_frame_label(text: str) -> str:
    return re.sub(
        r"^\s*(?:[-*]\s*)?(?:intro|closer|вступление|подводка|финал)\s*[:—-]\s*",
        "",
        str(text or "").strip(),
        flags=re.I | re.U,
    ).strip()


def _split_living_frame(raw: str) -> tuple[str, str] | None:
    text = (raw or "").strip()
    if not text:
        return None
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if len(paragraphs) < 2:
        paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    if len(paragraphs) < 2:
        return None
    intro = _strip_frame_label(paragraphs[0])
    closer = _strip_frame_label(paragraphs[-1])
    if not intro or not closer:
        return None
    if _NUMERIC_OR_MONEY_RX.search(intro) or _NUMERIC_OR_MONEY_RX.search(closer):
        return None
    return intro, closer


def _generate_frame_answer(*args, **kwargs):
    from llm import generate_answer_from_packet_fullctx

    return generate_answer_from_packet_fullctx(*args, **kwargs)


def compose_living_frame(
    *,
    client_id: str | None,
    patient_q: str | None,
    deterministic_card: str,
    session_id: str | None,
    enabled: bool,
) -> tuple[str, str] | None:
    if not enabled:
        return None
    q = (patient_q or "").strip()
    card = (deterministic_card or "").strip()
    if not q or not card:
        return None

    brief = (
        "Задача: написать только живое обрамление для детерминированной карточки цен.\n"
        "Верни ровно две короткие строки, каждая отдельным абзацем:\n"
        "INTRO: тёпло признай вопрос пациента и подведи к вариантам ниже.\n"
        "CLOSER: мягко предложи выбрать вариант ниже или уточнить вопрос.\n"
        "Не переписывай карточку цен и не называй никаких цифр, процентов, рублей или сумм. "
        "Цифры будут вставлены отдельно детерминированным блоком.\n\n"
        "Детерминированная карточка цен, только как факт для понимания порядка вариантов:\n"
        f"{card}"
    )
    meta = {
        "client_id": client_id,
        "composer_surface": "living_overview_frame",
    }
    try:
        answer, profile = _generate_frame_answer(
            q,
            brief,
            ["price"],
            [],
            meta,
            session_id or "",
        )
    except Exception as exc:
        log_json(
            logger,
            "living_frame_composer_failed",
            client_id=client_id,
            sid=session_id,
            err=str(exc)[:300],
        )
        return None
    if not isinstance(profile, dict) or not profile.get("composer_used"):
        log_json(
            logger,
            "living_frame_composer_fail_open",
            client_id=client_id,
            sid=session_id,
            reason="composer_not_used",
        )
        return None
    frame = _split_living_frame(answer)
    if frame is None:
        log_json(
            logger,
            "living_frame_composer_fail_open",
            client_id=client_id,
            sid=session_id,
            reason="empty_or_unsafe_frame",
        )
        return None
    return frame
