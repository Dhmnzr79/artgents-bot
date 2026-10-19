"""Read saved publication for page navigation; never refresh semantic context TTL."""
from datetime import datetime,timezone
from uuid import UUID

from contracts.response_plan import SessionKey
from contracts.d2_session_context import D2SessionSnapshot,D2SessionTtlPolicy
from core.d2_dialogue_store import D2DialogueStore
from core.d2_storage import dialogue_store_path
from core.d2_publication import public_completed_turn_payload
from core.d2_session_context import project_d2_session_context
from core.user_text_privacy import mask_phones_in_text,mask_emails_in_text


def widget_session(client_id,raw):
    if not isinstance(raw,dict) or set(raw)-{'client_id','sid','before_revision'}:
        raise ValueError('widget_session_input_invalid')
    sid=raw.get('sid')
    if not isinstance(sid,str) or str(UUID(sid)).replace('-','')!=sid.replace('-','') or UUID(sid).version!=4:
        raise ValueError('widget_session_sid_invalid')
    before=raw.get('before_revision')
    if before is not None and (type(before) is not int or before<1):
        raise ValueError('widget_session_cursor_invalid')
    path=dialogue_store_path(client_id)
    empty=dict(client_id=client_id,entries=[],current=None,next_before_revision=None,actions_current=False)
    if not path.exists():return empty
    key=SessionKey(client_id=client_id,sid=sid)
    with D2DialogueStore(path)as store:
        record=store.read(key)
        if record is None:return empty
        context=project_d2_session_context(D2SessionSnapshot(state=record.state,exists_in_store=True),
            expected_session_key=key,activity=record.activity,policy=D2SessionTtlPolicy(),now=datetime.now(timezone.utc))
        turns,has_more=store.read_dialogue_history(key,before_revision=before)
        entries=[]
        for turn in turns:
            if turn.dialogue_ref is None:
                parts=turn.response.resolved.d2_request_parts
                if parts and all(p.kind=='lead' for p in parts):continue
                if turn.response.resolved.route in {'ANSWER','CLARIFY'}:
                    raise ValueError('widget_history_receipt_ref_missing')
                entries.append(dict(payload=public_completed_turn_payload(turn),patient_text=None,selected_ref=None,source_revision=None))
                continue
            ref=turn.dialogue_ref
            entries.append(dict(payload=public_completed_turn_payload(turn),patient_text=mask_emails_in_text(mask_phones_in_text(ref.patient_text)) if ref.patient_text else None,
                selected_ref=ref.selected_ui_ref.reply_id if ref.selected_ui_ref else None,
                source_revision=ref.selected_ui_ref.source_revision if ref.selected_ui_ref else None))
        current=store.read_completion_at_revision(key,record.state.revision)
        return dict(client_id=client_id,entries=entries,current=public_completed_turn_payload(current) if current else None,
            next_before_revision=turns[0].committed_revision if has_more and turns else None,actions_current=context.freshness=='fresh')
