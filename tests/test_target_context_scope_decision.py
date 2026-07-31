"""Contract tests for TargetContextScopeDecision (PERF-6 Phase 2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.target_context_scope_decision import TargetContextScopeDecision

_FP = "a" * 64


def _base(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "level": "service_exact",
        "reason": "service_exact_complete",
        "service_id": "classic",
        "topic": None,
        "context_group_id": None,
        "included_content_refs": ("implantation__service__classic.md",),
        "included_offer_ids": ("classic.one_tooth.implantium",),
        "included_fact_ids": (),
        "included_doctor_ids": (),
        "included_policy_sections": (),
        "estimated_chars": 400,
        "estimated_tokens": 100,
        "package_fingerprint": _FP,
        "completeness_status": "complete",
        "widening_reason": None,
    }
    payload.update(overrides)
    return payload


def test_valid_service_exact_decision_constructs() -> None:
    decision = TargetContextScopeDecision.model_validate(_base())
    assert decision.level == "service_exact"
    assert decision.service_id == "classic"


def test_frozen_and_extra_forbidden() -> None:
    decision = TargetContextScopeDecision.model_validate(_base())
    with pytest.raises(ValidationError):
        decision.level = "full"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        TargetContextScopeDecision.model_validate({**_base(), "unexpected_field": 1})


def test_no_document_text_question_answer_sid_or_contact_fields() -> None:
    fields = set(TargetContextScopeDecision.model_fields)
    forbidden_tokens = {"text", "question", "answer", "sid", "phone", "address"}
    for field in fields:
        tokens = set(field.lower().split("_"))
        assert not (tokens & forbidden_tokens), field


def test_token_estimate_must_match_floor_division() -> None:
    with pytest.raises(ValidationError):
        TargetContextScopeDecision.model_validate(_base(estimated_chars=400, estimated_tokens=99))


def test_service_exact_requires_service_id() -> None:
    with pytest.raises(ValidationError):
        TargetContextScopeDecision.model_validate(_base(service_id=None))


def test_topic_requires_topic_field() -> None:
    with pytest.raises(ValidationError):
        TargetContextScopeDecision.model_validate(
            _base(level="topic", service_id=None, topic=None, reason="topic_complete")
        )


def test_context_group_requires_group_id_and_level() -> None:
    with pytest.raises(ValidationError):
        TargetContextScopeDecision.model_validate(
            _base(level="context_group", service_id=None, context_group_id=None, reason="context_group_complete")
        )
    with pytest.raises(ValidationError):
        # group id set but level not context_group
        TargetContextScopeDecision.model_validate(_base(context_group_id="tooth_restoration"))


def test_full_forbids_narrower_identity() -> None:
    with pytest.raises(ValidationError):
        TargetContextScopeDecision.model_validate(
            _base(
                level="full",
                service_id="classic",
                reason="full_safe_fallback",
                completeness_status="full_required",
                widening_reason="resolver_exception",
            )
        )


def test_full_requires_full_required_status() -> None:
    decision = TargetContextScopeDecision.model_validate(
        _base(
            level="full",
            service_id=None,
            reason="full_safe_fallback",
            completeness_status="full_required",
            widening_reason="no_service_or_topic_signal",
        )
    )
    assert decision.completeness_status == "full_required"
    with pytest.raises(ValidationError):
        TargetContextScopeDecision.model_validate(
            _base(
                level="full",
                service_id=None,
                reason="full_safe_fallback",
                completeness_status="insufficient_widened",
                widening_reason="no_service_or_topic_signal",
            )
        )


def test_complete_forbids_widening_reason_and_incomplete_requires_it() -> None:
    with pytest.raises(ValidationError):
        TargetContextScopeDecision.model_validate(_base(widening_reason="some_reason"))
    with pytest.raises(ValidationError):
        TargetContextScopeDecision.model_validate(
            _base(completeness_status="insufficient_widened", widening_reason=None)
        )


def test_included_ids_must_be_unique() -> None:
    with pytest.raises(ValidationError):
        TargetContextScopeDecision.model_validate(
            _base(included_offer_ids=("classic.one_tooth.implantium", "classic.one_tooth.implantium"))
        )


def test_negative_estimates_rejected() -> None:
    with pytest.raises(ValidationError):
        TargetContextScopeDecision.model_validate(_base(estimated_chars=-1, estimated_tokens=0))


def test_fingerprint_must_be_64_hex_chars() -> None:
    with pytest.raises(ValidationError):
        TargetContextScopeDecision.model_validate(_base(package_fingerprint="not-a-hash"))


def test_reason_must_be_canonical_snake_case_token() -> None:
    with pytest.raises(ValidationError):
        TargetContextScopeDecision.model_validate(_base(reason="Not Canonical!"))
