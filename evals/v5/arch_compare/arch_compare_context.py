"""Full vs curated MD context assembly for architecture comparison (eval-only)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from contracts.target_cached_full_context import TargetCachedFullContext
from core.target_cached_full_context import build_target_cached_full_context
from core.target_runtime_client_context import load_target_runtime_client_context
from evals.v5.arch_compare.arch_compare_contract import CLIENT_ID, CONTEXT_MODE_CURATED, CONTEXT_MODE_FULL

ContextMode = Literal["full", "curated"]


class ArchCompareContextError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class CuratedContextResolution:
    ordered_source_refs: tuple[str, ...]
    resolved_source_refs: tuple[str, ...]
    missing_source_refs: tuple[str, ...]
    full_context_size: int
    curated_context_size: int
    content_context_hash: str
    curated_cached_context: TargetCachedFullContext


def _digest_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_source_ref(ref: str) -> str:
    value = str(ref or "").strip().replace("\\", "/")
    if not value:
        raise ArchCompareContextError("source_ref_empty", repr(ref))
    if value.startswith("clients/"):
        parts = value.split("/")
        if "md" in parts:
            idx = parts.index("md")
            value = "/".join(parts[idx + 1 :])
    if value.endswith("/"):
        value = value.rstrip("/")
    return value


def normalize_source_refs(refs: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Deduplicate refs preserving first-seen order."""

    seen: set[str] = set()
    ordered: list[str] = []
    for raw in refs:
        ref = _normalize_source_ref(raw)
        if ref in seen:
            continue
        seen.add(ref)
        ordered.append(ref)
    return tuple(ordered)


def load_demo_full_cached_context() -> TargetCachedFullContext:
    ctx = load_target_runtime_client_context(CLIENT_ID)
    return ctx.cached_full_context


def _extract_document_block(full_corpus: str, relative_path: str) -> str:
    begin = f"---BEGIN DOC:{relative_path}---"
    end = f"---END DOC:{relative_path}---"
    start = full_corpus.find(begin)
    if start < 0:
        raise ArchCompareContextError("curated_doc_block_missing", relative_path)
    end_idx = full_corpus.find(end, start)
    if end_idx < 0:
        raise ArchCompareContextError("curated_doc_block_unterminated", relative_path)
    return full_corpus[start : end_idx + len(end)]


def build_curated_cached_context(
    full_context: TargetCachedFullContext,
    *,
    source_refs: tuple[str, ...],
) -> CuratedContextResolution:
    ordered = normalize_source_refs(source_refs)
    available = set(full_context.document_paths)
    missing = tuple(ref for ref in ordered if ref not in available)
    if missing:
        raise ArchCompareContextError("curated_source_ref_missing", ",".join(missing))

    resolved = tuple(ref for ref in ordered if ref in available)
    corpus = full_context.model_corpus_text
    blocks = [_extract_document_block(corpus, ref) for ref in resolved]
    curated_corpus = "\n".join(blocks)
    curated = TargetCachedFullContext(
        corpus_text=curated_corpus,
        document_count=len(resolved),
        document_paths=resolved,
        sha256=_digest_hex(curated_corpus),
        prompt_corpus_text=curated_corpus,
        prompt_sha256=_digest_hex(curated_corpus),
    )
    return CuratedContextResolution(
        ordered_source_refs=ordered,
        resolved_source_refs=resolved,
        missing_source_refs=missing,
        full_context_size=len(full_context.model_corpus_text),
        curated_context_size=len(curated_corpus),
        content_context_hash=_digest_hex(curated_corpus),
        curated_cached_context=curated,
    )


def cached_context_for_mode(
    *,
    context_mode: ContextMode,
    full_context: TargetCachedFullContext,
    curated_source_refs: tuple[str, ...],
) -> tuple[TargetCachedFullContext, CuratedContextResolution | None]:
    if context_mode == CONTEXT_MODE_FULL:
        return full_context, None
    if context_mode == CONTEXT_MODE_CURATED:
        resolution = build_curated_cached_context(full_context, source_refs=curated_source_refs)
        return resolution.curated_cached_context, resolution
    raise ArchCompareContextError("context_mode_invalid", str(context_mode))


def rebuild_full_context_from_md_root() -> TargetCachedFullContext:
    ctx = load_target_runtime_client_context(CLIENT_ID)
    return build_target_cached_full_context(ctx.md_root)


def content_context_hash_for(full_context: TargetCachedFullContext) -> str:
    return _digest_hex(full_context.model_corpus_text)
