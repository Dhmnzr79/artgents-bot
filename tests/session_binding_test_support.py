"""Shared helpers for explicit session client binding in offline tests."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from session import session_client_scope


@contextmanager
def bound_client_session(client_id: str = "demo") -> Iterator[str]:
    """Explicit client scope for direct session reads/writes outside HTTP ingress."""
    with session_client_scope(client_id) as pack:
        yield pack


def read_target_runtime_session_for(
    sid: str,
    *,
    client_id: str = "demo",
):
    from core.target_runtime_session import read_target_runtime_session

    with session_client_scope(client_id):
        return read_target_runtime_session(sid)
