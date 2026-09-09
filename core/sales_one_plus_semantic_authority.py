"""Bind validated envelope + governed UI into authoritative semantic frame (Stage 4.3 / 5.1B)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from contracts.effective_scope import EffectiveScope
from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.one_call_envelope import OneCallCommercialIntent, OneCallEnvelope, OneCallPromotionScope
from contracts.response_schema import ResponseSchemaBundle, TargetClinicStrategy, TargetStrategyMatch, TargetStrategyRule
from contracts.sales_one_plus_semantic import SalesOnePlusSemanticFrame, SemanticFieldProvenance
from contracts.service_reference import AvailabilityStatus
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.target_service_applicability import filter_applicable_services
from core.target_strategy_context import (
    selection_patient_context_from_inputs,
    strategy_match_from_effective_scope,
)


class SalesOnePlusSemanticConflictError(ValueError):
    """Typed UI/envelope semantic conflict — stable reason code only."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class GovernedUiSemanticAuthority:
    service_id: str | None
    extent: str | None
    jaw: str | None
    stage: str | None


def governed_ui_authority_from_resolution(
    resolution: ExactSalesResolution,
) -> GovernedUiSemanticAuthority:
    return GovernedUiSemanticAuthority(
        service_id=_value_if_governed(resolution.service_id, resolution.service_id_authority),
        extent=_value_if_governed(resolution.extent, resolution.extent_authority),
        jaw=_value_if_governed(resolution.jaw, resolution.jaw_authority),
        stage=_value_if_governed(resolution.stage, resolution.stage_authority),
    )


def _value_if_governed(value: object, authority: ExactSalesFieldAuthority) -> str | None:
    if authority.authority != "governed_ui":
        return None
    if value is None:
        return None
    token = str(value).strip()
    return token or None


def _merge_field(
    *,
    field: str,
    ui_value: str | None,
    envelope_value: str | None,
) -> tuple[str | None, SemanticFieldProvenance]:
    if ui_value is not None:
        if envelope_value is not None and envelope_value != ui_value:
            raise SalesOnePlusSemanticConflictError(f"semantic_ui_envelope_conflict_{field}")
        return ui_value, "governed_ui"
    if envelope_value is not None:
        return envelope_value, "envelope"
    return None, "null"


def _resolve_availability_status(
    *,
    service_reference_status: str,
    requested_service_id: str | None,
    reference_catalog: ServiceReferenceCatalogSnapshot,
) -> AvailabilityStatus:
    if service_reference_status == "unresolved":
        return "unresolved"
    if service_reference_status == "none":
        return "none"
    if service_reference_status != "resolved" or requested_service_id is None:
        return "none"
    active = reference_catalog.is_active(requested_service_id)
    if active is True:
        return "offered"
    if active is False:
        return "known_not_offered"
    return "unresolved"



@dataclass(frozen=True, slots=True)
class _EnvelopeServiceProjection:
    service_id: str | None
    provenance: SemanticFieldProvenance
    block_session_fallback: bool


def _project_envelope_service_id(
    *,
    envelope: OneCallEnvelope,
    reference_catalog: ServiceReferenceCatalogSnapshot,
) -> _EnvelopeServiceProjection:
    envelope_service_id = envelope.service_id
    if envelope.service_reference_status == "resolved":
        requested = envelope.requested_service_id
        if requested is None:
            raise SalesOnePlusSemanticConflictError("requested_service_id_required_for_resolved")
        is_active = reference_catalog.is_active(requested)
        if is_active is False:
            if envelope_service_id is not None:
                raise SalesOnePlusSemanticConflictError("service_id_conflict_inactive_reference")
            return _EnvelopeServiceProjection(None, "null", True)
        if is_active is None:
            raise SalesOnePlusSemanticConflictError("requested_service_id_invalid")
        if envelope_service_id is not None and envelope_service_id != requested:
            raise SalesOnePlusSemanticConflictError("semantic_envelope_service_id_conflict")
        return _EnvelopeServiceProjection(requested, "envelope", False)

    if envelope.service_reference_status == "unresolved":
        return _EnvelopeServiceProjection(None, "null", True)

    if envelope_service_id is not None:
        if envelope_service_id not in reference_catalog.active_service_ids:
            raise SalesOnePlusSemanticConflictError("service_id_inactive")
        return _EnvelopeServiceProjection(envelope_service_id, "envelope", False)
    return _EnvelopeServiceProjection(None, "null", False)


def _project_active_service_id(
    *,
    envelope: OneCallEnvelope,
    governed_ui: GovernedUiSemanticAuthority,
    reference_catalog: ServiceReferenceCatalogSnapshot,
    explicit_catalog_service_id: str | None = None,
    session_service_id: str | None = None,
) -> tuple[str | None, SemanticFieldProvenance]:
    if governed_ui.service_id is not None:
        if governed_ui.service_id not in reference_catalog.active_service_ids:
            raise SalesOnePlusSemanticConflictError("service_id_inactive")
        if envelope.service_reference_status == "resolved":
            requested = envelope.requested_service_id
            if requested is not None and requested != governed_ui.service_id:
                raise SalesOnePlusSemanticConflictError("semantic_ui_envelope_conflict_service_id")
        return governed_ui.service_id, "governed_ui"

    envelope_projection = _project_envelope_service_id(
        envelope=envelope,
        reference_catalog=reference_catalog,
    )
    if envelope_projection.service_id is not None:
        return envelope_projection.service_id, envelope_projection.provenance

    if envelope_projection.block_session_fallback:
        return None, "null"

    if explicit_catalog_service_id is not None:
        if explicit_catalog_service_id not in reference_catalog.active_service_ids:
            raise SalesOnePlusSemanticConflictError("service_id_inactive")
        return explicit_catalog_service_id, "exact_turn"

    if session_service_id is not None:
        if session_service_id not in reference_catalog.active_service_ids:
            raise SalesOnePlusSemanticConflictError("service_id_inactive")
        return session_service_id, "valid_session"

    return None, "null"


def bind_semantic_frame(
    *,
    envelope: OneCallEnvelope,
    governed_ui: GovernedUiSemanticAuthority,
    active_service_catalog: ActiveServiceCatalogSnapshot,
    service_reference_catalog: ServiceReferenceCatalogSnapshot,
    explicit_catalog_service_id: str | None = None,
    session_service_id: str | None = None,
) -> SalesOnePlusSemanticFrame:
    """Pure local binder — no provider calls, no regex, no client reload."""

    service_id, service_id_provenance = _project_active_service_id(
        envelope=envelope,
        governed_ui=governed_ui,
        reference_catalog=service_reference_catalog,
        explicit_catalog_service_id=explicit_catalog_service_id,
        session_service_id=session_service_id,
    )
    extent, extent_provenance = _merge_field(
        field="extent",
        ui_value=governed_ui.extent,
        envelope_value=envelope.extent,
    )
    jaw, jaw_provenance = _merge_field(
        field="jaw",
        ui_value=governed_ui.jaw,
        envelope_value=envelope.jaw,
    )
    stage, stage_provenance = _merge_field(
        field="stage",
        ui_value=governed_ui.stage,
        envelope_value=envelope.stage,
    )

    if service_id is not None and service_id not in active_service_catalog.active_service_ids:
        raise SalesOnePlusSemanticConflictError("service_id_inactive")
    if stage is not None and stage not in active_service_catalog.allowed_patient_stages:
        raise SalesOnePlusSemanticConflictError("stage_not_allowed")
    if envelope.clarify_service_options is not None:
        for option_id in envelope.clarify_service_options:
            if option_id not in active_service_catalog.active_service_ids:
                raise SalesOnePlusSemanticConflictError("clarify_service_options_invalid")

    availability_status = _resolve_availability_status(
        service_reference_status=envelope.service_reference_status,
        requested_service_id=envelope.requested_service_id,
        reference_catalog=service_reference_catalog,
    )

    commercial_intent: OneCallCommercialIntent = (
        "none" if envelope.route == "CLARIFY" else envelope.commercial_intent
    )
    promotion_scope: OneCallPromotionScope = (
        "none" if envelope.route in {"CLARIFY", "ADMIN"} else envelope.promotion_scope
    )
    return SalesOnePlusSemanticFrame(
        route=envelope.route,
        service_id=service_id,
        service_id_provenance=service_id_provenance,
        extent=extent,  # type: ignore[arg-type]
        extent_provenance=extent_provenance,
        jaw=jaw,  # type: ignore[arg-type]
        jaw_provenance=jaw_provenance,
        stage=stage,
        stage_provenance=stage_provenance,
        scenario=envelope.scenario,
        commercial_intent=commercial_intent,
        promotion_scope=promotion_scope,
        clarify_axis=envelope.clarify_axis,
        clarify_service_options=envelope.clarify_service_options,
        service_reference_status=envelope.service_reference_status,
        requested_service_id=envelope.requested_service_id,
        availability_status=availability_status,
        direct_fact_ids=envelope.references.direct_fact_ids,
    )


def presentation_commercial_intent(
    semantic: SalesOnePlusSemanticFrame,
) -> OneCallCommercialIntent:
    """Route-aware presentation intent — CLARIFY/ADMIN close commercial surfaces."""

    if semantic.route in {"CLARIFY", "ADMIN"}:
        return "none"
    if semantic.availability_status in {"known_not_offered", "unresolved"}:
        return "none"
    return semantic.commercial_intent


def presentation_promotion_scope(
    semantic: SalesOnePlusSemanticFrame,
) -> OneCallPromotionScope:
    """Route-aware promotion scope — CLARIFY/ADMIN close promotion surface."""

    if semantic.route in {"CLARIFY", "ADMIN"}:
        return "none"
    if semantic.availability_status in {"known_not_offered", "unresolved"}:
        return "none"
    return semantic.promotion_scope


def presentation_active_service_id(semantic: SalesOnePlusSemanticFrame) -> str | None:
    """Active service focus for commerce/marketing — unavailable axes force null."""

    if semantic.availability_status in {"known_not_offered", "unresolved"}:
        return None
    return semantic.service_id


CLINIC_STRATEGY_SERVICE_SELECTED = "clinic_strategy_service_selected"
CLINIC_STRATEGY_SKIPPED_NO_EXPLICIT_PRIORITY = "clinic_strategy_skipped_no_explicit_priority"
CLINIC_STRATEGY_SKIPPED_AMBIGUOUS_PRIORITY = "clinic_strategy_skipped_ambiguous_priority"
CLINIC_STRATEGY_SKIPPED_TOPIC_DISAGREEMENT = "clinic_strategy_skipped_topic_disagreement"

_STRATEGY_MATCH_FIELDS = ("family", "extent", "stage", "jaw", "reported_context")


def _record_clinic_strategy_selection(code: str, *, service_id: str | None = None) -> None:
    try:
        from core import turn_timing

        turn_timing.set_flag(
            "clinic_strategy_service_selection",
            {"code": code, "service_id": service_id},
        )
    except Exception:
        pass


def _first_matching_strategy_rule(
    strategy: TargetClinicStrategy,
    context: TargetStrategyMatch,
) -> TargetStrategyRule | None:
    return next(
        (
            rule
            for rule in strategy.rules
            if all(
                expected is None or getattr(context, field) == expected
                for field in _STRATEGY_MATCH_FIELDS
                for expected in (getattr(rule.match, field),)
            )
        ),
        None,
    )


def _explicit_service_priorities_for_context(
    strategy: TargetClinicStrategy,
    context: TargetStrategyMatch,
) -> dict[str, int]:
    matched_rule = _first_matching_strategy_rule(strategy, context)
    priorities = dict(strategy.default_service_priorities)
    if matched_rule is not None and matched_rule.service_priorities is not None:
        priorities.update(matched_rule.service_priorities)
    return priorities


def _unique_explicit_priority_leader(
    candidates: Sequence[str],
    explicit_priorities: Mapping[str, int],
) -> str | None:
    """Return the sole leader only when explicit clinic priorities define one."""

    candidate_set = frozenset(candidates)
    scored = {
        service_id: explicit_priorities[service_id]
        for service_id in candidate_set
        if service_id in explicit_priorities
    }
    if not scored:
        return None
    max_priority = max(scored.values())
    leaders = [service_id for service_id, priority in scored.items() if priority == max_priority]
    if len(leaders) != 1:
        return None
    return leaders[0]


def resolve_priority_service_from_clinic_strategy(
    *,
    bundle: ResponseSchemaBundle,
    effective_scope: EffectiveScope,
    allowed_topics: Sequence[str],
    semantic: SalesOnePlusSemanticFrame,
) -> str | None:
    """Pick one priority service from clinic_strategy when price intent lacks explicit service."""

    if semantic.route != "ANSWER":
        return None
    if semantic.commercial_intent != "price":
        return None
    if semantic.service_id is not None:
        return None
    if semantic.availability_status in {"known_not_offered", "unresolved"}:
        return None
    if effective_scope.extent == "unknown":
        return None

    strategy_context = strategy_match_from_effective_scope(
        effective_scope,
        stage=semantic.stage,  # type: ignore[arg-type]
        jaw=semantic.jaw,  # type: ignore[arg-type]
    )
    patient = selection_patient_context_from_inputs(effective_scope)
    explicit_priorities = _explicit_service_priorities_for_context(
        bundle.strategy,
        strategy_context,
    )
    leaders_by_topic: list[str] = []
    had_applicable_without_leader = False
    for topic in allowed_topics:
        applicable = filter_applicable_services(
            bundle,
            topic=topic,
            strategy_context=strategy_context,
            patient=patient,
        )
        if not applicable:
            continue
        applicable_ids = tuple(item.service_id for item in applicable)
        leader = _unique_explicit_priority_leader(applicable_ids, explicit_priorities)
        if leader is not None:
            leaders_by_topic.append(leader)
            continue
        if any(service_id in explicit_priorities for service_id in applicable_ids):
            had_applicable_without_leader = True

    if not leaders_by_topic:
        if had_applicable_without_leader:
            _record_clinic_strategy_selection(CLINIC_STRATEGY_SKIPPED_AMBIGUOUS_PRIORITY)
        else:
            _record_clinic_strategy_selection(CLINIC_STRATEGY_SKIPPED_NO_EXPLICIT_PRIORITY)
        return None

    unique_leaders = set(leaders_by_topic)
    if len(unique_leaders) != 1:
        _record_clinic_strategy_selection(CLINIC_STRATEGY_SKIPPED_TOPIC_DISAGREEMENT)
        return None
    return next(iter(unique_leaders))


def apply_clinic_strategy_service_selection(
    semantic: SalesOnePlusSemanticFrame,
    *,
    bundle: ResponseSchemaBundle,
    effective_scope: EffectiveScope,
    allowed_topics: Sequence[str],
    governed_ui_service_id: str | None,
) -> SalesOnePlusSemanticFrame:
    """Apply clinic_strategy priority service after envelope bind when service is still unset."""

    if governed_ui_service_id is not None or semantic.service_id is not None:
        _record_clinic_strategy_selection("skipped_existing_service", service_id=semantic.service_id)
        return semantic

    selected = resolve_priority_service_from_clinic_strategy(
        bundle=bundle,
        effective_scope=effective_scope,
        allowed_topics=allowed_topics,
        semantic=semantic,
    )
    if selected is None:
        _record_clinic_strategy_selection("skipped_no_match")
        return semantic

    _record_clinic_strategy_selection(CLINIC_STRATEGY_SERVICE_SELECTED, service_id=selected)
    return semantic.model_copy(
        update={
            "service_id": selected,
            "service_id_provenance": "clinic_strategy",
        }
    )
