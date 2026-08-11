"""Stage 3C quality guard rules (v2 scorer semantics)."""

from __future__ import annotations

import re

_FORBIDDEN_TOTAL_LINE_RE = re.compile(
    r"(?:^|\n)\s*итого\s*[:\-—]?\s*\d",
    re.IGNORECASE,
)
_COMPUTED_TOTAL_RE = re.compile(
    r"(?:общая\s+стоимость\s+составит|составит\s+\d|×\s*\d|\d\s*×)",
    re.IGNORECASE,
)


def matches_forbidden_term(term: str, answer: str) -> bool:
    lowered_term = term.strip().lower()
    lowered_answer = answer.lower()
    if not lowered_term:
        return False
    if lowered_term == "итого":
        if _FORBIDDEN_TOTAL_LINE_RE.search(answer):
            return True
        if re.search(r"\bитого\s+\d", lowered_answer):
            return True
        return False
    if lowered_term == "умнож":
        return lowered_term in lowered_answer or "×" in answer
    return lowered_term in lowered_answer


def matches_forbidden_computed_total(answer: str) -> bool:
    return bool(_COMPUTED_TOTAL_RE.search(answer))
