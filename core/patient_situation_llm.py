"""LLM augmentation for patient situation profile."""

from __future__ import annotations

from typing import Any

from llm import classify_patient_situation_semantic as _llm_classify_patient_situation


_ALLOWED_INTENTS = {
    "choose_solution",
    "restore",
    "price",
    "doctor",
    "warranty",
    "compare",
    "unknown",
}
_ALLOWED_PROBLEMS = {
    "missing_teeth",
    "bone_deficit",
    "existing_implant",
    "urgent",
    "generic_implant_interest",
    "unknown",
}
_ALLOWED_EXTENTS = {"one_tooth", "few_teeth", "full_arch", "unknown"}
_ALLOWED_JAWS = {"upper", "lower", "both", "unknown"}
_ALLOWED_MODIFIERS = {"bone_deficit", "extracted", "existing_implant", "urgent"}


def _clean_choice(value: Any, allowed: set[str], default: str = "unknown") -> str:
    text = str(value or "").strip().lower()
    return text if text in allowed else default


def classify_patient_situation_semantic(
    q: str,
    *,
    client_id: str | None = None,
    sid: str | None = None,
) -> dict[str, Any] | None:
    raw = _llm_classify_patient_situation(q, client_id=client_id, sid=sid)
    if not raw:
        return None
    try:
        confidence = float(raw.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    modifiers_raw = raw.get("modifiers")
    modifiers: list[str] = []
    if isinstance(modifiers_raw, list):
        for item in modifiers_raw:
            text = str(item or "").strip().lower()
            if text in _ALLOWED_MODIFIERS and text not in modifiers:
                modifiers.append(text)

    return {
        "intent": _clean_choice(raw.get("intent"), _ALLOWED_INTENTS),
        "problem": _clean_choice(raw.get("problem"), _ALLOWED_PROBLEMS),
        "extent": _clean_choice(raw.get("extent"), _ALLOWED_EXTENTS),
        "jaw": _clean_choice(raw.get("jaw"), _ALLOWED_JAWS),
        "modifiers": modifiers,
        "confidence": confidence,
    }
