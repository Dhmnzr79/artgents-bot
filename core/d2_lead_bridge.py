"""CP5-LEAD: bridge existing D1R lead/privacy owners onto the common D2 route.

PII and slot state stay in session mem. D2 store keeps only ordinary facts plus
optional PII-free lead_effect receipt (CP4). This module does not call a model.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from contracts.d2_tenant_snapshot import D2TenantSnapshot
from contracts.request_understanding import RequestUnderstanding
from contracts.response_plan import (
    ComposerResult,
    D2ExactTextBlock, D2ResolvedRequestPart,
    ComposerSelectedRouteAuthority,
    PreComposerPlan,
    PricePlan,
    RouteModePair,
    SessionKey,
    UiPlanCandidates,
    UiQuickReplyCandidate,
)
from contracts.response_plan_materialization import (
    MaterializationTrace,
    MaterializedResponseOutcome,
)
from contracts.response_plan_post_composer import ResponseSituationDelta
from core.client_config_loader import resolve_lead_name_prompt, tone_to_txt_dict
from core.clinic_policy_resolver import resolve_clinic_policies, resolve_clinic_policy_operations
from core.d2_snapshot_sources import d2_authored_policy_answers
from core.lead_phone_input import parse_unambiguous_lead_phone
from core.lead_provider_input_privacy import prepare_lead_pending_provider_question
from core.lead_turn_classifier import classify_lead_active_turn
from core.response_plan_resolver import resolve_response_plan
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui
from lead_interrupt import (
    LEAD_CANCEL_REF,
    LEAD_PENDING_ANSWER_REF,
    LEAD_PENDING_CONTINUE_NAME_REF,
    LEAD_PENDING_RETRY_PHONE_REF,
    LEAD_RESUME_REF,
    parse_lead_cancel,
)
from name_gate import accept_lead_name
from session import (
    SessionClientNotBoundError,
    clear_lead_pending_interruption,
    complete_lead_pending_answer_pause,
    exit_lead_flow,
    get_lead_pending_interruption,
    is_active_lead_flow,
    is_lead_paused,
    mark_booking_intent_ever,
    mem_get,
    peek_lead_activity,
    peek_lead_paused,
    resume_lead_from_pause,
    set_lead_intent,
    set_lead_pending_interruption,
    update_profile,
)

D2LeadKind = Literal[
    "collecting_name",
    "collecting_phone",
    "cancelled",
    "pending_interrupt",
    "booking_blocked",
    "submitted",
    "unclear",
]


@dataclass(frozen=True, slots=True)
class D2LeadBridgeResult:
    """One lead/privacy turn resolved without a model call (or booking entry)."""

    kind: D2LeadKind
    response: MaterializedResponseOutcome
    booking_request_id: str | None = None
    request_effect: bool = False


@dataclass(frozen=True, slots=True)
class D2PendingLeadAnswer:
    safe_question: str
    resume_step: Literal["collecting_name", "collecting_phone"]


def prepare_d2_pending_lead_answer(session_key: SessionKey) -> D2PendingLeadAnswer:
    """Read the verified click's question from this tenant's lead owner only."""
    if not d2_lead_session_client_matches(session_key):
        raise ValueError("d2_lead_session_client_required")
    state = mem_get(session_key.sid)
    raw, step = get_lead_pending_interruption(session_key.sid)
    if step not in {"collecting_name", "collecting_phone"} or state.get("lead_intent") != step:
        raise ValueError("d2_pending_lead_question_unavailable")
    profile = state.get("profile") or {}
    safe = prepare_lead_pending_provider_question(
        raw, profile_name=str(profile.get("name") or ""),
    )
    if safe is None:
        raise ValueError("d2_pending_lead_question_privacy_only")
    return D2PendingLeadAnswer(safe_question=safe, resume_step=step)


def d2_paused_lead_profile_name(session_key: SessionKey) -> str:
    """Use a bound name only for privacy stripping, never as model context."""
    if not d2_lead_session_client_matches(session_key):
        raise ValueError("d2_lead_session_client_required")
    state = mem_get(session_key.sid)
    if not is_lead_paused(state):
        return ""
    return str((state.get("profile") or {}).get("name") or "")


def apply_d2_lead_pause_ui(response: MaterializedResponseOutcome) -> MaterializedResponseOutcome:
    """Freeze resume/cancel in the resolved plan before D2 publishes its result."""
    session_key = response.resolved.session_delta.session_key
    if not d2_lead_session_client_matches(session_key):
        raise ValueError("d2_lead_session_client_required")
    client_id = session_key.client_id
    state = mem_get(session_key.sid)
    step = state.get("lead_resume_step") if is_lead_paused(state) else state.get("lead_intent")
    replies = (
        UiQuickReplyCandidate(source_client_id=client_id, reply_id=LEAD_RESUME_REF,
                              label="Продолжить запись"),
    )
    if step == "collecting_phone":
        replies += _lead_slot_quick_replies(client_id)
    ui = response.resolved.ui_plan.model_copy(update={
        "quick_replies": replies, "buttons": (), "widget": None,
        "video": None, "contact": None,
    })
    resolved = response.resolved.model_copy(update={
        "ui_plan": ui, "textual_cta_block": None,
        "finalized_commercial_ids": response.resolved.finalized_commercial_ids.model_copy(
            update={"shown_service_option_ids": ()}
        ),
        "session_delta": response.resolved.session_delta.model_copy(
            update={"shown_service_option_ids": ()}
        ),
    })
    resolved = type(resolved).model_validate(resolved.model_dump(mode="python"))
    return replace(
        response, resolved=resolved, rendered_text=render_response_text(resolved),
        ui_projection=project_response_ui(resolved),
    )


def reconcile_d2_lead_pause(session_key: SessionKey, completion) -> None:
    """Finish a committed answer after a post-commit interruption or replay."""
    if completion is None:
        return
    response = completion.response
    if response.resolved.session_delta.session_key != session_key:
        raise ValueError("d2_lead_completion_owner_mismatch")
    refs = {item.reply_id for item in response.ui_projection.quick_replies}
    if LEAD_RESUME_REF not in refs:
        return
    if not d2_lead_session_client_matches(session_key):
        raise ValueError("d2_lead_session_client_required")
    complete_lead_pending_answer_pause(
        session_key.sid, expected_source_revision=completion.committed_revision - 1,
    )


def d2_lead_session_client_matches(session_key: SessionKey) -> bool:
    """True only when thread-local pack id equals this turn's session client."""
    from session import current_session_client_id

    bound = current_session_client_id()
    if bound is None:
        return False
    if bound != session_key.client_id:
        raise ValueError("d2_lead_session_client_mismatch")
    return True


def d2_lead_needs_pre_provider(
    *,
    session_key: SessionKey,
    lead_ui_ref: str | None,
    user_message: str,
) -> bool:
    """True when the turn must short-circuit before the D1R provider.

    Ordinary D2 turns may probe the client binding but never read session mem.
    Active lead and paused text cancellation run only when the bound
    session client exactly matches ``session_key.client_id``.
    A mismatched binding fails closed.
    """
    ref = (lead_ui_ref or "").strip()
    if ref == "d2:booking_cta":
        return True
    if ref in {
        LEAD_CANCEL_REF,
        LEAD_PENDING_ANSWER_REF,
        LEAD_PENDING_CONTINUE_NAME_REF,
        LEAD_PENDING_RETRY_PHONE_REF,
        LEAD_RESUME_REF,
    }:
        return True
    if not d2_lead_session_client_matches(session_key):
        return False
    try:
        _, active_lead = peek_lead_activity(session_key.sid)
    except SessionClientNotBoundError:
        return False
    return active_lead or (
        peek_lead_paused(session_key.sid) and parse_lead_cancel(user_message)
    )


def resolve_d2_booking_lead_entry(
    *,
    snapshot: D2TenantSnapshot,
    session_key: SessionKey,
    understanding: RequestUnderstanding | None = None,
    operations=None,
) -> D2LeadBridgeResult | None:
    """Authorize typed booking via existing clinic_policy_resolver; enter name or block."""
    if operations is None:
        operations = understanding.requests
    booking_parts = tuple(item for item in operations if item.kind == "booking")
    if not booking_parts:
        return None
    policy = (resolve_clinic_policies(client_id=session_key.client_id, understanding=understanding)
        if understanding is not None else resolve_clinic_policy_operations(
            client_id=session_key.client_id, operations=operations,
            policy_keys=d2_authored_policy_answers(snapshot)))
    blocked_keys = tuple(dict.fromkeys(
        d.policy_key for d in policy.decisions if d.policy_key and (
            d.outcome == "blocked" or (
                policy.suppress_forbidden_booking_cta
                and d.policy_key == "no_pediatric_dentistry"
                and d.outcome == "allowed_by_known_rules"
            )
        )
    ))
    if blocked_keys:
        text = "\n\n".join(filter(None, (
            _authored_policy_answer(snapshot, key) for key in blocked_keys
        ))) or "У меня пока недостаточно информации об условиях такой записи."
        return D2LeadBridgeResult(
            kind="booking_blocked",
            response=_plain_answer(snapshot, session_key=session_key, text=text, quick=(),
                policy_ids=blocked_keys, request_id=booking_parts[0].request_id),
        )
    if not policy.active_booking_request_id or policy.suppress_forbidden_booking_cta:
        return D2LeadBridgeResult(
            kind="unclear",
            response=_plain_answer(snapshot, session_key=session_key,
                text="Уточните, пожалуйста, условия записи. Пока я не могу подтвердить её по указанным данным.",
                quick=()),
        )
    sid = session_key.sid
    st = mem_get(sid)
    if is_lead_paused(st):
        return D2LeadBridgeResult(
            kind="pending_interrupt",
            response=_plain_answer(
                snapshot, session_key=session_key,
                text="Запись уже начата. Продолжите её, когда будете готовы.", quick=(),
            ),
        )
    if is_active_lead_flow(st):
        # Already collecting; re-prompt name without stacking state.
        return D2LeadBridgeResult(
            kind="collecting_name",
            response=_name_prompt_response(snapshot, session_key=session_key),
            booking_request_id=policy.active_booking_request_id,
        )
    mark_booking_intent_ever(sid)
    set_lead_intent(sid, "collecting_name")
    return D2LeadBridgeResult(
        kind="collecting_name",
        response=_name_prompt_response(snapshot, session_key=session_key),
        booking_request_id=policy.active_booking_request_id,
    )


def resolve_d2_lead_pre_provider(
    *,
    snapshot: D2TenantSnapshot,
    session_key: SessionKey,
    user_message: str,
    lead_ui_ref: str | None = None,
    published_revision: int | None = None,
) -> D2LeadBridgeResult:
    """Handle active lead slots without a provider call."""
    sid = session_key.sid
    client_id = session_key.client_id
    txt = tone_to_txt_dict(client_id)
    ref = (lead_ui_ref or "").strip()
    q = (user_message or "").strip()
    st = mem_get(sid)

    if ref == "d2:booking_cta":
        mark_booking_intent_ever(sid)
        set_lead_intent(sid, "collecting_name")
        return D2LeadBridgeResult(
            kind="collecting_name",
            response=_name_prompt_response(snapshot, session_key=session_key),
        )

    # Pending-choice refs: the answer action enters the ordinary D2 route.
    if ref == LEAD_RESUME_REF:
        if not is_lead_paused(st):
            raise ValueError("d2_lead_resume_not_paused")
        step = resume_lead_from_pause(sid)
        return D2LeadBridgeResult(
            kind=step,
            response=(
                _phone_prompt_response(snapshot, session_key=session_key, txt=txt)
                if step == "collecting_phone"
                else _name_prompt_response(snapshot, session_key=session_key)
            ),
        )
    if ref == LEAD_PENDING_CONTINUE_NAME_REF:
        clear_lead_pending_interruption(sid)
        set_lead_intent(sid, "collecting_name")
        return D2LeadBridgeResult(
            kind="collecting_name",
            response=_name_prompt_response(snapshot, session_key=session_key),
        )
    if ref == LEAD_PENDING_RETRY_PHONE_REF:
        clear_lead_pending_interruption(sid)
        set_lead_intent(sid, "collecting_phone")
        return D2LeadBridgeResult(
            kind="collecting_phone",
            response=_phone_prompt_response(snapshot, session_key=session_key, txt=txt),
        )
    if ref == LEAD_PENDING_ANSWER_REF:
        raise ValueError("d2_pending_answer_requires_ordinary_route")

    decision = classify_lead_active_turn(q, ref=ref, st=st, sid=sid, client_id=client_id)
    if decision.kind == "meta_cancel":
        exit_lead_flow(sid)
        text = txt.get("lead_offer_declined") or "Хорошо. Если появятся вопросы — спрашивайте."
        return D2LeadBridgeResult(
            kind="cancelled",
            response=_plain_answer(snapshot, session_key=session_key, text=text, quick=()),
        )
    if decision.kind == "defer":
        exit_lead_flow(sid)
        text = txt.get("lead_defer_exit") or (
            "Хорошо, без спешки. Когда будете готовы — напишите о записи."
        )
        return D2LeadBridgeResult(
            kind="cancelled",
            response=_plain_answer(snapshot, session_key=session_key, text=text, quick=()),
        )
    if decision.kind == "slot" and decision.slot_value:
        step = (st.get("lead_intent") or "").strip()
        if step == "collecting_phone":
            update_profile(sid, phone=decision.slot_value)
            exit_lead_flow(sid)
            text = txt.get("lead_submit_ok") or "Спасибо! Заявку передали администратору."
            return D2LeadBridgeResult(
                kind="submitted",
                response=_plain_answer(snapshot, session_key=session_key, text=text, quick=()),
                request_effect=True,
            )
        # collecting_name: accept name, go to phone — no slot confirmation (A12).
        update_profile(sid, name=decision.slot_value)
        set_lead_intent(sid, "collecting_phone")
        return D2LeadBridgeResult(
            kind="collecting_phone",
            response=_phone_prompt_response(snapshot, session_key=session_key, txt=txt),
        )
    if decision.kind == "pending_interrupt":
        step = (st.get("lead_intent") or "collecting_name").strip()
        if step not in {"collecting_name", "collecting_phone"}:
            step = "collecting_name"
        set_lead_pending_interruption(
            sid, text=q, step=step, source_revision=published_revision,
        )
        if step == "collecting_phone":
            quick = (
                UiQuickReplyCandidate(
                    source_client_id=snapshot.client_id,
                    reply_id=LEAD_PENDING_ANSWER_REF,
                    label="Ответить",
                ),
                UiQuickReplyCandidate(
                    source_client_id=snapshot.client_id,
                    reply_id=LEAD_PENDING_RETRY_PHONE_REF,
                    label="Ввести номер заново",
                ),
            )
            text = "Сейчас собираем телефон для записи. Ответить на вопрос или ввести номер?"
        else:
            quick = (
                UiQuickReplyCandidate(
                    source_client_id=snapshot.client_id,
                    reply_id=LEAD_PENDING_ANSWER_REF,
                    label="Ответить",
                ),
                UiQuickReplyCandidate(
                    source_client_id=snapshot.client_id,
                    reply_id=LEAD_PENDING_CONTINUE_NAME_REF,
                    label="Продолжить запись",
                ),
            )
            text = (
                txt.get("lead_pending_choice")
                or "Сейчас оформляем запись. Ответить на вопрос или продолжить?"
            )
        return D2LeadBridgeResult(
            kind="pending_interrupt",
            response=_plain_answer(snapshot, session_key=session_key, text=text, quick=quick),
        )

    # Unclear / non-slot on name: re-prompt without confirming invented name.
    if (st.get("lead_intent") or "").strip() == "collecting_phone":
        return D2LeadBridgeResult(
            kind="unclear",
            response=_phone_prompt_response(snapshot, session_key=session_key, txt=txt),
        )
    return D2LeadBridgeResult(
        kind="unclear",
        response=_name_prompt_response(snapshot, session_key=session_key),
    )


def _authored_policy_answer(snapshot: D2TenantSnapshot, policy_key: str) -> str | None:
    import yaml

    raw_bytes = dict(snapshot.files).get("clinic_policies.yaml")
    if raw_bytes is None:
        return None
    raw = yaml.safe_load(raw_bytes.decode("utf-8"))
    if not isinstance(raw, dict):
        return None
    policies = raw.get("policies")
    if not isinstance(policies, dict):
        return None
    body = policies.get(policy_key)
    if not isinstance(body, dict):
        return None
    answer = body.get("answer")
    return answer.strip() if isinstance(answer, str) and answer.strip() else None


def _lead_slot_quick_replies(client_id: str) -> tuple[UiQuickReplyCandidate, ...]:
    return (
        UiQuickReplyCandidate(
            source_client_id=client_id,
            reply_id=LEAD_CANCEL_REF,
            label="Отменить запись",
        ),
    )


def _name_prompt_response(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
) -> MaterializedResponseOutcome:
    text = resolve_lead_name_prompt(session_key.client_id, cta_key="booking")
    return _plain_answer(
        snapshot,
        session_key=session_key,
        text=text,
        quick=(),
    )


def _phone_prompt_response(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
    txt: dict,
) -> MaterializedResponseOutcome:
    text = (
        txt.get("lead_phone_prompt_neutral")
        or "Оставьте, пожалуйста, номер телефона — администратор свяжется с вами, "
        "чтобы подтвердить запись."
    )
    return _plain_answer(
        snapshot,
        session_key=session_key,
        text=text,
        quick=_lead_slot_quick_replies(snapshot.client_id),
    )


def _plain_answer(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
    text: str,
    quick: tuple[UiQuickReplyCandidate, ...],
    policy_ids: tuple[str, ...] = (),
    request_id: str | None = None,
) -> MaterializedResponseOutcome:
    if snapshot.client_id != session_key.client_id:
        raise ValueError("d2_lead_client_mismatch")
    plan = PreComposerPlan(
        session_key=session_key,
        context_strategy="full_context",
        route_authority=ComposerSelectedRouteAuthority(
            allowed_route_modes=(RouteModePair(route="ANSWER", mode="standard"),),
            terminal_candidates=(),
        ),
        response_scope="clinic",
        selected_service_id=None,
        active_session_service_id=None,
        selected_topic_id=None,
        price_plan=PricePlan(kind="none"),
        d2_result_status="complete" if policy_ids else None,
        d2_request_parts=(D2ResolvedRequestPart(request_id=request_id,
            kind="reference", status="answered", scope="clinic"),) if policy_ids else (),
        d2_exact_text_blocks=(D2ExactTextBlock(request_id=request_id,
            source_client_id=session_key.client_id, display_text=text,
            policy_ids=policy_ids),) if policy_ids else (),
        ui_candidates=UiPlanCandidates(quick_replies=quick),
        transport_kind="blocking",
    )
    composer = ComposerResult(route="ANSWER", mode="standard",
        patient_text=None if policy_ids else text, code_owned_answer=bool(policy_ids))
    resolved = resolve_response_plan(plan, composer)
    resolved = resolved.model_copy(update={"attribution_kind": "lead"})
    return MaterializedResponseOutcome(
        resolved=resolved,
        rendered_text=render_response_text(resolved),
        ui_projection=project_response_ui(resolved),
        materialization_diagnostics=(),
        selection_diagnostics=(),
        adapter_diagnostics=(),
        situation_delta=ResponseSituationDelta(action="keep"),
        trace=MaterializationTrace(None, (), (), ()),
    )


# Re-export helpers used by dialogue for active-lead name gate checks in tests.
__all__ = [
    "D2LeadBridgeResult",
    "d2_lead_needs_pre_provider",
    "d2_lead_session_client_matches",
    "resolve_d2_booking_lead_entry",
    "resolve_d2_lead_pre_provider",
    "accept_lead_name",
    "parse_unambiguous_lead_phone",
]
