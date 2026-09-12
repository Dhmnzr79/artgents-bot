from __future__ import annotations

from typing import Any


def decision_dump(decision) -> dict[str, Any] | None:
    return decision.model_dump() if decision is not None else None


def get_last_content_ui_payload_compat(sid: str) -> dict | None:
    import session as session_mod

    fn = getattr(session_mod, "get_last_content_ui_payload", None)
    if callable(fn):
        return fn(sid)
    return None
