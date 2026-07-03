"""Unit tests for conditional retrieval query rewrite."""

from __future__ import annotations

import pytest

from core.rewrite_policy import rewrite_skip_reason


class _FakeMem:
    _store: dict[str, dict] = {}

    @classmethod
    def set_hist(cls, sid: str, hist: list[dict]) -> None:
        cls._store[sid] = {"hist": hist}

    @classmethod
    def clear(cls) -> None:
        cls._store.clear()


@pytest.fixture(autouse=True)
def _patch_mem(monkeypatch):
    import core.rewrite_policy as rp

    _FakeMem.clear()
    monkeypatch.setattr(rp, "mem_get", lambda sid: _FakeMem._store.get(sid, {}))
    yield
    _FakeMem.clear()


def test_skip_no_history():
    assert rewrite_skip_reason("s1", "а сколько стоит", client_id="demo") == "no_history"


def test_skip_clear_price_intent():
    _FakeMem.set_hist("s1", [{"role": "user", "content": "имплантация"}])
    assert (
        rewrite_skip_reason("s1", "сколько стоит имплантация", client_id="demo")
        == "clear_intent_regex"
    )


def test_skip_self_contained_long():
    _FakeMem.set_hist("s1", [{"role": "user", "content": "имплантация"}])
    q = "чем отличается имплантация от мостовидного протеза подробно"
    assert rewrite_skip_reason("s1", q, client_id="demo") == "self_contained_long"


def test_run_rewrite_on_pronoun():
    _FakeMem.set_hist("s1", [{"role": "user", "content": "имплантация"}])
    assert rewrite_skip_reason("s1", "а сколько это стоит", client_id="demo") is None


def test_run_rewrite_on_continuation():
    _FakeMem.set_hist("s1", [{"role": "user", "content": "имплантация"}])
    assert rewrite_skip_reason("s1", "а если не приживётся", client_id="demo") is None
