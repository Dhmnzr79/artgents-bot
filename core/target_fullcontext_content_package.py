"""FullContext-only service-optional content bound package (S45, offline/unwired)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import NoReturn

from contracts.response_schema import ResponseSchemaBundle
from contracts.target_response_spec import TargetResponseComponent, TargetResponseSpec
from core.target_marketing_selector import TargetMarketingSelection
from core.target_offline_response_assembly import TargetOfflineResponseMaterials
from core.target_offline_response_package import TargetOfflineResponsePackage
from core.target_response_followup_materializer import TargetResponseFollowups
from core.target_response_followup_policy import TargetResponseFollowupSelection
from core.target_response_materialization_plan import TargetResponseMaterializationPlan
from core.target_topic_scoped_commercial_fact import select_topic_scoped_consultation_fact


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


def is_fullcontext_doctors_only_spec(spec: TargetResponseSpec) -> bool:
    """True when clinic-wide doctors may materialize from cached FullContext."""

    if type(spec) is not TargetResponseSpec:
        return False
    return (
        spec.response_mode in {"answer", "medical_handoff"}
        and spec.service_id is None
        and spec.required_components == ("doctors",)
        and not spec.required_fact_ids
        and not spec.allow_marketing_facts
    )


def is_fullcontext_service_optional_spec(spec: TargetResponseSpec) -> bool:
    """True when spec may materialize from cached FullContext without service_id."""

    return is_fullcontext_content_only_spec(spec) or is_fullcontext_doctors_only_spec(spec)


def assemble_target_fullcontext_content_bound_package(
    spec: TargetResponseSpec,
    bundle: ResponseSchemaBundle | None = None,
    *,
    turn_topic: str | None = None,
    today: date | None = None,
    shown_fact_ids: Sequence[str] = (),
    include_consultation_close: bool = False,
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

    commercial_facts: tuple = ()
    commercial_fact_ids: tuple[str, ...] = ()
    if (
        include_consultation_close
        and spec.allow_consultation_close
        and bundle is not None
        and today is not None
    ):
        selected_fact = select_topic_scoped_consultation_fact(
            bundle,
            turn_topic=turn_topic,
            today=today,
            shown_fact_ids=frozenset(shown_fact_ids),
        )
        if selected_fact is not None:
            commercial_facts = (selected_fact,)
            commercial_fact_ids = (selected_fact.id,)

    plan = TargetResponseMaterializationPlan(
        service_id=None,
        selected_brand_id=None,
        required_components=("content",),
        unfulfilled_components=(),
        primary_content_ref=None,
        offer_ids=(),
        doctor_ids=(),
        commercial_fact_ids=commercial_fact_ids,
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
        commercial_facts=commercial_facts,
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


def assemble_target_fullcontext_doctors_bound_package(
    spec: TargetResponseSpec,
    bundle: ResponseSchemaBundle | None = None,
    *,
    turn_topic: str | None = None,
    today: date | None = None,
    shown_fact_ids: Sequence[str] = (),
    include_consultation_close: bool = False,
    selected_cta_key: str | None = None,
) -> "TargetSpecBoundOfflineResponsePackage":
    """Build minimal bound package for clinic-wide FullContext doctors materialization."""

    from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage

    if not is_fullcontext_doctors_only_spec(spec):
        _fail(
            "fullcontext_doctors_spec_invalid",
            (spec.response_mode, spec.service_id, spec.required_components),
        )
    if selected_cta_key is not None:
        _fail("fullcontext_doctors_cta_forbidden", selected_cta_key)

    commercial_facts: tuple = ()
    commercial_fact_ids: tuple[str, ...] = ()
    if (
        include_consultation_close
        and spec.allow_consultation_close
        and bundle is not None
        and today is not None
    ):
        selected_fact = select_topic_scoped_consultation_fact(
            bundle,
            turn_topic=turn_topic,
            today=today,
            shown_fact_ids=frozenset(shown_fact_ids),
        )
        if selected_fact is not None:
            commercial_facts = (selected_fact,)
            commercial_fact_ids = (selected_fact.id,)

    plan = TargetResponseMaterializationPlan(
        service_id=None,
        selected_brand_id=None,
        required_components=("doctors",),
        unfulfilled_components=(),
        primary_content_ref=None,
        offer_ids=(),
        doctor_ids=(),
        commercial_fact_ids=commercial_fact_ids,
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
        commercial_facts=commercial_facts,
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
