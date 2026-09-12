from __future__ import annotations

from core.turn_frame_from_raw import build_turn_frame_from_raw
from core.target_patient_scope_projection import project_patient_scope_from_turn_frame
from contracts.patient_scope_projection import NATIVE_PATIENT_SCOPE_PROVENANCE_PREFIX


def _build_frame(*, patient_scope: dict, service_id: str | None = None, topic: str = "implantation"):
    return build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "primary_aspect": "price",
            "service_id": service_id,
            "topic": topic,
            "topic_confidence": 0.9,
            "patient_scope": patient_scope,
        },
        allowed_topics=frozenset({"implantation", "prosthetics"}),
        allowed_service_ids=frozenset({"all_on_4", "classic"}),
    )


def test_native_full_arch_extent_usable() -> None:
    frame = _build_frame(
        patient_scope={
            "extent": "full_arch",
            "jaw": "unknown",
            "stage": "unknown",
            "modifiers": [],
        }
    )
    projected = project_patient_scope_from_turn_frame(frame)
    assert projected.extent.usable is True
    assert projected.extent.value == "full_arch"
    assert projected.extent.provenance.startswith(NATIVE_PATIENT_SCOPE_PROVENANCE_PREFIX)


def test_scalar_bridge_extent_not_usable_for_merge() -> None:
    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "patient_situation": "one_tooth_missing",
            "topic": "implantation",
            "topic_confidence": 0.9,
        },
        allowed_topics=frozenset({"implantation"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )
    projected = project_patient_scope_from_turn_frame(frame)
    assert projected.extent.usable is False
    assert projected.extent.value is None


def test_all_on_4_question_does_not_project_extent() -> None:
    frame = _build_frame(
        patient_scope={
            "extent": "unknown",
            "jaw": "unknown",
            "stage": "unknown",
            "modifiers": [],
        },
        service_id="all_on_4",
    )
    projected = project_patient_scope_from_turn_frame(frame)
    assert projected.extent.usable is False
    assert projected.jaw.usable is False
    assert projected.stage.usable is False


def test_implant_word_does_not_project_implant_placed() -> None:
    frame = _build_frame(
        patient_scope={
            "extent": "unknown",
            "jaw": "unknown",
            "stage": "unknown",
            "modifiers": [],
        }
    )
    projected = project_patient_scope_from_turn_frame(frame)
    assert projected.stage.usable is False


def test_natural_tooth_present_projects_to_stage() -> None:
    frame = _build_frame(
        patient_scope={
            "extent": "unknown",
            "jaw": "unknown",
            "stage": "natural_tooth_present",
            "modifiers": [],
        },
        topic="prosthetics",
    )
    projected = project_patient_scope_from_turn_frame(frame)
    assert projected.stage.usable is True
    assert projected.stage.value == "natural_tooth_present"


def test_reported_bone_deficit_projects_to_reported_context() -> None:
    frame = _build_frame(
        patient_scope={
            "extent": "unknown",
            "jaw": "unknown",
            "stage": "unknown",
            "modifiers": ["reported_bone_deficit"],
        }
    )
    projected = project_patient_scope_from_turn_frame(frame)
    assert projected.reported_context.usable is True
    assert projected.reported_context.value == "reported_bone_deficit"


def test_invalid_extent_is_not_usable() -> None:
    frame = _build_frame(
        patient_scope={
            "extent": "several",
            "jaw": "unknown",
            "stage": "unknown",
            "modifiers": [],
        }
    )
    projected = project_patient_scope_from_turn_frame(frame)
    assert projected.extent.usable is False
