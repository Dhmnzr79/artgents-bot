"""Константы, пути, модели, regex. Секреты только из окружения."""
import os
import re

from dotenv import load_dotenv

load_dotenv()

# --- LLM provider ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHAT_API_KEY = (
    (os.getenv("CHAT_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or "").strip()
    or OPENAI_API_KEY
)
CHAT_BASE_URL = (
    (os.getenv("CHAT_BASE_URL") or os.getenv("DASHSCOPE_BASE_URL") or "").strip()
    or None
)
QWEN_ENABLE_THINKING = os.getenv("QWEN_ENABLE_THINKING", "0").lower() in (
    "1",
    "true",
    "yes",
)


# --- Models (Qwen pilot defaults; override via .env to revert to OpenAI) ---
QWEN_PLUS_MODEL = "qwen3.7-plus"
QWEN_FLASH_MODEL = "qwen3.6-flash"

CHAT_MODEL = os.getenv("MODEL_CHAT", QWEN_PLUS_MODEL)


def chat_provider_is_qwen() -> bool:
    """True when chat client targets DashScope / MaaS Qwen (not OpenAI-native)."""
    model = (os.getenv("MODEL_CHAT") or CHAT_MODEL or "").strip().lower()
    base = (CHAT_BASE_URL or "").lower()
    return (
        "qwen" in model
        or "dashscope" in base
        or "aliyuncs" in base
        or "maas." in base
    )

RESOLVER_MODEL = (os.getenv("MODEL_RESOLVER") or "").strip() or QWEN_PLUS_MODEL
QUERY_REWRITE_MODEL = (os.getenv("MODEL_QUERY_REWRITE") or "").strip() or QWEN_FLASH_MODEL
LEAD_NAME_CLASSIFY_MODEL = (os.getenv("MODEL_LEAD_NAME") or "").strip() or QWEN_FLASH_MODEL
DIALOG_FOCUS_LLM_CLASSIFY_ON = os.getenv("DIALOG_FOCUS_LLM_CLASSIFY", "1").lower() in (
    "1",
    "true",
    "yes",
)
DIALOG_FOCUS_LLM_MODEL = (os.getenv("DIALOG_FOCUS_LLM_MODEL") or "").strip() or QWEN_FLASH_MODEL

# --- Patient situation semantic classifier ---
PATIENT_SITUATION_LLM_ON = os.getenv("PATIENT_SITUATION_LLM_ON", "1").lower() in (
    "1",
    "true",
    "yes",
)
PATIENT_SITUATION_LLM_MODEL = (
    (os.getenv("PATIENT_SITUATION_LLM_MODEL") or "").strip() or QWEN_FLASH_MODEL
)

# --- Aspect planner LLM (composite questions; composer roadmap phase 1) ---
ASPECT_PLANNER_LLM_ON = os.getenv("ASPECT_PLANNER_LLM_ON", "0").lower() in (
    "1",
    "true",
    "yes",
)
ASPECT_PLANNER_LLM_MODEL = (
    (os.getenv("ASPECT_PLANNER_LLM_MODEL") or "").strip() or QWEN_FLASH_MODEL
)

# --- Answer packet assembler (composer roadmap phase 2) ---
ANSWER_PACKET_ASSEMBLER_ON = os.getenv("ANSWER_PACKET_ASSEMBLER_ON", "0").lower() in (
    "1",
    "true",
    "yes",
)

# --- Packet composer (composer roadmap phase 3) ---
COMPOSER_ON = os.getenv("COMPOSER_ON", "1").lower() in (
    "1",
    "true",
    "yes",
)

# --- Full-context composer content (step 1: whole md base, not chunk refs) ---
FULLCTX_ON = os.getenv("FULLCTX_ON", "1").lower() in (
    "1",
    "true",
    "yes",
)

# --- Living copy for deterministic price group overviews (stage 5.5d) ---
LIVING_OVERVIEW_ON = os.getenv("LIVING_OVERVIEW_ON", "0").lower() in (
    "1",
    "true",
    "yes",
)

# --- Situation-level price overview through unified map (stage 5.5) ---
SITUATION_PRICE_ON = os.getenv("SITUATION_PRICE_ON", "0").lower() in (
    "1",
    "true",
    "yes",
)

# --- Symptom-only price → consult gate (medzone; default off) ---
PRICE_SYMPTOM_CONSULT_ON = os.getenv("PRICE_SYMPTOM_CONSULT_ON", "0").lower() in (
    "1",
    "true",
    "yes",
)

# --- Lead booking date defer (no slot confirmation without schedule; default off) ---
BOOKING_DATE_DEFER_ON = os.getenv("BOOKING_DATE_DEFER_ON", "0").lower() in (
    "1",
    "true",
    "yes",
)

# --- Composer clarify state (full-context roadmap stage 5) ---
CLARIFY_STATE_ON = os.getenv("CLARIFY_STATE_ON", "0").lower() in (
    "1",
    "true",
    "yes",
)

# --- LLM service selection in composer price path (step 2) ---
SERVICE_SELECT_LLM_ON = os.getenv("SERVICE_SELECT_LLM_ON", "1").lower() in (
    "1",
    "true",
    "yes",
)
SERVICE_SELECT_LLM_MODEL = (
    (os.getenv("SERVICE_SELECT_LLM_MODEL") or "").strip() or QWEN_FLASH_MODEL
)

# --- Single turn planner (full-context roadmap stage 4) ---
TURN_PLANNER_ON = os.getenv("TURN_PLANNER_ON", "1").lower() in (
    "1",
    "true",
    "yes",
)
TURN_PLANNER_LLM_MODEL = (
    (os.getenv("TURN_PLANNER_LLM_MODEL") or "").strip() or QWEN_FLASH_MODEL
)

# --- Lead active-turn gray-zone classifier ---
LEAD_TURN_LLM_CLASSIFY_ON = os.getenv("LEAD_TURN_LLM_CLASSIFY", "1").lower() in (
    "1",
    "true",
    "yes",
)
LEAD_TURN_LLM_MODEL = (os.getenv("LEAD_TURN_LLM_MODEL") or "").strip() or QWEN_FLASH_MODEL

# --- Намерение «записаться» (regex + при необходимости LLM) ---
BOOKING_INTENT_LLM_ON = os.getenv("BOOKING_INTENT_LLM_ON", "1").lower() in (
    "1",
    "true",
    "yes",
)
BOOKING_INTENT_LLM_MODEL = (os.getenv("BOOKING_INTENT_LLM_MODEL") or "").strip() or QWEN_FLASH_MODEL
PRICE_INTENT_LLM_ON = os.getenv("PRICE_INTENT_LLM_ON", "1").lower() in (
    "1",
    "true",
    "yes",
)
PRICE_INTENT_LLM_MODEL = (os.getenv("PRICE_INTENT_LLM_MODEL") or "").strip() or QWEN_FLASH_MODEL
SAFETY_CLASSIFY_MODEL = (os.getenv("MODEL_SAFETY_CLASSIFY") or "").strip() or QWEN_FLASH_MODEL
SAFETY_RED_CONFIDENCE_THRESHOLD = float(os.getenv("SAFETY_RED_CONFIDENCE_THRESHOLD", "0.8"))
COMPLAINT_CLASSIFY_MODEL = (os.getenv("MODEL_COMPLAINT_CLASSIFY") or "").strip() or QWEN_FLASH_MODEL
INGRESS_CLASSIFY_MODEL = (os.getenv("MODEL_INGRESS_CLASSIFY") or "").strip() or QWEN_FLASH_MODEL
QUERY_REWRITE_ON = os.getenv("QUERY_REWRITE_ON", "1").lower() in ("1", "true", "yes")
QUERY_REWRITE_MAX_MESSAGES = int(os.getenv("QUERY_REWRITE_MAX_MESSAGES", "10"))
# Подстроки в ответе rewrite → отбросить (утечка инструкции / мусор). Разделитель |
_rewrite_reject_raw = os.getenv(
    "REWRITE_REJECT_SUBSTRINGS",
    "врач, процедура, симптом, зуб, материал|ключевые сущности",
)
REWRITE_REJECT_SUBSTRINGS: tuple[str, ...] = tuple(
    x.strip().lower() for x in _rewrite_reject_raw.split("|") if x.strip()
)
QUERY_REWRITE_VALIDATE_OVERLAP = os.getenv("QUERY_REWRITE_VALIDATE_OVERLAP", "1").lower() in (
    "1",
    "true",
    "yes",
)

# --- HTTP / app ---
PORT = int(os.getenv("PORT", "9000"))
DEBUG_TOKEN = os.getenv("DEBUG_TOKEN", "dev-debug")
INPUT_MAX_CHARS = int(os.getenv("INPUT_MAX_CHARS", "600"))
RATE_LIMIT_WINDOW_SEC = int(os.getenv("RATE_LIMIT_WINDOW_SEC", "60"))
RATE_LIMIT_MAX_PER_IP = int(os.getenv("RATE_LIMIT_MAX_PER_IP", "40"))
ANTI_SPAM_NO_INTENT_TURNS = int(os.getenv("ANTI_SPAM_NO_INTENT_TURNS", "20"))
ANTI_SPAM_BURST_WINDOW_SEC = int(os.getenv("ANTI_SPAM_BURST_WINDOW_SEC", "120"))
ANTI_SPAM_BURST_MESSAGES = int(os.getenv("ANTI_SPAM_BURST_MESSAGES", "6"))

# --- Paths ---
DATA_DIR = os.getenv("DATA_DIR", "data")
SQLITE_PATH = os.getenv("SQLITE_PATH", os.path.join(DATA_DIR, "bot.db"))

# --- Retrieval / policy пороги ---

# Алиас по корпусу: «сильный» — как раньше 0.82; «мягкий» — подстраховка у LOW_SCORE (не второй порог на клиента).


# --- Ответ при низком score ---
DEFAULT_CTA_TEXT = os.getenv("DEFAULT_CTA_TEXT", "Записаться на консультацию")
DEFAULT_CTA_ACTION = os.getenv("DEFAULT_CTA_ACTION", "lead")

# --- LLM: JSON-ответ { "answer": "..." } ---
CHAT_JSON_MODE = os.getenv("CHAT_JSON_MODE", "1").lower() in ("1", "true", "yes")

# --- Явное намерение записаться (обход запрета CTA при turn_count < 2) ---
# Не матчим голые «консультац» / «приём» — иначе ловятся контентные вопросы.
# «записаться» не после как/где/куда (FAQ «как записаться»).
BOOKING_INTENT_RE = re.compile(
    r"(?:"
    r"запишите\s+меня"
    r"|хочу\s+запис(аться|ать)\b"
    r"|запись\s+на\s+(?:консультац|приём|прием)"
    r"|остав(ить|лю)\s+заявку"
    r"|(?<!\bкак\s)(?<!\bгде\s)(?<!\bкуда\s)\bзапис(аться|ать)\b"
    r"(?:\s+на\s+(?:консультац|приём|прием))?"
    r")",
    re.I | re.U,
)

# --- Multi-tenant (сейчас один клиент; неизвестный id → 403) ---
DEFAULT_CLIENT_ID = os.getenv("DEFAULT_CLIENT_ID", "demo").strip() or "demo"
_ac_raw = os.getenv("ALLOWED_CLIENTS", "").strip()
if _ac_raw:
    ALLOWED_CLIENTS = frozenset(x.strip() for x in _ac_raw.split(",") if x.strip())
else:
    ALLOWED_CLIENTS = frozenset({DEFAULT_CLIENT_ID, "demo", "cesi", "nikadent"})

# --- Детерминированный роутинг до LLM ---
CONTACTS_RE = re.compile(
    r"(адрес|"
    r"где\s+(?:вы\s+|вас\s+)?находит|"
    r"где.{0,40}клиник|"
    r"как\s+(доехать|проехать)|"
    r"время\s+работы|график|"
    r"телефон|whatsapp|карта|расположение|"
    r"метро|парковк|"
    r"суббот|воскресен)",
    re.I | re.U,
)
PRICES_RE = re.compile(
    r"(цена|стоимост|сколько\s+стоит|прайс|расценк|по\s+цене|сколько\s+будет|сколько\s+руб)",
    re.I,
)
PRICE_LOOKUP_RE = re.compile(
    r"(цена|стоимост|сколько\s+стоит|прайс|расценк|по\s+цене|сколько\s+будет|сколько\s+руб|сколько\s+обойд[её]тся?)",
    re.I,
)
# Без «скидк/рассрочк»: вопросы про скидки, полис, рассрочку — обычный retrieval (payment_terms и т.д.),
# а не price_concern к конкретной услуге.
PRICE_CONCERN_RE = re.compile(
    r"(дорог|почему\s+так\s+дорого|слишком\s+дорого|высокая\s+цена|не\s+потяну|не\s+по\s+карману|дешевле|снизить\s+стоимост)",
    re.I,
)
# Коммерческие/организационные вопросы — retrieval (payment_terms, warranty), не price_concern.
COMMERCIAL_INFO_RE = re.compile(
    r"(?:"
    r"рассрочк|"
    r"оплат\w*\s+по\s+(?:част|этап)|"
    r"оплат\w*\s+потом|"
    r"что\s+входит|"
    r"входит\s+в\s+(?:акци|стоим|цен)|"
    r"не\s+входит\s+в\s+(?:цен|стоим)|"
    r"акци\w*\s+на\s+имплант|"
    r"платн\w*\s+или\s+по\s+гарант|"
    r"повторн\w+\s+(?:установк|имплант)|"
    r"гаранти\w+\s+(?:на\s+)?(?:работ|имплант|повтор)|"
    r"посчитать\s+цен\w*|"
    r"(?:снимк|кт).*(?:посчитать|оценить|пример\w*).*(?:цен|стоим)|"
    r"(?:посчитать|оценить|пример\w*).*(?:цен|стоим).*(?:снимк|кт)|"
    r"под\s+ключ|"
    r"отдельно\s+(?:абатмент|коронк|снимок)"
    r")",
    re.I,
)
CONSULTATION_QUERY_RE = re.compile(
    r"(?:"
    r"(?:сколько\s+стоит\s+)?консультац(?:ия|ии)?(?:\s+\w+)?"
    r"|план\s+лечен"
    r"|стоимость\s+консультац"
    r")",
    re.I,
)
COMPARISON_QUERY_RE = re.compile(
    r"(?:"
    r"(?:all[\s-]?on[\s-]?)?4\s+или\s+6|"
    r"6\s+или\s+4|"
    r"все\s+на\s+(?:четыр|4)\s+или\s+(?:шест|6)|"
    r"чем\s+отличается\s+all|"
    r"что\s+(?:лучше|выбрать)|"
    r"лучше\s+(?:все\s+на|all-on|\d+\s+или\s+\d+|\d+\s+имплант)"
    r")",
    re.I,
)
STEPS_VISITS_QUERY_RE = re.compile(
    r"(?:"
    r"(?:сколько\s+)?(?:визит|приём|прием|этап)\w*.*(?:имплант|протез|челюст)|"
    r"(?:полн\w+\s+)?протезирован\w+\s+челюст\w*\s+на\s+имплант"
    r")",
    re.I,
)
KT_EXPLICIT_RE = re.compile(r"\bкт\b|томограф|компьютерн", re.I | re.U)
# Implant pain/fear intent (lead_interrupt, policy; ask_turn overlay removed E5) — см. ROUTING_MAP.md
IMPLANT_PAIN_FAQ_IMPLANT_RE = re.compile(
    r"(имплант|implant|all[\s-]?on|все\s+на\s+(?:четыр|4|шест|6))",
    re.I | re.U,
)
IMPLANT_PAIN_FAQ_FEAR_RE = re.compile(
    r"(больно|боюсь|страш|страх|анестез|наркоз|обезбол|седац|"
    r"не\s+больно|во\s+сне|дискомфорт\s+при\s+имплант)",
    re.I | re.U,
)

PRICE_SERVICE_MATCH_STRONG = float(os.getenv("PRICE_SERVICE_MATCH_STRONG", "0.62"))

# --- Память диалога ---
MEMORY_ON = True
MAX_TURNS = 8
MAX_IDLE_SEC = 60 * 60

# --- Кэш retrieval ---
RETRIEVE_CACHE_TTL_SEC = int(os.getenv("RETRIEVE_CACHE_TTL_SEC", "120"))
RETRIEVE_CACHE_MAXSIZE = int(os.getenv("RETRIEVE_CACHE_MAXSIZE", "512"))

# --- Эмпатия ---
EMPATHY_ON = True
TRIGGERS = {
    "fear_pain": r"(боюс|страшн|тревог|паник|боль|болит|болезнен|анестез|заморозк|укол)",
    "safety": r"(опасн|зараж|инфекц|стерил|безопасн|чистот|противопоказан|риск)",
    "price": r"(дорог|дешев|стоимост|цена|сколько стоит|рассрочк)",
    "timing": r"(сколько времен|как долго|срок|долго|за один день|быстрее)",
    "indications": r"(подходит ли|можно ли мне|мой случай|показан|показания)",
    "support": r"(пережив|сомнева|не уверен|не уверена|тяну ли|поможете|помогите)",
}
TRIGGERS_COMPILED = {k: re.compile(v, re.I | re.U) for k, v in TRIGGERS.items()}

_LLM_PRICE_IN_PER_1M = float(os.getenv("BOT_LLM_USD_PER_1M_PROMPT", "0") or "0")
_LLM_PRICE_OUT_PER_1M = float(os.getenv("BOT_LLM_USD_PER_1M_COMPLETION", "0") or "0")


def estimate_llm_usage_usd(
    *,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> float | None:
    """Грубая оценка затрат для дашборда. Нули env → вернуть None (не гадать)."""
    if _LLM_PRICE_IN_PER_1M <= 0 and _LLM_PRICE_OUT_PER_1M <= 0:
        return None
    pt = int(prompt_tokens or 0)
    ct = int(completion_tokens or 0)
    return round(
        (pt * _LLM_PRICE_IN_PER_1M + ct * _LLM_PRICE_OUT_PER_1M) / 1_000_000.0,
        8,
    )


if not OPENAI_API_KEY:
    # CI lint/unit import config without calling OpenAI; eval job checks the secret explicitly.
    if os.getenv("GITHUB_ACTIONS") == "true":
        OPENAI_API_KEY = "github-actions-placeholder"
        CHAT_API_KEY = CHAT_API_KEY or OPENAI_API_KEY
    else:
        raise RuntimeError("OPENAI_API_KEY is not set in .env (required for chat LLM)")
elif not CHAT_API_KEY:
    CHAT_API_KEY = OPENAI_API_KEY


def resolve_client_id(raw: str | None) -> str | None:
    cid = (raw or "").strip() or DEFAULT_CLIENT_ID
    if cid == "default":
        cid = "demo"
    return cid if cid in ALLOWED_CLIENTS else None


def default_cta_dict() -> dict:
    return {"text": DEFAULT_CTA_TEXT, "action": DEFAULT_CTA_ACTION}
