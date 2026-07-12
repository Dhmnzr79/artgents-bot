"""Deterministic emotion reassurance policy (P1 pilot)."""

from __future__ import annotations

from typing import Literal

from contracts.turn_plan import EmotionKind
from core.medzone_personal import is_medzone_personal

EmotionReassuranceKind = Literal["fear", "doubt"]

_REASSURANCE_EMOTIONS: frozenset[str] = frozenset({"fear", "doubt"})

_THEME_FOCUS: dict[tuple[str, str], str] = {
    ("doctors", "overview"): (
        "Тема ответа — опыт и квалификация врачей клиники. "
        "Дай одну короткую тёплую фразу, затем факты про стаж, опыт и сложные случаи. "
        "Не упоминай боль, анестезию, приживление имплантов и цены — пациент спрашивает про врачей."
    ),
    ("doctors", "stages"): (
        "Тема — опыт врачей и как устроена работа команды. "
        "Тёплый тон + факты про стаж и практику. Без боли и без цен."
    ),
    ("implantation", "pain"): (
        "Тема — обезболивание и ощущения при имплантации. "
        "Одна короткая тёплая фраза, затем факты про анестезию и комфорт из базы — дословно по числам."
    ),
    ("implantation", "overview"): (
        "Тема — приживление имплантов и надёжность лечения. "
        "Одна короткая тёплая фраза, затем факты про приживаемость и контроль из базы."
    ),
    ("implantation", "duration"): (
        "Тема — сроки имплантации. Тёплый тон + факты про этапы и длительность из базы."
    ),
    ("prosthetics", "pain"): (
        "Тема — комфорт процедуры (отбеливание/протезирование по вопросу). "
        "Тёплый тон + факты про безопасность и ощущения из базы по этой услуге. "
        "Не уходи в имплантацию, если вопрос не про неё."
    ),
    ("unknown", "duration"): (
        "Тема — сроки лечения. Тёплый тон + факты про длительность и этапы из базы."
    ),
    ("unknown", "pain"): (
        "Тема — боль и комфорт по вопросу пациента. "
        "Тёплый тон + факты про обезболивание из базы."
    ),
    ("unknown", "overview"): (
        "Тема — суть вопроса пациента. Тёплый тон + успокаивающие факты по теме из базы."
    ),
}


def is_emotion_reassurance_eligible(
    *,
    q: str,
    emotion: EmotionKind | str | None,
) -> bool:
    """emotion ∈ {fear,doubt} and not medzone-personal."""
    if is_medzone_personal(q):
        return False
    val = str(emotion or "none").strip().lower()
    return val in _REASSURANCE_EMOTIONS


def _resolve_primary_aspect(aspects: list[str]) -> str:
    for raw in aspects:
        cand = str(raw or "").strip().lower()
        if cand and cand != "overview":
            return cand
    for raw in aspects:
        cand = str(raw or "").strip().lower()
        if cand:
            return cand
    return "overview"


def build_theme_reassurance_instruction(
    *,
    topic: str | None,
    aspects: list[str],
    emotion: EmotionReassuranceKind,
    first_touch: bool,
) -> str:
    """User-prompt addon: warm tone + calming facts scoped to theme."""
    topic_norm = str(topic or "unknown").strip().lower() or "unknown"
    aspect = _resolve_primary_aspect(aspects)
    focus = _THEME_FOCUS.get((topic_norm, aspect))
    if focus is None:
        focus = _THEME_FOCUS.get((topic_norm, "overview"))
    if focus is None:
        focus = _THEME_FOCUS.get(("unknown", aspect)) or _THEME_FOCUS[("unknown", "overview")]

    emotion_line = (
        "Пациент переживает и сомневается — признай это коротко и по-человечески."
        if emotion == "doubt"
        else "Пациент боится — признай страх коротко и спокойно, без обесценивания."
    )
    touch = (
        "Это первое касание чувствительной темы в диалоге: "
        "одна короткая тёплая фраза, затем сразу факты по теме."
        if first_touch
        else "Тема уже обсуждалась — без вступительных фраз сочувствия, сразу по существу."
    )
    return f"{touch}\n{emotion_line}\n{focus}"


def reassurance_doc_key(*, topic: str | None, aspect: str) -> str:
    topic_norm = str(topic or "unknown").strip().lower() or "unknown"
    aspect_norm = str(aspect or "overview").strip().lower() or "overview"
    return f"emotion:{topic_norm}:{aspect_norm}"
