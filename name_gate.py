"""Жёсткий предфильтр строки «как к вам обращаться» — только явный мусор."""

from __future__ import annotations

import re
from collections import Counter

from session import normalize_phone

_EMAIL_RX = re.compile(r"\S+@\S+\.\S+", re.I)
_URL_RX = re.compile(r"(https?://|www\.)", re.I)
_MULTI_SPACE = re.compile(r"\s+")
_NAME_TOKEN_RX = re.compile(r"^[А-ЯЁA-Za-zа-яё\-]{2,40}$", re.U)
_VOWEL_CHARS = frozenset("аеёиоуыэюяaeiouy")

# Фразы, которые почти наверняка не имя (одна подстрока в нижнем регистре).
_REJECT_SUBSTRINGS = (
    "болит зуб",
    "у меня бол",
    "у меня болит",
    "хочу запис",
    "записаться на",
    "оставить заяв",
    "оформить заяв",
    "есть ли парков",
    "сколько стоит",
    "как добраться",
    "где находит",
    "адрес клиник",
    "номер телефон",
    "телефон клиник",
    "можно ли запис",
    "когда вы работ",
    "график работ",
    "стоимость леч",
    "сколько будет",
    "расскажите про",
    "подскажите про",
    "all-on",
    "all on",
    "делаете",
    "делаете?",
    "какой адрес",
    "какая цена",
)

# Отдельные токены-редфлаги (симптомы, интенты, вопросы — не ФИО).
_REJECT_TOKENS = frozenset(
    {
        "парковка",
        "парковку",
        "цена",
        "цены",
        "стоимость",
        "адрес",
        "телефон",
        "график",
        "запись",
        "записаться",
        "консультация",
        "консультацию",
        "имплант",
        "имплантация",
        "удалить",
        "удаление",
        "виниры",
        "брекеты",
        "болит",
        "болят",
        "боль",
        "больно",
        "ноет",
        "ноют",
        "зуб",
        "зуба",
        "зубы",
        "зубов",
        "зубной",
        "десна",
        "десны",
        "кариес",
        "лечение",
        "лечить",
        "лечат",
        "лечусь",
        "как",
        "где",
        "когда",
        "что",
        "почему",
        "зачем",
        "сколько",
        "какой",
        "какая",
        "какие",
        "какое",
        "можно",
        "есть",
        "делаете",
        "делать",
        "стоит",
        "стоят",
        "расскажите",
        "подскажите",
        "скажите",
        "интересует",
        "хочу",
        "нужно",
        "надо",
        "мне",
        "меня",
        "нас",
        "вам",
        "вас",
        "они",
        "оно",
        "это",
        "тут",
        "там",
        "сюда",
        "срочно",
        "пожалуйста",
        "please",
        "hello",
        "hi",
        "yes",
        "no",
    }
)

# Токены после «я …» / однословный filler — не имя.
_LEAD_NAME_REJECT = frozenset(
    {
        "боюсь", "хочу", "переживаю", "переживал", "переживала", "беспокоюсь",
        "думаю", "знаю", "понимаю", "слышал", "слышала", "видел", "видела",
        "устал", "устала", "устали", "надеюсь", "сомневаюсь",
        "хотел", "хотела", "хотели", "хотелось", "узнать", "узнаю", "спрашиваю",
        "бы", "же", "не", "тоже", "также", "просто", "очень", "уже", "ещё",
        "еще", "пока", "только", "да", "нет", "ок", "ага", "угу",
        "хорошо", "ладно", "спасибо", "привет", "здравствуйте", "понятно",
        "ясно", "конечно", "извините", "простите",
    }
)

# Корни внутри «слова» — симптом / service / troll, не имя.
_REJECT_TOKEN_SUBSTRINGS = (
    "болит",
    "болят",
    "боль",
    "зуб",
    "имплант",
    "протез",
    "удален",
    "кариес",
    "брекет",
    "винир",
    "пульпит",
    "десен",
    "десн",
    "стомат",
    "лечен",
    "запис",
    "консульт",
    "стоим",
    "цен",
    "адрес",
    "парков",
)

# Служебные слова вступления — не проверять как имя в hard_reject.
_LEAD_INTRO_FILLERS = frozenset({"меня", "зовут", "я", "это"})

# Минимальный список грубой лексики (корни); без попытки покрыть весь интернет.
_PROFANITY = frozenset(
    {
        "хуй",
        "хуе",
        "хуя",
        "пизд",
        "ебан",
        "ебат",
        "ёбан",
        "бля",
        "сука",
        "мудак",
        "дурак",
        "дура",
        "придурок",
        "придурочн",
        "говно",
    }
)


def _normalize_lead_name_input(text: str) -> str:
    s = (text or "").strip()
    if s.endswith("?") and s.count("?") == 1:
        s = s[:-1].strip()
    return s


def _normalize_token(tok: str) -> str:
    return tok.lower().replace("ё", "е").strip(".,!?-—")


def _token_has_vowel(tok: str) -> bool:
    return any(c in _VOWEL_CHARS for c in tok.lower() if c.isalpha())


def _max_consonant_run(tok: str) -> int:
    wl = _normalize_token(tok)
    run = 0
    best = 0
    for ch in wl:
        if not ch.isalpha() or ch in _VOWEL_CHARS:
            run = 0
            continue
        run += 1
        if run > best:
            best = run
    return best


def _token_rejected_by_substring(wl: str) -> bool:
    for needle in _REJECT_TOKEN_SUBSTRINGS:
        if needle in wl:
            return True
    return False


def is_plausible_name_token(tok: str) -> bool:
    """Один токен похож на часть ФИО (не симптом / вопрос / мусор)."""
    t = (tok or "").strip()
    if not t or not _NAME_TOKEN_RX.fullmatch(t):
        return False
    wl = _normalize_token(t)
    if wl in _REJECT_TOKENS or wl in _LEAD_NAME_REJECT:
        return False
    if _token_rejected_by_substring(wl):
        return False
    if not _token_has_vowel(t):
        return False
    if _max_consonant_run(t) > 5:
        return False
    if len(wl) >= 10 and max(Counter(wl).values()) >= 3:
        return False
    vowels_in = [c for c in wl if c in _VOWEL_CHARS]
    if len(wl) >= 9 and vowels_in:
        vowel_counts = Counter(vowels_in)
        if len(vowel_counts) == 1 and max(vowel_counts.values()) >= 3:
            return False
    return True


def hard_reject_lead_name(text: str) -> bool:
    """True — строку не рассматриваем как кандидат в имя (явный мусор)."""
    s = _normalize_lead_name_input(text)
    if not s:
        return True
    if len(s) > 120:
        return True
    words = _MULTI_SPACE.split(s)
    if len(words) > 3:
        return True
    low = s.lower().replace("ё", "е")
    if any(ch.isdigit() for ch in s):
        return True
    if normalize_phone(s):
        return True
    if _EMAIL_RX.search(s):
        return True
    if _URL_RX.search(s):
        return True
    if "?" in s:
        return True
    for needle in _REJECT_SUBSTRINGS:
        if needle in low:
            return True
    for w in words:
        wl = w.lower().replace("ё", "е").strip(".,!?-—")
        if wl in _LEAD_INTRO_FILLERS:
            continue
        if wl in _REJECT_TOKENS:
            return True
        if _token_rejected_by_substring(wl):
            return True
    for bad in _PROFANITY:
        if bad in low:
            return True
    return False


def accept_lead_name(text: str) -> str | None:
    """extract_name + hard_reject + token plausibility; None если сомнительно."""
    from session import extract_name

    raw = (text or "").strip()
    if not raw or hard_reject_lead_name(raw):
        return None
    name = extract_name(raw)
    if not name:
        return None
    for part in name.split():
        if not is_plausible_name_token(part):
            return None
    return name
