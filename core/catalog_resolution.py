"""Service catalog resolution helpers (price_lookup matrix)."""
from __future__ import annotations

import re
from typing import Literal

from core.md_chunks import get_chunk_by_ref

ContentSnippetSource = Literal["korotko", "facts", "title_only"]

_PRICE_FALLBACK_TO_RESOLUTION = {
    "price_not_in_catalog": "matched_service_but_no_price",
    "price_not_found": "matched_service_but_no_price",
    "context_session": "matched_service_but_no_price",
    "service_not_found": "service_not_found",
    "low_match_score": "low_match_score",
    "continuation_no_context": "continuation_no_context",
}


def fallback_reason_to_resolution(reason: str) -> str:
    r = (reason or "").strip()
    return _PRICE_FALLBACK_TO_RESOLUTION.get(r, r or "service_not_found")


def _md_korotko_ref(md_entry_ref: str) -> str:
    raw = (md_entry_ref or "").strip()
    if not raw:
        return ""
    base = raw if raw.lower().endswith(".md") else f"{raw}.md"
    if "#" in base:
        stem, anchor = base.split("#", 1)
        if not stem.lower().endswith(".md"):
            stem = f"{stem}.md"
        return f"{stem}#{anchor or 'korotko'}"
    return f"{base}#korotko"


def _strip_md_noise(text: str) -> str:
    out = re.sub(r"<!--.*?-->", " ", text or "", flags=re.S)
    out = re.sub(r"#+\s*", "", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"\1", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def first_sentences(text: str, *, max_sentences: int = 2, max_chars: int = 280) -> str:
    clean = _strip_md_noise(text)
    if not clean:
        return ""
    parts = re.split(r"(?<=[.!?…])\s+", clean)
    picked: list[str] = []
    total = 0
    for part in parts:
        p = part.strip()
        if not p:
            continue
        picked.append(p)
        total += len(p) + 1
        if len(picked) >= max_sentences or total >= max_chars:
            break
    return " ".join(picked).strip()


def service_content_snippet(
    service: dict | None,
    *,
    client_id: str | None,
) -> tuple[str, ContentSnippetSource | None]:
    """First 1–2 sentences from korotko, else facts, else title."""
    svc = service if isinstance(service, dict) else {}
    md_ref = str(svc.get("md_entry_ref") or "").strip()
    if md_ref:
        ref = _md_korotko_ref(md_ref)
        ch = get_chunk_by_ref(ref, client_id=client_id)
        if ch:
            snip = first_sentences(str(ch.get("text") or ""))
            if snip:
                return snip, "korotko"
    facts = [str(x).strip() for x in (svc.get("facts") or []) if str(x).strip()]
    if facts:
        if len(facts) == 1:
            return facts[0], "facts"
        return f"{facts[0]} {facts[1]}", "facts"
    title = str(svc.get("title") or "").strip()
    if title:
        return title, "title_only"
    return "", None
