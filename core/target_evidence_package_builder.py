"""Local offline Evidence Package builder (PERF-7B, unwired).

**Not wired to any runtime path.** Nothing in ``app.py``, the Composer/Verifier pipeline, or
``TurnFrame`` handling imports this module. One canonical producer,
``build_target_evidence_package``, combines four independent, already-existing sources -- never a
new content authority, never a second parser, never a service/topic/group tier ladder (PERF-6's own
``service_exact -> topic -> context_group -> full`` ladder is explicitly *not* extended or reused
here, per the owner's PERF-7 direction):

1. **Exact evidence** -- read directly from the already-materialized
   ``TargetComposerRequest.evidence_blocks`` (no new closure-computation logic, mirroring the exact
   precedent ``core/target_context_scope_resolver.py`` already established for PERF-6's own
   ``service_exact`` tier).
2. **Lexical retrieval** -- an auxiliary, non-authoritative signal via the existing, unmodified
   ``core/target_lexical_paragraph_index.py::search_target_lexical_paragraph_index`` public API
   only. Never a router: only used when exact evidence leaves a real gap, and only accepted when it
   meets an explainable, already-existing typed bar (an exact token match, an unambiguous top
   document) -- never an invented numeric confidence score.
3. **Explicit session projection** -- ``session_derived_refs``/``explicit_followup`` are caller-
   supplied parameters. This module never reads session state, a ``ContextVar``, a Flask request,
   or any global itself.
4. **FullContext fallback** -- chosen conservatively, before any (still entirely hypothetical,
   still unauthorized) single Composer call, whenever exact evidence and lexical retrieval together
   cannot honestly prove sufficiency. A fallback package is a normal, valid outcome, never an
   error, never a retry trigger, never something surfaced to a user.

**Honesty over completeness.** Zero, ambiguous, or prefix-only-weak lexical hits are deliberately
*never* treated as sufficient to mark a package complete -- they trigger FullContext fallback. This
milestone does not calibrate lexical recall (that is PERF-7C's job); this Builder is written to be
conservative until that calibration exists, not to make today's tests pass by being lenient.

**PERF-6 status (unchanged by this milestone):** the real Composer/Verifier pipeline still receives
the full cached FullContext corpus unconditionally, via PERF-6's own already-shipped, still-active
shadow hook in ``core/target_policy_bound_verified_response_pipeline.py``. This Builder is not
called from that hook and does not replace it. No speedup exists yet from either milestone.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from contracts.target_evidence_package import (
    TargetEvidencePackage,
    TargetEvidenceProvenance,
    TargetEvidenceStructuredRecordIds,
)
from contracts.target_response_spec import TargetResponseSpec
from contracts.target_cached_full_context import TargetCachedFullContext
from core.target_composer_request import TargetComposerEvidenceBlock, TargetComposerRequest
from core.target_lexical_paragraph_index import (
    TargetLexicalParagraphIndex,
    TargetLexicalParagraphIndexError,
    TargetLexicalSearchHit,
    search_target_lexical_paragraph_index,
)

__all__ = ["build_target_evidence_package", "TargetEvidencePackageBuilderError"]

EVIDENCE_PACKAGE_SCHEMA_VERSION = 1
_LEXICAL_SEARCH_LIMIT = 8
_MIN_EXACT_TOKEN_MATCHES_TO_TRUST = 1  # a categorical fact ("was there any real token match"),
# never an invented confidence score -- see module docstring point 2.


class TargetEvidencePackageBuilderError(ValueError):
    """Typed fail-closed PERF-7B input-contract failure (caller error, not a runtime ambiguity)."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _fail(code: str, value: object, cause: BaseException | None = None) -> NoReturn:
    error = TargetEvidencePackageBuilderError(code, value)
    if cause is None:
        raise error
    raise error from cause


class _StructuralInconsistency(Exception):
    """Internal-only signal: a claimed-safe ref could not be read back. Always converted to a
    conservative FullContext-fallback package by the caller -- never re-raised to the outside."""

    def __init__(self, reason: str) -> None:
        self.reason = reason


def _dedup(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: list[str] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return tuple(seen)


# --------------------------------------------------------------------------------------------
# Exact evidence extraction (reads only the already-materialized TargetComposerRequest)
# --------------------------------------------------------------------------------------------


def _strip_doc_ref(raw: str) -> str:
    """``content:{file}`` / ``content:{file}#{anchor}`` / ``kb:{file}#{anchor}`` -> ``{file}``."""

    value = raw
    if value.startswith("content:"):
        value = value.removeprefix("content:")
    elif value.startswith("kb:"):
        value = value.removeprefix("kb:")
    if "#" in value:
        value = value.split("#", 1)[0]
    return value


@dataclass(frozen=True, slots=True)
class _ExactClosure:
    content_refs: tuple[str, ...]
    offer_ids: tuple[str, ...]
    fact_ids: tuple[str, ...]
    doctor_ids: tuple[str, ...]
    policy_sections: tuple[str, ...]
    evidence_block_refs: tuple[str, ...]


def _extract_exact_closure(request: TargetComposerRequest) -> _ExactClosure:
    content_refs: list[str] = []
    offer_ids: list[str] = []
    fact_ids: list[str] = []
    doctor_ids: list[str] = []
    policy_sections: list[str] = []
    evidence_block_refs: list[str] = []

    for block in request.evidence_blocks:
        evidence_block_refs.append(block.ref)
        if block.kind in ("content", "external_kb"):
            content_refs.append(_strip_doc_ref(block.ref))
        elif block.kind == "offer":
            offer_ids.append(block.ref.removeprefix("offer:"))
        elif block.kind == "commercial_fact":
            fact_ids.append(block.ref.removeprefix("fact:"))
        elif block.kind in ("doctor", "external_doctor"):
            doctor_ids.append(block.ref.removeprefix("doctor:"))
        elif block.kind == "clinic_contact":
            policy_sections.append(block.ref.removeprefix("clinic_contact:"))
        elif block.kind == "consultation":
            content_refs.append(_strip_doc_ref(block.ref.removeprefix("consultation:")))
        # No else branch: TargetComposerEvidenceBlock.kind is a closed Literal, already validated
        # at materialization time -- an unrecognized kind is structurally impossible here.

    return _ExactClosure(
        content_refs=_dedup(tuple(content_refs)),
        offer_ids=_dedup(tuple(offer_ids)),
        fact_ids=_dedup(tuple(fact_ids)),
        doctor_ids=_dedup(tuple(doctor_ids)),
        policy_sections=_dedup(tuple(policy_sections)),
        evidence_block_refs=_dedup(tuple(evidence_block_refs)),
    )


def _document_types(index: TargetLexicalParagraphIndex) -> dict[str, str | None]:
    types: dict[str, str | None] = {}
    for paragraph in index.paragraphs:
        if paragraph.document_path not in types:
            types[paragraph.document_path] = paragraph.document_type
    return types


# --------------------------------------------------------------------------------------------
# Conservative completeness
# --------------------------------------------------------------------------------------------


def _missing_deficits(
    spec: TargetResponseSpec,
    closure: _ExactClosure,
    *,
    comparison_required: bool,
    document_types: dict[str, str | None],
) -> list[str]:
    missing: list[str] = []
    if not set(spec.required_fact_ids).issubset(set(closure.fact_ids)):
        missing.append("fact")
    if "price" in spec.required_components and not closure.offer_ids:
        missing.append("offer")
    if "doctors" in spec.required_components and not closure.doctor_ids:
        missing.append("doctor")
    if "content" in spec.required_components and not closure.content_refs:
        missing.append("content")
    if comparison_required and not any(
        document_types.get(ref) == "comparison" for ref in closure.content_refs
    ):
        missing.append("comparison")
    return missing


# --------------------------------------------------------------------------------------------
# Deterministic serialized size (chars actually already present -- never a claimed future HTTP
# prompt size; see module/contract docstrings for exactly what this is and is not).
# --------------------------------------------------------------------------------------------

_DOCUMENT_BACKED_KINDS = frozenset({"content", "external_kb", "consultation"})


def _wrapped_document_text(text: str, relative_ref: str) -> str:
    # Same stable wrapper shape core/target_cached_full_context.py documents publicly (its own
    # module docstring, not a private symbol) -- reused conceptually, not imported, since building
    # one small formatted string is not "a large parser" worth cross-module coupling for.
    return f"---BEGIN DOC:{relative_ref}---\n{text.rstrip(chr(10))}\n---END DOC:{relative_ref}---"


def _document_sizes(md_root: Path, refs: tuple[str, ...]) -> dict[str, tuple[int, str]]:
    resolved_root = md_root.resolve()
    sizes: dict[str, tuple[int, str]] = {}
    for ref in refs:
        try:
            candidate = md_root.joinpath(*ref.split("/")).resolve()
            if not candidate.is_relative_to(resolved_root) or not candidate.is_file():
                raise _StructuralInconsistency("selected_document_unreadable")
            text = candidate.read_text(encoding="utf-8")
        except (OSError, RuntimeError, UnicodeDecodeError) as exc:
            raise _StructuralInconsistency("selected_document_unreadable") from exc
        wrapped = _wrapped_document_text(text, ref)
        sizes[ref] = (len(wrapped), hashlib.sha256(wrapped.encode("utf-8")).hexdigest())
    return sizes


def _structured_evidence_chars(evidence_blocks: tuple[TargetComposerEvidenceBlock, ...]) -> int:
    return sum(len(block.text) for block in evidence_blocks if block.kind not in _DOCUMENT_BACKED_KINDS)


# --------------------------------------------------------------------------------------------
# Fingerprint (namespace-tagged, hash/ID-only payload -- never raw text)
# --------------------------------------------------------------------------------------------


def _fingerprint(
    *,
    document_sizes: dict[str, tuple[int, str]],
    evidence_blocks: tuple[TargetComposerEvidenceBlock, ...],
    structured: _ExactClosure,
    session_refs: tuple[str, ...],
    retrieval_refs: tuple[str, ...],
    completeness_status: str,
    fallback_reason: str | None,
) -> str:
    md_entries = sorted(f"md:{ref}:{digest}" for ref, (_chars, digest) in document_sizes.items())
    block_entries = sorted(
        f"{block.ref}:{hashlib.sha256(block.text.encode('utf-8')).hexdigest()[:16]}"
        for block in evidence_blocks
    )
    offer_entries = sorted(f"offer:{value}" for value in structured.offer_ids)
    fact_entries = sorted(f"fact:{value}" for value in structured.fact_ids)
    doctor_entries = sorted(f"doctor:{value}" for value in structured.doctor_ids)
    policy_entries = sorted(f"policy:{value}" for value in structured.policy_sections)
    session_entries = sorted(f"session:{value}" for value in session_refs)
    retrieval_entries = sorted(f"retrieval:{value}" for value in retrieval_refs)
    payload = "|".join(
        [
            str(EVIDENCE_PACKAGE_SCHEMA_VERSION),
            completeness_status,
            fallback_reason or "",
            ",".join(md_entries),
            ",".join(block_entries),
            ",".join(offer_entries),
            ",".join(fact_entries),
            ",".join(doctor_entries),
            ",".join(policy_entries),
            ",".join(session_entries),
            ",".join(retrieval_entries),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------------------------
# Provenance assembly (namespace-tagged structured-record refs -- never a bare id collision)
# --------------------------------------------------------------------------------------------


def _provenance_list(
    *,
    evidence_block_refs: tuple[str, ...],
    exact_content_refs: tuple[str, ...],
    structured: _ExactClosure,
    session_refs: tuple[str, ...],
    retrieval_refs: tuple[str, ...],
    fallback_ref: tuple[str, str] | None,
) -> tuple[TargetEvidenceProvenance, ...]:
    entries: list[TargetEvidenceProvenance] = []
    seen: set[str] = set()

    def add(ref: str, source: str, reason: str) -> None:
        if ref in seen:
            return
        seen.add(ref)
        entries.append(TargetEvidenceProvenance(ref=ref, source=source, reason=reason))

    for ref in evidence_block_refs:
        add(ref, "evidence_block", "materialized_evidence_block")
    for ref in exact_content_refs:
        add(ref, "exact_content_ref", "exact_content_reference")
    for value in structured.offer_ids:
        add(f"offer:{value}", "structured_record", "structured_record_id")
    for value in structured.fact_ids:
        add(f"fact:{value}", "structured_record", "structured_record_id")
    for value in structured.doctor_ids:
        add(f"doctor:{value}", "structured_record", "structured_record_id")
    for value in structured.policy_sections:
        add(f"policy:{value}", "structured_record", "structured_record_id")
    for ref in session_refs:
        add(ref, "session_projection", "explicit_session_followup")
    for ref in retrieval_refs:
        add(ref, "lexical_retrieval", "lexical_token_match")
    if fallback_ref is not None:
        ref, reason = fallback_ref
        add(ref, "fullcontext_fallback", reason)

    return tuple(entries)


# --------------------------------------------------------------------------------------------
# FullContext fallback assembly
# --------------------------------------------------------------------------------------------


def _fullcontext_fallback_package(
    request: TargetComposerRequest,
    cached_full_context: TargetCachedFullContext,
    *,
    reason: str,
) -> TargetEvidencePackage:
    closure = _extract_exact_closure(request)
    selected_md_refs = tuple(sorted(cached_full_context.document_paths))

    structured_chars = _structured_evidence_chars(request.evidence_blocks)
    serialized_chars = len(cached_full_context.corpus_text) + structured_chars

    document_sizes = {"fullcontext": (len(cached_full_context.corpus_text), cached_full_context.sha256)}
    fingerprint = _fingerprint(
        document_sizes=document_sizes,
        evidence_blocks=request.evidence_blocks,
        structured=closure,
        session_refs=(),
        retrieval_refs=(),
        completeness_status="fullcontext_fallback",
        fallback_reason=reason,
    )

    provenance = _provenance_list(
        evidence_block_refs=closure.evidence_block_refs,
        exact_content_refs=(),
        structured=closure,
        session_refs=(),
        retrieval_refs=(),
        fallback_ref=("fullcontext", reason),
    )

    return TargetEvidencePackage(
        selected_md_refs=selected_md_refs,
        selected_paragraph_refs=(),
        exact_evidence_block_refs=closure.evidence_block_refs,
        structured_record_ids=TargetEvidenceStructuredRecordIds(
            offer_ids=closure.offer_ids,
            fact_ids=closure.fact_ids,
            doctor_ids=closure.doctor_ids,
            policy_sections=closure.policy_sections,
        ),
        session_derived_refs=(),
        retrieval_derived_refs=(),
        provenance=provenance,
        completeness_status="fullcontext_fallback",
        fallback_reason=reason,
        serialized_context_chars=serialized_chars,
        estimated_tokens=serialized_chars // 4,
        package_fingerprint=fingerprint,
    )


# --------------------------------------------------------------------------------------------
# Input validation
# --------------------------------------------------------------------------------------------


def _require_md_root(md_root: object) -> Path:
    if not isinstance(md_root, Path):
        _fail("evidence_package_md_root_invalid", md_root)
    if not md_root.exists() or not md_root.is_dir():
        _fail("evidence_package_md_root_invalid", md_root)
    return md_root


def _validated_inputs(
    request: object,
    lexical_index: object,
    cached_full_context: object,
    *,
    md_root: object,
    explicit_followup: object,
    session_derived_refs: object,
    comparison_required: object,
) -> tuple[TargetComposerRequest, TargetLexicalParagraphIndex, TargetCachedFullContext, Path]:
    if type(request) is not TargetComposerRequest:
        _fail("evidence_package_request_invalid", type(request).__name__)
    if type(lexical_index) is not TargetLexicalParagraphIndex:
        _fail("evidence_package_lexical_index_invalid", type(lexical_index).__name__)
    if type(cached_full_context) is not TargetCachedFullContext:
        _fail("evidence_package_full_context_invalid", type(cached_full_context).__name__)
    root = _require_md_root(md_root)
    if type(explicit_followup) is not bool:
        _fail("evidence_package_explicit_followup_invalid", explicit_followup)
    if type(session_derived_refs) is not tuple or not all(
        type(item) is str for item in session_derived_refs
    ):
        _fail("evidence_package_session_refs_invalid", session_derived_refs)
    if type(comparison_required) is not bool:
        _fail("evidence_package_comparison_required_invalid", comparison_required)
    if not explicit_followup and session_derived_refs:
        _fail("evidence_package_session_refs_without_explicit_followup", session_derived_refs)
    return request, lexical_index, cached_full_context, root


# --------------------------------------------------------------------------------------------
# Public canonical producer
# --------------------------------------------------------------------------------------------


def build_target_evidence_package(
    request: TargetComposerRequest,
    lexical_index: TargetLexicalParagraphIndex,
    cached_full_context: TargetCachedFullContext,
    *,
    md_root: Path,
    explicit_followup: bool = False,
    session_derived_refs: tuple[str, ...] = (),
    comparison_required: bool = False,
) -> TargetEvidencePackage:
    """Build one local, offline ``TargetEvidencePackage``. Pure, deterministic, no LLM/network call.

    Reads ``request.user_message`` only to build a lexical search query -- never places it, the
    candidate answer, a session id, or a contact value on the returned package, in a cache, or in a
    log line (this module performs no logging at all). Never reads session state itself:
    ``session_derived_refs`` must be supplied explicitly by the caller, and is only ever accepted
    when ``explicit_followup=True``. This Builder knows nothing about PERF-6's
    ``service_exact``/``topic``/``context_group`` tiers -- there is exactly one code path here, not
    a ladder.
    """

    request, lexical_index, cached_full_context, root = _validated_inputs(
        request,
        lexical_index,
        cached_full_context,
        md_root=md_root,
        explicit_followup=explicit_followup,
        session_derived_refs=session_derived_refs,
        comparison_required=comparison_required,
    )

    index_document_paths = frozenset(p.document_path for p in lexical_index.paragraphs)
    full_context_document_paths = frozenset(cached_full_context.document_paths)
    if index_document_paths != full_context_document_paths:
        return _fullcontext_fallback_package(
            request,
            cached_full_context,
            reason="lexical_index_full_context_document_set_mismatch",
        )

    validated_session_refs: list[str] = []
    if explicit_followup:
        for ref in session_derived_refs:
            if ref not in index_document_paths:
                return _fullcontext_fallback_package(
                    request, cached_full_context, reason="unknown_session_ref"
                )
            validated_session_refs.append(ref)
    validated_session_refs = list(_dedup(tuple(validated_session_refs)))

    closure = _extract_exact_closure(request)
    document_types = _document_types(lexical_index)
    missing = _missing_deficits(
        request.spec,
        closure,
        comparison_required=comparison_required,
        document_types=document_types,
    )

    structural_missing = {"fact", "offer", "doctor"} & set(missing)
    if structural_missing:
        return _fullcontext_fallback_package(
            request,
            cached_full_context,
            reason="structured_evidence_incomplete_requires_fullcontext",
        )

    retrieval_content_refs: list[str] = []
    retrieval_paragraph_refs: list[str] = []
    widened = False

    if missing:  # only "content" and/or "comparison" can remain at this point
        try:
            hits: tuple[TargetLexicalSearchHit, ...] = search_target_lexical_paragraph_index(
                lexical_index, request.user_message, limit=_LEXICAL_SEARCH_LIMIT
            )
        except TargetLexicalParagraphIndexError:
            hits = ()

        eligible = [hit for hit in hits if hit.exact_token_matches >= _MIN_EXACT_TOKEN_MATCHES_TO_TRUST]
        if not eligible:
            reason = "lexical_zero_hits" if not hits else "lexical_only_weak_prefix_matches"
            return _fullcontext_fallback_package(request, cached_full_context, reason=reason)

        best_by_document: dict[str, TargetLexicalSearchHit] = {}
        for hit in eligible:
            document_path = hit.paragraph.document_path
            current_best = best_by_document.get(document_path)
            if current_best is None or hit.score > current_best.score:
                best_by_document[document_path] = hit

        top_score = max(hit.score for hit in best_by_document.values())
        top_documents = sorted(
            document_path
            for document_path, hit in best_by_document.items()
            if hit.score == top_score
        )
        if len(top_documents) > 1:
            return _fullcontext_fallback_package(
                request, cached_full_context, reason="lexical_ambiguous_top_match"
            )

        top_document = top_documents[0]
        top_hit = best_by_document[top_document]

        if "content" in missing:
            retrieval_content_refs.append(top_document)
            retrieval_paragraph_refs.append(top_hit.paragraph.paragraph_id)
            widened = True

        if "comparison" in missing:
            if document_types.get(top_document) != "comparison":
                return _fullcontext_fallback_package(
                    request, cached_full_context, reason="lexical_no_comparison_document_found"
                )
            if top_document not in retrieval_content_refs:
                retrieval_content_refs.append(top_document)
            if top_hit.paragraph.paragraph_id not in retrieval_paragraph_refs:
                retrieval_paragraph_refs.append(top_hit.paragraph.paragraph_id)
            widened = True

    retrieval_content_refs = list(_dedup(tuple(retrieval_content_refs)))
    retrieval_paragraph_refs = list(_dedup(tuple(retrieval_paragraph_refs)))

    selected_md_refs = _dedup(
        (*closure.content_refs, *retrieval_content_refs, *tuple(validated_session_refs))
    )
    selected_paragraph_refs = _dedup(tuple(retrieval_paragraph_refs))
    retrieval_derived_refs = _dedup((*retrieval_content_refs, *retrieval_paragraph_refs))

    completeness_status = "insufficient_widened" if widened else "complete"
    fallback_reason = (
        "exact_evidence_incomplete_widened_via_lexical_retrieval" if widened else None
    )

    try:
        document_sizes = _document_sizes(root, selected_md_refs)
    except _StructuralInconsistency as exc:
        return _fullcontext_fallback_package(request, cached_full_context, reason=exc.reason)

    structured_chars = _structured_evidence_chars(request.evidence_blocks)
    serialized_chars = sum(chars for chars, _digest in document_sizes.values()) + structured_chars

    fingerprint = _fingerprint(
        document_sizes=document_sizes,
        evidence_blocks=request.evidence_blocks,
        structured=closure,
        session_refs=tuple(validated_session_refs),
        retrieval_refs=retrieval_derived_refs,
        completeness_status=completeness_status,
        fallback_reason=fallback_reason,
    )

    provenance = _provenance_list(
        evidence_block_refs=closure.evidence_block_refs,
        exact_content_refs=closure.content_refs,
        structured=closure,
        session_refs=tuple(validated_session_refs),
        retrieval_refs=retrieval_derived_refs,
        fallback_ref=None,
    )

    return TargetEvidencePackage(
        selected_md_refs=selected_md_refs,
        selected_paragraph_refs=selected_paragraph_refs,
        exact_evidence_block_refs=closure.evidence_block_refs,
        structured_record_ids=TargetEvidenceStructuredRecordIds(
            offer_ids=closure.offer_ids,
            fact_ids=closure.fact_ids,
            doctor_ids=closure.doctor_ids,
            policy_sections=closure.policy_sections,
        ),
        session_derived_refs=tuple(validated_session_refs),
        retrieval_derived_refs=retrieval_derived_refs,
        provenance=provenance,
        completeness_status=completeness_status,
        fallback_reason=fallback_reason,
        serialized_context_chars=serialized_chars,
        estimated_tokens=serialized_chars // 4,
        package_fingerprint=fingerprint,
    )
