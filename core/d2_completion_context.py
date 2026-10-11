"""Safe read projection of the sole D2 store's completed results."""

from contracts.d2_session_context import D2ProjectedDialoguePair
from contracts.response_plan_session import D2DialogueReceiptRef, D2ShownPriceOfferRef
from core.response_text_renderer import render_response_text
from core.user_text_privacy import mask_phones_in_text, mask_emails_in_text


def discussion_scope(resolved):
    """Read the finalized task, never infer a patient or choose among alternatives."""
    if resolved.response_scope == "mixed":
        return None
    scopes = [p.discussion_scope for p in resolved.d2_request_parts
        if p.discussion_scope is not None]
    if not scopes or not any(p.discussion_scope is not None and p.status in {"answered", "unavailable"} for p in resolved.d2_request_parts) or any(scope != scopes[0] for scope in scopes[1:]):
        return None
    return scopes[0]


def _receipt(store, key, request_id, revision, turn=None):
    result = store.read_completion(key, request_id)
    if result is None or result.committed_revision > revision or (
        turn is not None and result.context.source_turn_index + 1 != turn
    ):
        raise ValueError("d2_history_receipt_invalid")
    if result.context.session_key != key:
        raise ValueError("d2_history_receipt_owner_mismatch")
    return result


def _project_pair(ref, result):
    resolved = result.response.resolved
    # Read the same frozen publication as the widget; intake has explicit provenance.
    def safe(text):
        return mask_emails_in_text(mask_phones_in_text(text)) if text else text

    # Mask untrusted prose, not published clinic data (dates can resemble phones).
    public_plan = resolved.model_copy(update={
        "information_blocks": tuple(b.model_copy(update={"display_text": safe(b.display_text)})
            if b.publication == "model_prose" else b for b in resolved.information_blocks),
        "patient_text": safe(resolved.patient_text),
        "terminal_text": safe(resolved.terminal_text),
    })
    safe_text = render_response_text(public_plan, include_lead=False)
    price_blocks = (*((resolved.d2_price_block,) if resolved.d2_price_block else ()),
        *resolved.d2_price_detail_blocks)
    offers = tuple({(row.source_client_id, row.offer_id, row.service_id):
        D2ShownPriceOfferRef(source_client_id=row.source_client_id,
            offer_id=row.offer_id, service_id=row.service_id)
        for block in price_blocks for row in block.rows}.values())
    return D2ProjectedDialoguePair(
        patient_text=ref.patient_text, selected_ui_ref=ref.selected_ui_ref,
        committed_at_turn=ref.committed_at_turn, assistant_text=safe_text,
        parts=tuple(p for p in resolved.d2_request_parts if p.kind != "lead"), price_scope=discussion_scope(resolved), offers=offers,
        detail_aspects=tuple(block.aspect for block in resolved.d2_price_detail_blocks),
        policy_ids=tuple(dict.fromkeys(i for b in (*resolved.d2_policy_blocks, *resolved.d2_exact_text_blocks) for i in b.policy_ids)),
        fact_ids=tuple(dict.fromkeys((
            *resolved.finalized_commercial_ids.requested_fact_ids,
            *resolved.finalized_commercial_ids.promo_fact_ids,
            *resolved.finalized_commercial_ids.amplifier_fact_ids,
            *(b.fact_id for b in resolved.requested_fact_blocks),
            *(i for b in resolved.d2_exact_text_blocks for i in (*b.requested_fact_ids, *b.promo_fact_ids))))),
    )


def _published_offers(resolved):
    blocks = (*((resolved.d2_price_block,) if resolved.d2_price_block else ()),
        *resolved.d2_price_detail_blocks)
    return tuple({row.offer_id: D2ShownPriceOfferRef(
        source_client_id=row.source_client_id, offer_id=row.offer_id,
        service_id=row.service_id)
        for block in blocks for row in block.rows
        if not getattr(row, "missing", False)}.values())


def _current_offers(context, snapshot, store, scope):
    # The last completed result is the sole source; history is not a fallback.
    if scope is None or snapshot.state.clarify_pending:
        return ()
    latest = store.read_latest_completion(context.session_key)
    if latest is None:
        return ()
    if (latest.context.session_key != context.session_key
        or latest.committed_revision != context.source_revision
        or latest.context.source_turn_index + 1 != context.source_turn_index):
        raise ValueError("d2_latest_receipt_invalid")
    resolved = latest.response.resolved
    if resolved.response_scope == "mixed":
        return ()
    refs = _published_offers(resolved)
    has_price_result = any(p.kind in {"price", "price_detail", "price_reference", "price_clarification"}
        for p in resolved.d2_request_parts)
    if not refs and not has_price_result and latest.context.freshness == "fresh" and (
        latest.context.ordinary.discussion_scope == scope
    ):
        refs = latest.context.ordinary.d2_shown_price_offer_refs
    if len({r.offer_id for r in refs}) != len(refs):
        raise ValueError("d2_shown_price_offer_id_duplicate")
    if any(r.source_client_id != context.session_key.client_id for r in refs):
        raise ValueError("d2_shown_price_offer_client_mismatch")
    if scope.service_id is not None and any(r.service_id != scope.service_id for r in refs):
        raise ValueError("d2_shown_price_offer_scope_mismatch")
    return refs


def project_completed_dialogue(context, snapshot, store, policy):
    """TTL already authorized this read; projection never interprets user text."""
    if context.freshness != "fresh":
        return context
    key = context.session_key
    pairs = []
    for ref in snapshot.state.dialogue_pairs[-policy.history_pair_limit:]:
        if not isinstance(ref, D2DialogueReceiptRef):
            raise ValueError("d2_history_receipt_required")
        result = _receipt(store, key, ref.request_id, context.source_revision, ref.committed_at_turn)
        pairs.append(_project_pair(ref, result))
    scope = None
    reference = snapshot.state.discussion_request_id
    if reference is not None:
        result = _receipt(store, key, reference, context.source_revision)
        scope = discussion_scope(result.response.resolved)
        if scope is None:
            raise ValueError("d2_discussion_receipt_scope_mismatch")
    ordinary = context.ordinary.model_copy(update={"dialogue_pairs": tuple(pairs),
        "discussion_scope": scope,
        "d2_shown_price_offer_refs": _current_offers(context, snapshot, store, scope)})
    return context.model_copy(update={"ordinary": ordinary})


def retain_discussion_reference(state, previous, context, resolved, request_id):
    """Contacts retain context; scoped tasks replace it, ambiguity clears it."""
    scope = discussion_scope(resolved)
    if scope is not None:
        reference = request_id
    elif resolved.d2_request_parts and all(
        p.kind in {"contact", "clinic_policy", "clarification", "price_clarification"}
        or (p.source_results and all(s.source_ref.startswith("policy:") for s in p.source_results))
        for p in resolved.d2_request_parts
    ) and not any(p.discussion_scope is not None for p in resolved.d2_request_parts):
        reference = previous.discussion_request_id if context.freshness == "fresh" else None
    else:
        reference = None
    return state.model_copy(update={"discussion_request_id": reference})
