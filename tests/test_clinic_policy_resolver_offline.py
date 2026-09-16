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


def test_requested_oms_booking_blocks_only_that_request() -> None:
    understanding = RequestUnderstanding(subjects=(), requests=(
        RequestUnderstandingRequest(request_id="r1", kind="booking", subject_id=None,
            context="current_care", payment_scheme="oms", payment_scheme_intent="requested_payment"),
        RequestUnderstandingRequest(request_id="r2", kind="booking", subject_id=None,
            context="current_care", payment_scheme="self_pay", payment_scheme_intent="requested_payment"),
    ))
    result = resolve_clinic_policies(client_id="demo", understanding=understanding)
    assert [(d.request_id, d.policy_key, d.outcome) for d in result.decisions] == [
        ("r1", "no_oms", "blocked")]
    assert [entry.status for entry in result.ledger] == ["blocked", "deferred"]
    assert result.active_booking_request_id == "r2"


def test_eligibility_fact_without_policy_id_uses_authored_rule() -> None:
    understanding = RequestUnderstanding(subjects=(), requests=(
        RequestUnderstandingRequest(request_id="r1", kind="clinic_policy", subject_id=None,
            context="general_information", payment_scheme="dms",
            payment_scheme_intent="eligibility_question"),
    ))
    result = resolve_clinic_policies(client_id="demo", understanding=understanding)
    assert [(d.policy_key, d.outcome) for d in result.decisions] == [
        ("no_dms", "allowed_by_known_rules")]
    assert result.ledger[0].status == "answered"


def test_past_childhood_history_does_not_authorize_current_booking() -> None:
    understanding = RequestUnderstanding(subjects=(
        RequestUnderstandingSubject(subject_id="s1", relation="self", age_group="child"),
    ), requests=(
        RequestUnderstandingRequest(request_id="r1", kind="booking", subject_id="s1",
            context="past_history"),
    ))
    result = resolve_clinic_policies(client_id="demo", understanding=understanding)
    assert result.active_booking_request_id is None
    assert result.ledger[0].status == "clarification_needed"
    assert all(d.policy_key != "no_pediatric_dentistry" for d in result.decisions)


def test_payment_rule_is_not_invented_when_pack_lacks_it(monkeypatch) -> None:
    from core import clinic_policy_resolver as resolver
    monkeypatch.setattr(resolver, "_pack_policy_keys", lambda _client_id: frozenset())
    understanding = RequestUnderstanding(subjects=(), requests=(
        RequestUnderstandingRequest(request_id="r1", kind="booking", subject_id=None,
            context="current_care", payment_scheme="oms", payment_scheme_intent="requested_payment"),
    ))
    result = resolve_clinic_policies(client_id="missing", understanding=understanding)
    assert result.active_booking_request_id is None
    assert result.ledger[0].status == "clarification_needed"
    assert result.decisions[0].policy_key is None


def test_child_requested_oms_explains_both_authored_blocks() -> None:
    understanding = RequestUnderstanding(subjects=(
        RequestUnderstandingSubject(subject_id="s1", relation="other", age_group="child"),
    ), requests=(
        RequestUnderstandingRequest(request_id="r1", kind="booking", subject_id="s1",
            context="current_care", payment_scheme="oms", payment_scheme_intent="requested_payment"),
    ))
    result = resolve_clinic_policies(client_id="demo", understanding=understanding)
    assert [d.policy_key for d in result.decisions] == ["no_pediatric_dentistry", "no_oms"]
    assert result.ledger[0].status == "blocked"
