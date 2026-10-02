"""Safe read projection of the sole D2 store's completed results."""

from contracts.d2_session_context import D2DiscussionScope, D2ProjectedDialoguePair
from contracts.response_plan_session import D2DialogueReceiptRef, D2ShownPriceOfferRef
from core.user_text_privacy import mask_phones_in_text, mask_emails_in_text


def discussion_scope(resolved):
    decision = resolved.d2_price_scope_decision
    if decision is None:
        prices = [p for p in resolved.d2_request_parts if p.kind == "price" and p.status in {"answered", "unavailable"}]
        if len(prices) != 1 or prices[0].topic_id is None:
            return None
        part = prices[0]
        situation = resolved.d2_treatment_situation
        extent = (situation.extent if situation is not None
            and situation.source_request_id == part.request_id
            and situation.scope_commitment in {"reported", "correction", "hypothetical"} else "unknown")
        return D2DiscussionScope(topic_id=part.topic_id, service_id=part.service_id,
            brand_id=part.brand_id, extent=extent)
    if not any(p.request_id == decision.source_request_id and p.kind == "price"
        and p.status in {"answered", "unavailable"}
        and p.topic_id == decision.topic_id and p.service_id == decision.service_id
        for p in resolved.d2_request_parts):
        raise ValueError("d2_discussion_price_part_required")
    return D2DiscussionScope(topic_id=decision.topic_id, service_id=decision.service_id,
        brand_id=decision.brand_id, extent=decision.applied_extent or "unknown")


def _receipt(store, key, request_id, revision, turn=None):
    result = store.read_completion(key, request_id)
    if result is None or result.committed_revision > revision or (
        turn is not None and result.context.source_turn_index + 1 != turn
    ):
        raise ValueError("d2_history_receipt_invalid")
    if result.focus.source_session_key != key:
        raise ValueError("d2_history_receipt_owner_mismatch")
    return result


def _project_pair(ref, result, limit):
    resolved = result.response.resolved
    # Do not copy rendered_text: it also contains money, promotions and lead UI.
    # Code-owned financial text stays in the replay receipt, not ordinary memory.
    safe_prose = lambda text: mask_emails_in_text(mask_phones_in_text(text))
    by_request = {b.request_id: safe_prose(b.display_text)
        for b in resolved.information_blocks if b.publication == "model_prose"}
    by_request.update({b.request_id: b.display_text for b in resolved.d2_contact_blocks})
    text = []
    for part in resolved.d2_request_parts:
        if part.kind == "price" and resolved.patient_text:
            text.append(safe_prose(resolved.patient_text))
        if part.request_id in by_request:
            text.append(by_request[part.request_id])
    if not resolved.d2_request_parts and resolved.patient_text:
        text.append(safe_prose(resolved.patient_text))
    safe_text = "\n\n".join(dict.fromkeys(text))[:limit].strip()
    price = resolved.d2_price_block or resolved.d2_price_detail_block
    offers = tuple(D2ShownPriceOfferRef(source_client_id=row.source_client_id,
        offer_id=row.offer_id, service_id=row.service_id) for row in price.rows) if price else ()
    return D2ProjectedDialoguePair(
        patient_text=ref.patient_text, selected_ui_ref=ref.selected_ui_ref,
        committed_at_turn=ref.committed_at_turn, assistant_text=safe_text,
        parts=resolved.d2_request_parts, price_scope=discussion_scope(resolved), offers=offers,
        detail_aspect=resolved.d2_price_detail_block.aspect if resolved.d2_price_detail_block else None,
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
    topic = snapshot.state.active_topic
    scope = None
    if topic is not None and topic.discussion_request_id:
        result = _receipt(store, key, topic.discussion_request_id, context.source_revision)
        scope = discussion_scope(result.response.resolved)
        service = snapshot.state.active_service
        if scope is None or scope.topic_id != topic.topic_id or (
            service is not None and scope.service_id is not None and scope.service_id != service.service_id
        ):
            raise ValueError("d2_discussion_receipt_scope_mismatch")
    ordinary = context.ordinary.model_copy(update={"dialogue_pairs": tuple(pairs), "discussion_scope": scope,
        "active_topic": topic.model_copy(update={"discussion_request_id": None}) if topic else None})
    return context.model_copy(update={"ordinary": ordinary})


def retain_discussion_reference(state, previous, context, resolved, request_id):
    """Follow the finalized active focus; no text parsing or price search."""
    topic = state.active_topic
    if topic is None:
        return state
    scope = discussion_scope(resolved)
    reference = None
    if scope is not None and scope.topic_id == topic.topic_id:
        reference = request_id
    elif context.freshness == "fresh" and previous.active_topic is not None:
        old = previous.active_topic
        old_scope = context.ordinary.discussion_scope
        if old.topic_id == topic.topic_id and old_scope is not None and not (
            state.active_service is not None and state.active_service.service_id != old_scope.service_id
        ):
            reference = old.discussion_request_id
    return state.model_copy(update={"active_topic": topic.model_copy(update={"discussion_request_id": reference})})
