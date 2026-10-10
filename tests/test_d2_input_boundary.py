"""2V: real JSON/SSE ingress, safe completed history, and replay; offline only."""
import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from tests.d2_ci_http import FakeProvider, completed_context, explanation, http_env, raw, send


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("query", ["Да", "Ок", "А", "Сколько **стоит** КТ?"])
def test_short_and_formatted_turn_reaches_provider_without_reclassification(http_env, transport, query):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(explanation("Могу рассказать о технологиях клиники."))))
    send(client, transport, sid="input-boundary", request_id="first", q="Расскажите о клинике")
    fake.raw = raw(explanation("Продолжение разговора."))
    args = dict(sid="input-boundary", request_id="next", q=query)
    answer = send(client, transport, **args)
    assert fake.inputs[-1].user_message == query
    assert fake.inputs[-1].context.ordinary.dialogue_pairs[-1].assistant_text == "Могу рассказать о технологиях клиники."
    assert answer["answer"] == "Продолжение разговора."
    assert send(client, transport, **args) == answer
    assert len(fake.inputs) == 2
    with D2DialogueStore(db) as store:
        pair = completed_context(store, SessionKey(client_id="demo", sid="input-boundary")).ordinary.dialogue_pairs[-1]
        assert pair.patient_text == query


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_punctuation_email_is_masked_in_input_and_assistant_history(http_env, transport):
    client, db, use, _ = http_env
    email = "boundary.person+tag@sub.example.co.uk"
    fake = use(FakeProvider(raw(explanation(f"Напишите {email}. Можно обсудить КТ."))))
    query = f"Почта {email}. Сколько стоит КТ?"
    send(client, transport, sid="input-boundary", request_id="email", q=query)
    assert email not in fake.inputs[-1].user_message
    assert "[email скрыт]. Сколько стоит КТ?" in fake.inputs[-1].user_message
    with D2DialogueStore(db) as store:
        result = completed_context(store, SessionKey(client_id="demo", sid="input-boundary"))
        pair = result.ordinary.dialogue_pairs[-1]
        assert email not in pair.patient_text and email not in pair.assistant_text
        assert pair.assistant_text == "Напишите [email скрыт]. Можно обсудить КТ."
    fake.raw = raw(explanation("Продолжение."))
    send(client, transport, sid="input-boundary", request_id="continue", q="Расскажите")
    pair = fake.inputs[-1].context.ordinary.dialogue_pairs[-1]
    assert email not in pair.assistant_text and email not in pair.patient_text
