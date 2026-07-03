"""When to skip retrieval query rewrite LLM (speed without losing follow-up context)."""

from __future__ import annotations

import re

from config import BOOKING_INTENT_RE, CONTACTS_RE, PRICES_RE, QUERY_REWRITE_ON
from session import mem_get

_PRONOUN_RE = re.compile(
    r"\b("
    r"он|она|оно|они|его|её|ее|их|ему|ей|им|этот|эта|это|эти|тот|та|то|те|"
    r"такой|такая|такое|такие|там|туда|оттуда|сюда|здесь|тут|"
    r"прижив|не\s+прижив"
    r")\b",
    re.I | re.U,
)

_CONTINUATION_START_RE = re.compile(
    r"^(?:а|и|ну|так|ещё|еще|продолж|подробн|дальше|а\s+если|а\s+что)\b",
    re.I | re.U,
)

_SELF_CONTAINED_MIN_WORDS = 6


def rewrite_skip_reason(
    session_id: str,
    question: str,
    *,
    client_id: str | None = None,
) -> str | None:
    """
    None → run rewrite LLM; str → skip rewrite (reason for telemetry).
    client_id reserved for future per-client rules.
    """
    _ = client_id
    if not QUERY_REWRITE_ON:
        return "rewrite_off"
    q0 = (question or "").strip()
    if not q0:
        return "empty_query"
    st = mem_get(session_id)
    hist = list(st.get("hist") or [])
    if not hist:
        return "no_history"

    if CONTACTS_RE.search(q0) or PRICES_RE.search(q0) or BOOKING_INTENT_RE.search(q0):
        return "clear_intent_regex"

    words = [w for w in re.split(r"\s+", q0) if w]
    has_pronoun = bool(_PRONOUN_RE.search(q0))
    continuation_start = bool(_CONTINUATION_START_RE.search(q0))

    if continuation_start or has_pronoun:
        return None

    if len(words) <= 4:
        return None

    if len(words) >= _SELF_CONTAINED_MIN_WORDS:
        return "self_contained_long"

    return "self_contained_short"
