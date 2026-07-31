"""PERF-8 Phase 1 retrieval-executor: candidate B (weighted-lexical) and candidate C
(SQLite FTS5/BM25) retrieval prototypes, plus the shared corpus-loading helpers they use.

**New, unwired research code.** Nothing here is imported by any runtime path, `app.py`, the
Composer/Verifier pipeline, or any file under ``core/``/``contracts/``/``clients/``. It exists only
to be driven by ``evals/v5/run_perf8_retrieval_relevance_comparison.py`` for the PERF-8 Phase 1
retrieval-relevance comparison study.

Read-only reuse: this module imports the already-shipped, unmodified
``core.target_lexical_paragraph_index.build_target_lexical_paragraph_index`` to get the corpus's
paragraph/document/topic records (same MD-parsing precedent the real production Builder uses) --
no MD parsing is re-implemented here. Everything downstream of that import (IDF computation,
coverage scoring, margin gating, the FTS5 table build, BM25 ranking, MATCH-expression sanitization)
is this module's own new code, per this milestone's brief.

No network calls, no package installs, no LLM/provider calls anywhere in this file.
"""

from __future__ import annotations

import math
import re
import sqlite3
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from core.target_lexical_paragraph_index import (
    TargetLexicalParagraphIndex,
    build_target_lexical_paragraph_index,
)

__all__ = [
    "CandidateOutcome",
    "load_corpus_index",
    "build_document_token_sets",
    "build_document_topic_map",
    "build_document_char_lengths",
    "build_idf_table",
    "candidate_b_decide",
    "build_fts5_index",
    "candidate_c_decide",
    "tokenize_query",
]


# --------------------------------------------------------------------------------------------
# Shared query tokenizer (this module's own, small, new code -- not imported from core's private
# ``_tokenize``/``_normalize_text`` helpers, which are module-private to
# ``core/target_lexical_paragraph_index.py`` and not part of that module's public ``__all__``).
# Deliberately mirrors the same "Cyrillic/Latin/digit runs, NFKC, casefold, ё->е" shape as the
# existing precedent (restated, not imported), the same way that module itself restated
# ``core/target_composer_request.py``'s heading rule instead of importing its private names.
# --------------------------------------------------------------------------------------------

_TOKEN_CHARS_RE = re.compile(r"[a-zа-я0-9]+")


def tokenize_query(text: str) -> tuple[str, ...]:
    """Deterministic query tokenizer: NFKC normalize, ё/Ё -> е/Е, casefold, alnum runs only."""

    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("ё", "е").replace("Ё", "Е")
    normalized = normalized.casefold()
    tokens = _TOKEN_CHARS_RE.findall(normalized)
    # de-duplicate, preserve first-seen order (same convention as core's own search function)
    return tuple(dict.fromkeys(tokens))


# --------------------------------------------------------------------------------------------
# Corpus loading (read-only reuse of the existing, unmodified PERF-7A builder)
# --------------------------------------------------------------------------------------------


def load_corpus_index(md_root: Path) -> TargetLexicalParagraphIndex:
    return build_target_lexical_paragraph_index(md_root)


def build_document_token_sets(index: TargetLexicalParagraphIndex) -> dict[str, set[str]]:
    """One token set per document, built from the index's already-normalized paragraph text.

    Reuses ``TargetLexicalParagraph.normalized_searchable_text`` (a public dataclass field --
    already-normalized, space-joined tokens) rather than re-normalizing raw MD ourselves.
    """

    doc_tokens: dict[str, set[str]] = {}
    for paragraph in index.paragraphs:
        bucket = doc_tokens.setdefault(paragraph.document_path, set())
        bucket.update(paragraph.normalized_searchable_text.split())
    return doc_tokens


def build_document_topic_map(index: TargetLexicalParagraphIndex) -> dict[str, str | None]:
    topics: dict[str, str | None] = {}
    for paragraph in index.paragraphs:
        topics.setdefault(paragraph.document_path, paragraph.topic)
    return topics


def build_document_char_lengths(md_root: Path, document_paths: list[str]) -> dict[str, int]:
    """Character length of each real MD file on disk (rough token-count proxy)."""

    lengths: dict[str, int] = {}
    for relative_posix in document_paths:
        path = md_root / relative_posix
        try:
            lengths[relative_posix] = len(path.read_text(encoding="utf-8-sig"))
        except OSError:
            lengths[relative_posix] = 0
    return lengths


# --------------------------------------------------------------------------------------------
# Shared candidate-outcome contract
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CandidateOutcome:
    """One candidate's decision for one scenario.

    ``decision`` is the selected MD filename, or ``None`` for fallback (post-gate). ``raw_top3`` is
    the raw ranked distinct document list *before* the conservative accept/decline gate is applied
    -- diagnostic only, used for recall@3 / unrelated_top_candidate_count. ``elapsed_ms`` is the
    wall-clock time this single scenario's decision took (build time is amortized/measured
    separately by the caller, per the brief).
    """

    decision: str | None
    raw_top3: tuple[str, ...]
    elapsed_ms: float


# --------------------------------------------------------------------------------------------
# Candidate B: conservative weighted-lexical (IDF coverage + margin gate + topic-hint bonus)
# --------------------------------------------------------------------------------------------

# Smoothed IDF, standard sklearn-style smoothing: idf(t) = ln((N+1)/(df(t)+1)) + 1. df=0 (a query
# token never seen anywhere in the 55-doc corpus) yields the *maximum* weight, which is harmless
# here because such a token also can never be "matched" by any document (matched_weight only sums
# weights of tokens actually present in a candidate document's token set).
_IDF_SMOOTHING_NUMERATOR_OFFSET = 1
_IDF_SMOOTHING_DENOMINATOR_OFFSET = 1

# Topic-hint bonus: a small additive nudge (not a requirement, not a filter) applied to a
# document's coverage score when the document's own frontmatter `topic:` is among the scenario's
# `topic_hint`. Kept well below 1.0 (the maximum possible coverage) so a document with weak lexical
# coverage can never win purely on topic match -- the query text remains the primary signal.
_TOPIC_HINT_BONUS = 0.08

# Exploratory acceptance bar. These values were selected after inspecting aggregate score
# distributions on the same 49-scenario development matrix used by this comparison. Consequently
# candidate B's measured zero-false-narrow result is descriptive only: it is not independent
# holdout evidence and must not authorize runtime wiring. The comparison runner records that
# limitation explicitly in its top-level decision.
_MIN_TOP_COVERAGE = 0.45
_MIN_TOP_MARGIN = 0.35


def build_idf_table(index: TargetLexicalParagraphIndex, document_token_sets: dict[str, set[str]]) -> dict[str, float]:
    doc_count = len(document_token_sets) or 1
    document_frequency: dict[str, int] = {}
    for tokens in document_token_sets.values():
        for token in tokens:
            document_frequency[token] = document_frequency.get(token, 0) + 1
    return {
        token: math.log(
            (doc_count + _IDF_SMOOTHING_NUMERATOR_OFFSET) / (df + _IDF_SMOOTHING_DENOMINATOR_OFFSET)
        )
        + 1.0
        for token, df in document_frequency.items()
    }


def candidate_b_decide(
    query: str,
    *,
    document_token_sets: dict[str, set[str]],
    idf: dict[str, float],
    document_topics: dict[str, str | None],
    topic_hint: tuple[str, ...],
) -> CandidateOutcome:
    started = time.perf_counter()
    query_tokens = tokenize_query(query)
    if not query_tokens:
        return CandidateOutcome(decision=None, raw_top3=(), elapsed_ms=(time.perf_counter() - started) * 1000)

    total_weight = sum(idf.get(token, 0.0) for token in query_tokens)
    scores: list[tuple[float, str]] = []
    for document_path, tokens in document_token_sets.items():
        if total_weight <= 0:
            coverage = 0.0
        else:
            matched_weight = sum(idf.get(token, 0.0) for token in query_tokens if token in tokens)
            coverage = matched_weight / total_weight
        bonus = 0.0
        if topic_hint and document_topics.get(document_path) in topic_hint:
            bonus = _TOPIC_HINT_BONUS
        scores.append((coverage + bonus, document_path))

    # Rank by score desc, then document path asc for deterministic tie-break.
    scores.sort(key=lambda item: (-item[0], item[1]))
    raw_top3 = tuple(document_path for _, document_path in scores[:3])

    top1_score, top1_doc = scores[0]
    top2_score = scores[1][0] if len(scores) > 1 else 0.0
    margin = top1_score - top2_score

    decision: str | None = None
    if top1_score >= _MIN_TOP_COVERAGE and margin >= _MIN_TOP_MARGIN:
        decision = top1_doc

    elapsed_ms = (time.perf_counter() - started) * 1000
    return CandidateOutcome(decision=decision, raw_top3=raw_top3, elapsed_ms=elapsed_ms)


# --------------------------------------------------------------------------------------------
# Candidate C: in-memory SQLite FTS5 + bm25() prototype
# --------------------------------------------------------------------------------------------

# SQLite's bm25() returns *more negative == more relevant* (see SQLite FTS5 docs). We negate it
# into a "higher is better" relevance score before applying the same margin-gate shape as B, so
# both prototypes' gates read the same way in the result file and in this module's own logic.
# These constants were tuned on the same development matrix as candidate B. Candidate C is
# therefore also exploratory rather than independent evidence of safe generalization.
_MIN_BM25_RELEVANCE = 8.0
_MIN_BM25_MARGIN = 6.0


def build_fts5_index(index: TargetLexicalParagraphIndex) -> sqlite3.Connection:
    """Build a fresh in-memory FTS5 virtual table from the corpus's already-split paragraphs.

    Indexes each paragraph's already-normalized ``normalized_searchable_text`` (public field, same
    reuse precedent as candidate B) as the FTS5 ``body`` column, with ``doc_path`` carried as an
    UNINDEXED column for document-level aggregation. No raw user text is ever interpolated into
    SQL -- inserts use parameter binding, and queries use a sanitized, fully-quoted MATCH
    expression built only from this module's own tokenizer output (see
    ``_build_safe_match_expression``).
    """

    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE VIRTUAL TABLE paragraphs USING fts5(doc_path UNINDEXED, body)")
    connection.executemany(
        "INSERT INTO paragraphs (doc_path, body) VALUES (?, ?)",
        (
            (paragraph.document_path, paragraph.normalized_searchable_text)
            for paragraph in index.paragraphs
        ),
    )
    connection.commit()
    return connection


def _build_safe_match_expression(query_tokens: tuple[str, ...]) -> str | None:
    """Build a safe FTS5 MATCH expression from already-tokenized (alnum-only) query terms.

    Every term is individually double-quoted, which makes it a literal FTS5 string token even if
    it happened to collide with an FTS5 query-language keyword (AND/OR/NOT/NEAR) -- and since
    ``tokenize_query`` only ever emits ``[a-zа-я0-9]+`` runs, there is no quote character, operator,
    or column-filter syntax a caller-supplied query string could ever smuggle into this
    expression. A raw, unsanitized user string is never passed to ``MATCH``.
    """

    if not query_tokens:
        return None
    quoted_terms = [f'"{token}"' for token in query_tokens]
    return " OR ".join(quoted_terms)


def candidate_c_decide(query: str, connection: sqlite3.Connection) -> CandidateOutcome:
    started = time.perf_counter()
    query_tokens = tokenize_query(query)
    match_expression = _build_safe_match_expression(query_tokens)
    if match_expression is None:
        return CandidateOutcome(decision=None, raw_top3=(), elapsed_ms=(time.perf_counter() - started) * 1000)

    rows = connection.execute(
        "SELECT doc_path, bm25(paragraphs) AS raw_score FROM paragraphs "
        "WHERE paragraphs MATCH ? ORDER BY raw_score ASC LIMIT 50",
        (match_expression,),
    ).fetchall()

    best_relevance_by_doc: dict[str, float] = {}
    for doc_path, raw_score in rows:
        relevance = -float(raw_score)  # flip sign: higher now means more relevant
        current = best_relevance_by_doc.get(doc_path)
        if current is None or relevance > current:
            best_relevance_by_doc[doc_path] = relevance

    if not best_relevance_by_doc:
        return CandidateOutcome(decision=None, raw_top3=(), elapsed_ms=(time.perf_counter() - started) * 1000)

    ranked = sorted(best_relevance_by_doc.items(), key=lambda item: (-item[1], item[0]))
    raw_top3 = tuple(doc_path for doc_path, _ in ranked[:3])

    top1_doc, top1_relevance = ranked[0]
    top2_relevance = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = top1_relevance - top2_relevance

    decision: str | None = None
    if top1_relevance >= _MIN_BM25_RELEVANCE and margin >= _MIN_BM25_MARGIN:
        decision = top1_doc

    elapsed_ms = (time.perf_counter() - started) * 1000
    return CandidateOutcome(decision=decision, raw_top3=raw_top3, elapsed_ms=elapsed_ms)
