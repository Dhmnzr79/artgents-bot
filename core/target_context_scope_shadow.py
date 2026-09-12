"""Post-verification shadow comparison + observability (PERF-6 Phase 2, shadow-only).

Compares a locally-resolved ``TargetContextScopeDecision`` against what the real, unmodified
Composer/Verifier pipeline actually needed -- log-only, never gating, never retried, never able to
change the real answer/route/UI. See
``docs/evidence/performance/FINAL_MULTI_LEVEL_SCOPED_CONTEXT_SHADOW_SEAM_AUDIT.md`` §§7-9.

Comparison uses the **post-validation** source identity
(``TargetVerifiedComposedResponse.primary_content_ref``/``used_content_refs``, already filtered by
``core/target_presentation_source_identity.py::validate_used_content_refs`` inside the Verifier) --
never the Composer's raw, unvalidated JSON claim -- so an invented/nonexistent ref can never
inflate ``shadow_hit``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from contracts.target_context_scope_decision import TargetContextScopeDecision
from core.target_composer_request import TargetComposerRequest
from core.target_context_scope_resolver import ContextScopeLevel
from core.target_response_verifier import TargetVerifiedComposedResponse
from logging_setup import emit_bot_event, get_logger

logger = get_logger("target_context_scope_shadow")

SHADOW_TIMING_MARK = "scoped_context_shadow_ms"
_EVENT_NAME = "scoped_context_shadow_comparison"

ComparisonStatus: TypeAlias = Literal["compared", "not_available_verifier_blocked"]


@dataclass(frozen=True, slots=True)
class TargetContextScopeShadowComparison:
    shadow_hit: bool
    missing_source_classes: tuple[str, ...]
    estimated_reduction_tokens: int
    comparison_status: ComparisonStatus


def compare_target_context_scope_shadow(
    decision: TargetContextScopeDecision,
    request: TargetComposerRequest,
    verified: TargetVerifiedComposedResponse,
    *,
    full_context_estimated_tokens: int,
) -> TargetContextScopeShadowComparison:
    """Compare ``decision`` against the real, already-verified response.

    Never mutates ``request``/``verified``. Never raises for an ordinary comparison outcome --
    a comparison always produces a result, only a structurally-invalid ``verified`` object is a
    programmer error, not a shadow-miss.
    """

    reduction = max(0, full_context_estimated_tokens - decision.estimated_tokens)

    if decision.level == "full":
        # The full corpus is, by construction, a superset of any narrower candidate -- a `full`
        # decision is definitionally always sufficient.
        return TargetContextScopeShadowComparison(
            shadow_hit=True,
            missing_source_classes=(),
            estimated_reduction_tokens=0,
            comparison_status="compared",
        )

    validated_used: set[str] = set(verified.used_content_refs)
    if verified.primary_content_ref:
        validated_used.add(verified.primary_content_ref)

    missing: list[str] = []
    if not validated_used.issubset(set(decision.included_content_refs)):
        missing.append("content")

    required_fact_ids = set(request.spec.required_fact_ids)
    if not required_fact_ids.issubset(set(decision.included_fact_ids)):
        missing.append("fact")

    for component in request.spec.required_components:
        if component == "price" and not decision.included_offer_ids:
            missing.append("offer")
        if component == "doctors" and not decision.included_doctor_ids:
            missing.append("doctor")

    missing_unique = tuple(dict.fromkeys(missing))
    return TargetContextScopeShadowComparison(
        shadow_hit=not missing_unique,
        missing_source_classes=missing_unique,
        estimated_reduction_tokens=reduction,
        comparison_status="compared",
    )


def _base_details(
    decision: TargetContextScopeDecision,
    *,
    widening_steps: tuple[ContextScopeLevel, ...],
    full_context_estimated_tokens: int,
    resolver_ms: int,
) -> dict[str, object]:
    return {
        "scope_level": decision.level,
        "scope_reason": decision.reason,
        "context_group_id": decision.context_group_id,
        "included_doc_count": len(decision.included_content_refs),
        "included_offer_count": len(decision.included_offer_ids),
        "included_fact_count": len(decision.included_fact_ids),
        "included_doctor_count": len(decision.included_doctor_ids),
        "estimated_tokens": decision.estimated_tokens,
        "full_context_estimated_tokens": full_context_estimated_tokens,
        "completeness_status": decision.completeness_status,
        "widening_steps": list(widening_steps),
        "widening_step_count": len(widening_steps),
        "resolver_ms": resolver_ms,
        "package_fingerprint": decision.package_fingerprint,
    }


def emit_target_context_scope_shadow_event(
    decision: TargetContextScopeDecision,
    comparison: TargetContextScopeShadowComparison,
    *,
    widening_steps: tuple[ContextScopeLevel, ...],
    full_context_estimated_tokens: int,
    resolver_ms: int,
    client_id: str,
) -> None:
    """Emit one anonymized shadow-comparison event. Best-effort: never raises into the caller."""

    details = _base_details(
        decision,
        widening_steps=widening_steps,
        full_context_estimated_tokens=full_context_estimated_tokens,
        resolver_ms=resolver_ms,
    )
    details.update(
        {
            "estimated_reduction_tokens": comparison.estimated_reduction_tokens,
            "shadow_hit": comparison.shadow_hit,
            "shadow_would_widen": decision.completeness_status != "complete",
            "missing_source_classes": list(comparison.missing_source_classes),
            "comparison_status": comparison.comparison_status,
        }
    )
    try:
        emit_bot_event(
            logger,
            _EVENT_NAME,
            status="info",
            details=details,
            client_id=client_id,
        )
    except Exception:  # noqa: BLE001 -- observability must never affect the real response
        pass


def emit_target_context_scope_shadow_blocked_event(
    decision: TargetContextScopeDecision,
    *,
    widening_steps: tuple[ContextScopeLevel, ...],
    full_context_estimated_tokens: int,
    resolver_ms: int,
    client_id: str,
) -> None:
    """Emit a shadow event for a turn where the real Verifier blocked the answer.

    The real exception is never touched here -- callers must re-raise it unchanged after this
    (best-effort, never-raising) call. Never attempts to repair, retry, or widen the real Composer
    call post-hoc.
    """

    details = _base_details(
        decision,
        widening_steps=widening_steps,
        full_context_estimated_tokens=full_context_estimated_tokens,
        resolver_ms=resolver_ms,
    )
    details.update(
        {
            "estimated_reduction_tokens": max(
                0, full_context_estimated_tokens - decision.estimated_tokens
            ),
            "shadow_hit": None,
            "shadow_would_widen": decision.completeness_status != "complete",
            "missing_source_classes": [],
            "comparison_status": "not_available_verifier_blocked",
        }
    )
    try:
        emit_bot_event(
            logger,
            _EVENT_NAME,
            status="info",
            details=details,
            client_id=client_id,
        )
    except Exception:  # noqa: BLE001 -- observability must never affect the real response
        pass


__all__ = [
    "SHADOW_TIMING_MARK",
    "TargetContextScopeShadowComparison",
    "compare_target_context_scope_shadow",
    "emit_target_context_scope_shadow_event",
    "emit_target_context_scope_shadow_blocked_event",
]
