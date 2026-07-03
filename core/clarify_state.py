from __future__ import annotations

from typing import Any

from core.catalog_resolution import _md_korotko_ref
from core.service_selector_llm import _read_service_catalog

CLARIFY_ALLOW_INSTRUCTION = (
    "Если без уточнения ответ будет вслепую — вместо ответа верни clarify: один короткий дружелюбный вопрос "
    "и 2–4 service_id вариантов из каталога. Спрашивать можно ТОЛЬКО о том, что пациент сам легко знает о себе: "
    "один зуб или несколько/вся челюсть, свой зуб или уже стоит имплант, верхняя или нижняя челюсть, было ли удаление. "
    "НИКОГДА не спрашивай о том, что определяет врач: диагноз (кариес/пульпит), состояние кости или дёсен, "
    "стадию заболевания. Если варианты различит только врач — не переспрашивай: коротко расскажи про оба варианта "
    "и заверши тем, что точно определит врач на консультации. Если база позволяет полезно ответить — отвечай, не переспрашивай.\n"
    'Формат JSON в этом случае: ЛИБО {"answer": "..."} как обычно, '
    'ЛИБО {"clarify": {"question": "<короткий дружелюбный вопрос>", '
    '"option_service_ids": ["<service_id из каталога>", "..."]}} — 2–4 id, без других полей.'
)

TURN_PLANNER_PENDING_CLARIFY_INSTRUCTION = (
    "бот только что задал уточняющий вопрос {question} с вариантами {options}. "
    "Если пациент выбирает один из них (словами, номером, \"первое\") — верни его service_id. "
    "Если отвечает не на вопрос — обычный план."
)


def active_service_catalog(client_id: str | None) -> dict[str, dict[str, Any]]:
    catalog = _read_service_catalog(client_id)
    out: dict[str, dict[str, Any]] = {}
    for service_id, entry in catalog.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("active") is False:
            continue
        sid = str(service_id or "").strip()
        if sid:
            out[sid] = entry
    return out


def service_ref(entry: dict[str, Any]) -> str:
    ref = str(entry.get("md_entry_ref") or "").strip()
    return _md_korotko_ref(ref)


def validate_clarify_payload(raw: Any, *, client_id: str | None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    question = str(raw.get("question") or "").strip()
    raw_ids = raw.get("option_service_ids")
    if raw_ids is None:
        raw_ids = raw.get("option_ids")
    if not question or not isinstance(raw_ids, list):
        return None
    catalog = active_service_catalog(client_id)
    option_ids: list[str] = []
    seen: set[str] = set()
    for raw_id in raw_ids:
        sid = str(raw_id or "").strip()
        if not sid or sid in seen:
            continue
        entry = catalog.get(sid)
        if not isinstance(entry, dict):
            return None
        if not service_ref(entry):
            return None
        seen.add(sid)
        option_ids.append(sid)
    if not (2 <= len(option_ids) <= 4):
        return None
    return {"question": question, "option_service_ids": option_ids}


def pending_options_line(
    *,
    client_id: str | None,
    option_service_ids: list[str],
) -> str:
    catalog = active_service_catalog(client_id)
    labels: list[str] = []
    for idx, service_id in enumerate(option_service_ids, start=1):
        entry = catalog.get(str(service_id or "").strip())
        title = str((entry or {}).get("title") or service_id).strip()
        labels.append(f"{idx}. {service_id} ({title})")
    return "; ".join(labels)
