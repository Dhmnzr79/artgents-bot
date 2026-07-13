"""Unit contract for PlannerAttempt envelope (A7; no runtime wiring)."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import get_args

import pytest

from contracts.planner_attempt import (
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
from contracts.turn_plan import TurnPlan


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


def _legacy_plan() -> TurnPlan:
    return TurnPlan(route="content", aspects=["overview"])


def test_ok_with_valid_legacy_plan_and_frame():
    attempt = PlannerAttempt(
        legacy_plan=_legacy_plan(),
        shadow_frame=_frame(),
        shadow_status="ok",
    )
    assert attempt.shadow_status == "ok"


def test_ok_without_legacy_plan_rejected():
    with pytest.raises(ValueError):
        PlannerAttempt(
            legacy_plan=None,
            shadow_frame=_frame(),
            shadow_status="ok",
        )


def test_ok_without_frame_rejected():
    with pytest.raises(ValueError):
        PlannerAttempt(
            legacy_plan=_legacy_plan(),
            shadow_frame=None,
            shadow_status="ok",
        )


def test_ok_with_invalid_metadata_rejected():
    frame = _frame(
        field_meta=_frame_meta(
            topic=_meta(status="invalid", error="topic_not_allowed", confidence=0.0),
        ),
    )
    with pytest.raises(ValueError):
        PlannerAttempt(
            legacy_plan=_legacy_plan(),
            shadow_frame=frame,
            shadow_status="ok",
        )


def test_ok_with_missing_metadata_rejected():
    frame = _frame(
        field_meta=_frame_meta(topic=_meta(status="missing", confidence=0.0, provenance="missing")),
    )
    with pytest.raises(ValueError):
        PlannerAttempt(
            legacy_plan=_legacy_plan(),
            shadow_frame=frame,
            shadow_status="ok",
        )


def test_partial_with_legacy_none_and_frame():
    attempt = PlannerAttempt(
        legacy_plan=None,
        shadow_frame=_frame(),
        shadow_status="partial",
    )
    assert attempt.legacy_plan is None


def test_partial_with_legacy_valid_and_invalid_metadata():
    frame = _frame(
        field_meta=_frame_meta(
            aspects=_meta(status="invalid", error="aspects_empty", confidence=0.0),
        ),
    )
    attempt = PlannerAttempt(
        legacy_plan=_legacy_plan(),
        shadow_frame=frame,
        shadow_status="partial",
    )
    assert attempt.shadow_status == "partial"


def test_partial_with_legacy_valid_and_only_missing_metadata():
    frame = _frame(
        field_meta=_frame_meta(
            patient_scope=_scope_meta(
                extent=_meta(status="missing", confidence=0.0, provenance="missing_legacy_axis"),
            ),
        ),
    )
    attempt = PlannerAttempt(
        legacy_plan=_legacy_plan(),
        shadow_frame=frame,
        shadow_status="partial",
    )
    assert attempt.shadow_status == "partial"


def test_recursive_helper_accepts_nested_all_valid():
    assert turn_frame_has_invalid_or_missing(_frame()) is False


def test_recursive_helper_accepts_nested_all_defaulted():
    defaulted = _meta(
        status="defaulted",
        confidence=0.0,
        provenance="turn_plan.schema_default",
    )
    frame = _frame(
        field_meta=_frame_meta(
            patient_scope=PatientScopeFrameMeta(
                extent=defaulted,
                jaw=defaulted,
                stage=defaulted,
                modifiers=defaulted,
            ),
        ),
    )
    assert turn_frame_has_invalid_or_missing(frame) is False
    assert PlannerAttempt(
        legacy_plan=_legacy_plan(),
        shadow_frame=frame,
        shadow_status="ok",
    ).shadow_status == "ok"


@pytest.mark.parametrize(
    ("subfield", "status", "error"),
    [
        ("extent", "invalid", "patient_extent_not_allowed"),
        ("jaw", "invalid", "patient_jaw_not_allowed"),
        ("stage", "invalid", "patient_stage_not_allowed"),
        ("modifiers", "invalid", "patient_modifier_not_allowed"),
        ("extent", "missing", None),
        ("jaw", "missing", None),
        ("stage", "missing", None),
        ("modifiers", "missing", None),
    ],
)
def test_recursive_helper_detects_each_nested_invalid_or_missing(subfield, status, error):
    issue = _meta(
        status=status,
        error=error,
        confidence=0.0,
        provenance="test.patient_scope",
    )
    frame = _frame(
        field_meta=_frame_meta(
            patient_scope=_scope_meta(**{subfield: issue}),
        ),
    )

    assert turn_frame_has_invalid_or_missing(frame) is True
    with pytest.raises(ValueError, match="ok_forbids_invalid_or_missing_metadata"):
        PlannerAttempt(
            legacy_plan=_legacy_plan(),
            shadow_frame=frame,
            shadow_status="ok",
        )
    assert PlannerAttempt(
        legacy_plan=_legacy_plan(),
        shadow_frame=frame,
        shadow_status="partial",
    ).shadow_status == "partial"


def test_partial_with_legacy_valid_and_fully_valid_frame_rejected():
    with pytest.raises(ValueError):
        PlannerAttempt(
            legacy_plan=_legacy_plan(),
            shadow_frame=_frame(),
            shadow_status="partial",
        )


def test_partial_without_frame_rejected():
    with pytest.raises(ValueError):
        PlannerAttempt(
            legacy_plan=None,
            shadow_frame=None,
            shadow_status="partial",
        )


def test_not_available_with_both_none():
    attempt = PlannerAttempt(
        legacy_plan=None,
        shadow_frame=None,
        shadow_status="not_available",
    )
    assert attempt.shadow_status == "not_available"


def test_not_available_with_legacy_plan_rejected():
    with pytest.raises(ValueError):
        PlannerAttempt(
            legacy_plan=_legacy_plan(),
            shadow_frame=None,
            shadow_status="not_available",
        )


def test_not_available_with_frame_rejected():
    with pytest.raises(ValueError):
        PlannerAttempt(
            legacy_plan=None,
            shadow_frame=_frame(),
            shadow_status="not_available",
        )


def test_degraded_without_frame_with_legacy_none():
    attempt = PlannerAttempt(
        legacy_plan=None,
        shadow_frame=None,
        shadow_status="degraded",
    )
    assert attempt.shadow_status == "degraded"


def test_degraded_without_frame_with_legacy_plan():
    attempt = PlannerAttempt(
        legacy_plan=_legacy_plan(),
        shadow_frame=None,
        shadow_status="degraded",
    )
    assert attempt.legacy_plan is not None


def test_degraded_with_frame_rejected():
    with pytest.raises(ValueError):
        PlannerAttempt(
            legacy_plan=_legacy_plan(),
            shadow_frame=_frame(),
            shadow_status="degraded",
        )


def test_extra_field_rejected():
    with pytest.raises(ValueError):
        PlannerAttempt.model_validate(
            {
                "legacy_plan": None,
                "shadow_frame": None,
                "shadow_status": "not_available",
                "retry_count": 1,
            }
        )


def test_unknown_shadow_status_rejected():
    with pytest.raises(ValueError):
        PlannerAttempt(
            legacy_plan=None,
            shadow_frame=None,
            shadow_status="broken",  # type: ignore[arg-type]
        )


def test_worked_example_topic_doctors_aspects_empty():
    frame = TurnFrame(
        intent="content",
        topic="doctors",
        aspects=[],
        primary_aspect=None,
        field_meta=_frame_meta(
            topic=_meta(confidence=0.95, provenance="turn_plan.raw.topic", status="valid"),
            aspects=_meta(
                confidence=0.0,
                provenance="turn_plan.raw.aspects",
                status="invalid",
                error="aspects_empty",
            ),
            primary_aspect=_meta(
                confidence=0.0,
                provenance="turn_plan.raw.primary_aspect",
                status="invalid",
                error="primary_aspect_unavailable",
            ),
        ),
    )
    attempt = PlannerAttempt(
        legacy_plan=None,
        shadow_frame=frame,
        shadow_status="partial",
    )
    assert attempt.shadow_frame is not None
    assert attempt.shadow_frame.topic == "doctors"
    assert attempt.shadow_frame.field_meta.topic.status == "valid"
    assert attempt.shadow_frame.field_meta.aspects.error == "aspects_empty"
    assert attempt.shadow_frame.field_meta.primary_aspect.error == "primary_aspect_unavailable"


def test_model_dump_has_no_forbidden_leaks():
    attempt = PlannerAttempt(
        legacy_plan=None,
        shadow_frame=_frame(),
        shadow_status="partial",
    )
    dumped = attempt.model_dump()
    text = str(dumped).lower()
    assert "question" not in text
    assert "answer" not in text
    assert "history" not in text
    assert "exception" not in text
    assert "raw" not in dumped


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
    assert "app" not in imported


def test_planner_uses_shared_recursive_helper_without_local_duplicate():
    contract_source = Path("contracts/planner_attempt.py").read_text(encoding="utf-8")
    planner_source = Path("core/turn_planner_llm.py").read_text(encoding="utf-8")

    assert contract_source.count("def turn_frame_has_invalid_or_missing(") == 1
    assert "turn_frame_has_invalid_or_missing" in planner_source
    assert "def _frame_has_invalid_or_missing(" not in planner_source
    assert "TurnFrameMeta.model_fields" not in planner_source


def test_only_planner_and_shadow_recorder_import_planner_attempt():
    planner_source = Path("core/turn_planner_llm.py").read_text(encoding="utf-8")
    recorder_source = Path("core/turn_frame_shadow.py").read_text(encoding="utf-8")
    assert "from contracts.planner_attempt import PlannerAttempt" in planner_source
    assert "from contracts.planner_attempt import PlannerAttempt" in recorder_source

    paths = [Path("app.py"), Path("llm.py")]
    paths.extend(sorted(Path("core").rglob("*.py")))
    paths.extend(sorted(Path("orchestration").rglob("*.py")))
    allowed = {
        "core/turn_planner_llm.py",
        "core/turn_frame_shadow.py",
    }
    offenders: list[str] = []
    for path in paths:
        if path.as_posix() in allowed:
            continue
        source = path.read_text(encoding="utf-8")
        if (
            "contracts.planner_attempt" in source
            or "PlannerAttempt" in source
            or ".shadow_frame" in source
            or ".shadow_status" in source
        ):
            offenders.append(str(path))
    assert offenders == []


def test_patient_scope_contract_has_no_product_consumers():
    paths = [Path("app.py"), Path("llm.py")]
    paths.extend(sorted(Path("core").rglob("*.py")))
    paths.extend(sorted(Path("orchestration").rglob("*.py")))
    allowed = {
        "core/turn_frame_adapter.py",
        "core/turn_frame_from_raw.py",
    }
    forbidden_reads = (
        ".patient_scope.extent",
        ".patient_scope.jaw",
        ".patient_scope.stage",
        ".patient_scope.modifiers",
    )
    offenders: list[str] = []
    for path in paths:
        relative = path.as_posix()
        if relative in allowed:
            continue
        source = path.read_text(encoding="utf-8")
        if (
            "PatientScopeFrame" in source
            or "_patient_scope_from_raw" in source
            or any(token in source for token in forbidden_reads)
        ):
            offenders.append(relative)
    assert offenders == []
