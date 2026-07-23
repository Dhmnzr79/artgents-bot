"""Extract authoritative session selection from spec-bound packages (S61 correction)."""

from __future__ import annotations

from dataclasses import dataclass

from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage


@dataclass(frozen=True, slots=True)
class TargetMaterializedSessionSelection:
    shown_fact_ids: tuple[str, ...]
    shown_amplifier_refs: tuple[str, ...]
    shown_consultation_value_refs: tuple[str, ...]


def extract_target_session_selection(
    bound: TargetSpecBoundOfflineResponsePackage,
) -> TargetMaterializedSessionSelection:
    """Return IDs/refs selected in the current materialization package."""

    package = bound.package
    consultation_ref = package.plan.consultation_content_ref
    consultation_refs = (consultation_ref,) if consultation_ref else ()
    return TargetMaterializedSessionSelection(
        shown_fact_ids=package.plan.commercial_fact_ids,
        shown_amplifier_refs=package.materials.marketing_selection.amplifier_refs,
        shown_consultation_value_refs=consultation_refs,
    )
