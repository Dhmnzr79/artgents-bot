"""Real-client admission on actual JSON/SSE and native transport, offline only."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
import yaml

from core.d2_usage_limits import ClientUsageAdmission, ClientUsageLimits, ClientUsageLimitReached
from core.d2_live_provider import D2HttpProvider
from core.d2_dialogue_store import D2DialogueStore
from contracts.response_plan import SessionKey
from tests.d2_ci_http import http_env, click
from tests.test_d2_http_contract import post, post_sse, sse_events
from tests.test_d2_native_price_runtime import Transport, message, price
from tests.test_d2_price_cards import cards

VISITOR = "a" * 32
OTHER = "b" * 32


def settings(**changes):
    return ClientUsageLimits(visitor_messages_per_minute=10, ip_messages_per_minute=40,
        visitor_ai_questions_per_day=40, tenant_model_calls_per_day=1000,
        message_max_chars=1500, request_max_bytes=16384, visitor_leads_per_hour=3).model_copy(update=changes)


def admission(db, *, sid="chat", rid="turn", visitor=VISITOR, peer="ip", tenant="nikadent", now=100, **changes):
    return ClientUsageAdmission(db, limits=settings(**changes), client_id=tenant,
        sid=sid, request_id=rid, visitor_id=visitor, peer_ip=peer, clock=lambda: now)


def count(db, kind):
    with sqlite3.connect(db) as conn:
        return conn.execute("SELECT COUNT(*) FROM d2_usage_event WHERE kind=?", (kind,)).fetchone()[0]


def configure(tmp, **changes):
    p = tmp / "clients/nikadent/features.yaml"
    value = yaml.safe_load(p.read_text(encoding="utf-8"))
    value["usage_limits"].update(changes)
    p.write_text(yaml.safe_dump(value, allow_unicode=True), encoding="utf-8")


def wire(monkeypatch, *replies):
    transport = Transport(*(replies or (message("Ответ по материалам клиники."),)))
    monkeypatch.setattr("core.d2_http_adapter.D2HttpProvider",
                        lambda **kw: D2HttpProvider(transport=transport, **kw))
    return transport


def send(client, transport="json", **kwargs):
    response = (post if transport == "json" else post_sse)(client, client_id="nikadent", visitor_id=VISITOR, **kwargs)
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json() if transport == "json" else dict(sse_events(response))["ui"]
    return body


def test_durable_rolling_visitor_questions_across_chat_and_tenant(tmp_path):
    db = tmp_path / "usage.sqlite"
    for i in range(40):
        with sqlite3.connect(db) as conn:
            admission(conn, sid=f"chat{i}", now=100).model()
    with sqlite3.connect(db) as conn:
        with pytest.raises(ClientUsageLimitReached, match="visitor_ai_limit"):
            admission(conn, sid="new-chat", now=86499).model()
        admission(conn, sid="other", visitor=OTHER, now=101).model()
        admission(conn, sid="other-tenant", tenant="secondary", now=101).model()
        admission(conn, sid="next-day", now=86500).model()
    assert count(db, "model") == 43


def test_rate_windows_peer_backstop_and_fallback(tmp_path):
    with sqlite3.connect(tmp_path / "usage.sqlite") as conn:
        for i in range(10): admission(conn, sid=str(i)).message()
        with pytest.raises(ClientUsageLimitReached, match="visitor_rate_limit"):
            admission(conn, sid="fresh").message()
        admission(conn, sid="fresh", now=160).message()
        for i in range(40): admission(conn, sid=f"peer{i}", visitor=f"{i:032x}", peer="shared", now=200).message()
        with pytest.raises(ClientUsageLimitReached, match="ip_rate_limit"):
            admission(conn, sid="peer-more", visitor=OTHER, peer="shared", now=200).message()
        for i in range(10): admission(conn, sid=f"missing{i}", visitor=None, peer="missing", now=300).message()
        with pytest.raises(ClientUsageLimitReached, match="visitor_rate_limit"):
            admission(conn, sid="missing-more", visitor=None, peer="missing", now=300).message()


@pytest.mark.parametrize("kind,cap,code", [("model", 1, "tenant_ai_limit"), ("message", 1, "visitor_rate_limit"), ("lead", 1, "visitor_lead_limit")])
def test_atomic_parallel_admission(tmp_path, kind, cap, code):
    db = tmp_path / "usage.sqlite"
    with sqlite3.connect(db) as conn: admission(conn)
    def attempt(i):
        with sqlite3.connect(db) as conn:
            guard = admission(conn, sid=str(i), tenant_model_calls_per_day=cap,
                              visitor_messages_per_minute=cap, visitor_leads_per_hour=cap)
            try: getattr(guard, kind)()
            except ClientUsageLimitReached as exc: return exc.code
            return "accepted"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == sorted(["accepted", code])


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_quota_contacts_booking_and_free_replay(http_env, monkeypatch, transport):
    client, db, _, tmp = http_env
    configure(tmp, visitor_ai_questions_per_day=1)
    calls = wire(monkeypatch)
    first = send(client, transport, sid="first", request_id="one", q="Какие услуги есть?")
    assert send(client, transport, sid="first", request_id="one", q="Какие услуги есть?") == first
    limited = send(client, transport, sid="new-chat", request_id="two", q="А какие врачи?")
    assert "оставьте заявку" in limited["answer"].lower()
    assert "Телефон" in limited["answer"] and len(calls.calls) == 1
    assert not cards(limited)
    cta = next(b for b in limited["ui"]["buttons"] if b["action_kind"] == "cta")
    consent = click(client, limited, "button:" + cta["button_id"], client_id="nikadent",
        sid="new-chat", request_id="book", transport=transport, visitor_id=VISITOR)
    assert consent["ui"]["lead_consent"]
    named = click(client, consent, "lead:consent_accept", client_id="nikadent", sid="new-chat",
        request_id="accept", transport=transport, visitor_id=VISITOR)
    assert named["ui"]["lead_consent"] is None
    assert len(calls.calls) == 1 and count(db, "question") == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("budget", [1, 2])
def test_native_two_calls_one_question_no_partial_price(http_env, monkeypatch, transport, budget):
    client, db, _, tmp = http_env
    configure(tmp, tenant_model_calls_per_day=budget)
    calls = wire(monkeypatch, message(None, price("classic")), message("<NO_TEXT>"))
    body = send(client, transport, request_id="price", q="Сколько стоит имплантация?")
    assert count(db, "question") == 1 and count(db, "model") == budget
    assert len(calls.calls) == budget
    if budget == 1:
        assert "временно недоступна" in body["answer"] and not cards(body)
    else:
        assert cards(body)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_request_frequency_and_input_boundaries(http_env, monkeypatch, transport):
    client, db, _, tmp = http_env
    configure(tmp, visitor_messages_per_minute=1)
    calls = wire(monkeypatch)
    send(client, transport, request_id="first", q="Услуги?")
    response = (post if transport == "json" else post_sse)(client, client_id="nikadent", visitor_id=VISITOR,
        sid="new-chat", request_id="next", q="Врачи?")
    error = response.get_json() if transport == "json" else dict(sse_events(response))["error"]
    assert error["error"] == "visitor_rate_limit"
    assert len(calls.calls) == 1
    # Message length is checked before admission, not silently truncated.
    response = (post if transport == "json" else post_sse)(client, client_id="nikadent", visitor_id=VISITOR,
        sid="long", request_id="long", q="з" * 1501)
    error = response.get_json() if transport == "json" else dict(sse_events(response))["error"]
    assert error["error"] == "message_too_long"
    route = "/ask" if transport == "json" else "/ask/stream"
    response = client.post(route, data=json.dumps({"q":"x" * 17000}), content_type="application/json")
    assert response.status_code == 413 and response.get_json() == {"error":"request_too_large"}


def test_failed_attempt_is_charged_once_question_retry(http_env, monkeypatch):
    client, db, _, _ = http_env
    calls = wire(monkeypatch, RuntimeError("offline failure"), message("Повторный ответ."))
    kwargs = dict(client_id="nikadent", visitor_id=VISITOR, request_id="retry", q="Расскажите о клинике")
    assert post(client, **kwargs).status_code == 503
    assert post(client, **kwargs).status_code == 200
    assert count(db,"question") == 1 and count(db,"model") == 2 and len(calls.calls) == 2


def test_failed_same_request_retry_does_not_bypass_rate_limit(http_env, monkeypatch):
    client, db, _, tmp = http_env
    configure(tmp,visitor_messages_per_minute=1)
    calls=wire(monkeypatch,RuntimeError("offline failure"))
    kwargs=dict(client_id="nikadent",visitor_id=VISITOR,request_id="failed",q="Услуги клиники?")
    assert post(client,**kwargs).status_code==503
    retry=post(client,**kwargs)
    assert retry.status_code==429 and retry.get_json()["error"]=="visitor_rate_limit"
    assert len(calls.calls)==1


@pytest.mark.parametrize("value", [0, -1, True, "40", None])
def test_invalid_config_rejected(value):
    data=settings().model_dump(); data["visitor_ai_questions_per_day"]=value
    with pytest.raises(ValueError): ClientUsageLimits.model_validate(data)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_three_leads_hour_and_no_fourth_delivery(http_env, monkeypatch, transport):
    client, db, _, tmp = http_env
    configure(tmp, visitor_messages_per_minute=100, ip_messages_per_minute=100,
              visitor_ai_questions_per_day=1)
    wire(monkeypatch)
    smtp=[]
    def handle(*args, **kw):
        smtp.append(args)
        return {"delivery":"email"},200
    monkeypatch.setattr("core.d2_lead_bridge.handle_lead",handle)
    first=send(client,transport,sid="consume",request_id="ai",q="Расскажите о клинике")
    for i in range(4):
        sid=f"booking-{i}"
        body=send(client,transport,sid=sid,request_id="quota",q="Хочу записаться")
        cta=next(b for b in body["ui"]["buttons"] if b["action_kind"]=="cta")
        body=click(client,body,"button:"+cta["button_id"],client_id="nikadent",sid=sid,
                   request_id="book",transport=transport,visitor_id=VISITOR)
        body=click(client,body,"lead:consent_accept",client_id="nikadent",sid=sid,
                   request_id="accept",transport=transport,visitor_id=VISITOR)
        send(client,transport,sid=sid,request_id="name",q="Анна")
        body=send(client,transport,sid=sid,request_id="phone",q="+79001234567")
        assert body["lead_effect"]["status"] == ("sent" if i<3 else "failed")
        assert send(client,transport,sid=sid,request_id="phone",q="+79001234567") == body
    assert len(smtp)==3 and count(db,"lead")==3 and count(db,"model")==1


def test_lead_window_rolling_and_failed_attempt_dedup(tmp_path):
    with sqlite3.connect(tmp_path / "usage.sqlite") as conn:
        for i in range(3): admission(conn, rid=str(i), now=100).lead()
        with pytest.raises(ClientUsageLimitReached, match="visitor_lead_limit"):
            admission(conn, rid="fourth", now=3699).lead()
        admission(conn, rid="fourth", now=3700).lead()
        with pytest.raises(ClientUsageLimitReached, match="lead_already_attempted"):
            admission(conn, rid="0", now=10000).lead()


def test_tenant_denial_does_not_charge_new_visitor_and_window_recovers(tmp_path):
    with sqlite3.connect(tmp_path / "usage.sqlite") as conn:
        admission(conn, tenant_model_calls_per_day=1).model()
        with pytest.raises(ClientUsageLimitReached, match="tenant_ai_limit"):
            admission(conn, visitor=OTHER, sid="other", tenant_model_calls_per_day=1).model()
        assert conn.execute("SELECT COUNT(*) FROM d2_usage_event WHERE kind='question'").fetchone()[0] == 1
        admission(conn, visitor=OTHER, sid="other", tenant_model_calls_per_day=1, now=86500).model()


def test_hashed_buckets_no_contact_or_input_in_ledger(tmp_path):
    with sqlite3.connect(tmp_path / "usage.sqlite") as conn:
        guard=admission(conn, peer="203.0.113.17")
        guard.message();guard.model();guard.lead()
        dump="\n".join(conn.iterdump())
        assert VISITOR not in dump and "203.0.113.17" not in dump
        assert "phone" not in dump and "user_message" not in dump


@pytest.mark.parametrize("route", ["/ask", "/ask/stream", "/lead"])
def test_oversized_body_returns_bounded_cors_error_before_audit(http_env, monkeypatch, route):
    client,db,_,_=http_env
    audits=[]
    monkeypatch.setattr("core.client_host.APP_ENV", "prod")
    monkeypatch.setattr("app._audit_d2_request", lambda *args: audits.append(args))
    response=client.post(route,data=json.dumps({"q":"x"*17000}),content_type="application/json",
        base_url="https://nikadent.bot.artgents.ru",headers={"Origin":"https://nikadent41.ru"})
    assert response.status_code == 413
    assert response.headers["Access-Control-Allow-Origin"] == "https://nikadent41.ru"
    assert not audits and not db.exists()


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_code_only_price_click_free_after_ai_budget_and_preserves_scope(http_env,monkeypatch,transport):
    client,db,_,tmp=http_env
    configure(tmp, tenant_model_calls_per_day=2)
    calls=wire(monkeypatch,message(None,{"target":{"type":"topic","id":"prosthetics"}}),message("<NO_TEXT>"))
    initial=send(client,transport,sid="scope",request_id="price",q="Цена имплантации одного зуба")
    with D2DialogueStore(db) as store:
        before=store.read(SessionKey(client_id="nikadent",sid="scope")).state
    limited=send(client,transport,sid="scope",request_id="blocked",q="А сроки?")
    with D2DialogueStore(db) as store:
        after=store.read(SessionKey(client_id="nikadent",sid="scope")).state
    assert before.discussion_request_id == after.discussion_request_id
    assert after.terminal_state == before.terminal_state
    choice=next(q for q in initial["ui"]["quick_replies"] if q["reply_id"].startswith("volume:"))
    changed=click(client,initial,choice["reply_id"],client_id="nikadent",sid="scope",request_id="volume",
                  transport=transport,visitor_id=VISITOR)
    assert len(calls.calls)==2 and cards(changed)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_untrusted_forwarded_header_does_not_reset_ip_bucket(http_env,monkeypatch,transport):
    client,db,_,tmp=http_env
    configure(tmp,ip_messages_per_minute=1)
    calls=wire(monkeypatch)
    route="/ask" if transport=="json" else "/ask/stream"
    for i,visitor in enumerate((VISITOR,OTHER)):
        response=client.post(route,json={"client_id":"nikadent","visitor_id":visitor,
            "sid":f"chat{i}","request_id":"q","q":"Какие услуги есть?"},
            headers={"X-Forwarded-For":f"203.0.113.{i+1}"})
        payload=response.get_json() if transport=="json" else dict(sse_events(response)).get("error",{})
        if i==0:
            assert response.status_code==200
        else:
            assert payload["error"]=="ip_rate_limit"
    assert len(calls.calls)==1
