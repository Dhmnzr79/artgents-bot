"""C1: explicit commercial scope and existing clarification through JSON/SSE."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import TypeAdapter

from contracts.d2_dialogue_result import ClarifiedOperation, validate_d2_payload
from contracts.d2_session_context import D2SessionActivity
from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import build_d2_d1r_messages
from tests.d2_ci_http import FakeProvider, http_env, raw, send
from tests.test_d2_http_contract import post, post_sse
from tests.test_d2_live_provider_offline import _request


def fact(fact_id="installment_12", target=None, request_id="r1"):
    return {"kind": "commercial_fact", "request_id": request_id,
            "fact_ids": [fact_id], "target": target or {"type": "clinic"}}


def pending():
    return {**fact(target={"type": "unresolved"}),
            "clarification": {"missing": "service", "choices": ["classic", "caries"]}}


def saved(db, sid="commercial-scope"):
    with D2DialogueStore(db) as store:
        return store.read_latest_completion(SessionKey(client_id="demo", sid=sid)).response.resolved


@pytest.mark.parametrize("target", ["omitted", None, {"type": "unresolved"}])
def test_completed_commercial_scope_is_never_implicit(target):
    block = fact()
    if target == "omitted":
        block.pop("target")
    else:
        block["target"] = target
    with pytest.raises(ValueError):
        validate_d2_payload({"outcome": "dialogue", "blocks": [block]}, active_service_ids=frozenset({"classic"}))


@pytest.mark.parametrize("clarify", [False, True])
def test_empty_commercial_task_rejected_in_both_forms(clarify):
    block = pending() if clarify else fact()
    block["fact_ids"] = []
    with pytest.raises(ValueError, match="commercial_task_required"):
        validate_d2_payload({"outcome": "dialogue", "blocks": [block]}, active_service_ids=frozenset({"classic", "caries"}))


def test_sent_schema_requires_explicit_scope_and_storage_retains_pending_subject():
    system, _ = build_d2_d1r_messages(_request())
    text = system["content"].split("=== D2_RESULT_SCHEMA ===\n", 1)[1]
    schema = json.JSONDecoder().raw_decode(text)[0]
    direct = schema["$defs"]["CommercialOperation"]
    assert "target" in direct["required"]
    assert set(direct["properties"]["target"]["discriminator"]["mapping"]) == {"clinic", "service", "topic", "unresolved"}
    assert "PendingCommercialOperation" not in schema["$defs"]
    clarification = direct["properties"]["clarification"]["anyOf"][0]
    assert set(clarification["discriminator"]["mapping"]) == {"service", "term"}
    assert TypeAdapter(ClarifiedOperation).validate_python(pending()).fact_ids == ("installment_12",)


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("fact_id,target,expected", [
    ("installment_12", {"type": "clinic"}, "до 12 месяцев"),
    ("installment_12", {"type": "service", "id": "classic"}, "до 12 месяцев"),
    ("installment_12", {"type": "service", "id": "caries"}, "рассрочка не предоставляется"),
    ("installment_12", {"type": "service", "id": "tooth_extraction"}, "рассрочка не предоставляется"),
    ("free_implant_consult", {"type": "topic", "id": "implantation"}, "КТ при необходимости оплачивается отдельно"),
    ("professional_whitening_discount", {"type": "service", "id": "professional_whitening"}, "скидка 10%"),
])
def test_explicit_scope_preserves_exact_policy_and_replay(http_env, transport, fact_id, target, expected):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(fact(fact_id, target))))
    args = dict(sid="commercial-scope", request_id="scope", q="Условия для указанной услуги?")
    body = send(client, transport, **args)
    assert expected in body["answer"]
    assert "недостаточно информации" not in body["answer"]
    result = saved(db)
    assert result.d2_result_status == "complete"
    if target.get("id") in {"caries", "tooth_extraction"}:
        assert result.finalized_commercial_ids.requested_fact_ids == ()
    else:
        assert result.finalized_commercial_ids.requested_fact_ids == (fact_id,)
    assert send(client, transport, **args) == body
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_compound_whitening_price_and_own_scoped_discount_have_no_false_gap(http_env, transport):
    client, db, use, _ = http_env
    target = {"type": "service", "id": "professional_whitening"}
    fake = use(FakeProvider(raw({"kind": "price", "request_id": "r1", "target": target},
                               fact("professional_whitening_discount", target, "r2"))))
    body = send(client, transport, sid="commercial-scope", q="Цена отбеливания и скидка?")
    assert "18\u00a0000" in body["answer"]
    assert "скидка 10%" in body["answer"]
    assert "недостаточно информации" not in body["answer"]
    assert saved(db).d2_result_status == "complete"
    assert saved(db).finalized_commercial_ids.requested_fact_ids == ("professional_whitening_discount",)
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_missing_commercial_scope_is_not_repaired_from_neighbor_price(http_env, transport):
    client, db, use, _ = http_env
    incomplete = fact("professional_whitening_discount", request_id="r2")
    incomplete.pop("target")
    fake = use(FakeProvider(raw({"kind": "price", "request_id": "r1",
                                "target": {"type": "service", "id": "professional_whitening"}}, incomplete)))
    response = (post if transport == "json" else post_sse)(
        client, sid="commercial-scope", q="Цена отбеливания и скидка?")
    if transport == "json":
        assert response.status_code == 400
    else:
        assert "event: error" in response.get_data(as_text=True)
    with D2DialogueStore(db) as store:
        assert store.read_latest_completion(SessionKey(client_id="demo", sid="commercial-scope")) is None
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_unclear_term_keeps_commercial_subject_and_independent_address(http_env, transport):
    client, db, use, _ = http_env
    question = pending()
    question["clarification"] = {"missing": "term", "choices": []}
    fake = use(FakeProvider(raw(question, {"kind": "contact", "request_id": "r2",
                                         "contact_fields": ["contact_address"]})))
    first = send(client, transport, sid="commercial-scope", request_id="term", q="Рассрочка на эту штуку и адрес?")
    assert "Тверская" in first["answer"]
    assert "Уточните" in first["answer"]
    assert "до 12 месяцев" not in first["answer"]
    assert first["ui"]["quick_replies"] == []
    fake.raw = raw(fact(target={"type": "service", "id": "classic"}))
    second = send(client, transport, sid="commercial-scope", request_id="term-reply", q="Имел в виду классическую имплантацию")
    assert "до 12 месяцев" in second["answer"]
    assert fake.inputs[-1].context.ordinary.clarify_task.fact_ids == ("installment_12",)
    assert fake.inputs[-1].context.ordinary.clarify_task.clarification.missing == "term"
    assert len(fake.inputs) == 2


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("reply", ["click", "text", "topic_change"])
def test_pending_commercial_uses_existing_task_and_one_owner(http_env, transport, reply):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(pending())))
    first = send(client, transport, sid="commercial-scope", request_id="pending", q="А на эту услугу рассрочка?")
    assert {r["reply_id"] for r in first["ui"]["quick_replies"]} == {"service:classic", "service:caries"}
    with D2DialogueStore(db) as store:
        task = store.read(SessionKey(client_id="demo", sid="commercial-scope")).state.clarify_task
        assert task.fact_ids == ("installment_12",)
    assert "до 12 месяцев" not in first["answer"]
    args = dict(sid="commercial-scope", request_id="complete")
    if reply == "click":
        args.update(q="", ref="service:caries", ui_revision=first["revision"])
    elif reply == "text":
        fake.raw = raw(fact(target={"type": "service", "id": "caries"}))
        args.update(q="Я про кариес")
    else:
        fake.raw = raw({"kind": "contact", "request_id": "r1", "contact_fields": ["contact_address"]})
        args.update(q="Лучше скажите адрес")
    second = send(client, transport, **args)
    if reply != "topic_change":
        assert "рассрочка не предоставляется" in second["answer"]
        assert "до 12 месяцев" not in second["answer"]
    else:
        assert "Тверская" in second["answer"]
        assert "рассроч" not in second["answer"].lower()
    assert len(fake.inputs) == (1 if reply == "click" else 2)
    if reply != "click":
        assert fake.inputs[-1].context.ordinary.clarify_task.fact_ids == ("installment_12",)
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="commercial-scope")).state.clarify_task is None
    assert send(client, transport, **args) == second
    assert len(fake.inputs) == (1 if reply == "click" else 2)


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("fault", ["forged", "stale", "foreign", "expired"])
def test_commercial_pending_ui_keeps_authenticity_and_ttl(http_env, transport, fault):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(pending())))
    first = send(client, transport, sid="commercial-scope", q="Уточните рассрочку")
    args = dict(sid="commercial-scope", request_id="invalid", q="", ref="service:caries", ui_revision=first["revision"])
    if fault == "forged":
        args["ref"] = "service:veneers"
    elif fault == "stale":
        args["ui_revision"] += 1
    elif fault == "foreign":
        args["client_id"] = "nikadent"
    else:
        key = SessionKey(client_id="demo", sid="commercial-scope")
        with D2DialogueStore(db) as store:
            record = store.read(key)
            expired = record.model_copy(update={"activity": D2SessionActivity(
                session_key=key, last_user_turn_at=datetime.now(timezone.utc) - timedelta(hours=1))})
            with store._connection:
                store._connection.execute("UPDATE d2_dialogue SET payload=? WHERE client_id=? AND sid=?",
                    (expired.model_dump_json(), "demo", "commercial-scope"))
    response = (post if transport == "json" else post_sse)(client, **args)
    if transport == "json":
        assert response.status_code == 400
    else:
        assert "event: error" in response.get_data(as_text=True)
    assert len(fake.inputs) == 1
