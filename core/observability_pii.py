"""PII withholding for admin/PG/JSONL observability (name, phone, situation)."""
from __future__ import annotations

from logging_setup import redact_text

PII_WITHHELD_USER = "[данные заявки не хранятся]"

_LEAD_STEP_BOT_LABELS: dict[str, str] = {
    "name": "Запрос имени (данные на почте)",
    "confirm_name": "Подтверждение имени (данные на почте)",
    "phone": "Запрос телефона (данные на почте)",
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
    full = redact_text(q or "", max_len=8000)
    preview = redact_text(q or "", max_len=200)
    return full, preview, False


def observability_bot_text(
    answer: str,
    *,
    route: str | None,
    meta: dict | None,
) -> str:
    if not is_pii_withheld_route(route, meta):
        return redact_text(answer or "", max_len=8000)
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
    return (q or "").strip()[:max_len]


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
    if not withheld:
        return d
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
