"""Current D2 HTTP migration helpers, with actual published UI actions."""
import json

from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from tests.test_d2_sim2_dialogues import raw, explanation
from core.d2_live_provider import build_d2_d1r_messages


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
