"""Identity-only target response materialization plan (S28, offline/unwired)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from contracts.target_response_spec import TargetResponseComponent
from core.target_offline_response_assembly import TargetOfflineResponseMaterials


_COMPONENTS = frozenset({"content", "price", "doctors"})


@dataclass(frozen=True, slots=True)
class TargetResponseMaterializationPlan:
    service_id: str
    selected_brand_id: str | None
    required_components: tuple[TargetResponseComponent, ...]
    unfulfilled_components: tuple[TargetResponseComponent, ...]
    primary_content_ref: str | None
    offer_ids: tuple[str, ...]
    doctor_ids: tuple[str, ...]
    commercial_fact_ids: tuple[str, ...]
    external_source_refs: tuple[str, ...]
    consultation_content_ref: str | None
    cta_key: str


class TargetResponseMaterializationPlanError(ValueError):
    """Typed error for invalid explicit S28 inputs."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _validated_components(
    values: Sequence[str],
) -> tuple[TargetResponseComponent, ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise TargetResponseMaterializationPlanError(
            "materialization_plan_components_invalid", values
        )
    copied = tuple(values)
    if not copied:
        raise TargetResponseMaterializationPlanError(
            "materialization_plan_components_empty", copied
        )
    for value in copied:
        if type(value) is not str or value not in _COMPONENTS:
            raise TargetResponseMaterializationPlanError(
                "materialization_plan_components_invalid", value
            )
    if len(copied) != len(set(copied)):
        raise TargetResponseMaterializationPlanError(
            "materialization_plan_component_duplicate", copied
        )
    return copied  # type: ignore[return-value]


def build_target_response_materialization_plan(
    materials: TargetOfflineResponseMaterials,
    *,
    required_components: Sequence[str],
) -> TargetResponseMaterializationPlan:
    """Project already-selected S27 identities without selecting or rendering again."""

    if type(materials) is not TargetOfflineResponseMaterials:
        raise TargetResponseMaterializationPlanError(
            "materialization_plan_materials_invalid", materials
        )
    components = _validated_components(required_components)

    primary_content_ref = (
        materials.selected_content_ref if "content" in components else None
    )
    offer_ids = (
        tuple(offer.offer_id for offer in materials.offers)
        if "price" in components
        else ()
    )
    doctor_ids = (
        tuple(doctor.doctor_id for doctor in materials.doctors)
        if "doctors" in components
        else ()
    )

    unfulfilled: list[TargetResponseComponent] = []
    for component in components:
        if component == "content" and primary_content_ref is None:
            unfulfilled.append(component)
        elif component == "price" and not offer_ids:
            unfulfilled.append(component)
        elif component == "doctors" and not doctor_ids:
            unfulfilled.append(component)

    consultation_content_ref = (
        materials.consultation_close.content_ref
        if materials.consultation_close is not None
        else None
    )
    return TargetResponseMaterializationPlan(
        service_id=materials.service_id,
        selected_brand_id=materials.selected_brand_id,
        required_components=components,
        unfulfilled_components=tuple(unfulfilled),
        primary_content_ref=primary_content_ref,
        offer_ids=offer_ids,
        doctor_ids=doctor_ids,
        commercial_fact_ids=tuple(fact.id for fact in materials.commercial_facts),
        external_source_refs=materials.external_source_refs,
        consultation_content_ref=consultation_content_ref,
        cta_key=materials.marketing_selection.cta_key,
    )
