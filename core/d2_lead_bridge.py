"""Booking policy offers the shared form; no conversational contact-slot intake."""
from dataclasses import dataclass
from typing import Literal
from contracts.d2_tenant_snapshot import D2TenantSnapshot
from contracts.d2_dialogue import D2LeadEffectStatus
from contracts.request_understanding import RequestUnderstanding
from contracts.response_plan import (ComposerResult,D2ExactTextBlock,D2ResolvedRequestPart,D2SourceResult,
    ComposerSelectedRouteAuthority,PreComposerPlan,PricePlan,RouteModePair,SessionKey,UiPlanCandidates,UiQuickReplyCandidate)
from contracts.response_plan_materialization import MaterializationTrace,MaterializedResponseOutcome
from contracts.response_plan_post_composer import ResponseSituationDelta
from core.clinic_policy_resolver import resolve_clinic_policies,resolve_clinic_policy_operations
from core.d2_snapshot_sources import d2_authored_policy_answers
from core.response_plan_resolver import resolve_response_plan
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui
from core.client_config_loader import tone_to_txt_dict
from lead_service import resolve_lead_submit_message

@dataclass(frozen=True,slots=True)
class D2LeadBridgeResult:
    kind: str
    response: MaterializedResponseOutcome
    booking_request_id: str | None = None


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
            d2_authored_policy_answers(snapshot).get(key) for key in blocked_keys
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
                quick=(), public_kind="clarification"),
        )
    return D2LeadBridgeResult(kind="form", booking_request_id=policy.active_booking_request_id,
        response=booking_form_response(snapshot,session_key=session_key))


def booking_form_response(snapshot, *, session_key):
    return _plain_answer(snapshot,session_key=session_key,
        text="Оставьте имя и телефон — администратор свяжется с вами по заявке.",quick=(),booking_form=True)


def resolve_d2_lead_delivery_response(
    snapshot: D2TenantSnapshot, *, session_key: SessionKey, status: D2LeadEffectStatus,
) -> MaterializedResponseOutcome:
    """The lead owner freezes the same truthful delivery result for HTTP and replay."""
    if status in {"sent", "demo_stub"}:
        text = resolve_lead_submit_message(session_key.client_id, tone_to_txt_dict(session_key.client_id))
    elif status == "failed":
        text = "Не удалось отправить заявку. Пожалуйста, свяжитесь с клиникой напрямую."
    else:
        text = "Подтверждение отправки заявки пока не получено. Пожалуйста, свяжитесь с клиникой напрямую."
    return _plain_answer(snapshot, session_key=session_key, text=text, quick=())


def _plain_answer(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
    text: str,
    quick: tuple[UiQuickReplyCandidate, ...],
    policy_ids: tuple[str, ...] = (),
    request_id: str | None = None,
    public_kind: Literal["clarification"] | None = None,
    booking_form: bool = False,
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
        d2_result_status="complete",
        d2_request_parts=(D2ResolvedRequestPart(request_id=request_id or "r1",
            kind="reference" if policy_ids else public_kind or "lead", status="answered", scope="clinic",
            source_results=tuple(D2SourceResult(source_ref=f"policy:{key}", outcome="answered")
                for key in policy_ids)),),
        d2_exact_text_blocks=(D2ExactTextBlock(request_id=request_id or "r1",
            source_client_id=session_key.client_id, display_text=text,
            policy_ids=policy_ids),),
        ui_candidates=UiPlanCandidates(quick_replies=quick, booking_form=booking_form),
        transport_kind="blocking",
    )
    composer = ComposerResult(route="ANSWER", mode="standard",
        patient_text=None, code_owned_answer=True)
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
