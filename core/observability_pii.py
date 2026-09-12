"""PII withholding for admin/PG/JSONL observability (name, phone, situation)."""
from __future__ import annotations

from core.user_text_privacy import observability_safe_bot_text, observability_safe_user_text

PII_WITHHELD_USER = "[данные заявки не хранятся]"

_LEAD_STEP_BOT_LABELS: dict[str, str] = {
    "name": "Запрос имени (данные на почте)",
    "confirm_name": "Подтверждение имени (данные на почте)",
    "phone": "Запрос телефона (данные на почте)",
    "paused": "Уточнение в процессе записи (данные на почте)",
    "done": "Заявка принята (данные на почте)",
}

_SITUATION_BOT_LABEL = "Расскажите о ситуации (текст не хранится)"
_DEFAULT_LEAD_BOT_LABEL = "Шаг заявки (данные на почте)"


def is_pii_withheld_route(route: str | None, meta: dict | None) -> bool:
    m = meta or {}
    if bool(m.get("lead_flow")) or bool(m.get("situation_collect")):
        return True
    r = (route or "").strip().lower()
    return r in {"lead_flow", "situation_collect"}


def observability_user_texts(
    q: str,
    *,
    route: str | None,
    meta: dict | None,
) -> tuple[str, str, bool]:
    """Return (user_text_redacted, user_preview_redacted, pii_withheld)."""
    if is_pii_withheld_route(route, meta):
        return PII_WITHHELD_USER, PII_WITHHELD_USER, True
    full = observability_safe_user_text(q or "", max_len=8000)
    preview = observability_safe_user_text(q or "", max_len=200)
    return full, preview, False


def observability_bot_text(
    answer: str,
    *,
    route: str | None,
    meta: dict | None,
) -> str:
    if not is_pii_withheld_route(route, meta):
        return observability_safe_bot_text(answer or "", max_len=8000)
    m = meta or {}
    if bool(m.get("situation_collect")) and not bool(m.get("lead_flow")):
        return _SITUATION_BOT_LABEL
    step = str(m.get("lead_step") or "").strip().lower()
    return _LEAD_STEP_BOT_LABELS.get(step, _DEFAULT_LEAD_BOT_LABEL)


def observability_turn_preview(
    q: str,
    *,
    route: str | None,
    meta: dict | None,
    max_len: int = 120,
) -> str:
    if is_pii_withheld_route(route, meta):
        return PII_WITHHELD_USER
    return observability_safe_user_text(q or "", max_len=max_len)


def scrub_observability_details(details: dict | None) -> dict:
    """Defense-in-depth before PG/JSONL (Developer Mode reads the same store)."""
    if not isinstance(details, dict):
        return {}
    d = dict(details)
    route = str(d.get("route") or "").lower()
    withheld = bool(d.get("pii_withheld")) or is_pii_withheld_route(
        route,
        {
            "lead_flow": d.get("lead_flow"),
            "situation_collect": d.get("situation_collect"),
        },
    )
    if withheld:
        for key in (
            "user_text_redacted",
            "user_preview_redacted",
            "preview",
            "question_preview",
            "user_text",
            "bot_text",
        ):
            if key in d:
                if key.startswith("bot"):
                    d[key] = observability_bot_text(
                        "",
                        route=route or None,
                        meta={
                            "lead_flow": d.get("lead_flow"),
                            "situation_collect": d.get("situation_collect"),
                            "lead_step": d.get("lead_step"),
                        },
                    )
                else:
                    d[key] = PII_WITHHELD_USER
        d["pii_withheld"] = True
        return d
    for key in ("preview", "question_preview", "user_text", "user_text_redacted", "user_preview_redacted"):
        if key in d and isinstance(d[key], str):
            lim = 200 if "preview" in key else 8000
            d[key] = observability_safe_user_text(d[key], max_len=lim)
    for key in ("bot_text", "bot_text_redacted"):
        if key in d and isinstance(d[key], str) and len(d[key]) > 8000:
            d[key] = d[key][:8000]
    return d


def error_turn_complete_details(
    q: str,
    *,
    fallback_reason: str,
    route: str = "error",
    meta: dict | None = None,
) -> dict:
    """Shared error-path turn_complete payload (no raw user text)."""
    pmeta = dict(meta or {})
    user_full, user_preview, withheld = observability_user_texts(
        q or "",
        route=route,
        meta=pmeta,
    )
    return {
        "turn_number": None,
        "user_text_redacted": user_full,
        "user_preview_redacted": user_preview,
        "bot_text_redacted": "",
        "intent": None,
        "doc_id": None,
        "route": route,
        "low_score": False,
        "lead_flow": bool(pmeta.get("lead_flow")),
        "situation_collect": bool(pmeta.get("situation_collect")),
        "handoff_filter": False,
        "pii_withheld": withheld,
        "answer_chars": 0,
        "latency_ms": None,
        "fallback_reason": fallback_reason,
        "effective_intent": "",
    }
