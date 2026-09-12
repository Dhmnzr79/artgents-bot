"""Deterministic cached FullContext builder (S44, offline/unwired).

Corpus format (stable, documented):

- Every ``*.md`` under explicit ``md_root`` is included exactly once.
- Order: canonical relative POSIX path ascending.
- Each document block:

  ---BEGIN DOC:{relative_path}---
  {full on-disk UTF-8 content, including YAML frontmatter}
  ---END DOC:{relative_path}---

- Blocks are joined with a single ``\\n`` between the previous ``---END DOC:...---``
  line and the next ``---BEGIN DOC:...---`` line.
- ``sha256`` is the lowercase hex SHA-256 of ``corpus_text`` encoded as UTF-8.

This module prepares a deterministic provider prompt prefix candidate. Provider-side
prompt caching is a separate future live integration gate and is **not** implemented here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import NoReturn

import frontmatter

from contracts.target_cached_full_context import TargetCachedFullContext


class TargetCachedFullContextError(ValueError):
    """Typed fail-closed FullContext build failure."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _fail(code: str, value: object, cause: BaseException | None = None) -> NoReturn:
    error = TargetCachedFullContextError(code, value)
    if cause is None:
        raise error
    raise error from cause


def _require_md_root(md_root: object) -> Path:
    if not isinstance(md_root, Path):
        _fail("full_context_md_root_invalid", md_root)
    if not md_root.exists():
        _fail("full_context_md_root_invalid", md_root, FileNotFoundError(str(md_root)))
    if not md_root.is_dir():
        _fail("full_context_md_root_invalid", md_root, NotADirectoryError(str(md_root)))
    return md_root


def _discover_markdown_files(md_root: Path) -> list[tuple[Path, Path]]:
    files = [path for path in md_root.rglob("*") if path.is_file() and path.suffix == ".md"]
    return sorted(
        ((path, path.relative_to(md_root)) for path in files),
        key=lambda item: item[1].as_posix(),
    )


def _read_utf8(path: Path, relative_path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        _fail("full_context_document_unreadable", relative_path.as_posix(), exc)


def _document_block(relative_path: str, content: str) -> str:
    return (
        f"---BEGIN DOC:{relative_path}---\n"
        f"{content}\n"
        f"---END DOC:{relative_path}---"
    )


_MODEL_ROUTING_FRONTMATTER_KEYS = frozenset(
    {"doc_id", "doc_type", "topic", "subtopic", "aspect"}
)


def _prompt_document_block(relative_path: str, content: str) -> str:
    """Serialize the whole answer body plus only lean model-routing metadata."""

    try:
        post = frontmatter.loads(content)
    except Exception as exc:  # noqa: BLE001 - malformed source must fail closed
        _fail("full_context_frontmatter_invalid", relative_path, exc)
    metadata = {
        str(key): value
        for key, value in post.metadata.items()
        if str(key) in _MODEL_ROUTING_FRONTMATTER_KEYS
    }
    meta_json = json.dumps(
        metadata,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )
    body = post.content.rstrip("\n")
    if not body.strip():
        _fail("full_context_document_body_empty", relative_path)
    prefix = f"META_JSON:{meta_json}\n" if metadata else ""
    return _document_block(relative_path, f"{prefix}{body}")


def build_target_cached_full_context(md_root: Path) -> TargetCachedFullContext:
    """Build one immutable cached FullContext corpus from explicit client MD root."""

    root = _require_md_root(md_root)
    discovered = _discover_markdown_files(root)
    if not discovered:
        _fail("full_context_corpus_empty", root)

    blocks: list[str] = []
    prompt_blocks: list[str] = []
    paths: list[str] = []
    for path, relative_path in discovered:
        relative_posix = relative_path.as_posix()
        text = _read_utf8(path, relative_path)
        if not text.strip():
            _fail("full_context_document_empty", relative_posix)
        blocks.append(_document_block(relative_posix, text.rstrip("\n")))
        prompt_blocks.append(_prompt_document_block(relative_posix, text))
        paths.append(relative_posix)

    corpus_text = "\n".join(blocks)
    digest = hashlib.sha256(corpus_text.encode("utf-8")).hexdigest()
    prompt_corpus_text = "\n".join(prompt_blocks)
    prompt_digest = hashlib.sha256(prompt_corpus_text.encode("utf-8")).hexdigest()
    return TargetCachedFullContext(
        corpus_text=corpus_text,
        document_count=len(paths),
        document_paths=tuple(paths),
        sha256=digest,
        prompt_corpus_text=prompt_corpus_text,
        prompt_sha256=prompt_digest,
    )
