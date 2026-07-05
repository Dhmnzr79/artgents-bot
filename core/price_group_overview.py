"""PriceBook group overview (S3) from manifest.json."""
from __future__ import annotations

from typing import Any

from config import LIVING_OVERVIEW_ON
from core.living_frame import compose_living_frame
from core.price_offers import format_rub, min_offer_total
from core.pricebook_loader import load_pricebook_manifest


def _static_group_overview_closer(group_id: str) -> str:
    if group_id == "upper_jaw":
        return "Выберите протокол ниже или уточните вопрос — на консультации покажут оба варианта по снимку."
    if group_id == "implantation":
        return "Выберите протокол ниже или уточните вопрос."
    return "Выберите вариант ниже или уточните вопрос."


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
        living_frame = compose_living_frame(
            client_id=client_id,
            patient_q=patient_q,
            deterministic_card=price_card,
            session_id=session_id,
            enabled=LIVING_OVERVIEW_ON,
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
