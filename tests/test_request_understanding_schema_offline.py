"""Offline schema tests for request_understanding (D1R)."""

from __future__ import annotations

import pytest

from contracts.request_understanding import (
    RequestUnderstanding,
    RequestUnderstandingRequest,
    RequestUnderstandingSubject,
    minimal_content_understanding,
)


def test_minimal_content_understanding_valid() -> None:
    u = minimal_content_understanding("Привет.")
    assert len(u.requests) == 1
    assert u.requests[0].kind == "content"
    assert u.requests[0].content_text == "Привет."


def test_subject_id_pattern() -> None:
    with pytest.raises(ValueError):
        RequestUnderstandingSubject(subject_id="x1", relation="unknown", age_group="unknown")


def test_unresolved_subject_ref_rejected() -> None:
    with pytest.raises(ValueError, match="subject_id_unresolved"):
        RequestUnderstanding(
            subjects=(),
            requests=(
                RequestUnderstandingRequest(
                    request_id="r1",
                    kind="price",
                    subject_id="s1",
                    context="current_care",
                ),
            ),
        )


def test_empty_subjects_allowed_for_policy() -> None:
    u = RequestUnderstanding(
        subjects=(),
        requests=(
            RequestUnderstandingRequest(
                request_id="r1",
                kind="clinic_policy",
                subject_id=None,
                context="general_information",
                policy_ids=("no_oms",),
            ),
        ),
    )
    assert u.subjects == ()
