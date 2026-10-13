"""Server-owned historical card action retained after ordinary detail removal."""
import pytest
from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from tests.d2_ci_http import FakeProvider, http_env, raw, send, explanation
from tests.test_d2_sim2_dialogues import forbidden


def price():
    return dict(kind="price", request_id="r1", target={"type": "service", "id": "classic"},
                brand_id="nobel_biocare", volume={"extent": "one_tooth"})


def plan(db):
    with D2DialogueStore(db) as store:
        return store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_old_card_detail_click_after_topic_change_remains_exact(http_env, transport):
    client, db, use, _ = http_env
    operation = price()
    operation.pop("brand_id")
    fake = use(FakeProvider(raw(operation)))
    first = send(client, transport, request_id="price")
    assert "price_select:classic.one_tooth.nobel" in {
        choice["reply_id"] for card in first["ui"]["body_parts"] if card["kind"] == "price_card"
        for choice in card["choices"]}
    fake.raw = raw(explanation("Информация об отбеливании.", target={"type": "service", "id": "professional_whitening"}))
    send(client, transport, request_id="new")
    fake.generate = forbidden
    # Historical tabs support returning to a card; obsolete detail revisions
    # remain protected by the existing ingress contract.
    restored = send(client, transport, request_id="return", q="",
                    ref="price_select:classic.one_tooth.nobel", ui_revision=first["revision"])
    args = dict(request_id="click", q="", ref="price_detail:includes", ui_revision=restored["revision"])
    body = send(client, transport, **args)
    assert [r.offer_id for r in plan(db).d2_price_detail_blocks[0].rows] == ["classic.one_tooth.nobel"]
    assert send(client, transport, **args) == body
    assert len(fake.inputs) == 2
