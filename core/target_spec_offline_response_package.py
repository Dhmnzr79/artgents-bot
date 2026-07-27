"""Spec-bound S31 composition integration (S34, offline/unwired).

The nested S31 materials and follow-up candidates are internal candidate evidence. Output
consumers may use only spec-projected plan identities, selected follow-ups, and this
boundary's selected CTA key.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import NoReturn

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.effective_scope import EffectiveScope
from contracts.response_schema import ResponseSchemaBundle, TargetStrategyMatch
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from contracts.service_consultation import ServiceConsultationValue
from contracts.target_response_spec import TargetResponseSpec
from core.target_fullcontext_content_package import (
    assemble_target_fullcontext_content_bound_package,
    assemble_target_fullcontext_doctors_bound_package,
    is_fullcontext_content_only_spec,
    is_fullcontext_doctors_only_spec,
)
from core.target_offline_response_package import (
    TargetOfflineResponsePackage,
    assemble_target_offline_response_package,
)
from core.target_scope_aware_price_package import (
    assemble_scope_aware_price_package,
    is_scope_aware_price_spec,
)
from core.target_response_followup_policy import TargetResponseFollowupSelection


@dataclass(frozen=True, slots=True)
class TargetSpecBoundOfflineResponsePackage:
    spec: TargetResponseSpec
    package: TargetOfflineResponsePackage
    selected_cta_key: str | None


class TargetSpecOfflineResponsePackageError(ValueError):
    """Typed S34 validation/permission failure."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _error(code: str, value: object) -> NoReturn:
    raise TargetSpecOfflineResponsePackageError(code, value)


def assemble_target_spec_offline_response_package(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: ResponseSchemaExternalIndex,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    spec: TargetResponseSpec,
    brand_term: str | None,
    strategy_context: TargetStrategyMatch,
    semantic_context: str,
    today: date,
    md_root: Path,
    include_initial_block: bool,
    include_consultation_close: bool,
    include_cta: bool,
    marketing_scenarios: Sequence[str] = (),
    shown_fact_ids: Sequence[str] = (),
    shown_amplifier_refs: Sequence[str] = (),
    shown_consultation_value_refs: Sequence[str] = (),
    turn_topic: str | None = None,
    effective_scope: EffectiveScope | None = None,
    client_id: str = "demo",
) -> TargetSpecBoundOfflineResponsePackage:
    """Bind proven S32/S33 composition decisions to one S31 package."""

    if type(spec) is not TargetResponseSpec:
        _error("spec_package_spec_invalid", spec)
    for field_name, value in (
        ("include_initial_block", include_initial_block),
        ("include_consultation_close", include_consultation_close),
        ("include_cta", include_cta),
    ):
        if type(value) is not bool:
            _error("spec_package_selection_invalid", (field_name, value))
    effective_include_cta = include_cta and spec.allow_cta
    scope = effective_scope or EffectiveScope()
    if is_fullcontext_content_only_spec(spec):
        if brand_term is not None or include_initial_block or marketing_scenarios != ():
            _error("spec_package_permission_forbidden", "marketing_facts")
        if include_consultation_close and not spec.allow_consultation_close:
            _error("spec_package_permission_forbidden", "consultation_close")
        return assemble_target_fullcontext_content_bound_package(
            spec,
            bundle,
            turn_topic=turn_topic,
            today=today,
            shown_fact_ids=shown_fact_ids,
            include_consultation_close=include_consultation_close,
            selected_cta_key=None,
        )
    if is_fullcontext_doctors_only_spec(spec):
        if brand_term is not None or include_initial_block or marketing_scenarios != ():
            _error("spec_package_permission_forbidden", "marketing_facts")
        if include_consultation_close and not spec.allow_consultation_close:
            _error("spec_package_permission_forbidden", "consultation_close")
        return assemble_target_fullcontext_doctors_bound_package(
            spec,
            bundle,
            turn_topic=turn_topic,
            today=today,
            shown_fact_ids=shown_fact_ids,
            include_consultation_close=include_consultation_close,
            selected_cta_key=None,
        )
    if is_scope_aware_price_spec(spec):
        if spec.response_stage not in {None, "broad_family_price"} and (
            brand_term is not None or include_initial_block or marketing_scenarios != ()
        ):
            _error("spec_package_permission_forbidden", "marketing_facts")
        if include_consultation_close:
            _error("spec_package_permission_forbidden", "consultation_close")
        if include_cta and spec.response_stage not in {None, "broad_family_price"}:
            _error("spec_package_permission_forbidden", "cta")
        if spec.scope_price_topic is None:
            _error("spec_package_not_materializable", "scope_price_topic")
        package = assemble_scope_aware_price_package(
            bundle,
            doctor_catalog,
            external_index,
            consultation_values,
            spec=spec,
            effective_scope=scope,
            strategy_context=strategy_context,
            client_id=client_id,
            md_root=md_root,
            semantic_context=semantic_context,
            today=today,
            include_initial_block=include_initial_block,
            include_cta=include_cta,
            marketing_scenarios=marketing_scenarios,
            shown_fact_ids=shown_fact_ids,
            shown_amplifier_refs=shown_amplifier_refs,
            shown_consultation_value_refs=shown_consultation_value_refs,
        )
        out_spec = spec
        collapsed_service_id = package.plan.service_id
        resolved_stage = package.response_stage or spec.response_stage
        if resolved_stage is not None and resolved_stage != spec.response_stage:
            followup_source = None
            if resolved_stage in {"scoped_family_price", "concrete_service_price"}:
                followup_source = "price"
            out_spec = spec.model_copy(
                update={
                    "response_stage": resolved_stage,
                    "followup_source": followup_source,
                }
            )
        if collapsed_service_id and spec.service_id is None:
            out_spec = out_spec.model_copy(
                update={
                    "service_id": collapsed_service_id,
                    "response_stage": "concrete_service_price",
                    "followup_source": "price",
                }
            )
        if out_spec.service_id is None and (
            out_spec.followup_source == "price" or package.selected_followups.price
        ):
            out_spec = out_spec.model_copy(update={"followup_source": None})
            package = replace(
                package,
                selected_followups=TargetResponseFollowupSelection(
                    source=None,
                    content=package.selected_followups.content,
                    price=(),
                ),
            )
        selected_cta_key = None
        effective_stage = out_spec.response_stage
        if effective_include_cta and effective_stage == "broad_family_price":
            cta_key = package.materials.marketing_selection.cta_key
            selected_cta_key = cta_key if cta_key else None
        return TargetSpecBoundOfflineResponsePackage(
            spec=out_spec,
            package=package,
            selected_cta_key=selected_cta_key,
        )
    if (
        spec.response_mode not in {"answer", "medical_handoff"}
        or spec.service_id is None
        or not spec.required_components
    ):
        _error(
            "spec_package_not_materializable",
            (spec.response_mode, spec.service_id, spec.required_components),
        )
    if not spec.allow_marketing_facts and (
        include_initial_block or marketing_scenarios != ()
    ):
        _error("spec_package_permission_forbidden", "marketing_facts")
    if include_consultation_close and not spec.allow_consultation_close:
        _error("spec_package_permission_forbidden", "consultation_close")

    package = assemble_target_offline_response_package(
        bundle,
        doctor_catalog,
        external_index,
        consultation_values,
        service_term=spec.service_id,
        brand_term=brand_term,
        strategy_context=strategy_context,
        semantic_context=semantic_context,
        today=today,
        include_initial_block=include_initial_block,
        include_consultation_close=include_consultation_close,
        required_components=spec.required_components,
        followup_source=spec.followup_source,
        md_root=md_root,
        marketing_scenarios=marketing_scenarios,
        shown_fact_ids=shown_fact_ids,
        shown_amplifier_refs=shown_amplifier_refs,
        shown_consultation_value_refs=shown_consultation_value_refs,
        effective_scope=scope,
    )
    out_spec = spec
    if package.response_stage is not None:
        out_spec = spec.model_copy(update={"response_stage": package.response_stage})
    selected_cta_key = package.plan.cta_key if effective_include_cta else None
    return TargetSpecBoundOfflineResponsePackage(
        spec=out_spec,
        package=package,
        selected_cta_key=selected_cta_key,
    )
