"""Offline controls and hard budget; no network or real tenant conversations."""
from copy import deepcopy

import pytest
from scripts import probe_selectel_thinking as probe
from scripts import selectel_d2_regression as observation


def original():
    return dict(model="qwen3.8-flash-next", messages=[{"role":"user", "content":"Один зуб"}],
        temperature=0, tools=[{"type":"function"}], tool_choice="auto", max_completion_tokens=1536,
        timeout=20, extra_body={"enable_thinking":False})


def test_changes_only_declared_settings_and_preserves_input():
    source = original()
    saved = deepcopy(source)
    variants = {m: probe.settings(source, m) for m in probe.MODES}
    assert source == saved
    for variant in variants.values():
        for key in ("model", "messages", "temperature", "tools", "tool_choice"):
            assert variant[key] == source[key]
        assert variant["timeout"] == 60
    assert variants["current_1536"]["max_completion_tokens"] == 1536
    assert variants["current_4096"]["max_completion_tokens"] == 4096
    assert variants["nested_off_4096"]["extra_body"] == {"chat_template_kwargs":{"enable_thinking":False}}
    assert variants["nested_on_4096"]["extra_body"] == {"chat_template_kwargs":{"enable_thinking":True}}
    for left, right, key in [("current_1536","current_4096","max_completion_tokens"),
                             ("current_4096","nested_off_4096","extra_body"),
                             ("nested_off_4096","nested_on_4096","extra_body")]:
        assert {k:v for k,v in variants[left].items() if k != key} == {
            k:v for k,v in variants[right].items() if k != key}


def test_rejects_unplanned_mode_or_unexpected_original_settings():
    with pytest.raises(ValueError, match="unapproved_mode"):
        probe.settings(original(), "auto_retry")
    with pytest.raises(ValueError, match="unexpected_original"):
        probe.settings({**original(), "extra_body":{}}, "nested_off_4096")


def test_eight_call_guard_counts_failed_attempts_and_blocks_ninth(tmp_path, monkeypatch):
    monkeypatch.setattr(observation, "MAX_CALLS", probe.MAX_CALLS)
    monkeypatch.setattr(observation, "MODEL", "qwen3.8-flash-next")
    calls = []
    def fail(**kwargs):
        calls.append(1)
        raise RuntimeError("offline")
    guarded = observation.BoundedCalls(tmp_path/"calls.json", fail)
    for _ in range(8):
        with pytest.raises(RuntimeError):
            guarded(model="qwen3.8-flash-next")
    with pytest.raises(ValueError, match="budget_exhausted"):
        guarded(model="qwen3.8-flash-next")
    assert len(calls) == 8 and len(guarded.rows) == 8
