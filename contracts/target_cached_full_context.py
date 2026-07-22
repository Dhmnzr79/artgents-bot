"""Immutable cached FullContext contract (S44, offline/unwired)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TargetCachedFullContext:
    """Deterministic client MD corpus built once and reused across turns."""

    corpus_text: str
    document_count: int
    document_paths: tuple[str, ...]
    sha256: str
