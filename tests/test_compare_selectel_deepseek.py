"""Offline checks for the matched provider experiment; never call live API."""
from contextlib import closing
import sqlite3

import pytest
from scripts import compare_selectel_deepseek as pair
from scripts import selectel_d2_regression as observed


def test_hash_matches_content_contract_not_provider_specific_options():
    qwen = dict(model="qwen3.8-flash-next", messages=[{"role": "user", "content": "Один зуб"}],
                tools=[{"function": {"name": "show_price"}}], tool_choice="auto",
                temperature=0, max_completion_tokens=1536, timeout=20,
                extra_body={"enable_thinking": False})
    deepseek = {**qwen, "model": "deepseek-flash", "extra_body": {"thinking": {"type": "disabled"}}}
    assert pair.payload_hash(qwen) == pair.payload_hash(deepseek)
    for field, value in [("messages", [{"role": "user", "content": "Вся челюсть"}]),
                         ("tools", []), ("tool_choice", "none"), ("max_completion_tokens", 1000)]:
        assert pair.payload_hash(qwen) != pair.payload_hash({**deepseek, field: value})


def test_all_sqlite_state_restored_and_new_session_db_removed(tmp_path):
    root = tmp_path / "isolated"
    root.mkdir()
    path = root / "d2.sqlite"
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute('CREATE TABLE test(value INTEGER)')
        conn.execute('INSERT INTO test VALUES(1)')
    fixture = root / "fixtures" / "before"
    names = pair.save_state(root, fixture)
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute('INSERT INTO test VALUES(2)')
    extra = root / "sessions" / "demo.sqlite"
    extra.parent.mkdir()
    with closing(sqlite3.connect(extra)):
        pass
    pair.restore_state(root, fixture, names)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute('SELECT value FROM test').fetchall() == [(1,)]
    assert not extra.exists()


def test_each_arm_limit_is_sixteen_even_when_first_attempt_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(observed, "MAX_CALLS", 16)
    counter = []
    def fail(**kwargs):
        counter.append(1)
        raise RuntimeError('offline')
    for arm, (model, _) in pair.ARMS.items():
        monkeypatch.setattr(observed, "MODEL", model)
        budget = observed.BoundedCalls(tmp_path / (arm + '.json'), fail)
        for _ in range(16):
            with pytest.raises(RuntimeError):
                budget(model=model)
        with pytest.raises(ValueError, match='budget_exhausted'):
            budget(model=model)
    assert len(counter) == 32
