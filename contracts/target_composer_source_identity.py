"""Composer source identity sidecar for FullContext answers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MarketingScenarioKind = Literal[
    "pain_fear",
    "cost",
    "time",
    "doctor_trust",
    "result_reliability",
]

MARKETING_SCENARIO_KINDS: frozenset[str] = frozenset(
    {
        "pain_fear",
        "cost",
        "time",
        "doctor_trust",
        "result_reliability",
    }
)


@dataclass(frozen=True, slots=True)
class TargetComposerSourceIdentity:
    primary_content_ref: str | None
    used_content_refs: tuple[str, ...]
