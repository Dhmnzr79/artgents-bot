"""Shared rolling demo budget, independent of dialogue sessions; offline."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from core.d2_demo_limits import admit_demo_call, D2DemoLimitReached

VISITOR = "11111111-1111-1111-1111-111111111111"


def call(conn, i, **kwargs):
    args = dict(sid="sid", request_id=str(i), visitor_id=VISITOR,
                peer_ip="ip", client_id="demo", now=100)
    args.update(kwargs)
    admit_demo_call(conn, **args)


def test_shared_visitor_questions_survive_sid_and_tenant_changes(tmp_path):
    path = tmp_path / "quota.sqlite"
    with sqlite3.connect(path) as conn:
        for i in range(30): call(conn, i, client_id="demo" if i % 2 else "demo_medical", sid=str(i))
    with sqlite3.connect(path) as conn:
        with pytest.raises(D2DemoLimitReached, match="demo_visitor_limit"):
            call(conn, 31, sid="fresh", client_id="demo_medical")
        # Another browser has its own question quota.
        call(conn, 31, visitor_id="22222222-2222-2222-2222-222222222222")
        assert conn.execute("SELECT COUNT(*) FROM demo_usage_attempt").fetchone()[0] == 31


def test_second_call_and_failed_retry_count_calls_not_questions(tmp_path):
    with sqlite3.connect(tmp_path / "quota.sqlite") as conn:
        for i in range(30): call(conn, i)
        call(conn, 29)  # Second call of the thirtieth question is allowed.
        call(conn, 29)  # Same failed request retry costs another model attempt.
        with pytest.raises(D2DemoLimitReached, match="demo_visitor_limit"): call(conn, 30)
        assert conn.execute("SELECT COUNT(*) FROM demo_usage_attempt").fetchone()[0] == 32
        with pytest.raises(ValueError, match="visitor_mismatch"):
            call(conn, 29, visitor_id="22222222-2222-2222-2222-222222222222")


def test_shared_4000_boundary_atomic_and_rolling(tmp_path):
    path = tmp_path / "quota.sqlite"
    with sqlite3.connect(path) as conn:
        call(conn, 0, now=0)
        row = conn.execute("SELECT * FROM demo_usage_attempt").fetchone()
        conn.executemany("INSERT INTO demo_usage_attempt VALUES(?,?,?,?,?,?)", [row] * 3998)
    def attempt(i):
        with sqlite3.connect(path) as conn:
            try: call(conn, i, now=100, peer_ip=str(i), client_id="demo_medical")
            except D2DemoLimitReached as exc: return exc.code
            return "admitted"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, (1, 2))) == ["admitted", "demo_daily_limit"]
    with sqlite3.connect(path) as conn:
        call(conn, 3, now=86400, peer_ip="new")
        assert conn.execute("SELECT COUNT(*) FROM demo_usage_attempt").fetchone()[0] == 4001


def test_visitor_window_and_ip_throttle(tmp_path, monkeypatch):
    import core.d2_demo_limits as quota
    with sqlite3.connect(tmp_path / "quota.sqlite") as conn:
        for i in range(30): call(conn, i, now=0)
        with pytest.raises(D2DemoLimitReached, match="demo_visitor_limit"): call(conn, 30, now=86399)
        call(conn, 30, now=86400)
        monkeypatch.setattr(quota, "RATE_LIMIT_MAX_PER_IP", 1)
        with pytest.raises(D2DemoLimitReached, match="demo_ip_limit"): call(conn, 31, now=86459)
        call(conn, 31, now=86460)
        assert "ip" not in [r[0] for r in conn.execute("SELECT peer_hash FROM demo_usage_attempt")]


def test_invalid_tenant_and_database_fail_closed(tmp_path):
    with sqlite3.connect(tmp_path / "quota.sqlite") as conn:
        with pytest.raises(ValueError, match="identity_invalid"): call(conn, 0, client_id="nikadent")
    path = tmp_path / "broken.sqlite"
    path.write_bytes(b"invalid sqlite")
    with sqlite3.connect(path) as conn:
        with pytest.raises(sqlite3.DatabaseError): call(conn, 0)


def test_visitor_last_question_is_atomic(tmp_path):
    path = tmp_path / "visitor.sqlite"
    with sqlite3.connect(path) as conn:
        for i in range(29): call(conn, i, now=0)
    def attempt(i):
        with sqlite3.connect(path) as conn:
            try: call(conn, i, sid=str(i), now=100)
            except D2DemoLimitReached as exc: return exc.code
            return "admitted"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, (30, 31))) == ["admitted", "demo_visitor_limit"]
