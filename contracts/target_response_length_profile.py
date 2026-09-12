"""Canonical adaptive response length profile (PERF-5 Phase 2).

Soft budgets are Composer instructions, never a blocking limit: exceeding a profile's
soft_max never blocks the answer, triggers no retry, no fallback, and no route change
(see docs/evidence/performance/FINAL_ADAPTIVE_RESPONSE_LENGTH_BUDGETS_SEAM_AUDIT.md).
"""

from __future__ import annotations

from typing import Literal

TargetResponseLengthProfile = Literal[
    "clarification_concise",
    "simple_faq",
    "standard_information",
    "marketing_concern",
    "broad_price_overview",
    "scoped_price",
    "comparison_or_complex",
]

_RESPONSE_LENGTH_PROFILES: frozenset[str] = frozenset(
    {
        "clarification_concise",
        "simple_faq",
        "standard_information",
        "marketing_concern",
        "broad_price_overview",
        "scoped_price",
        "comparison_or_complex",
    }
)

# (soft_min, soft_max) chars, over the `answer` text alone -- no UI buttons, no CTA key,
# no source_identity metadata counted.
RESPONSE_LENGTH_SOFT_BUDGETS: dict[TargetResponseLengthProfile, tuple[int, int]] = {
    "clarification_concise": (0, 250),
    "simple_faq": (250, 450),
    "standard_information": (400, 700),
    "marketing_concern": (350, 650),
    "broad_price_overview": (450, 750),
    "scoped_price": (350, 650),
    "comparison_or_complex": (700, 1000),
}


def is_target_response_length_profile(value: object) -> bool:
    return value in _RESPONSE_LENGTH_PROFILES


def response_length_soft_range(profile: TargetResponseLengthProfile) -> tuple[int, int]:
    return RESPONSE_LENGTH_SOFT_BUDGETS[profile]


def response_length_soft_max(profile: TargetResponseLengthProfile) -> int:
    return RESPONSE_LENGTH_SOFT_BUDGETS[profile][1]
