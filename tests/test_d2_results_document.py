"""Results requests use existing authored source follow-ups, with one model call."""
import json
import pytest

from core.d2_live_provider import D2HttpProvider
from tests.test_d2_http_contract import http_env
from tests.test_d2_demo_release_gate import call
from tests.test_d2_native_price_runtime import Transport, message
from tests.test_d2_primary_source_followups import reply, source

DOCUMENT = "clinic__info__results.md"
GALLERY_REF = f"{DOCUMENT}#posmotret-rezultaty"


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_results_document_and_repeat_keep_authored_gallery_link(http_env, transport):
    client, _, use, _ = http_env
    wire = Transport(message(reply([source(DOCUMENT)], "Покажу примеры наших работ.")),
                     message(reply([source(DOCUMENT)], "Можно посмотреть их снова.")))
    use(D2HttpProvider(transport=wire))
    for number, question in enumerate(["Можно посмотреть ваши работы?", "Покажите ещё раз до и после"]):
        body = call(client, transport, request_id=f"results-{number}", q=question)
        assert body["client_id"] == "demo"
        assert [item["reply_id"] for item in body["ui"]["quick_replies"]] == [GALLERY_REF]
        assert all(item["source_client_id"] == "demo" for item in body["ui"]["quick_replies"])
    assert len(wire.calls) == 2
    model_context = json.dumps(wire.calls[0]["messages"], ensure_ascii=False)
    assert DOCUMENT in model_context
    assert "протезирования циркониевыми коронками" in model_context


def test_consumed_server_document_ref_stays_consumed(http_env):
    client, _, use, _ = http_env
    wire = Transport(*(message(reply([source(DOCUMENT)])) for _ in range(3)))
    use(D2HttpProvider(transport=wire))
    first = call(client, request_id="first", q="Ваши работы?")
    clicked = call(client, request_id="server-click", q="", ref=GALLERY_REF,
                   ui_revision=first["revision"])
    assert clicked["ui"]["quick_replies"] == []
    repeated = call(client, request_id="repeat", q="Ещё раз результаты")
    assert repeated["ui"]["quick_replies"] == []
    assert len(wire.calls) == 3


def test_results_published_cta_starts_existing_lead_without_model(http_env):
    client, _, use, _ = http_env
    wire = Transport(message(reply([source(DOCUMENT)])))
    use(D2HttpProvider(transport=wire))
    first = call(client, request_id="results", q="Покажите ваши работы")
    buttons = first["ui"]["buttons"]
    assert buttons and buttons[0]["source_client_id"] == "demo"
    started = call(client, request_id="booking", q="",
                   ref=f"button:{buttons[0]['button_id']}", ui_revision=first["revision"])
    assert started["ui"]["booking_form"] is True
    assert started["ui"]["lead_consent"] is None
    assert not started["ui"]["quick_replies"]
    assert len(wire.calls) == 1
