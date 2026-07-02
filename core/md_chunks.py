"""Resolve md section refs to chunk dicts without corpus.jsonl (RAG removal prep)."""

from __future__ import annotations

import os
import re
from functools import lru_cache

import frontmatter

from core.aspect_metadata import infer_chunk_aspect
from core.client_config_loader import resolve_pack_client_id
from core.client_runtime import client_md_dir
from meta_loader import get_doc_path

ALIAS_RX = re.compile(r"<!--\s*aliases:\s*\[(.*?)\]\s*-->", re.I | re.S)
_H2RX = re.compile(r"^##\s+(.+?)(?:\s*\{#([a-z0-9\-\_]+)\})?\s*$", re.I)
_H3RX = re.compile(r"^###\s+(.+?)(?:\s*\{#([a-z0-9\-\_]+)\})?\s*$", re.I)

CONTACTS_CHUNK_REF = "clinic__info__contacts.md#korotko"


def extract_id_from_heading(txt: str) -> str | None:
    if not isinstance(txt, str):
        return None
    m = re.search(r"\{\s*#([^\}]+)\s*\}", txt)
    return m.group(1).strip() if m else None


def extract_local_aliases(block_text: str) -> list[str]:
    m = ALIAS_RX.search(block_text or "")
    if not m:
        return []
    return re.findall(r'"([^"]+)"', m.group(1))


def split_md_to_chunks(text: str) -> list[dict]:
    """Split markdown body (without frontmatter) into h2/h3 sections."""
    lines = text.splitlines()
    chunks: list[dict] = []
    h2: str | None = None
    h2_id: str | None = None
    h3: str | None = None
    h3_id: str | None = None
    buf: list[str] = []

    def flush() -> None:
        if buf:
            chunks.append(
                {
                    "h2": h2,
                    "h2_id": h2_id,
                    "h3": h3,
                    "h3_id": h3_id,
                    "text": "\n".join(buf).strip(),
                }
            )

    for ln in lines:
        m2 = _H2RX.match(ln)
        m3 = _H3RX.match(ln)
        if m2:
            flush()
            buf = []
            h2, h2_id = m2.group(1).strip(), (m2.group(2) or "").strip()
            h3, h3_id = None, None
        elif m3:
            flush()
            buf = []
            h3, h3_id = m3.group(1).strip(), (m3.group(2) or "").strip()
        else:
            buf.append(ln)
    flush()
    return [c for c in chunks if c["text"]]


def _resolve_md_path(basename: str, *, client_id: str | None) -> str | None:
    path = get_doc_path(basename, client_id=client_id)
    if path and os.path.isfile(path):
        return path
    pack = resolve_pack_client_id(client_id)
    guess = os.path.join(client_md_dir(pack), basename)
    return guess if os.path.isfile(guess) else None


def _build_chunk_items(md_path: str, *, client_id: str) -> list[dict]:
    with open(md_path, "r", encoding="utf-8-sig") as fh:
        fm = frontmatter.load(fh)
    meta = fm.metadata or {}
    doc_id = meta.get("doc_id") or os.path.splitext(os.path.basename(md_path))[0]
    doc_aliases = meta.get("aliases") or []
    basename = os.path.basename(md_path)
    pack = resolve_pack_client_id(client_id)
    items: list[dict] = []
    for ch in split_md_to_chunks(fm.content):
        local_aliases = extract_local_aliases(ch["text"])
        aspect = infer_chunk_aspect(
            doc_id=str(doc_id),
            doc_type=meta.get("doc_type"),
            subtopic=meta.get("subtopic"),
            frontmatter_aspect=meta.get("aspect"),
        )
        items.append(
            {
                "doc": doc_id,
                "doc_id": doc_id,
                "file": basename,
                "client_id": pack,
                "topic": meta.get("topic"),
                "subtopic": meta.get("subtopic"),
                "doc_type": meta.get("doc_type"),
                "aspect": aspect,
                "subtype": meta.get("subtype"),
                "cta_action": meta.get("cta_action"),
                "cta_text": meta.get("cta_text"),
                "cta_key": meta.get("cta_key"),
                "empathy_enabled": bool(meta.get("empathy_enabled", False)),
                "empathy_tag": meta.get("empathy_tag"),
                "followups": meta.get("followups", []),
                "h2": ch["h2"],
                "h2_id": ch["h2_id"],
                "h3": ch["h3"],
                "h3_id": ch["h3_id"],
                "text": ch["text"],
                "aliases": list(set(doc_aliases + local_aliases)),
            }
        )
    return items


@lru_cache(maxsize=256)
def _chunks_for_file(client_id: str, basename: str) -> tuple[dict, ...]:
    md_path = _resolve_md_path(basename, client_id=client_id)
    if not md_path:
        return ()
    return tuple(_build_chunk_items(md_path, client_id=client_id))


def get_chunk_by_ref(ref: str, *, client_id: str | None = None) -> dict | None:
    """Return one chunk dict for ``doc.md#anchor`` by parsing client md directly."""
    if not ref or "#" not in ref:
        return None
    pack = resolve_pack_client_id(client_id)
    fname, anchor = ref.split("#", 1)
    base = os.path.basename(fname)
    if not base.endswith(".md"):
        base = base + ".md"
    anchor_norm = (anchor or "").strip().lower()
    cands = list(_chunks_for_file(pack, base))
    if not cands:
        return None
    if anchor_norm in ("overview", "korotko", ""):
        for ch in cands:
            h3_id = (ch.get("h3_id") or "").strip().lower()
            if (not ch.get("h2_id") and not ch.get("h3_id")) or h3_id in {"overview", "korotko"}:
                out = dict(ch)
                out["_score"] = 1.0
                return out
        out = dict(cands[0])
        out["_score"] = 1.0
        return out
    for ch in cands:
        hid2 = ch.get("h2_id") or extract_id_from_heading(str(ch.get("h2") or ""))
        hid3 = ch.get("h3_id") or extract_id_from_heading(str(ch.get("h3") or ""))
        if anchor_norm in {
            (hid3 or "").lower(),
            (hid2 or "").lower(),
            str(ch.get("h3") or "").lower(),
            str(ch.get("h2") or "").lower(),
        }:
            out = dict(ch)
            out["_score"] = 1.0
            return out
    return None
