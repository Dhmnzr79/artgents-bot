"""S2-V0 direct A08 route: raw D1R -> typed D2 -> text/UI -> one store.

This is deliberately an internal experiment, not an HTTP adapter or the full
product. Unsupported inputs fail explicitly; there is no legacy fallback.
"""

from datetime import datetime
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
from core import d2_diagnostics as diagnostics
from core.d2_full_audit import full_audit, full_audit_exception

from contracts.d2_dialogue import (
    D2CompletedTurn, D2DialogueRecord, D2DialogueTurn, D2LeadEffect,
    D2LeadEffectDispatcher, D2ProviderInput, D2RawProvider, D2SelectedUiRef,
)
from contracts.d2_session_context import (
    D2SessionActivity, D2SessionTtlPolicy, D2SessionState, D2SessionSnapshot,
    D2_SESSION_SCHEMA_VERSION, empty_d2_session_snapshot,
)
from contracts.response_plan import D2PriceDetailUiAction, SessionKey
from contracts.d2_dialogue_result import (
    DiscussionScope, DiscussionVolume, D2DialogueResult, PriceOperation, ExplanationOperation, DetailOperation,
    ContactOperation, DoctorsOperation, PolicyOperation, CommercialOperation,
    ClarifiedOperation, PendingExplanationOperation,
    ServiceTarget, TopicTarget, UnresolvedTarget, ScopedOperation, OffTopicOperation,
)
from contracts.response_plan import (
    D2ExactTextBlock, D2ResolvedRequestPart, D2PartDeferredBlock,
    D2_CLARIFICATION_DEFERRAL_TEXT,
)
from contracts.response_plan_materialization import D2SelectedDocumentAction
from contracts.response_plan_session import (
    D2ShownPriceOfferRef, PersistedShownCommercialIds, D2DialogueReceiptRef,
)
from core.d2_dialogue_store import D2DialogueStore
from core.d2_completion_context import project_completed_dialogue, retain_discussion_reference, discussion_scope
from core.d2_lead_bridge import (
    apply_d2_lead_pause_ui,
    d2_paused_lead_profile_name,
    d2_lead_needs_pre_provider,
    d2_lead_session_client_matches,
    prepare_d2_pending_lead_answer,
    reconcile_d2_lead_pause,
    resolve_d2_booking_lead_entry,
    resolve_d2_lead_pre_provider,
)
from core.d2_session_context import project_d2_session_context
from core.d2_snapshot_sources import (
    build_d2_focus_clarify_response,
    build_d2_manual_contact_terminal_response,
    build_d2_snapshot_sources,
    build_d2_clinic_policy_response,
    build_d2_brand_policy_response,
    build_d2_service_availability_response,
    build_d2_unknown_reference_response,
    build_d2_unknown_brand_response,
    resolve_d2_clarify_service_topic,
    resolve_d2_selected_document_action,
    build_d2_document_task,
)
from core.d2_spam_gate import build_d2_spam_gate_response, is_d2_garbage_message
from core.d2_contacts_cta import build_d2_contact_fact_block
from core.d2_offtopic import build_d2_offtopic_response
from core.d2_directory import build_d2_directory_response
from core.d2_tenant_snapshot import build_d2_model_view, load_d2_tenant_snapshot
from core.one_call_envelope_protocol import (
    parse_production_envelope_json,
)
from core.response_plan_materialization import resolve_d2_operations
from core.user_text_privacy import provider_message_has_substance, provider_safe_user_text
from core.clinic_policy_resolver import resolve_clinic_policy_operations
from lead_interrupt import LEAD_PENDING_ANSWER_REF
from session import peek_lead_paused


@dataclass(frozen=True)
class _SelectedVolumePriceTask:
    """Price intent carried by a verified choice from one frozen completion."""

    source_request_id: str
    topic_id: str
    service_id: str | None
    brand_id: str | None
    extent: str


def _request_fingerprint(*, session_key: SessionKey, user_message: str) -> str:
    """Store a non-reversible request identity, never the raw patient message."""
    source = "\x1f".join((session_key.client_id, session_key.sid, user_message))
    return sha256(source.encode("utf-8")).hexdigest()


def _turn_from_completion(completion: D2CompletedTurn, *, idempotent_replay: bool) -> D2DialogueTurn:
    return D2DialogueTurn(
        response=completion.response,
        context=completion.context,
        committed_revision=completion.committed_revision,
        request_id=completion.request_id,
        idempotent_replay=idempotent_replay,
        lead_effect=completion.lead_effect,
    )


def _shown_secondary_ref_ids(response) -> tuple[str, ...]:
    ui = response.ui_projection
    shown = [ui.video.video_id] if ui.video is not None else []
    price_refs = {item.reply_id for item in response.resolved.ui_plan.price_detail_actions}
    shown.extend(item.reply_id for item in ui.quick_replies if item.reply_id not in price_refs)
    return tuple(shown)


def _bounded_d2_text(value: str, *, limit: int) -> str:
    """Keep only bounded, provider-safe prose in the D2 dialogue memory."""
    return value.strip()[:limit].strip()


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


def _apply_lead_pause_without_detail_actions(response):
    # Lead resume/cancel owns the sole navigation channel while paused.
    # Drop the private action map together with the visible detail replies.
    ui = response.resolved.ui_plan
    if ui.price_detail_actions:
        resolved = response.resolved.model_copy(update={
            "ui_plan": ui.model_copy(update={"price_detail_actions": ()}),
        })
        response = replace(response, resolved=resolved)
    return apply_d2_lead_pause_ui(response)


def _current_d2_shown_price_offer_refs(context) -> tuple[D2ShownPriceOfferRef, ...]:
    if context.freshness != "fresh":
        return ()
    refs = context.ordinary.d2_shown_price_offer_refs
    active_service = context.ordinary.discussion_scope
    if active_service is not None and any(
        active_service.service_id is not None and ref.service_id != active_service.service_id for ref in refs
    ):
        return ()
    return refs


def _volume_price_task(action: _SelectedVolumePriceTask) -> D2DialogueResult:
    target = ServiceTarget(type="service", id=action.service_id) if action.service_id else TopicTarget(type="topic", id=action.topic_id)
    return D2DialogueResult(outcome="dialogue", blocks=(PriceOperation(
        request_id="r1", kind="price", target=target, brand_id=action.brand_id,
        volume=DiscussionVolume(
            extent=action.extent, tooth_count=1 if action.extent == "one_tooth" else None,
            jaw="unknown",
        ),
    ),))


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
    full_audit(
        "turn_input", session_key=session_key, request_id=effective_request_id,
        user_message=user_message, lead_ui_ref=lead_ui_ref,
        ui_revision=ui_revision, situation_action=situation_action,
    )
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
    diagnostics.stage("reserve")
    reservation = store.reserve_request(
        session_key, request_id=effective_request_id, request_fingerprint=fingerprint,
    )
    full_audit("reservation", is_replay=reservation.is_replay)
    if reservation.is_replay:
        diagnostics.replayed()
        full_audit("replay", completion=reservation.completed)
        latest = store.read_latest_completion(session_key)
        if (
            latest is not None
            and latest.request_id == reservation.completed.request_id
            and latest.committed_revision == reservation.completed.committed_revision
        ):
            reconcile_d2_lead_pause(session_key, reservation.completed)
        return _turn_from_completion(reservation.completed, idempotent_replay=True)
    try:
        diagnostics.stage("snapshot")
        tenant = load_d2_tenant_snapshot(session_key.client_id, clients_root=clients_root)
        diagnostics.stage("state_read")
        previous = store.read(session_key)
        if previous and previous.tenant_fingerprint != tenant.fingerprint:
            raise ValueError("d2_experiment_tenant_changed")
        early_snapshot = (
            D2SessionSnapshot(state=previous.state, exists_in_store=True)
            if previous else empty_d2_session_snapshot(session_key)
        )
        early_context = project_d2_session_context(
            early_snapshot,
            expected_session_key=session_key,
            activity=previous.activity if previous else None,
            policy=ttl_policy,
            now=now,
        )
        full_audit(
            "session_before", record=previous, context=early_context,
            tenant_fingerprint=tenant.fingerprint,
        )
        if lead_bridge and d2_lead_session_client_matches(session_key):
            reconcile_d2_lead_pause(session_key, store.read_latest_completion(session_key))
        lead_paused = bool(
            lead_bridge and d2_lead_session_client_matches(session_key)
            and peek_lead_paused(session_key.sid)
        )
        diagnostics.stage("binding")
        selected_ui_ref: D2SelectedUiRef | None = None
        selected_document_action: D2SelectedDocumentAction | None = None
        selected_price_detail_action: D2PriceDetailUiAction | None = None
        selected_volume_price_task: _SelectedVolumePriceTask | None = None
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
                    selected_price_detail_action = next(
                        (item for item in shown.response.resolved.ui_plan.price_detail_actions
                         if item.reply_id == reply.reply_id), None,
                    )
                    if selected_price_detail_action is None:
                        selected_document_action = resolve_d2_selected_document_action(
                            tenant, reply_id=reply.reply_id,
                            source_revision=ui_revision,
                            shown_source_content_ref=shown.response.resolved.ui_plan.source_content_ref,
                        )
                    if selected_document_action is None and selected_price_detail_action is None:
                        source = shown.response.resolved.d2_price_scope_decision
                        if source is not None:
                            choice = next((
                                item for item in source.volume_choices
                                if item.candidate.reply_id == reply.reply_id
                                and item.candidate.source_client_id == session_key.client_id
                            ), None)
                            if choice is not None:
                                source_part = next((
                                    item for item in shown.response.resolved.d2_request_parts
                                    if item.request_id == source.source_request_id
                                    and item.kind == "price" and item.status == "answered"
                                    and item.topic_id == source.topic_id
                                    and item.service_id == source.service_id
                                ), None)
                                if source_part is None:
                                    raise ValueError("d2_ui_volume_price_task_missing")
                                selected_volume_price_task = _SelectedVolumePriceTask(
                                    source_request_id=source.source_request_id,
                                    topic_id=source.topic_id,
                                    service_id=source.service_id,
                                    brand_id=source.brand_id,
                                    extent=choice.extent,
                                )
        full_audit(
            "ui_binding", effective_ref=lead_ui_ref,
            selected_ui_ref=selected_ui_ref,
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
        pending_answer = None
        if lead_ui_ref == LEAD_PENDING_ANSWER_REF:
            pending_answer = prepare_d2_pending_lead_answer(session_key)
        lead_pause_response = lead_paused or pending_answer is not None
        lead_gate = bool(
            lead_bridge
            or session_matched
            or (situation_action or "").strip()
            or (lead_ui_ref or "").strip()
        )
        if pending_answer is None and lead_gate and d2_lead_needs_pre_provider(
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
        # D2-040: one authored chance, then hard-stop. Medical ends one turn only.
        if (
            selected_ui_ref is None
            and not (lead_ui_ref or "").startswith("lead:")
            and not lead_pause_response
            and is_d2_garbage_message(user_message)
            and early_context.retained_terminal_state in {
            "none",
            "clarify",
            "spam_warn",
            "medical_terminal",
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
        safe_user_message = (
            pending_answer.safe_question
            if pending_answer is not None
            else provider_safe_user_text(
                user_message,
                profile_name=(d2_paused_lead_profile_name(session_key) if lead_paused else ""),
            )
        )
        full_audit("effective_input", provider_safe_user_message=safe_user_message)
        if (
            selected_ui_ref is None
            and not provider_message_has_substance(
                safe_user_message, raw_source=(user_message or safe_user_message),
                reject_lone_personal_name=lead_paused,
            )
        ):
            store.abandon_request(
                session_key, request_id=effective_request_id, request_fingerprint=fingerprint,
            )
            raise ValueError("d2_provider_input_privacy_only")
        turn = _run_reserved_d2_dialogue_turn(
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
            lead_pause_response=lead_pause_response,
            selected_ui_ref=selected_ui_ref,
            selected_document_action=selected_document_action,
            selected_price_detail_action=selected_price_detail_action,
            selected_volume_price_task=selected_volume_price_task,
            selected_service_id=(
                lead_ui_ref.removeprefix("service:")
                if lead_ui_ref and lead_ui_ref.startswith("service:") and ui_revision is not None
                else None
            ),
        )
        if lead_pause_response:
            reconcile_d2_lead_pause(session_key, store.read_latest_completion(session_key))
        return turn
    except Exception as exc:
        diagnostics.failure(exc)
        full_audit_exception("dialogue_turn", exc)
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
    diagnostics.stage("materialize")
    response = build_d2_spam_gate_response(tenant, session_key=session_key, kind=kind)
    if response.resolved.route != "ADMIN" or not response.rendered_text.strip():
        raise ValueError("d2_experiment_spam_gate_not_resolved")
    return _commit_non_price_d2_turn(
        session_key=session_key,
        store=store,
        snapshot=snapshot,
        context=context,
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
    diagnostics.stage("snapshot")
    tenant = load_d2_tenant_snapshot(session_key.client_id, clients_root=clients_root)
    diagnostics.stage("state_read")
    previous = store.read(session_key)
    if previous and previous.tenant_fingerprint != tenant.fingerprint:
        raise ValueError("d2_experiment_tenant_changed")
    snapshot = (
        D2SessionSnapshot(state=previous.state, exists_in_store=True)
        if previous else empty_d2_session_snapshot(session_key)
    )
    context = project_d2_session_context(
        snapshot, expected_session_key=session_key,
        activity=previous.activity if previous else None, policy=ttl_policy, now=now,
    )
    diagnostics.stage("materialize")
    bridge = resolve_d2_lead_pre_provider(
        snapshot=tenant,
        session_key=session_key,
        user_message=user_message,
        situation_action=situation_action,
        lead_ui_ref=lead_ui_ref,
        published_revision=snapshot.state.revision + 1,
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
    return _commit_non_price_d2_turn(
        session_key=session_key,
        store=store,
        snapshot=snapshot,
        context=context,
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
    response,
    tenant_fingerprint: str,
    now: datetime,
    request_id: str,
    request_fingerprint: str,
    lead_effect_id: str | None,
    lead_effect_dispatcher: D2LeadEffectDispatcher | None,
    clarify_task: ClarifiedOperation | None = None,
    prepared_state=None, safe_user_message=None, selected_ui_ref=None, ttl_policy=None,
    lead_pause_response: bool = False,
) -> D2DialogueTurn:
    """Commit a result and its receipt references in the sole D2 store."""
    if lead_pause_response:
        response = _apply_lead_pause_without_detail_actions(response)
    full_audit("materialized_response", response=response, branch="non_price")
    diagnostics.stage("state_build")
    turn = snapshot.current_turn_index
    state = D2SessionState(
        schema_version=D2_SESSION_SCHEMA_VERSION, session_key=session_key,
        revision=snapshot.state.revision + 1, last_committed_turn_index=turn,
        dialogue_pairs=snapshot.state.dialogue_pairs if context.freshness == "fresh" else (),
        d2_shown_price_offer_refs=context.ordinary.d2_shown_price_offer_refs,
        accumulated_shown_ids=context.retained_shown_ids.model_copy(update={
            "secondary_ref_ids": tuple(dict.fromkeys((
                *context.retained_shown_ids.secondary_ref_ids, *_shown_secondary_ref_ids(response),
            ))),
        }),
        terminal_state=response.resolved.session_delta.terminal_state,
        clarify_pending=response.resolved.session_delta.clarify_pending,
        clarify_task=(
            clarify_task if response.resolved.session_delta.clarify_pending else None
        ),
    )
    if prepared_state is not None:
        state = prepared_state
    if ttl_policy is not None:
        refs = snapshot.state.dialogue_pairs if context.freshness == "fresh" else ()
        if (response.resolved.route in {"ANSWER", "CLARIFY"}
            or (response.resolved.route == "ADMIN" and response.resolved.mode == "medical_terminal")) and (selected_ui_ref is not None or safe_user_message):
            ref = D2DialogueReceiptRef(request_id=request_id,
                patient_text=_bounded_d2_text(safe_user_message, limit=ttl_policy.history_text_max_chars) if selected_ui_ref is None else None,
                selected_ui_ref=selected_ui_ref, committed_at_turn=turn)
            refs = (*refs, ref)[-ttl_policy.history_pair_limit:]
        state = state.model_copy(update={"dialogue_pairs": refs})
        state = retain_discussion_reference(state, snapshot.state, context, response.resolved, request_id)
    initial_effect = (
        D2LeadEffect(effect_id=lead_effect_id, status="pending")
        if lead_effect_id is not None else D2LeadEffect()
    )
    completion = D2CompletedTurn(
        request_id=request_id,
        request_fingerprint=request_fingerprint,
        response=response,
        context=context,
        committed_revision=state.revision,
        lead_effect=initial_effect,
    )
    full_audit("commit_intent", state=state, completion=completion, branch="non_price")
    diagnostics.stage("commit")
    store.complete(D2DialogueRecord(
        state=state, activity=D2SessionActivity(session_key=session_key, last_user_turn_at=now),
        tenant_fingerprint=tenant_fingerprint,
    ), expected_revision=snapshot.state.revision, completion=completion)
    diagnostics.committed()
    full_audit("commit_confirmed", state=state, completion=completion, branch="non_price")
    if lead_effect_dispatcher is not None and lead_effect_id is not None:
        diagnostics.stage("effect")
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
        full_audit("effect_result", status=effect_status, completion=completion)
    turn_result = _turn_from_completion(completion, idempotent_replay=False)
    full_audit("turn_return", turn=turn_result)
    return turn_result


def _run_reserved_d2_dialogue_turn(
    *, session_key: SessionKey, safe_user_message: str, provider: D2RawProvider,
    clients_root: Path, store: D2DialogueStore, now: datetime,
    ttl_policy: D2SessionTtlPolicy, request_id: str, request_fingerprint: str,
    lead_effect_id: str | None, lead_effect_dispatcher: D2LeadEffectDispatcher | None,
    lead_bridge: bool = False,
    lead_pause_response: bool = False,
    selected_ui_ref: D2SelectedUiRef | None = None,
    selected_document_action: D2SelectedDocumentAction | None = None,
    selected_price_detail_action: D2PriceDetailUiAction | None = None,
    selected_volume_price_task: _SelectedVolumePriceTask | None = None,
    selected_service_id: str | None = None,
) -> D2DialogueTurn:
    """Build a final result only after ``reserve_request`` made this turn owner."""
    diagnostics.stage("snapshot")
    tenant = load_d2_tenant_snapshot(session_key.client_id, clients_root=clients_root)
    view = build_d2_model_view(tenant)
    diagnostics.stage("state_read")
    previous = store.read(session_key)
    if previous and previous.tenant_fingerprint != tenant.fingerprint:
        raise ValueError("d2_experiment_tenant_changed")
    snapshot = (D2SessionSnapshot(state=previous.state, exists_in_store=True)
                if previous else empty_d2_session_snapshot(session_key))
    context = project_d2_session_context(
        snapshot, expected_session_key=session_key,
        activity=previous.activity if previous else None, policy=ttl_policy, now=now,
    )
    context = project_completed_dialogue(context, snapshot, store, ttl_policy)
    full_audit(
        "model_context", record=previous, state=snapshot.state,
        context=context, tenant_fingerprint=tenant.fingerprint,
    )
    known_task = None
    if selected_service_id is not None:
        pending = context.ordinary.clarify_task
        if pending is None or pending.clarification.missing != "service":
            raise ValueError("d2_ui_service_task_missing")
        if selected_service_id not in view.active_service_catalog.active_service_ids:
            raise ValueError("d2_ui_service_selection_mismatch")
        # A verified click completes the task as a regular operation,
        # rather than retaining the narrower unresolved-price subtype.
        known_task = D2DialogueResult.model_validate({"outcome": "dialogue", "blocks": [{
            **pending.model_dump(exclude={"clarification"}),
            "target": {"type": "service", "id": selected_service_id},
        }]})
    elif selected_volume_price_task is not None:
        known_task = _volume_price_task(selected_volume_price_task)
    elif selected_document_action is not None:
        known_task = build_d2_document_task(tenant, selected_document_action)
    elif selected_price_detail_action is not None:
        known_task = D2DialogueResult(outcome="dialogue", blocks=(DetailOperation(
            request_id="r1", kind="price_detail",
            target=(ServiceTarget(type="service", id=selected_price_detail_action.service_id)
                    if selected_price_detail_action.service_id else None),
            price_detail_aspect=selected_price_detail_action.aspect,
        ),))
    if known_task is not None and (selected_document_action is not None or selected_price_detail_action is not None):
        shown = store.read_latest_completion(session_key)
        source_parts = [p for p in shown.response.resolved.d2_request_parts
            if p.status == "answered" and (
                (selected_document_action is not None and p.kind == "content"
                 and p.content_ref == selected_document_action.content_ref)
                or (selected_price_detail_action is not None and p.kind in {"price", "price_detail"}))]
        if source_parts and source_parts[0].discussion_scope is not None and all(
            part.discussion_scope == source_parts[0].discussion_scope
            for part in source_parts
        ):
            descriptor = source_parts[0].discussion_scope
            # Execute the scope captured by the shown source, not a semantic carry.
            task = known_task.blocks[0].model_copy(update={"target": descriptor.target, "volume": descriptor.volume, "brand_id": descriptor.brand_id})
            known_task = D2DialogueResult.model_validate({"outcome": "dialogue", "blocks": [task.model_dump()]})
    needs_explanation = known_task is not None and any(isinstance(b, PendingExplanationOperation) for b in known_task.blocks)
    if known_task is not None and not needs_explanation:
        result = known_task
    else:
        provider_input = D2ProviderInput(
            user_message=safe_user_message, model_view=view, context=context,
            selected_ui_ref=selected_ui_ref, selected_document_action=selected_document_action,
            known_task=known_task,
        )
        full_audit("provider_input", provider_input=provider_input)
        diagnostics.stage("provider")
        raw = provider.generate(provider_input)
        full_audit("raw_model_response", raw=raw)
        diagnostics.stage("parse")
        result = parse_production_envelope_json(
            raw, active_service_catalog=view.active_service_catalog,
            service_reference_catalog=view.service_reference_catalog,
            commercial_fact_catalog=view.commercial_fact_catalog,
            known_task=known_task, d2_contract=True,
        )
    full_audit("parsed_result", result=result)
    commit_args = dict(
        session_key=session_key, store=store, snapshot=snapshot, context=context,
        tenant_fingerprint=tenant.fingerprint, now=now,
        request_id=request_id, request_fingerprint=request_fingerprint,
        lead_effect_id=lead_effect_id, lead_effect_dispatcher=lead_effect_dispatcher,
        lead_pause_response=lead_pause_response, safe_user_message=safe_user_message,
        selected_ui_ref=selected_ui_ref, ttl_policy=ttl_policy,
    )
    if result.outcome == "admin":
        if context.retained_terminal_state not in {"none", "clarify", "admin", "medical_terminal", "spam_warn"}:
            raise ValueError("d2_experiment_terminal_session_unsupported")
        response = build_d2_manual_contact_terminal_response(tenant, session_key=session_key)
        return _commit_non_price_d2_turn(response=response, **commit_args)
    if context.retained_terminal_state not in {"none", "clarify", "spam_warn", "medical_terminal"}:
        raise ValueError("d2_experiment_terminal_session_unsupported")
    booking_blocks = tuple(block for block in result.blocks if block.kind == "booking")
    if lead_bridge:
        if not d2_lead_session_client_matches(session_key):
            raise ValueError("d2_lead_session_client_required")
        if booking_blocks and len(booking_blocks) == len(result.blocks):
            booking = resolve_d2_booking_lead_entry(
                snapshot=tenant, session_key=session_key, operations=booking_blocks,
            )
            return _commit_non_price_d2_turn(response=booking.response, **commit_args)

    operations, contact_blocks, policy_blocks = [], [], []
    exact_text, exact_parts, extra_ui, deferred = [], [], [], []
    exact_deferred = []
    pending = None
    first_price_seen = False
    contact_button = canonical_contact = None
    commercial_operations = []
    directory_cta = None
    suppress_forbidden_booking_cta = False
    for block in result.blocks:
        if block.kind == "booking":
            continue
        is_price = isinstance(block, PriceOperation)
        if is_price and first_price_seen:
            deferred.append(block)
            continue
        first_price_seen |= is_price
        if isinstance(block, DoctorsOperation):
            answer = build_d2_directory_response(
                tenant, session_key=session_key, kind="doctors_for_service",
                service_id=block.service_id, as_of=now.date(),
            )
            exact_text.append(D2ExactTextBlock(request_id=block.request_id,
                source_client_id=session_key.client_id, display_text=answer.rendered_text))
            exact_parts.append(D2ResolvedRequestPart(request_id=block.request_id,
                kind="reference", status="answered", scope="service", service_id=block.service_id,
                discussion_scope=DiscussionScope(target=block.target),
                topic_id=resolve_d2_clarify_service_topic(tenant, (block.service_id,))))
            directory_cta = directory_cta or next(
                (button for button in answer.resolved.ui_plan.buttons if button.action_kind == "cta"), None,
            )
            continue
        if isinstance(block, OffTopicOperation):
            answer = build_d2_offtopic_response(tenant, session_key=session_key)
            exact_text.append(D2ExactTextBlock(request_id=block.request_id,
                source_client_id=session_key.client_id, display_text=answer.rendered_text))
            exact_parts.append(D2ResolvedRequestPart(request_id=block.request_id,
                kind="reference", status="answered", scope="clinic"))
            continue
        clarification = getattr(block, "clarification", None)
        if clarification is not None:
            # For price, only unresolved service/term tasks reach this branch.
            # Content/detail also keep their agreed parameter clarifications.
            if pending is not None:
                if is_price:
                    deferred.append(block)
                else:
                    exact_parts.append(D2ResolvedRequestPart(request_id=block.request_id,
                        kind="clarification", status="deferred", scope="clinic"))
                    exact_deferred.append(D2PartDeferredBlock(request_id=block.request_id,
                        source_client_id=session_key.client_id, display_text=D2_CLARIFICATION_DEFERRAL_TEXT))
                continue
            pending = block
            answer = build_d2_focus_clarify_response(
                tenant, session_key=session_key, clarify_axis=clarification.missing,
                service_options=clarification.choices if clarification.missing == "service" else None,
            )
            exact_text.append(D2ExactTextBlock(request_id=block.request_id,
                source_client_id=session_key.client_id, display_text=answer.rendered_text))
            exact_parts.append(D2ResolvedRequestPart(request_id=block.request_id,
                kind="price_clarification" if is_price else "clarification", status="answered", scope="clinic"))
            extra_ui.extend(answer.resolved.ui_plan.quick_replies)
            continue
        if isinstance(block, ContactOperation):
            text, button, canonical = build_d2_contact_fact_block(
                tenant, session_key=session_key, request_id=block.request_id,
                contact_fields=block.contact_fields, contact_branch_id=block.contact_branch_id,
            )
            contact_blocks.append(text)
            contact_button = contact_button or button
            canonical_contact = canonical_contact or canonical
            continue
        if isinstance(block, PolicyOperation):
            policy = resolve_clinic_policy_operations(client_id=session_key.client_id,
                operations=(block,))
            suppress_forbidden_booking_cta |= policy.suppress_forbidden_booking_cta
            answer = build_d2_clinic_policy_response(
                tenant, session_key=session_key, request=block,
            )
            # Rules have already been applied to this local operation. The final
            # renderer receives code-owned text, not a second route decision.
            exact_text.append(D2ExactTextBlock(request_id=block.request_id,
                source_client_id=session_key.client_id, display_text=answer.rendered_text,
                policy_ids=tuple(dict.fromkeys(d.policy_key for d in policy.decisions
                    if d.outcome == "allowed_by_known_rules" and d.policy_key))))
            exact_parts.append(D2ResolvedRequestPart(request_id=block.request_id,
                kind="reference", status="answered", scope="clinic"))
            continue
        if isinstance(block, CommercialOperation):
            commercial_operations.append(block)
            continue
        if isinstance(block, PriceOperation):
            policy = resolve_clinic_policy_operations(client_id=session_key.client_id,
                operations=(block,))
            suppress_forbidden_booking_cta |= policy.suppress_forbidden_booking_cta
            blocked = tuple(d.policy_key for d in policy.decisions if d.outcome == "blocked" and d.policy_key)
            if blocked:
                rule = PolicyOperation(request_id=block.request_id, kind="clinic_policy",
                    policy_ids=blocked, age_group=block.age_group, context=block.context)
                answer = build_d2_clinic_policy_response(tenant, session_key=session_key,
                    request=rule)
                exact_text.append(D2ExactTextBlock(request_id=block.request_id,
                    source_client_id=session_key.client_id, display_text=answer.rendered_text,
                    policy_ids=blocked))
                exact_parts.append(D2ResolvedRequestPart(request_id=block.request_id,
                    kind="price_reference", status="answered", scope="clinic"))
                continue
        target = getattr(block, "target", None)
        brand = getattr(block, "brand_id", None)
        reference_response = None
        if brand is not None and brand not in view.brand_catalog.brands:
            reference_response = build_d2_unknown_brand_response(tenant, session_key=session_key, brand_id=brand)
        elif isinstance(target, UnresolvedTarget):
            reference_response = build_d2_unknown_reference_response(tenant, session_key=session_key)
        elif isinstance(target, ServiceTarget) and target.id in view.service_reference_catalog.inactive_service_ids:
            reference_response = build_d2_service_availability_response(tenant, session_key=session_key, service_id=target.id)
        elif brand is not None:
            reference_response = build_d2_brand_policy_response(tenant, session_key=session_key, brand_id=brand)
        if reference_response is not None:
            exact_text.append(D2ExactTextBlock(request_id=block.request_id,
                source_client_id=session_key.client_id, display_text=reference_response.rendered_text))
            exact_parts.append(D2ResolvedRequestPart(request_id=block.request_id,
                kind="price_reference" if is_price else "reference", status="answered", scope="clinic"))
            # These producers publish an exact availability/reference fact,
            # with no service-choice UI. Only explicit clarification owns a task.
            continue
        if isinstance(block, PriceOperation) and block.target is None:
            raise ValueError("d2_price_target_required")
        if isinstance(block, PriceOperation) and selected_volume_price_task is not None and selected_volume_price_task.extent == "unknown":
            exact_text.append(D2ExactTextBlock(request_id=block.request_id,
                source_client_id=session_key.client_id,
                display_text="Ничего страшного. На консультации врач поможет разобраться с объёмом лечения."))
            exact_parts.append(D2ResolvedRequestPart(request_id=block.request_id,
                kind="reference", status="answered",
                scope="service" if isinstance(block.target, ServiceTarget) else "topic",
                service_id=block.service_id, topic_id=block.topic_id, brand_id=block.brand_id,
                discussion_scope=DiscussionScope(target=block.target, volume=block.volume, brand_id=block.brand_id)))
            continue
        operations.append(block)
    sources = build_d2_snapshot_sources(
        tenant, model_view=view, operations=tuple(operations), session_key=session_key,
        shown_promo_fact_ids=context.retained_shown_ids.promo_fact_ids,
        shown_secondary_ref_ids=context.retained_shown_ids.secondary_ref_ids,
    )
    render_order = tuple(b.request_id for b in result.blocks if b.kind != "booking")
    response = resolve_d2_operations(
        tuple(operations), sources, as_of=now.date(),
        common_route_content_lookup=bool(operations) and all(isinstance(p, ExplanationOperation) for p in operations),
        exact_contact_blocks=tuple(contact_blocks), exact_policy_blocks=tuple(policy_blocks),
        exact_contact_button=contact_button, exact_canonical_contact=canonical_contact,
        exact_text_blocks=tuple(exact_text), exact_parts=tuple(exact_parts),
        extra_ui=tuple(extra_ui), deferred_price_parts=tuple(deferred),
        exact_deferred_blocks=tuple(exact_deferred),
        d2_request_order=render_order,
        shown_price_offer_refs=_current_d2_shown_price_offer_refs(context),
        selected_price_detail_action=selected_price_detail_action,
        commercial_operations=tuple(commercial_operations),
        directory_cta=directory_cta,
        suppress_forbidden_booking_cta=(suppress_forbidden_booking_cta
            or all(isinstance(block, OffTopicOperation) for block in result.blocks)),
    )
    if lead_bridge and booking_blocks:
        # Resolve siblings before the existing lead owner mutates intake state.
        booking = resolve_d2_booking_lead_entry(
            snapshot=tenant, session_key=session_key,
            operations=tuple(p for p in result.blocks if p.kind in {"booking", "price", "clinic_policy"}),
        )
        booking_part = D2ResolvedRequestPart(request_id=booking_blocks[0].request_id,
            kind="clarification" if booking.kind == "unclear" else "reference",
            status="answered", scope="clinic")
        values = response.resolved.model_dump()
        values.update(
            attribution_kind=booking.response.resolved.attribution_kind,
            d2_request_parts=(*response.resolved.d2_request_parts, booking_part),
            d2_exact_text_blocks=(*response.resolved.d2_exact_text_blocks,
                D2ExactTextBlock(request_id=booking_part.request_id,
                    source_client_id=session_key.client_id, display_text=booking.response.rendered_text)),
            ui_plan=booking.response.resolved.ui_plan,
            textual_cta_block=None,
            d2_result_status=("degraded" if any(part.status != "answered"
                for part in response.resolved.d2_request_parts) else "complete"),
        )
        resolved = type(response.resolved).model_validate(values)
        from core.response_text_renderer import render_response_text
        from core.response_ui_projection import project_response_ui
        response = replace(response, resolved=resolved,
            rendered_text=render_response_text(resolved), ui_projection=project_response_ui(resolved))
    if not response.rendered_text.strip():
        raise ValueError("d2_empty_completed_answer")
    if lead_pause_response:
        response = _apply_lead_pause_without_detail_actions(response)
        pending = None
    turn = snapshot.current_turn_index
    delta = response.resolved.session_delta
    price_operations_by_id = {p.request_id: p for p in operations if isinstance(p, PriceOperation)}
    parts = tuple(part.model_copy(update={
        "brand_id": price_operations_by_id[part.request_id].brand_id,
        "topic_id": part.topic_id or (resolve_d2_clarify_service_topic(tenant, (part.service_id,)) if part.service_id else None),
    }) if part.kind == "price" and part.request_id in price_operations_by_id else part
        for part in response.resolved.d2_request_parts)
    # Freeze proven source IDs, without changing published text or repricing.
    enriched = type(response.resolved).model_validate({**response.resolved.model_dump(), "d2_request_parts": parts})
    response = replace(response, resolved=enriched)
    price = response.resolved.d2_price_block
    scope = response.resolved.response_scope
    current_discussion = discussion_scope(response.resolved)
    refs = _next_d2_shown_price_offer_refs(snapshot=snapshot, price=price, context=context)
    if response.resolved.d2_price_detail_blocks:
        refs = tuple({(r.source_client_id, r.offer_id, r.service_id):
            D2ShownPriceOfferRef(source_client_id=r.source_client_id, offer_id=r.offer_id, service_id=r.service_id)
            for block in (*((price,) if price else ()), *response.resolved.d2_price_detail_blocks)
            for r in block.rows}.values())
    if pending is not None or scope == "mixed":
        refs = ()
    elif price is None and not response.resolved.d2_price_detail_blocks:
        if current_discussion is not None and current_discussion != context.ordinary.discussion_scope:
            refs = ()
    accumulated = context.retained_shown_ids.model_copy(update={
        "requested_fact_ids": tuple(dict.fromkeys((*context.retained_shown_ids.requested_fact_ids, *delta.shown_requested_fact_ids))),
        "promo_fact_ids": tuple(dict.fromkeys((*context.retained_shown_ids.promo_fact_ids, *delta.shown_promo_ids))),
        "price_offer_ids": tuple(dict.fromkeys((*context.retained_shown_ids.price_offer_ids, *(r.offer_id for r in price.rows)))) if price else context.retained_shown_ids.price_offer_ids,
        "secondary_ref_ids": tuple(dict.fromkeys((
            *context.retained_shown_ids.secondary_ref_ids, *_shown_secondary_ref_ids(response),
            *((f"price_detail_clicked:{selected_price_detail_action.service_id}:{selected_price_detail_action.aspect}",)
              if selected_price_detail_action is not None else ()),
        ))),
    })
    state = D2SessionState(
        schema_version=D2_SESSION_SCHEMA_VERSION, session_key=session_key,
        revision=snapshot.state.revision+1, last_committed_turn_index=turn,
        d2_shown_price_offer_refs=refs,
        dialogue_pairs=(),
        accumulated_shown_ids=accumulated, terminal_state=delta.terminal_state,
        clarify_pending=pending is not None, clarify_task=pending,
    )
    return _commit_non_price_d2_turn(response=response, prepared_state=state, **commit_args)
