"""Unit contract for PlannerAttempt envelope (A7; no runtime wiring)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from contracts.planner_attempt import PlannerAttempt, ShadowAttemptStatus
from contracts.turn_frame import FieldErrorReason, FieldMeta, TurnFrame, TurnFrameMeta
from contracts.turn_plan import TurnPlan


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


def _frame_meta(**overrides: FieldMeta) -> TurnFrameMeta:
    base = _meta()
    defaults = {
        "intent": base,
        "topic": base,
        "aspects": base,
        "primary_aspect": base,
        "emotion": _meta(confidence=0.0, provenance="default", status="defaulted"),
        "specificity": base,
        "patient_scope": base,
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
            patient_scope=_meta(status="missing", confidence=0.0, provenance="missing_legacy_axis"),
        ),
    )
    attempt = PlannerAttempt(
        legacy_plan=_legacy_plan(),
        shadow_frame=frame,
        shadow_status="partial",
    )
    assert attempt.shadow_status == "partial"


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


def test_runtime_modules_do_not_import_planner_attempt():
    for rel in (
        "core/turn_frame_shadow.py",
        "orchestration/resolver_turn.py",
        "core/turn_planner_llm.py",
    ):
        source = Path(rel).read_text(encoding="utf-8")
        assert "planner_attempt" not in source
