"""Read-only public projection of an already frozen D2 result, excluding intake."""
from core.d2_completion_context import public_dialogue_plan
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui


def public_completed_turn_payload(turn, *, include_card_details=False):
    plan = public_dialogue_plan(turn.response.resolved)
    lead_ids = {p.request_id for p in plan.d2_request_parts if p.kind == 'lead'}
    ui = plan.ui_plan.model_copy(update={
        'booking_form': False, 'lead_consent': None,
        'quick_replies': tuple(q for q in plan.ui_plan.quick_replies if not q.reply_id.startswith('lead:')),
    })
    plan = plan.model_copy(update={
        'd2_request_parts': tuple(p for p in plan.d2_request_parts if p.kind != 'lead'),
        'd2_exact_text_blocks': tuple(b for b in plan.d2_exact_text_blocks if b.request_id not in lead_ids),
        'ui_plan': ui,
    })
    key = turn.context.session_key
    return dict(answer=render_response_text(plan, include_lead=False, include_card_details=include_card_details),
                ui=project_response_ui(plan).model_dump(mode='json'),
                client_id=key.client_id, sid=key.sid, request_id=turn.request_id,
                revision=turn.committed_revision, catalog_version=turn.catalog_version,
                attribution_kind=plan.attribution_kind)
