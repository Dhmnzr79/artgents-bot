"""Safe read projection of the sole D2 store's completed results."""

from contracts.d2_session_context import D2ProjectedDialoguePair
from contracts.response_plan_session import D2DialogueReceiptRef, D2ShownPriceOfferRef
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


def _project_pair(ref, result, limit):
    resolved = result.response.resolved
    # Do not copy rendered_text: it also contains money, promotions and lead UI.
    # Code-owned financial text stays in the replay receipt, not ordinary memory.
    safe_prose = lambda text: mask_emails_in_text(mask_phones_in_text(text))
    by_request = {b.request_id: safe_prose(b.display_text)
        for b in resolved.information_blocks if b.publication == "model_prose"}
    # Authored reference text can contain amounts, so keep its typed identity only.
    # This fixed policy clarification has known nonfinancial provenance.
    from core.d2_snapshot_sources import _POLICY_CLARIFY
    reference_ids = {p.request_id for p in resolved.d2_request_parts
        if p.kind == "clarification"}
    by_request.update({b.request_id: safe_prose(b.display_text)
        for b in resolved.d2_exact_text_blocks if b.request_id in reference_ids
        and b.display_text == _POLICY_CLARIFY
        and not (b.policy_ids or b.requested_fact_ids or b.promo_fact_ids)})
    by_request.update({b.request_id: b.display_text for b in resolved.d2_contact_blocks})
    text = []
    for part in resolved.d2_request_parts:
        if part.kind == "price" and resolved.patient_text:
            text.append(safe_prose(resolved.patient_text))
        if part.request_id in by_request:
            text.append(by_request[part.request_id])
    if not resolved.d2_request_parts and resolved.patient_text:
        text.append(safe_prose(resolved.patient_text))
    if resolved.route == "ADMIN" and resolved.mode == "medical_terminal" and resolved.terminal_text:
        text.append(safe_prose(resolved.terminal_text))
    safe_text = "\n\n".join(dict.fromkeys(text))[:limit].strip()
    price_blocks = (*((resolved.d2_price_block,) if resolved.d2_price_block else ()),
        *resolved.d2_price_detail_blocks)
    offers = tuple({(row.source_client_id, row.offer_id, row.service_id):
        D2ShownPriceOfferRef(source_client_id=row.source_client_id,
            offer_id=row.offer_id, service_id=row.service_id)
        for block in price_blocks for row in block.rows}.values())
    return D2ProjectedDialoguePair(
        patient_text=ref.patient_text, selected_ui_ref=ref.selected_ui_ref,
        committed_at_turn=ref.committed_at_turn, assistant_text=safe_text,
        parts=resolved.d2_request_parts, price_scope=discussion_scope(resolved), offers=offers,
        detail_aspects=tuple(block.aspect for block in resolved.d2_price_detail_blocks),
        policy_ids=tuple(dict.fromkeys(i for b in (*resolved.d2_policy_blocks, *resolved.d2_exact_text_blocks) for i in b.policy_ids)),
        fact_ids=tuple(dict.fromkeys((
            *resolved.finalized_commercial_ids.requested_fact_ids,
            *resolved.finalized_commercial_ids.promo_fact_ids,
            *resolved.finalized_commercial_ids.amplifier_fact_ids,
            *(b.fact_id for b in resolved.requested_fact_blocks),
            *(i for b in resolved.d2_exact_text_blocks for i in (*b.requested_fact_ids, *b.promo_fact_ids))))),
    )


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
        pairs.append(_project_pair(ref, result, policy.history_text_max_chars))
    scope = None
    reference = snapshot.state.discussion_request_id
    if reference is not None:
        result = _receipt(store, key, reference, context.source_revision)
        scope = discussion_scope(result.response.resolved)
        if scope is None:
            raise ValueError("d2_discussion_receipt_scope_mismatch")
    ordinary = context.ordinary.model_copy(update={"dialogue_pairs": tuple(pairs), "discussion_scope": scope})
    return context.model_copy(update={"ordinary": ordinary})


def retain_discussion_reference(state, previous, context, resolved, request_id):
    """Contacts retain context; scoped tasks replace it, ambiguity clears it."""
    scope = discussion_scope(resolved)
    if scope is not None:
        reference = request_id
    elif resolved.response_scope != "clinic" or any(p.discussion_scope is not None for p in resolved.d2_request_parts):
        reference = None
    else:
        reference = previous.discussion_request_id if context.freshness == "fresh" else None
    return state.model_copy(update={"discussion_request_id": reference})
