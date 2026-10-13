"""Primary document owns source UI; supplemental facts never choose navigation."""
import json

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import D2HttpProvider
from tests.test_d2_http_contract import http_env
from tests.test_d2_demo_release_gate import call
from tests.test_d2_native_price_runtime import Transport, message

WARRANTY = "clinic__info__warranty.md"
FIRST_VISIT = "clinic__info__first_visit.md"
AFTERCARE = "implantation__info__aftercare.md"
WARRANTY_LINKS = [f"{WARRANTY}#chto-delat-esli-voznikla-problema",
                  f"{WARRANTY}#pochemu-garantiya-na-rabotu-vracha-1-god"]


def reply(sources, text="Краткий ответ на текущий вопрос."):
    return text + "\n<D2_META>\n" + json.dumps({"sources": sources}) + "\n</D2_META>"


def source(document, **fields):
    return {"content_ref": document, "content_section_refs": ["a:korotko"], **fields}


def links(body):
    return [item["reply_id"] for item in body["ui"]["quick_replies"]]


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_first_visit_keeps_its_links_with_consultation_facts(http_env, transport):
    client, _, use, _ = http_env
    text = "Начните с обычного осмотра."
    wire = Transport(message(reply([source(FIRST_VISIT),
        source("clinic__info__consultation.md")], text)))
    use(D2HttpProvider(transport=wire))
    body = call(client, transport, q="С чего начать?")
    assert body["answer"] == text
    assert links(body) == [f"{FIRST_VISIT}#rasskazhite-pro-kliniku",
                           f"{FIRST_VISIT}#kak-vybirayut-lechenie"]
    assert len(wire.calls) == 1


@pytest.mark.parametrize("primary", [WARRANTY, AFTERCARE])
def test_model_declared_primary_controls_links_across_topics(http_env, primary):
    client, db, use, _ = http_env
    secondary = AFTERCARE if primary == WARRANTY else WARRANTY
    fields = {"target": {"type": "service", "id": "classic"}}
    claims = [source(doc, **(fields if doc == AFTERCARE else {}))
              for doc in [primary, secondary]]
    wire = Transport(message(reply(claims)))
    use(D2HttpProvider(transport=wire))
    body = call(client, q="Расскажите об условиях и уходе")
    expected = WARRANTY_LINKS if primary == WARRANTY else [
        f"{AFTERCARE}#chto-proishodit-v-pervye-dni",
        f"{AFTERCARE}#kak-prohodit-vosstanovlenie-do-koronki"]
    assert links(body) == expected
    with D2DialogueStore(db) as store:
        resolved = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved
    assert resolved.response_scope == "mixed"
    assert resolved.d2_request_parts[0].discussion_scope is None
    assert resolved.ui_plan.source_content_ref == primary
    assert len(wire.calls) == 1


@pytest.mark.parametrize("primary", [None, {}, source("missing.md"),
    {"content_ref": WARRANTY, "content_section_refs": ["a:missing"]}])
def test_invalid_primary_never_promotes_valid_supplement(http_env, primary):
    client, _, use, _ = http_env
    wire = Transport(message(reply([primary, source(WARRANTY)])))
    use(D2HttpProvider(transport=wire))
    body = call(client, q="Вопрос про гарантию")
    assert body["answer"] == "Краткий ответ на текущий вопрос."
    assert links(body) == []
    assert len(wire.calls) == 1


def test_invalid_supplement_does_not_erase_valid_primary_links(http_env):
    client, _, use, _ = http_env
    wire = Transport(message(reply([source(WARRANTY), None])))
    use(D2HttpProvider(transport=wire))
    assert links(call(client, q="Вопрос про гарантию")) == WARRANTY_LINKS
    assert len(wire.calls) == 1


def test_clicked_document_remains_owner_despite_model_source_reordering(http_env):
    client, _, use, _ = http_env
    wire = Transport(message(reply([source(WARRANTY), source(AFTERCARE)])),
                     message(reply([source(AFTERCARE), source(WARRANTY)])))
    use(D2HttpProvider(transport=wire))
    first = call(client, request_id="first", q="Гарантия?")
    assert links(first) == WARRANTY_LINKS
    second = call(client, request_id="click", q="", ref=WARRANTY_LINKS[1],
                  ui_revision=first["revision"])
    assert links(second) == WARRANTY_LINKS[:1]
    assert len(wire.calls) == 2


@pytest.mark.parametrize("primary", [source(WARRANTY), None])
def test_foreign_supplement_is_rejected_even_with_invalid_primary(http_env, monkeypatch, primary):
    client, db, use, _ = http_env
    import core.d2_dialogue as dialogue
    from tests.test_d2_http_contract import post
    build = dialogue.build_d2_snapshot_sources

    def foreign_sources(*args, **kwargs):
        result = build(*args, **kwargs)
        return result.model_copy(update={"d2_authored_content": tuple(
            item.model_copy(update={"source_client_id": "foreign"})
            if item.content_ref == AFTERCARE else item
            for item in result.d2_authored_content)})

    monkeypatch.setattr(dialogue, "build_d2_snapshot_sources", foreign_sources)
    wire = Transport(message(reply([primary, source(AFTERCARE)])))
    use(D2HttpProvider(transport=wire))
    response = post(client, q="Гарантия и уход?")
    assert response.status_code == 400
    with D2DialogueStore(db) as store:
        assert store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")) is None
    assert len(wire.calls) == 1


def test_native_price_keeps_its_own_ui_and_call_count(http_env):
    client, _, use, _ = http_env
    args = {"target": {"type": "service", "id": "classic"}}
    wire = Transport(message(None, args), message(reply([source(WARRANTY), source(AFTERCARE)])))
    use(D2HttpProvider(transport=wire))
    body = call(client, q="Цена и условия?")
    assert any(part["kind"] == "price_card" for part in body["ui"]["body_parts"])
    assert not set(links(body)).intersection(WARRANTY_LINKS)
    assert len(wire.calls) == 2
