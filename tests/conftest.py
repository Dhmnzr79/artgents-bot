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
