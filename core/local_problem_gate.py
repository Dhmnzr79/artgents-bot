"""Pure local spam/noise gate before Composer.

Only unmistakable non-text noise is blocked locally. Semantic routing
(ADMIN/ANSWER/CLARIFY) is owned by Composer in the same provider call.
"""

from __future__ import annotations

import re

from contracts.local_problem_gate import LocalProblemGateResult


class LocalProblemGateError(ValueError):
    """Raised when the pure gate receives a non-text input."""


_OBVIOUS_TEXT_NOISE_RE = re.compile(r"^[^\w\s]+$", re.UNICODE)


def _normalized_text(value: str) -> str:
    return value.strip().casefold().replace("ё", "е")


def _is_obvious_text_noise(text: str) -> bool:
    """Only stateless, unmistakable text noise belongs to this gate."""

    return len(text) >= 4 and bool(_OBVIOUS_TEXT_NOISE_RE.fullmatch(text))


def decide_local_problem_gate(text: str) -> LocalProblemGateResult:
    """Return ``spam`` or ``pass`` without side effects."""

    if not isinstance(text, str):
        raise LocalProblemGateError("local_problem_gate_text_invalid")
    normalized = _normalized_text(text)
    if _is_obvious_text_noise(normalized):
        return LocalProblemGateResult(
            decision="spam", reason_code="obvious_text_noise"
        )
    return LocalProblemGateResult(
        decision="pass", reason_code="no_high_precision_match"
    )
