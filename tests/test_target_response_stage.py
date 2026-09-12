from __future__ import annotations

from contracts.effective_scope import EffectiveScope
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.target_response_stage import (
    derive_response_stage,
    discover_stage_clarification_stages,
)
from core.target_strategy_context import selection_patient_context_from_inputs


TARGET_ROOT = __import__("pathlib").Path("clients/demo/target_response")


def test_unknown_extent_yields_broad_family_price() -> None:
    stage = derive_response_stage(
        explicit_service_id=None,
        effective_scope=EffectiveScope(),
        topic="implantation",
        bundle=load_response_schema_bundle(TARGET_ROOT),
        selection=None,
    )
    assert stage == "broad_family_price"


def test_known_extent_without_services_may_need_stage_clarify() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    scope = EffectiveScope(extent="one_tooth", topic="prosthetics", source="session", provenance="test")
    patient = selection_patient_context_from_inputs(scope)
    stages = discover_stage_clarification_stages(
        bundle,
        topic="prosthetics",
        patient=patient,
    )
    assert stages
    stage = derive_response_stage(
        explicit_service_id=None,
        effective_scope=scope,
        topic="prosthetics",
        bundle=bundle,
        selection=None,
    )
    assert stage in {"stage_clarify", "scoped_family_price", "data_gap"}
