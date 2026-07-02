"""LLM service selection for composer price card (SERVICE_SELECT_LLM_ON)."""

from __future__ import annotations

import json
from typing import Any

from config import SERVICE_SELECT_LLM_MODEL, SERVICE_SELECT_LLM_ON
from contracts.service_selection import ServiceSelection
from core.client_runtime import client_pack_dir
from logging_setup import get_logger, log_json, log_llm_error, log_llm_usage
from llm import LLM_REQUEST_TIMEOUT_SEC, chat_completions_create

logger = get_logger(__name__)

_SYSTEM = (
    "Ты классификатор услуги для ценового вопроса в чате стоматологии.\n"
    "Выбери ОДНУ услугу из каталога ниже, к которой относится вопрос про цену.\n"
    "Если вопрос про ГРУППУ или размытый термин (например «имплантация» без конкретного протокола) "
    "или ты не уверен — верни service_id = null.\n"
    'Ответь одним JSON: {"service_id": "<id из каталога или null>", "confidence": 0.0-1.0}. '
    "Без markdown и текста вне JSON."
)


def _read_service_catalog(client_id: str | None) -> dict[str, Any]:
    import os

    path = os.path.join(client_pack_dir(client_id), "service_catalog.json")
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _service_blurb(entry: dict[str, Any]) -> str:
    facts = entry.get("facts")
    if isinstance(facts, list):
        for raw in facts:
            text = str(raw or "").strip()
            if text:
                return text[:160]
    return ""


def build_compact_service_catalog(client_id: str | None) -> list[dict[str, str]]:
    """Active catalog rows: service_id, title, short description."""
    catalog = _read_service_catalog(client_id)
    rows: list[dict[str, str]] = []
    for sid in sorted(catalog.keys()):
        entry = catalog.get(sid)
        if not isinstance(entry, dict):
            continue
        if entry.get("active") is False:
            continue
        title = str(entry.get("title") or sid).strip()
        blurb = _service_blurb(entry)
        rows.append(
            {
                "service_id": str(sid).strip(),
                "title": title,
                "about": blurb or title,
            }
        )
    return rows


def _validate_selection(
    raw: dict[str, Any],
    *,
    allowed_ids: frozenset[str],
) -> ServiceSelection | None:
    try:
        sel = ServiceSelection.model_validate(raw)
    except Exception:
        return None
    sid = (sel.service_id or "").strip() or None
    if sid and sid not in allowed_ids:
        return ServiceSelection(service_id=None, confidence=sel.confidence)
    return ServiceSelection(service_id=sid, confidence=sel.confidence)


def classify_service(
    q: str,
    *,
    client_id: str | None,
    sid: str | None,
) -> ServiceSelection | None:
    """Pick catalog service for price aspect, or null for group/defer. None = fail-open."""
    if not SERVICE_SELECT_LLM_ON:
        return None
    msg = (q or "").strip()
    if not msg:
        return None
    rows = build_compact_service_catalog(client_id)
    if not rows:
        return None
    allowed_ids = frozenset(r["service_id"] for r in rows)
    lines = [
        f"- {r['service_id']}: {r['title']}" + (f" — {r['about']}" if r["about"] != r["title"] else "")
        for r in rows
    ]
    catalog_blob = "\n".join(lines)
    user_content = f"Каталог услуг:\n{catalog_blob}\n\nВопрос пациента:\n{msg[:900]}"
    try:
        resp = chat_completions_create(
            model=SERVICE_SELECT_LLM_MODEL,
            temperature=0,
            max_completion_tokens=120,
            response_format={"type": "json_object"},
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_content},
            ],
        )
        log_llm_usage(
            logger,
            resp,
            call_type="service_selector_classify",
            model=SERVICE_SELECT_LLM_MODEL,
        )
        raw_text = (resp.choices[0].message.content or "").strip()
        obj = json.loads(raw_text)
        if not isinstance(obj, dict):
            raise ValueError("service_selector_not_object")
        sel = _validate_selection(obj, allowed_ids=allowed_ids)
        if sel is None:
            raise ValueError("service_selector_invalid_shape")
        log_json(
            logger,
            "service_selector_llm",
            client_id=client_id,
            sid=sid,
            service_id=sel.service_id,
            confidence=sel.confidence,
        )
        return sel
    except Exception as e:
        log_llm_error(
            logger,
            call_type="service_selector_classify",
            err=str(e),
            model=SERVICE_SELECT_LLM_MODEL,
        )
        log_json(
            logger,
            "service_selector_classify_failed",
            client_id=client_id,
            sid=sid,
            err=str(e)[:300],
        )
        return None
