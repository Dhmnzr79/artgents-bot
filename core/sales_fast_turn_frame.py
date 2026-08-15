"""Deterministic TurnFrame projection for the sales-fast path (no Planner)."""

from __future__ import annotations

import re

from contracts.answer_plan import AspectKind
from contracts.exact_sales_resolution import ExactSalesResolution
from contracts.patient_scope_projection import ProjectedPatientScope, ProjectedScopeAxis
from contracts.response_schema import ResponseSchemaBundle
from contracts.sales_one_plus_semantic import SalesOnePlusSemanticFrame
from contracts.turn_frame import FieldMeta, PatientScopeFrame, PatientScopeFrameMeta, TurnFrame, TurnFrameMeta
from core.answer_planner import detect_aspects_regex

_CLINIC_INFO_RE = re.compile(
    r"парков|адрес|как добраться|где наход|режим работ|график|контакт|телефон",
    re.I | re.U,
)
_ONE_TOOTH_RE = re.compile(
    r"(?:\bодин\b|\bодного\b|\bодну\b).{0,24}зуб|\bза\s+зуб\b",
    re.I | re.U,
)
_FEW_TEETH_RE = re.compile(r"несколько\s+зуб", re.I | re.U)
_FULL_ARCH_RE = re.compile(
    r"all[\s-]?on[\s-]?[46]|полн\w*\s+ряд|все\s+зуб|всю\s+челюст",
    re.I | re.U,
)
_JAW_BOTH_RE = re.compile(r"обе\s+челюст", re.I | re.U)
_JAW_LOWER_RE = re.compile(r"нижн\w*", re.I | re.U)
_JAW_UPPER_RE = re.compile(r"верхн\w*", re.I | re.U)
_SCOPE_PROVENANCE = "sales_fast.message_scope"

_SERVICE_FAMILY_TO_TOPIC: dict[str, str] = {
    "implantology": "implantation",
    "prosthodontics": "prosthetics",
}

_SALES_FAST_PROVENANCE = "sales_fast.exact_turn"
_SEMANTIC_PROVENANCE = "sales_fast.semantic_authority"
_ASPECT_TO_SCENARIO: dict[AspectKind, str] = {
    "pain": "pain_fear",
    "payment": "cost",
    "price": "cost",
    "duration": "time",
    "overview": "result_reliability",
    "warranty": "result_reliability",
}
_SCENARIO_TO_ASPECT: dict[str, AspectKind] = {
    "pain_fear": "pain",
    "cost": "price",
    "time": "duration",
    "result_reliability": "overview",
    "none": "overview",
}


def _valid_meta(*, provenance: str = _SALES_FAST_PROVENANCE) -> FieldMeta:
    return FieldMeta(confidence=1.0, provenance=provenance, status="valid")


def _defaulted_meta(*, provenance: str = _SALES_FAST_PROVENANCE) -> FieldMeta:
    return FieldMeta(confidence=0.0, provenance=provenance, status="defaulted")


def _default_patient_scope_meta() -> PatientScopeFrameMeta:
    defaulted = _defaulted_meta()
    return PatientScopeFrameMeta(
        container=defaulted,
        extent=defaulted,
        jaw=defaulted,
        stage=defaulted,
        modifiers=defaulted,
    )


def _topic_for_confirmed_service(
    *,
    service_id: str | None,
    bundle: ResponseSchemaBundle,
    user_message: str,
) -> str | None:
    if _CLINIC_INFO_RE.search(user_message):
        return "clinic"
    if not service_id:
        return None
    service = bundle.services.get(service_id)
    if service is None or not service.family:
        return None
    family = str(service.family).strip().lower()
    mapped = _SERVICE_FAMILY_TO_TOPIC.get(family)
    if mapped is not None:
        return mapped
    return family


def build_provisional_turn_frame(
    *,
    resolution: ExactSalesResolution,
    user_message: str,
    client_id: str,
    bundle: ResponseSchemaBundle,
) -> TurnFrame:
    """Pre-Flash neutral frame — no implantation default, no catalog authority."""

    _ = client_id
    aspects = tuple(detect_aspects_regex(user_message))
    if resolution.aspect is not None and resolution.aspect not in aspects:
        aspects = (resolution.aspect, *aspects)
    primary_aspect = resolution.aspect or (aspects[0] if aspects else "overview")
    governed_service_id = (
        resolution.service_id if resolution.service_id_authority.authority == "governed_ui" else None
    )
    topic = _topic_for_confirmed_service(
        service_id=governed_service_id,
        bundle=bundle,
        user_message=user_message,
    )
    intent = "price_lookup" if primary_aspect in {"price", "payment", "included"} else "content"
    scenario = _ASPECT_TO_SCENARIO.get(primary_aspect)
    marketing_scenarios = (scenario,) if scenario else ()
    valid = _valid_meta()
    return TurnFrame(
        intent=intent,
        topic=topic,
        aspects=list(aspects),
        primary_aspect=primary_aspect,
        emotion="none",
        specificity="unknown",
        patient_scope=PatientScopeFrame(),
        service_id=governed_service_id,
        follow_up=False,
        followup_of=None,
        needs_clarification=False,
        marketing_scenarios=marketing_scenarios,  # type: ignore[arg-type]
        field_meta=TurnFrameMeta(
            intent=valid,
            topic=valid if topic else _defaulted_meta(),
            aspects=valid,
            primary_aspect=valid,
            emotion=valid,
            specificity=valid,
            patient_scope=_default_patient_scope_meta(),
            service_id=valid if governed_service_id else _defaulted_meta(),
            follow_up=valid,
            followup_of=_defaulted_meta(),
            needs_clarification=valid,
            marketing_scenarios=valid if marketing_scenarios else _defaulted_meta(),
        ),
    )


def build_turn_frame_from_semantic_frame(
    *,
    semantic: SalesOnePlusSemanticFrame,
    user_message: str,
    bundle: ResponseSchemaBundle,
) -> TurnFrame:
    """Post-envelope authoritative TurnFrame for full bound-package rebuild."""

    aspects = list(detect_aspects_regex(user_message))
    scenario_aspect = _SCENARIO_TO_ASPECT.get(semantic.scenario, "overview")
    if scenario_aspect not in aspects:
        aspects = [scenario_aspect, *aspects]
    primary_aspect = scenario_aspect if semantic.scenario != "none" else (aspects[0] if aspects else "overview")
    if semantic.commercial_intent == "price":
        primary_aspect = "price"
    elif semantic.commercial_intent == "payment":
        primary_aspect = "payment"
    elif semantic.commercial_intent == "included":
        primary_aspect = "included"
    if primary_aspect not in aspects:
        aspects = [primary_aspect, *aspects]
    topic = _topic_for_confirmed_service(
        service_id=semantic.service_id,
        bundle=bundle,
        user_message=user_message,
    )
    intent = "price_lookup" if semantic.commercial_intent in {"price", "payment", "included"} else "content"
    if semantic.route == "CLARIFY":
        intent = "content"
    marketing_scenarios = (semantic.scenario,) if semantic.scenario != "none" else ()
    valid = _valid_meta(provenance=_SEMANTIC_PROVENANCE)
    patient_scope = PatientScopeFrame(
        extent=semantic.extent or "unknown",  # type: ignore[arg-type]
        jaw=semantic.jaw or "unknown",  # type: ignore[arg-type]
        stage=semantic.stage or "unknown",  # type: ignore[arg-type]
    )
    return TurnFrame(
        intent=intent,
        topic=topic,
        aspects=list(aspects),
        primary_aspect=primary_aspect,
        emotion="none",
        specificity="unknown",
        patient_scope=patient_scope,
        service_id=semantic.service_id,
        follow_up=False,
        followup_of=None,
        needs_clarification=semantic.route == "CLARIFY",
        marketing_scenarios=marketing_scenarios,  # type: ignore[arg-type]
        field_meta=TurnFrameMeta(
            intent=valid,
            topic=valid if topic else _defaulted_meta(provenance=_SEMANTIC_PROVENANCE),
            aspects=valid,
            primary_aspect=valid,
            emotion=valid,
            specificity=valid,
            patient_scope=_default_patient_scope_meta(),
            service_id=valid if semantic.service_id else _defaulted_meta(provenance=_SEMANTIC_PROVENANCE),
            follow_up=valid,
            followup_of=_defaulted_meta(provenance=_SEMANTIC_PROVENANCE),
            needs_clarification=valid if semantic.route == "CLARIFY" else _defaulted_meta(provenance=_SEMANTIC_PROVENANCE),
            marketing_scenarios=valid if marketing_scenarios else _defaulted_meta(provenance=_SEMANTIC_PROVENANCE),
        ),
    )


def build_sales_fast_turn_frame(
    *,
    resolution: ExactSalesResolution,
    user_message: str,
    client_id: str,
    bundle: ResponseSchemaBundle,
) -> TurnFrame:
    """Backward-compatible alias for provisional pre-Flash frame."""

    return build_provisional_turn_frame(
        resolution=resolution,
        user_message=user_message,
        client_id=client_id,
        bundle=bundle,
    )


def _scope_axis(value: str | None) -> ProjectedScopeAxis:
    if value is None:
        return ProjectedScopeAxis(
            value=None,
            provenance=_SCOPE_PROVENANCE,
            usable=False,
        )
    return ProjectedScopeAxis(
        value=value,
        provenance=_SCOPE_PROVENANCE,
        usable=True,
    )


def project_sales_fast_scope_from_message(user_message: str) -> ProjectedPatientScope:
    text = (user_message or "").strip()
    if not text:
        return ProjectedPatientScope(
            extent=_scope_axis(None),
            jaw=_scope_axis(None),
            stage=_scope_axis(None),
            reported_context=_scope_axis(None),
        )

    extent: str | None = None
    if _ONE_TOOTH_RE.search(text):
        extent = "one_tooth"
    elif _FEW_TEETH_RE.search(text):
        extent = "few_teeth"
    elif _FULL_ARCH_RE.search(text):
        extent = "full_arch"

    jaw: str | None = None
    if _JAW_BOTH_RE.search(text):
        jaw = "both"
    elif _JAW_LOWER_RE.search(text):
        jaw = "lower"
    elif _JAW_UPPER_RE.search(text):
        jaw = "upper"

    return ProjectedPatientScope(
        extent=_scope_axis(extent),
        jaw=_scope_axis(jaw),
        stage=_scope_axis(None),
        reported_context=_scope_axis(None),
    )
