"""No networking: check the diagnostic budget, accounting and no-resume gates."""
import json
from types import SimpleNamespace as NS

import pytest
from scripts import selectel_d2_regression as probe


def reply():
    return NS(model="qwen-3.8-flash-next-fp8", choices=[NS(finish_reason="stop",
        message=NS(tool_calls=[]))], usage=NS(prompt_tokens=100, completion_tokens=20,
        prompt_tokens_details=NS(cached_tokens=80),
        completion_tokens_details=NS(reasoning_tokens=15)))


def test_calls_reserved_before_transport_and_failed_attempt_consumes_budget(tmp_path):
    ledger = tmp_path / "calls.json"
    seen = []
    def fail(**kwargs):
        seen.append(kwargs)
        assert json.loads(ledger.read_text())[0]["status"] == "reserved"
        raise RuntimeError("synthetic failure")
    calls = probe.BoundedCalls(ledger, fail)
    with pytest.raises(RuntimeError):
        calls(model=probe.MODEL)
    calls.transport = lambda **kwargs: reply()
    for _ in range(probe.MAX_CALLS - 1):
        calls(model=probe.MODEL)
    with pytest.raises(ValueError, match="budget_exhausted"):
        calls(model=probe.MODEL)
    assert len(calls.rows) == 32
    assert calls.rows[0]["error_type"] == "RuntimeError"
    with pytest.raises(ValueError, match="ledger_refused"):
        probe.BoundedCalls(ledger, fail)


def test_cache_reasoning_counted_once_and_no_credentials_saved(tmp_path):
    calls = probe.BoundedCalls(tmp_path / "calls.json", lambda **kwargs: reply())
    calls(model=probe.MODEL, messages=[{"role": "user", "content": "private-marker"}],
          extra_body={"enable_thinking": False})
    row = calls.rows[0]
    assert (row["prompt_tokens"], row["cached_tokens"], row["uncached_tokens"]) == (100, 80, 20)
    assert row["reasoning_tokens"] == 15
    assert row["estimated_rub"] == pytest.approx((80*2.09 + 20*20.85 + 20*61.3)/1_000_000)
    assert "private-marker" not in calls.path.read_text()
    with pytest.raises(ValueError, match="unexpected_model"):
        calls(model="other")
    assert len(calls.rows) == 1


def test_default_prepares_only_and_refuses_existing_run(monkeypatch, tmp_path):
    monkeypatch.setattr(probe, "OUTPUT", tmp_path / "prepared")
    assert probe.run() == {"prepared": True, "provider_calls": 0}
    with pytest.raises(ValueError, match="existing_run_refused"):
        probe.run(live=True)
