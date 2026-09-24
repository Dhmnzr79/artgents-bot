"""Publication of D2 model-authored prose and non-blocking review signals.

This module deliberately has no access to the raw question, model flags beyond the
typed request, or tenant files. A nonempty model answer is published without
copying a document section into the reply.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from contracts.request_understanding import RequestUnderstandingRequest
from contracts.response_plan_materialization import D2AuthoredContentAuthority


ContentOutcome = Literal["answered", "recovered", "unavailable"]
ContentPublication = Literal["authored", "model_prose", "fallback"]
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
    authority: D2AuthoredContentAuthority,
) -> D2ContentRealization:
    """Publish the model's answer; a document is evidence, never reply copy."""

    text = (request.content_text or "").strip()
    if not text:
        return D2ContentRealization(
            outcome="unavailable", publication=None, display_text=None,
            section_refs=(), reason="d2_model_prose_empty",
        )
    return D2ContentRealization(
        outcome="answered", publication="model_prose", display_text=text,
        section_refs=request.content_section_refs,
    )


def realize_d2_unattributed_content(
    request: RequestUnderstandingRequest,
) -> D2ContentRealization:
    """Publish ordinary FullContext prose without a document-route requirement.

    The model has already received the complete approved corpus. Numbers and
    links in its answer are review signals, not reasons to hide the answer.
    """

    text = (request.content_text or "").strip()
    if not text:
        return D2ContentRealization(
            outcome="unavailable", publication=None, display_text=None,
            section_refs=(), reason="d2_model_prose_empty",
        )
    return D2ContentRealization(
        outcome="answered", publication="model_prose", display_text=text,
        section_refs=(),
    )


def d2_content_review_flags(text: str) -> tuple[ContentViolation, ...]:
    """Flag prose for later review without changing what the visitor sees."""
    flags: list[ContentViolation] = []
    if _MONEY.search(text):
        flags.append("d2_model_prose_money")
    if _LINK.search(text):
        flags.append("d2_model_prose_link")
    return tuple(flags)
