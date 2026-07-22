"""FullContext-only service-optional content bound package (S45, offline/unwired)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from contracts.target_response_spec import TargetResponseComponent, TargetResponseSpec
from core.target_marketing_selector import TargetMarketingSelection
from core.target_offline_response_assembly import TargetOfflineResponseMaterials
from core.target_offline_response_package import TargetOfflineResponsePackage
from core.target_response_followup_materializer import TargetResponseFollowups
from core.target_response_followup_policy import TargetResponseFollowupSelection
from core.target_response_materialization_plan import TargetResponseMaterializationPlan


class TargetFullContextContentPackageError(ValueError):
    """Typed fail-closed FullContext content-only package failure."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _fail(code: str, value: object) -> NoReturn:
    raise TargetFullContextContentPackageError(code, value)


def is_fullcontext_content_only_spec(spec: TargetResponseSpec) -> bool:
    """True when spec may materialize from cached FullContext without service_id."""

    if type(spec) is not TargetResponseSpec:
        return False
    return (
        spec.response_mode in {"answer", "medical_handoff"}
        and spec.service_id is None
        and spec.required_components == ("content",)
        and not spec.required_fact_ids
        and not spec.allow_marketing_facts
    )


def assemble_target_fullcontext_content_bound_package(
    spec: TargetResponseSpec,
    *,
    selected_cta_key: str | None = None,
) -> "TargetSpecBoundOfflineResponsePackage":
    """Build minimal bound package for FullContext content-only materialization."""

    from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage

    if not is_fullcontext_content_only_spec(spec):
        _fail(
            "fullcontext_content_spec_invalid",
            (spec.response_mode, spec.service_id, spec.required_components),
        )
    if selected_cta_key is not None:
        _fail("fullcontext_content_cta_forbidden", selected_cta_key)

    plan = TargetResponseMaterializationPlan(
        service_id=None,
        selected_brand_id=None,
        required_components=("content",),
        unfulfilled_components=(),
        primary_content_ref=None,
        offer_ids=(),
        doctor_ids=(),
        commercial_fact_ids=(),
        external_source_refs=(),
        consultation_content_ref=None,
        cta_key="",
    )
    materials = TargetOfflineResponseMaterials(
        service_id=None,
        service=None,
        selected_brand_id=None,
        brand=None,
        matched_rule_id=None,
        max_options=0,
        offers=(),
        doctors=(),
        selected_content_ref=None,
        marketing_selection=TargetMarketingSelection(
            applied_scenarios=(),
            selected_refs=(),
            amplifier_refs=(),
            cta_key="",
        ),
        commercial_facts=(),
        external_source_refs=(),
        consultation_close=None,
        marketing_slots_used=0,
        amplifier_slots_used=0,
    )
    package = TargetOfflineResponsePackage(
        materials=materials,
        plan=plan,
        followup_candidates=TargetResponseFollowups(content=(), price=()),
        selected_followups=TargetResponseFollowupSelection(
            source=None,
            content=(),
            price=(),
        ),
    )
    return TargetSpecBoundOfflineResponsePackage(
        spec=spec,
        package=package,
        selected_cta_key=selected_cta_key,
    )
