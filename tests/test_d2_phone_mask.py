"""Phone composer mode comes from the frozen lead response, JSON and SSE."""
import pytest
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse
from tests.test_d2_document_click_task_http import _body
from tests.test_d2_text_reply import response, action
from lead_interrupt import LEAD_CANCEL_REF, LEAD_PENDING_RETRY_PHONE_REF

@pytest.mark.parametrize("transport", ["json", "sse"])
def test_phone_mode_transitions_and_frozen_replay(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(response(actions=[action("start_booking", age_group="adult")])))
    send = post if transport == "json" else post_sse
    def call(**args):
        result = send(client, **args)
        assert result.status_code == 200, result.get_data(as_text=True)
        return _body(result, transport)
    first = call(request_id="book", q="Хочу записаться")
    assert first["ui"]["composer_input_mode"] == "text"
    phone = call(request_id="name", q="Анна")
    assert phone["ui"]["composer_input_mode"] == "phone"
    pending = call(request_id="question", q="А где вы находитесь?")
    assert pending["ui"]["composer_input_mode"] == "text"
    retry = call(request_id="retry-phone", q="", ref=LEAD_PENDING_RETRY_PHONE_REF,
                 ui_revision=pending["revision"])
    assert retry["ui"]["composer_input_mode"] == "phone"
    cancelled = call(request_id="cancel", q="", ref=LEAD_CANCEL_REF,
                     ui_revision=retry["revision"])
    assert cancelled["ui"]["composer_input_mode"] == "text"
    assert call(request_id="name", q="Анна") == phone
    assert len(fake.inputs) == 1  # No contacts or interrupted question sent to model.
