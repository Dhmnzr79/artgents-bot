"""Deterministic post-Composer service selection orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.effective_scope import EffectiveScope
from contracts.response_plan_composer import ComposerDecisionDiagnostic, OptionReferenceKind
from contracts.response_plan_post_composer import (
    PostComposerDiagnostic,
    ReferenceServiceStatus,
    SelectionBasis,
    SelectionPresentationIntent,
)
from contracts.response_schema import ResponseSchemaBundle, TargetService
from contracts.target_service_applicability import SelectionPatientContext
from core.response_plan_dialogue_context import ValidatedShownOptionsSnapshot
from core.response_strategy import resolve_target_strategy
from core.target_service_applicability import (
    exclusion_codes_for_service,
    filter_applicable_services,
)
from core.target_strategy_context import (
    selection_patient_context_from_inputs,
    strategy_match_from_effective_scope,
)

REJECTED_REFERENCE_DIAGNOSTIC_CODES = frozenset(
    {"service_id_not_allowed", "active_session_service_unavailable"}
)


@dataclass(frozen=True, slots=True)
class ServiceSelectionResult:
    reference_service_status: ReferenceServiceStatus
    ranked_service_ids: tuple[str, ...]
    visible_service_option_ids: tuple[str, ...]
    price_candidate_service_ids: tuple[str, ...]
    comparison_service_ids: tuple[str, ...]
    selection_basis: SelectionBasis
    selection_intent: SelectionPresentationIntent
    diagnostics: tuple[PostComposerDiagnostic, ...]


def adapter_reference_rejection(
    diagnostics: tuple[ComposerDecisionDiagnostic, ...],
) -> tuple[bool, object | None]:
    for item in diagnostics:
        if item.code in REJECTED_REFERENCE_DIAGNOSTIC_CODES:
            return True, item.detail
    return False, None


def _patient_axis(patient: SelectionPatientContext, field: str) -> str | None:
    if field == "extent":
        if patient.extent == "unknown":
            return None
        return patient.extent
    return getattr(patient, field)


def _axis_conflict_unknown(
    service: TargetService,
    patient: SelectionPatientContext,
) -> tuple[bool, bool]:
    selection = service.selection
    has_unknown = False
    has_conflict = False
    for field in ("extent", "stage", "jaw", "reported_context"):
        required = getattr(selection, field, None)
        if required is None:
            continue
        patient_value = _patient_axis(patient, field)
        if patient_value is None:
            has_unknown = True
        elif patient_value not in required:
            has_conflict = True
    return has_unknown, has_conflict


def resolve_reference_service_status(
    bundle: ResponseSchemaBundle,
    *,
    reference_service_id: str,
    resolved_topic_id: str | None,
    patient: SelectionPatientContext,
) -> tuple[ReferenceServiceStatus, tuple[PostComposerDiagnostic, ...]]:
    service = bundle.services.get(reference_service_id)
    if service is None or not service.active:
        return "unknown", (
            PostComposerDiagnostic(
                code="reference_service_unavailable",
                detail=reference_service_id,
            ),
        )

    if resolved_topic_id is not None:
        applicable = filter_applicable_services(
            bundle,
            topic=resolved_topic_id,
            patient=patient,
            explicit_service_id=reference_service_id,
            explicit_service_price_lookup=False,
        )
        if not any(item.service_id == reference_service_id for item in applicable):
            has_unknown, has_conflict = _axis_conflict_unknown(service, patient)
            if has_conflict:
                return "conflict", (
                    PostComposerDiagnostic(
                        code="explicit_service_situation_conflict",
                        detail=reference_service_id,
                    ),
                )
            return "unknown", ()

    codes = exclusion_codes_for_service(
        service,
        patient=patient,
        explicit_service_id=reference_service_id,
        service_id=reference_service_id,
    )
    if not codes:
        return "compatible", ()
    has_unknown, has_conflict = _axis_conflict_unknown(service, patient)
    if has_conflict:
        return "conflict", (
            PostComposerDiagnostic(
                code="explicit_service_situation_conflict",
                detail=reference_service_id,
            ),
        )
    return "unknown", ()


def _price_requested(requested_aspect_ids: tuple[str, ...]) -> bool:
    return "price" in requested_aspect_ids


def _comparison_requested(requested_aspect_ids: tuple[str, ...]) -> bool:
    return "comparison" in requested_aspect_ids


def _overview_requested(requested_aspect_ids: tuple[str, ...]) -> bool:
    return "overview" in requested_aspect_ids


def _has_known_extent(effective_scope: EffectiveScope) -> bool:
    return effective_scope.extent != "unknown"


def _rank_situation_candidates(
    bundle: ResponseSchemaBundle,
    *,
    effective_scope: EffectiveScope,
    resolved_topic_id: str,
) -> tuple[str, ...]:
    patient = selection_patient_context_from_inputs(effective_scope)
    applicable = filter_applicable_services(
        bundle,
        topic=resolved_topic_id,
        patient=patient,
    )
    if not applicable:
        return ()
    resolution = resolve_target_strategy(
        bundle.strategy,
        strategy_match_from_effective_scope(effective_scope),
        service_ids=tuple(item.service_id for item in applicable),
    )
    return resolution.service_ids


def _filter_snapshot_candidates(
    bundle: ResponseSchemaBundle,
    *,
    snapshot: ValidatedShownOptionsSnapshot,
    effective_scope: EffectiveScope,
    resolved_topic_id: str,
) -> tuple[tuple[str, ...], tuple[PostComposerDiagnostic, ...]]:
    patient = selection_patient_context_from_inputs(effective_scope)
    diagnostics: list[PostComposerDiagnostic] = []
    kept: list[str] = []
    for service_id in snapshot.eligible_service_ids:
        status, status_diag = resolve_reference_service_status(
            bundle,
            reference_service_id=service_id,
            resolved_topic_id=resolved_topic_id,
            patient=patient,
        )
        diagnostics.extend(status_diag)
        if status == "compatible":
            kept.append(service_id)
        else:
            diagnostics.append(
                PostComposerDiagnostic(
                    code="shown_options_snapshot_unavailable",
                    detail=service_id,
                )
            )
    return tuple(kept), tuple(diagnostics)


def post_composer_reference_blocked(
    *,
    reference_rejected: bool,
    reference_service_id: str | None,
    reference_status: ReferenceServiceStatus,
    diagnostics: tuple[PostComposerDiagnostic, ...],
) -> bool:
    if reference_rejected:
        return True
    if reference_service_id is None:
        return False
    if any(
        diagnostic.code
        in {
            "reference_service_unavailable",
            "post_composer_active_service_unavailable",
        }
        for diagnostic in diagnostics
    ):
        return True
    if reference_status == "unknown":
        return any(
            diagnostic.code == "reference_service_unavailable"
            for diagnostic in diagnostics
        )
    return False


def resolve_service_selection(
    bundle: ResponseSchemaBundle,
    *,
    effective_scope: EffectiveScope,
    resolved_topic_id: str | None,
    reference_service_id: str | None,
    reference_rejected: bool,
    option_reference_kind: OptionReferenceKind,
    validated_shown: ValidatedShownOptionsSnapshot | None,
    requested_aspect_ids: tuple[str, ...],
) -> ServiceSelectionResult:
    diagnostics: list[PostComposerDiagnostic] = []
    patient = selection_patient_context_from_inputs(effective_scope)

    reference_status: ReferenceServiceStatus = "none"
    if reference_service_id is not None:
        reference_status, status_diag = resolve_reference_service_status(
            bundle,
            reference_service_id=reference_service_id,
            resolved_topic_id=resolved_topic_id,
            patient=patient,
        )
        diagnostics.extend(status_diag)

    ranked: tuple[str, ...] = ()
    visible: tuple[str, ...] = ()
    price_candidates: tuple[str, ...] = ()
    comparison_ids: tuple[str, ...] = ()
    basis: SelectionBasis = "none"
    intent: SelectionPresentationIntent = "none"

    price = _price_requested(requested_aspect_ids)
    comparison = _comparison_requested(requested_aspect_ids)
    overview = _overview_requested(requested_aspect_ids)

    if reference_rejected:
        diagnostics.append(PostComposerDiagnostic(code="reference_service_rejected"))
        return ServiceSelectionResult(
            reference_service_status=reference_status,
            ranked_service_ids=(),
            visible_service_option_ids=(),
            price_candidate_service_ids=(),
            comparison_service_ids=(),
            selection_basis="none",
            selection_intent="none",
            diagnostics=tuple(diagnostics),
        )
    if post_composer_reference_blocked(
        reference_rejected=False,
        reference_service_id=reference_service_id,
        reference_status=reference_status,
        diagnostics=tuple(diagnostics),
    ):
        diagnostics.append(PostComposerDiagnostic(code="reference_service_rejected"))
        return ServiceSelectionResult(
            reference_service_status=reference_status,
            ranked_service_ids=(),
            visible_service_option_ids=(),
            price_candidate_service_ids=(),
            comparison_service_ids=(),
            selection_basis="none",
            selection_intent="none",
            diagnostics=tuple(diagnostics),
        )

    if option_reference_kind == "shown_options":
        if validated_shown is None:
            diagnostics.append(PostComposerDiagnostic(code="shown_options_snapshot_unavailable"))
            return ServiceSelectionResult(
                reference_service_status=reference_status,
                ranked_service_ids=(),
                visible_service_option_ids=(),
                price_candidate_service_ids=(),
                comparison_service_ids=(),
                selection_basis="none",
                selection_intent="none",
                diagnostics=tuple(diagnostics),
            )
        if resolved_topic_id is None:
            diagnostics.append(PostComposerDiagnostic(code="shown_options_snapshot_unavailable"))
            return ServiceSelectionResult(
                reference_service_status=reference_status,
                ranked_service_ids=(),
                visible_service_option_ids=(),
                price_candidate_service_ids=(),
                comparison_service_ids=(),
                selection_basis="none",
                selection_intent="none",
                diagnostics=tuple(diagnostics),
            )
        snapshot_ids, snapshot_diag = _filter_snapshot_candidates(
            bundle,
            snapshot=validated_shown,
            effective_scope=effective_scope,
            resolved_topic_id=resolved_topic_id,
        )
        diagnostics.extend(snapshot_diag)
        if reference_service_id is not None and reference_service_id not in snapshot_ids:
            diagnostics.append(
                PostComposerDiagnostic(
                    code="explicit_service_not_in_shown_options",
                    detail=reference_service_id,
                )
            )
        basis = "shown_options"
        ranked = snapshot_ids
        if comparison:
            comparison_ids = snapshot_ids
            if len(comparison_ids) < 2:
                diagnostics.append(
                    PostComposerDiagnostic(code="insufficient_comparison_candidates")
                )
            intent = "comparison_candidates"
        if price:
            price_candidates = snapshot_ids
            intent = "price_candidates" if not comparison else intent
        return ServiceSelectionResult(
            reference_service_status=reference_status,
            ranked_service_ids=ranked,
            visible_service_option_ids=(),
            price_candidate_service_ids=price_candidates,
            comparison_service_ids=comparison_ids,
            selection_basis=basis,
            selection_intent=intent,
            diagnostics=tuple(diagnostics),
        )

    has_reference = reference_service_id is not None
    if has_reference and price:
        if reference_status != "compatible":
            diagnostics.append(PostComposerDiagnostic(code="reference_service_rejected"))
            return ServiceSelectionResult(
                reference_service_status=reference_status,
                ranked_service_ids=(),
                visible_service_option_ids=(),
                price_candidate_service_ids=(),
                comparison_service_ids=(),
                selection_basis="none",
                selection_intent="none",
                diagnostics=tuple(diagnostics),
            )
        price_candidates = (reference_service_id,)
        basis = "referenced_service"
        intent = "price_candidates"
        if comparison and option_reference_kind != "shown_options":
            diagnostics.append(
                PostComposerDiagnostic(code="insufficient_comparison_candidates")
            )
        return ServiceSelectionResult(
            reference_service_status=reference_status,
            ranked_service_ids=(),
            visible_service_option_ids=(),
            price_candidate_service_ids=price_candidates,
            comparison_service_ids=(),
            selection_basis=basis,
            selection_intent=intent,
            diagnostics=tuple(diagnostics),
        )

    if has_reference:
        return ServiceSelectionResult(
            reference_service_status=reference_status,
            ranked_service_ids=(),
            visible_service_option_ids=(),
            price_candidate_service_ids=(),
            comparison_service_ids=(),
            selection_basis="referenced_service" if has_reference else "none",
            selection_intent="none",
            diagnostics=tuple(diagnostics),
        )

    if resolved_topic_id is not None and _has_known_extent(effective_scope):
        ranked = _rank_situation_candidates(
            bundle,
            effective_scope=effective_scope,
            resolved_topic_id=resolved_topic_id,
        )
        if not ranked:
            diagnostics.append(PostComposerDiagnostic(code="no_applicable_services"))
        if price:
            price_candidates = tuple(ranked[:3])
            basis = "current_situation"
            intent = "price_candidates"
        elif overview or comparison:
            visible = tuple(ranked[:3])
            basis = "current_situation"
            intent = "service_options"
        else:
            basis = "current_situation" if ranked else "none"

    return ServiceSelectionResult(
        reference_service_status=reference_status,
        ranked_service_ids=ranked,
        visible_service_option_ids=visible,
        price_candidate_service_ids=price_candidates,
        comparison_service_ids=comparison_ids,
        selection_basis=basis,
        selection_intent=intent,
        diagnostics=tuple(diagnostics),
    )
