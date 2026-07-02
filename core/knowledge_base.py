"""Assemble client md corpus into one composer knowledge block (FULLCTX_ON step 1)."""

from __future__ import annotations

import glob
import os
import re

from core.client_runtime import client_md_dir

_FM_RE = re.compile(r"^---\s*\n.*?\n---\s*\n?", re.DOTALL)
_ALIAS_COMMENT_RE = re.compile(r"<!--\s*aliases:.*?-->\s*", re.IGNORECASE | re.DOTALL)
_ANCHOR_RE = re.compile(r"\s*\{#[^}]+\}")

_KB_CACHE: dict[str, str] = {}


def _should_include_md_file(basename: str) -> bool:
    name = basename.lower()
    if not name.endswith(".md"):
        return False
    if name.startswith("doctors__"):
        return False
    if "__pricing__" in name:
        return False
    return True


def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def _clean_md_body(text: str) -> str:
    body = _FM_RE.sub("", text, count=1) if _FM_RE.match(text) else text
    body = _ALIAS_COMMENT_RE.sub("", body)
    body = _ANCHOR_RE.sub("", body)
    return body.strip()


def assemble_client_knowledge_base(client_id: str | None) -> str:
    """All client md (except doctors/pricing) as one readable block; cached per pack id."""
    from core.client_config_loader import resolve_pack_client_id

    pack = resolve_pack_client_id(client_id)
    cached = _KB_CACHE.get(pack)
    if cached is not None:
        return cached

    md_dir = client_md_dir(client_id)
    parts: list[str] = []
    pattern = os.path.join(md_dir, "*.md")
    for path in sorted(glob.glob(pattern)):
        if not _should_include_md_file(os.path.basename(path)):
            continue
        cleaned = _clean_md_body(_read_file(path))
        if cleaned:
            parts.append(cleaned)

    blob = "\n\n---\n\n".join(parts)
    _KB_CACHE[pack] = blob
    return blob


def clear_knowledge_base_cache() -> None:
    """Test helper — drop per-client cache."""
    _KB_CACHE.clear()
