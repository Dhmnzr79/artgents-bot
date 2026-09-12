"""Сборка JSON ответа /ask (одна точка сборки)."""
from __future__ import annotations

import os
import re

from meta_loader import get_doc_path


def heading_label(md_file: str, sect_id: str, client_id: str | None = None) -> str:
    if not md_file or not sect_id:
        return (sect_id or "").replace("-", " ").capitalize()
    try:
        path = get_doc_path(os.path.basename(md_file), client_id=client_id) or md_file
        with open(path, "r", encoding="utf-8-sig") as f:
            txt = f.read()
        rx3 = re.compile(
            rf"^###\s+(.*?)\s*\{{#{re.escape(sect_id)}\}}\s*$", re.M | re.I
        )
        rx2 = re.compile(
            rf"^##\s+(.*?)\s*\{{#{re.escape(sect_id)}\}}\s*$", re.M | re.I
        )
        m = rx3.search(txt) or rx2.search(txt)
        if m:
            return m.group(1).strip()
    except OSError:
        pass
    return (sect_id or "").replace("-", " ").capitalize()


def normalize_policy_payload(payload: dict) -> dict:
    """UI-level limiter: enforce screen limits; do not invent business logic."""
    dropped = []
    if not isinstance(payload, dict):
        return payload

    meta = payload.setdefault("meta", {})
    if meta.get("presentation_dropped"):
        return payload

    try:
        from policy import infer_ui_source_family

        family = infer_ui_source_family(payload)
    except Exception:
        family = str(meta.get("ui_source_family") or "md_navigation").strip().lower()

    followups = list(meta.get("followups") or [])
    if len(followups) > 2:
        dropped.append("followups_over_limit")
        meta["followups"] = followups[:2]

    refs = list(payload.get("quick_replies") or [])
    if family == "md_navigation" and len(refs) > 2:
        dropped.append("suggest_refs_over_limit")
        payload["quick_replies"] = refs[:2]

    if dropped:
        meta["ui_dropped"] = dropped
    return payload


def empty_question_response(client_id: str | None = None) -> dict:
    from core.client_config_loader import load_ui_bundle, ui_menu_to_payload

    ui = load_ui_bundle(client_id)
    return ui_menu_to_payload(
        ui.empty_question,
        sid="",
        client_id=client_id,
        extra_meta={"error": "empty_question"},
    )


def reset_session_response(sid: str) -> dict:
    return {
        "answer": "Начнём заново. Чем помочь?",
        "quick_replies": [],
        "cta": None,
        "video": None,
        "situation": {"show": False, "mode": "normal"},
        "offer": None,
        "meta": {"sid": sid},
    }


def internal_error_response(*, client_id: str | None = None) -> dict:
    from core.target_contact_authority import fallback_answer_with_phone

    base_text = "Что-то пошло не так. Попробуйте спросить ещё раз."
    resolved_client = (client_id or "").strip() or None
    if resolved_client:
        answer = fallback_answer_with_phone(base_text=base_text, client_id=resolved_client)
    else:
        answer = base_text
    return {
        "answer": answer,
        "quick_replies": [],
        "cta": None,
        "video": None,
        "situation": {"show": False, "mode": "normal"},
        "offer": None,
        "meta": {
            "error": "internal",
            "attribution_kind": "plain",
        },
    }
