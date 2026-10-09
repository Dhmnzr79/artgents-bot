"""Current D2 HTTP migration helpers, with actual published UI actions."""
import json

from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from core.d2_live_provider import build_d2_d1r_messages


def raw(*blocks, **kwargs):
    from tests.test_d2_sim2_dialogues import raw as construct
    return construct(*blocks, **kwargs)


def explanation(*args, **kwargs):
    from tests.test_d2_sim2_dialogues import explanation as construct
    return construct(*args, **kwargs)


def send(client, transport="json", **kwargs):
    response = (post if transport == "json" else post_sse)(client, **kwargs)
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json() if transport == "json" else dict(sse_events(response))["ui"]
    assert body["revision"] > 0
    return body


def click(client, body, ref, *, request_id, transport="json", **kwargs):
    published = {q["reply_id"] for q in body["ui"]["quick_replies"]}
    published.update("button:" + b["button_id"] for b in body["ui"]["buttons"])
    assert ref in published, (ref, published)
    return send(client, transport, q="", ref=ref, ui_revision=body["revision"],
                request_id=request_id, **kwargs)


def begin(client, fake, *, sid="cp6a", phone=False, transport="json", client_id="demo"):
    fake.raw = raw({"kind": "booking", "request_id": "r1", "age_group": "adult"})
    body = send(client, transport, sid=sid, client_id=client_id,
                request_id="book", q="Хочу записаться")
    if phone:
        body = send(client, transport, sid=sid, client_id=client_id,
                    request_id="name", q="Анна")
    return body


def prompt(fake, index=-1):
    return json.dumps(build_d2_d1r_messages(fake.inputs[index]), ensure_ascii=False)


def completed_context(store, key):
    """Exercise the actual read projection, not a test-owned offer carrier."""
    from contracts.d2_session_context import D2SessionSnapshot, D2SessionTtlPolicy
    from core.d2_session_context import project_d2_session_context
    from core.d2_completion_context import project_completed_dialogue
    record = store.read(key)
    snapshot = D2SessionSnapshot(state=record.state, exists_in_store=True)
    policy = D2SessionTtlPolicy()
    context = project_d2_session_context(snapshot, expected_session_key=key,
        activity=record.activity, policy=policy, now=record.activity.last_user_turn_at)
    return project_completed_dialogue(context, snapshot, store, policy)
