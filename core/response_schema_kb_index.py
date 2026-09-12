"""Strict offline KB source-index builder for the target response schema (S4)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import NoReturn

from pydantic import TypeAdapter, ValidationError

from contracts.response_schema import SourceRef


_FENCE_OPENER = re.compile(r"^(?P<fence>`{3,}|~{3,}).*$")
_TARGET_HEADING = re.compile(r"^(?:##|###) (?P<body>.*)$")
_TERMINAL_ANCHOR = re.compile(
    r"^(?P<title>.+?)[ ]+\{#(?P<chunk_id>[A-Za-z0-9][A-Za-z0-9._-]*)\}[ \t]*$"
)


class ResponseSchemaKbIndexError(Exception):
    """Typed fail-closed error for one target KB root or Markdown source."""

    def __init__(self, code: str, path: Path) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {path.as_posix()}")


def _raise_index_error(code: str, path: Path, cause: BaseException) -> NoReturn:
    raise ResponseSchemaKbIndexError(code, path) from cause


def _require_md_root(md_root: object) -> Path:
    if not isinstance(md_root, Path):
        _raise_index_error(
            "md_root_invalid",
            Path("."),
            TypeError("md_root_must_be_pathlib_path"),
        )
    if not md_root.exists():
        _raise_index_error(
            "md_root_invalid",
            Path("."),
            FileNotFoundError(str(md_root)),
        )
    if not md_root.is_dir():
        _raise_index_error(
            "md_root_invalid",
            Path("."),
            NotADirectoryError(str(md_root)),
        )
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
        _raise_index_error("file_read_failed", relative_path, exc)


def _is_fence_closer(line: str, fence_character: str, opener_length: int) -> bool:
    return re.fullmatch(
        rf"{re.escape(fence_character)}{{{opener_length},}}[ \t]*",
        line,
    ) is not None


def _chunk_ids(text: str, relative_path: Path) -> tuple[str, ...]:
    chunk_ids: list[str] = []
    seen: set[str] = set()
    fence_character: str | None = None
    fence_length = 0

    for line in text.splitlines():
        if fence_character is not None:
            if _is_fence_closer(line, fence_character, fence_length):
                fence_character = None
                fence_length = 0
            continue

        opener = _FENCE_OPENER.fullmatch(line)
        if opener is not None:
            fence = opener.group("fence")
            fence_character = fence[0]
            fence_length = len(fence)
            continue

        heading = _TARGET_HEADING.fullmatch(line)
        if heading is None:
            continue
        body = heading.group("body")
        if "{#" not in body:
            continue

        anchor = _TERMINAL_ANCHOR.fullmatch(body)
        if (
            anchor is None
            or body.count("{#") != 1
            or not anchor.group("title").strip()
        ):
            _raise_index_error(
                "chunk_anchor_invalid",
                relative_path,
                ValueError("target_chunk_anchor_invalid"),
            )

        chunk_id = anchor.group("chunk_id")
        if chunk_id in seen:
            _raise_index_error(
                "chunk_anchor_duplicate",
                relative_path,
                ValueError("target_chunk_anchor_duplicate"),
            )
        seen.add(chunk_id)
        chunk_ids.append(chunk_id)

    return tuple(chunk_ids)


def build_response_schema_kb_refs(md_root: Path) -> tuple[SourceRef, ...]:
    """Build exact KB refs from one explicit target Markdown root."""

    root = _require_md_root(md_root)
    adapter = TypeAdapter(SourceRef)
    refs: list[SourceRef] = []

    for path, relative_path in _discover_markdown_files(root):
        text = _read_utf8(path, relative_path)
        for chunk_id in _chunk_ids(text, relative_path):
            raw_ref = f"kb:{relative_path.as_posix()}#{chunk_id}"
            try:
                refs.append(adapter.validate_python(raw_ref))
            except ValidationError as exc:
                _raise_index_error("source_ref_invalid", relative_path, exc)

    return tuple(sorted(refs))
