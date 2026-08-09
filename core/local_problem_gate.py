"""Pure high-precision local routing for spam, administrator, or pass.

This is intentionally a small lexical guard, not a replacement for the
existing stateful input guard or a medical-topic classifier.  Anything that
is not explicit enough to match the rules passes through unchanged.
"""

from __future__ import annotations

import re

from contracts.local_problem_gate import LocalProblemGateResult


class LocalProblemGateError(ValueError):
    """Raised when the pure gate receives a non-text input."""


_OBVIOUS_TEXT_NOISE_RE = re.compile(r"^[^\w\s]+$", re.UNICODE)

_CURRENT_SYMPTOM_MARKERS = (
    "сильно болит",
    "сильная боль",
    "кровоточит",
    "идет кровь",
    "идёт кровь",
    "опухло",
    "опухла",
    "отек",
    "гной",
    "раздуло",
    "ноет зуб",
    "ноет десна",
    "пульсирует",
    "имплант шатается",
    "зуб шатается",
    "покраснела десна",
    "онемела губа",
    "онемел язык",
    "не заживает",
    "не могу открыть рот",
    "больно жевать",
    "больно накусывать",
)
_COMPLAINT_MARKERS = (
    "хочу пожаловаться",
    "жалоба",
    "претензия",
    "дайте директора",
    "руководител",
    "главврач",
)
_REVIEW_ACTION_MARKERS = (
    "хочу оставить",
    "хочу написать",
    "как оставить",
    "как написать",
    "оставлю",
    "напишу",
)
_DIAGNOSIS_MARKERS = ("какой диагноз", "поставить диагноз", "определить диагноз")
_PERSONAL_TREATMENT_MARKERS = (
    "что принимать",
    "какую дозу",
    "какая дозировка",
    "назначьте мне",
    "назначить мне",
    "подберите лечение",
    "что лучше мне",
    "что мне выбрать",
    "выберите мне",
)
_PERSONAL_MEDICAL_CONTEXT = (
    "диабет",
    "беремен",
    "онколог",
    "антикоагулянт",
    "разжижающ",
    "аллерги",
)
_PERSONAL_MEDICAL_QUESTION = ("можно ли", "подойдет ли", "подойдёт ли", "противопоказ")
_CHRONIC_DISEASE_MARKERS = ("хроническ", "заболеван")
_IMPLANT_ELIGIBILITY_MARKERS = ("имплантац", "возможност")
_CONTRAINDICATION_MARKERS = ("противопоказан",)
_TREATMENT_SELECTION_MARKERS = ("лечен", "имплантац", "подбира")
_POST_PROCEDURE_MARKERS = ("после",)
_POST_PROCEDURE_CONTEXT = ("операц", "имплантац")
_POST_PROCEDURE_SYMPTOM_MARKERS = (
    "воспален",
    "осложнен",
    "кров",
    "бол",
    "отек",
    "отёк",
)


def _normalized_text(value: str) -> str:
    return value.strip().casefold().replace("ё", "е")


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _is_obvious_text_noise(text: str) -> bool:
    """Only stateless, unmistakable text noise belongs to this gate."""

    return len(text) >= 4 and bool(_OBVIOUS_TEXT_NOISE_RE.fullmatch(text))


def _has_explicit_current_symptom(text: str) -> bool:
    """Keep symptom routing precise enough for ordinary FAQ phrasing to pass."""

    if _contains_any(text, _CURRENT_SYMPTOM_MARKERS):
        return True
    if "болит" in text and _contains_any(
        text,
        ("у меня", "сейчас", "после", "зуб болит", "десна болит", "щека болит"),
    ):
        return True
    return "температура" in text and _contains_any(
        text,
        ("у меня", "поднялась", "держится", "после операции", "после имплантации"),
    )


def _is_review_requiring_reaction(text: str) -> bool:
    return "отзыв" in text and _contains_any(text, _REVIEW_ACTION_MARKERS)


def _is_chronic_disease_implant_eligibility(text: str) -> bool:
    return _contains_any(text, _CHRONIC_DISEASE_MARKERS) and _contains_any(
        text, _IMPLANT_ELIGIBILITY_MARKERS
    )


def _is_contraindication_treatment_question(text: str) -> bool:
    return _contains_any(text, _CONTRAINDICATION_MARKERS) and _contains_any(
        text, _TREATMENT_SELECTION_MARKERS
    )


def _is_post_procedure_complication(text: str) -> bool:
    return (
        _contains_any(text, _POST_PROCEDURE_MARKERS)
        and _contains_any(text, _POST_PROCEDURE_CONTEXT)
        and _contains_any(text, _POST_PROCEDURE_SYMPTOM_MARKERS)
    )


def decide_local_problem_gate(text: str) -> LocalProblemGateResult:
    """Return ``spam``, ``admin`` or ``pass`` without side effects.

    A future-oriented fear (pain, price, osseointegration, timing, trust) has
    no special rule and therefore reaches the commercial answer path.  The
    current-symptom rule is intentionally limited to explicit markers.
    """

    if not isinstance(text, str):
        raise LocalProblemGateError("local_problem_gate_text_invalid")
    normalized = _normalized_text(text)
    if _is_obvious_text_noise(normalized):
        return LocalProblemGateResult(
            decision="spam", reason_code="obvious_text_noise"
        )
    if _contains_any(normalized, _COMPLAINT_MARKERS) or _is_review_requiring_reaction(
        normalized
    ):
        return LocalProblemGateResult(
            decision="admin", reason_code="complaint_or_management"
        )
    if _contains_any(normalized, _DIAGNOSIS_MARKERS) or (
        "диагноз" in normalized
        and _contains_any(normalized, ("какой", "постав", "определ"))
    ) or (
        _contains_any(normalized, ("по фото", "по снимку"))
        and _contains_any(normalized, ("что с", "скажите", "определ", "диагноз"))
    ):
        return LocalProblemGateResult(
            decision="admin", reason_code="diagnosis_request"
        )
    if _contains_any(normalized, _PERSONAL_TREATMENT_MARKERS):
        return LocalProblemGateResult(
            decision="admin", reason_code="personal_treatment_request"
        )
    if _has_explicit_current_symptom(normalized):
        return LocalProblemGateResult(
            decision="admin", reason_code="current_symptom"
        )
    if _is_post_procedure_complication(normalized):
        return LocalProblemGateResult(
            decision="admin", reason_code="post_procedure_complication"
        )
    if _is_chronic_disease_implant_eligibility(normalized):
        return LocalProblemGateResult(
            decision="admin", reason_code="chronic_disease_implant_eligibility"
        )
    if _is_contraindication_treatment_question(normalized):
        return LocalProblemGateResult(
            decision="admin", reason_code="contraindication_treatment_question"
        )
    if (
        _contains_any(normalized, _PERSONAL_MEDICAL_CONTEXT)
        and _contains_any(normalized, _PERSONAL_MEDICAL_QUESTION)
    ):
        return LocalProblemGateResult(
            decision="admin", reason_code="personal_medical_question"
        )
    return LocalProblemGateResult(
        decision="pass", reason_code="no_high_precision_match"
    )
