"""Mechanical publication checks for D2 model-authored prose.

This module deliberately has no access to the raw question, model flags beyond the
typed request, or tenant files.  It only decides whether one already-grounded prose
block can be frozen or is unavailable. Documents never replace model prose.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from contracts.request_understanding import RequestUnderstandingRequest
from core import d2_diagnostics


ContentOutcome = Literal["answered", "unavailable"]
ContentPublication = Literal["model_prose"]
ContentViolation = Literal[
    "d2_model_prose_empty",
    "d2_model_prose_money",
    "d2_model_prose_link",
    "d2_content_source_missing",
]

_MONEY = re.compile(
    r"(?ix)(?:\d{1,3}(?:[\s\u00a0,]\d{3})+|\d+)(?:[.,]\d{1,2})?\s*"
    r"(?:₽|руб(?:\.|лей)?|rub|usd|eur|\$|€)"
)
_LINK = re.compile(
    r"(?ix)(?:\[[^\]]+\]\([^)]*\)|\b[a-z][a-z0-9+.-]*:\S*|www\.\S+)"
)


@dataclass(frozen=True, slots=True)
class D2ContentRealization:
    outcome: ContentOutcome
    publication: ContentPublication | None
    display_text: str | None
    section_refs: tuple[str, ...]
    reason: ContentViolation | None = None


def realize_d2_content(
    request: RequestUnderstandingRequest,
) -> D2ContentRealization:
    """Return one frozen content result without interpreting prose semantics."""

    text = (request.content_text or "").strip()
    if text:
        _observe_model_prose(text)
        return D2ContentRealization(
            outcome="answered",
            publication="model_prose",
            display_text=text,
            section_refs=request.content_section_refs,
        )

    reason: ContentViolation = "d2_model_prose_empty"
    return D2ContentRealization(
        outcome="unavailable",
        publication=None,
        display_text=None,
        section_refs=(),
        reason=reason,
    )


def realize_d2_unattributed_content(
    request: RequestUnderstandingRequest,
) -> D2ContentRealization:
    """Publish ordinary FullContext prose without a document-route requirement.

    The model has already received the complete approved corpus. Optional
    provenance does not decide whether nonempty prose can be published.
    """

    text = (request.content_text or "").strip()
    if not text:
        return D2ContentRealization(
            outcome="unavailable", publication=None, display_text=None,
            section_refs=(), reason="d2_model_prose_empty",
        )
    _observe_model_prose(text)
    return D2ContentRealization(
        outcome="answered", publication="model_prose", display_text=text,
        section_refs=(),
    )


def _observe_model_prose(text: str) -> None:
    # Existing mechanical detectors are review signals only. Never log prose.
    if _MONEY.search(text):
        d2_diagnostics.prose_review_signal("d2_model_prose_money")
    if _LINK.search(text):
        d2_diagnostics.prose_review_signal("d2_model_prose_link")
