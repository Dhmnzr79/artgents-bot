"""Offline tests for clinic_policy_resolver (D1R)."""

from __future__ import annotations

from contracts.request_understanding import RequestUnderstanding, RequestUnderstandingRequest, RequestUnderstandingSubject
from core.clinic_policy_resolver import resolve_clinic_policies


def _policy_req(policy_key: str) -> RequestUnderstanding:
    return RequestUnderstanding(
        subjects=(),
        requests=(
            RequestUnderstandingRequest(
                request_id="r1",
                kind="clinic_policy",
                subject_id=None,
                context="general_information",
                policy_ids=(policy_key,),
            ),
        ),
    )


def test_demo_pack_resolves_no_oms() -> None:
    result = resolve_clinic_policies(client_id="demo", understanding=_policy_req("no_oms"))
    assert any(d.policy_key == "no_oms" for d in result.decisions)
    assert result.ledger[0].status == "answered"


def test_child_price_blocked_on_demo() -> None:
    understanding = RequestUnderstanding(
        subjects=(
            RequestUnderstandingSubject(subject_id="s1", relation="other", age_group="child"),
        ),
        requests=(
            RequestUnderstandingRequest(
                request_id="r1",
                kind="price",
                subject_id="s1",
                context="current_care",
            ),
        ),
    )
    result = resolve_clinic_policies(client_id="demo", understanding=understanding)
    assert result.suppress_forbidden_booking_cta
    assert result.ledger[0].status == "blocked"
