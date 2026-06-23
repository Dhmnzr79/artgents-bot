"""PriceBook group overview (S3) from manifest.json."""
from __future__ import annotations

from typing import Any

from core.price_offers import format_rub, min_offer_total
from core.pricebook_loader import load_pricebook_manifest


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
) -> tuple[str | None, list[dict[str, str]], dict[str, Any]]:
    manifest = load_pricebook_manifest(client_id)
    if not manifest:
        return None, [], {}
    group = manifest.groups.get(group_id)
    if not group or not group.members:
        return None, [], {}

    intro = (group.overview_prompt or group.label or "").strip()
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
        parts.append(section)
        parts.extend(price_lines)
    if group_id == "upper_jaw":
        parts.append("Выберите протокол ниже или уточните вопрос — на консультации покажут оба варианта по снимку.")
    elif group_id == "implantation":
        parts.append(
            "Выберите протокол ниже или уточните вопрос."
        )
    else:
        parts.append(
            "Выберите вариант ниже или уточните вопрос."
        )

    quick = group_overview_quick_replies(client_id, group_id=group_id)
    meta = {
        "pricebook_applied": True,
        "pricebook_scenario": "overview",
        "pricebook_group_id": group_id,
    }
    return "\n\n".join(p for p in parts if p), quick, meta
