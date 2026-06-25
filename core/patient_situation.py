"""Patient situation detection — structured cues + rule-based confidence (Slice 1)."""

from __future__ import annotations

import re
from typing import Any

from config import PRICE_LOOKUP_RE
from contracts.patient_situation import (
    CueIntent,
    CueQuantity,
    PatientNextBestAction,
    PatientScope,
    PatientSituationCues,
    PatientSituationKind,
    PatientSituationResult,
    PatientSituationSessionContext,
    PatientSituationSource,
)
from core.price_offers import (
    _FULL_ARCH_RX,
    _JAW_RESTORATION_RX,
    _ONE_STAGE_PRICE_RX,
    _ONE_TOOTH_EXPLICIT_RX,
    _UPPER_JAW_RX,
)
from core.price_scope import _ONE_TOOTH_SITUATION_RX, _PROSTHETIC_STAGE_RX

_PRICE_INTENT_RX = re.compile(
    r"(цена|стоимост|сколько\s+сто(?:ит|ят)|прайс|расценк|по\s+цене|сколько\s+будет|сколько\s+руб|сколько\s+обойд)",
    re.I | re.U,
)
_CHOOSE_SOLUTION_RX = re.compile(
    r"(что\s+(?:мне\s+)?подойд|что\s+делать|как\s+лучше|какой\s+вариант|что\s+можно|чем\s+лучше)",
    re.I | re.U,
)
_RESTORE_RX = re.compile(r"восстанов\w*|постав\w*|встав\w*|вернут\w*", re.I | re.U)
_COMPARE_RX = re.compile(r"сравн|отличи|чем\s+лучше|или\s+лучше", re.I | re.U)
_DOCTOR_RX = re.compile(r"врач|доктор|хирург|имплантолог", re.I | re.U)
_WARRANTY_RX = re.compile(r"гарант", re.I | re.U)

_FEW_TEETH_RX = re.compile(
    r"нескольк\w+\s+зуб|2\s+зуб|3\s+зуб|два\s+зуб|три\s+зуб|не\s+хватает\s+зуб",
    re.I | re.U,
)
_ALL_TEETH_MISSING_RX = re.compile(
    r"нет\s+зуб\w*\s+вообще|нет\s+всех\s+зуб|без\s+зуб|зубов\s+нет|зубов\s+почти\s+не\s+осталось",
    re.I | re.U,
)
_FULL_JAW_RESTORE_RX = re.compile(
    r"восстанов\w*\s+(?:всю|всей)\s+челюст|вся\s+челюсть|всю\s+челюсть",
    re.I | re.U,
)
_UPPER_JAW_BONE_RX = re.compile(r"мало\s+кост\w*\s+сверху|кост\w*\s+на\s+верхн", re.I | re.U)
_EXTRACTED_TOOTH_RX = re.compile(
    r"удалил\w*|удален\w*|выдернул\w*|шест[её]рк|седьм[её]рк|восьм[её]рк",
    re.I | re.U,
)
_GAP_RX = re.compile(r"промежуток|пустое\s+место|щел|щель|диастем", re.I | re.U)
_CHEW_SIDE_RX = re.compile(r"нечем\s+жевать|жевать\s+нечем|не\s+могу\s+жевать", re.I | re.U)
_EXISTING_IMPLANT_RX = re.compile(
    r"уже\s+(?:стоит|вкручен|установлен)\s+имплант|имплант\s+уже|вкручен\w*\s+имплант",
    re.I | re.U,
)
_CROWN_ON_IMPLANT_RX = re.compile(
    r"коронк\w*\s+на\s+имплант|протез\s+на\s+имплант\w*|абатмент",
    re.I | re.U,
)
_BONE_DEFICIT_RX = re.compile(
    r"мало\s+кост|недостат\w*\s+кост|не\s+хватает\s+кост|кост\w*\s+мало",
    re.I | re.U,
)
_SINUS_GRAFT_RX = re.compile(
    r"синус[\s-]?лифт|костн\w*\s+пластик|наращив\w*\s+кост|без\s+костн\w*\s+пластик",
    re.I | re.U,
)
_EXTRACTION_IMPLANT_RX = re.compile(
    r"нужно\s+удал|удалить.{0,40}имплант|имплант.{0,40}удалить|сразу\s+после\s+удал",
    re.I | re.U,
)
_URGENT_RX = re.compile(
    r"болит|боль\s+в\s+зуб|сломал\w*\s+зуб|треснул\w*\s+зуб|срочно|можно\s+сегодня|сегодня\s+можно|от[её]к",
    re.I | re.U,
)
_GENERIC_IMPLANT_RX = re.compile(
    r"что\s+такое\s+имплант|виды\s+имплант|какие\s+есть\s+имплант|имплантаци\w*\s+—|хочу\s+имплант,\s+с\s+чего",
    re.I | re.U,
)
_IMPLANT_INTEREST_RX = re.compile(r"имплант|имплантаци", re.I | re.U)
_TOOTH_RX = re.compile(r"зуб", re.I | re.U)

_JAW_ARCH_EXCLUDES = ("all_on_4", "all_on_6", "zygomatic_implants", "pterygoid_implants")
_ONE_TOOTH_EXCLUDES = _JAW_ARCH_EXCLUDES
_FULL_JAW_EXCLUDES = ("classic", "one_stage")


def _has_price_intent(text: str) -> bool:
    return bool(_PRICE_INTENT_RX.search(text) or PRICE_LOOKUP_RE.search(text))


def _extract_cues(text: str) -> PatientSituationCues:
    anatomy: list[str] = []
    state: list[str] = []

    if _TOOTH_RX.search(text):
        anatomy.append("tooth")
    if re.search(r"зуб[а-я]*", text, re.I | re.U) and not re.search(
        r"один\s+зуб", text, re.I | re.U
    ):
        anatomy.append("teeth")
    if re.search(r"челюст", text, re.I | re.U):
        anatomy.append("jaw")
    if _UPPER_JAW_RX.search(text) or re.search(r"верхн\w*\s+челюст", text, re.I | re.U):
        anatomy.append("upper_jaw")
    if re.search(r"нижн\w*\s+челюст", text, re.I | re.U):
        anatomy.append("lower_jaw")
    if _IMPLANT_INTEREST_RX.search(text):
        anatomy.append("implant")
    if re.search(r"коронк|протез|абатмент", text, re.I | re.U):
        anatomy.append("crown")
    if _BONE_DEFICIT_RX.search(text) or _SINUS_GRAFT_RX.search(text):
        anatomy.append("bone")

    if re.search(r"нет\s+зуб|без\s+зуб|отсутств", text, re.I | re.U):
        state.append("missing")
    if _EXTRACTED_TOOTH_RX.search(text):
        state.append("extracted")
    if re.search(r"сломал|треснул|скол", text, re.I | re.U):
        state.append("broken")
    if _EXISTING_IMPLANT_RX.search(text):
        state.append("existing_implant")
    if _BONE_DEFICIT_RX.search(text) or _SINUS_GRAFT_RX.search(text):
        state.append("bone_deficit")
    if _URGENT_RX.search(text):
        state.append("urgent_pain")

    quantity: CueQuantity = "unknown"
    if (
        _ONE_TOOTH_EXPLICIT_RX.search(text)
        or _ONE_TOOTH_SITUATION_RX.search(text)
        or (
            _EXTRACTED_TOOTH_RX.search(text)
            and (_RESTORE_RX.search(text) or _IMPLANT_INTEREST_RX.search(text))
        )
        or (_GAP_RX.search(text) and re.search(r"закрыть", text, re.I | re.U))
    ):
        quantity = "one"
    elif _FEW_TEETH_RX.search(text) or _CHEW_SIDE_RX.search(text):
        quantity = "few"
    elif _ALL_TEETH_MISSING_RX.search(text) or _FULL_ARCH_RX.search(text):
        quantity = "all"
    elif _FULL_JAW_RESTORE_RX.search(text) or _JAW_RESTORATION_RX.search(text):
        quantity = "jaw"
    elif _UPPER_JAW_RX.search(text) or re.search(r"верхн\w*\s+челюст", text, re.I | re.U):
        quantity = "jaw"

    intent: CueIntent = "unknown"
    if _has_price_intent(text):
        intent = "price"
    elif _CHOOSE_SOLUTION_RX.search(text):
        intent = "choose_solution"
    elif _RESTORE_RX.search(text):
        intent = "restore"
    elif _COMPARE_RX.search(text):
        intent = "compare"
    elif _DOCTOR_RX.search(text):
        intent = "doctor"
    elif _WARRANTY_RX.search(text):
        intent = "warranty"
    elif _GENERIC_IMPLANT_RX.search(text):
        intent = "choose_solution"

    return PatientSituationCues(
        quantity=quantity,
        anatomy=sorted(set(anatomy)),
        state=sorted(set(state)),
        intent=intent,
    )


def _scope_for_kind(kind: PatientSituationKind) -> PatientScope:
    return {
        "one_tooth_missing": "one_tooth",
        "few_teeth_missing": "few_teeth",
        "full_arch_missing": "full_jaw",
        "upper_jaw_missing_or_complex": "upper_jaw",
        "existing_implant_prosthetic_stage": "prosthetic_stage",
        "extraction_then_implant": "one_tooth",
        "bone_deficit_or_grafting": "adjunct",
        "urgent_problem": "urgent",
        "generic_implant_interest": "generic",
        "unknown": "unknown",
    }[kind]


def _next_action_for(
    kind: PatientSituationKind,
    *,
    intent: CueIntent,
    should_clarify: bool,
) -> PatientNextBestAction:
    if should_clarify:
        return "clarify"
    if kind == "urgent_problem":
        # Telemetry signal only until dedicated urgent slice (tighter cues; no booking hook).
        return "urgent_booking"
    if kind == "bone_deficit_or_grafting":
        return "ct"
    if kind in {"full_arch_missing", "upper_jaw_missing_or_complex"}:
        return "ct"
    if intent == "price":
        return "price_estimate"
    if intent == "doctor":
        return "doctor_lookup"
    if kind == "generic_implant_interest":
        return "consult"
    if kind != "unknown":
        return "consult"
    return "none"


def _hints_for_kind(kind: PatientSituationKind) -> tuple[list[str], list[str], list[str]]:
    """Contract/telemetry placeholders only (Slice 1).

    Slice 2 MUST NOT use these lists as routing hardcode (if X → service Y).
    Influence only via patient_scope + pricebook/default_unit + soft boost/filter.
    """
    if kind == "one_tooth_missing":
        return list(_ONE_TOOTH_EXCLUDES), ["classic", "one_stage"], ["one_tooth"]
    if kind == "few_teeth_missing":
        return list(_JAW_ARCH_EXCLUDES), [], ["few_teeth"]
    if kind == "full_arch_missing":
        return list(_FULL_JAW_EXCLUDES), [], ["full_jaw", "implantation"]
    if kind == "upper_jaw_missing_or_complex":
        return list(_ONE_TOOTH_EXCLUDES), [], ["upper_jaw"]
    if kind == "existing_implant_prosthetic_stage":
        return ["classic", "one_stage", "all_on_4", "all_on_6"], ["implant_supported_prosthetics"], [
            "prosthetic_stage"
        ]
    if kind == "extraction_then_implant":
        return list(_JAW_ARCH_EXCLUDES), ["one_stage", "classic"], ["one_tooth"]
    if kind == "bone_deficit_or_grafting":
        return [], [], ["bone_grafting", "sinus_lift"]
    return [], [], []


def _clarify_for_ambiguous(cues: PatientSituationCues) -> tuple[bool, str | None, str | None]:
    if cues.quantity == "few" and "urgent_pain" not in cues.state:
        return (
            True,
            "Речь про один зуб или про несколько / всю челюсть?",
            "ambiguous_quantity_few",
        )
    return False, None, None


def _resolve_from_cues(
    text: str,
    cues: PatientSituationCues,
) -> tuple[PatientSituationKind, float, list[str], bool, str | None, str | None]:
    evidence: list[str] = []
    should_clarify = False
    clarify_question: str | None = None
    clarification_reason: str | None = None

    if _URGENT_RX.search(text) and (
        re.search(r"зуб|бол|сломал|удал|срочно|сегодня|от[её]к", text, re.I | re.U)
    ):
        evidence.append("urgent_cue")
        return "urgent_problem", 0.93, evidence, False, None, None

    if (_EXISTING_IMPLANT_RX.search(text) or "existing_implant" in cues.state) and (
        _CROWN_ON_IMPLANT_RX.search(text) or "crown" in cues.anatomy
    ):
        evidence.append("existing_implant_prosthetic")
        return "existing_implant_prosthetic_stage", 0.94, evidence, False, None, None

    if (
        _PROSTHETIC_STAGE_RX.search(text)
        or _CROWN_ON_IMPLANT_RX.search(text)
    ):
        evidence.append("prosthetic_stage_phrase")
        return "existing_implant_prosthetic_stage", 0.91, evidence, False, None, None

    if _UPPER_JAW_BONE_RX.search(text) or (
        "upper_jaw" in cues.anatomy and "bone_deficit" in cues.state
    ):
        evidence.append("upper_jaw_bone")
        return "upper_jaw_missing_or_complex", 0.89, evidence, False, None, None

    if _UPPER_JAW_RX.search(text) or (
        "upper_jaw" in cues.anatomy and ("missing" in cues.state or cues.quantity == "jaw")
    ):
        evidence.append("upper_jaw_scope")
        return "upper_jaw_missing_or_complex", 0.88, evidence, False, None, None

    if _BONE_DEFICIT_RX.search(text) or _SINUS_GRAFT_RX.search(text):
        evidence.append("bone_deficit_cue")
        conf = 0.9 if _SINUS_GRAFT_RX.search(text) else 0.86
        return "bone_deficit_or_grafting", conf, evidence, False, None, None

    if (
        _EXTRACTION_IMPLANT_RX.search(text)
        or _ONE_STAGE_PRICE_RX.search(text)
    ):
        evidence.append("extraction_then_implant")
        return "extraction_then_implant", 0.9, evidence, False, None, None

    if (
        _ALL_TEETH_MISSING_RX.search(text)
        or _FULL_ARCH_RX.search(text)
        or _FULL_JAW_RESTORE_RX.search(text)
        or (
            cues.quantity in {"all", "jaw"}
            and ("missing" in cues.state or cues.intent in {"restore", "choose_solution"})
            and "upper_jaw" not in cues.anatomy
        )
    ):
        evidence.append("full_arch_missing")
        return "full_arch_missing", 0.92, evidence, False, None, None

    if (
        _ONE_TOOTH_EXPLICIT_RX.search(text)
        or _ONE_TOOTH_SITUATION_RX.search(text)
        or (
            _EXTRACTED_TOOTH_RX.search(text)
            and (_RESTORE_RX.search(text) or _IMPLANT_INTEREST_RX.search(text))
        )
        or (_GAP_RX.search(text) and re.search(r"закрыть", text, re.I | re.U))
    ):
        evidence.append("one_tooth_missing")
        conf = 0.94 if _ONE_TOOTH_SITUATION_RX.search(text) else 0.82
        return "one_tooth_missing", conf, evidence, False, None, None

    if _FEW_TEETH_RX.search(text):
        evidence.append("few_teeth_explicit")
        return "few_teeth_missing", 0.84, evidence, False, None, None

    if _CHEW_SIDE_RX.search(text):
        evidence.append("chew_side_ambiguous")
        return (
            "few_teeth_missing",
            0.62,
            evidence,
            True,
            "Речь про один зуб или про несколько / всю челюсть?",
            "ambiguous_chew_side",
        )

    if _GENERIC_IMPLANT_RX.search(text) or (
        _IMPLANT_INTEREST_RX.search(text)
        and len(text.split()) >= 3
        and cues.intent in {"choose_solution", "unknown"}
        and cues.quantity == "unknown"
        and "missing" not in cues.state
    ):
        evidence.append("generic_implant_interest")
        return "generic_implant_interest", 0.87, evidence, False, None, None

    if re.search(r"пустое\s+место|сбоку", text, re.I | re.U) and cues.quantity == "unknown":
        evidence.append("vague_location")
        return (
            "unknown",
            0.38,
            evidence,
            True,
            "Речь про один зуб или про всю челюсть?",
            "vague_location",
        )

    if len(text.strip()) < 12 and cues.quantity == "unknown" and not cues.state:
        evidence.append("short_vague")
        return "unknown", 0.25, evidence, True, None, "short_vague_query"

    return "unknown", 0.3, evidence, should_clarify, clarify_question, clarification_reason


def detect_patient_situation(
    q: str,
    *,
    session_context: PatientSituationSessionContext | None = None,
    client_id: str | None = None,
) -> PatientSituationResult:
    """Detect patient situation from query (+ optional session context for future slices)."""
    del client_id  # Slice 2+: pricebook-aware excludes
    text = (q or "").strip()
    if session_context and session_context.last_question and not text:
        text = session_context.last_question.strip()

    if not text:
        return PatientSituationResult(
            kind="unknown",
            confidence=0.0,
            source="unknown",
            evidence=[],
            patient_scope="unknown",
            next_best_action="none",
            should_clarify=False,
        )

    cues = _extract_cues(text)
    kind, confidence, evidence, should_clarify, clarify_q, clarify_reason = _resolve_from_cues(
        text, cues
    )

    if not should_clarify:
        amb_clarify, amb_q, amb_reason = _clarify_for_ambiguous(cues)
        if amb_clarify:
            should_clarify = True
            clarify_q = amb_q
            clarify_reason = amb_reason

    excludes, preferred_ids, preferred_groups = _hints_for_kind(kind)
    next_action = _next_action_for(kind, intent=cues.intent, should_clarify=should_clarify)

    return PatientSituationResult(
        kind=kind,
        confidence=confidence,
        source="rule_based" if kind != "unknown" or confidence > 0 else "unknown",
        evidence=evidence,
        patient_scope=_scope_for_kind(kind),
        exclude_service_ids=excludes,
        preferred_service_ids=preferred_ids,
        preferred_groups=preferred_groups,
        next_best_action=next_action,
        should_clarify=should_clarify,
        clarify_question=clarify_q,
        clarification_reason=clarify_reason,
        cues=cues,
    )


def patient_situation_telemetry(result: PatientSituationResult) -> dict[str, Any]:
    """Flat telemetry dict for request.ctx / bot events."""
    return {
        "patient_situation_kind": result.kind,
        "patient_situation_confidence": result.confidence,
        "patient_scope": result.patient_scope,
        "patient_next_best_action": result.next_best_action,
        "patient_situation_evidence": list(result.evidence),
        "patient_situation_source": result.source,
        "patient_situation_should_clarify": result.should_clarify,
        "patient_situation_clarify_question": result.clarify_question,
        "patient_situation_clarification_reason": result.clarification_reason,
    }


def record_patient_situation_ctx(result: PatientSituationResult) -> None:
    """Write patient situation telemetry to Flask request.ctx (Slice 1 observability)."""
    try:
        from flask import request
    except ImportError:
        return
    if not hasattr(request, "ctx"):
        return
    for key, value in patient_situation_telemetry(result).items():
        request.ctx[key] = value
