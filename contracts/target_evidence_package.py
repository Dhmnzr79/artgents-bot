"""Canonical local Evidence Package contract (PERF-7B, offline/unwired).

Immutable, strict, anonymized. Never carries a raw question, a raw answer, a session id, a
contact value, an absolute filesystem path, or MD/evidence prose beyond short reference-shaped
identifiers -- every field is a reference ID, an enum, a count, or a hash. Produced by exactly one
canonical builder (``core/target_evidence_package_builder.py::build_target_evidence_package``).

This contract is measurement/design-stage only: nothing reads it to change the real Composer/
Verifier invocation in this milestone. See
``docs/evidence/performance/FINAL_LOCAL_EVIDENCE_PACKAGE_BUILDER_FOUNDATION_SEAM_AUDIT.md`` §9 for
the original Phase 1 design this contract implements (the field named ``estimated_chars`` there is
renamed ``serialized_context_chars`` here -- a documented contract clarification, not a silent
deviation: it names exactly what is measured, deterministic serialization of the *selected*
evidence, never a claim about the real future HTTP prompt size once a Scoped Composer exists).
"""

from __future__ import annotations

import re
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

EvidencePackageCompletenessStatus: TypeAlias = Literal[
    "complete",
    "insufficient_widened",
    "fullcontext_fallback",
]
EvidencePackageProvenanceSource: TypeAlias = Literal[
    "evidence_block",
    "exact_content_ref",
    "structured_record",
    "session_projection",
    "lexical_retrieval",
    "fullcontext_fallback",
]

_CANONICAL_TOKEN_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]|^[\\/]")


def _is_canonical_ref(value: str) -> bool:
    if not value or value != value.strip():
        return False
    if "\\" in value:
        return False
    if _ABSOLUTE_PATH_RE.match(value):
        return False
    return True


def _validated_ref_tuple(value: tuple[str, ...]) -> tuple[str, ...]:
    if not all(_is_canonical_ref(item) for item in value):
        raise ValueError("evidence_package_ref_invalid")
    if len(value) != len(set(value)):
        raise ValueError("evidence_package_ref_duplicate")
    return value


class TargetEvidenceStructuredRecordIds(BaseModel):
    """Exact structured record identifiers -- never "any offer/doctor of this class present"."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    offer_ids: tuple[str, ...] = ()
    fact_ids: tuple[str, ...] = ()
    doctor_ids: tuple[str, ...] = ()
    policy_sections: tuple[str, ...] = ()

    @field_validator("offer_ids", "fact_ids", "doctor_ids", "policy_sections")
    @classmethod
    def _ids_canonical(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validated_ref_tuple(value)


class TargetEvidenceProvenance(BaseModel):
    """One provenance entry: which source produced ``ref`` and why.

    ``ref`` uses a namespace-tag prefix (``offer:``/``fact:``/``doctor:``/``policy:``) for
    structured records -- the same disambiguation scheme the package fingerprint uses -- so a
    provenance list can never confuse an offer id and a doctor id that happen to share the same
    literal string. MD/evidence-block/paragraph/session/retrieval refs are recorded in their own
    natural (already-namespaced-by-shape) form.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ref: str
    source: EvidencePackageProvenanceSource
    reason: str

    @field_validator("ref")
    @classmethod
    def _ref_canonical(cls, value: str) -> str:
        if not _is_canonical_ref(value):
            raise ValueError("evidence_package_provenance_ref_invalid")
        return value

    @field_validator("reason")
    @classmethod
    def _reason_canonical(cls, value: str) -> str:
        if not _CANONICAL_TOKEN_RE.match(value):
            raise ValueError("evidence_package_provenance_reason_invalid")
        return value


class TargetEvidencePackage(BaseModel):
    """Strict immutable local Evidence Package (PERF-7B, no product/runtime authority).

    Every ``*_refs``/``*_ids`` field holds only reference-shaped strings (MD filenames, evidence
    block refs, structured record IDs, paragraph IDs) -- there is no field on this contract capable
    of holding a raw question, a raw answer, an MD/evidence body, a session id, or a contact value.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    selected_md_refs: tuple[str, ...] = ()
    selected_paragraph_refs: tuple[str, ...] = ()
    exact_evidence_block_refs: tuple[str, ...] = ()
    structured_record_ids: TargetEvidenceStructuredRecordIds
    session_derived_refs: tuple[str, ...] = ()
    retrieval_derived_refs: tuple[str, ...] = ()
    provenance: tuple[TargetEvidenceProvenance, ...] = ()
    completeness_status: EvidencePackageCompletenessStatus
    fallback_reason: str | None = None
    serialized_context_chars: int
    estimated_tokens: int
    package_fingerprint: str

    @field_validator(
        "selected_md_refs",
        "selected_paragraph_refs",
        "exact_evidence_block_refs",
        "session_derived_refs",
        "retrieval_derived_refs",
    )
    @classmethod
    def _refs_canonical(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validated_ref_tuple(value)

    @field_validator("fallback_reason")
    @classmethod
    def _fallback_reason_canonical(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _CANONICAL_TOKEN_RE.match(value):
            raise ValueError("evidence_package_fallback_reason_invalid")
        return value

    @field_validator("serialized_context_chars", "estimated_tokens")
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("evidence_package_size_negative")
        return value

    @field_validator("package_fingerprint")
    @classmethod
    def _fingerprint_shape(cls, value: str) -> str:
        if not _FINGERPRINT_RE.match(value):
            raise ValueError("evidence_package_fingerprint_invalid")
        return value

    @model_validator(mode="after")
    def _consistent_package(self) -> "TargetEvidencePackage":
        if self.estimated_tokens != self.serialized_context_chars // 4:
            raise ValueError("evidence_package_token_estimate_inconsistent")
        if self.completeness_status == "complete" and self.fallback_reason is not None:
            raise ValueError("evidence_package_complete_forbids_fallback_reason")
        if self.completeness_status != "complete" and self.fallback_reason is None:
            raise ValueError("evidence_package_incomplete_requires_fallback_reason")
        if self.session_derived_refs and self.completeness_status == "fullcontext_fallback":
            raise ValueError("evidence_package_fallback_forbids_session_refs")
        if self.retrieval_derived_refs and self.completeness_status == "fullcontext_fallback":
            raise ValueError("evidence_package_fallback_forbids_retrieval_refs")
        return self


__all__ = [
    "EvidencePackageCompletenessStatus",
    "EvidencePackageProvenanceSource",
    "TargetEvidenceStructuredRecordIds",
    "TargetEvidenceProvenance",
    "TargetEvidencePackage",
]
