"""Integrated S27-S30 target response package (offline/unwired)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle, TargetStrategyMatch
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from contracts.service_consultation import ServiceConsultationValue
from contracts.target_response_spec import TargetFollowupSource
from contracts.target_response_stage import ResponseStage
from core.target_offline_response_assembly import (
    TargetOfflineResponseMaterials,
    assemble_target_offline_response_materials,
)
from core.target_response_followup_materializer import (
    TargetResponseFollowups,
    materialize_target_response_followups,
)
from core.target_response_followup_policy import (
    TargetResponseFollowupSelection,
    select_target_response_followups,
)
from core.target_client_ui_nav import TargetNavigationFollowup
from core.target_response_materialization_plan import (
    TargetResponseMaterializationPlan,
    build_target_response_materialization_plan,
)


@dataclass(frozen=True, slots=True)
class TargetOfflineResponsePackage:
    materials: TargetOfflineResponseMaterials
    plan: TargetResponseMaterializationPlan
    followup_candidates: TargetResponseFollowups
    selected_followups: TargetResponseFollowupSelection
    navigation_followups: tuple[TargetNavigationFollowup, ...] = ()
    response_stage: ResponseStage | None = None


def assemble_target_offline_response_package(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: ResponseSchemaExternalIndex,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    service_term: str,
    brand_term: str | None,
    strategy_context: TargetStrategyMatch,
    semantic_context: str,
    today: date,
    include_initial_block: bool,
    include_consultation_close: bool,
    required_components: Sequence[str],
    followup_source: TargetFollowupSource | None,
    md_root: Path,
    marketing_scenarios: Sequence[str] = (),
    shown_fact_ids: Sequence[str] = (),
    shown_amplifier_refs: Sequence[str] = (),
    shown_consultation_value_refs: Sequence[str] = (),
) -> TargetOfflineResponsePackage:
    """Run the proven offline S27-S30 segment without adding decisions."""

    materials = assemble_target_offline_response_materials(
        bundle,
        doctor_catalog,
        external_index,
        consultation_values,
        service_term=service_term,
        brand_term=brand_term,
        strategy_context=strategy_context,
        semantic_context=semantic_context,
        today=today,
        include_initial_block=include_initial_block,
        include_consultation_close=include_consultation_close,
        marketing_scenarios=marketing_scenarios,
        shown_fact_ids=shown_fact_ids,
        shown_amplifier_refs=shown_amplifier_refs,
        shown_consultation_value_refs=shown_consultation_value_refs,
    )
    plan = build_target_response_materialization_plan(
        materials,
        required_components=required_components,
    )
    followup_candidates = materialize_target_response_followups(
        plan,
        materials,
        md_root=md_root,
    )
    selected_followups = select_target_response_followups(
        followup_candidates,
        source=followup_source,
    )
    return TargetOfflineResponsePackage(
        materials=materials,
        plan=plan,
        followup_candidates=followup_candidates,
        selected_followups=selected_followups,
        navigation_followups=(),
    )
