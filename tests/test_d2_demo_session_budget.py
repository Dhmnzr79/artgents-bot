"""Current native transport and session quota boundary; no network."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from core.d2_demo_limits import admit_demo_call, D2DemoLimitReached
from core.d2_live_provider import D2HttpProvider
from tests.d2_ci_http import http_env, send
from tests.test_d2_native_price_runtime import Transport, message, price
from tests.test_d2_http_contract import post, post_sse, sse_events


def test_demo_tenants_have_separate_session_budgets_even_in_shared_store(tmp_path):
    with sqlite3.connect(tmp_path/'limits.sqlite')as conn:
        for _ in range(30):admit_demo_call(conn,sid='same',peer_ip='local',now=100,client_id='demo')
        with pytest.raises(D2DemoLimitReached,match='demo_session_limit'):
            admit_demo_call(conn,sid='same',peer_ip='local',now=100,client_id='demo')
        admit_demo_call(conn,sid='same',peer_ip='local',now=100,client_id='demo_medical')


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_thirtieth_call_completes_price_replay_is_free_next_denied(http_env, transport):
    client, db, use, _ = http_env
    def admit():
        with sqlite3.connect(db) as conn:
            admit_demo_call(conn, sid="budget", peer_ip="test")
    for _ in range(28): admit()
    wire = Transport(message(None, price()), message("<NO_TEXT>"))
    use(D2HttpProvider(transport=wire, admission=admit))
    args = dict(sid="budget", request_id="price", q="Price")
    body = send(client, transport, **args)
    assert body["ui"]["projected_commercial_ids"]["price_offer_ids"]
    assert send(client, transport, **args) == body
    assert len(wire.calls) == 2
    denied = (post if transport == "json" else post_sse)(client, sid="budget", request_id="next", q="Warranty")
    if transport == "json":
        assert denied.status_code == 429
        assert denied.get_json() == {"error": "demo_session_limit"}
    else:
        assert dict(sse_events(denied))["error"] == {"error": "demo_session_limit"}
    assert len(wire.calls) == 2
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM d2_demo_model_attempt").fetchone()[0] == 30


def test_session_boundary_atomic_and_persistent(tmp_path):
    path = tmp_path / "budget.sqlite"
    with sqlite3.connect(path) as conn:
        for _ in range(29): admit_demo_call(conn, sid="same", peer_ip="test", now=0)
    def attempt(_):
        with sqlite3.connect(path) as conn:
            try: admit_demo_call(conn, sid="same", peer_ip="test", now=90000)
            except D2DemoLimitReached as exc: return exc.code
            return "admitted"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == ["admitted", "demo_session_limit"]
