"""Shared pytest fixtures for the test suite."""

from __future__ import annotations

import pytest

from orchestration import route_guards


@pytest.fixture(autouse=True)
def _reset_ip_rate_limit_buckets() -> None:
    """Isolate HTTP harness tests from module-global per-IP rate limit state."""

    with route_guards._IP_RATE_LOCK:
        route_guards._IP_RATE_BUCKETS.clear()
    yield
    with route_guards._IP_RATE_LOCK:
        route_guards._IP_RATE_BUCKETS.clear()


class RealProviderTransportBlockedError(RuntimeError):
    """Raised when a pytest test reaches the real provider transport (no owner-
    authorized LIVE gate open). See `_block_real_provider_transport` below."""


_REAL_TRANSPORT_BLOCKED_MESSAGE = (
    "BLOCKED: this test reached the real provider transport "
    "(llm.chat_client.chat.completions.create) during a normal pytest run. "
    "Inject a fake/recording backend instead of relying on real credentials being "
    "available -- having a real API key configured is never sufficient by itself. "
    "A deliberately owner-authorized live test must go through the existing, "
    "separate, explicit LIVE gate "
    "(core.target_prompt_cache_prewarm.LIVE_AUTHORIZED_ATTEMPT_ID) -- a pytest "
    "marker or fixture flag alone is not a valid bypass."
)


@pytest.fixture(autouse=True)
def _block_real_provider_transport(monkeypatch: pytest.MonkeyPatch):
    """Centralized, mandatory guard: block the real provider transport for every
    normal pytest test, even when real credentials (e.g. a local `.env` API key) are
    configured -- found necessary after PERF-4 development inadvertently made 230 real
    provider calls (see docs/evidence/performance/
    PERF4_DEVELOPMENT_LIVE_PROVIDER_CALLS_FORENSIC_AUDIT.md and TASK.md's PERF-4
    activation completion record).

    Patches the single shared choke point every provider call funnels through --
    `llm.chat_client.chat.completions.create` -- which `llm.chat_completions_create`,
    `ingress_gate._call_ingress_llm`, `core/turn_planner_llm.py`'s
    `_planner_chat_completions_create`, and `core/target_runtime_llm_backends.py`'s
    Composer/Verifier/Boundary backends all resolve to at call time (they call through
    various wrapper functions, but every one of those wrappers ultimately calls this
    same object's `.create`). Tests that inject their own fake/recording backend (the
    existing, correct pattern throughout this suite) are completely unaffected: a fake
    replaces the higher-level function entirely, so execution never reaches this
    choke point at all -- this guard only ever fires for a test that forgot to fake
    something and would otherwise have silently reached the real network.

    The only recognized bypass is the existing, separate, explicit LIVE gate already
    used by PERF-3 (`core.target_prompt_cache_prewarm.LIVE_AUTHORIZED_ATTEMPT_ID`) --
    a hardcoded module constant that requires an actual code change plus a fresh
    owner GO to ever be non-`None`. Neither an available API key nor a pytest
    marker/fixture flag is treated as authorization on its own.
    """
    import core.target_prompt_cache_prewarm as prewarm_module

    if prewarm_module.LIVE_AUTHORIZED_ATTEMPT_ID is not None:
        # An explicit owner-authorized live attempt is open via the existing PERF-3
        # gate -- that gate has its own exact-attempt-id/budget checks; do not also
        # intercept here.
        yield
        return

    import llm as llm_module

    def _blocked_create(*_args: object, **_kwargs: object):
        raise RealProviderTransportBlockedError(_REAL_TRANSPORT_BLOCKED_MESSAGE)

    monkeypatch.setattr(llm_module.chat_client.chat.completions, "create", _blocked_create)
    yield
