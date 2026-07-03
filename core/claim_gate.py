"""Deterministic forbidden-claim gate for composer answers (composer roadmap phase 3b).

Detects unambiguous promises that must not appear in composer output.
Fail-open: any internal error returns no hits (never block the turn).
"""
from __future__ import annotations

import re

_FORBIDDEN_CLAIM_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("bezbolesnenno", re.compile(r"безболезненн", re.I | re.UNICODE)),
    ("guarantee_result", re.compile(r"гарантиру\w*\s+результат", re.I | re.UNICODE)),
    ("guaranteed_result", re.compile(r"гарантированн\w*\s+результат", re.I | re.UNICODE)),
    (
        "sto_procent_prizhivlenie",
        re.compile(r"стопроцентн\w*\s+(?:приживл|прижива)", re.I | re.UNICODE),
    ),
    (
        "hundred_pct_prizhivlenie",
        re.compile(r"100\s*%\s*(?:приживл|прижива|безопасн)", re.I | re.UNICODE),
    ),
    ("prizhivetsya_na_100", re.compile(r"прижив\w*\s+на\s+100", re.I | re.UNICODE)),
    ("fully_safe", re.compile(r"полност\w*\s+безопасн", re.I | re.UNICODE)),
    ("no_pain_promise", re.compile(r"боли\s+(?:совсем\s+)?не\s+будет", re.I | re.UNICODE)),
    ("not_painful_promise", re.compile(r"не\s+будет\s+больно", re.I | re.UNICODE)),
)


def detect_forbidden_claims(text: str) -> list[str]:
    """Return matched blocklist pattern ids. Empty list means clean (or fail-open)."""
    try:
        blob = (text or "").strip()
        if not blob:
            return []
        hits: list[str] = []
        for pattern_id, rx in _FORBIDDEN_CLAIM_PATTERNS:
            if rx.search(blob):
                hits.append(pattern_id)
        return hits
    except Exception:
        return []
