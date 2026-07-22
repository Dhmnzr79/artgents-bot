"""Medical boundary enforcement for TurnFrame policy envelopes (S42, offline/unwired)."""

from __future__ import annotations

from typing import NoReturn

from contracts.target_medical_boundary import (
    TargetMedicalBoundaryEnvelopeEnforcement,
    TargetMedicalBoundaryResult,
    TargetMedicalBoundaryTerminalEnforcement,
)
from contracts.target_response_spec import CanonicalToken
from contracts.target_turn_frame_policy_envelope import TargetTurnFramePolicyEnvelope


class TargetMedicalBoundaryEnforcementError(ValueError):
    """Typed fail-closed envelope enforcement failure."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _fail(code: str, value: object) -> NoReturn:
    raise TargetMedicalBoundaryEnforcementError(code, value)


def _valid_token(value: object) -> bool:
    return type(value) is str and bool(value.strip())


def _valid_token_tuple(value: object, *, nonempty: bool) -> bool:
    return (
        type(value) is tuple
        and (bool(value) or not nonempty)
        and all(_valid_token(item) for item in value)
    )


def _assert_boundary_result_consistent(boundary: TargetMedicalBoundaryResult) -> None:
    if boundary.decision == "none":
        if boundary.reason_code != "boundary_none_confident" or boundary.source != "backend":
            _fail("medical_boundary_result_inconsistent", boundary.model_dump())
    elif boundary.decision == "medical_handoff":
        if (
            boundary.reason_code != "boundary_medical_handoff_confident"
            or boundary.source != "backend"
        ):
            _fail("medical_boundary_result_inconsistent", boundary.model_dump())
    elif boundary.source != "fail_closed" or boundary.reason_code == "boundary_uncertain":
        _fail("medical_boundary_result_inconsistent", boundary.model_dump())


def enforce_target_medical_boundary_on_envelope(
    boundary: TargetMedicalBoundaryResult,
    *,
    tone_key: CanonicalToken,
    allowed_topics: tuple[CanonicalToken, ...],
    forbidden_topics: tuple[CanonicalToken, ...] = (),
    required_fact_ids: tuple[CanonicalToken, ...] = (),
    allow_marketing_facts: bool = False,
    allow_consultation_close: bool = False,
    allow_cta: bool = False,
    min_topic_confidence: float = 0.0,
    min_service_confidence: float = 0.0,
    min_intent_confidence: float = 0.0,
) -> TargetMedicalBoundaryEnvelopeEnforcement | TargetMedicalBoundaryTerminalEnforcement:
    """Map one boundary result to envelope or terminal defer enforcement."""

    if type(boundary) is not TargetMedicalBoundaryResult:
        _fail("medical_boundary_enforcement_input_invalid", boundary)
    if not _valid_token(tone_key):
        _fail("medical_boundary_envelope_tone_invalid", tone_key)
    if not _valid_token_tuple(allowed_topics, nonempty=True):
        _fail("medical_boundary_envelope_allowed_topics_invalid", allowed_topics)
    if not _valid_token_tuple(forbidden_topics, nonempty=False):
        _fail("medical_boundary_envelope_forbidden_topics_invalid", forbidden_topics)
    if not _valid_token_tuple(required_fact_ids, nonempty=False):
        _fail("medical_boundary_envelope_required_fact_ids_invalid", required_fact_ids)

    _assert_boundary_result_consistent(boundary)

    if boundary.decision == "uncertain":
        return TargetMedicalBoundaryTerminalEnforcement()

    boundary_decision = "none" if boundary.decision == "none" else "medical_handoff"
    envelope = TargetTurnFramePolicyEnvelope.model_validate(
        {
            "boundary_decision": boundary_decision,
            "tone_key": tone_key,
            "allowed_topics": allowed_topics,
            "forbidden_topics": forbidden_topics,
            "required_fact_ids": required_fact_ids,
            "allow_marketing_facts": allow_marketing_facts,
            "allow_consultation_close": allow_consultation_close,
            "allow_cta": allow_cta,
            "min_topic_confidence": min_topic_confidence,
            "min_service_confidence": min_service_confidence,
            "min_intent_confidence": min_intent_confidence,
        }
    )
    return TargetMedicalBoundaryEnvelopeEnforcement(envelope=envelope)
