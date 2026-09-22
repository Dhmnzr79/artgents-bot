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
from core.d2_snapshot_sources import build_d2_focus_clarify_response, build_d2_snapshot_sources
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


def _d2_supported_price_shape_failure_codes(*, part: object, subject: object) -> tuple[str, ...]:
    """Return typed gate failures only; never include model prose or payload values."""
    failures: list[str] = []
    if part.kind != "price":
        failures.append("request_kind_not_price")
    # Empty/ambiguous «Сколько стоит?» (A10 / D2-077): no topic and no service → clarify.
    if part.service_id is None and part.topic_id is None:
        if subject is not None and subject.age_group == "child":
            failures.append("subject_age_group_child")
        return tuple(failures)
    if part.topic_id is None:
        failures.append("request_topic_id_missing")
    if part.service_id is None:
        if subject is None:
            failures.append("subject_missing")
        else:
            if subject.age_group == "child":
                failures.append("subject_age_group_child")
            # B11: relation=other is allowed; carry is blocked in session binding.
        # situation=None is the direction overview turn (volume choices).
        if part.situation is not None and part.situation.scope_commitment not in {
            "reported",
            "unknown",
            "correction",
            "hypothetical",
            "reset",
        }:
            failures.append("situation_scope_unsupported")
    return tuple(failures)


def _d2_multipart_shape_ok(*, parts: tuple, subjects_by_id: dict) -> bool:
    """True when the envelope is an assembled multi-part turn (A05/A06/B14 / D2-080).

    Each part must already carry typed refs. Multi-topic is allowed: parts stay
    independent (D2-042 / T2). No patient_text / regex inference.
    """
    if len(parts) < 2 or len(parts) > 3:
        return False
    if any(item.kind not in {"price", "content"} for item in parts):
        return False
    price_parts = tuple(item for item in parts if item.kind == "price")
    content_parts = tuple(item for item in parts if item.kind == "content")
    if not price_parts:
        return False
    # At least one price; optional independent content; extra prices are deferred.
    if len(price_parts) + len(content_parts) != len(parts):
        return False
    for item in price_parts:
        subject = subjects_by_id.get(item.subject_id) if item.subject_id else None
        if _d2_supported_price_shape_failure_codes(part=item, subject=subject):
            return False
        # Direct service or typed topic overview (A05 prices); never empty focus.
        if item.service_id is None and item.topic_id is None:
            return False
    for item in content_parts:
        if item.content_ref is None:
            return False
    return True


def _shown_secondary_ref_ids(response) -> tuple[str, ...]:
    ui = response.ui_projection
    shown: list[str] = []
    if ui.video is not None:
        shown.append(ui.video.video_id)
    shown.extend(item.reply_id for item in ui.quick_replies)
    return tuple(shown)


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
    if envelope.route != "ANSWER" or understanding is None or not understanding.requests:
        raise ValueError("d2_experiment_single_price_required")
    parts = understanding.requests
    part = parts[0]
    subjects_by_id = {item.subject_id: item for item in understanding.subjects}
    multi_part = _d2_multipart_shape_ok(parts=parts, subjects_by_id=subjects_by_id)
    direct_promotion = (
        envelope.commercial_intent == "promotion"
        and envelope.promotion_scope in {"general", "service", "shown"}
        and len(parts) == 1
        and part.kind == "content"
    )
    direct_fact = (
        envelope.commercial_intent == "payment"
        and bool(envelope.references.direct_fact_ids)
        and len(parts) == 1
        and part.kind == "content"
    )
    content_lookup = (
        envelope.commercial_intent == "none"
        and 1 <= len(parts) <= 2
        and all(item.kind == "content" for item in parts)
        and (len(parts) == 2 or part.content_ref is not None)
    )
    if not (direct_promotion or direct_fact or content_lookup or multi_part):
        if len(parts) != 1:
            raise ValueError("d2_experiment_single_price_required")
        subject = subjects_by_id.get(part.subject_id) if part.subject_id else None
        shape_failures = _d2_supported_price_shape_failure_codes(part=part, subject=subject)
        if shape_failures:
            raise ValueError("d2_experiment_a08_shape_required:" + ",".join(shape_failures))
    elif direct_promotion and envelope.promotion_scope == "service" and part.service_id is None:
        raise ValueError("d2_experiment_promotion_service_required")
    # Clarify is soft (A10); hard terminals remain unsupported on this route.
    if context.retained_terminal_state not in {"none", "clarify"}:
        raise ValueError("d2_experiment_terminal_session_unsupported")
    binding = bind_d1r_envelope_to_d2_context(envelope, context)
    focus = seed_d2_plan_focus(binding)
    price_focus_clarify = (
        focus.action == "clarify_focus"
        and part.kind == "price"
        and part.service_id is None
        and part.topic_id is None
        and binding.outcome == "ambiguous_focus"
    )
    if not (direct_promotion and envelope.promotion_scope == "general"):
        if price_focus_clarify or multi_part:
            # Multi-part: each request carries its own typed topic/service (D2-042/T2).
            # Session bind may be ambiguous across topics; parts stay independent.
            pass
        elif (
            focus.action != "resolve_topic"
            or binding.outcome not in {"explicit_new_topic", "clear_continuation"}
        ):
            raise ValueError("d2_experiment_resolved_topic_required")
    if price_focus_clarify:
        response = build_d2_focus_clarify_response(tenant, session_key=session_key)
        price = None
        decision = None
    else:
        sources = build_d2_snapshot_sources(
            tenant,
            model_view=view,
            envelope=envelope,
            session_key=session_key,
            shown_promo_fact_ids=context.retained_shown_ids.promo_fact_ids,
            shown_secondary_ref_ids=context.retained_shown_ids.secondary_ref_ids,
        )
        response = resolve_d2_envelope_response(
            envelope,
            sources,
            as_of=now.date(),
            d2_plan_focus_seed=focus,
            common_route_direct_service_only=True,
            common_route_content_lookup=True,
        )
        price = response.resolved.d2_price_block
        decision = response.resolved.d2_price_scope_decision
    if price_focus_clarify:
        if response.resolved.route != "CLARIFY" or not response.rendered_text.strip():
            raise ValueError("d2_experiment_focus_clarify_not_resolved")
    elif direct_promotion:
        if not response.rendered_text.strip() or not response.resolved.promo_blocks:
            raise ValueError("d2_experiment_promotion_not_resolved")
    elif direct_fact:
        if not response.rendered_text.strip() or not response.resolved.requested_fact_blocks:
            raise ValueError("d2_experiment_fact_not_resolved")
    elif content_lookup:
        if not response.rendered_text.strip():
            raise ValueError("d2_experiment_content_not_resolved")
        if len(parts) == 1 and not response.resolved.information_blocks:
            raise ValueError("d2_experiment_content_not_resolved")
    elif multi_part:
        resolved_parts = response.resolved.d2_request_parts
        if not response.rendered_text.strip():
            raise ValueError("d2_experiment_multipart_not_resolved")
        if not any(item.status in {"answered", "recovered"} for item in resolved_parts):
            raise ValueError("d2_experiment_multipart_not_resolved")
        # Anchor persistence on the first answered price part when present (D2-080).
        answered_price = next(
            (
                item
                for item in resolved_parts
                if item.kind == "price" and item.status == "answered"
            ),
            None,
        )
        if answered_price is not None:
            part = next(item for item in parts if item.request_id == answered_price.request_id)
    elif price is None or (part.service_id is None and decision is None) or not response.rendered_text.strip():
        raise ValueError("d2_experiment_price_not_resolved")
    turn = snapshot.current_turn_index
    # Persist only finalized facts. Hypothetical/overview/unknown must not wipe
    # a previously reported or corrected situation (D2-003).
    situation = snapshot.state.situation_state
    if price_focus_clarify:
        situation = snapshot.state.situation_state
    elif multi_part and (price is None or decision is None or decision.applied_extent is None):
        # Independent parts: do not invent a situation from deferred/unavailable price.
        if (
            snapshot.state.situation_state is not None
            and part.topic_id is not None
            and snapshot.state.situation_state.topic_id != part.topic_id
            and focus.cross_topic_carry is None
        ):
            situation = None
    elif decision is not None and decision.applied_extent is not None:
        current = part.situation
        carried = focus.carried_situation
        if (
            current is not None
            and carried is not None
            and current.continuity == "same"
            and carried.situation_owner_id is not None
            and carried.session_key == session_key
            and carried.topic_id == part.topic_id
            and carried.extent == decision.applied_extent
        ):
            situation = PersistedSituationState(
                session_key=session_key, topic_id=part.topic_id, extent=carried.extent,
                jaw=carried.jaw, stage=carried.stage, modifiers=carried.modifiers, set_at_turn=turn,
                situation_owner_id=carried.situation_owner_id, tooth_count=carried.tooth_count,
            )
        elif (
            current is not None
            and current.scope_commitment in {"reported", "correction"}
            and current.extent == decision.applied_extent
        ):
            situation = PersistedSituationState(
                session_key=session_key, topic_id=part.topic_id, extent=current.extent,
                jaw=current.jaw, stage="unknown", modifiers=(), set_at_turn=turn,
                situation_owner_id=(
                    snapshot.state.situation_state.situation_owner_id
                    if (
                        current.scope_commitment == "correction"
                        and snapshot.state.situation_state is not None
                        and snapshot.state.situation_state.situation_owner_id is not None
                        and snapshot.state.situation_state.topic_id == part.topic_id
                    )
                    else uuid4().hex
                ),
                tooth_count=current.tooth_count,
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
        elif current is not None and current.scope_commitment == "hypothetical":
            situation = snapshot.state.situation_state
    elif decision is not None and decision.reason == "overview":
        current = part.situation
        if current is not None and current.scope_commitment in {"unknown", "reset"}:
            situation = None
        else:
            situation = snapshot.state.situation_state
    elif (
        snapshot.state.situation_state is not None
        and part.topic_id is not None
        and snapshot.state.situation_state.topic_id != part.topic_id
        and focus.cross_topic_carry is None
        and (decision is None or decision.applied_extent is None)
    ):
        # Explicit new topic without carried extent: do not keep prior situation (D2-032).
        situation = None
    shown_services = tuple(dict.fromkeys(row.service_id for row in price.rows)) if price is not None else ()
    extra_offers = tuple(row.offer_id for row in price.rows) if price is not None else ()
    shown_offers = tuple(dict.fromkeys((*context.retained_shown_ids.price_offer_ids, *extra_offers)))
    active_topic = (
        PersistedActiveTopic(topic_id=part.topic_id, provenance="explicit_topic", set_at_turn=turn)
        if part.topic_id is not None
        else snapshot.state.active_topic
    )
    shown_options_snapshot = snapshot.state.shown_options_snapshot
    if price is not None and part.topic_id is not None:
        shown_options_snapshot = PersistedShownOptionsSnapshot(
            session_key=session_key, topic_id=part.topic_id, service_ids=shown_services,
            shown_at_turn=turn, provenance="finalized_plan_price_offers",
        )
    state = ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION, session_key=session_key,
        revision=snapshot.state.revision + 1, last_committed_turn_index=turn,
        active_topic=active_topic,
        situation_state=situation,
        shown_options_snapshot=shown_options_snapshot,
        accumulated_shown_ids=PersistedShownCommercialIds(
            requested_fact_ids=tuple(dict.fromkeys((
                *context.retained_shown_ids.requested_fact_ids,
                *response.resolved.session_delta.shown_requested_fact_ids,
            ))),
            promo_fact_ids=tuple(dict.fromkeys((
                *context.retained_shown_ids.promo_fact_ids,
                *response.resolved.session_delta.shown_promo_ids,
            ))),
            amplifier_fact_ids=context.retained_shown_ids.amplifier_fact_ids,
            service_value_ids=context.retained_shown_ids.service_value_ids,
            price_offer_ids=shown_offers,
            required_offer_condition_ids=context.retained_shown_ids.required_offer_condition_ids,
            shown_service_option_ids=context.retained_shown_ids.shown_service_option_ids,
            secondary_ref_ids=tuple(dict.fromkeys((
                *context.retained_shown_ids.secondary_ref_ids,
                *_shown_secondary_ref_ids(response),
            ))),
        ),
        terminal_state=response.resolved.session_delta.terminal_state,
        clarify_pending=response.resolved.session_delta.clarify_pending,
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
