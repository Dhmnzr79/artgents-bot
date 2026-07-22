"""Minimal one-family target follow-up policy (S30, offline/unwired)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from core.target_response_followup_materializer import (
    TargetContentFollowup,
    TargetPriceFollowup,
    TargetResponseFollowups,
)


TargetFollowupSource: TypeAlias = Literal["content", "price"]

_SOURCES = frozenset({"content", "price"})


@dataclass(frozen=True, slots=True)
class TargetResponseFollowupSelection:
    source: TargetFollowupSource | None
    content: tuple[TargetContentFollowup, ...]
    price: tuple[TargetPriceFollowup, ...]


class TargetResponseFollowupPolicyError(ValueError):
    """Typed failure for invalid explicit S30 inputs."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _valid_candidates(followups: object) -> bool:
    return (
        type(followups) is TargetResponseFollowups
        and type(followups.content) is tuple
        and all(type(item) is TargetContentFollowup for item in followups.content)
        and type(followups.price) is tuple
        and all(type(item) is TargetPriceFollowup for item in followups.price)
    )


def select_target_response_followups(
    followups: TargetResponseFollowups,
    *,
    source: TargetFollowupSource | None,
) -> TargetResponseFollowupSelection:
    """Expose exactly one explicit S29 family without inference or fallback."""

    if not _valid_candidates(followups):
        raise TargetResponseFollowupPolicyError(
            "followup_policy_candidates_invalid", followups
        )
    if source is not None and (type(source) is not str or source not in _SOURCES):
        raise TargetResponseFollowupPolicyError(
            "followup_policy_source_invalid", source
        )

    if source == "content" and followups.content:
        return TargetResponseFollowupSelection(
            source="content",
            content=followups.content,
            price=(),
        )
    if source == "price" and followups.price:
        return TargetResponseFollowupSelection(
            source="price",
            content=(),
            price=followups.price,
        )
    return TargetResponseFollowupSelection(source=None, content=(), price=())
