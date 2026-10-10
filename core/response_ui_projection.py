"""Pure UI projection for frozen ResolvedResponsePlan."""

from __future__ import annotations

from contracts.response_plan import (
    FinalizedCommercialIds,
    ResolvedResponsePlan,
    ResponsePlanContractError,
    ResponseUIProjection,
    ResponsePriceCardPart,
)
from core.response_text_renderer import render_response_parts


def project_response_ui(plan: ResolvedResponsePlan) -> ResponseUIProjection:
    """Project UI metadata from plan-owned fields without changing visible text."""

    client_id = plan.session_delta.session_key.client_id
    ui = plan.ui_plan
    _validate_ui_ownership(client_id, ui.quick_replies)
    _validate_ui_ownership(client_id, ui.buttons)
    if ui.widget is not None and ui.widget.source_client_id != client_id:
        raise ResponsePlanContractError("client_source_mismatch")
    if ui.video is not None and ui.video.source_client_id != client_id:
        raise ResponsePlanContractError("client_source_mismatch")
    if ui.contact is not None and ui.contact.source_client_id != client_id:
        raise ResponsePlanContractError("client_source_mismatch")

    actions = {action.reply_id: action for action in ui.price_select_actions}
    def card_metadata(part):
        service_choices = []
        seen = set()
        for reply in ui.quick_replies:
            action = actions.get(reply.reply_id)
            if action is None or action.service_id in seen:
                continue
            seen.add(action.service_id)
            service_choices.append(reply.model_copy(update={"label":action.service_name or reply.label}))
        return part.model_copy(update={"choices": tuple(
        reply for reply in ui.quick_replies if reply.reply_id in actions
        and actions[reply.reply_id].service_id == part.price.rows[0].service_id
        ), "service_choices": tuple(service_choices) if len(service_choices) > 1 else (),
            "overview": plan.d2_price_scope_decision})
    body_parts = tuple(card_metadata(part) if isinstance(part, ResponsePriceCardPart) else part
                      for part in render_response_parts(plan))
    if not any(isinstance(part, ResponsePriceCardPart) for part in body_parts):
        body_parts = ()
    return ResponseUIProjection(
        quick_replies=ui.quick_replies,
        buttons=ui.buttons,
        widget=ui.widget,
        video=ui.video,
        contact=ui.contact,
        projected_commercial_ids=plan.finalized_commercial_ids,
        transport_kind=plan.transport_kind,
        body_parts=body_parts,
    )


def _validate_ui_ownership(client_id: str, items: tuple[object, ...]) -> None:
    for item in items:
        source_client_id = getattr(item, "source_client_id", None)
        if source_client_id != client_id:
            raise ResponsePlanContractError("client_source_mismatch")
