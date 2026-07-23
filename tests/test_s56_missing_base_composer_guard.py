from __future__ import annotations

import pytest

from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
from core.target_composer_executor import TARGET_COMPOSER_SYSTEM_POLICY
from core.target_response_verifier import TargetResponseVerificationError
from core.target_turn_frame_bound_response import run_target_offline_turn_frame_bound_response
from tests.test_target_fullcontext_content_response import (
    DIABETES_GROUNDED_TEXT,
    FC_MISSING_01_TEXT,
    MISSING_TOPIC_TEXT,
    PAIN_GROUNDED_TEXT,
    RuleBasedSemanticBackend,
    _envelope,
    _frame,
    _pipeline_inputs,
)


class RecordingComposerBackend:
    def __init__(self, text: str) -> None:
        self.text = text
        self.invocations: list[object] = []

    def generate(self, invocation: object, /) -> object:
        self.invocations.append(invocation)
        return self.text


class RecordingSemanticBackend:
    def __init__(self, assessment: object | None = None) -> None:
        from core.target_response_verifier import TargetSemanticAssessment

        self.assessment = assessment or TargetSemanticAssessment()
        self.invocations: list[object] = []

    def assess(self, invocation: object, /) -> object:
        self.invocations.append(invocation)
        return self.assessment


def test_composer_policy_forbids_missing_base_transfer_and_classification() -> None:
    rule_7 = next(
        line for line in TARGET_COMPOSER_SYSTEM_POLICY.splitlines() if line.startswith("7.")
    )
    lowered = rule_7.lower()
    assert "do not name, classify" in lowered
    assert "do not transfer contraindications" in lowered
    assert "immune-system" in lowered


def test_missing_base_lupus_path_verifies_general_external_context() -> None:
    composer = RecordingComposerBackend(FC_MISSING_01_TEXT)
    semantic = RuleBasedSemanticBackend(mode="fc_missing_01")
    result = run_target_offline_turn_frame_bound_response(
        _frame(aspects=["overview"], route="content"),
        _envelope(
            boundary_decision="medical_handoff",
            required_fact_ids=(),
            allow_marketing_facts=False,
        ),
        **_pipeline_inputs(
            user_message="Можно ли делать имплантацию при системной красной волчанке?"
        ),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.verification_status == "verified"


def test_known_diabetes_topic_stays_verified() -> None:
    composer = RecordingComposerBackend(DIABETES_GROUNDED_TEXT)
    semantic = RuleBasedSemanticBackend(mode="diabetes_ok")
    result = run_target_offline_turn_frame_bound_response(
        _frame(aspects=["overview"], route="content"),
        _envelope(
            boundary_decision="medical_handoff",
            required_fact_ids=(),
            allow_marketing_facts=False,
        ),
        **_pipeline_inputs(user_message="Можно ли ставить импланты при диабете?"),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.verification_status == "verified"


def test_general_selling_scenarios_remain_verified() -> None:
    composer = RecordingComposerBackend(PAIN_GROUNDED_TEXT)
    semantic = RuleBasedSemanticBackend(mode="pain")
    result = run_target_offline_turn_frame_bound_response(
        _frame(),
        _envelope(boundary_decision="medical_handoff"),
        **_pipeline_inputs(user_message="Больно ли ставить имплант?"),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.verification_status == "verified"


def test_missing_base_honest_gap_answer_stays_verified() -> None:
    composer = RecordingComposerBackend(MISSING_TOPIC_TEXT)
    semantic = RuleBasedSemanticBackend(mode="missing_ok")
    result = run_target_offline_turn_frame_bound_response(
        _frame(aspects=["overview"], route="content"),
        _envelope(
            boundary_decision="medical_handoff",
            required_fact_ids=(),
            allow_marketing_facts=False,
        ),
        **_pipeline_inputs(
            user_message="Можно ли делать имплантацию при системной красной волчанке?"
        ),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.verification_status == "verified"
