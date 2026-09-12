from __future__ import annotations

from pathlib import Path

from contracts.target_service_applicability import SelectionPatientContext
from core.response_schema_loader import load_response_schema_bundle
from core.target_service_applicability import filter_applicable_services

TARGET_ROOT = Path("clients/demo/target_response")


def _bundle():
    return load_response_schema_bundle(TARGET_ROOT)


def _ids(patient: SelectionPatientContext, *, topic: str = "implantation") -> set[str]:
    return {
        item.service_id
        for item in filter_applicable_services(
            _bundle(),
            topic=topic,
            patient=patient,
        )
    }


def test_unknown_extent_excludes_scope_services() -> None:
    patient = SelectionPatientContext(extent="unknown")
    ids = _ids(patient)
    assert "classic" not in ids
    assert "all_on_4" not in ids


def test_one_tooth_includes_classic_excludes_one_stage_without_stage() -> None:
    patient = SelectionPatientContext(extent="one_tooth")
    ids = _ids(patient)
    assert "classic" in ids
    assert "one_stage" not in ids


def test_one_tooth_with_extraction_stage_includes_one_stage() -> None:
    patient = SelectionPatientContext(extent="one_tooth", stage="extraction_context")
    ids = _ids(patient)
    assert "one_stage" in ids


def test_full_arch_includes_all_on_protocols() -> None:
    patient = SelectionPatientContext(extent="full_arch")
    ids = _ids(patient)
    assert "all_on_4" in ids
    assert "all_on_6" in ids


def test_direct_mode_requires_explicit_service() -> None:
    patient = SelectionPatientContext(extent="one_tooth")
    bundle = _bundle()
    direct_only = filter_applicable_services(
        bundle,
        topic="implantation",
        patient=patient,
        explicit_service_id="tomography",
    )
    assert [item.service_id for item in direct_only] == ["tomography"]


def test_implant_placed_required_for_implant_supported_prosthetics() -> None:
    patient = SelectionPatientContext(extent="one_tooth")
    assert "implant_supported_prosthetics" not in _ids(patient, topic="prosthetics")
    patient_ok = SelectionPatientContext(extent="one_tooth", stage="implant_placed")
    assert "implant_supported_prosthetics" in _ids(patient_ok, topic="prosthetics")


def test_option_level_extent_on_removable_dentures() -> None:
    few = SelectionPatientContext(extent="few_teeth")
    items = filter_applicable_services(_bundle(), topic="prosthetics", patient=few)
    entry = next(item for item in items if item.service_id == "removable_dentures")
    assert entry.eligible_option_ids == ("partial",)

    full = SelectionPatientContext(extent="full_arch")
    items_full = filter_applicable_services(_bundle(), topic="prosthetics", patient=full)
    entry_full = next(item for item in items_full if item.service_id == "removable_dentures")
    assert entry_full.eligible_option_ids == ("full",)
