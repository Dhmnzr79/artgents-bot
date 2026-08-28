"""Extract authoritative session selection from spec-bound packages (S61 correction)."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage


@dataclass(frozen=True, slots=True)
class TargetMaterializedSessionSelection:
    shown_fact_ids: tuple[str, ...]
    shown_amplifier_refs: tuple[str, ...]
    shown_consultation_value_refs: tuple[str, ...]
    shown_service_value_ids: tuple[str, ...] = ()
    last_rendered_promo_fact_id: str | None = None
    rendered_promo_fact_ids: tuple[str, ...] = ()
    last_turn_rendered_promo_fact_ids: tuple[str, ...] = ()


def extract_target_session_selection(
    bound: TargetSpecBoundOfflineResponsePackage,
    *,
    rendered_text: str | None = None,
    used_content_refs: Sequence[str] | None = None,
) -> TargetMaterializedSessionSelection:
    """Return only selections proven rendered when proof is available.

    Offline callers that do not yet have a rendered answer retain the former
    selected-material behaviour.  Runtime callers pass both values from the
    verified response and use strict literal/source-reference checks instead
    of semantic inference.
    """

    package = bound.package
    if rendered_text is None or used_content_refs is None:
        shown_fact_ids = package.plan.commercial_fact_ids
        shown_amplifier_refs = package.materials.marketing_selection.amplifier_refs
        consultation_ref = package.plan.consultation_content_ref
        consultation_refs = (consultation_ref,) if consultation_ref else ()
        return TargetMaterializedSessionSelection(
            shown_fact_ids=shown_fact_ids,
            shown_amplifier_refs=shown_amplifier_refs,
            shown_consultation_value_refs=consultation_refs,
            shown_service_value_ids=(),
            last_rendered_promo_fact_id=None,
            rendered_promo_fact_ids=(),
        )

    facts_by_id = {fact.id: fact for fact in package.materials.commercial_facts}
    doctors_by_id = {doctor.doctor_id: doctor for doctor in package.materials.doctors}
    shown_fact_ids = tuple(
        fact_id
        for fact_id in package.plan.commercial_fact_ids
        if (fact := facts_by_id.get(fact_id)) is not None
        and fact.text_fact in rendered_text
    )
    used_refs = frozenset(str(ref).strip() for ref in used_content_refs if str(ref).strip())

    def external_ref_was_used(ref: str) -> bool:
        if ref.startswith("fact:"):
            return ref.removeprefix("fact:") in shown_fact_ids
        if ref.startswith("kb:"):
            return ref.removeprefix("kb:").split("#", 1)[0] in used_refs
        if ref.startswith("doctor:"):
            doctor = doctors_by_id.get(ref.removeprefix("doctor:"))
            if doctor is None:
                return False
            return (
                doctor.profile_ref.removeprefix("kb:").split("#", 1)[0] in used_refs
                or doctor.name.casefold() in rendered_text.casefold()
            )
        return False

    consultation_ref = package.plan.consultation_content_ref
    consultation_refs = (
        (consultation_ref,)
        if consultation_ref is not None and consultation_ref in used_refs
        else ()
    )
    return TargetMaterializedSessionSelection(
        shown_fact_ids=shown_fact_ids,
        shown_amplifier_refs=tuple(
            ref
            for ref in package.materials.marketing_selection.amplifier_refs
            if external_ref_was_used(ref)
        ),
        shown_consultation_value_refs=consultation_refs,
        shown_service_value_ids=(),
        last_rendered_promo_fact_id=None,
        rendered_promo_fact_ids=(),
    )
