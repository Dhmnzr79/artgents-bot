"""S2-V0 direct A08 route: raw D1R -> typed D2 -> text/UI -> one store.

This is deliberately an internal experiment, not an HTTP adapter or the full
product. Unsupported inputs fail explicitly; there is no legacy fallback.
"""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from contracts.d2_dialogue import D2DialogueRecord, D2DialogueTurn, D2ProviderInput, D2RawProvider
from contracts.d2_session_context import D2SessionActivity, D2SessionTtlPolicy
from contracts.response_plan import SessionKey
from contracts.response_plan_session import (
    SESSION_SCHEMA_VERSION, PersistedActiveTopic, PersistedShownCommercialIds,
    PersistedShownOptionsSnapshot, PersistedSituationState, ResponsePlanSessionSnapshot,
    ResponsePlanSessionState, empty_session_snapshot,
)
from core.d2_dialogue_store import D2DialogueStore
from core.d2_session_context import (
    bind_d1r_envelope_to_d2_context, project_d2_session_context, seed_d2_plan_focus,
)
from core.d2_snapshot_sources import build_d2_snapshot_sources
from core.d2_tenant_snapshot import build_d2_model_view, load_d2_tenant_snapshot
from core.one_call_envelope_protocol import parse_production_envelope_json
from core.response_plan_materialization import resolve_d2_envelope_response


def run_d2_dialogue_turn(
    *, session_key: SessionKey, user_message: str, provider: D2RawProvider,
    clients_root: Path, store: D2DialogueStore, now: datetime,
    ttl_policy: D2SessionTtlPolicy = D2SessionTtlPolicy(),
) -> D2DialogueTurn:
    """All state/context/sources are built here, never accepted from the caller."""
    tenant = load_d2_tenant_snapshot(session_key.client_id, clients_root=clients_root)
    view = build_d2_model_view(tenant)
    previous = store.read(session_key)
    if previous and previous.tenant_fingerprint != tenant.fingerprint:
        raise ValueError("d2_experiment_tenant_changed")
    snapshot = (ResponsePlanSessionSnapshot(state=previous.state, exists_in_store=True)
                if previous else empty_session_snapshot(session_key))
    context = project_d2_session_context(
        snapshot, expected_session_key=session_key,
        activity=previous.activity if previous else None, policy=ttl_policy, now=now,
    )
    raw = provider.generate(D2ProviderInput(user_message=user_message, model_view=view, context=context))
    envelope = parse_production_envelope_json(
        raw, active_service_catalog=view.active_service_catalog,
        service_reference_catalog=view.service_reference_catalog,
        commercial_fact_catalog=view.commercial_fact_catalog,
    )
    understanding = envelope.request_understanding
    if envelope.route != "ANSWER" or understanding is None or len(understanding.requests) != 1:
        raise ValueError("d2_experiment_single_price_required")
    part = understanding.requests[0]
    subject = next((item for item in understanding.subjects if item.subject_id == part.subject_id), None)
    if (part.kind != "price" or part.service_id is not None or part.topic_id is None
            or subject is None or subject.relation != "self" or subject.age_group == "child"
            or part.situation is None or part.situation.scope_commitment not in {"reported", "unknown"}):
        raise ValueError("d2_experiment_a08_shape_required")
    if context.retained_terminal_state != "none":
        raise ValueError("d2_experiment_terminal_session_unsupported")
    binding = bind_d1r_envelope_to_d2_context(envelope, context)
    focus = seed_d2_plan_focus(binding)
    if focus.action != "resolve_topic" or binding.outcome != "explicit_new_topic":
        raise ValueError("d2_experiment_explicit_new_topic_required")
    sources = build_d2_snapshot_sources(tenant, model_view=view, envelope=envelope, session_key=session_key)
    response = resolve_d2_envelope_response(envelope, sources, as_of=now.date(), d2_plan_focus_seed=focus)
    price = response.resolved.d2_price_block
    decision = response.resolved.d2_price_scope_decision
    if price is None or decision is None or not response.rendered_text.strip():
        raise ValueError("d2_experiment_price_not_resolved")
    turn = snapshot.current_turn_index
    situation = None
    # Persist only finalized facts. C15 consumption, not a candidate alone,
    # authorizes keeping the source extent in the new topic.
    if decision.applied_extent is not None:
        current = part.situation
        if current.scope_commitment == "reported" and current.extent == decision.applied_extent:
            situation = PersistedSituationState(
                session_key=session_key, topic_id=part.topic_id, extent=current.extent,
                jaw=current.jaw, stage="unknown", modifiers=(), set_at_turn=turn,
                situation_owner_id=uuid4().hex, tooth_count=current.tooth_count,
            )
        elif focus.cross_topic_carry is not None:
            source = focus.cross_topic_carry.source_situation
            if source.extent != decision.applied_extent:
                raise ValueError("d2_experiment_carry_extent_mismatch")
            situation = PersistedSituationState(
                session_key=session_key, topic_id=part.topic_id, extent=source.extent,
                jaw=source.jaw, stage=source.stage, modifiers=source.modifiers, set_at_turn=turn,
                situation_owner_id=source.situation_owner_id, tooth_count=source.tooth_count,
            )
    shown_services = tuple(dict.fromkeys(row.service_id for row in price.rows))
    shown_offers = tuple(dict.fromkeys((*context.retained_shown_ids.price_offer_ids,
                                      *(row.offer_id for row in price.rows))))
    state = ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION, session_key=session_key,
        revision=snapshot.state.revision + 1, last_committed_turn_index=turn,
        active_topic=PersistedActiveTopic(topic_id=part.topic_id, provenance="explicit_topic", set_at_turn=turn),
        situation_state=situation,
        shown_options_snapshot=PersistedShownOptionsSnapshot(
            session_key=session_key, topic_id=part.topic_id, service_ids=shown_services,
            shown_at_turn=turn, provenance="finalized_plan_price_offers",
        ),
        accumulated_shown_ids=PersistedShownCommercialIds(price_offer_ids=shown_offers),
        terminal_state=context.retained_terminal_state,
    )
    store.commit(D2DialogueRecord(
        state=state, activity=D2SessionActivity(session_key=session_key, last_user_turn_at=now),
        tenant_fingerprint=tenant.fingerprint,
    ), expected_revision=snapshot.state.revision)
    return D2DialogueTurn(response=response, context=context, focus=focus, committed_revision=state.revision)
