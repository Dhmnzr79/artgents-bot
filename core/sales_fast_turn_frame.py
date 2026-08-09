"""Deterministic TurnFrame projection for the sales-fast path (no Planner)."""

from __future__ import annotations

import re

from contracts.answer_plan import AspectKind
from contracts.exact_sales_resolution import ExactSalesResolution
from contracts.patient_scope_projection import ProjectedPatientScope, ProjectedScopeAxis
from contracts.response_schema import ResponseSchemaBundle
from contracts.turn_frame import FieldMeta, PatientScopeFrame, PatientScopeFrameMeta, TurnFrame, TurnFrameMeta
from core.answer_planner import detect_aspects_regex
from core.target_client_data import match_service_from_target_catalog

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

_SALES_FAST_PROVENANCE = "sales_fast.exact_turn"
_ASPECT_TO_SCENARIO: dict[AspectKind, str] = {
    "pain": "pain_fear",
    "payment": "cost",
    "price": "cost",
    "duration": "time",
    "overview": "result_reliability",
    "warranty": "result_reliability",
}


def _valid_meta() -> FieldMeta:
    return FieldMeta(confidence=1.0, provenance=_SALES_FAST_PROVENANCE, status="valid")


def _defaulted_meta() -> FieldMeta:
    return FieldMeta(confidence=0.0, provenance=_SALES_FAST_PROVENANCE, status="defaulted")


def _default_patient_scope_meta() -> PatientScopeFrameMeta:
    defaulted = _defaulted_meta()
    return PatientScopeFrameMeta(
        container=defaulted,
        extent=defaulted,
        jaw=defaulted,
        stage=defaulted,
        modifiers=defaulted,
    )


def _topic_for_resolution(
    *,
    resolution: ExactSalesResolution,
    bundle: ResponseSchemaBundle,
    client_id: str,
    user_message: str,
) -> str:
    if _CLINIC_INFO_RE.search(user_message):
        return "clinic"
    match = match_service_from_target_catalog(user_message, client_id=client_id)
    catalog_topic = str(match.get("catalog_topic") or match.get("matched_topic") or "").strip().lower()
    if catalog_topic:
        return catalog_topic
    if resolution.service_id:
        service = bundle.services.get(resolution.service_id)
        if service is not None and service.family:
            family = str(service.family).strip().lower()
            if family == "implantology":
                return "implantation"
            return family
    return "implantation"


def build_sales_fast_turn_frame(
    *,
    resolution: ExactSalesResolution,
    user_message: str,
    client_id: str,
    bundle: ResponseSchemaBundle,
) -> TurnFrame:
    aspects = tuple(detect_aspects_regex(user_message))
    if resolution.aspect is not None and resolution.aspect not in aspects:
        aspects = (resolution.aspect, *aspects)
    primary_aspect = resolution.aspect or (aspects[0] if aspects else "overview")
    topic = _topic_for_resolution(
        resolution=resolution,
        bundle=bundle,
        client_id=client_id,
        user_message=user_message,
    )
    intent = "price_lookup" if primary_aspect in {"price", "payment", "included"} else "content"
    scenario = _ASPECT_TO_SCENARIO.get(primary_aspect)
    marketing_scenarios = (scenario,) if scenario else ()
    valid = _valid_meta()
    return TurnFrame(
        intent=intent,
        topic=topic,
        aspects=aspects,
        primary_aspect=primary_aspect,
        emotion="none",
        specificity="unknown",
        patient_scope=PatientScopeFrame(),
        service_id=resolution.service_id,
        follow_up=False,
        followup_of=None,
        needs_clarification=False,
        marketing_scenarios=marketing_scenarios,  # type: ignore[arg-type]
        field_meta=TurnFrameMeta(
            intent=valid,
            topic=valid,
            aspects=valid,
            primary_aspect=valid,
            emotion=valid,
            specificity=valid,
            patient_scope=_default_patient_scope_meta(),
            service_id=valid if resolution.service_id else _defaulted_meta(),
            follow_up=valid,
            followup_of=_defaulted_meta(),
            needs_clarification=valid,
            marketing_scenarios=valid if marketing_scenarios else _defaulted_meta(),
        ),
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
