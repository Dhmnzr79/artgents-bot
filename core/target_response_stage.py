"""Derive response_stage and stage-clarify discovery (AC3)."""

from __future__ import annotations

from contracts.effective_scope import EffectiveScope
from contracts.response_schema import ResponseSchemaBundle
from contracts.target_response_stage import ResponseStage
from contracts.target_service_applicability import (
    PatientStage,
    SelectionPatientContext,
)
from contracts.target_service_content_topic import service_catalog_content_topic_matches
from contracts.target_scope_aware_selection import TargetScopeAwareSelectionResult
from core.target_family_price_resolution import resolve_explicit_service_price_stage
from core.target_service_applicability import filter_applicable_services
from core.target_strategy_context import selection_patient_context_from_inputs


def _authored_stages_for_topic(
    bundle: ResponseSchemaBundle,
    topic: str,
) -> tuple[PatientStage, ...]:
    stages: list[PatientStage] = []
    seen: set[str] = set()
    for service in bundle.services.values():
        if service.content_ref is None:
            continue
        if not service_catalog_content_topic_matches(service.content_ref, topic):
            continue
        selection = service.selection
        if selection.stage:
            for stage in selection.stage:
                if stage not in seen:
                    seen.add(stage)
                    stages.append(stage)  # type: ignore[arg-type]
    return tuple(stages)


def discover_stage_clarification_stages(
    bundle: ResponseSchemaBundle,
    *,
    topic: str,
    patient: SelectionPatientContext,
) -> tuple[PatientStage, ...]:
    """Return stage values that would change AC2 applicability vs unknown stage."""

    if patient.stage is not None:
        return ()
    baseline = filter_applicable_services(bundle, topic=topic, patient=patient)
    baseline_ids = frozenset(item.service_id for item in baseline)
    useful: list[PatientStage] = []
    for stage in _authored_stages_for_topic(bundle, topic):
        trial = SelectionPatientContext(
            extent=patient.extent,
            stage=stage,
            jaw=patient.jaw,
            reported_context=patient.reported_context,
        )
        trial_services = filter_applicable_services(bundle, topic=topic, patient=trial)
        trial_ids = frozenset(item.service_id for item in trial_services)
        if trial_ids != baseline_ids and trial_ids:
            useful.append(stage)
    return tuple(dict.fromkeys(useful))


def can_collapse_to_concrete_service(
    selection: TargetScopeAwareSelectionResult,
) -> bool:
    if selection.kind != "scoped_shortlist":
        return False
    if len(selection.service_ids) != 1:
        return False
    offers = selection.offers_by_service_id.get(selection.service_ids[0], ())
    return bool(offers)


def derive_response_stage(
    *,
    explicit_service_id: str | None,
    effective_scope: EffectiveScope,
    topic: str,
    bundle: ResponseSchemaBundle,
    selection: TargetScopeAwareSelectionResult | None = None,
) -> ResponseStage:
    if explicit_service_id:
        if selection is not None:
            protocol_stage = resolve_explicit_service_price_stage(
                bundle,
                explicit_service_id=explicit_service_id,
                topic=topic,
                selection=selection,
            )
            if protocol_stage is not None:
                return protocol_stage  # type: ignore[return-value]
            offers = selection.offers_by_service_id.get(explicit_service_id, ())
            if offers:
                return "concrete_service_price"
        return "concrete_service_price"
    patient = selection_patient_context_from_inputs(
        effective_scope,
        stage=effective_scope.stage,
    )
    if effective_scope.extent == "unknown":
        return "broad_family_price"
    if selection is not None and can_collapse_to_concrete_service(selection):
        return "concrete_service_price"
    if selection is not None and selection.kind == "broad_anchors":
        return "broad_family_price"
    applicable = filter_applicable_services(bundle, topic=topic, patient=patient)
    if not applicable:
        stages = discover_stage_clarification_stages(bundle, topic=topic, patient=patient)
        if stages:
            return "stage_clarify"
        return "data_gap"
    if selection is not None and not selection.offers_by_service_id:
        return "data_gap"
    return "scoped_family_price"
