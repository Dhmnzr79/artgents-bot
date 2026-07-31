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
    # PERF: model-facing serialization keeps every document body and factual
    # metadata, but omits structured/routing/UI frontmatter already consumed by Python.
    # Optional defaults preserve compatibility with synthetic/frozen fixtures.
    prompt_corpus_text: str | None = None
    prompt_sha256: str | None = None

    @property
    def model_corpus_text(self) -> str:
        return self.prompt_corpus_text or self.corpus_text
