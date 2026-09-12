"""Canonical Scoped FullContext decision contract (PERF-6 Phase 2, shadow-only).

Immutable, strict, anonymized. Never carries document text, question, answer, SID, or contact
values -- every field is an enum, a count, a hash, or a reference ID. Produced by exactly one
canonical resolver (``core/target_context_scope_resolver.py::resolve_target_context_scope``).

This contract is measurement-only: nothing reads it to change the real Composer/Verifier
invocation in this milestone. See
``docs/evidence/performance/FINAL_MULTI_LEVEL_SCOPED_CONTEXT_SHADOW_SEAM_AUDIT.md`` §4.
"""

from __future__ import annotations

import re
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

ContextScopeLevel: TypeAlias = Literal["service_exact", "topic", "context_group", "full"]
ContextScopeCompletenessStatus: TypeAlias = Literal[
    "complete",
    "insufficient_widened",
    "full_required",
]

_CANONICAL_TOKEN_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_canonical_id(value: str) -> bool:
    return bool(value) and value == value.strip() and value != ""


class TargetContextScopeDecision(BaseModel):
    """Strict immutable Scoped FullContext level decision (shadow-only, no product authority)."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    level: ContextScopeLevel
    reason: str
    service_id: str | None = None
    topic: str | None = None
    context_group_id: str | None = None
    included_content_refs: tuple[str, ...] = ()
    included_offer_ids: tuple[str, ...] = ()
    included_fact_ids: tuple[str, ...] = ()
    included_doctor_ids: tuple[str, ...] = ()
    included_policy_sections: tuple[str, ...] = ()
    estimated_chars: int
    estimated_tokens: int
    package_fingerprint: str
    completeness_status: ContextScopeCompletenessStatus
    widening_reason: str | None = None

    @field_validator("reason")
    @classmethod
    def _reason_canonical(cls, value: str) -> str:
        if not _CANONICAL_TOKEN_RE.match(value):
            raise ValueError("context_scope_reason_invalid")
        return value

    @field_validator("widening_reason")
    @classmethod
    def _widening_reason_canonical(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _CANONICAL_TOKEN_RE.match(value):
            raise ValueError("context_scope_widening_reason_invalid")
        return value

    @field_validator(
        "included_content_refs",
        "included_offer_ids",
        "included_fact_ids",
        "included_doctor_ids",
        "included_policy_sections",
    )
    @classmethod
    def _ids_canonical_and_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not all(_is_canonical_id(item) for item in value):
            raise ValueError("context_scope_id_invalid")
        if len(value) != len(set(value)):
            raise ValueError("context_scope_id_duplicate")
        return value

    @field_validator("estimated_chars", "estimated_tokens")
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("context_scope_estimate_negative")
        return value

    @field_validator("package_fingerprint")
    @classmethod
    def _fingerprint_shape(cls, value: str) -> str:
        if not _FINGERPRINT_RE.match(value):
            raise ValueError("context_scope_fingerprint_invalid")
        return value

    @model_validator(mode="after")
    def _consistent_decision(self) -> "TargetContextScopeDecision":
        if self.estimated_tokens != self.estimated_chars // 4:
            raise ValueError("context_scope_token_estimate_inconsistent")
        if self.level == "service_exact" and self.service_id is None:
            raise ValueError("context_scope_service_exact_requires_service_id")
        if self.level == "topic" and self.topic is None:
            raise ValueError("context_scope_topic_requires_topic")
        if self.level == "context_group" and self.context_group_id is None:
            raise ValueError("context_scope_group_requires_group_id")
        if self.level != "context_group" and self.context_group_id is not None:
            raise ValueError("context_scope_group_id_requires_group_level")
        if self.level == "full" and (
            self.service_id is not None
            or self.topic is not None
            or self.context_group_id is not None
        ):
            raise ValueError("context_scope_full_forbids_narrower_identity")
        if self.completeness_status == "complete" and self.widening_reason is not None:
            raise ValueError("context_scope_complete_forbids_widening_reason")
        if self.completeness_status != "complete" and self.widening_reason is None:
            raise ValueError("context_scope_incomplete_requires_widening_reason")
        if self.level == "full" and self.completeness_status == "insufficient_widened":
            # full is either the safe terminal widen target or the immediate fallback --
            # never itself reported as "still insufficient" (there is nothing narrower left).
            raise ValueError("context_scope_full_cannot_be_insufficient_widened")
        return self
