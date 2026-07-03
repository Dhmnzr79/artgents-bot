"""Assemble client md corpus into one composer knowledge block (FULLCTX_ON step 1)."""

from __future__ import annotations

import glob
import os
import re

from core.client_runtime import client_md_dir
from core.clinic_policies_loader import load_clinic_policies

_FM_RE = re.compile(r"^---\s*\n.*?\n---\s*\n?", re.DOTALL)
_DOC_ID_RE = re.compile(r"^doc_id:\s*(.+)$", re.MULTILINE)
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


def _doc_id_from_text(basename: str, text: str) -> str:
    fm = _FM_RE.match(text)
    if fm:
        m = _DOC_ID_RE.search(fm.group(0))
        if m:
            return m.group(1).strip()
    return os.path.splitext(basename)[0]


def _first_h2_title(cleaned_body: str) -> str:
    for line in cleaned_body.splitlines():
        if line.startswith("## "):
            return line[3:].strip()
    return ""


def _document_header(basename: str, text: str, cleaned_body: str) -> str:
    doc_id = _doc_id_from_text(basename, text)
    title = _first_h2_title(cleaned_body)
    if title:
        return f"## {doc_id} — {title}"
    return f"## {doc_id}"


def _clinic_limitations_section(client_id: str) -> str:
    bundle = load_clinic_policies(client_id)
    if bundle is None:
        return ""
    texts: list[str] = []
    for policy in bundle.policies:
        answer = str(policy.answer or "").strip()
        if answer:
            texts.append(answer)
    for alt in bundle.service_alternatives:
        note = str(alt.note or "").strip()
        if note:
            texts.append(note)
    if not texts:
        return ""
    body = "\n\n".join(f"- {text}" for text in texts)
    return f"## Ограничения клиники (чего мы НЕ делаем)\n\n{body}"


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
        raw = _read_file(path)
        cleaned = _clean_md_body(raw)
        if cleaned:
            header = _document_header(os.path.basename(path), raw, cleaned)
            parts.append(f"{header}\n\n{cleaned}")

    limitations = _clinic_limitations_section(pack)
    if limitations:
        parts.append(limitations)

    blob = "\n\n---\n\n".join(parts)
    _KB_CACHE[pack] = blob
    return blob


def clear_knowledge_base_cache() -> None:
    """Test helper — drop per-client cache."""
    _KB_CACHE.clear()
