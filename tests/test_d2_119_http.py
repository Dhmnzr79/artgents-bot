"""D2-119 mechanics through real local HTTP; fake output is not live-model evidence."""
import json

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from tests.test_d2_document_click_task_http import PromptProvider, _body
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from tests.test_d2_sim2_dialogues import raw, price, explanation


UNKNOWN = "Ничего страшного. На консультации врач поможет разобраться с объёмом лечения."


def replies(body):
    return [r["reply_id"] for r in body["ui"]["quick_replies"]]


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_unknown_acknowledges_without_price_model_or_lead_and_retains_context(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price())))
    send = post if transport == "json" else post_sse
    first = _body(send(client, request_id="overview", q="Цена имплантации?"), transport)
    args = dict(request_id="unknown", q="", ref="volume:implantation:unknown", ui_revision=first["revision"])
    answer = _body(send(client, **args), transport)
    assert answer["answer"] == UNKNOWN
    assert replies(answer) == []
    assert any(b["label"] == "Записаться на консультацию" for b in answer["ui"]["buttons"])
    assert _body(send(client, **args), transport) == answer
    assert len(fake.inputs) == 1
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="cp6a")
        saved = store.read_latest_completion(key)
        assert saved.lead_effect.status == "not_requested"
        assert saved.response.resolved.d2_price_block is None
        assert not store.read(key).state.clarify_pending
    fake.raw = raw(explanation("Срок зависит от выбранного метода."))
    _body(send(client, request_id="next", q="А сроки?"), transport)
    scope = fake.inputs[-1].context.ordinary.discussion_scope
    assert scope.topic_id == "implantation" and scope.volume.extent == "unknown"


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_price_click_consumes_only_clicked_service_button_and_survives_history(http_env, transport):
    client, db, use, tmp_path = http_env
    config = tmp_path / "clients/demo/target_response/d2_commercial.json"
    catalog = json.loads(config.read_text(encoding="utf-8"))
    catalog["service_profiles"].append({"service_id": "all_on_4", "price_detail_ids": ["includes", "stages"]})
    config.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    fake = use(FakeProvider(raw(price("classic", "service"))))
    send = post if transport == "json" else post_sse
    first = _body(send(client, request_id="price", q="Цена классической имплантации?"), transport)
    both = ["price_detail:includes", "price_detail:stages"]
    assert replies(first) == both
    args = dict(request_id="includes", q="", ref=both[0], ui_revision=first["revision"])
    includes = _body(send(client, **args), transport)
    assert replies(includes) == [both[1]]
    assert len(fake.inputs) == 1
    assert _body(send(client, **args), transport) == includes
    rejected = send(client, request_id="stale", q="", ref=both[0], ui_revision=first["revision"])
    if transport == "json":
        assert rejected.status_code == 400
    else:
        assert "error" in dict(sse_events(rejected))
    assert len(fake.inputs) == 1
    for i in range(4):
        fake.raw = raw({"request_id": "r1", "kind": "contact", "contact_fields": ["contact_phone"]})
        _body(send(client, request_id=f"contact{i}", q="Телефон?"), transport)
    fake.raw = raw(price("classic", "service"))
    same = _body(send(client, request_id="same", q="Напомните цену"), transport)
    assert replies(same) == [both[1]]
    calls = len(fake.inputs)
    stages = _body(send(client, request_id="stages", q="", ref=both[1], ui_revision=same["revision"]), transport)
    assert replies(stages) == [] and len(fake.inputs) == calls
    assert "Хирургический этап" in stages["answer"]
    fake.raw = raw(price("all_on_4", "service"))
    new = _body(send(client, request_id="new-service", q="А All-on-4?"), transport)
    assert replies(new) == both
    with D2DialogueStore(db) as store:
        state = store.read(SessionKey(client_id="demo", sid="cp6a")).state
        assert set(state.accumulated_shown_ids.secondary_ref_ids).issuperset({
            "price_detail_clicked:classic:includes", "price_detail_clicked:classic:stages"})
        assert not set(both).intersection(state.accumulated_shown_ids.secondary_ref_ids)


@pytest.mark.parametrize("extra", [{"content_realization": "authored"}, {"content_realization": "model_prose"},
    {"content_fallback_section_ref": "a:korotko"}])
def test_removed_ordinary_modes_rejected_without_repair(http_env, extra):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(explanation("Текст модели", content_ref="implantation__faq__pain.md", **extra))))
    response = post(client, q="Об обезболивании")
    assert response.status_code == 400 and len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_empty_prose_never_recovers_document_text(http_env, transport):
    client, db, use, _ = http_env
    use(FakeProvider(raw(explanation(" ", content_ref="implantation__faq__pain.md",
        content_section_refs=["a:kakuyu-anesteziyu-ispolzuyut"])) ))
    send = post if transport == "json" else post_sse
    answer = _body(send(client, q="Об обезболивании"), transport)
    assert "{#" not in answer["answer"]
    with D2DialogueStore(db) as store:
        resolved = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved
        assert resolved.information_blocks == ()
        assert resolved.d2_request_parts[0].status == "unavailable"


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_admin_executes_clinic_contact_and_prompt_distinguishes_fear(http_env, transport):
    client, db, use, _ = http_env
    fake = use(PromptProvider(raw(outcome="admin")))
    send = post if transport == "json" else post_sse
    answer = _body(send(client, q="После операции сильно болит, опухло и кровь. А сколько стоит лечение?"), transport)
    assert "Такой вопрос лучше решить напрямую с клиникой" in answer["answer"]
    assert "Если ситуация срочная" in answer["answer"]
    assert "+7" in answer["answer"]
    assert replies(answer) == [] and answer["ui"]["buttons"] == []
    prompt = fake.messages[0][0]["content"]
    assert "current personal medical problem" in prompt and "Fear of future pain" in prompt
    assert "never numeric list positions" in prompt
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("policy_ids", [["no_pediatric_dentistry"], [0]])
def test_policy_uses_exact_key_never_guesses_numeric_id(http_env, policy_ids):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw({"request_id": "r1", "kind": "clinic_policy", "policy_ids": policy_ids,
        "age_group": "child", "context": "current_care"})))
    response = post(client, q="Можно записать ребёнка 12 лет?")
    assert response.status_code == (200 if isinstance(policy_ids[0], str) else 400)
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_old_authored_receipt_rejected_without_reset_or_lead_loss(http_env, transport):
    from lead_interrupt import LEAD_PENDING_ANSWER_REF
    from session import capture_lead_session_row, session_client_scope
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(explanation("Объяснение из базы.", content_ref="implantation__faq__pain.md",
        target={"type": "service", "id": "classic"}))))
    assert post(client, request_id="source", q="Больно ли?").status_code == 200
    fake.raw = raw({"kind": "booking", "request_id": "r1", "age_group": "adult"})
    assert post(client, request_id="book", q="Хочу записаться").status_code == 200
    assert post(client, request_id="name", q="Анна").status_code == 200
    paused = post(client, request_id="pause", q="А адрес клиники?").get_json()
    assert any(r["reply_id"] == LEAD_PENDING_ANSWER_REF for r in paused["ui"]["quick_replies"])
    with session_client_scope("demo"):
        lead_before = capture_lead_session_row("cp6a")
        assert json.loads(lead_before[0])["profile"]["name"] == "Анна"
    with D2DialogueStore(db) as store:
        connection = store._connection
        payload = json.loads(connection.execute("SELECT payload FROM d2_turn_request WHERE sid='cp6a' AND request_id='source'").fetchone()[0])
        payload["response"]["resolved"]["information_blocks"][0]["publication"] = "authored"
        with connection:
            connection.execute("UPDATE d2_turn_request SET payload=? WHERE sid='cp6a' AND request_id='source'", (json.dumps(payload, ensure_ascii=False),))
        before = connection.execute("SELECT request_id,status,payload FROM d2_turn_request WHERE sid='cp6a' ORDER BY rowid").fetchall()
        state_before = connection.execute("SELECT payload FROM d2_dialogue WHERE sid='cp6a'").fetchone()
    calls = len(fake.inputs)
    send = post if transport == "json" else post_sse
    failed = send(client, request_id="next", q="", ref=LEAD_PENDING_ANSWER_REF, ui_revision=paused["revision"])
    if transport == "json":
        assert failed.status_code == 400 and failed.get_json()["error"] == "d2_invalid_turn"
    else:
        assert dict(sse_events(failed))["error"]["error"] == "d2_invalid_turn"
    assert len(fake.inputs) == calls
    with session_client_scope("demo"):
        assert capture_lead_session_row("cp6a") == lead_before
    with D2DialogueStore(db) as store:
        assert store._connection.execute("SELECT request_id,status,payload FROM d2_turn_request WHERE sid='cp6a' ORDER BY rowid").fetchall() == before
        assert store._connection.execute("SELECT payload FROM d2_dialogue WHERE sid='cp6a'").fetchone() == state_before
