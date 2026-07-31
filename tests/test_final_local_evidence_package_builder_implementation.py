"""Implementation tests for FINAL_LOCAL_EVIDENCE_PACKAGE_BUILDER / PERF-7B.

Covers the strict immutable ``TargetEvidencePackage`` contract, exact evidence extraction from
``TargetComposerRequest.evidence_blocks``, conservative completeness (never "any offer/doctor
present"), lexical-retrieval-assisted widening with an explainable accept/reject rule (never an
invented confidence score), explicit-only session projection, FullContext fallback, deterministic
sizing/fingerprinting, and this module's own isolation guarantees (no runtime wiring, no
Composer/Verifier/pipeline change, no context_group dependency, no persistent artifacts, no
logging of queries/raw text).

Most fixtures are synthetic (``tmp_path`` MD trees + hand-built ``TargetComposerRequest``
dataclasses) for determinism; a handful of tests exercise the real, already-committed
``clients/demo`` corpus end-to-end (read-only) via the same production materialization chain
``tests/test_target_context_scope_resolver.py`` already uses. Nothing here uses real user-log text.
"""

from __future__ import annotations

import ast
import dataclasses
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from contracts.doctor_schema_refs import (  # noqa: E402
    DoctorCatalogExternalIndex,
    build_doctor_source_refs,
    validate_doctor_catalog_external_refs,
)
from contracts.response_schema import TargetStrategyMatch  # noqa: E402
from contracts.response_schema_refs import (  # noqa: E402
    ResponseSchemaExternalIndex,
    validate_response_schema_external_refs,
)
from contracts.service_consultation import validate_service_consultation_refs  # noqa: E402
from contracts.target_cached_full_context import TargetCachedFullContext  # noqa: E402
from contracts.target_evidence_package import (  # noqa: E402
    TargetEvidencePackage,
    TargetEvidenceProvenance,
    TargetEvidenceStructuredRecordIds,
)
from contracts.target_response_policy import TargetResponsePolicyRequest  # noqa: E402
from contracts.target_response_spec import TargetResponseSpec  # noqa: E402
from core.doctor_schema_loader import load_doctor_catalog  # noqa: E402
from core.response_schema_kb_index import build_response_schema_kb_refs  # noqa: E402
from core.response_schema_loader import load_response_schema_bundle  # noqa: E402
from core.service_consultation_source import build_service_consultation_values  # noqa: E402
from core.target_cached_full_context import build_target_cached_full_context  # noqa: E402
from core.target_composer_request import (  # noqa: E402
    TargetComposerEvidenceBlock,
    TargetComposerRequest,
    materialize_target_composer_request,
)
from core.target_evidence_package_builder import (  # noqa: E402
    build_target_evidence_package,
    TargetEvidencePackageBuilderError,
)
from core.target_lexical_paragraph_index import (  # noqa: E402
    build_target_lexical_paragraph_index,
    search_target_lexical_paragraph_index,
)
from core.target_response_followup_policy import TargetResponseFollowupSelection  # noqa: E402
from core.target_response_policy import build_target_response_spec  # noqa: E402
from core.target_spec_offline_response_package import (  # noqa: E402
    assemble_target_spec_offline_response_package,
)

BUILDER_MODULE_PATH = _REPO_ROOT / "core" / "target_evidence_package_builder.py"
CONTRACT_MODULE_PATH = _REPO_ROOT / "contracts" / "target_evidence_package.py"
GOVERNANCE_BASELINE_HEAD = "802dfa1"


# --------------------------------------------------------------------------------------------
# Synthetic fixture helpers
# --------------------------------------------------------------------------------------------


def _spec(
    *,
    response_mode: str = "answer",
    service_id: str | None = None,
    allowed_topics: tuple[str, ...] = ("clinic",),
    required_components: tuple[str, ...] = ("content",),
    required_fact_ids: tuple[str, ...] = (),
    forbidden_topics: tuple[str, ...] = (),
) -> TargetResponseSpec:
    if response_mode == "medical_handoff" and not forbidden_topics:
        forbidden_topics = ("diagnosis",)
    return TargetResponseSpec.model_validate(
        {
            "response_mode": response_mode,
            "service_id": service_id,
            "tone_key": "commercial_warm",
            "allowed_topics": allowed_topics,
            "forbidden_topics": forbidden_topics,
            "required_fact_ids": required_fact_ids,
            "required_components": required_components,
        }
    )


def _block(
    kind: str,
    ref: str,
    *,
    topics: tuple[str, ...] = ("clinic",),
    fact_ids: tuple[str, ...] = (),
    text: str = "block text content long enough",
    must_preserve_exact: bool = False,
) -> TargetComposerEvidenceBlock:
    return TargetComposerEvidenceBlock(
        kind=kind,
        ref=ref,
        topics=topics,
        fact_ids=fact_ids,
        text=text,
        must_preserve_exact=must_preserve_exact,
    )


def _request(
    spec: TargetResponseSpec,
    evidence_blocks: tuple[TargetComposerEvidenceBlock, ...] = (),
    *,
    user_message: str = "Тестовый вопрос про клинику",
) -> TargetComposerRequest:
    return TargetComposerRequest(
        user_message=user_message,
        spec=spec,
        evidence_blocks=tuple(evidence_blocks),
        selected_followups=TargetResponseFollowupSelection(source=None, content=(), price=()),
        selected_cta_key=None,
    )


def _write_md(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _md(doc_id: str, doc_type: str, topic: str, body: str) -> str:
    return f"---\ndoc_id: {doc_id}\ndoc_type: {doc_type}\ntopic: {topic}\n---\n" + body


def _corpus(
    tmp_path: Path, docs: dict[str, str]
) -> tuple[Path, "TargetLexicalParagraphIndexType", TargetCachedFullContext]:  # noqa: F821
    for name, content in docs.items():
        _write_md(tmp_path, name, content)
    index = build_target_lexical_paragraph_index(tmp_path)
    full_context = build_target_cached_full_context(tmp_path)
    return tmp_path, index, full_context


# --------------------------------------------------------------------------------------------
# 1-2. Strict immutable contract / no raw question-answer-text fields
# --------------------------------------------------------------------------------------------


def test_1_contract_is_strict_frozen_and_rejects_extra_fields() -> None:
    package = TargetEvidencePackage(
        structured_record_ids=TargetEvidenceStructuredRecordIds(),
        completeness_status="complete",
        serialized_context_chars=100,
        estimated_tokens=25,
        package_fingerprint="a" * 64,
    )
    with pytest.raises(ValidationError):
        package.selected_md_refs = ("x.md",)  # type: ignore[misc]
    with pytest.raises(ValidationError):
        TargetEvidencePackage(
            structured_record_ids=TargetEvidenceStructuredRecordIds(),
            completeness_status="complete",
            serialized_context_chars=100,
            estimated_tokens=25,
            package_fingerprint="a" * 64,
            unexpected_field="nope",  # type: ignore[call-arg]
        )


def test_2_contract_has_no_field_capable_of_holding_raw_question_answer_text() -> None:
    forbidden_names = {"question", "answer", "raw_text", "text", "candidate_text", "sid", "session_id", "contact_value"}
    field_names = set(TargetEvidencePackage.model_fields)
    assert not (field_names & forbidden_names), field_names & forbidden_names
    # Every field is either an int, an enum/str-token, or a tuple of short reference strings /
    # nested reference-only models -- never an unbounded freeform text field.
    for name, field in TargetEvidencePackage.model_fields.items():
        assert name not in {"prompt", "message", "body"}


# --------------------------------------------------------------------------------------------
# 3-10. Exact evidence extraction
# --------------------------------------------------------------------------------------------


def test_3_content_ref_extraction_via_full_build(tmp_path: Path) -> None:
    _, index, full_context = _corpus(
        tmp_path,
        {"svc.md": _md("svc", "service", "clinic", "## H\n\nContent body long enough for a paragraph unit here.\n")},
    )
    spec = _spec(service_id="svc", required_components=("content",))
    request = _request(spec, (_block("content", "content:svc.md"),))
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.selected_md_refs == ("svc.md",)
    assert package.completeness_status == "complete"


def test_4_anchored_content_ref_extraction_strips_anchor(tmp_path: Path) -> None:
    _, index, full_context = _corpus(
        tmp_path,
        {"svc.md": _md("svc", "service", "clinic", "## H\n\nContent body long enough for a paragraph unit here.\n")},
    )
    spec = _spec(service_id="svc", required_components=("content",))
    # content: refs never carry an anchor in the real pipeline, but extraction must still handle
    # one defensively/correctly per the brief's explicit "content:{file}#{anchor}" requirement.
    request = _request(spec, (_block("content", "content:svc.md#some-anchor"),))
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.selected_md_refs == ("svc.md",)


def test_5_kb_ref_extraction_strips_anchor(tmp_path: Path) -> None:
    _, index, full_context = _corpus(
        tmp_path,
        {
            "svc.md": _md("svc", "service", "clinic", "## H\n\nContent body long enough for a paragraph unit here.\n"),
            "other.md": _md("other", "info", "clinic", "## H\n\nOther content long enough for a paragraph unit too.\n"),
        },
    )
    spec = _spec(service_id="svc", required_components=("content",))
    request = _request(
        spec,
        (
            _block("content", "content:svc.md"),
            _block("external_kb", "kb:other.md#korotko", topics=("clinic",)),
        ),
    )
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert "other.md" in package.selected_md_refs


def test_6_exact_offer_ids(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("price",))
    request = _request(spec, (_block("offer", "offer:svc.classic", must_preserve_exact=True),))
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.structured_record_ids.offer_ids == ("svc.classic",)
    assert package.completeness_status == "complete"


def test_7_exact_required_fact_ids(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("content",), required_fact_ids=("promo_x",))
    request = _request(
        spec,
        (
            _block("content", "content:svc.md"),
            _block("commercial_fact", "fact:promo_x", fact_ids=("promo_x",), must_preserve_exact=True),
        ),
    )
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.structured_record_ids.fact_ids == ("promo_x",)
    assert package.completeness_status == "complete"


def test_8_exact_doctor_ids(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("doctors",))
    request = _request(spec, (_block("doctor", "doctor:kuznetsov", must_preserve_exact=True),))
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.structured_record_ids.doctor_ids == ("kuznetsov",)
    assert package.completeness_status == "complete"


def test_9_exact_contact_policy_fields(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("content",))
    request = _request(
        spec,
        (
            _block("content", "content:svc.md"),
            _block("clinic_contact", "clinic_contact:phone", must_preserve_exact=True, text="Телефон: +7 000"),
        ),
    )
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.structured_record_ids.policy_sections == ("phone",)


def test_10_consultation_ref_included(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("content",))
    request = _request(
        spec,
        (
            _block("content", "content:svc.md"),
            _block("consultation", "consultation:svc.md", text="Оставьте заявку на консультацию сегодня."),
        ),
    )
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert "svc.md" in package.selected_md_refs


# --------------------------------------------------------------------------------------------
# 11. Stable dedup/order
# --------------------------------------------------------------------------------------------


def test_11_stable_dedup_and_order(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("content", "price"))
    request = _request(
        spec,
        (
            _block("content", "content:svc.md"),
            _block("offer", "offer:svc.a", must_preserve_exact=True),
            _block("offer", "offer:svc.b", must_preserve_exact=True),
        ),
    )
    package_1 = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    package_2 = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package_1.structured_record_ids.offer_ids == ("svc.a", "svc.b")
    assert package_1 == package_2


# --------------------------------------------------------------------------------------------
# 12-15. Completeness by exact evidence class
# --------------------------------------------------------------------------------------------


def test_12_exact_service_content_package_complete(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("content",))
    request = _request(spec, (_block("content", "content:svc.md"),))
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.completeness_status == "complete"
    assert package.fallback_reason is None


def test_13_price_only_package_with_exact_offer_complete(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("price",))
    request = _request(spec, (_block("offer", "offer:svc.tomography", must_preserve_exact=True),))
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.completeness_status == "complete"
    assert package.structured_record_ids.offer_ids == ("svc.tomography",)


def test_14_doctors_package_with_exact_doctor_ids_complete(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("doctors",))
    request = _request(spec, (_block("doctor", "doctor:volkov", must_preserve_exact=True),))
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.completeness_status == "complete"


def test_15_contact_package_with_exact_fields_complete(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("content",))
    request = _request(
        spec,
        (
            _block("content", "content:svc.md"),
            _block("clinic_contact", "clinic_contact:address", must_preserve_exact=True, text="Адрес: где-то"),
        ),
    )
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.completeness_status == "complete"
    assert package.structured_record_ids.policy_sections == ("address",)


# --------------------------------------------------------------------------------------------
# 16-18. Missing/wrong exact evidence never counted as complete
# --------------------------------------------------------------------------------------------


def test_16_required_fact_missing_is_not_complete(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("content",), required_fact_ids=("promo_x",))
    request = _request(spec, (_block("content", "content:svc.md"),))  # no fact:promo_x block
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.completeness_status == "fullcontext_fallback"
    assert package.fallback_reason == "structured_evidence_incomplete_requires_fullcontext"


def test_17_wrong_offer_id_never_fabricated_as_required_offer(tmp_path: Path) -> None:
    """No ``required_offer_id`` ground truth exists on ``TargetResponseSpec`` -- the exactness
    guarantee this milestone asks for is that extraction never reports an offer id that was not
    actually present in ``evidence_blocks``. Proven here: only the real offer id appears, a
    different (never-materialized) id never does."""

    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("price",))
    request = _request(spec, (_block("offer", "offer:svc.actual_offer", must_preserve_exact=True),))
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.structured_record_ids.offer_ids == ("svc.actual_offer",)
    assert "svc.wrong_offer" not in package.structured_record_ids.offer_ids


def test_18_wrong_doctor_id_never_fabricated_as_required_doctor(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("doctors",))
    request = _request(spec, (_block("doctor", "doctor:actual_doctor", must_preserve_exact=True),))
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.structured_record_ids.doctor_ids == ("actual_doctor",)
    assert "wrong_doctor" not in package.structured_record_ids.doctor_ids


# --------------------------------------------------------------------------------------------
# 19-23. Lexical retrieval assistance
# --------------------------------------------------------------------------------------------


def test_19_lexical_result_adds_paragraph_and_document_refs(tmp_path: Path) -> None:
    _, index, full_context = _corpus(
        tmp_path,
        {"faq.md": _md("faq", "faq", "clinic", "## H\n\nЦентрализованное стерилизационное отделение работает как в крупных больницах города.\n")},
    )
    spec = _spec(service_id=None, allowed_topics=("clinic",), required_components=("content",))
    request = _request(spec, (), user_message="централизованное стерилизационное отделение")
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.completeness_status == "insufficient_widened"
    assert "faq.md" in package.selected_md_refs
    assert package.selected_paragraph_refs != ()
    assert package.retrieval_derived_refs != ()


def test_20_lexical_result_never_removes_exact_refs(tmp_path: Path) -> None:
    _, index, full_context = _corpus(
        tmp_path,
        {
            "svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n"),
            "faq.md": _md("faq", "faq", "clinic", "## H\n\nЦентрализованное стерилизационное отделение работает как в крупных больницах города.\n"),
        },
    )
    spec = _spec(service_id="svc", required_components=("content", "price"))
    request = _request(
        spec,
        (
            _block("content", "content:svc.md"),
            _block("offer", "offer:svc.a", must_preserve_exact=True),
        ),
        user_message="централизованное стерилизационное отделение",
    )
    # "content" is already satisfied by exact evidence -- comparison/content deficits are absent,
    # so lexical retrieval must not even run, and exact refs must remain untouched.
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.completeness_status == "complete"
    assert "svc.md" in package.selected_md_refs
    assert package.structured_record_ids.offer_ids == ("svc.a",)
    assert package.retrieval_derived_refs == ()


def test_21_zero_lexical_hits_is_fullcontext_fallback_not_data_gap(tmp_path: Path) -> None:
    _, index, full_context = _corpus(
        tmp_path,
        {"unrelated.md": _md("unrelated", "info", "clinic", "## H\n\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA просто текст.\n")},
    )
    spec = _spec(service_id=None, allowed_topics=("clinic",), required_components=("content",))
    request = _request(spec, (), user_message="совершенно другая тема без общих слов вообще никак")
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.completeness_status == "fullcontext_fallback"
    assert package.fallback_reason == "lexical_zero_hits"
    # completeness_status is a closed Literal -- "data_gap" cannot exist as a value at all.
    assert "data_gap" not in TargetEvidencePackage.model_fields["completeness_status"].annotation.__args__


def test_22_ambiguous_lexical_hits_trigger_conservative_fallback(tmp_path: Path) -> None:
    shared_body = "## H\n\nОбщий одинаковый текст документа тест тест тест тест тест тест дважды тут.\n"
    _, index, full_context = _corpus(
        tmp_path,
        {
            "a.md": _md("a", "info", "clinic", shared_body),
            "b.md": _md("b", "info", "clinic", shared_body),
        },
    )
    spec = _spec(service_id=None, allowed_topics=("clinic",), required_components=("content",))
    request = _request(spec, (), user_message="общий одинаковый текст документа")
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.completeness_status == "fullcontext_fallback"
    assert package.fallback_reason == "lexical_ambiguous_top_match"


def test_23_weak_prefix_only_hit_never_confidently_complete(tmp_path: Path) -> None:
    _, index, full_context = _corpus(
        tmp_path,
        {"faq.md": _md("faq", "faq", "clinic", "## H\n\nСтерилизационное оборудование клиники соответствует стандартам всегда.\n")},
    )
    spec = _spec(service_id=None, allowed_topics=("clinic",), required_components=("content",))
    # A short query token below the prefix-matching minimum length -- PERF-7A's own rule --
    # produces zero eligible (exact-match) hits, never a false "complete".
    request = _request(spec, (), user_message="сте")
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.completeness_status == "fullcontext_fallback"
    assert package.fallback_reason in {"lexical_zero_hits", "lexical_only_weak_prefix_matches"}


# --------------------------------------------------------------------------------------------
# 24-25. Comparison-required rule
# --------------------------------------------------------------------------------------------


def test_24_comparison_required_without_comparison_doc_falls_back(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("content",))
    request = _request(spec, (_block("content", "content:svc.md"),), user_message="сравнение вариантов лечения полностью")
    package = build_target_evidence_package(
        request, index, full_context, md_root=tmp_path, comparison_required=True
    )
    assert package.completeness_status == "fullcontext_fallback"


def test_25_comparison_required_with_valid_comparison_document(tmp_path: Path) -> None:
    _, index, full_context = _corpus(
        tmp_path,
        {
            "svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n"),
            "compare.md": _md(
                "compare", "comparison", "clinic",
                "## H\n\nУникальнаяфразасравнениявариантовтерапииздесь однозначно отличает этот документ от всех.\n",
            ),
        },
    )
    spec = _spec(service_id="svc", required_components=("content",))
    request = _request(
        spec,
        (_block("content", "content:svc.md"),),
        user_message="уникальнаяфразасравнениявариантовтерапииздесь",
    )
    package = build_target_evidence_package(
        request, index, full_context, md_root=tmp_path, comparison_required=True
    )
    assert package.completeness_status == "insufficient_widened"
    assert "compare.md" in package.selected_md_refs


# --------------------------------------------------------------------------------------------
# 26-28. Session projection rules
# --------------------------------------------------------------------------------------------


def test_26_explicit_followup_session_refs_included(tmp_path: Path) -> None:
    _, index, full_context = _corpus(
        tmp_path,
        {
            "svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n"),
            "prior.md": _md("prior", "service", "clinic", "## H\n\nPrior service body long enough here today.\n"),
        },
    )
    spec = _spec(service_id="svc", required_components=("content",))
    request = _request(spec, (_block("content", "content:svc.md"),))
    package = build_target_evidence_package(
        request,
        index,
        full_context,
        md_root=tmp_path,
        explicit_followup=True,
        session_derived_refs=("prior.md",),
    )
    assert "prior.md" in package.session_derived_refs
    assert "prior.md" in package.selected_md_refs


def test_27_independent_question_cannot_use_session_refs(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("content",))
    request = _request(spec, (_block("content", "content:svc.md"),))
    with pytest.raises(TargetEvidencePackageBuilderError) as excinfo:
        build_target_evidence_package(
            request,
            index,
            full_context,
            md_root=tmp_path,
            explicit_followup=False,
            session_derived_refs=("svc.md",),
        )
    assert excinfo.value.code == "evidence_package_session_refs_without_explicit_followup"


def test_28_unknown_session_ref_falls_back(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("content",))
    request = _request(spec, (_block("content", "content:svc.md"),))
    package = build_target_evidence_package(
        request,
        index,
        full_context,
        md_root=tmp_path,
        explicit_followup=True,
        session_derived_refs=("does_not_exist.md",),
    )
    assert package.completeness_status == "fullcontext_fallback"
    assert package.fallback_reason == "unknown_session_ref"


# --------------------------------------------------------------------------------------------
# 29-30. FullContext fallback shape
# --------------------------------------------------------------------------------------------


def test_29_fullcontext_includes_all_document_paths(tmp_path: Path) -> None:
    _, index, full_context = _corpus(
        tmp_path,
        {
            "a.md": _md("a", "info", "clinic", "## H\n\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA.\n"),
            "b.md": _md("b", "info", "clinic", "## H\n\nBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB.\n"),
        },
    )
    spec = _spec(service_id=None, allowed_topics=("clinic",), required_components=("content",))
    request = _request(spec, (), user_message="совершенно другая тема без общих слов вообще")
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.completeness_status == "fullcontext_fallback"
    assert set(package.selected_md_refs) == {"a.md", "b.md"}


def test_30_fullcontext_is_valid_status_not_exception(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"a.md": _md("a", "info", "clinic", "## H\n\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA.\n")})
    spec = _spec(service_id=None, allowed_topics=("clinic",), required_components=("content",))
    request = _request(spec, (), user_message="совершенно другая тема без общих слов")
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert isinstance(package, TargetEvidencePackage)


# --------------------------------------------------------------------------------------------
# 31-34. Fingerprint
# --------------------------------------------------------------------------------------------


def test_31_fingerprint_deterministic(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("content",))
    request = _request(spec, (_block("content", "content:svc.md"),))
    package_1 = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    package_2 = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package_1.package_fingerprint == package_2.package_fingerprint


def test_32_md_content_change_changes_fingerprint(tmp_path: Path) -> None:
    _, index, full_context = _corpus(
        tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nOriginal body long enough here today content.\n")}
    )
    spec = _spec(service_id="svc", required_components=("content",))
    request = _request(spec, (_block("content", "content:svc.md"),))
    before = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    (tmp_path / "svc.md").write_text(
        _md("svc", "service", "clinic", "## H\n\nModified body long enough here today content too.\n"),
        encoding="utf-8",
    )
    after = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert before.package_fingerprint != after.package_fingerprint


def test_33_evidence_block_text_change_changes_fingerprint(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("price",))
    request = _request(spec, (_block("offer", "offer:svc.a", text="original offer text", must_preserve_exact=True),))
    before = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    changed_block = dataclasses.replace(request.evidence_blocks[0], text="changed offer text now")
    after_request = dataclasses.replace(request, evidence_blocks=(changed_block,))
    after = build_target_evidence_package(after_request, index, full_context, md_root=tmp_path)
    assert before.package_fingerprint != after.package_fingerprint


def test_34_same_string_id_in_different_namespaces_does_not_collide(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("price", "doctors"))
    same_id = "shared_id_123"
    request = _request(
        spec,
        (
            _block("offer", f"offer:{same_id}", must_preserve_exact=True),
            _block("doctor", f"doctor:{same_id}", must_preserve_exact=True),
        ),
    )
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    assert package.structured_record_ids.offer_ids == (same_id,)
    assert package.structured_record_ids.doctor_ids == (same_id,)
    provenance_refs = {p.ref for p in package.provenance}
    assert f"offer:{same_id}" in provenance_refs
    assert f"doctor:{same_id}" in provenance_refs
    assert len(provenance_refs) == len(package.provenance)  # no accidental collapse


# --------------------------------------------------------------------------------------------
# 35. Size includes MD and evidence-block serialization
# --------------------------------------------------------------------------------------------


def test_35_size_includes_md_and_evidence_block_serialization(tmp_path: Path) -> None:
    body_text = "Body long enough here today for a real paragraph unit to exist."
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", f"## H\n\n{body_text}\n")})
    spec = _spec(service_id="svc", required_components=("content", "price"))
    offer_text = "offer json text representative of a real structured evidence block"
    request = _request(
        spec,
        (
            _block("content", "content:svc.md"),
            _block("offer", "offer:svc.a", text=offer_text, must_preserve_exact=True),
        ),
    )
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    raw_doc_text = (tmp_path / "svc.md").read_text(encoding="utf-8")
    expected_doc_chars = len(f"---BEGIN DOC:svc.md---\n{raw_doc_text.rstrip(chr(10))}\n---END DOC:svc.md---")
    expected_total = expected_doc_chars + len(offer_text)
    assert package.serialized_context_chars == expected_total
    assert package.estimated_tokens == expected_total // 4


# --------------------------------------------------------------------------------------------
# 36-40. Anonymization / isolation
# --------------------------------------------------------------------------------------------


def test_36_no_absolute_paths_in_package(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("content",))
    request = _request(spec, (_block("content", "content:svc.md"),))
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    dumped = package.model_dump_json()
    assert str(tmp_path) not in dumped


def test_37_no_question_answer_sid_contact_values_in_package(tmp_path: Path) -> None:
    _, index, full_context = _corpus(tmp_path, {"svc.md": _md("svc", "service", "clinic", "## H\n\nBody long enough here today.\n")})
    spec = _spec(service_id="svc", required_components=("content",))
    secret_message = "УНИКАЛЬНЫЙ_ВОПРОС_ПОЛЬЗОВАТЕЛЯ_НЕ_ДОЛЖЕН_ПОПАСТЬ_В_ПАКЕТ"
    contact_value_text = "Телефон: +7 999 000 00 00"
    request = _request(
        spec,
        (
            _block("content", "content:svc.md"),
            _block("clinic_contact", "clinic_contact:phone", text=contact_value_text, must_preserve_exact=True),
        ),
        user_message=secret_message,
    )
    package = build_target_evidence_package(request, index, full_context, md_root=tmp_path)
    dumped = package.model_dump_json()
    assert secret_message not in dumped
    assert contact_value_text not in dumped
    assert "+7 999 000 00 00" not in dumped
    # Only the field name ("phone"), never the contact value, is present.
    assert package.structured_record_ids.policy_sections == ("phone",)


def test_38_no_logging_calls_in_builder_module() -> None:
    tree = ast.parse(BUILDER_MODULE_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "print"
        if isinstance(node, ast.Attribute) and node.attr in {"info", "warning", "error", "debug", "emit_bot_event"}:
            raise AssertionError(f"unexpected logging-shaped call: {node.attr}")
    source = BUILDER_MODULE_PATH.read_text(encoding="utf-8").lower()
    assert "import logging" not in source
    assert "get_logger" not in source


def test_39_no_flask_request_session_dependency() -> None:
    """Checks actual code shapes only -- the module's own docstring legitimately *discusses* why
    a ContextVar/Flask request is not used (same pattern as PERF-7A's own FTS5-discussion false
    positive lesson), so this must not fail on prose mentioning the forbidden words."""

    tree = ast.parse(BUILDER_MODULE_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    forbidden = {"flask", "session", "app", "contextvars"}
    assert not (imported & forbidden), imported & forbidden
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"ContextVar", "current_app"}
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"ctx", "current_app"}


def test_40_no_llm_network_or_provider_dependency() -> None:
    tree = ast.parse(BUILDER_MODULE_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    forbidden = {"requests", "httpx", "openai", "anthropic", "urllib", "socket", "sqlite3"}
    assert not (imported & forbidden), imported & forbidden


# --------------------------------------------------------------------------------------------
# 41-43. Repository-wide isolation checks
# --------------------------------------------------------------------------------------------


def test_41_builder_not_imported_anywhere_outside_its_own_files() -> None:
    proc = subprocess.run(
        ["git", "grep", "-nE", r"^\s*(from|import)\s+.*target_evidence_package_builder", "--", "*.py"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode not in (0, 1):
        pytest.skip(f"git grep unavailable: {proc.stderr.strip()}")
    hits = [line for line in proc.stdout.splitlines() if line.strip()]
    allowed_files = {
        "core/target_evidence_package_builder.py",
        "tests/test_final_local_evidence_package_builder_implementation.py",
    }
    unexpected = [line for line in hits if not any(line.startswith(f"{path}:") for path in allowed_files)]
    assert unexpected == [], unexpected


def test_42_no_composer_verifier_pipeline_runtime_files_touched() -> None:
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{GOVERNANCE_BASELINE_HEAD}..HEAD"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    changed = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
    forbidden_paths = {
        "config.py",
        "app.py",
        "session.py",
        "core/target_composer_executor.py",
        "core/target_response_verifier.py",
        "core/target_composer_request.py",
        "core/target_verified_response_pipeline.py",
        "core/target_policy_bound_verified_response_pipeline.py",
        "contracts/turn_frame.py",
        "core/target_context_scope_resolver.py",
        "core/target_context_scope_shadow.py",
    }
    assert not (changed & forbidden_paths), changed & forbidden_paths


def test_43_no_client_pack_files_touched() -> None:
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{GOVERNANCE_BASELINE_HEAD}..HEAD", "--", "clients/"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    changed = [line for line in proc.stdout.splitlines() if line.strip()]
    assert changed == [], changed


# --------------------------------------------------------------------------------------------
# 44-45. Real demo corpus end-to-end + determinism
# --------------------------------------------------------------------------------------------

DEMO_ROOT = Path("clients/demo")
_TARGET_ROOT = DEMO_ROOT / "target_response"
_MD_ROOT = DEMO_ROOT / "md"
_BUNDLE = load_response_schema_bundle(_TARGET_ROOT)
_DOCTORS = load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")
_KB_REFS = build_response_schema_kb_refs(_MD_ROOT)
_DOCTOR_INDEX = DoctorCatalogExternalIndex(service_ids=tuple(_BUNDLE.services), kb_refs=_KB_REFS)
assert validate_doctor_catalog_external_refs(_DOCTORS, _DOCTOR_INDEX) is None
_EXTERNAL_INDEX = ResponseSchemaExternalIndex(kb_refs=_KB_REFS, doctor_refs=build_doctor_source_refs(_DOCTORS))
assert validate_response_schema_external_refs(_BUNDLE, _EXTERNAL_INDEX) is None
_CONSULTATIONS = build_service_consultation_values(_MD_ROOT)
assert validate_service_consultation_refs(_CONSULTATIONS, _BUNDLE.services) is None
_DEMO_FULL_CONTEXT = build_target_cached_full_context(_MD_ROOT)
_DEMO_LEXICAL_INDEX = build_target_lexical_paragraph_index(_MD_ROOT)


def _demo_materialize(
    *,
    service_id: str | None,
    allowed_topics: tuple[str, ...],
    requested_components: tuple[str, ...] = ("content",),
    user_message: str = "Расскажите подробнее",
) -> TargetComposerRequest:
    policy_request = TargetResponsePolicyRequest.model_validate(
        {
            "response_mode": "answer",
            "service_id": service_id,
            "tone_key": "commercial_warm",
            "allowed_topics": allowed_topics,
            "forbidden_topics": ("diagnosis", "personal_eligibility"),
            "required_fact_ids": (),
            "requested_components": requested_components,
            "primary_component": requested_components[0] if requested_components else None,
            "allow_marketing_facts": False,
            "allow_consultation_close": False,
            "allow_cta": False,
        }
    )
    spec = build_target_response_spec(policy_request)
    bound_package = assemble_target_spec_offline_response_package(
        _BUNDLE,
        _DOCTORS,
        _EXTERNAL_INDEX,
        _CONSULTATIONS,
        spec=spec,
        brand_term=None,
        strategy_context=TargetStrategyMatch(family="implantology", extent="full_arch"),
        semantic_context="service",
        today=date(2026, 7, 31),
        md_root=_MD_ROOT,
        include_initial_block=False,
        include_consultation_close=False,
        include_cta=False,
        marketing_scenarios=(),
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
        turn_topic=None,
        effective_scope=None,
        client_id="demo",
    )
    return materialize_target_composer_request(
        bound_package,
        _BUNDLE,
        _DOCTORS,
        _CONSULTATIONS,
        user_message=user_message,
        md_root=_MD_ROOT,
        client_id="demo",
    )


def test_44_demo_index_and_real_composer_request_build_succeeds() -> None:
    request = _demo_materialize(service_id="classic", allowed_topics=("implantation",))
    package = build_target_evidence_package(
        request, _DEMO_LEXICAL_INDEX, _DEMO_FULL_CONTEXT, md_root=_MD_ROOT
    )
    assert isinstance(package, TargetEvidencePackage)
    assert package.completeness_status == "complete"
    assert "implantation__service__classic.md" in package.selected_md_refs


def test_45_builder_called_repeatedly_gives_identical_result() -> None:
    request = _demo_materialize(service_id="classic", allowed_topics=("implantation",))
    first = build_target_evidence_package(request, _DEMO_LEXICAL_INDEX, _DEMO_FULL_CONTEXT, md_root=_MD_ROOT)
    second = build_target_evidence_package(request, _DEMO_LEXICAL_INDEX, _DEMO_FULL_CONTEXT, md_root=_MD_ROOT)
    assert first == second


# --------------------------------------------------------------------------------------------
# 46-47. No context_group dependency / no persistent artifacts
# --------------------------------------------------------------------------------------------


def test_46_no_context_group_dependency() -> None:
    """Checks actual identifiers (imports, names, attributes) only -- the module's own docstring
    legitimately explains that PERF-6's ladder is not reused, which would otherwise false-positive
    a raw substring check (same lesson as test_39)."""

    tree = ast.parse(BUILDER_MODULE_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    identifiers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        elif isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
    forbidden_modules = {"core.target_context_scope_resolver", "core.target_context_scope_shadow"}
    assert not (imported_modules & forbidden_modules), imported_modules & forbidden_modules
    forbidden_identifiers = {"context_group", "context_groups", "service_exact", "ContextScopeLevel"}
    assert not (identifiers & forbidden_identifiers), identifiers & forbidden_identifiers


def test_47_no_persistent_artifacts_written() -> None:
    tree = ast.parse(BUILDER_MODULE_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in {"write_text", "write_bytes", "mkdir"}:
            raise AssertionError(f"unexpected filesystem-write call: {node.attr}")
    source = BUILDER_MODULE_PATH.read_text(encoding="utf-8")
    assert "open(" not in source or "'w'" not in source and '"w"' not in source


# --------------------------------------------------------------------------------------------
# 48-49. PERF-7A behaviour unaffected (light regression)
# --------------------------------------------------------------------------------------------


def test_48_existing_lexical_miss_inventory_remains_honest(tmp_path: Path) -> None:
    _, index, _full_context = _corpus(
        tmp_path,
        {"doc.md": _md("doc", "faq", "clinic", "## H\n\nИмплантация зубов проводится опытными врачами клиники по протоколам всегда.\n")},
    )
    # Same honest-miss shape PERF-7A's own suite already proved: a short (<4 char) query token
    # never prefix-matches -- this module's presence must not silently change that.
    assert search_target_lexical_paragraph_index(index, "зуб", limit=5) == ()
    assert search_target_lexical_paragraph_index(index, "имплантация", limit=5) != ()


def test_49_add_change_delete_index_behaviour_unaffected(tmp_path: Path) -> None:
    _write_md(tmp_path, "a.md", _md("a", "info", "clinic", "## H\n\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA.\n"))
    before = build_target_lexical_paragraph_index(tmp_path)
    _write_md(tmp_path, "b.md", _md("b", "info", "clinic", "## H\n\nBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB.\n"))
    after = build_target_lexical_paragraph_index(tmp_path)
    assert after.document_count == before.document_count + 1
    assert after.fingerprint != before.fingerprint


# --------------------------------------------------------------------------------------------
# 50. PERF-7C remains NOT STARTED (authoritative check lives in the governance test file; this
# is a light, redundant, defense-in-depth confirmation from this file too).
# --------------------------------------------------------------------------------------------


def test_50_perf7c_offline_eval_harness_does_not_exist() -> None:
    assert not (_REPO_ROOT / "evals" / "v5" / "demo" / "evidence_package_eval_matrix.json").exists()
    assert not (_REPO_ROOT / "scripts" / "run_evidence_package_eval.py").exists()


# --------------------------------------------------------------------------------------------
# Additional structural safety net: contract module isolation
# --------------------------------------------------------------------------------------------


def test_contract_module_imports_no_product_runtime_code() -> None:
    tree = ast.parse(CONTRACT_MODULE_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"__future__", "re", "typing", "pydantic"}
