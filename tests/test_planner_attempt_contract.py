"""Unit contract for PlannerAttempt envelope (C2b frame-first)."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import get_args

import pytest

from contracts.planner_attempt import (
    FrameAttemptStatus,
    PlannerAttempt,
    ShadowAttemptStatus,
    turn_frame_has_invalid_or_missing,
)
from contracts.turn_frame import (
    FieldErrorReason,
    FieldMeta,
    PatientScopeFrameMeta,
    TurnFrame,
    TurnFrameMeta,
)


def test_field_error_reason_allowlist_includes_exact_a9_contract():
    assert set(get_args(FieldErrorReason)) == {
        "aspects_empty",
        "aspects_invalid_type",
        "aspect_not_allowed",
        "primary_aspect_unavailable",
        "topic_not_allowed",
        "topic_invalid_type",
        "topic_confidence_invalid",
        "route_invalid",
        "service_id_invalid_type",
        "service_id_not_allowed",
        "followup_of_invalid_type",
        "followup_of_not_allowed",
        "follow_up_unavailable",
        "needs_clarification_invalid_type",
        "patient_extent_invalid_type",
        "patient_extent_not_allowed",
        "patient_jaw_invalid_type",
        "patient_jaw_not_allowed",
        "patient_stage_invalid_type",
        "patient_stage_not_allowed",
        "patient_modifiers_invalid_type",
        "patient_modifier_not_allowed",
        "patient_scope_invalid_type",
        "patient_scope_extra_field",
    }


def _meta(
    *,
    confidence: float = 1.0,
    provenance: str = "test",
    status: str = "valid",
    error: FieldErrorReason | None = None,
) -> FieldMeta:
    return FieldMeta(
        confidence=confidence,
        provenance=provenance,
        status=status,
        error=error,
    )


def _scope_meta(**overrides: FieldMeta) -> PatientScopeFrameMeta:
    base = _meta()
    defaults = {name: base for name in PatientScopeFrameMeta.model_fields}
    defaults.update(overrides)
    return PatientScopeFrameMeta(**defaults)


def _frame_meta(**overrides: FieldMeta | PatientScopeFrameMeta) -> TurnFrameMeta:
    base = _meta()
    defaults = {
        "intent": base,
        "topic": base,
        "aspects": base,
        "primary_aspect": base,
        "emotion": _meta(confidence=0.0, provenance="default", status="defaulted"),
        "specificity": base,
        "patient_scope": _scope_meta(),
        "service_id": base,
        "follow_up": base,
        "followup_of": base,
        "needs_clarification": base,
        "marketing_scenarios": base,
    }
    defaults.update(overrides)
    return TurnFrameMeta(**defaults)


def _frame(**overrides) -> TurnFrame:
    payload = {
        "intent": "content",
        "topic": "clinic",
        "aspects": ["overview"],
        "primary_aspect": "overview",
        "field_meta": _frame_meta(),
    }
    payload.update(overrides)
    return TurnFrame.model_validate(payload)


def test_ok_requires_valid_frame():
    attempt = PlannerAttempt(frame=_frame(), status="ok")
    assert attempt.status == "ok"
    assert attempt.shadow_status == "ok"


def test_ok_without_frame_rejected():
    with pytest.raises(ValueError):
        PlannerAttempt(frame=None, status="ok")


def test_ok_with_invalid_metadata_rejected():
    frame = _frame(
        field_meta=_frame_meta(
            topic=_meta(status="invalid", error="topic_not_allowed", confidence=0.0),
        ),
    )
    with pytest.raises(ValueError):
        PlannerAttempt(frame=frame, status="ok")


def test_partial_requires_invalid_metadata():
    frame = _frame(
        field_meta=_frame_meta(
            aspects=_meta(status="invalid", error="aspects_empty", confidence=0.0),
        ),
    )
    attempt = PlannerAttempt(frame=frame, status="partial")
    assert attempt.status == "partial"


def test_partial_rejects_valid_frame():
    with pytest.raises(ValueError):
        PlannerAttempt(frame=_frame(), status="partial")


def test_not_available_forbids_frame():
    attempt = PlannerAttempt(frame=None, status="not_available")
    assert attempt.frame is None


def test_degraded_forbids_frame():
    attempt = PlannerAttempt(frame=None, status="degraded")
    assert attempt.status == "degraded"


def test_shadow_aliases_match_frame_fields():
    attempt = PlannerAttempt(frame=_frame(), status="ok")
    assert attempt.shadow_frame is attempt.frame
    assert attempt.shadow_status == attempt.status


def test_planner_attempt_contract_has_no_runtime_imports():
    source = Path("contracts/planner_attempt.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert "flask" not in imported
    assert "orchestration" not in imported


def test_only_runtime_and_planner_import_planner_attempt():
    planner_source = Path("core/turn_planner_llm.py").read_text(encoding="utf-8")
    runtime_source = Path("core/runtime_turn_frame.py").read_text(encoding="utf-8")
    assert "PlannerAttempt" in planner_source
    assert "PlannerAttempt" in runtime_source

    paths = [Path("app.py"), Path("llm.py")]
    paths.extend(sorted(Path("core").rglob("*.py")))
    paths.extend(sorted(Path("orchestration").rglob("*.py")))
    allowed = {
        "core/turn_planner_llm.py",
        "core/runtime_turn_frame.py",
        "core/turn_frame_shadow.py",
    }
    offenders: list[str] = []
    for path in paths:
        if path.as_posix() in allowed:
            continue
        source = path.read_text(encoding="utf-8")
        if "PlannerAttempt" in source or "contracts.planner_attempt" in source:
            offenders.append(str(path))
    assert offenders == []
