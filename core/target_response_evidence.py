"""Pure one-service target evidence assembly (S22, offline and unwired)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from pydantic import TypeAdapter, ValidationError

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle, TargetCommercialFact
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from contracts.service_consultation import (
    ConsultationContentRef,
    ServiceConsultationValue,
    validate_service_consultation_refs,
)
from core.service_data_context import ServiceDataContext, build_service_data_context
from core.target_marketing_selector import (
    TargetMarketingSelection,
    select_target_marketing,
)


_CONTENT_REF_ADAPTER = TypeAdapter(ConsultationContentRef)


@dataclass(frozen=True, slots=True)
class TargetResponseEvidencePackage:
    service_context: ServiceDataContext
    selected_content_ref: str | None
    marketing_selection: TargetMarketingSelection
    commercial_facts: tuple[TargetCommercialFact, ...]
    external_source_refs: tuple[str, ...]
    consultation_close: ServiceConsultationValue | None
    marketing_slots_used: int
    amplifier_slots_used: int


class TargetResponseEvidencePackageError(ValueError):
    """Typed error for invalid explicit S22-only inputs."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _validated_content_ref(value: object, *, code: str) -> str:
    try:
        return _CONTENT_REF_ADAPTER.validate_python(value)
    except ValidationError as exc:
        raise TargetResponseEvidencePackageError(code, value) from exc


def _validated_consultation_values(
    values: Sequence[ServiceConsultationValue],
) -> tuple[ServiceConsultationValue, ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise TargetResponseEvidencePackageError(
            "evidence_consultation_values_invalid", values
        )
    copied = tuple(values)
    for value in copied:
        if not isinstance(value, ServiceConsultationValue):
            raise TargetResponseEvidencePackageError(
                "evidence_consultation_values_invalid", value
            )
    refs = tuple(value.content_ref for value in copied)
    if len(refs) != len(set(refs)):
        raise TargetResponseEvidencePackageError(
            "evidence_consultation_content_ref_duplicate", refs
        )
    return copied


def _validated_shown_consultation_refs(
    values: Sequence[str],
) -> tuple[str, ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise TargetResponseEvidencePackageError(
            "evidence_shown_consultation_ref_invalid", values
        )
    copied = tuple(values)
    validated = tuple(
        _validated_content_ref(
            value,
            code="evidence_shown_consultation_ref_invalid",
        )
        for value in copied
    )
    if len(validated) != len(set(validated)):
        raise TargetResponseEvidencePackageError(
            "evidence_shown_consultation_ref_duplicate", validated
        )
    return validated


def build_target_response_evidence_package(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: ResponseSchemaExternalIndex,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    service_id: str,
    selected_content_ref: str | None,
    semantic_context: str,
    today: date,
    include_initial_block: bool,
    include_consultation_close: bool,
    marketing_scenarios: Sequence[str] = (),
    shown_fact_ids: Sequence[str] = (),
    shown_amplifier_refs: Sequence[str] = (),
    shown_consultation_value_refs: Sequence[str] = (),
    turn_topic: str | None = None,
) -> TargetResponseEvidencePackage:
    """Assemble detached target materials without selecting or rendering an answer."""

    service_context = build_service_data_context(bundle, doctor_catalog, service_id)
    marketing_selection = select_target_marketing(
        bundle,
        doctor_catalog,
        external_index,
        semantic_context=semantic_context,
        service_id=service_id,
        today=today,
        include_initial_block=include_initial_block,
        marketing_scenarios=marketing_scenarios,
        shown_fact_ids=shown_fact_ids,
        shown_amplifier_refs=shown_amplifier_refs,
        turn_topic=turn_topic,
    )

    consultation_records = _validated_consultation_values(consultation_values)
    validate_service_consultation_refs(consultation_records, bundle.services)

    validated_selected_ref: str | None = None
    if selected_content_ref is not None:
        validated_selected_ref = _validated_content_ref(
            selected_content_ref,
            code="evidence_selected_content_ref_invalid",
        )
        owned_content_refs = {
            content_ref
            for content_ref in (
                service_context.service.content_ref,
                *(option.content_ref for option in service_context.service.options),
            )
            if content_ref is not None
        }
        if validated_selected_ref not in owned_content_refs:
            raise TargetResponseEvidencePackageError(
                "evidence_selected_content_ref_not_owned", validated_selected_ref
            )

    if type(include_consultation_close) is not bool:
        raise TargetResponseEvidencePackageError(
            "evidence_include_consultation_close_invalid", include_consultation_close
        )
    shown_consultation_refs = _validated_shown_consultation_refs(
        shown_consultation_value_refs
    )

    commercial_facts: list[TargetCommercialFact] = []
    external_source_refs: list[str] = []
    for ref in marketing_selection.selected_refs:
        if ref.startswith("fact:"):
            commercial_facts.append(
                bundle.facts[ref.removeprefix("fact:")].model_copy(deep=True)
            )
        else:
            external_source_refs.append(ref)

    marketing_slots_used = len(marketing_selection.selected_refs)
    amplifier_slots_used = len(marketing_selection.amplifier_refs)
    consultation_close: ServiceConsultationValue | None = None
    consultation_by_ref = {
        record.content_ref: record for record in consultation_records
    }
    if (
        include_consultation_close
        and validated_selected_ref is not None
        and validated_selected_ref in consultation_by_ref
        and validated_selected_ref not in shown_consultation_refs
        and marketing_slots_used
        < bundle.marketing.limits.max_marketing_facts_per_turn
        and amplifier_slots_used < bundle.marketing.limits.max_amplifiers_per_turn
    ):
        consultation_close = consultation_by_ref[validated_selected_ref].model_copy(
            deep=True
        )
        marketing_slots_used += 1
        amplifier_slots_used += 1

    return TargetResponseEvidencePackage(
        service_context=service_context,
        selected_content_ref=validated_selected_ref,
        marketing_selection=marketing_selection,
        commercial_facts=tuple(commercial_facts),
        external_source_refs=tuple(external_source_refs),
        consultation_close=consultation_close,
        marketing_slots_used=marketing_slots_used,
        amplifier_slots_used=amplifier_slots_used,
    )


def merge_marketing_selection_into_materials(
    materials: object,
    bundle: ResponseSchemaBundle,
    selection: TargetMarketingSelection,
) -> object:
    """Attach scenario marketing selection to minimal FullContext materials."""

    from dataclasses import replace

    from core.target_offline_response_assembly import TargetOfflineResponseMaterials

    if type(materials) is not TargetOfflineResponseMaterials:
        raise TypeError("materials_must_be_target_offline_response_materials")

    commercial_facts = list(materials.commercial_facts)
    external_source_refs = list(materials.external_source_refs)
    for ref in selection.selected_refs:
        if ref.startswith("fact:"):
            commercial_facts.append(
                bundle.facts[ref.removeprefix("fact:")].model_copy(deep=True)
            )
        else:
            external_source_refs.append(ref)
    for ref in selection.amplifier_refs:
        if not ref.startswith("fact:"):
            external_source_refs.append(ref)
            continue
        fact_id = ref.removeprefix("fact:")
        if fact_id in {fact.id for fact in commercial_facts}:
            continue
        commercial_facts.append(bundle.facts[fact_id].model_copy(deep=True))
    if selection.service_value_ref and selection.service_value_ref.startswith("fact:"):
        sv_id = selection.service_value_ref.removeprefix("fact:")
        if sv_id not in {fact.id for fact in commercial_facts}:
            commercial_facts.append(bundle.facts[sv_id].model_copy(deep=True))
    return replace(
        materials,
        marketing_selection=selection,
        commercial_facts=tuple(commercial_facts),
        external_source_refs=tuple(external_source_refs),
        marketing_slots_used=len(selection.selected_refs),
        amplifier_slots_used=len(selection.amplifier_refs),
    )
