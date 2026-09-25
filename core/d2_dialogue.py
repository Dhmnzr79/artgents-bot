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
    D2LeadEffectDispatcher, D2ProviderInput, D2RawProvider, D2SelectedUiRef,
)
from contracts.d2_session_context import D2SessionActivity, D2SessionTtlPolicy
from contracts.response_plan import SessionKey
from contracts.response_plan_session import (
    SESSION_SCHEMA_VERSION, D2ShownPriceOfferRef, PersistedActiveService, PersistedActiveTopic,
    PersistedClarifyTask, PersistedShownCommercialIds, PersistedShownOptionsSnapshot,
    PersistedSituationState, ResponsePlanSessionSnapshot, ResponsePlanSessionState,
    SessionDialoguePair, empty_session_snapshot,
)
from core.d2_dialogue_store import D2DialogueStore
from core.d2_lead_bridge import (
    d2_lead_needs_pre_provider,
    d2_lead_session_client_matches,
    resolve_d2_booking_lead_entry,
    resolve_d2_lead_pre_provider,
)
from core.d2_session_context import (
    bind_d1r_envelope_to_d2_context, project_d2_session_context, seed_d2_plan_focus,
)
from core.d2_snapshot_sources import (
    build_d2_focus_clarify_response,
    build_d2_manual_contact_terminal_response,
    build_d2_snapshot_sources,
    build_d2_clinic_policy_response,
    build_d2_clinic_policy_fact_block,
    build_d2_brand_policy_response,
    build_d2_service_availability_response,
    build_d2_unknown_reference_response,
    resolve_d2_clarify_service_topic,
)
from core.d2_spam_gate import build_d2_spam_gate_response, is_d2_garbage_message
from core.d2_contacts_cta import build_d2_contact_fact_block, build_d2_contact_response
from core.d2_offtopic import build_d2_offtopic_response, is_d2_offtopic_envelope
from core.d2_tenant_snapshot import build_d2_model_view, load_d2_tenant_snapshot
from core.one_call_envelope_protocol import (
    parse_production_envelope_json,
    production_envelope_template,
)
from core.response_plan_materialization import resolve_d2_envelope_response
from core.user_text_privacy import provider_message_has_substance, provider_safe_user_text
import json


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
    if any(item.kind not in {"price", "content", "contact", "clinic_policy"} for item in parts):
        return False
    price_parts = tuple(item for item in parts if item.kind == "price")
    content_parts = tuple(item for item in parts if item.kind == "content")
    contact_parts = tuple(item for item in parts if item.kind == "contact")
    policy_parts = tuple(item for item in parts if item.kind == "clinic_policy")
    if not price_parts and not content_parts:
        return False
    # Typed exact facts may be added to an ordinary FullContext/price answer.
    if len(price_parts) + len(content_parts) + len(contact_parts) + len(policy_parts) != len(parts):
        return False
    if any(not item.policy_ids for item in policy_parts):
        return False
    for item in price_parts:
        subject = subjects_by_id.get(item.subject_id) if item.subject_id else None
        if _d2_supported_price_shape_failure_codes(part=item, subject=subject):
            return False
        # Direct service or typed topic overview (A05 prices); never empty focus.
        if item.service_id is None and item.topic_id is None:
            return False
    # FullContext prose has optional provenance. A missing content_ref must not
    # prevent it from being combined with a typed price request.
    return True


def _shown_secondary_ref_ids(response) -> tuple[str, ...]:
    ui = response.ui_projection
    shown: list[str] = []
    if ui.video is not None:
        shown.append(ui.video.video_id)
    shown.extend(item.reply_id for item in ui.quick_replies)
    return tuple(shown)


def _bounded_d2_text(value: str, *, limit: int) -> str:
    """Keep only bounded, provider-safe prose in the D2 dialogue memory."""
    return value.strip()[:limit].strip()


def _d2_live_prose_for_history(response) -> str | None:
    """Return only free model prose; frozen price and authored blocks are excluded."""
    resolved = response.resolved
    if resolved.route != "ANSWER" or resolved.is_price_answer:
        return None
    if resolved.patient_text is not None:
        return resolved.patient_text
    blocks = tuple(
        block.display_text
        for block in resolved.information_blocks
        if block.publication == "model_prose"
    )
    return "\n\n".join(blocks) if blocks else None


def _next_d2_dialogue_pairs(
    *, snapshot: ResponsePlanSessionSnapshot, safe_user_message: str,
    selected_ui_ref: D2SelectedUiRef | None, response, turn: int,
    ttl_policy: D2SessionTtlPolicy, context,
) -> tuple[SessionDialoguePair, ...]:
    """Append one live-prose pair; code-owned prices and terminal stubs stay out."""
    assistant_text = _d2_live_prose_for_history(response)
    previous_pairs = (
        snapshot.state.dialogue_pairs if context.freshness == "fresh" else ()
    )
    if assistant_text is None:
        return previous_pairs
    assistant_text = _bounded_d2_text(
        assistant_text, limit=ttl_policy.history_text_max_chars,
    )
    if not assistant_text:
        return previous_pairs
    patient_text = _bounded_d2_text(
        safe_user_message, limit=ttl_policy.history_text_max_chars,
    )
    if selected_ui_ref is None and not patient_text:
        return previous_pairs
    pair = SessionDialoguePair(
        patient_text=patient_text if selected_ui_ref is None else None,
        selected_ui_ref=selected_ui_ref,
        assistant_text=assistant_text,
        committed_at_turn=turn,
    )
    return (*previous_pairs, pair)[-ttl_policy.history_pair_limit:]


def _d2_clarify_task(*, envelope) -> PersistedClarifyTask:
    """Persist the unresolved typed request; never derive it from dialogue prose."""
    understanding = envelope.request_understanding
    if understanding is None:
        raise ValueError("d2_clarify_task_understanding_required")
    requests = understanding.requests
    return PersistedClarifyTask(
        axis=envelope.clarify_axis or "focus",
        request_ids=tuple(item.request_id for item in requests),
        request_kinds=tuple(dict.fromkeys(item.kind for item in requests)),
        topic_ids=tuple(dict.fromkeys(
            item.topic_id for item in requests if item.topic_id is not None
        )),
        service_ids=tuple(dict.fromkeys(
            item.service_id for item in requests if item.service_id is not None
        )),
        requested_extents=tuple(dict.fromkeys(
            item.situation.extent
            for item in requests
            if item.situation is not None
        )),
    )


def _next_d2_shown_price_offer_refs(*, snapshot, price, context):
    """Retain only verified D2 offer IDs and display order, never price prose."""
    if price is None:
        return (
            snapshot.state.d2_shown_price_offer_refs
            if context.freshness == "fresh"
            else ()
        )
    return tuple(
        D2ShownPriceOfferRef(
            source_client_id=row.source_client_id,
            offer_id=row.offer_id,
            service_id=row.service_id,
        )
        for row in price.rows
    )


def run_d2_dialogue_turn(
    *, session_key: SessionKey, user_message: str, provider: D2RawProvider,
    clients_root: Path, store: D2DialogueStore, now: datetime,
    ttl_policy: D2SessionTtlPolicy = D2SessionTtlPolicy(),
    request_id: str | None = None,
    lead_effect_id: str | None = None,
    lead_effect_dispatcher: D2LeadEffectDispatcher | None = None,
    lead_ui_ref: str | None = None,
    ui_revision: int | None = None,
    situation_action: str | None = None,
    lead_bridge: bool = False,
) -> D2DialogueTurn:
    """Complete one D2 turn with one state/result owner.

    Ordinary dialogue state lives in ``D2DialogueStore``. Active lead/privacy
    slots stay with the existing session owner (CP5-LEAD / D2-036); only a
    PII-free effect receipt may be recorded on the D2 completion.

    ``lead_bridge=True`` enables booking entry via the existing lead owner.
    Every turn may read the client binding to detect an already active lead;
    ordinary state remains exclusively in ``D2DialogueStore``.
    """
    effective_request_id = (request_id or uuid4().hex).strip()
    if not effective_request_id:
        raise ValueError("d2_request_id_required")
    if (lead_effect_id is None) != (lead_effect_dispatcher is None):
        raise ValueError("d2_lead_effect_pair_required")
    fingerprint = _request_fingerprint(
        session_key=session_key,
        user_message="\x1f".join(
            (
                user_message,
                (lead_ui_ref or "").strip(),
                str(ui_revision or ""),
                (situation_action or "").strip(),
            )
        ),
    )
    reservation = store.reserve_request(
        session_key, request_id=effective_request_id, request_fingerprint=fingerprint,
    )
    if reservation.is_replay:
        return _turn_from_completion(reservation.completed, idempotent_replay=True)
    try:
        tenant = load_d2_tenant_snapshot(session_key.client_id, clients_root=clients_root)
        previous = store.read(session_key)
        if previous and previous.tenant_fingerprint != tenant.fingerprint:
            raise ValueError("d2_experiment_tenant_changed")
        early_snapshot = (
            ResponsePlanSessionSnapshot(state=previous.state, exists_in_store=True)
            if previous else empty_session_snapshot(session_key)
        )
        early_context = project_d2_session_context(
            early_snapshot,
            expected_session_key=session_key,
            activity=previous.activity if previous else None,
            policy=ttl_policy,
            now=now,
        )
        selected_ui_ref: D2SelectedUiRef | None = None
        if lead_ui_ref and ui_revision is not None:
            shown = store.read_latest_completion(session_key)
            if (
                previous is None or shown is None or early_context.freshness != "fresh"
                or previous.state.revision != ui_revision
                or shown.committed_revision != ui_revision
            ):
                raise ValueError("d2_stale_ui_action")
            ui = shown.response.ui_projection
            if lead_ui_ref.startswith("button:"):
                button_id = lead_ui_ref.removeprefix("button:")
                button = next((item for item in ui.buttons if item.button_id == button_id), None)
                if button is None or button.source_client_id != session_key.client_id or button.action_kind != "cta":
                    raise ValueError("d2_unauthorized_ui_action")
                lead_ui_ref = "d2:booking_cta"
            else:
                reply = next((item for item in ui.quick_replies if item.reply_id == lead_ui_ref), None)
                if reply is None or reply.source_client_id != session_key.client_id:
                    raise ValueError("d2_unauthorized_ui_action")
                if not lead_ui_ref.startswith("lead:"):
                    selected_ui_ref = D2SelectedUiRef(
                        reply_id=reply.reply_id,
                        source_revision=ui_revision,
                    )
        # D2-071: closed until a new chat/sid; beats lead and ordinary turns.
        if early_context.retained_terminal_state == "spam_closed":
            return _run_spam_gate_turn(
                session_key=session_key,
                clients_root=clients_root,
                store=store,
                now=now,
                ttl_policy=ttl_policy,
                request_id=effective_request_id,
                request_fingerprint=fingerprint,
                kind="closed",
                tenant=tenant,
                previous=previous,
                snapshot=early_snapshot,
                context=early_context,
            )
        session_matched = d2_lead_session_client_matches(session_key)
        lead_gate = bool(
            lead_bridge
            or session_matched
            or (situation_action or "").strip()
            or (lead_ui_ref or "").strip()
        )
        if lead_gate and d2_lead_needs_pre_provider(
            session_key=session_key,
            situation_action=situation_action,
            lead_ui_ref=lead_ui_ref,
        ):
            return _run_lead_pre_provider_turn(
                session_key=session_key,
                user_message=user_message,
                clients_root=clients_root,
                store=store,
                now=now,
                ttl_policy=ttl_policy,
                request_id=effective_request_id,
                request_fingerprint=fingerprint,
                lead_effect_id=lead_effect_id,
                lead_effect_dispatcher=lead_effect_dispatcher,
                lead_ui_ref=lead_ui_ref,
                situation_action=situation_action,
            )
        # D2-040: one authored chance, then hard-stop. Lead/medical terminals stay owners.
        if (
            selected_ui_ref is None
            and is_d2_garbage_message(user_message)
            and early_context.retained_terminal_state in {
            "none",
            "clarify",
            "spam_warn",
            }
        ):
            kind = (
                "closed"
                if early_context.retained_terminal_state == "spam_warn"
                else "warn"
            )
            return _run_spam_gate_turn(
                session_key=session_key,
                clients_root=clients_root,
                store=store,
                now=now,
                ttl_policy=ttl_policy,
                request_id=effective_request_id,
                request_fingerprint=fingerprint,
                kind=kind,
                tenant=tenant,
                previous=previous,
                snapshot=early_snapshot,
                context=early_context,
            )
        safe_user_message = provider_safe_user_text(user_message)
        if (
            selected_ui_ref is None
            and not provider_message_has_substance(safe_user_message, raw_source=user_message)
        ):
            store.abandon_request(
                session_key, request_id=effective_request_id, request_fingerprint=fingerprint,
            )
            raise ValueError("d2_provider_input_privacy_only")
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
            lead_bridge=lead_bridge,
            selected_ui_ref=selected_ui_ref,
            selected_service_id=(
                lead_ui_ref.removeprefix("service:")
                if lead_ui_ref and lead_ui_ref.startswith("service:") and ui_revision is not None
                else None
            ),
        )
    except Exception:
        store.abandon_request(
            session_key, request_id=effective_request_id, request_fingerprint=fingerprint,
        )
        raise


def _run_spam_gate_turn(
    *,
    session_key: SessionKey,
    clients_root: Path,
    store: D2DialogueStore,
    now: datetime,
    ttl_policy: D2SessionTtlPolicy,
    request_id: str,
    request_fingerprint: str,
    kind: str,
    tenant,
    previous,
    snapshot,
    context,
) -> D2DialogueTurn:
    """Authored spam warn/closed stub without a provider call."""
    del clients_root, ttl_policy, previous  # already projected by caller
    response = build_d2_spam_gate_response(tenant, session_key=session_key, kind=kind)
    if response.resolved.route != "ADMIN" or not response.rendered_text.strip():
        raise ValueError("d2_experiment_spam_gate_not_resolved")
    raw = json.dumps(
        production_envelope_template(
            route="ADMIN",
            patient_text=None,
            commercial_intent="none",
            promotion_scope="none",
            scenario="none",
            primary_price_request_id=None,
            request_understanding={"subjects": [], "requests": []},
        ),
        ensure_ascii=False,
    )
    view = build_d2_model_view(tenant)
    envelope = parse_production_envelope_json(
        raw,
        active_service_catalog=view.active_service_catalog,
        service_reference_catalog=view.service_reference_catalog,
        commercial_fact_catalog=view.commercial_fact_catalog,
    )
    binding = bind_d1r_envelope_to_d2_context(envelope, context)
    focus = seed_d2_plan_focus(binding)
    return _commit_non_price_d2_turn(
        session_key=session_key,
        store=store,
        snapshot=snapshot,
        context=context,
        focus=focus,
        response=response,
        tenant_fingerprint=tenant.fingerprint,
        now=now,
        request_id=request_id,
        request_fingerprint=request_fingerprint,
        lead_effect_id=None,
        lead_effect_dispatcher=None,
    )


def _run_lead_pre_provider_turn(
    *,
    session_key: SessionKey,
    user_message: str,
    clients_root: Path,
    store: D2DialogueStore,
    now: datetime,
    ttl_policy: D2SessionTtlPolicy,
    request_id: str,
    request_fingerprint: str,
    lead_effect_id: str | None,
    lead_effect_dispatcher: D2LeadEffectDispatcher | None,
    lead_ui_ref: str | None,
    situation_action: str | None,
) -> D2DialogueTurn:
    """Situation intake / active lead slots: no provider, existing privacy owners."""
    if not d2_lead_session_client_matches(session_key):
        raise ValueError("d2_lead_session_client_required")
    tenant = load_d2_tenant_snapshot(session_key.client_id, clients_root=clients_root)
    previous = store.read(session_key)
    if previous and previous.tenant_fingerprint != tenant.fingerprint:
        raise ValueError("d2_experiment_tenant_changed")
    snapshot = (
        ResponsePlanSessionSnapshot(state=previous.state, exists_in_store=True)
        if previous else empty_session_snapshot(session_key)
    )
    context = project_d2_session_context(
        snapshot, expected_session_key=session_key,
        activity=previous.activity if previous else None, policy=ttl_policy, now=now,
    )
    bridge = resolve_d2_lead_pre_provider(
        snapshot=tenant,
        session_key=session_key,
        user_message=user_message,
        situation_action=situation_action,
        lead_ui_ref=lead_ui_ref,
    )
    if not bridge.response.rendered_text.strip():
        raise ValueError("d2_experiment_lead_not_resolved")
    effect_id = lead_effect_id
    effect_dispatcher = lead_effect_dispatcher
    if bridge.request_effect:
        if effect_id is None:
            effect_id = f"lead-{request_id}"

            class _DemoStubDispatcher:
                def dispatch(self, *, effect_id: str):
                    return "demo_stub"

            effect_dispatcher = effect_dispatcher or _DemoStubDispatcher()
    # Synthetic empty envelope: lead does not reinterpret ordinary focus.
    raw = json.dumps(
        production_envelope_template(
            route="ANSWER",
            patient_text=None,
            commercial_intent="none",
            promotion_scope="none",
            scenario="none",
            primary_price_request_id=None,
            request_understanding={
                "subjects": [],
                "requests": [
                    {
                        "request_id": "r1",
                        "kind": "booking",
                        "subject_id": None,
                        "context": "general_information",
                        "policy_ids": [],
                        "payment_scheme": "unspecified",
                        "payment_scheme_intent": "not_requested",
                        "contact_fields": [],
                        "content_text": None,
                    }
                ],
            },
        ),
        ensure_ascii=False,
    )
    view = build_d2_model_view(tenant)
    envelope = parse_production_envelope_json(
        raw, active_service_catalog=view.active_service_catalog,
        service_reference_catalog=view.service_reference_catalog,
        commercial_fact_catalog=view.commercial_fact_catalog,
    )
    binding = bind_d1r_envelope_to_d2_context(envelope, context)
    focus = seed_d2_plan_focus(binding)
    return _commit_non_price_d2_turn(
        session_key=session_key,
        store=store,
        snapshot=snapshot,
        context=context,
        focus=focus,
        response=bridge.response,
        tenant_fingerprint=tenant.fingerprint,
        now=now,
        request_id=request_id,
        request_fingerprint=request_fingerprint,
        lead_effect_id=effect_id if bridge.request_effect else lead_effect_id,
        lead_effect_dispatcher=(
            effect_dispatcher if bridge.request_effect else lead_effect_dispatcher
        ),
    )


def _commit_non_price_d2_turn(
    *,
    session_key: SessionKey,
    store: D2DialogueStore,
    snapshot,
    context,
    focus,
    response,
    tenant_fingerprint: str,
    now: datetime,
    request_id: str,
    request_fingerprint: str,
    lead_effect_id: str | None,
    lead_effect_dispatcher: D2LeadEffectDispatcher | None,
    shown_service_options: tuple[str, ...] = (),
    shown_service_topic: str | None = None,
    selected_service_id: str | None = None,
    selected_service_topic: str | None = None,
    clear_active_service: bool = False,
    clear_situation: bool = False,
    dialogue_pairs: tuple[SessionDialoguePair, ...] | None = None,
    d2_shown_price_offer_refs: tuple[D2ShownPriceOfferRef, ...] | None = None,
    clarify_task: PersistedClarifyTask | None = None,
) -> D2DialogueTurn:
    """Persist lead/terminal/clarify-style turns without mutating price situation."""
    turn = snapshot.current_turn_index
    state = ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION, session_key=session_key,
        revision=snapshot.state.revision + 1, last_committed_turn_index=turn,
        active_service=(
            PersistedActiveService(
                service_id=selected_service_id, provenance="explicit_current", set_at_turn=turn,
            ) if selected_service_id is not None else (
                None if clear_active_service else snapshot.state.active_service
            )
        ),
        active_topic=(
            PersistedActiveTopic(
                topic_id=selected_service_topic, provenance="explicit_topic", set_at_turn=turn,
            ) if selected_service_topic is not None else snapshot.state.active_topic
        ),
        situation_state=None if clear_situation else snapshot.state.situation_state,
        shown_options_snapshot=(
            PersistedShownOptionsSnapshot(
                session_key=session_key, topic_id=shown_service_topic,
                service_ids=shown_service_options, shown_at_turn=turn,
            )
            if shown_service_options and shown_service_topic is not None
            else snapshot.state.shown_options_snapshot
        ),
        dialogue_pairs=(
            (
                snapshot.state.dialogue_pairs
                if context.freshness == "fresh"
                else ()
            )
            if dialogue_pairs is None
            else dialogue_pairs
        ),
        d2_shown_price_offer_refs=(
            (
                snapshot.state.d2_shown_price_offer_refs
                if context.freshness == "fresh"
                else ()
            )
            if d2_shown_price_offer_refs is None
            else d2_shown_price_offer_refs
        ),
        accumulated_shown_ids=PersistedShownCommercialIds(
            requested_fact_ids=context.retained_shown_ids.requested_fact_ids,
            promo_fact_ids=context.retained_shown_ids.promo_fact_ids,
            amplifier_fact_ids=context.retained_shown_ids.amplifier_fact_ids,
            service_value_ids=context.retained_shown_ids.service_value_ids,
            price_offer_ids=context.retained_shown_ids.price_offer_ids,
            required_offer_condition_ids=context.retained_shown_ids.required_offer_condition_ids,
            shown_service_option_ids=tuple(dict.fromkeys((
                *context.retained_shown_ids.shown_service_option_ids,
                *shown_service_options,
            ))),
            secondary_ref_ids=tuple(dict.fromkeys((
                *context.retained_shown_ids.secondary_ref_ids,
                *_shown_secondary_ref_ids(response),
            ))),
        ),
        terminal_state=response.resolved.session_delta.terminal_state,
        clarify_pending=response.resolved.session_delta.clarify_pending,
        clarify_task=(
            clarify_task if response.resolved.session_delta.clarify_pending else None
        ),
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
        tenant_fingerprint=tenant_fingerprint,
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


def _run_reserved_d2_dialogue_turn(
    *, session_key: SessionKey, safe_user_message: str, provider: D2RawProvider,
    clients_root: Path, store: D2DialogueStore, now: datetime,
    ttl_policy: D2SessionTtlPolicy, request_id: str, request_fingerprint: str,
    lead_effect_id: str | None, lead_effect_dispatcher: D2LeadEffectDispatcher | None,
    lead_bridge: bool = False,
    selected_ui_ref: D2SelectedUiRef | None = None,
    selected_service_id: str | None = None,
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
    raw = provider.generate(D2ProviderInput(
        user_message=safe_user_message,
        model_view=view,
        context=context,
        selected_ui_ref=selected_ui_ref,
    ))
    envelope = parse_production_envelope_json(
        raw, active_service_catalog=view.active_service_catalog,
        service_reference_catalog=view.service_reference_catalog,
        commercial_fact_catalog=view.commercial_fact_catalog,
    )
    selected_topic = None
    if selected_service_id is not None:
        selected_topic = resolve_d2_clarify_service_topic(tenant, (selected_service_id,))
        understanding_for_click = envelope.request_understanding
        if selected_topic is None or envelope.route not in {"ANSWER", "CLARIFY"} or understanding_for_click is None or len(understanding_for_click.requests) != 1:
            raise ValueError("d2_ui_service_selection_unresolved")
        if envelope.route == "CLARIFY" and envelope.clarify_axis == "service":
            raise ValueError("d2_ui_service_selection_unresolved")
        selected_part = understanding_for_click.requests[0]
        if (
            selected_part.kind not in {"content", "price"}
            or selected_part.service_id not in {None, selected_service_id}
            or selected_part.topic_id not in {None, selected_topic}
        ):
            raise ValueError("d2_ui_service_selection_mismatch")
        selected_part = selected_part.model_copy(update={
            "service_id": selected_service_id, "topic_id": selected_topic,
        })
        understanding_for_click = understanding_for_click.model_copy(update={
            "requests": (selected_part,),
        })
        envelope = envelope.model_copy(update={"request_understanding": understanding_for_click})
    understanding = envelope.request_understanding
    # ``other`` with actual prose is an ordinary answer, not a menu route.
    # Keep empty ``other`` for the explicit off-topic response below.
    if (
        envelope.route == "ANSWER"
        and understanding is not None
        and len(understanding.requests) == 1
        and understanding.requests[0].kind == "other"
        and (understanding.requests[0].content_text or "").strip()
    ):
        ordinary = understanding.requests[0].model_copy(update={"kind": "content"})
        envelope = envelope.model_copy(update={
            "request_understanding": understanding.model_copy(update={"requests": (ordinary,)})
        })
        understanding = envelope.request_understanding
    admin_terminal = envelope.route == "ADMIN"
    if admin_terminal:
        # B03/D2-023: one authored stub; no ordinary parts / focus required.
        if context.retained_terminal_state not in {"none", "clarify", "admin", "medical_terminal"}:
            raise ValueError("d2_experiment_terminal_session_unsupported")
        response = build_d2_manual_contact_terminal_response(tenant, session_key=session_key)
        if response.resolved.route != "ADMIN" or not response.rendered_text.strip():
            raise ValueError("d2_experiment_admin_terminal_not_resolved")
        binding = bind_d1r_envelope_to_d2_context(envelope, context)
        focus = seed_d2_plan_focus(binding)
        price = None
        decision = None
        part = None
        price_focus_clarify = False
        clinic_policy = False
        service_availability = False
        unknown_brand = False
        unknown_term = False
        clinic_contact = False
        offtopic = False
        direct_promotion = False
        direct_fact = False
        content_lookup = False
        multi_part = False
        parts = ()
        directory_kind = None
    elif envelope.route == "CLARIFY":
        if context.retained_terminal_state not in {"none", "clarify", "spam_warn"}:
            raise ValueError("d2_experiment_terminal_session_unsupported")
        response = build_d2_focus_clarify_response(
            tenant,
            session_key=session_key,
            clarify_axis=envelope.clarify_axis,
            service_options=envelope.clarify_service_options,
        )
        if response.resolved.route != "CLARIFY" or not response.rendered_text.strip():
            raise ValueError("d2_experiment_clarify_not_resolved")
        binding = bind_d1r_envelope_to_d2_context(envelope, context)
        focus = seed_d2_plan_focus(binding)
        shown_topic = (
            resolve_d2_clarify_service_topic(tenant, envelope.clarify_service_options)
            if envelope.clarify_service_options else None
        )
        return _commit_non_price_d2_turn(
            session_key=session_key, store=store, snapshot=snapshot, context=context,
            focus=focus, response=response, tenant_fingerprint=tenant.fingerprint,
            now=now, request_id=request_id, request_fingerprint=request_fingerprint,
            lead_effect_id=lead_effect_id, lead_effect_dispatcher=lead_effect_dispatcher,
            shown_service_options=(
                envelope.clarify_service_options
                or ((selected_service_id,) if selected_service_id is not None else ())
            ),
            shown_service_topic=(shown_topic or selected_topic),
            selected_service_id=(selected_service_id if selected_service_id is not None else None),
            selected_service_topic=(selected_topic if selected_service_id is not None else shown_topic),
            clear_active_service=(selected_service_id is None and shown_topic is not None),
            clear_situation=(
                (selected_topic if selected_service_id is not None else shown_topic) is not None
                and snapshot.state.situation_state is not None
                and snapshot.state.situation_state.topic_id
                != (selected_topic if selected_service_id is not None else shown_topic)
            ),
            dialogue_pairs=_next_d2_dialogue_pairs(
                snapshot=snapshot,
                safe_user_message=safe_user_message,
                selected_ui_ref=selected_ui_ref,
                response=response,
                turn=snapshot.current_turn_index,
                ttl_policy=ttl_policy,
                context=context,
            ),
            d2_shown_price_offer_refs=_next_d2_shown_price_offer_refs(
                snapshot=snapshot, price=None, context=context,
            ),
            clarify_task=_d2_clarify_task(envelope=envelope),
        )
    else:
        if envelope.route != "ANSWER" or understanding is None or not understanding.requests:
            raise ValueError("d2_experiment_single_price_required")
        offtopic = is_d2_offtopic_envelope(envelope)
        if offtopic:
            if context.retained_terminal_state not in {"none", "clarify", "spam_warn"}:
                raise ValueError("d2_experiment_terminal_session_unsupported")
            response = build_d2_offtopic_response(tenant, session_key=session_key)
            if not response.rendered_text.strip():
                raise ValueError("d2_experiment_offtopic_not_resolved")
            binding = bind_d1r_envelope_to_d2_context(envelope, context)
            focus = seed_d2_plan_focus(binding)
            return _commit_non_price_d2_turn(
                session_key=session_key,
                store=store,
                snapshot=snapshot,
                context=context,
                focus=focus,
                response=response,
                tenant_fingerprint=tenant.fingerprint,
                now=now,
                request_id=request_id,
                request_fingerprint=request_fingerprint,
                lead_effect_id=lead_effect_id,
                lead_effect_dispatcher=lead_effect_dispatcher,
            )
        booking_entry = None
        if lead_bridge:
            if not d2_lead_session_client_matches(session_key):
                raise ValueError("d2_lead_session_client_required")
            booking_entry = resolve_d2_booking_lead_entry(
                snapshot=tenant,
                session_key=session_key,
                understanding=understanding,
            )
        if booking_entry is not None:
            response = booking_entry.response
            if not response.rendered_text.strip():
                raise ValueError("d2_experiment_lead_not_resolved")
            binding = bind_d1r_envelope_to_d2_context(envelope, context)
            focus = seed_d2_plan_focus(binding)
            return _commit_non_price_d2_turn(
                session_key=session_key,
                store=store,
                snapshot=snapshot,
                context=context,
                focus=focus,
                response=response,
                tenant_fingerprint=tenant.fingerprint,
                now=now,
                request_id=request_id,
                request_fingerprint=request_fingerprint,
                lead_effect_id=lead_effect_id,
                lead_effect_dispatcher=lead_effect_dispatcher,
            )
        parts = understanding.requests
        part = parts[0]
        contact_parts = tuple(item for item in parts if item.kind == "contact")
        policy_parts = tuple(item for item in parts if item.kind == "clinic_policy")
        subjects_by_id = {item.subject_id: item for item in understanding.subjects}
        multi_part = _d2_multipart_shape_ok(parts=parts, subjects_by_id=subjects_by_id)
        clinic_policy = (
            len(parts) == 1
            and part.kind == "clinic_policy"
        )
        clinic_contact = (
            envelope.commercial_intent == "none"
            and len(parts) == 1
            and part.kind == "contact"
        )
        # Ordinary FullContext prose is the default. These narrow exceptions
        # are driven by typed IDs/statuses, never by a second pass over text.
        service_availability = (
            envelope.service_reference_status == "resolved"
            and envelope.requested_service_id is not None
            and envelope.requested_service_id in view.service_reference_catalog.inactive_service_ids
        )
        unknown_brand = (
            len(parts) == 1
            and part.kind in {"price", "content"}
            and part.brand_id is not None
            and part.brand_id not in view.brand_catalog.brands
        )
        unknown_term = envelope.service_reference_status == "unresolved"
        brand_policy = (
            build_d2_brand_policy_response(tenant, session_key=session_key, brand_id=part.brand_id)
            if part.brand_id is not None else None
        )
        directory_kind = None
        direct_promotion = (
            envelope.commercial_intent == "promotion"
            and envelope.promotion_scope in {"general", "service", "shown"}
            and len(parts) == 1
            and part.kind == "content"
        )
        direct_fact = (
            envelope.commercial_intent == "payment"
            and bool(envelope.references.direct_fact_ids)
            and 1 <= len(parts) <= 3
            and all(item.kind == "content" for item in parts)
        )
        content_lookup = (
            envelope.commercial_intent == "none"
            and 1 <= len(parts) <= 2
            and all(item.kind == "content" for item in parts)
        )
        if not (
            direct_promotion
            or direct_fact
            or content_lookup
            or multi_part
            or clinic_policy
            or clinic_contact
            or service_availability
            or unknown_brand
            or unknown_term
            or brand_policy is not None
            or directory_kind is not None
        ):
            if len(parts) != 1:
                raise ValueError("d2_experiment_single_price_required")
            if part.kind != "price":
                raise ValueError("d2_experiment_single_price_required")
            subject = subjects_by_id.get(part.subject_id) if part.subject_id else None
            shape_failures = _d2_supported_price_shape_failure_codes(part=part, subject=subject)
            if shape_failures:
                raise ValueError("d2_experiment_a08_shape_required:" + ",".join(shape_failures))
        elif direct_promotion and envelope.promotion_scope == "service" and part.service_id is None:
            raise ValueError("d2_experiment_promotion_service_required")
        # Clarify and spam_warn are soft; hard terminals remain unsupported on ordinary answers.
        if context.retained_terminal_state not in {"none", "clarify", "spam_warn"}:
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
            if (
                price_focus_clarify
                # A direct service ID is already sufficient for the
                # catalog-owned price lookup. Session binding deliberately
                # does not infer its topic from dialogue text or labels.
                or (part.kind == "price" and part.service_id is not None and part.topic_id is None)
                or multi_part
                or content_lookup
                or clinic_policy
                or clinic_contact
                or service_availability
                or unknown_brand
                or unknown_term
                or brand_policy is not None
                or directory_kind is not None
            ):
                # Independent content parts and typed special routes need no single-topic focus.
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
        elif clinic_policy:
            response = build_d2_clinic_policy_response(
                tenant,
                session_key=session_key,
                understanding=understanding,
            )
            price = None
            decision = None
        elif clinic_contact:
            response = build_d2_contact_response(
                tenant,
                session_key=session_key,
                contact_fields=tuple(part.contact_fields),
            )
            price = None
            decision = None
        elif service_availability:
            assert envelope.requested_service_id is not None
            response = build_d2_service_availability_response(
                tenant,
                session_key=session_key,
                service_id=envelope.requested_service_id,
            )
            price = None
            decision = None
        elif brand_policy is not None:
            response = brand_policy
            price = None
            decision = None
        elif unknown_brand or unknown_term:
            response = build_d2_unknown_reference_response(
                tenant,
                session_key=session_key,
            )
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
            # The common lower materializer owns free prose and price. Contacts
            # and policies enter its pre-resolver plan as exact tenant facts;
            # they never trigger a second render or UI projection.
            resolution_envelope = envelope
            exact_contact_blocks = []
            exact_contact_button = None
            exact_canonical_contact = None
            for contact_part in contact_parts:
                block, button, canonical_contact = build_d2_contact_fact_block(
                    tenant,
                    session_key=session_key,
                    request_id=contact_part.request_id,
                    contact_fields=tuple(contact_part.contact_fields),
                )
                exact_contact_blocks.append(block)
                if exact_contact_button is None:
                    exact_contact_button = button
                if exact_canonical_contact is None:
                    exact_canonical_contact = canonical_contact
            exact_policy_blocks = tuple(
                build_d2_clinic_policy_fact_block(
                    tenant,
                    session_key=session_key,
                    understanding=understanding,
                    request_id=policy_part.request_id,
                )
                for policy_part in policy_parts
            )
            if contact_parts or policy_parts:
                resolution_envelope = envelope.model_copy(
                    update={
                        "request_understanding": understanding.model_copy(
                            update={
                                "requests": tuple(
                                    item for item in parts
                                    if item.kind not in {"contact", "clinic_policy"}
                                )
                            }
                        )
                    }
                )
            response = resolve_d2_envelope_response(
                resolution_envelope,
                sources,
                as_of=now.date(),
                d2_plan_focus_seed=focus,
                common_route_direct_service_only=True,
                common_route_content_lookup=True,
                exact_contact_blocks=tuple(exact_contact_blocks),
                exact_policy_blocks=exact_policy_blocks,
                exact_contact_button=exact_contact_button,
                exact_canonical_contact=exact_canonical_contact,
                d2_request_order=tuple(item.request_id for item in parts),
            )
            price = response.resolved.d2_price_block
            decision = response.resolved.d2_price_scope_decision
    if admin_terminal:
        pass
    elif price_focus_clarify:
        if response.resolved.route != "CLARIFY" or not response.rendered_text.strip():
            raise ValueError("d2_experiment_focus_clarify_not_resolved")
    elif clinic_policy or clinic_contact or service_availability or brand_policy is not None or unknown_brand or unknown_term or directory_kind is not None:
        if not response.rendered_text.strip():
            raise ValueError("d2_experiment_directory_or_availability_not_resolved")
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
    elif (
        part.kind == "price"
        and part.brand_id is not None
        and price is None
        and response.resolved.d2_part_failure_blocks
        and response.rendered_text.strip()
    ):
        # Exact brand/service without a published offer is an honest gap.
        pass
    elif price is None or (part.service_id is None and decision is None) or not response.rendered_text.strip():
        raise ValueError("d2_experiment_price_not_resolved")
    turn = snapshot.current_turn_index
    # Persist only finalized facts. Hypothetical/overview/unknown must not wipe
    # a previously reported or corrected situation (D2-003).
    situation = snapshot.state.situation_state
    if (
        admin_terminal
        or price_focus_clarify
        or clinic_policy
        or clinic_contact
        or service_availability
        or unknown_brand
        or unknown_term
        or directory_kind is not None
    ):
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
    if admin_terminal or part is None:
        active_topic = snapshot.state.active_topic
        shown_options_snapshot = snapshot.state.shown_options_snapshot
    else:
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
        active_service=(
            PersistedActiveService(
                service_id=selected_service_id, provenance="explicit_current", set_at_turn=turn,
            ) if selected_service_id is not None else (
                PersistedActiveService(
                    service_id=part.service_id, provenance="explicit_current", set_at_turn=turn,
                )
                if part is not None and part.service_id is not None
                and active_topic is not None and focus.action == "resolve_topic"
                and focus.topic_id == active_topic.topic_id
                else (
                    snapshot.state.active_service
                    if (
                        active_topic is not None
                        and snapshot.state.active_topic is not None
                        and active_topic.topic_id == snapshot.state.active_topic.topic_id
                    ) else None
                )
            )
        ),
        active_topic=active_topic,
        situation_state=situation,
        shown_options_snapshot=shown_options_snapshot,
        dialogue_pairs=_next_d2_dialogue_pairs(
            snapshot=snapshot,
            safe_user_message=safe_user_message,
            selected_ui_ref=selected_ui_ref,
            response=response,
            turn=turn,
            ttl_policy=ttl_policy,
            context=context,
        ),
        d2_shown_price_offer_refs=_next_d2_shown_price_offer_refs(
            snapshot=snapshot, price=price, context=context,
        ),
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
        clarify_task=(
            _d2_clarify_task(envelope=envelope)
            if response.resolved.session_delta.clarify_pending
            else None
        ),
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
