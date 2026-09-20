"""S2-V0 direct A08 route: raw D1R -> typed D2 -> text/UI -> one store.

This is deliberately an internal experiment, not an HTTP adapter or the full
product. Unsupported inputs fail explicitly; there is no legacy fallback.
"""

from datetime import datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from contracts.d2_dialogue import (
    D2CompletedTurn, D2DialogueRecord, D2DialogueTurn, D2LeadEffect,
    D2LeadEffectDispatcher, D2ProviderInput, D2RawProvider,
)
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
from core.user_text_privacy import provider_message_has_substance, provider_safe_user_text


def _request_fingerprint(*, session_key: SessionKey, user_message: str) -> str:
    """Store a non-reversible request identity, never the raw patient message."""
    source = "\x1f".join((session_key.client_id, session_key.sid, user_message))
    return sha256(source.encode("utf-8")).hexdigest()


def _turn_from_completion(completion: D2CompletedTurn, *, idempotent_replay: bool) -> D2DialogueTurn:
    return D2DialogueTurn(
        response=completion.response,
        context=completion.context,
        focus=completion.focus,
        committed_revision=completion.committed_revision,
        request_id=completion.request_id,
        idempotent_replay=idempotent_replay,
        lead_effect=completion.lead_effect,
    )


def _d2_a08_shape_failure_codes(*, part: object, subject: object) -> tuple[str, ...]:
    """Return typed gate failures only; never include model prose or payload values."""
    failures: list[str] = []
    if part.kind != "price":
        failures.append("request_kind_not_price")
    if part.service_id is not None:
        failures.append("request_service_id_present")
    if part.topic_id is None:
        failures.append("request_topic_id_missing")
    if subject is None:
        failures.append("subject_missing")
    else:
        if subject.relation != "self":
            failures.append("subject_relation_not_self")
        if subject.age_group == "child":
            failures.append("subject_age_group_child")
    if part.situation is None:
        failures.append("situation_missing")
    elif part.situation.scope_commitment not in {"reported", "unknown"}:
        failures.append("situation_scope_unsupported")
    return tuple(failures)


def run_d2_dialogue_turn(
    *, session_key: SessionKey, user_message: str, provider: D2RawProvider,
    clients_root: Path, store: D2DialogueStore, now: datetime,
    ttl_policy: D2SessionTtlPolicy = D2SessionTtlPolicy(),
    request_id: str | None = None,
    lead_effect_id: str | None = None,
    lead_effect_dispatcher: D2LeadEffectDispatcher | None = None,
) -> D2DialogueTurn:
    """Complete one D2 turn with one state/result owner and no legacy memory."""
    effective_request_id = (request_id or uuid4().hex).strip()
    if not effective_request_id:
        raise ValueError("d2_request_id_required")
    if (lead_effect_id is None) != (lead_effect_dispatcher is None):
        raise ValueError("d2_lead_effect_pair_required")
    fingerprint = _request_fingerprint(session_key=session_key, user_message=user_message)
    reservation = store.reserve_request(
        session_key, request_id=effective_request_id, request_fingerprint=fingerprint,
    )
    if reservation.is_replay:
        return _turn_from_completion(reservation.completed, idempotent_replay=True)
    safe_user_message = provider_safe_user_text(user_message)
    if not provider_message_has_substance(safe_user_message, raw_source=user_message):
        store.abandon_request(
            session_key, request_id=effective_request_id, request_fingerprint=fingerprint,
        )
        raise ValueError("d2_provider_input_privacy_only")
    try:
        return _run_reserved_d2_dialogue_turn(
            session_key=session_key,
            safe_user_message=safe_user_message,
            provider=provider,
            clients_root=clients_root,
            store=store,
            now=now,
            ttl_policy=ttl_policy,
            request_id=effective_request_id,
            request_fingerprint=fingerprint,
            lead_effect_id=lead_effect_id,
            lead_effect_dispatcher=lead_effect_dispatcher,
        )
    except Exception:
        store.abandon_request(
            session_key, request_id=effective_request_id, request_fingerprint=fingerprint,
        )
        raise


def _run_reserved_d2_dialogue_turn(
    *, session_key: SessionKey, safe_user_message: str, provider: D2RawProvider,
    clients_root: Path, store: D2DialogueStore, now: datetime,
    ttl_policy: D2SessionTtlPolicy, request_id: str, request_fingerprint: str,
    lead_effect_id: str | None, lead_effect_dispatcher: D2LeadEffectDispatcher | None,
) -> D2DialogueTurn:
    """Build a final result only after ``reserve_request`` made this turn owner."""
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
    raw = provider.generate(D2ProviderInput(user_message=safe_user_message, model_view=view, context=context))
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
    shape_failures = _d2_a08_shape_failure_codes(part=part, subject=subject)
    if shape_failures:
        raise ValueError("d2_experiment_a08_shape_required:" + ",".join(shape_failures))
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
    initial_effect = (
        D2LeadEffect(effect_id=lead_effect_id, status="pending")
        if lead_effect_id is not None else D2LeadEffect()
    )
    completion = D2CompletedTurn(
        request_id=request_id,
        request_fingerprint=request_fingerprint,
        response=response,
        context=context,
        focus=focus,
        committed_revision=state.revision,
        lead_effect=initial_effect,
    )
    store.complete(D2DialogueRecord(
        state=state, activity=D2SessionActivity(session_key=session_key, last_user_turn_at=now),
        tenant_fingerprint=tenant.fingerprint,
    ), expected_revision=snapshot.state.revision, completion=completion)
    if lead_effect_dispatcher is not None and lead_effect_id is not None:
        try:
            effect_status = lead_effect_dispatcher.dispatch(effect_id=lead_effect_id)
            if effect_status not in {"sent", "failed", "unknown", "demo_stub"}:
                raise ValueError("d2_lead_effect_dispatch_status_invalid")
        except Exception:
            effect_status = "unknown"
        completion = store.update_lead_effect(
            session_key,
            request_id=request_id,
            effect=D2LeadEffect(effect_id=lead_effect_id, status=effect_status),
        )
    return _turn_from_completion(completion, idempotent_replay=False)
