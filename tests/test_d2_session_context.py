"""D2-117: TTL and ownership without patient bindings or a second focus."""
from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from contracts.d2_session_context import (
    D2SessionState, D2SessionSnapshot, D2SessionActivity, D2SessionTtlPolicy,
    D2SessionContextError, empty_d2_session_snapshot,
)
from contracts.d2_dialogue_result import (
    PendingExplanationOperation, ParameterClarification, ServiceTarget,
)
from contracts.response_plan import SessionKey
from contracts.response_plan_session import PersistedShownCommercialIds, D2ShownPriceOfferRef
from core.d2_session_context import project_d2_session_context

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
KEY = SessionKey(client_id="demo", sid="ttl")


def snapshot():
    return D2SessionSnapshot(state=D2SessionState(
        schema_version=5, session_key=KEY, revision=2, last_committed_turn_index=2,
        discussion_request_id="completed-price", terminal_state="clarify",
        accumulated_shown_ids=PersistedShownCommercialIds(promo_fact_ids=("promo",)),
        d2_shown_price_offer_refs=(D2ShownPriceOfferRef(source_client_id="demo", offer_id="offer", service_id="classic"),),
        clarify_pending=True, clarify_task=PendingExplanationOperation(
            request_id="r1", kind="content", target=ServiceTarget(type="service", id="classic"),
            pending_question="How long?", clarification=ParameterClarification(missing="extent"),
        ),
    ))


@pytest.mark.parametrize("seconds,freshness", [(0,"fresh"),(1799,"fresh"),(1800,"expired"),(1801,"expired")])
def test_ttl_boundary_gates_pending_and_offer_refs_but_retains_terminal_and_shown_ids(seconds, freshness):
    source = snapshot()
    before = source.model_dump()
    context = project_d2_session_context(source, expected_session_key=KEY,
        activity=D2SessionActivity(session_key=KEY,last_user_turn_at=NOW-timedelta(seconds=seconds)),
        policy=D2SessionTtlPolicy(), now=NOW)
    assert context.freshness == freshness
    assert (context.ordinary.clarify_task is not None) == (freshness == "fresh")
    assert bool(context.ordinary.d2_shown_price_offer_refs) == (freshness == "fresh")
    assert context.retained_terminal_state == "clarify"
    assert context.retained_shown_ids.promo_fact_ids == ("promo",)
    assert context.ordinary.discussion_scope is None  # only the receipt reader owns this
    assert source.model_dump() == before


def test_missing_activity_does_not_authorize_context():
    result = project_d2_session_context(snapshot(), expected_session_key=KEY,
        activity=None, policy=D2SessionTtlPolicy(), now=NOW)
    assert result.freshness == "unknown"
    assert result.ordinary.clarify_task is None
    assert result.ordinary.dialogue_pairs == ()


@pytest.mark.parametrize("which", ["snapshot", "activity", "future", "naive"])
def test_owner_and_time_boundaries(which):
    source = snapshot()
    activity = D2SessionActivity(session_key=KEY,last_user_turn_at=NOW)
    foreign = SessionKey(client_id="other",sid=KEY.sid)
    if which == "snapshot":
        source = source.model_copy(update={"state": source.state.model_copy(update={"session_key": foreign})})
    if which == "activity":
        activity = activity.model_copy(update={"session_key": foreign})
    if which == "future":
        activity = activity.model_copy(update={"last_user_turn_at": NOW+timedelta(seconds=1)})
    with pytest.raises(D2SessionContextError):
        project_d2_session_context(source, expected_session_key=KEY, activity=activity,
            policy=D2SessionTtlPolicy(), now=NOW.replace(tzinfo=None) if which == "naive" else NOW)


@pytest.mark.parametrize("field", ["idle_ttl_seconds","history_pair_limit","history_text_max_chars"])
@pytest.mark.parametrize("value", [0,-1,True,"3",1.5])
def test_policy_requires_positive_strict_counters(field,value):
    with pytest.raises(ValidationError):
        D2SessionTtlPolicy(**{field:value})


@pytest.mark.parametrize("field", ["situation_state","active_service","active_topic","shown_options_snapshot","historical_price_offers"])
def test_old_memory_fields_are_rejected_even_when_null(field):
    payload = empty_d2_session_snapshot(KEY).state.model_dump()
    with pytest.raises(ValidationError):
        D2SessionState.model_validate({**payload,field:None})


@pytest.mark.parametrize("version", [3,4,True,"5",6])
def test_old_schema_is_not_migrated(version):
    with pytest.raises(ValidationError):
        D2SessionState.model_validate({**snapshot().state.model_dump(), "schema_version":version})


def test_foreign_offer_and_future_receipt_are_rejected():
    payload = snapshot().state.model_dump()
    payload["d2_shown_price_offer_refs"][0]["source_client_id"] = "foreign"
    with pytest.raises(ValidationError,match="client_mismatch"):
        D2SessionState.model_validate(payload)
    payload = snapshot().state.model_dump()
    payload["dialogue_pairs"] = [{"request_id":"future","patient_text":"hello","committed_at_turn":3}]
    with pytest.raises(ValidationError,match="future_turn"):
        D2SessionState.model_validate(payload)


def test_pending_operation_must_have_pending_state():
    with pytest.raises(ValidationError,match="requires_pending"):
        D2SessionState.model_validate({**snapshot().state.model_dump(),"clarify_pending":False})
