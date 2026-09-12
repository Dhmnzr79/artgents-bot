from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import core.target_turn_frame_policy_envelope_enforcement as enforcement_module
from contracts.target_medical_boundary import (
    TargetMedicalBoundaryEnvelopeEnforcement,
    TargetMedicalBoundaryResult,
    TargetMedicalBoundaryTerminalEnforcement,
)
from core.target_turn_frame_policy_envelope_enforcement import (
    TargetMedicalBoundaryEnforcementError,
    enforce_target_medical_boundary_on_envelope,
)


def _boundary(
    *,
    decision: str,
    reason_code: str,
    source: str = "backend",
    confidence: float = 0.9,
) -> TargetMedicalBoundaryResult:
    return TargetMedicalBoundaryResult.model_validate(
        {
            "decision": decision,
            "confidence": confidence,
            "reason_code": reason_code,
            "source": source,
        }
    )


def _envelope_kwargs() -> dict[str, object]:
    return {
        "tone_key": "commercial_warm",
        "allowed_topics": ("implantation",),
        "forbidden_topics": ("diagnosis", "personal_eligibility"),
    }


def test_confident_none_builds_envelope_with_boundary_none() -> None:
    result = enforce_target_medical_boundary_on_envelope(
        _boundary(decision="none", reason_code="boundary_none_confident"),
        **_envelope_kwargs(),
    )
    assert isinstance(result, TargetMedicalBoundaryEnvelopeEnforcement)
    assert result.envelope.boundary_decision == "none"


def test_medical_handoff_builds_envelope_with_boundary_medical_handoff() -> None:
    result = enforce_target_medical_boundary_on_envelope(
        _boundary(
            decision="medical_handoff",
            reason_code="boundary_medical_handoff_confident",
        ),
        **_envelope_kwargs(),
    )
    assert isinstance(result, TargetMedicalBoundaryEnvelopeEnforcement)
    assert result.envelope.boundary_decision == "medical_handoff"


def test_uncertain_returns_terminal_defer_not_envelope_none() -> None:
    result = enforce_target_medical_boundary_on_envelope(
        _boundary(
            decision="uncertain",
            reason_code="boundary_uncertain_low_confidence",
            source="fail_closed",
            confidence=0.0,
        ),
        **_envelope_kwargs(),
    )
    assert isinstance(result, TargetMedicalBoundaryTerminalEnforcement)
    assert result.terminal_mode == "defer"
    assert result.reason_code == "boundary_uncertain"


def test_invalid_boundary_input_raises() -> None:
    with pytest.raises(TargetMedicalBoundaryEnforcementError) as caught:
        enforce_target_medical_boundary_on_envelope(
            object(),  # type: ignore[arg-type]
            **_envelope_kwargs(),
        )
    assert caught.value.code == "medical_boundary_enforcement_input_invalid"


def test_empty_allowed_topics_raises() -> None:
    with pytest.raises(TargetMedicalBoundaryEnforcementError) as caught:
        enforce_target_medical_boundary_on_envelope(
            _boundary(decision="none", reason_code="boundary_none_confident"),
            tone_key="commercial_warm",
            allowed_topics=(),
        )
    assert caught.value.code == "medical_boundary_envelope_allowed_topics_invalid"


def test_inconsistent_none_result_cannot_build_envelope_with_boundary_none() -> None:
    inconsistent = TargetMedicalBoundaryResult.model_construct(
        decision="none",
        confidence=0.9,
        reason_code="boundary_medical_handoff_confident",
        source="backend",
    )
    with pytest.raises(TargetMedicalBoundaryEnforcementError) as caught:
        enforce_target_medical_boundary_on_envelope(
            inconsistent,
            **_envelope_kwargs(),
        )
    assert caught.value.code == "medical_boundary_result_inconsistent"


def test_inconsistent_uncertain_aggregate_reason_blocked_by_enforcement() -> None:
    inconsistent = TargetMedicalBoundaryResult.model_construct(
        decision="uncertain",
        confidence=0.0,
        reason_code="boundary_uncertain",
        source="fail_closed",
    )
    with pytest.raises(TargetMedicalBoundaryEnforcementError) as caught:
        enforce_target_medical_boundary_on_envelope(
            inconsistent,
            **_envelope_kwargs(),
        )
    assert caught.value.code == "medical_boundary_result_inconsistent"


def test_import_firewall_has_no_legacy_runtime_reads() -> None:
    source = Path(inspect.getfile(enforcement_module)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {
        "ingress_gate",
        "turn_frame",
        "patient_scope",
        "llm",
        "flask",
        "app",
        "orchestration",
        "chunk_responder",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert module.split(".")[0] not in forbidden
