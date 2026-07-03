"""Промпты и вызовы OpenAI (чат); эмпатия."""
import json
import os
import re

from openai import OpenAI

from config import (
    BOOKING_INTENT_LLM_MODEL,
    BOOKING_INTENT_LLM_ON,
    CHAT_API_KEY,
    CHAT_BASE_URL,
    CHAT_JSON_MODE,
    QWEN_ENABLE_THINKING,
    chat_provider_is_qwen,
    CHAT_MODEL,
    COMPLAINT_CLASSIFY_MODEL,
    DIALOG_FOCUS_LLM_CLASSIFY_ON,
    DIALOG_FOCUS_LLM_MODEL,
    EMPATHY_ON,
    LEAD_NAME_CLASSIFY_MODEL,
    LEAD_TURN_LLM_CLASSIFY_ON,
    LEAD_TURN_LLM_MODEL,
    MEMORY_ON,
    PATIENT_SITUATION_LLM_MODEL,
    PATIENT_SITUATION_LLM_ON,
    ASPECT_PLANNER_LLM_MODEL,
    ASPECT_PLANNER_LLM_ON,
    COMPOSER_ON,
    FULLCTX_ON,
    PRICE_INTENT_LLM_MODEL,
    PRICE_INTENT_LLM_ON,
    QUERY_REWRITE_MAX_MESSAGES,
    QUERY_REWRITE_MODEL,
    QUERY_REWRITE_ON,
    QUERY_REWRITE_VALIDATE_OVERLAP,
    REWRITE_REJECT_SUBSTRINGS,
    SAFETY_CLASSIFY_MODEL,
    SAFETY_RED_CONFIDENCE_THRESHOLD,
)
from logging_setup import get_logger, log_json, log_llm_error, log_llm_stream_usage, log_llm_usage
from meta_loader import get_doc_meta, get_doc_path
from session import (
    format_dialog_context_for_understanding,
    is_first_in_topic,
    mem_context,
    mem_get,
    recent_dialog_history,
    update_topic_empathy,
)

_chat_client_kwargs: dict = {"api_key": CHAT_API_KEY}
if CHAT_BASE_URL:
    _chat_client_kwargs["base_url"] = CHAT_BASE_URL
chat_client = OpenAI(**_chat_client_kwargs)
client = chat_client

logger = get_logger("bot")


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
    kwargs = _qwen_disable_thinking(model=model, kwargs=dict(kwargs))
    return chat_client.chat.completions.create(model=model, **kwargs)
LLM_REQUEST_TIMEOUT_SEC = float(os.getenv("LLM_REQUEST_TIMEOUT_SEC", "20"))
LLM_FALLBACK_ANSWER = os.getenv(
    "LLM_FALLBACK_ANSWER",
    "Извините, сейчас есть техническая задержка. Могу повторить ответ или предложить консультацию.",
)

_REWRITE_SYSTEM = (
    "Ты формулируешь поисковый запрос для семантического поиска по базе знаний стоматологии. "
    "По последним репликам диалога и текущему вопросу пациента напиши одну короткую строку на русском "
    "для векторного поиска (ключевые сущности: врач, процедура, симптом, зуб, материал). "
    "Не выдумывай факты: опирайся только на явное в диалоге и в текущем вопросе. "
    "Если вопрос уже самодостаточен — сожми до сути без лишних слов. "
    'Ответь одним JSON-объектом с ключом "search_query" (строка). Без markdown.'
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


def _norm_rewrite_compare(s: str) -> str:
    x = (s or "").strip().lower().replace("ё", "е")
    x = re.sub(r"[^\w\s\-]", " ", x, flags=re.U)
    return re.sub(r"\s+", " ", x).strip()


def validated_retrieval_rewrite(
    q_user: str,
    model_out: str,
    *,
    context_anchors: list[str] | None = None,
) -> tuple[str, str | None]:
    """Вернуть (эффективная строка для доп. семантики, причина отказа или None).

    Эффективная строка никогда не бывает пустой при непустом q_user."""
    from core.service_followup import (
        rewrite_overlaps_attribute_synonyms,
        rewrite_overlaps_context_anchors,
    )

    u0 = (q_user or "").strip()
    w0 = (model_out or "").strip()
    if not u0:
        return w0, None
    if not w0 or w0.lower() == u0.lower():
        return u0 if not w0 else w0, None

    wl = w0.lower()
    for marker in REWRITE_REJECT_SUBSTRINGS:
        if marker and marker in wl:
            return u0, "prompt_leak"

    if QUERY_REWRITE_VALIDATE_OVERLAP:
        if _rewrite_overlaps_user_question(u0, w0):
            return w0, None
        if rewrite_overlaps_attribute_synonyms(u0, w0):
            return w0, None
        anchors = [a for a in (context_anchors or []) if str(a).strip()]
        if anchors and rewrite_overlaps_context_anchors(w0, anchors):
            return w0, None
        return u0, "no_overlap"

    return w0, None


def _rewrite_overlaps_user_question(q_user: str, q_rewrite: str) -> bool:
    """Есть ли общая содержательная связь между исходным вопросом и переписанным запросом."""
    u = _norm_rewrite_compare(q_user)
    r = _norm_rewrite_compare(q_rewrite)
    if not u or not r:
        return True
    for tok in u.split():
        if len(tok) >= 4 and tok[:4] in r:
            return True
        if 3 <= len(tok) < 4 and tok in r.split():
            return True
    for tok in r.split():
        if len(tok) >= 4 and tok[:4] in u:
            return True
        if 3 <= len(tok) < 4 and tok in u.split():
            return True
    return False


def rewrite_query_for_retrieval(
    session_id: str, current_q: str, *, client_id: str | None = None
) -> str:
    """Переписать вопрос для retrieval с учётом последних реплик (текущий ход ещё не в hist)."""
    q0 = (current_q or "").strip()
    if not QUERY_REWRITE_ON or not q0:
        return q0
    st = mem_get(session_id)
    hist = list(st.get("hist") or [])
    if not hist:
        return q0

    from core.rewrite_policy import rewrite_skip_reason
    from core.turn_timing import set_flag, timed_stage

    skip_reason = rewrite_skip_reason(session_id, q0, client_id=client_id)
    if skip_reason:
        set_flag("rewrite_enabled", False)
        set_flag("rewrite_skipped_reason", skip_reason)
        return q0
    set_flag("rewrite_enabled", True)

    def _h2_title_for_doc(doc_id: str) -> str | None:
        if not doc_id:
            return None
        name = f"{doc_id}.md"
        path = get_doc_path(name, client_id=client_id) or get_doc_path(name)
        if not path:
            return None
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                txt = f.read()
        except OSError:
            return None
        m = re.search(r"^##\s+(.+?)\s*(?:\{\#.*?\})?\s*$", txt, flags=re.M)
        return m.group(1).strip() if m else None

    def _service_title_from_catalog(service_id: str) -> str | None:
        if not service_id:
            return None
        cid = (client_id or os.getenv("DEFAULT_CLIENT_ID") or "default").strip() or "default"
        path = os.path.join(os.path.dirname(__file__), "clients", cid, "service_catalog.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                catalog = json.load(f)
        except Exception:
            return None
        svc = catalog.get(service_id) if isinstance(catalog, dict) else None
        if isinstance(svc, dict):
            t = str(svc.get("title") or "").strip()
            return t or None
        return None

    current_doc_id = str(st.get("current_doc_id") or "").strip()
    last_service_id = str(st.get("last_catalog_service_id") or "").strip()
    topic_bits: list[str] = []
    if current_doc_id:
        fm = get_doc_meta(f"{current_doc_id}.md", client_id=client_id) or {}
        h2_title = _h2_title_for_doc(current_doc_id)
        topic_label = h2_title or str(fm.get("doc_id") or current_doc_id).replace("_", " ")
        topic_label = str(topic_label).strip()
        if topic_label:
            topic_bits.append(topic_label)
    if last_service_id:
        stitle = _service_title_from_catalog(last_service_id)
        if stitle:
            topic_bits.append(stitle)
    topic_line = f"Текущая обсуждаемая тема: {' / '.join(topic_bits[:2])}\n\n" if topic_bits else ""

    tail = hist[-QUERY_REWRITE_MAX_MESSAGES:]
    dialog_lines = [f"{m.get('role', '?')}: {m.get('content', '')}" for m in tail]
    dialog_block = "\n".join(dialog_lines)
    user_block = (
        topic_line
        + "Последние реплики диалога:\n"
        f"{dialog_block}\n\n"
        "Текущий вопрос пациента:\n"
        f"{q0}"
    )
    try:
        with timed_stage("rewrite_ms"):
            resp = chat_completions_create(
                model=QUERY_REWRITE_MODEL,
                max_completion_tokens=200,
                response_format={"type": "json_object"},
                timeout=LLM_REQUEST_TIMEOUT_SEC,
                messages=[
                    {"role": "system", "content": _REWRITE_SYSTEM},
                    {"role": "user", "content": user_block},
                ],
            )
        log_llm_usage(
            logger, resp, call_type="retrieval_query_rewrite", model=QUERY_REWRITE_MODEL
        )
        raw = (resp.choices[0].message.content or "").strip()
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("rewrite_not_object")
        sq = obj.get("search_query")
        if sq is None and "query" in obj:
            sq = obj.get("query")
        out = str(sq).strip() if sq is not None else ""
        if not out or len(out) > 600:
            raise ValueError("rewrite_empty_or_long")
        context_anchors = []
        if last_service_id:
            context_anchors.append(last_service_id)
        if last_service_id:
            stitle_for_val = _service_title_from_catalog(last_service_id)
            if stitle_for_val:
                context_anchors.append(stitle_for_val)
        context_anchors.extend(topic_bits[:2])
        effective, reject_reason = validated_retrieval_rewrite(
            q0,
            out,
            context_anchors=context_anchors,
        )
        if reject_reason:
            log_json(
                logger,
                "retrieval_query_rewrite_rejected",
                client_id=client_id,
                sid=session_id,
                model_used=QUERY_REWRITE_MODEL,
                query_raw=q0[:200],
                model_out=out[:200],
                reason=reject_reason,
                effective=effective[:200],
            )
        rewrite_applied = effective.lower() != q0.lower()
        log_json(
            logger,
            "retrieval_query_rewrite",
            client_id=client_id,
            sid=session_id,
            model_used=QUERY_REWRITE_MODEL,
            query_raw=q0[:200],
            query_for_retrieval=effective[:200],
            rewrite_applied=rewrite_applied,
            model_raw_before_validate=out[:200] if reject_reason else None,
        )
        return effective
    except Exception as e:
        log_llm_error(
            logger,
            call_type="retrieval_query_rewrite",
            err=str(e),
            model=QUERY_REWRITE_MODEL,
        )
        log_json(
            logger,
            "retrieval_query_rewrite_failed",
            client_id=client_id,
            sid=session_id,
            model_used=QUERY_REWRITE_MODEL,
            query_raw=q0[:200],
            err=str(e)[:300],
        )
        return q0


_FACTS_CARD_SYSTEM = (
    "Ты помощник стоматологической клиники. "
    "Тебе дан вопрос пациента, название услуги и список фактов о ней. "
    "Напиши живой разговорный ответ — 2-3 предложения. "
    "Правила: ответь именно на вопрос пациента (если спрашивает 'делаете ли?' — сначала подтверди одним словом); "
    "используй ТОЛЬКО факты из списка, ничего не добавляй от себя; "
    "все цифры и числовые показатели из фактов обязательно сохрани; "
    "не перечисляй факты списком — пиши текстом; "
    "тон спокойный и доброжелательный, без канцелярита. "
    'Ответь одним JSON-объектом с ключом "answer".'
)


def generate_facts_card_answer(
    title: str,
    facts: list[str],
    *,
    sid: str,
    client_id: str | None,
    user_question: str = "",
    consult_nudge: str | None = None,
) -> str | None:
    if not facts:
        return None
    from core.consult_nudge import consult_nudge_prompt_addon

    system = _FACTS_CARD_SYSTEM + consult_nudge_prompt_addon(
        consult_nudge,  # type: ignore[arg-type]
        client_id=client_id,
    )
    facts_block = "\n".join(f"- {f}" for f in facts)
    q_line = f"Вопрос пациента: {user_question}\n\n" if user_question else ""
    user_msg = f"{q_line}Услуга: {title}\n\nФакты:\n{facts_block}"
    try:
        resp = chat_completions_create(
            model=CHAT_MODEL,
            temperature=0.2,
            max_completion_tokens=300,
            response_format={"type": "json_object"},
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
        )
        log_llm_usage(logger, resp, call_type="facts_card", model=CHAT_MODEL)
        raw = (resp.choices[0].message.content or "").strip()
        obj = json.loads(raw)
        answer = str(obj.get("answer") or "").strip()
        if answer:
            log_json(logger, "facts_card_llm", client_id=client_id, sid=sid, title=title)
            return answer
    except Exception as exc:
        log_llm_error(logger, call_type="facts_card", err=str(exc), model=CHAT_MODEL)
        log_json(logger, "facts_card_llm_error", client_id=client_id, sid=sid, error=str(exc))
    return None


from core.llm_system_prompt import build_base_system
# См. docs/WIDGET_ANSWER_FORMAT.md — контракт с виджетом.
RESPONSE_FORMAT = (
    "\n\nФормат текста ответа (виджет чата, см. WIDGET_ANSWER_FORMAT):\n"
    "Используй безопасный поднабор Markdown в тексте для пациента.\n"
    "Разрешено: короткие абзацы (между абзацами — пустая строка); списки «- пункт»; "
    "нумерованные «1. пункт»; выделение **только** для сумм с ₽, процентов, сроков "
    "(например **3–6 месяцев**, **1 год**), **Этап 1** / **Этап 2**, слова **пожизненная**.\n"
    "Нельзя выделять **бренды**, названия систем, заголовки пунктов и обычные слова.\n"
    "В списке цен формат: Implantium (Южная Корея) — **76 200 ₽** (жирным только цена).\n"
    "Запрещено: заголовки #, ссылки, HTML, вложенные списки, таблицы, "
    "символы галочки или • вручную.\n"
    "Структура: максимум одна короткая вводная фраза (или сразу суть); "
    "список только если 3+ однотипных пункта (цены, шаги, варианты); "
    "1–2 факта — связным абзацем, не списком.\n"
    "Обязательно: если в ответе есть список, сначала дай одну короткую вводную фразу "
    "по смыслу связанную со списком (цены, этапы, варианты), уже потом список. "
    "Никогда не начинай ответ сразу со списка.\n"
    "Первый символ ответа не должен быть маркером списка: «-», «•», «1.» — "
    "сначала хотя бы одно предложение вводного текста.\n"
    "Не копируй служебную разметку источника. Не заканчивай ответ предложением "
    "продолжить тему — это делают кнопки интерфейса."
)

def _consult_nudge_addon(meta: dict) -> str:
    from core.consult_nudge import consult_nudge_prompt_addon

    return consult_nudge_prompt_addon(
        meta.get("consult_nudge"),
        client_id=meta.get("client_id"),
    )


GENERATOR_SINGLE_SOURCE_RULE = (
    "\n\n"
    "Факты, числа, сроки, гарантии и цены бери только из единственного блока источника ниже "
    "(поле материала клиники) или из явно переданных structured facts в том же сообщении.\n\n"
    "Не используй историю диалога и любой контекст вне этого блока как источник фактов. "
    "Они нужны только для того, чтобы понять, о чем именно спрашивает пользователь "
    "и как лучше сформулировать ответ."
)

COMPOSER_TRUTH_STYLE_RULE = (
    "Пиши ЖИВЫМ, естественным языком — перефразируй и вплетай куски в один связный ответ, "
    "как говорил бы внимательный консультант. Это НЕ дословное цитирование.\n"
    "НО: факты, цифры и конкретные утверждения — СТРОГО из источника (база знаний / карточки ниже):\n"
    "- не выдумывай фактов, которых в источнике нет;\n"
    "- не меняй числа (проценты, суммы, сроки, гарантии) — переноси их дословно "
    "(99,8% остаётся 99,8%, а не «почти 100%»);\n"
    "- не добавляй утверждений, которых в источнике нет, и не смягчай/не усиливай то, что есть.\n"
    "Смысл источника доноси точно, слова — свои, живые.\n"
    "Если в источнике «без боли, лёгкий дискомфорт» — донеси именно этот смысл своими словами."
)

COMPOSER_PACKET_RULE = (
    "\n\n"
    "Собери ОДИН связный ответ из разрешённых карточек ниже, В ПОРЯДКЕ их следования.\n"
    f"{COMPOSER_TRUTH_STYLE_RULE}\n"
    "ЦЕНОВОЙ ФАКТБЛОК (помечен ДОСЛОВНО) воспроизведи дословно: суммы, единицу, список «входит» — "
    "не меняй, не округляй, не дописывай и не выкидывай пункты.\n"
    "Вплетай естественно, без шва между темами. Приглашений и CTA не добавляй — их добавит интерфейс."
)

COMPOSER_FULLCTX_NO_KB_ANSWER_RULE = (
    "Если в базе знаний нет ответа на вопрос пациента — не выдумывай и не отвечай из общих знаний. "
    "Скажи об этом легко и по-человечески, без извинений и канцелярита: короткая честная фраза, "
    "что такой детали в твоих материалах нет, и сразу — полезный следующий шаг. "
    "Если в базе есть смежная информация, которая частично помогает — дай её "
    "(\"точных цифр по этому у меня нет, но вот что важно знать...\"). "
    "Заверши мыслью, что такие вещи быстрее всего уточнить у администратора или врача на консультации — "
    "тёпло, без давления. Кнопки записи добавит интерфейс — не дублируй призыв текстом дважды.\n"
)

COMPOSER_FULLCTX_RULE = (
    "\n\n"
    + COMPOSER_FULLCTX_NO_KB_ANSWER_RULE
    + "\n\n"
    "Собери ОДИН связный ответ по вопросу пациента.\n"
    "Медицинские и информационные факты — из базы знаний клиники ниже.\n"
    f"{COMPOSER_TRUTH_STYLE_RULE}\n"
    "Цены и промо — ТОЛЬКО из разрешённых карточек; "
    "ценовой фактблок (помечен ДОСЛОВНО) воспроизведи дословно: суммы, единицу, список «входит» — "
    "не меняй, не округляй, не дописывай и не выкидывай пункты.\n"
    "Вплетай естественно, без шва между темами. Приглашений и CTA не добавляй — их добавит интерфейс."
)

EMPATHY_ADDON = (
    "\n\n"
    "Если в YAML-шапке текущего документа включена эмпатия, начни ответ с одной короткой "
    "естественной человеческой фразы, а затем сразу переходи к сути.\n\n"
    "Эта фраза нужна не для длинного сочувствия, а только для мягкого снижения напряжения "
    "перед полезным ответом. Она должна быть короткой, спокойной и звучать естественно. "
    "Не делай длинное вступление и не превращай ответ в психологическую поддержку.\n\n"
    "Не сообщай пользователю о внутренних правилах, YAML, эмпатии, маршрутизации "
    "или логике ответа.\n\n"
    "Тон ответа:\n"
    "- спокойный;\n"
    "- уверенный;\n"
    "- человеческий;\n"
    "- без пафоса;\n"
    "- без сюсюканья;\n"
    "- без драматизации;\n"
    "- без шаблонной вежливости;\n"
    "- без давления на запись;\n"
    "- без ощущения, что человеку что-то продают.\n\n"
    "После первой фразы сразу отвечай по существу: что происходит, от чего зависит ситуация, "
    "какие есть варианты, что обычно делает врач или клиника, и какой следующий шаг разумен.\n\n"
    "Не используй фразы:\n"
    "- «я понимаю ваше беспокойство»;\n"
    "- «как хорошо, что вы спросили»;\n"
    "- «отлично, что интересуетесь»;\n"
    "- «спасибо за вопрос»;\n"
    "- «не переживайте»;\n"
    "- «с радостью подскажу»;\n"
    "- «бояться нечего»;\n"
    "- «ничего страшного»;\n"
    "- «всё будет хорошо»;\n"
    "- «это обычная процедура»;\n"
    "- «у нас такого не бывает»;\n"
    "- «мы гарантируем»;\n"
    "- «у нас лучшие врачи»;\n"
    "- «цена полностью оправдана»;\n"
    "- «на здоровье нельзя экономить»;\n"
    "- «лучше скорее записаться, пока не стало хуже».\n\n"
    "Не обещай:\n"
    "- гарантированный результат;\n"
    "- полное отсутствие боли;\n"
    "- стопроцентное приживение;\n"
    "- полную безопасность без диагностики;\n"
    "- точную цену без осмотра и плана лечения;\n"
    "- что пациенту точно подходит или точно не подходит лечение без оценки врача.\n\n"
    "Используй аккуратные формулировки:\n"
    "- «обычно»;\n"
    "- «чаще всего»;\n"
    "- «в большинстве случаев»;\n"
    "- «по ситуации»;\n"
    "- «после диагностики»;\n"
    "- «врач оценит»;\n"
    "- «итог зависит от…»;\n"
    "- «точнее можно сказать после осмотра».\n\n"
    "Поведение по чувствительным темам:\n\n"
    "1. Боль, страх боли, анестезия, неприятные ощущения\n"
    "Если материал относится к боли, страху боли, анестезии или ощущениям во время "
    "и после лечения:\n"
    "- коротко снизь напряжение;\n"
    "- не обесценивай страх;\n"
    "- сразу объясни по фактам, как проходит обезболивание и что человек обычно чувствует.\n\n"
    "2. Дорого, бюджет, сомнение в стоимости\n"
    "Если материал относится к дороговизне, бюджету или сомнению в стоимости:\n"
    "- не спорь с сомнением человека;\n"
    "- не оправдывай цену;\n"
    "- коротко покажи, что вопрос бюджета нормален;\n"
    "- затем сразу дай ориентир по стоимости, составу цены, этапности оплаты "
    "или тому, от чего зависит сумма.\n\n"
    "3. Приживление импланта, риск неудачи, плохой прошлый опыт\n"
    "Если материал относится к приживлению импланта, риску отторжения или прошлому "
    "неудачному опыту:\n"
    "- не воспринимай это как жалобу по умолчанию;\n"
    "- не защищай клинику;\n"
    "- не уводи сразу в ручной контакт;\n"
    "- спокойно объясни, от чего зависит приживление и что делают, если возникают проблемы.\n\n"
    "4. Потеря зуба, выпал зуб, что делать сейчас\n"
    "Если материал относится к потере зуба или вопросу «что делать сейчас»:\n"
    "- не нагнетай;\n"
    "- не пугай;\n"
    "- коротко собери человека;\n"
    "- сразу дай понятный следующий шаг и покажи, что ситуация обычно решаемая, "
    "если не затягивать.\n\n"
    "5. Безопасность, заражение, противопоказания, «мне вообще можно?»\n"
    "Если материал относится к безопасности, стерильности, противопоказаниям "
    "или сомнению «мне вообще можно?»:\n"
    "- отвечай спокойно и уверенно;\n"
    "- не звучь как приговор;\n"
    "- не делай категоричных выводов без диагностики;\n"
    "- делай акцент на обследовании, условиях безопасности и индивидуальной оценке.\n\n"
    "Главное правило:\n"
    "одна короткая человеческая фраза — и сразу полезный ответ по существу."
)

JSON_ANSWER_RULE = (
    ' Ответь одним JSON-объектом с единственным ключом "answer" '
    "(строка для пациента в формате RESPONSE_FORMAT выше). "
    "Без пояснений вне JSON."
)

PLAIN_ANSWER_RULE = (
    "\n\nОтветь только текстом для пациента в формате RESPONSE_FORMAT выше. "
    "Без JSON-обёртки, без пояснений вне ответа."
)


def _doc_key(md_file: str, meta: dict) -> str:
    return meta.get("doc_id") or md_file


def normalize_generator_sources(sources: object) -> list[dict] | None:
    """Ровно один источник с непустым ref и content. Иначе None (без вызова LLM)."""
    if not isinstance(sources, list) or len(sources) != 1:
        return None
    s0 = sources[0]
    if not isinstance(s0, dict):
        return None
    ref = str(s0.get("ref") or "").strip()
    content = str(s0.get("content") or "").strip()
    if not ref or not content:
        return None
    out = {
        "ref": ref,
        "content": content,
        "doc_id": s0.get("doc_id"),
        "doc_type": s0.get("doc_type"),
        "subtype": s0.get("subtype"),
    }
    return [out]


def build_messages_for_gpt(
    user_q: str,
    sources: list[dict],
    meta: dict,
    session_id: str,
    *,
    force_text: bool = False,
    dialog_context_for_understanding: str | None = None,
):
    norm = normalize_generator_sources(sources)
    if norm is None:
        raise ValueError("sources must be a list of length 1 with non-empty ref and content")

    doc_key = _doc_key(
        meta.get("md_file") or meta.get("source") or meta.get("title", ""),
        meta,
    )
    allow_empathy = bool(EMPATHY_ON and meta.get("empathy_enabled"))
    first_in_topic = is_first_in_topic(session_id, doc_key)
    use_empathy = bool(allow_empathy and first_in_topic)
    client_id = meta.get("client_id")
    system_prompt = (
        build_base_system(client_id)
        + RESPONSE_FORMAT
        + GENERATOR_SINGLE_SOURCE_RULE
        + (EMPATHY_ADDON if use_empathy else "")
        + _consult_nudge_addon(meta)
    )
    if CHAT_JSON_MODE and not force_text:
        system_prompt += JSON_ANSWER_RULE
    elif force_text:
        system_prompt += PLAIN_ANSWER_RULE

    src0 = norm[0]
    dialog_block = ""
    dctx = (dialog_context_for_understanding or "").strip()
    if dctx:
        dialog_block = (
            "Контекст диалога (не источник фактов, только для понимания продолжения диалога):\n"
            f"{dctx}\n\n"
        )

    user_content = (
        f"{dialog_block}"
        "Вопрос пациента:\n"
        f"{(user_q or '').strip()}\n\n"
        f"Единственный источник ответа (ref={src0['ref']}):\n"
        f"{src0['content']}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    meta["_empathy_used"] = use_empathy
    meta["_first_in_topic"] = first_in_topic
    meta["_doc_key"] = doc_key

    return messages, use_empathy, doc_key


def generate_answer_with_empathy(
    user_q: str, sources: list[dict], meta: dict, session_id: str
) -> tuple[str, dict]:
    mem_txt, profile = mem_context(session_id)
    norm = normalize_generator_sources(sources)
    if norm is None:
        log_json(
            logger,
            "llm_generate_skipped_invalid_sources",
            sid=session_id,
            generator_input={"source_count": 0, "source_ref": None},
        )
        return LLM_FALLBACK_ANSWER, profile

    dialog_ctx = ""
    if mem_txt and MEMORY_ON:
        dialog_ctx = mem_txt.replace("Недавний диалог:", "").strip()

    messages, use_empathy, doc_key = build_messages_for_gpt(
        user_q,
        norm,
        meta,
        session_id,
        dialog_context_for_understanding=dialog_ctx or None,
    )

    kwargs = dict(model=CHAT_MODEL, temperature=0.3, messages=messages)
    if CHAT_JSON_MODE:
        kwargs["response_format"] = {"type": "json_object"}
    kwargs["timeout"] = LLM_REQUEST_TIMEOUT_SEC
    try:
        resp = chat_completions_create(**kwargs)
        log_llm_usage(logger, resp, call_type="chat_answer", model=CHAT_MODEL)
        raw = (resp.choices[0].message.content or "").strip()
        answer = raw
        if CHAT_JSON_MODE:
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict) and obj.get("answer"):
                    answer = str(obj["answer"]).strip()
            except (json.JSONDecodeError, TypeError):
                pass
        if not (answer or "").strip():
            answer = LLM_FALLBACK_ANSWER
        log_json(
            logger,
            "llm_generate",
            sid=session_id,
            model_used=CHAT_MODEL,
            empathy_used=bool(use_empathy),
            used_fallback=bool(answer == LLM_FALLBACK_ANSWER),
            generator_input={
                "source_ref": norm[0]["ref"],
                "source_count": 1,
            },
        )
    except Exception as e:
        log_llm_error(logger, call_type="chat_answer", err=str(e), model=CHAT_MODEL)
        log_json(
            logger,
            "llm_generate_failed",
            sid=session_id,
            model_used=CHAT_MODEL,
            err=str(e)[:300],
        )
        answer = LLM_FALLBACK_ANSWER

    update_topic_empathy(session_id, doc_key, use_empathy)

    return answer, profile


def _format_composer_card_blocks(materialized_cards: list) -> str:
    from contracts.answer_packet import MaterializedCard

    blocks: list[str] = []
    for idx, raw in enumerate(materialized_cards, start=1):
        card = (
            raw
            if isinstance(raw, MaterializedCard)
            else MaterializedCard.model_validate(raw)
        )
        aspect_bit = f", aspect={card.aspect}" if card.aspect else ""
        mode = "ДОСЛОВНО" if card.verbatim else "пересказ с сохранением оговорок"
        blocks.append(f"Карточка {idx} ({card.kind}{aspect_bit}) [{mode}]:\n{card.text}")
    return "\n\n---\n\n".join(blocks)


def build_messages_for_packet_composer(
    user_q: str,
    materialized_cards: list,
    meta: dict,
    session_id: str,
) -> list[dict[str, str]]:
    """Messages for packet composer (phase 3a); cards are MaterializedCard-like."""
    client_id = meta.get("client_id")
    system = (
        build_base_system(client_id)
        + RESPONSE_FORMAT
        + COMPOSER_PACKET_RULE
        + _consult_nudge_addon(meta)
    )
    if CHAT_JSON_MODE:
        system += JSON_ANSWER_RULE
    cards_blob = _format_composer_card_blocks(materialized_cards)
    user_content = f"Вопрос пациента:\n{(user_q or '').strip()}\n\nРазрешённые карточки:\n{cards_blob}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def build_messages_for_packet_composer_fullctx(
    user_q: str,
    knowledge_base: str,
    aspects: list[str],
    deterministic_cards: list,
    meta: dict,
    session_id: str,
    dialog_history: str | None = None,
) -> list[dict[str, str]]:
    """Messages for full-context composer — medical text from knowledge base, money from cards."""
    client_id = meta.get("client_id")
    kb_block = (
        "\n\n[БАЗА ЗНАНИЙ]\n"
        f"База знаний клиники (источник медицинского текста):\n{(knowledge_base or '').strip()}"
    )
    # Stable prefix for DashScope context cache: identity + rules + KB; per-turn addons after KB.
    system = (
        build_base_system(client_id)
        + RESPONSE_FORMAT
        + COMPOSER_FULLCTX_RULE
        + kb_block
        + _consult_nudge_addon(meta)
    )
    if CHAT_JSON_MODE:
        system += JSON_ANSWER_RULE
    aspect_line = ", ".join(str(a).strip() for a in (aspects or []) if str(a).strip())
    cards_blob = _format_composer_card_blocks(deterministic_cards)
    dialog_block = format_dialog_context_for_understanding(dialog_history or "")
    parts: list[str] = []
    if dialog_block:
        parts.append(dialog_block.rstrip())
    parts.extend(
        [
            f"Вопрос пациента:\n{(user_q or '').strip()}",
            f"Ответь на аспекты: {aspect_line}",
        ]
    )
    if cards_blob.strip():
        parts.append(
            "Разрешённые карточки (деньги/промо — вставь как есть / только отсюда):\n"
            + cards_blob
        )
    else:
        parts.append("Разрешённые карточки (деньги/промо — вставь как есть / только отсюда):\n(нет)")
    user_content = "\n\n".join(parts)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def generate_answer_from_packet(
    user_q: str,
    materialized_cards: list,
    meta: dict,
    session_id: str,
) -> tuple[str, dict]:
    """Compose one answer from materialized packet cards (fail-open if disabled or empty)."""
    if not COMPOSER_ON or not materialized_cards:
        return LLM_FALLBACK_ANSWER, {"composer_used": False}
    messages = build_messages_for_packet_composer(
        user_q,
        materialized_cards,
        meta,
        session_id,
    )
    kwargs: dict = dict(model=CHAT_MODEL, temperature=0.3, messages=messages)
    if CHAT_JSON_MODE:
        kwargs["response_format"] = {"type": "json_object"}
    kwargs["timeout"] = LLM_REQUEST_TIMEOUT_SEC
    try:
        resp = chat_completions_create(**kwargs)
        log_llm_usage(logger, resp, call_type="packet_composer", model=CHAT_MODEL)
        raw = (resp.choices[0].message.content or "").strip()
        answer = raw
        if CHAT_JSON_MODE:
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict) and obj.get("answer"):
                    answer = str(obj["answer"]).strip()
            except (json.JSONDecodeError, TypeError):
                pass
        if not (answer or "").strip():
            answer = LLM_FALLBACK_ANSWER
        log_json(
            logger,
            "packet_composer_generate",
            sid=session_id,
            client_id=meta.get("client_id"),
            card_count=len(materialized_cards),
            used_fallback=bool(answer == LLM_FALLBACK_ANSWER),
        )
        return answer, {"composer_used": True}
    except Exception as e:
        log_llm_error(logger, call_type="packet_composer", err=str(e), model=CHAT_MODEL)
        log_json(
            logger,
            "packet_composer_failed",
            sid=session_id,
            client_id=meta.get("client_id"),
            err=str(e)[:300],
        )
        return LLM_FALLBACK_ANSWER, {"composer_used": False}


def generate_answer_from_packet_fullctx(
    user_q: str,
    knowledge_base: str,
    aspects: list[str],
    deterministic_cards: list,
    meta: dict,
    session_id: str,
) -> tuple[str, dict]:
    """Compose answer from full md knowledge base + deterministic price/promo cards."""
    if not COMPOSER_ON or not FULLCTX_ON:
        return LLM_FALLBACK_ANSWER, {"composer_used": False}
    if not (knowledge_base or "").strip():
        return LLM_FALLBACK_ANSWER, {"composer_used": False}
    dialog_history = ""
    if MEMORY_ON and session_id:
        dialog_history = recent_dialog_history(session_id)
    messages = build_messages_for_packet_composer_fullctx(
        user_q,
        knowledge_base,
        aspects,
        deterministic_cards,
        meta,
        session_id,
        dialog_history=dialog_history or None,
    )
    kwargs: dict = dict(model=CHAT_MODEL, temperature=0.3, messages=messages)
    if CHAT_JSON_MODE:
        kwargs["response_format"] = {"type": "json_object"}
    kwargs["timeout"] = LLM_REQUEST_TIMEOUT_SEC
    try:
        resp = chat_completions_create(**kwargs)
        log_llm_usage(logger, resp, call_type="packet_composer_fullctx", model=CHAT_MODEL)
        raw = (resp.choices[0].message.content or "").strip()
        answer = raw
        if CHAT_JSON_MODE:
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict) and obj.get("answer"):
                    answer = str(obj["answer"]).strip()
            except (json.JSONDecodeError, TypeError):
                pass
        if not (answer or "").strip():
            answer = LLM_FALLBACK_ANSWER
        log_json(
            logger,
            "packet_composer_fullctx_generate",
            sid=session_id,
            client_id=meta.get("client_id"),
            aspect_count=len(aspects or []),
            card_count=len(deterministic_cards or []),
            kb_chars=len(knowledge_base or ""),
            used_fallback=bool(answer == LLM_FALLBACK_ANSWER),
        )
        return answer, {"composer_used": True}
    except Exception as e:
        log_llm_error(logger, call_type="packet_composer_fullctx", err=str(e), model=CHAT_MODEL)
        log_json(
            logger,
            "packet_composer_fullctx_failed",
            sid=session_id,
            client_id=meta.get("client_id"),
            err=str(e)[:300],
        )
        return LLM_FALLBACK_ANSWER, {"composer_used": False}


def generate_answer_stream(user_q: str, sources: list[dict], meta: dict, session_id: str):
    """Generator для стриминга ответа.

    Yields:
        ("delta", str)            — очередной токен ответа
        ("done", (str, dict))     — финальный накопленный текст + profile
    """
    mem_txt, profile = mem_context(session_id)
    norm = normalize_generator_sources(sources)
    if norm is None:
        log_json(
            logger,
            "llm_generate_stream_skipped_invalid_sources",
            sid=session_id,
            generator_input={"source_count": 0, "source_ref": None},
        )
        yield ("done", (LLM_FALLBACK_ANSWER, profile))
        return

    dialog_ctx = ""
    if mem_txt and MEMORY_ON:
        dialog_ctx = mem_txt.replace("Недавний диалог:", "").strip()

    messages, use_empathy, doc_key = build_messages_for_gpt(
        user_q,
        norm,
        meta,
        session_id,
        force_text=True,
        dialog_context_for_understanding=dialog_ctx or None,
    )

    full_text = ""
    stream_usage = None
    try:
        try:
            stream = chat_completions_create(
                model=CHAT_MODEL,
                messages=messages,
                stream=True,
                timeout=LLM_REQUEST_TIMEOUT_SEC,
                stream_options={"include_usage": True},
            )
        except TypeError:
            stream = chat_completions_create(
                model=CHAT_MODEL,
                messages=messages,
                stream=True,
                timeout=LLM_REQUEST_TIMEOUT_SEC,
            )
        first_delta_marked = False
        for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    if not first_delta_marked:
                        first_delta_marked = True
                        from core.turn_timing import mark

                        mark("chat_first_delta")
                    full_text += delta
                    yield ("delta", delta)
            u = getattr(chunk, "usage", None)
            if u is not None:
                stream_usage = u
        if not full_text.strip():
            full_text = LLM_FALLBACK_ANSWER
        log_llm_stream_usage(
            logger,
            stream_usage,
            call_type="chat_answer_stream",
            model=CHAT_MODEL,
        )
        log_json(
            logger,
            "llm_generate_stream",
            sid=session_id,
            model_used=CHAT_MODEL,
            empathy_used=bool(use_empathy),
            generator_input={
                "source_ref": norm[0]["ref"],
                "source_count": 1,
            },
        )
    except Exception as e:
        log_llm_error(logger, call_type="chat_answer_stream", err=str(e), model=CHAT_MODEL)
        log_json(
            logger,
            "llm_generate_stream_failed",
            sid=session_id,
            model_used=CHAT_MODEL,
            err=str(e)[:300],
        )
        if not full_text.strip():
            full_text = LLM_FALLBACK_ANSWER

    update_topic_empathy(session_id, doc_key, use_empathy)
    yield ("done", (full_text, profile))


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
