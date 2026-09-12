"""Session-bound pending price-service clarification (BOT-CLEANUP-UI-SERVICE-FLOW-1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from contracts.response_schema import ResponseSchemaBundle
from core.target_client_data import match_service_from_bundle

_PENDING_PRICE_CLARIFY_KEY = "pending_price_clarify"
_KIND: Literal["price_service"] = "price_service"


@dataclass(frozen=True, slots=True)
class PendingPriceClarifyState:
    kind: Literal["price_service"]
    allowed_service_ids: tuple[str, ...]
    set_at_turn: int


def _catalog_authority_eligible(match: dict[str, object]) -> bool:
    service_id = str(match.get("matched_service_id") or "").strip()
    if not service_id:
        return False
    if not bool(match.get("is_confident")):
        return False
    if not bool(match.get("containment_eligible")):
        return False
    if bool(match.get("catalog_ambiguous")):
        return False
    return True


def read_pending_price_clarify(st: dict[str, Any]) -> PendingPriceClarifyState | None:
    raw = st.get(_PENDING_PRICE_CLARIFY_KEY)
    if not isinstance(raw, dict):
        return None
    if str(raw.get("kind") or "").strip() != _KIND:
        return None
    allowed_raw = raw.get("allowed_service_ids")
    if not isinstance(allowed_raw, list):
        return None
    allowed = tuple(
        str(item).strip()
        for item in allowed_raw
        if str(item).strip()
    )
    if not allowed:
        return None
    try:
        set_at_turn = int(raw.get("set_at_turn") or 0)
    except (TypeError, ValueError):
        return None
    return PendingPriceClarifyState(
        kind=_KIND,
        allowed_service_ids=allowed,
        set_at_turn=set_at_turn,
    )


def is_pending_price_clarify_fresh(
    state: PendingPriceClarifyState,
    *,
    session_turn_count: int,
) -> bool:
    """Pending is valid for the next user turn before session_turn_count advances."""

    return int(session_turn_count) == int(state.set_at_turn)


def maybe_clear_unrelated_pending_price_clarify(
    sid: str,
    *,
    user_message: str,
    bundle: ResponseSchemaBundle,
    is_governed_service_click: bool,
) -> None:
    """Clear pending when the next turn is unrelated or stale."""

    from session import mem_get

    pending = read_pending_price_clarify(mem_get(sid))
    if pending is None:
        return
    session_turn_count = int(mem_get(sid).get("session_turn_count") or 0)
    if not is_pending_price_clarify_fresh(
        pending,
        session_turn_count=session_turn_count,
    ):
        clear_pending_price_clarify(sid)
        return
    if is_governed_service_click:
        return
    if resolve_service_id_from_pending_price_text(
        user_message,
        bundle=bundle,
        pending=pending,
    ):
        return
    if (user_message or "").strip():
        clear_pending_price_clarify(sid)


def write_pending_price_clarify(
    sid: str,
    *,
    allowed_service_ids: tuple[str, ...],
    session_turn_count: int,
) -> None:
    from session import _lock, _persist_unlocked, mem_get

    allowed = tuple(str(item).strip() for item in allowed_service_ids if str(item).strip())
    if not allowed:
        return
    with _lock:
        st = mem_get(sid)
        st[_PENDING_PRICE_CLARIFY_KEY] = {
            "kind": _KIND,
            "allowed_service_ids": list(allowed),
            "set_at_turn": int(session_turn_count),
        }
        _persist_unlocked(sid, st)


def clear_pending_price_clarify(sid: str) -> None:
    from session import _lock, _persist_unlocked, mem_get

    with _lock:
        st = mem_get(sid)
        if _PENDING_PRICE_CLARIFY_KEY in st:
            st.pop(_PENDING_PRICE_CLARIFY_KEY, None)
            _persist_unlocked(sid, st)


def resolve_service_id_from_pending_price_text(
    user_message: str,
    *,
    bundle: ResponseSchemaBundle,
    pending: PendingPriceClarifyState,
) -> str | None:
    """Match free text only against services shown in the pending clarify."""

    allowed = frozenset(pending.allowed_service_ids)
    match = match_service_from_bundle(user_message, bundle)
    if not _catalog_authority_eligible(match):
        return None
    service_id = str(match.get("matched_service_id") or "").strip()
    if service_id not in allowed:
        return None
    service = bundle.services.get(service_id)
    if service is None or not service.active:
        return None
    return service_id
