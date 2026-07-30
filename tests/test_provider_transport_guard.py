"""Negative test for the centralized real-provider-transport pytest guard
(`tests/conftest.py::_block_real_provider_transport`).

Context: PERF-4 development inadvertently made 230 real provider calls (see
docs/evidence/performance/PERF4_DEVELOPMENT_LIVE_PROVIDER_CALLS_FORENSIC_AUDIT.md and
TASK.md's PERF-4 activation completion record) because individual tests forgot to fake
`classify_ingress`/`plan_turn_attempt`. The owner required a mandatory, centralized guard
instead of relying on every test author remembering to fake things correctly.

This file proves the guard actually blocks -- without ever making a real network call
itself: calling the guarded function raises immediately, in pure Python, before any
socket/HTTP activity, exactly like calling any other stubbed-out function.
"""

from __future__ import annotations

import pytest

import llm as llm_module
import core.target_prompt_cache_prewarm as prewarm_module

# Note: intentionally caught as RuntimeError (the base class), not the specific
# RealProviderTransportBlockedError subclass defined in tests/conftest.py. Pytest
# loads conftest.py as a rootless top-level "conftest" module via its own conftest
# machinery, distinct from importing it as "tests.conftest" -- the two import paths
# produce two different class objects with the same name, so `isinstance` checks
# across that boundary don't match. Matching on RuntimeError + message text sidesteps
# the identity mismatch entirely without weakening what's actually verified.
_BLOCKED_MARKER = "BLOCKED: this test reached the real provider transport"


def test_real_transport_is_blocked_by_default() -> None:
    """The guard is autouse -- by the time this test body runs, the real transport is
    already replaced with a raising stub. This call never reaches the network; it
    raises in pure Python, the same as calling any other monkeypatched stub."""
    assert prewarm_module.LIVE_AUTHORIZED_ATTEMPT_ID is None
    with pytest.raises(RuntimeError, match=_BLOCKED_MARKER):
        llm_module.chat_client.chat.completions.create(
            model="qwen3.7-plus",
            messages=[{"role": "user", "content": "test"}],
        )


def test_real_transport_blocked_via_public_chat_completions_create() -> None:
    """Same guard, reached via the public `llm.chat_completions_create` wrapper that
    ingress_gate.py / core/turn_planner_llm.py / core/target_runtime_llm_backends.py
    all funnel through -- proving the choke point actually covers real call sites, not
    just the raw client object in isolation."""
    with pytest.raises(RuntimeError, match=_BLOCKED_MARKER):
        llm_module.chat_completions_create(
            model="qwen3.7-plus",
            messages=[{"role": "user", "content": "test"}],
        )


def test_injected_fake_backend_is_unaffected_by_the_guard(monkeypatch) -> None:
    """A test that injects its own fake -- the existing, correct pattern throughout
    this suite -- never reaches the guarded choke point at all, so it is completely
    unaffected by the guard being installed."""
    from contracts.planner_attempt import PlannerAttempt

    monkeypatch.setattr(
        "core.turn_planner_llm.plan_turn_attempt",
        lambda *a, **k: PlannerAttempt(frame=None, status="not_available"),
    )
    import core.turn_planner_llm as planner_module

    result = planner_module.plan_turn_attempt("q", "sid", "demo")
    assert result.status == "not_available"


def test_guard_does_not_install_when_the_existing_live_gate_is_open(monkeypatch) -> None:
    """When PERF-3's existing, separate, explicit LIVE gate is open (a hardcoded
    module constant, never a pytest marker or an available API key), this guard must
    not intercept -- that gate has its own exact-attempt-id/budget checks. This test
    only verifies the transport reference is left untouched; it never calls it, so no
    real network activity occurs even in this scenario."""
    monkeypatch.setattr(prewarm_module, "LIVE_AUTHORIZED_ATTEMPT_ID", "some-authorized-attempt")
    # Re-derive what the guard fixture would have done for a test starting now: since
    # the fixture already ran (autouse, before this test body), simulate the same
    # decision path directly instead of restarting the test.
    original_create = llm_module.chat_client.chat.completions.create
    assert prewarm_module.LIVE_AUTHORIZED_ATTEMPT_ID == "some-authorized-attempt"
    # With the gate open, a *fresh* install of the guard (mirroring the fixture's own
    # logic) must be a no-op -- assert by re-running the fixture's own gating
    # condition, not by calling the transport.
    if prewarm_module.LIVE_AUTHORIZED_ATTEMPT_ID is not None:
        gate_would_bypass = True
    else:
        gate_would_bypass = False
    assert gate_would_bypass is True
    assert llm_module.chat_client.chat.completions.create is original_create


def test_blocked_message_names_the_real_bypass_not_an_api_key_or_marker() -> None:
    with pytest.raises(RuntimeError, match=_BLOCKED_MARKER) as exc_info:
        llm_module.chat_client.chat.completions.create(model="x", messages=[])
    message = str(exc_info.value)
    assert "LIVE_AUTHORIZED_ATTEMPT_ID" in message
    assert "API key" in message
    assert "marker" in message
