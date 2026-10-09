"""Display attribution follows frozen owners through JSON/SSE and replay."""
import json

import pytest

from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse
from tests.test_d2_document_click_task_http import _body
from tests.test_d2_compound_answers import content, raw, saved


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("blocks,expected", [
    ([content()], "content"),
    ([dict(kind="price", request_id="r1", target={"type": "service", "id": "classic"})], "content"),
    ([dict(kind="clinic_policy", request_id="r1", policy_ids=["no_oms"])], "content"),
    ([dict(kind="commercial_fact", request_id="r1", target={"type": "clinic"}, promotion_scope="general")], "content"),
    ([dict(kind="off_topic", request_id="r1")], "plain"),
    ([dict(kind="booking", request_id="r1", age_group="adult")], "lead"),
    ([content(), dict(kind="booking", request_id="r2", age_group="adult")], "lead"),
], ids=["explanation", "price", "policy", "commercial", "off_topic", "booking", "mixed_booking"])
def test_frozen_attribution_replays_and_stays_out_of_model_context(http_env, transport, blocks, expected):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(*blocks)))
    send = post if transport == "json" else post_sse
    args = dict(request_id="attribution", q="Вопрос")
    first = _body(send(client, **args), transport)
    assert first["attribution_kind"] == expected
    assert saved(db).response.resolved.attribution_kind == expected
    assert _body(send(client, **args), transport) == first
    assert len(fake.inputs) == 1
    assert "attribution_kind" not in json.dumps(fake.inputs[0].context.model_dump(mode="json"))
    if expected != "lead":
        fake.raw = raw(dict(kind="off_topic", request_id="r1"))
        assert _body(send(client, request_id="next", q="Следующий вопрос"), transport)
        assert "attribution_kind" not in json.dumps(fake.inputs[-1].context.model_dump(mode="json"))
    else:
        name = _body(send(client, request_id="name", q="Денис"), transport)
        assert name["attribution_kind"] == "lead"
        assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_spam_has_no_material_attribution_or_model_call(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider("forbidden"))
    body = _body((post if transport == "json" else post_sse)(client, q="!!!"), transport)
    assert body["attribution_kind"] == "plain"
    assert not fake.inputs
