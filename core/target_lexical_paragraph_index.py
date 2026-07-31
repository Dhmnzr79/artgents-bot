"""Local in-memory lexical paragraph index over client MD (PERF-7A, offline/unwired).

**Not wired to any runtime path.** Nothing in ``app.py``, the Composer/Verifier pipeline, or
``TurnFrame`` handling imports this module. It exists so a future, separately owner-approved
``EvidencePackageBuilder`` (PERF-7B) has a local, pure, deterministic way to find MD paragraphs that
contain a micro-fact a structured source (offers/facts/doctors/contacts) does not cover -- retrieval
as one auxiliary input among several, never a router, per
``docs/evidence/performance/FINAL_LOCAL_EVIDENCE_PACKAGE_BUILDER_FOUNDATION_SEAM_AUDIT.md`` §§7-8.

One canonical builder, one canonical search function -- no parallel per-service/topic/group index:

- ``build_target_lexical_paragraph_index(md_root)`` -- pure, offline, deterministic. Walks every
  ``*.md`` under ``md_root`` recursively, splits each into paragraph/list/fence-aware section
  blocks, and returns one immutable ``TargetLexicalParagraphIndex``.
- ``search_target_lexical_paragraph_index(index, query, *, limit)`` -- pure in-memory Python
  token-overlap + prefix scan (Option A, selected over SQLite FTS5 in the PERF-7 seam audit §§4-7:
  simplest option sufficient for a 55-150-short-document corpus, zero query-language injection
  surface). No SQLite, no FTS5, no embeddings, no network, no LLM.

**No persistent cache.** A pure builder is enough at this stage: nothing in this repository calls
either function yet, so there is no real caller whose repeated-build cost would justify an
in-memory cache layer, and a module-level mutable cache would be dead weight added only for the
word "cache" (explicitly warned against in this milestone's brief). A future PERF-7B loader can
hold one already-built ``TargetLexicalParagraphIndex`` in its own instance/session state and decide
its own rebuild-on-fingerprint-change policy once a real caller exists to design that policy
against.

**Reuse decision (recorded, not silent):** ``core/target_composer_request.py`` already contains a
frontmatter/heading/fence parser (``_FRONTMATTER``, ``_EXPLICIT_HEADING``, ``_HEADING``, ``_FENCE``,
``_section``), which this module's design was reviewed against before writing a single line here.
It was **not imported**: every one of those names is module-private (leading underscore, not a
public contract), ``_section`` only extracts a single named anchor section (it does not walk and
emit every section of a document, which is this module's actual job), and its error semantics
(``TargetComposerRequestError``, exact-ref-format validation) are tied to the Composer-request
evidence-block contract, not to a tolerant, best-effort corpus-wide indexer. Importing those private
names would couple this new, foundational, unwired module to an unrelated module's internal
contract for no real benefit. What *is* reused, conceptually (not by import): the same "H2/H3 is a
section boundary" rule and the same fence-aware "a heading marker inside an open code fence is not
a heading" rule -- restated here as this module's own small, self-contained regexes, matching the
existing precedent's shape without creating a cross-module dependency on private internals.
``python-frontmatter`` (the ``frontmatter`` package) is reused as an actual import -- it is already
a repository dependency used the same way by ``core/topic_taxonomy.py`` and
``core/target_context_scope_resolver.py``, so using it here adds no new dependency.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, NoReturn

import frontmatter

__all__ = [
    "TargetLexicalParagraph",
    "TargetLexicalParagraphIndex",
    "TargetLexicalSearchHit",
    "TargetLexicalParagraphIndexError",
    "build_target_lexical_paragraph_index",
    "search_target_lexical_paragraph_index",
]


# --------------------------------------------------------------------------------------------
# Typed public contracts
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TargetLexicalParagraph:
    """One indexed paragraph/list/fence block. Immutable, deterministic identity.

    ``text`` carries the raw (pre-normalization) block text for a future Builder's use -- it is
    intentionally kept in this in-memory structure (per this milestone's brief) but must never be
    written to a log line, an observability event, or disk by any caller.
    """

    paragraph_id: str
    document_path: str
    document_identity: str | None
    heading: str | None
    topic: str | None
    document_type: str | None
    normalized_searchable_text: str
    content_hash: str
    text: str


@dataclass(frozen=True, slots=True)
class TargetLexicalParagraphIndex:
    """One immutable corpus-wide index. Deterministic order, deterministic fingerprint."""

    paragraphs: tuple[TargetLexicalParagraph, ...]
    document_count: int
    paragraph_count: int
    fingerprint: str


@dataclass(frozen=True, slots=True)
class TargetLexicalSearchHit:
    """One ranked search result. Score breakdown is explicit, not a single opaque number."""

    paragraph: TargetLexicalParagraph
    score: int
    exact_token_matches: int
    prefix_token_matches: int


class TargetLexicalParagraphIndexError(ValueError):
    """Typed fail-closed PERF-7A build/search failure."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _fail(code: str, value: object, cause: BaseException | None = None) -> NoReturn:
    error = TargetLexicalParagraphIndexError(code, value)
    if cause is None:
        raise error
    raise error from cause


# --------------------------------------------------------------------------------------------
# Discovery (mirrors core/target_cached_full_context.py's own tiny discovery helper in shape --
# not imported, since that helper is private to that module and this is a 4-line function, not
# "a large parser" worth avoiding duplication of).
# --------------------------------------------------------------------------------------------


def _require_md_root(md_root: object) -> Path:
    if not isinstance(md_root, Path):
        _fail("lexical_index_md_root_invalid", md_root)
    if not md_root.exists():
        _fail("lexical_index_md_root_invalid", md_root, FileNotFoundError(str(md_root)))
    if not md_root.is_dir():
        _fail("lexical_index_md_root_invalid", md_root, NotADirectoryError(str(md_root)))
    return md_root


def _discover_markdown_files(md_root: Path) -> list[tuple[Path, Path]]:
    files = [path for path in md_root.rglob("*") if path.is_file() and path.suffix.lower() == ".md"]
    return sorted(
        ((path, path.relative_to(md_root)) for path in files),
        key=lambda item: item[1].as_posix(),
    )


def _optional_meta_str(value: object, *, lower: bool = False) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return stripped.lower() if lower else stripped


# --------------------------------------------------------------------------------------------
# Section/paragraph/list/fence splitting
# --------------------------------------------------------------------------------------------

_MIN_PARAGRAPH_CHARS = 40  # same constant the client-pack dedup audit's own near-duplicate
# detector already uses for its minimum block length -- no second, unrelated size constant
# invented here (docs/evidence/client_pack/FINAL_CLIENT_PACK_CONTENT_DEDUP_AND_TOKEN_AUDIT.md §3).

_HEADING_RE = re.compile(r"^(?P<marks>#{1,6})[ \t]+(?P<text>.+?)[ \t]*$")
_HEADING_ANCHOR_SUFFIX_RE = re.compile(r"\s*\{#[^}\r\n]+\}\s*$")
_FENCE_RE = re.compile(r"^[ \t]{0,3}(?P<marker>`{3,}|~{3,})")
_LIST_ITEM_RE = re.compile(r"^[ \t]*(?:[-*+][ \t]+|\d+[.)][ \t]+)\S")


class _RawBlock(NamedTuple):
    heading: str | None
    lines: tuple[str, ...]


class _ParagraphDraft(NamedTuple):
    heading: str | None
    text: str


def _block_text(block: _RawBlock) -> str:
    return "\n".join(block.lines).strip()


def _split_document_into_blocks(body: str) -> list[_RawBlock]:
    """Fence-aware H2/H3-section-scoped block walker.

    A "block" is either one contiguous paragraph, one contiguous run of list items, or one fenced
    code region -- exactly the three unit kinds this milestone's brief names. Blank lines, heading
    lines, and fence open/close markers are structural separators, never block content (except a
    fence's own opening/closing marker lines, which belong to that fence block). A heading line
    inside an open fence is never treated as a section boundary -- the fence-tracking state is
    checked first, before any heading/list/blank classification.
    """

    blocks: list[_RawBlock] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    current_kind: str | None = None  # "paragraph" | "list" | "fence" | None
    fence_char: str | None = None
    fence_len = 0

    def flush() -> None:
        nonlocal current_lines, current_kind
        if current_lines:
            text = "\n".join(current_lines).strip()
            if text:
                blocks.append(_RawBlock(heading=current_heading, lines=tuple(current_lines)))
        current_lines = []
        current_kind = None

    for line in body.splitlines():
        if fence_char is not None:
            current_lines.append(line)
            closing = re.match(
                rf"^[ \t]{{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*$", line
            )
            if closing is not None:
                fence_char = None
                fence_len = 0
            continue

        fence_open = _FENCE_RE.match(line)
        if fence_open is not None:
            flush()
            marker = fence_open.group("marker")
            fence_char = marker[0]
            fence_len = len(marker)
            current_kind = "fence"
            current_lines = [line]
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match is not None:
            flush()
            marks = heading_match.group("marks")
            label = _HEADING_ANCHOR_SUFFIX_RE.sub("", heading_match.group("text")).strip()
            current_heading = label or None if len(marks) in (2, 3) else None
            continue

        if not line.strip():
            flush()
            continue

        if _LIST_ITEM_RE.match(line) is not None:
            if current_kind != "list":
                flush()
                current_kind = "list"
            current_lines.append(line)
            continue

        if current_kind != "paragraph":
            flush()
            current_kind = "paragraph"
        current_lines.append(line)

    flush()
    return blocks


def _group_runs(blocks: list[_RawBlock]) -> list[list[_RawBlock]]:
    """Group consecutive blocks sharing the same enclosing heading into one section.

    Blocks are already produced in document order with a flush on every heading transition, so
    blocks sharing a heading are always contiguous -- a simple run-length grouping, never a
    heading-name lookup that could accidentally merge two same-titled-but-separate sections.
    """

    groups: list[list[_RawBlock]] = []
    for block in blocks:
        if groups and groups[-1][0].heading == block.heading:
            groups[-1].append(block)
        else:
            groups.append([block])
    return groups


def _merge_short_blocks(texts: list[str], *, min_chars: int) -> list[str]:
    """Deterministic minimum-unit-size rule (brief: "не выбрасывай молча факт только из-за длины").

    A lone block in a section is kept whole regardless of length (there is nothing to merge into --
    the "poднять весь короткий раздел" case). Otherwise: accumulate short blocks forward into the
    next block until the running total reaches ``min_chars``; if the final accumulated remainder is
    still short (the section's last block(s) never reached the threshold), merge it backward into
    the last emitted paragraph instead. No block's content is ever discarded.
    """

    if len(texts) <= 1:
        return list(texts)

    merged: list[str] = []
    carry: str | None = None
    for text in texts:
        combined = f"{carry}\n{text}" if carry else text
        if len(combined) < min_chars:
            carry = combined
            continue
        merged.append(combined)
        carry = None

    if carry is not None:
        if merged:
            merged[-1] = f"{merged[-1]}\n{carry}"
        else:
            merged.append(carry)
    return merged


def _document_paragraphs(body: str) -> list[_ParagraphDraft]:
    blocks = _split_document_into_blocks(body)
    drafts: list[_ParagraphDraft] = []
    for group in _group_runs(blocks):
        heading = group[0].heading
        texts = [_block_text(block) for block in group]
        for merged_text in _merge_short_blocks(texts, min_chars=_MIN_PARAGRAPH_CHARS):
            stripped = merged_text.strip()
            if stripped:
                drafts.append(_ParagraphDraft(heading=heading, text=stripped))
    return drafts


# --------------------------------------------------------------------------------------------
# Normalization / tokenization (shared, identically, by indexing and query-time search)
# --------------------------------------------------------------------------------------------

_TOKEN_CHARS_RE = re.compile(r"[a-zа-я0-9]+")


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("ё", "е").replace("Ё", "Е")
    normalized = normalized.casefold()
    return " ".join(_TOKEN_CHARS_RE.findall(normalized))


def _tokenize(text: str) -> tuple[str, ...]:
    return tuple(_normalize_text(text).split())


# --------------------------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------------------------


def build_target_lexical_paragraph_index(md_root: Path) -> TargetLexicalParagraphIndex:
    """Build one immutable lexical paragraph index from every ``*.md`` under ``md_root``.

    Pure, offline, deterministic: no network, no provider, no LLM call, no disk write. Recursive
    discovery in canonical relative-POSIX-path order -- a new MD file is automatically included on
    the next call, a changed file changes both its own paragraphs and the whole-index fingerprint, a
    deleted file simply no longer appears. No manual document registration anywhere.
    """

    root = _require_md_root(md_root)
    discovered = _discover_markdown_files(root)
    if not discovered:
        _fail("lexical_index_corpus_empty", root)

    paragraphs: list[TargetLexicalParagraph] = []
    doc_hash_entries: list[str] = []

    for path, relative_path in discovered:
        relative_posix = relative_path.as_posix()
        try:
            raw_text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            _fail("lexical_index_document_unreadable", relative_posix, exc)

        try:
            post = frontmatter.loads(raw_text)
        except Exception as exc:  # noqa: BLE001 -- any malformed-frontmatter failure, fail-closed
            _fail("lexical_index_frontmatter_invalid", relative_posix, exc)

        doc_id = _optional_meta_str(post.metadata.get("doc_id"))
        doc_type = _optional_meta_str(post.metadata.get("doc_type"))
        topic = _optional_meta_str(post.metadata.get("topic"), lower=True)

        doc_content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        doc_hash_entries.append(f"{relative_posix}:{doc_content_hash}")

        for ordinal, draft in enumerate(_document_paragraphs(post.content)):
            paragraph_id = f"{relative_posix}#p{ordinal:03d}"
            paragraphs.append(
                TargetLexicalParagraph(
                    paragraph_id=paragraph_id,
                    document_path=relative_posix,
                    document_identity=doc_id,
                    heading=draft.heading,
                    topic=topic,
                    document_type=doc_type,
                    normalized_searchable_text=_normalize_text(draft.text),
                    content_hash=hashlib.sha256(draft.text.encode("utf-8")).hexdigest(),
                    text=draft.text,
                )
            )

    fingerprint = hashlib.sha256(
        "|".join(sorted(doc_hash_entries)).encode("utf-8")
    ).hexdigest()

    return TargetLexicalParagraphIndex(
        paragraphs=tuple(paragraphs),
        document_count=len(discovered),
        paragraph_count=len(paragraphs),
        fingerprint=fingerprint,
    )


# --------------------------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------------------------

_MIN_PREFIX_QUERY_TOKEN_LEN = 4  # "осторожное prefix/common-root matching" -- a short query token
# (e.g. 2-3 chars) is not allowed to prefix-match, to avoid over-matching unrelated words.
_EXACT_MATCH_WEIGHT = 2
_PREFIX_MATCH_WEIGHT = 1


def _score_paragraph(
    paragraph_tokens: tuple[str, ...], query_tokens: tuple[str, ...]
) -> tuple[int, int, int]:
    paragraph_token_set = set(paragraph_tokens)
    exact = 0
    prefix = 0
    for token in query_tokens:
        if token in paragraph_token_set:
            exact += 1
            continue
        if len(token) >= _MIN_PREFIX_QUERY_TOKEN_LEN and any(
            candidate.startswith(token) for candidate in paragraph_token_set
        ):
            prefix += 1
    score = exact * _EXACT_MATCH_WEIGHT + prefix * _PREFIX_MATCH_WEIGHT
    return score, exact, prefix


def search_target_lexical_paragraph_index(
    index: TargetLexicalParagraphIndex,
    query: str,
    *,
    limit: int = 10,
) -> tuple[TargetLexicalSearchHit, ...]:
    """Pure in-memory Python token-overlap + prefix search (Option A). No SQLite, no network.

    ``query``/matched raw text are never logged by this function -- callers must uphold the same
    discipline (this module has no logging calls at all). An empty/whitespace-only query or a
    non-positive ``limit`` is a typed validation error, never a silent empty result and never a
    network/LLM call. A well-formed but entirely non-lexical query (e.g. pure punctuation) is not
    an error -- it legitimately produces zero tokens and therefore zero hits.
    """

    if type(index) is not TargetLexicalParagraphIndex:
        _fail("lexical_index_search_index_invalid", type(index).__name__)
    if type(query) is not str:
        _fail("lexical_index_search_query_invalid", type(query).__name__)
    if not query.strip():
        _fail("lexical_index_search_query_empty", "")
    if type(limit) is not int or isinstance(limit, bool) or limit <= 0:
        _fail("lexical_index_search_limit_invalid", limit)

    query_tokens = tuple(dict.fromkeys(_tokenize(query)))
    if not query_tokens:
        return ()

    scored: list[tuple[int, int, int, TargetLexicalParagraph]] = []
    for paragraph in index.paragraphs:
        paragraph_tokens = tuple(paragraph.normalized_searchable_text.split())
        score, exact, prefix = _score_paragraph(paragraph_tokens, query_tokens)
        if score > 0:
            scored.append((score, exact, prefix, paragraph))

    scored.sort(key=lambda item: (-item[0], item[3].paragraph_id))
    return tuple(
        TargetLexicalSearchHit(
            paragraph=paragraph,
            score=score,
            exact_token_matches=exact,
            prefix_token_matches=prefix,
        )
        for score, exact, prefix, paragraph in scored[:limit]
    )
