"""D2-DOC-CLICK: verified section task and ordinary prose through real HTTP."""
from tests.test_d2_continuation_scenarios import projected_history

import json

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import build_d2_d1r_messages
from core.one_call_envelope_protocol import (
    parse_production_envelope_json, production_envelope_template,
)
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from tests.test_d2_live_provider_offline import _request
from tests.test_d2_ui_b12_scenarios import _price_raw


def _raw(text, *, ref=None, kind="content", **fields):
    return json.dumps({"outcome": "dialogue", "blocks": [{
        "kind": kind, "request_id": "r1", "content_text": text, "content_ref": ref,
        **fields}]}, ensure_ascii=False)


def _parse(raw):
    view = _request().model_view
    return parse_production_envelope_json(
        raw, active_service_catalog=view.active_service_catalog,
        service_reference_catalog=view.service_reference_catalog,
        commercial_fact_catalog=view.commercial_fact_catalog,
    )


def _legacy_raw(text, *, kind="content", **fields):
    """Historical parser consumers remain tested separately from active D2 HTTP."""
    return json.dumps(production_envelope_template(
        request_understanding={"subjects": [], "requests": [{
            "request_id": "r1", "kind": kind, "subject_id": None,
            "context": "general_information", "content_text": text, **fields,
        }]},
    ), ensure_ascii=False)


class PromptProvider(FakeProvider):
    def __init__(self, raw):
        super().__init__(raw)
        self.messages = []

    def generate(self, request):
        # Build the production prompt at generation time, not after the turn.
        self.messages.append(build_d2_d1r_messages(request))
        return super().generate(request)


def _body(response, transport):
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json() if transport == "json" else dict(sse_events(response))["ui"]


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("doc,sections", [
    ("implantation__faq__pain.md", (
        ("kakuyu-anesteziyu-ispolzuyut", "Какую анестезию используют"),
        ("chto-chuvstvuetsya-posle-ustanovki", "Что чувствуется после установки"),
    )),
    ("implantation__faq__osseointegration.md", (
        ("a-esli-implant-ne-prizhivetsya", "А если имплант не приживётся"),
        ("ot-chego-zavisit-prizhivlenie", "От чего зависит приживление"),
    )),
])
def test_current_document_question_is_explicit_before_provider_and_replays(
    http_env, transport, doc, sections,
):
    client, db, use_provider, _ = http_env
    first_text = "Первое пояснение по материалу клиники."
    fake = use_provider(PromptProvider(_raw(first_text, ref=doc)))
    sid = f"document-task-{transport}"
    send = post if transport == "json" else post_sse
    body = _body(send(client, sid=sid, request_id="first", q="Расскажите подробнее"), transport)
    assert fake.inputs[0].selected_document_action is None
    assert "=== D2_SELECTED_DOCUMENT_ACTION ===\nnull" in fake.messages[0][1]["content"]

    for index, (anchor, title) in enumerate(sections, 1):
        ref = f"{doc}#{anchor}"
        assert any(row["reply_id"] == ref for row in body["ui"]["quick_replies"])
        prose = f"Самостоятельное пояснение выбранного раздела номер {index}."
        # Omitted mode and missing model ref exercise the real incident shape.
        fake.raw = json.dumps({"explanations": [{"request_id": "r1", "content_text": prose}]})
        args = dict(sid=sid, request_id=f"click-{index}", q="", ref=ref,
                    ui_revision=body["revision"])
        body = _body(send(client, **args), transport)
        request = fake.inputs[-1]
        action = request.selected_document_action
        assert action.source_client_id == "demo"
        assert (action.reply_id, action.source_revision) == (ref, args["ui_revision"])
        assert (action.content_ref, action.section_ref, action.section_title) == (
            doc, f"a:{anchor}", title,
        )
        assert request.selected_ui_ref.reply_id == action.reply_id
        assert request.selected_ui_ref.source_revision == action.source_revision
        assert request.user_message == ""
        system, user = fake.messages[-1]
        block = user["content"].split("=== D2_SELECTED_DOCUMENT_ACTION ===\n", 1)[1]
        task = json.loads(block.split("\n\n=== USER_MESSAGE ===", 1)[0])
        assert task == action.model_dump(mode="json")
        assert user["content"].endswith("=== USER_MESSAGE ===\n")
        assert request.model_view.approved_md_corpus in system["content"]
        assert "An empty USER_MESSAGE is expected for this click" in system["content"]
        assert "Do not answer the previous question again" in system["content"]
        assert "Use only its declared reply_id" not in system["content"]
        assert body["answer"] == prose
        with D2DialogueStore(db) as store:
            key = SessionKey(client_id="demo", sid=sid)
            saved = store.read_latest_completion(key)
            source = saved.response.resolved.information_blocks[0]
            assert (source.publication, source.content_ref, source.source_section_refs) == (
                "model_prose", action.content_ref, (action.section_ref,),
            )
            assert saved.response.resolved.ui_plan.source_content_ref == doc
            assert [button.button_id for button in saved.response.ui_projection.buttons] == ["consult"]
            pair = store.read(key).state.dialogue_pairs[-1]
            assert pair.patient_text is None
            assert pair.selected_ui_ref == request.selected_ui_ref
            assert pair.request_id == saved.request_id
            assert projected_history(store, key)[-1].assistant_text == prose
            assert saved.response.rendered_text == body["answer"]
        assert _body(send(client, **args), transport) == body
        assert len(fake.inputs) == index + 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_ordinary_content_omitted_mode_preserves_prose_without_source(http_env, transport):
    client, db, use_provider, _ = http_env
    prose = "Уточните, какой вопрос о клинике вас интересует."
    fake = use_provider(PromptProvider(_raw(prose)))
    send = post if transport == "json" else post_sse
    args = dict(sid="other-prose", request_id="other", q="Здравствуйте")
    body = _body(send(client, **args), transport)
    assert body["answer"] == prose
    assert fake.inputs[0].selected_document_action is None
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="other-prose"))
        block = saved.response.resolved.information_blocks[0]
        assert block.publication == "model_prose" and block.content_ref is None
    assert _body(send(client, **args), transport) == body
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("kind", ["content", "other"])
def test_explicit_authored_is_not_reinterpreted(kind):
    parsed = _parse(_legacy_raw(
        "Явно заданный authored текст.", kind=kind, content_realization="authored",
    ))
    assert parsed.request_understanding.requests[0].content_realization == "authored"


@pytest.mark.parametrize("mode", [None, "unknown-mode"])
def test_invalid_explicit_mode_is_not_repaired(mode):
    with pytest.raises(ValueError):
        _parse(_legacy_raw("Текст", kind="other", content_realization=mode))


def test_empty_other_keeps_its_existing_mode():
    parsed = _parse(_legacy_raw(None, kind="other"))
    part = parsed.request_understanding.requests[0]
    assert part.kind == "other" and part.content_realization == "authored"


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_missing_authored_source_publishes_gap_not_untrusted_live_prose(http_env, transport):
    client, db, use_provider, _ = http_env
    fake = use_provider(PromptProvider(_raw(
        "Явный authored без источника.", content_realization="authored",
    )))
    send = post if transport == "json" else post_sse
    response = send(client, sid="authored-other", request_id="authored", q="Вопрос о клинике")
    body = _body(response, transport)
    assert "Явный authored без источника." not in body["answer"]
    assert "недостаточно информации" in body["answer"]
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="authored-other")
        saved = store.read_latest_completion(key)
        assert saved.response.resolved.d2_request_parts[0].status == "unavailable"
        assert saved.response.resolved.d2_request_parts[0].failure_reason == "d2_content_source_missing"
        assert len(store.read(key).state.dialogue_pairs) == 1
        assert projected_history(store, key)[0].parts[0].status == saved.response.resolved.d2_request_parts[0].status
    assert len(fake.inputs) == 1


def test_off_topic_operation_produces_existing_boundary_without_live_prose(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(PromptProvider(json.dumps({"outcome": "dialogue", "blocks": [
        {"kind": "off_topic", "request_id": "r1"},
    ]})))
    response = post(client, sid="empty-other", request_id="empty", q="Не по теме клиники")
    assert response.status_code == 200
    assert response.get_json()["answer"].strip()
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="empty-other")
        saved = store.read_latest_completion(key)
        assert saved is not None
        assert not any(block.publication == "model_prose"
                       for block in saved.response.resolved.information_blocks)
        assert len(store.read(key).state.dialogue_pairs) == 1
        assert projected_history(store, key)[0].parts[0].status == saved.response.resolved.d2_request_parts[0].status
    assert len(fake.inputs) == 1


def test_document_boundaries_reject_before_generation(http_env):
    client, _, use_provider, _ = http_env
    fake = use_provider(PromptProvider(_raw("Ответ по материалу.", ref="implantation__faq__pain.md")))
    body = post(client, sid="doc-boundaries", request_id="first", q="Об анестезии").get_json()
    ref = body["ui"]["quick_replies"][0]["reply_id"]
    for request_id, extra in [
        ("stale", {"ui_revision": 0}),
        ("foreign", {"client_id": "nikadent"}),
        ("forged", {"ref": "implantation__faq__pain.md#never-shown"}),
    ]:
        args = dict(sid="doc-boundaries", request_id=request_id, q="", ref=ref,
                    ui_revision=body["revision"])
        args.update(extra)
        assert post(client, **args).status_code == 400
    assert len(fake.inputs) == 1


def test_volume_and_lead_actions_do_not_get_document_task(http_env):
    client, _, use_provider, _ = http_env
    fake = use_provider(PromptProvider(_price_raw("implantation")))
    first = post(client, sid="non-document", request_id="first", q="Цена имплантации").get_json()
    fake.raw = _price_raw("implantation", {
        "scope_commitment": "reported", "extent": "one_tooth",
        "tooth_count": 1, "jaw": "unknown", "continuity": "same",
    })
    response = post(client, sid="non-document", request_id="volume", q="",
                    ref="volume:implantation:one_tooth", ui_revision=first["revision"])
    assert response.status_code == 200
    body = response.get_json()
    assert fake.inputs[-1].selected_document_action is None
    assert len(fake.inputs) == 1  # The click is executed without a provider call.
    button = next(row for row in body["ui"]["buttons"] if row["action_kind"] == "cta")
    response = post(client, sid="non-document", request_id="lead", q="",
                    ref=f"button:{button['button_id']}", ui_revision=body["revision"])
    assert response.status_code == 200
    assert len(fake.inputs) == 1
