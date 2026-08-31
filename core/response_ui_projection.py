"""Pure UI projection for frozen ResolvedResponsePlan."""

from __future__ import annotations

from contracts.response_plan import (
    FinalizedCommercialIds,
    ResolvedResponsePlan,
    ResponsePlanContractError,
    ResponseUIProjection,
)


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

    return ResponseUIProjection(
        quick_replies=ui.quick_replies,
        buttons=ui.buttons,
        widget=ui.widget,
        video=ui.video,
        contact=ui.contact,
        projected_commercial_ids=plan.finalized_commercial_ids,
        transport_kind=plan.transport_kind,
    )


def _validate_ui_ownership(client_id: str, items: tuple[object, ...]) -> None:
    for item in items:
        source_client_id = getattr(item, "source_client_id", None)
        if source_client_id != client_id:
            raise ResponsePlanContractError("client_source_mismatch")
