"""Промпты и вызовы OpenAI (чат); эмпатия."""
import json
import os
import re
import time

from openai import OpenAI

from core.alibaba_openai_transport_policy import (
    build_openai_compatible_client_kwargs,
    validate_alibaba_chat_transport_config,
)
from config import (
    BOOKING_INTENT_LLM_MODEL,
    BOOKING_INTENT_LLM_ON,
    CHAT_BASE_URL,
    QWEN_ENABLE_THINKING,
    chat_provider_is_qwen,
    CHAT_MODEL,
    COMPLAINT_CLASSIFY_MODEL,
    DIALOG_FOCUS_LLM_CLASSIFY_ON,
    DIALOG_FOCUS_LLM_MODEL,
    LEAD_NAME_CLASSIFY_MODEL,
    LEAD_TURN_LLM_CLASSIFY_ON,
    LEAD_TURN_LLM_MODEL,
    PATIENT_SITUATION_LLM_MODEL,
    PATIENT_SITUATION_LLM_ON,
    ASPECT_PLANNER_LLM_MODEL,
    ASPECT_PLANNER_LLM_ON,
    PRICE_INTENT_LLM_MODEL,
    PRICE_INTENT_LLM_ON,
    SAFETY_CLASSIFY_MODEL,
    SAFETY_RED_CONFIDENCE_THRESHOLD,
)
from logging_setup import get_logger, log_json, log_llm_error, log_llm_usage

_chat_client_kwargs = build_openai_compatible_client_kwargs(validate_endpoint=False)
chat_client = OpenAI(**_chat_client_kwargs)
client = chat_client

logger = get_logger("bot")

COMPOSER_FULLCTX_EMPATHY_FIRST_TOUCH = (
    "Это первое касание чувствительной темы в диалоге: начни с одной короткой "
    "человеческой фразы, снижающей напряжение, затем сразу суть."
)
COMPOSER_FULLCTX_EMPATHY_REPEAT_TOUCH = (
    "Тема уже обсуждалась — без вступительных фраз сочувствия, сразу по существу."
)


def _qwen_disable_thinking(*, model: str, kwargs: dict) -> dict:
    """DashScope Qwen only: thinking adds latency; off by default (QWEN_ENABLE_THINKING=0)."""
    extra_body = dict(kwargs.pop("extra_body", None) or {})
    if not QWEN_ENABLE_THINKING and chat_provider_is_qwen():
        extra_body.setdefault("enable_thinking", False)
    if extra_body:
        kwargs["extra_body"] = extra_body
    return kwargs


def chat_completions_create(*, model: str, **kwargs):
    """Chat completion via chat_client with Qwen-compatible extras."""
    from core.provider_call_budget import (
        record_provider_call_outcome,
        reserve_provider_call,
    )

    validate_alibaba_chat_transport_config()
    kwargs = _qwen_disable_thinking(model=model, kwargs=dict(kwargs))
    source = kwargs.pop("provider_call_source", None)
    started = time.monotonic()
    call_index = reserve_provider_call(model=model, source=source)
    try:
        response = chat_client.chat.completions.create(model=model, **kwargs)
    except Exception:
        record_provider_call_outcome(
            call_index=call_index,
            outcome="error",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        raise
    record_provider_call_outcome(
        call_index=call_index,
        outcome="ok",
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    return response
LLM_REQUEST_TIMEOUT_SEC = float(os.getenv("LLM_REQUEST_TIMEOUT_SEC", "20"))
LLM_FALLBACK_ANSWER = os.getenv(
    "LLM_FALLBACK_ANSWER",
    "Извините, сейчас есть техническая задержка. Могу повторить ответ или предложить консультацию.",
)
_DIALOG_FOCUS_GRAY_SYSTEM = (
    "Ты строгий классификатор коротких уточняющих вопросов в стоматологическом чате. "
    "У тебя есть текущая тема диалога: конкретная услуга. "
    "Задача: определить, является ли сообщение пациента нормальным уточнением по этой теме. "
    "Не выбирай маршрут, не добавляй маркетинг, не выдумывай факты. "
    "Если это уточнение по текущей теме, верни kind=follow_up и короткий query_rewrite для поиска по базе знаний. "
    "query_rewrite должен явно включать текущую услугу и смысл вопроса пациента. "
    "Если пациент явно меняет тему, просит записаться, называет другую услугу или непонятно о чем речь — верни kind=unclear. "
    'Ответь одним JSON-объектом: {"kind":"follow_up|unclear","attribute":"general","query_rewrite":"...","confidence":0.0}. '
    "Без markdown и текста вне JSON."
)

_NAME_CLASSIFY_SYSTEM = (
    "Ты классификатор короткой строки на шаге «как к вам обращаться» в чате стоматологии. "
    "Нужно решить, пригодна ли строка как личное обращение к человеку.\n"
    "Значения label:\n"
    "- valid_name — нормальное имя или обращение (имя, имя и отчество, имя и фамилия, "
    "в т.ч. латиница вроде Kai Chen).\n"
    "- invalid_name — явно не имя: вопрос по клинике/лечению, оскорбление или псевдо-фамилия для троллинга, "
    "служебный текст вместо имени.\n"
    "- unsure — формально похоже на имя (1–3 коротких слова), но смысл неоднозначен: ник, шутка, "
    "нарицательное слово как обращение (например «Рыба», «Лиса»).\n"
    'Ответь одним JSON-объектом с ключом "label" и значением ровно одним из: '
    '"valid_name", "invalid_name", "unsure". Без markdown и текста вне JSON.'
)


def classify_lead_name_shape(
    candidate: str, raw_user: str, *, client_id: str | None, sid: str
) -> str:
    """Только для строк, прошедших жёсткий предфильтр и extract_name."""
    c = (candidate or "").strip()
    r = (raw_user or "").strip()
    if not c:
        return "invalid_name"
    payload = json.dumps({"candidate": c, "original": r}, ensure_ascii=False)
    try:
        resp = chat_completions_create(
            model=LEAD_NAME_CLASSIFY_MODEL,
            temperature=0,
            max_completion_tokens=60,
            response_format={"type": "json_object"},
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=[
                {"role": "system", "content": _NAME_CLASSIFY_SYSTEM},
                {"role": "user", "content": payload},
            ],
        )
        log_llm_usage(
            logger, resp, call_type="lead_name_classify", model=LEAD_NAME_CLASSIFY_MODEL
        )
        raw = (resp.choices[0].message.content or "").strip()
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("name_classify_not_object")
        label = str(obj.get("label") or "").strip().lower()
        if label in ("valid_name", "invalid_name", "unsure"):
            log_json(
                logger,
                "lead_name_classify",
                client_id=client_id,
                sid=sid,
                label=label,
                candidate=c[:80],
            )
            return label
    except Exception as e:
        log_llm_error(
            logger, call_type="lead_name_classify", err=str(e), model=LEAD_NAME_CLASSIFY_MODEL
        )
        log_json(
            logger,
            "lead_name_classify_failed",
            client_id=client_id,
            sid=sid,
            err=str(e)[:300],
            candidate=c[:80],
        )
    return "unsure"


_BOOKING_INTENT_SYSTEM = (
    "Ты классификатор намерения в чате стоматологии. Пользователь только что написал одну реплику.\n"
    "wants_booking = true, если он явно хочет записаться на приём/консультацию, оставить заявку на связь, "
    "попросить записать его сейчас (в т.ч. с опечатками: «записатся», «зописаться», «хачу записаться»).\n"
    "wants_booking = false, если это вопрос по лечению, ценам, FAQ «как записаться / куда звонить», "
    "общая консультация без явной просьбы записать именно его, или просто болтовня.\n"
    'Ответь одним JSON-объектом с ключом "wants_booking" (boolean true или false). '
    "Без markdown и текста вне JSON."
)


def classify_booking_wants_appointment(
    user_message: str, *, client_id: str | None, sid: str
) -> bool:
    if not BOOKING_INTENT_LLM_ON:
        return False
    msg = (user_message or "").strip()
    if len(msg) < 2:
        return False
    try:
        resp = chat_completions_create(
            model=BOOKING_INTENT_LLM_MODEL,
            temperature=0,
            max_completion_tokens=40,
            response_format={"type": "json_object"},
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=[
                {"role": "system", "content": _BOOKING_INTENT_SYSTEM},
                {"role": "user", "content": msg[:600]},
            ],
        )
        log_llm_usage(
            logger, resp, call_type="booking_intent", model=BOOKING_INTENT_LLM_MODEL
        )
        raw = (resp.choices[0].message.content or "").strip()
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("booking_intent_not_object")
        wb = obj.get("wants_booking")
        out = wb is True or str(wb).lower() in ("true", "1", "yes")
        log_json(
            logger,
            "booking_intent_llm",
            client_id=client_id,
            sid=sid,
            wants_booking=out,
            msg_len=len(msg),
        )
        return out
    except Exception as e:
        log_llm_error(
            logger, call_type="booking_intent", err=str(e), model=BOOKING_INTENT_LLM_MODEL
        )
        log_json(
            logger,
            "booking_intent_llm_failed",
            client_id=client_id,
            sid=sid,
            err=str(e)[:300],
        )
        return False


_LEAD_TURN_GRAY_SYSTEM = (
    "Ты классификатор реплики пациента на шаге записи в чате стоматологии "
    "(бот спрашивает имя или телефон для записи).\n"
    "Определи намерение реплики. НЕ извлекай имя и телефон — только класс намерения.\n"
    "kind:\n"
    "- meta_cancel — отказ от записи, передумал, не хочу (в т.ч. с разговорными вставками: "
    "«Не, я передумал», «ну ладно, не буду»).\n"
    "- meta_pause — хочет сначала задать вопрос, не заполняя слот.\n"
    "- defer — нужно время подумать, не спешит, но не явный отказ.\n"
    "- content — вопрос по лечению, боли, цене, адресу, услуге (не имя).\n"
    "- unclear — непонятно / мусор / похоже на попытку имени, но сомнительно.\n"
    "content_hint (только при kind=content): price | contacts | pain | generic.\n"
    "confidence: 0.0–1.0.\n"
    'Ответь одним JSON: {"kind":"...", "content_hint": null или "price|contacts|pain|generic", '
    '"confidence": число}. Без markdown.'
)


def classify_lead_turn_gray_zone(
    user_message: str,
    *,
    lead_step: str,
    client_id: str | None,
    sid: str | None,
) -> dict | None:
    """
    Gray-zone LLM for LEAD_ACTIVE when deterministic rules did not match.
    Returns parsed dict with kind/content_hint/confidence, or None on skip/failure.
    """
    from core.routing_loader import THRESHOLDS

    if not LEAD_TURN_LLM_CLASSIFY_ON:
        return None
    msg = (user_message or "").strip()
    if len(msg) < 2:
        return None
    step = (lead_step or "collecting_name").strip()
    payload = json.dumps(
        {"message": msg[:600], "lead_step": step},
        ensure_ascii=False,
    )
    try:
        resp = chat_completions_create(
            model=LEAD_TURN_LLM_MODEL,
            temperature=0,
            max_completion_tokens=80,
            response_format={"type": "json_object"},
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=[
                {"role": "system", "content": _LEAD_TURN_GRAY_SYSTEM},
                {"role": "user", "content": payload},
            ],
        )
        log_llm_usage(
            logger, resp, call_type="lead_turn_gray", model=LEAD_TURN_LLM_MODEL
        )
        raw = (resp.choices[0].message.content or "").strip()
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("lead_turn_gray_not_object")
        kind = str(obj.get("kind") or "").strip().lower()
        allowed = {"meta_cancel", "meta_pause", "defer", "content", "unclear"}
        if kind not in allowed:
            raise ValueError(f"lead_turn_gray_bad_kind:{kind!r}")
        hint_raw = obj.get("content_hint")
        hint = None
        if hint_raw is not None and str(hint_raw).strip():
            hint = str(hint_raw).strip().lower()
            if hint not in {"price", "contacts", "pain", "generic"}:
                hint = "generic"
        conf_raw = obj.get("confidence")
        try:
            confidence = float(conf_raw)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        min_conf = float(THRESHOLDS.lead_turn.min_confidence)
        if confidence < min_conf:
            log_json(
                logger,
                "lead_turn_gray_low_confidence",
                client_id=client_id,
                sid=sid,
                kind=kind,
                confidence=confidence,
                min_confidence=min_conf,
            )
            return None
        log_json(
            logger,
            "lead_turn_gray",
            client_id=client_id,
            sid=sid,
            kind=kind,
            content_hint=hint,
            confidence=confidence,
            lead_step=step,
        )
        return {"kind": kind, "content_hint": hint, "confidence": confidence}
    except Exception as e:
        log_llm_error(
            logger,
            call_type="lead_turn_gray",
            err=str(e),
            model=LEAD_TURN_LLM_MODEL,
        )
        log_json(
            logger,
            "lead_turn_gray_failed",
            client_id=client_id,
            sid=sid,
            err=str(e)[:300],
        )
        return None


def classify_dialog_focus_gray_zone(
    user_message: str,
    *,
    focus_service_id: str,
    focus_label: str,
    focus_topic: str | None,
    client_id: str | None,
    sid: str | None,
) -> dict | None:
    """
    Gray-zone LLM for short dialog follow-ups.
    Returns parsed dict with kind/attribute/query_rewrite/confidence, or None.
    """
    if not DIALOG_FOCUS_LLM_CLASSIFY_ON:
        return None
    msg = (user_message or "").strip()
    service_id = (focus_service_id or "").strip()
    label = (focus_label or service_id).strip()
    if len(msg) < 2 or not service_id or not label:
        return None
    payload = json.dumps(
        {
            "message": msg[:600],
            "focus_service_id": service_id,
            "focus_label": label,
            "focus_topic": (focus_topic or "").strip() or None,
        },
        ensure_ascii=False,
    )
    try:
        resp = chat_completions_create(
            model=DIALOG_FOCUS_LLM_MODEL,
            temperature=0,
            max_completion_tokens=120,
            response_format={"type": "json_object"},
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=[
                {"role": "system", "content": _DIALOG_FOCUS_GRAY_SYSTEM},
                {"role": "user", "content": payload},
            ],
        )
        log_llm_usage(
            logger, resp, call_type="dialog_focus_gray", model=DIALOG_FOCUS_LLM_MODEL
        )
        raw = (resp.choices[0].message.content or "").strip()
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("dialog_focus_gray_not_object")
        kind = str(obj.get("kind") or "").strip().lower()
        if kind not in {"follow_up", "unclear"}:
            raise ValueError(f"dialog_focus_gray_bad_kind:{kind!r}")
        rewrite = str(obj.get("query_rewrite") or "").strip()
        if len(rewrite) > 300:
            rewrite = rewrite[:300].strip()
        conf_raw = obj.get("confidence")
        try:
            confidence = float(conf_raw)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        if kind != "follow_up":
            log_json(
                logger,
                "dialog_focus_gray_unclear",
                client_id=client_id,
                sid=sid,
                confidence=confidence,
            )
            return None
        if confidence < 0.72 or not rewrite:
            log_json(
                logger,
                "dialog_focus_gray_low_confidence",
                client_id=client_id,
                sid=sid,
                confidence=confidence,
                has_rewrite=bool(rewrite),
            )
            return None
        log_json(
            logger,
            "dialog_focus_gray",
            client_id=client_id,
            sid=sid,
            focus_service_id=service_id,
            confidence=confidence,
        )
        return {
            "kind": "follow_up",
            "attribute": "general",
            "query_rewrite": rewrite,
            "confidence": confidence,
        }
    except Exception as e:
        log_llm_error(
            logger,
            call_type="dialog_focus_gray",
            err=str(e),
            model=DIALOG_FOCUS_LLM_MODEL,
        )
        log_json(
            logger,
            "dialog_focus_gray_failed",
            client_id=client_id,
            sid=sid,
            err=str(e)[:300],
        )
        return None


_PATIENT_SITUATION_SYSTEM = (
    "Ты семантический классификатор ситуации пациента в стоматологическом чате. "
    "Ты НЕ отвечаешь пациенту и НЕ ставишь диагноз. Ты только заполняешь JSON-карточку смысла сообщения.\n"
    "Поля:\n"
    "- intent: choose_solution|restore|price|doctor|warranty|compare|unknown. "
    "choose_solution = человек просит подобрать/посоветовать/порекомендовать вариант, говорит что не знает что выбрать, "
    "спрашивает что лучше в его случае, как быть, что поставить. "
    "restore = человек описывает желание восстановить зубы без просьбы выбрать. "
    "Не ставь choose_solution для прямого запроса объяснить конкретную услугу: «что такое All-on-4», «расскажите про скуловую».\n"
    "- problem: missing_teeth|bone_deficit|existing_implant|urgent|generic_implant_interest|unknown.\n"
    "- extent: one_tooth|few_teeth|full_arch|unknown.\n"
    "- jaw: upper|lower|both|unknown.\n"
    "- modifiers: массив из: bone_deficit, extracted, existing_implant, urgent. Можно пустой.\n"
    "- confidence: число 0..1.\n"
    "Если явно нет всех зубов, вся челюсть, верхняя/нижняя челюсть или полный ряд — extent=full_arch. "
    "Если мало/не хватает/тонкая кость, атрофия кости, синус-лифтинг или костная пластика — добавь bone_deficit. "
    "Верни только JSON без markdown."
)


def classify_patient_situation_semantic(
    user_message: str,
    *,
    client_id: str | None,
    sid: str | None,
) -> dict | None:
    """LLM semantic patient-situation classifier. Returns parsed JSON or None."""
    if not PATIENT_SITUATION_LLM_ON:
        return None
    msg = (user_message or "").strip()
    if len(msg) < 4:
        return None
    try:
        resp = chat_completions_create(
            model=PATIENT_SITUATION_LLM_MODEL,
            temperature=0,
            max_completion_tokens=180,
            response_format={"type": "json_object"},
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=[
                {"role": "system", "content": _PATIENT_SITUATION_SYSTEM},
                {"role": "user", "content": msg[:800]},
            ],
        )
        log_llm_usage(
            logger,
            resp,
            call_type="patient_situation_classify",
            model=PATIENT_SITUATION_LLM_MODEL,
        )
        raw = (resp.choices[0].message.content or "").strip()
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("patient_situation_not_object")
        log_json(
            logger,
            "patient_situation_llm",
            client_id=client_id,
            sid=sid,
            intent=str(obj.get("intent") or "")[:40],
            problem=str(obj.get("problem") or "")[:40],
            extent=str(obj.get("extent") or "")[:40],
            jaw=str(obj.get("jaw") or "")[:40],
            confidence=obj.get("confidence"),
        )
        return obj
    except Exception as e:
        log_llm_error(
            logger,
            call_type="patient_situation_classify",
            err=str(e),
            model=PATIENT_SITUATION_LLM_MODEL,
        )
        log_json(
            logger,
            "patient_situation_classify_failed",
            client_id=client_id,
            sid=sid,
            err=str(e)[:300],
        )
        return None


_ASPECT_PLANNER_SYSTEM = (
    "Ты классификатор аспектов вопроса в стоматологическом чате. "
    "Ты НЕ отвечаешь пациенту. Ты только выбираешь подмножество аспектов из фиксированного списка.\n"
    "Допустимые аспекты:\n"
    "- price — цена, стоимость, сколько стоит/выйдет/обойдётся\n"
    "- payment — рассрочка, оплата по частям/этапам, кредит, когда платить\n"
    "- warranty — гарантия на работу/имплант/коронку\n"
    "- pain — больно ли, страшно, анестезия, обезболивание\n"
    "- included — что входит под ключ, что отдельно\n"
    "- duration — срок, длительность, сколько по времени, заживление, реабилитация\n"
    "- comparison — сравнение вариантов (что лучше, 4 или 6)\n"
    "- stages — этапы лечения, визиты, последовательность\n"
    "- overview — общий вопрос без явного аспекта выше\n"
    "Правила:\n"
    "- Верни все аспекты, о которых спрашивают в одном сообщении.\n"
    "- Не добавляй аспект, которого нет в вопросе.\n"
    "- Если вопрос только про цену — aspects=[\"price\"].\n"
    "- confidence: 0..1, насколько уверен в разметке.\n"
    "Примеры:\n"
    'Вопрос: «Сколько стоит All-on-4 и есть ли рассрочка?» → {"aspects":["price","payment"],"confidence":0.95}\n'
    'Вопрос: «Сколько стоит all-on-4, это больно и долго ли заживает?» → '
    '{"aspects":["price","pain","duration"],"confidence":0.93}\n'
    "Верни только JSON без markdown."
)


def classify_question_aspects(
    user_message: str,
    *,
    client_id: str | None,
    sid: str | None,
    context_hint: str | None = None,
) -> dict | None:
    """LLM aspect planner for composite questions. Returns parsed JSON or None."""
    if not ASPECT_PLANNER_LLM_ON:
        return None
    msg = (user_message or "").strip()
    if len(msg) < 8:
        return None
    user_payload = msg[:900]
    if (context_hint or "").strip():
        user_payload = f"{msg[:800]}\n\nКонтекст: {(context_hint or '').strip()[:200]}"
    try:
        resp = chat_completions_create(
            model=ASPECT_PLANNER_LLM_MODEL,
            temperature=0,
            max_completion_tokens=160,
            response_format={"type": "json_object"},
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=[
                {"role": "system", "content": _ASPECT_PLANNER_SYSTEM},
                {"role": "user", "content": user_payload},
            ],
        )
        log_llm_usage(
            logger,
            resp,
            call_type="aspect_planner_classify",
            model=ASPECT_PLANNER_LLM_MODEL,
        )
        raw = (resp.choices[0].message.content or "").strip()
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("aspect_planner_not_object")
        log_json(
            logger,
            "aspect_planner_llm",
            client_id=client_id,
            sid=sid,
            aspects=obj.get("aspects"),
            confidence=obj.get("confidence"),
        )
        return obj
    except Exception as e:
        log_llm_error(
            logger,
            call_type="aspect_planner_classify",
            err=str(e),
            model=ASPECT_PLANNER_LLM_MODEL,
        )
        log_json(
            logger,
            "aspect_planner_classify_failed",
            client_id=client_id,
            sid=sid,
            err=str(e)[:300],
        )
        return None


_PRICE_INTENT_SYSTEM = (
    "Ты классификатор ценового намерения в чате стоматологии. "
    "Нужно выбрать один label: "
    "price_lookup (пользователь спрашивает цену/стоимость конкретной услуги), "
    "price_concern (сомнение или возражение по цене: дорого, почему так дорого, не по карману), "
    "other (неценовой вопрос). "
    "Важно: вопросы про скидки, полис ОМС/ДМС, рассрочку, оплату по частям без жалобы «дорого» — это other. "
    'Ответь одним JSON-объектом: {"label":"price_lookup|price_concern|other"}. '
    "Без markdown и текста вне JSON."
)


def classify_price_intent(user_message: str, *, client_id: str | None, sid: str) -> str:
    from policy import continuation_only_phrase

    if not PRICE_INTENT_LLM_ON:
        return "other"
    msg = (user_message or "").strip()
    if len(msg) < 2:
        return "other"
    if continuation_only_phrase(msg):
        return "other"
    try:
        resp = chat_completions_create(
            model=PRICE_INTENT_LLM_MODEL,
            temperature=0,
            max_completion_tokens=50,
            response_format={"type": "json_object"},
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=[
                {"role": "system", "content": _PRICE_INTENT_SYSTEM},
                {"role": "user", "content": msg[:700]},
            ],
        )
        log_llm_usage(logger, resp, call_type="price_intent", model=PRICE_INTENT_LLM_MODEL)
        raw = (resp.choices[0].message.content or "").strip()
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("price_intent_not_object")
        label = str(obj.get("label") or "").strip().lower()
        if label not in {"price_lookup", "price_concern", "other"}:
            label = "other"
        log_json(
            logger,
            "price_intent_llm",
            client_id=client_id,
            sid=sid,
            label=label,
            msg_len=len(msg),
        )
        return label
    except Exception as e:
        log_llm_error(
            logger, call_type="price_intent", err=str(e), model=PRICE_INTENT_LLM_MODEL
        )
        log_json(
            logger,
            "price_intent_llm_failed",
            client_id=client_id,
            sid=sid,
            err=str(e)[:300],
        )
        return "other"


_SAFETY_CLASSIFY_SYSTEM = (
    "Ты классифицируешь сообщение пациента стоматологической клиники.\n"
    "Верни label=red только если сообщение явно описывает острое состояние:\n"
    "- сильное кровотечение или кровь не останавливается\n"
    "- травма лица/челюсти/зуба\n"
    "- отёк лица/горла/языка, трудно дышать или глотать\n"
    "- высокая температура после лечения\n"
    "- гной после процедуры\n"
    "- просьба назначить антибиотики, дозировку или схему лечения\n"
    "Не возвращай red для конверсионных страхов и сомнений: боюсь боли, страшно лечить, "
    "переживаю, что не приживётся, плохой опыт, дорого, сомневаюсь.\n"
    "Если не уверен — верни normal_sales_concern.\n"
    'Ответь JSON: {"label":"red|normal_sales_concern","confidence":0-1}. Без markdown.'
)


def classify_safety(user_message: str, *, client_id: str | None, sid: str) -> dict:
    msg = (user_message or "").strip()
    if len(msg) < 2:
        return {"label": "normal_sales_concern", "confidence": 0.0}
    try:
        resp = chat_completions_create(
            model=SAFETY_CLASSIFY_MODEL,
            temperature=0,
            max_completion_tokens=60,
            response_format={"type": "json_object"},
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=[
                {"role": "system", "content": _SAFETY_CLASSIFY_SYSTEM},
                {"role": "user", "content": msg[:700]},
            ],
        )
        log_llm_usage(logger, resp, call_type="safety_classify", model=SAFETY_CLASSIFY_MODEL)
        raw = (resp.choices[0].message.content or "").strip()
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("safety_not_object")
        label = str(obj.get("label") or "").strip().lower()
        if label not in {"red", "normal_sales_concern"}:
            label = "normal_sales_concern"
        try:
            confidence = float(obj.get("confidence"))
        except Exception:
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        log_json(
            logger,
            "safety_classify",
            client_id=client_id,
            sid=sid,
            label=label,
            confidence=round(confidence, 4),
            msg_len=len(msg),
        )
        return {"label": label, "confidence": confidence}
    except Exception as e:
        log_llm_error(
            logger, call_type="safety_classify", err=str(e), model=SAFETY_CLASSIFY_MODEL
        )
        log_json(
            logger,
            "safety_classify_failed",
            client_id=client_id,
            sid=sid,
            err=str(e)[:300],
        )
        return {"label": "normal_sales_concern", "confidence": 0.0}


_COMPLAINT_CLASSIFY_SYSTEM = (
    "Ты классифицируешь сообщение пациента стоматологической клиники.\n"
    "Верни label=complaint_or_management_contact, только если пользователь явно:\n"
    "- жалуется на вашу клинику, врача или сервис с требованием реакции,\n"
    "- просит контакт руководства/директора/главврача,\n"
    "- хочет оставить претензию или разбирательство.\n"
    "НЕ complaint: страх, что имплант не приживётся; плохой опыт в прошлом у другого врача; "
    "сомнения в приживлении; «в прошлый раз не прижился» без претензии к этой клинике.\n"
    "Во всех остальных случаях верни normal.\n"
    'Ответь JSON: {"label":"complaint_or_management_contact|normal","confidence":0-1}. Без markdown.'
)


def classify_complaint_request(user_message: str, *, client_id: str | None, sid: str) -> dict:
    msg = (user_message or "").strip()
    if len(msg) < 2:
        return {"label": "normal", "confidence": 0.0}
    try:
        resp = chat_completions_create(
            model=COMPLAINT_CLASSIFY_MODEL,
            temperature=0,
            max_completion_tokens=60,
            response_format={"type": "json_object"},
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=[
                {"role": "system", "content": _COMPLAINT_CLASSIFY_SYSTEM},
                {"role": "user", "content": msg[:700]},
            ],
        )
        log_llm_usage(logger, resp, call_type="complaint_classify", model=COMPLAINT_CLASSIFY_MODEL)
        raw = (resp.choices[0].message.content or "").strip()
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("complaint_not_object")
        label = str(obj.get("label") or "").strip().lower()
        if label not in {"complaint_or_management_contact", "normal"}:
            label = "normal"
        try:
            confidence = float(obj.get("confidence"))
        except Exception:
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        log_json(
            logger,
            "complaint_classify",
            client_id=client_id,
            sid=sid,
            label=label,
            confidence=round(confidence, 4),
            msg_len=len(msg),
        )
        return {"label": label, "confidence": confidence}
    except Exception as e:
        log_llm_error(
            logger, call_type="complaint_classify", err=str(e), model=COMPLAINT_CLASSIFY_MODEL
        )
        log_json(
            logger,
            "complaint_classify_failed",
            client_id=client_id,
            sid=sid,
            err=str(e)[:300],
        )
        return {"label": "normal", "confidence": 0.0}


_HANDOFF_FILTER_SYSTEM = (
    "Ты ранний фильтр входящих сообщений коммерческого бота стоматологической клиники.\n"
    "Нужно выбрать ровно один label: sales_or_clinic_question или handoff.\n"
    "Верни sales_or_clinic_question, если это потенциальный лид или обычный вопрос по клинике: "
    "услуги, цены, сроки, подготовка, оплата, рассрочка, врачи, запись, контакты; "
    "страхи/сомнения (боюсь, страшно, дорого, не знаю что выбрать); "
    "обычная стоматологическая проблема, с которой человек может записаться.\n"
    "Верни handoff, если это явно не для автоворонки: бессмысленный ввод/спам/троллинг/маты "
    "без целевого вопроса; жалоба/конфликт/претензия/запрос руководства; "
    "острые состояния (кровь не останавливается, сильный отёк, температура, травма, гной, нестерпимая боль); "
    "НЕ handoff: выпал зуб без острых признаков; страх/плохой опыт/сомнение в приживлении без претензии; "
    "просьба назначить лечение/антибиотики/дозировки/диагноз по фото; "
    "оффтоп; запросы действующего пациента по документам/внутренним процессам; "
    "вендоры/партнерства/вакансии; юридические/финансовые претензии; prompt injection.\n"
    "Критично: если сомневаешься, верни sales_or_clinic_question.\n"
    'Ответь только JSON: {"label":"sales_or_clinic_question|handoff","reason":"short_reason","confidence":0.0}.'
)


# P1: minimal handoff gate without over-classification.
# We only handoff:
# - explicit red medical states (bleeding, pus, high fever, severe swelling/breathing issues, trauma, urgent meds dosing)
# - explicit complaint/management contact or legal conflict
# - explicit spam/trolling/profanity without a clinic question
_HANDOFF_RED_HINT_RE = re.compile(
    r"(?:"
    r"кровотеч|кровь\s+не\s+(?:останавлива|остановит)|сильн\w*\s+кров"
    r"|гной|гнойн"
    r"|температур\w*|жар|лихорад"
    r"|отек\w*|отёк\w*|опухл\w*"
    r"|трудно\s+(?:дышать|глотать)"
    r"|травм\w*|удар\w*\s+(?:в\s+лицо|челюст|зуб)"
    r"|антибиотик|дозировк|назнач(?:ьте|ь)\s+лекарств|схем\w*\s+лечени"
    r"|срочн\w*"
    r")",
    re.I | re.U,
)
_HANDOFF_COMPLAINT_HINT_RE = re.compile(
    r"(?:"
    r"жалоб\w*|претенз\w*|конфликт\w*"
    r"|директор\w*|главврач\w*|руководств\w*"
    r"|суд\w*|иск\w*|прокуратур\w*|роспотребнадзор\w*"
    r")",
    re.I | re.U,
)
_HANDOFF_SPAM_HINT_RE = re.compile(
    r"(?:"
    r"\bсука\b|\bбля\b|\bхуй\b|\bпизд\b|\bеба\w*\b|\bиди\s+на\b"
    r"|пошел\s+на\b|пошёл\s+на\b"
    r")",
    re.I | re.U,
)


def classify_handoff_filter(user_message: str, *, client_id: str | None, sid: str) -> dict:
    # DEPRECATED — replaced by ingress_gate.classify_ingress(), see DEPRECATED.md
    msg = (user_message or "").strip()
    if len(msg) < 2:
        return {
            "label": "sales_or_clinic_question",
            "reason": "empty_or_short",
            "confidence": 0.0,
        }
    # Deterministic allow-by-default.
    # Most sales/clinic questions (including fear/concern) must NOT be handoff'ed.
    mlow = msg.lower()
    if _HANDOFF_COMPLAINT_HINT_RE.search(mlow):
        # use existing complaint classifier only for likely complaints to avoid over-triggering
        cc = classify_complaint_request(msg, client_id=client_id, sid=sid)
        if str(cc.get("label") or "").lower() == "complaint_or_management_contact" and float(
            cc.get("confidence") or 0.0
        ) >= 0.7:
            return {"label": "handoff", "reason": "complaint_or_management", "confidence": float(cc.get("confidence") or 0.7)}
        return {"label": "sales_or_clinic_question", "reason": "complaint_low_confidence", "confidence": float(cc.get("confidence") or 0.0)}
    if _HANDOFF_RED_HINT_RE.search(mlow):
        sc = classify_safety(msg, client_id=client_id, sid=sid)
        if str(sc.get("label") or "").lower() == "red" and float(sc.get("confidence") or 0.0) >= float(
            SAFETY_RED_CONFIDENCE_THRESHOLD
        ):
            return {"label": "handoff", "reason": "safety_red", "confidence": float(sc.get("confidence") or 0.8)}
        return {"label": "sales_or_clinic_question", "reason": "safety_not_red", "confidence": float(sc.get("confidence") or 0.0)}
    if _HANDOFF_SPAM_HINT_RE.search(mlow):
        return {"label": "handoff", "reason": "spam_or_profanity", "confidence": 1.0}

    # If nothing looks like a red/complaint/spam case, do not spend LLM tokens here.
    # (P1: minimal safety/complaint without over-complication.)
    return {"label": "sales_or_clinic_question", "reason": "default_allow", "confidence": 0.0}

    try:
        resp = chat_completions_create(
            model=CHAT_MODEL,
            temperature=0,
            max_completion_tokens=80,
            response_format={"type": "json_object"},
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=[
                {"role": "system", "content": _HANDOFF_FILTER_SYSTEM},
                {"role": "user", "content": msg[:1200]},
            ],
        )
        log_llm_usage(logger, resp, call_type="handoff_filter", model=CHAT_MODEL)
        raw = (resp.choices[0].message.content or "").strip()
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("handoff_filter_not_object")
        label = str(obj.get("label") or "").strip().lower()
        if label not in {"sales_or_clinic_question", "handoff"}:
            label = "sales_or_clinic_question"
        reason = str(obj.get("reason") or "").strip().lower()
        if not reason:
            reason = "unspecified"
        try:
            confidence = float(obj.get("confidence"))
        except Exception:
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        log_json(
            logger,
            "handoff_filter_classify",
            client_id=client_id,
            sid=sid,
            label=label,
            reason=reason[:64],
            confidence=round(confidence, 4),
            msg_len=len(msg),
        )
        return {"label": label, "reason": reason, "confidence": confidence}
    except Exception as e:
        log_llm_error(logger, call_type="handoff_filter", err=str(e), model=CHAT_MODEL)
        log_json(
            logger,
            "handoff_filter_classify_failed",
            client_id=client_id,
            sid=sid,
            err=str(e)[:300],
        )
        return {
            "label": "sales_or_clinic_question",
            "reason": "classifier_error",
            "confidence": 0.0,
        }


_INTENT_CLASSIFY_SYSTEM = (
    "Ты классификатор намерения пользователя в чате стоматологии. "
    "Определи intent по одному сообщению пациента.\n\n"
    "Значения intent:\n"
    "- contacts: адрес, телефон, как доехать, время работы, график\n"
    "- price_lookup: вопрос про цену или стоимость конкретной услуги\n"
    "- price_concern: сомнение по цене — дорого, почему так дорого, "
    "не по карману, у конкурентов дешевле\n"
    "- offtopic: вопрос не про клинику и не про медицинскую консультацию в рамках сервиса "
    "(например: погода, политика, стихи, программирование, общие факты вне темы)\n"
    "- content: всё остальное — услуги, врачи, процедуры, страхи, "
    "сроки, безопасность, рассрочка, противопоказания и т.д.\n\n"
    "Важно: рассрочка, полис, скидки без жалобы дорого — content.\n"
    "FAQ как записаться / куда звонить — content.\n"
    'Ответь одним JSON: {"intent": "contacts|price_lookup|'
    'price_concern|offtopic|content"}. Без markdown.'
)


def classify_intent(
    user_message: str, *, client_id: str | None, sid: str
) -> str:
    # DEPRECATED — replaced by resolver.resolve(), see DEPRECATED.md, removed in PR #2.1
    msg = (user_message or "").strip()
    if len(msg) < 2:
        return "content"
    try:
        resp = chat_completions_create(
            model=CHAT_MODEL,
            temperature=0,
            max_completion_tokens=50,
            response_format={"type": "json_object"},
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=[
                {"role": "system", "content": _INTENT_CLASSIFY_SYSTEM},
                {"role": "user", "content": msg[:700]},
            ],
        )
        log_llm_usage(logger, resp, call_type="intent_classify", model=CHAT_MODEL)
        raw = (resp.choices[0].message.content or "").strip()
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("intent_not_object")
        intent = str(obj.get("intent") or "").strip().lower()
        if intent not in {"contacts", "price_lookup", "price_concern", "offtopic", "content"}:
            intent = "content"
        log_json(
            logger, "intent_classify",
            client_id=client_id, sid=sid,
            intent=intent, msg_len=len(msg),
        )
        return intent
    except Exception as e:
        log_llm_error(logger, call_type="intent_classify", err=str(e), model=CHAT_MODEL)
        log_json(
            logger, "intent_classify_failed",
            client_id=client_id, sid=sid, err=str(e)[:300],
        )
        return "content"
