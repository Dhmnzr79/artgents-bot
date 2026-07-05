"""PriceBook group overview (S3) from manifest.json."""
from __future__ import annotations

import re
from typing import Any

from config import LIVING_OVERVIEW_ON
from logging_setup import get_logger, log_json
from core.price_offers import format_rub, min_offer_total
from core.pricebook_loader import load_pricebook_manifest

logger = get_logger("bot")

_NUMERIC_OR_MONEY_RX = re.compile(r"[\d%₽]|руб\.?", re.I | re.U)


def _static_group_overview_closer(group_id: str) -> str:
    if group_id == "upper_jaw":
        return "Выберите протокол ниже или уточните вопрос — на консультации покажут оба варианта по снимку."
    if group_id == "implantation":
        return "Выберите протокол ниже или уточните вопрос."
    return "Выберите вариант ниже или уточните вопрос."


def _strip_frame_label(text: str) -> str:
    return re.sub(
        r"^\s*(?:[-*]\s*)?(?:intro|closer|вступление|подводка|финал)\s*[:—-]\s*",
        "",
        str(text or "").strip(),
        flags=re.I | re.U,
    ).strip()


def _split_living_overview_frame(raw: str) -> tuple[str, str] | None:
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


def _generate_living_overview_answer(*args, **kwargs):
    from llm import generate_answer_from_packet_fullctx

    return generate_answer_from_packet_fullctx(*args, **kwargs)


def _compose_living_overview_frame(
    *,
    client_id: str | None,
    group_id: str,
    patient_q: str | None,
    price_card: str,
    session_id: str | None,
) -> tuple[str, str] | None:
    if not LIVING_OVERVIEW_ON:
        return None
    q = (patient_q or "").strip()
    if not q or not price_card.strip():
        return None

    brief = (
        "Задача: написать только живое обрамление для детерминированной карточки цен.\n"
        "Верни ровно две короткие строки, каждая отдельным абзацем:\n"
        "INTRO: тёпло признай вопрос пациента и подведи к вариантам ниже.\n"
        "CLOSER: мягко предложи выбрать протокол/вариант ниже или уточнить вопрос.\n"
        "Не переписывай карточку цен и не называй никаких цифр, процентов, рублей или сумм. "
        "Цифры будут вставлены отдельно детерминированным блоком.\n\n"
        "Детерминированная карточка цен, только как факт для понимания порядка вариантов:\n"
        f"{price_card}"
    )
    meta = {
        "client_id": client_id,
        "pricebook_group_id": group_id,
        "composer_surface": "living_overview_frame",
    }
    try:
        answer, profile = _generate_living_overview_answer(
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
            "living_overview_composer_failed",
            client_id=client_id,
            sid=session_id,
            group_id=group_id,
            err=str(exc)[:300],
        )
        return None
    if not isinstance(profile, dict) or not profile.get("composer_used"):
        log_json(
            logger,
            "living_overview_composer_fail_open",
            client_id=client_id,
            sid=session_id,
            group_id=group_id,
            reason="composer_not_used",
        )
        return None
    frame = _split_living_overview_frame(answer)
    if frame is None:
        log_json(
            logger,
            "living_overview_composer_fail_open",
            client_id=client_id,
            sid=session_id,
            group_id=group_id,
            reason="empty_or_unsafe_frame",
        )
        return None
    return frame


def group_overview_quick_replies(
    client_id: str | None,
    group_id: str = "implantation",
) -> list[dict[str, str]]:
    manifest = load_pricebook_manifest(client_id)
    if not manifest:
        return []
    group = manifest.groups.get(group_id)
    if not group:
        return []
    out: list[dict[str, str]] = []
    for member in group.members:
        label = str(member.label or member.service_id).strip()
        sid = str(member.service_id or "").strip()
        if label and sid:
            out.append({"label": label, "ref": f"price:{sid}"})
    return out


def build_group_overview_answer(
    client_id: str | None,
    group_id: str = "implantation",
    *,
    patient_q: str | None = None,
    session_id: str | None = None,
) -> tuple[str | None, list[dict[str, str]], dict[str, Any]]:
    manifest = load_pricebook_manifest(client_id)
    if not manifest:
        return None, [], {}
    group = manifest.groups.get(group_id)
    if not group or not group.members:
        return None, [], {}

    static_intro = (group.overview_prompt or group.label or "").strip()
    static_closer = _static_group_overview_closer(group_id)
    intro = static_intro
    closer = static_closer
    parts: list[str] = [intro] if intro else []
    price_lines: list[str] = []
    for member in group.members:
        label = str(member.label or member.service_id).strip()
        sid = str(member.service_id or "").strip()
        if not label or not sid:
            continue
        total = member.from_total
        if total is None:
            total = min_offer_total(client_id, sid, unit=member.unit_hint)
        if total is not None:
            suffix = " за челюсть" if member.unit_hint == "jaw" else ""
            price_lines.append(f"- {label} — от **{format_rub(total)}**{suffix}")
        else:
            price_lines.append(f"- {label}")

    if price_lines:
        section = "**По протоколам:**" if group_id == "implantation" else "**All-on-4 и All-on-6:**"
        price_card = "\n".join([section, *price_lines])
        living_frame = _compose_living_overview_frame(
            client_id=client_id,
            group_id=group_id,
            patient_q=patient_q,
            price_card=price_card,
            session_id=session_id,
        )
        if living_frame is not None:
            intro, closer = living_frame
            parts = [intro] if intro else []
        parts.append(section)
        parts.extend(price_lines)
    parts.append(closer)

    quick = group_overview_quick_replies(client_id, group_id=group_id)
    meta = {
        "pricebook_applied": True,
        "pricebook_scenario": "overview",
        "pricebook_group_id": group_id,
    }
    return "\n\n".join(p for p in parts if p), quick, meta
