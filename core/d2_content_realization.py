"""Mechanical publication checks for D2 model-authored prose.

This module deliberately has no access to the raw question, model flags beyond the
typed request, or tenant files.  It only decides whether one already-grounded prose
block can be frozen, recovered from its explicitly named section, or unavailable.
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
    """Return one frozen content result without interpreting prose semantics."""

    if request.content_realization == "authored":
        return D2ContentRealization(
            outcome="answered",
            publication="authored",
            display_text=_exact_authored_text(request, authority),
            section_refs=request.content_section_refs,
        )

    text = (request.content_text or "").strip()
    reason: ContentViolation | None = None
    if not text:
        reason = "d2_model_prose_empty"
    elif _MONEY.search(text):
        reason = "d2_model_prose_money"
    elif _LINK.search(text):
        reason = "d2_model_prose_link"
    if reason is None:
        return D2ContentRealization(
            outcome="answered",
            publication="model_prose",
            display_text=text,
            section_refs=request.content_section_refs,
        )

    recovery_refs = _recovery_section_refs(request)
    recovered: list[str] = []
    used: list[str] = []
    by_ref = {section.section_ref: section for section in authority.sections}
    for ref in recovery_refs:
        section = by_ref.get(ref)
        if section is None:
            continue
        recovered.append(section.display_text)
        used.append(ref)
    if recovered:
        return D2ContentRealization(
            outcome="recovered",
            publication="fallback",
            display_text="\n\n".join(recovered),
            section_refs=tuple(used),
            reason=reason,
        )
    return D2ContentRealization(
        outcome="unavailable",
        publication=None,
        display_text=None,
        section_refs=(),
        reason=reason,
    )


def _is_korotko_section(ref: str) -> bool:
    token = ref.rsplit(":", 1)[-1]
    return token == "korotko" or ref.endswith("#korotko")


def _recovery_section_refs(request: RequestUnderstandingRequest) -> tuple[str, ...]:
    fallback = request.content_fallback_section_ref
    if fallback is None:
        return ()
    if _is_korotko_section(fallback):
        specific = tuple(
            ref for ref in request.content_section_refs if not _is_korotko_section(ref)
        )
        if specific:
            return specific
    return (fallback,)


def _exact_authored_text(
    request: RequestUnderstandingRequest,
    authority: D2AuthoredContentAuthority,
) -> str:
    if not request.content_section_refs:
        return authority.display_text
    by_ref = {section.section_ref: section for section in authority.sections}
    return "\n\n".join(by_ref[ref].display_text for ref in request.content_section_refs)
