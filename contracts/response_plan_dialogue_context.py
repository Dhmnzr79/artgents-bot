"""Typed dialogue continuity for confirmed shown service options."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from contracts.response_plan import SessionKey

ShownOptionsProvenance = Literal[
    "finalized_plan_service_options",
    "finalized_plan_price_offers",
]
_VALID_SHOWN_PROVENANCES = frozenset(
    {"finalized_plan_service_options", "finalized_plan_price_offers"}
)


class ShownOptionsSnapshotError(ValueError):
    """Strict validation error for shown-options snapshot input."""


def require_non_negative_int(field: str, value: object) -> int:
    if type(value) is bool:
        raise ShownOptionsSnapshotError(f"{field}_bool_forbidden")
    if isinstance(value, float):
        if math.isnan(value):
            raise ShownOptionsSnapshotError(f"{field}_nan_forbidden")
        raise ShownOptionsSnapshotError(f"{field}_float_forbidden")
    if not isinstance(value, int):
        raise ShownOptionsSnapshotError(f"{field}_not_int")
    if value < 0:
        raise ShownOptionsSnapshotError(f"{field}_negative")
    return value


@dataclass(frozen=True, slots=True)
class ShownServiceOptionsSnapshot:
    session_key: SessionKey
    topic_id: str
    service_ids: tuple[str, ...]
    shown_at_turn: int
    provenance: ShownOptionsProvenance = "finalized_plan_service_options"

    def __post_init__(self) -> None:
        if self.provenance not in _VALID_SHOWN_PROVENANCES:
            raise ShownOptionsSnapshotError("shown_provenance_invalid")
        require_non_negative_int("shown_at_turn", self.shown_at_turn)
        if not self.topic_id or not self.topic_id.strip():
            raise ShownOptionsSnapshotError("shown_topic_blank")
        if self.topic_id != self.topic_id.strip():
            raise ShownOptionsSnapshotError("shown_topic_padded")
        if not self.service_ids:
            raise ShownOptionsSnapshotError("shown_service_ids_empty")
        seen: set[str] = set()
        for service_id in self.service_ids:
            if not service_id or not service_id.strip():
                raise ShownOptionsSnapshotError("shown_service_id_blank")
            if service_id != service_id.strip():
                raise ShownOptionsSnapshotError("shown_service_id_padded")
            if service_id in seen:
                raise ShownOptionsSnapshotError("shown_service_id_duplicate")
            seen.add(service_id)


@dataclass(frozen=True, slots=True)
class ShownOptionsFreshnessPolicy:
    max_age_turns: int

    def __post_init__(self) -> None:
        require_non_negative_int("max_age_turns", self.max_age_turns)


@dataclass(frozen=True, slots=True)
class ModelVisibleShownOptions:
    topic_id: str
    services: tuple[tuple[str, str], ...]
