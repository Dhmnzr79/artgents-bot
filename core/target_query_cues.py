"""Deterministic query cues for planner ingress (no legacy price island)."""

from __future__ import annotations

from config import COMMERCIAL_INFO_RE, CONSULTATION_QUERY_RE


def commercial_info_query(q: str) -> bool:
    return bool(COMMERCIAL_INFO_RE.search(q or ""))


def consultation_info_query(q: str) -> bool:
    return bool(CONSULTATION_QUERY_RE.search(q or ""))
