"""Fail-closed target response verification boundary (S38, offline/unwired)."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal, NoReturn, Protocol, TypeAlias

from contracts.target_cached_full_context import TargetCachedFullContext
from contracts.target_response_spec import TargetResponseSpec
from core import turn_timing
from core.target_composer_executor import TargetUnverifiedComposedResponse
from contracts.target_response_stage import is_scope_aware_price_stage
from core.target_fullcontext_content_package import is_fullcontext_service_optional_spec
from core.target_presentation_source_identity import validate_used_content_refs
from core.target_composer_request import (
    TargetComposerEvidenceBlock,
    TargetComposerRequest,
)
from core.target_client_ui_nav import TargetNavigationFollowup
from core.target_response_followup_policy import TargetResponseFollowupSelection


TargetNumericKind: TypeAlias = Literal[
    "money",
    "percent",
    "day",
    "month",
    "year",
    "generic",
]

TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY = """1. Assess the candidate answer against CACHED_FULL_CONTEXT and PRIMARY_EVIDENCE.
2. Return JSON only: {"issues":[{"kind":"<kind>","offending_span":"<exact substring from candidate>"}, ...]}. An empty issues array means no semantic violations.
3. unsupported_clinic_claim — invented or distorted clinic prices, numbers, guarantees, or facts; ungrounded strict commercial claims (prices, payment stages, promotions, marketing facts, consultation values, CTA, exact doctor credentials) not supported by PRIMARY_EVIDENCE; phone numbers, messenger handles, URLs, or contact CTAs in prose when allow_cta is false or they are absent from allowed PRIMARY_EVIDENCE; content outside allowed topics or touching forbidden topics; selected commercial facts paraphrased with meaning change or missing strict verbatim facts.
4. personal_medical_conclusion — BLOCKING: diagnosis or differential for the user; personal eligibility verdict (вам можно/нельзя); treatment choice or medical recommendation for this patient. NOT AN ISSUE: neutral statements that the doctor will decide after examination or diagnostics; consultation invitations without the bot issuing its own eligibility verdict; general educational comparison of options without telling this patient what to choose.
5. material_external_medical_claim — BLOCKING ONLY for medical claims that are clearly dangerous, clearly absurd, or directly contradict CACHED_FULL_CONTEXT or PRIMARY_EVIDENCE in a way that changes risk, contraindication, treatability, or treatment recommendation. A plausible general medical fact absent from the corpus is NOT enough for this kind. NOT BLOCKING: general public-knowledge associations (for example autoimmune disease category, immune system context, pregnancy/hormone/lactation/healing context) when the answer does not diagnose the user, does not decide eligibility or treatment, and does not contradict approved materials; honest missing-base statements with consultation invite.
6. minor_external_detail — NON-BLOCKING: plausible general medical context or classification absent from corpus that does not diagnose the user, does not decide eligibility or treatment, and does not materially contradict approved materials. Prefer this over material_external_medical_claim when the answer stays neutral. Absence of grounding alone is not a block reason.
7. Conversational empathy, neutral consultation invitations without contact details, and faithful paraphrase preserving meaning are not violations.
8. Each offending_span must be a non-empty exact substring of the candidate answer. Never rewrite, repair, shorten, or replace the candidate answer."""


@dataclass(frozen=True, slots=True)
class TargetNumericClaim:
    kind: TargetNumericKind
    value: str


@dataclass(frozen=True, slots=True)
class TargetSemanticVerifierInvocation:
    system_policy: str
    cached_full_context: str
    response_spec_json: str
    primary_evidence_json: str
    candidate_text: str


TargetSemanticIssueKind: TypeAlias = Literal[
    "unsupported_clinic_claim",
    "personal_medical_conclusion",
    "material_external_medical_claim",
    "minor_external_detail",
]

_TARGET_SEMANTIC_ISSUE_KINDS = frozenset(
    {
        "unsupported_clinic_claim",
        "personal_medical_conclusion",
        "material_external_medical_claim",
        "minor_external_detail",
    }
)

TARGET_SEMANTIC_ISSUE_KINDS = _TARGET_SEMANTIC_ISSUE_KINDS

_TARGET_SEMANTIC_BLOCKING_KINDS = frozenset(
    {
        "unsupported_clinic_claim",
        "personal_medical_conclusion",
        "material_external_medical_claim",
    }
)


@dataclass(frozen=True, slots=True)
class TargetSemanticIssue:
    kind: TargetSemanticIssueKind
    offending_span: str


@dataclass(frozen=True, slots=True)
class TargetSemanticAssessment:
    issues: tuple[TargetSemanticIssue, ...] = ()


class TargetSemanticVerifierBackend(Protocol):
    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object: ...


@dataclass(frozen=True, slots=True)
class TargetVerifiedComposedResponse:
    text: str
    spec: TargetResponseSpec
    selected_followups: TargetResponseFollowupSelection
    selected_cta_key: str | None
    navigation_followups: tuple[TargetNavigationFollowup, ...] = ()
    primary_content_ref: str | None = None
    used_content_refs: tuple[str, ...] = ()
    verification_status: Literal["verified"] = "verified"


class TargetResponseVerificationError(ValueError):
    """Typed fail-closed S38 verification error."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _error(code: str, value: object, cause: BaseException | None = None) -> NoReturn:
    error = TargetResponseVerificationError(code, value)
    if cause is None:
        raise error
    raise error from cause


def _canonical(value: object) -> bool:
    return type(value) is str and bool(value) and value == value.strip()


def _canonical_tuple(value: object, *, nonempty: bool) -> bool:
    return (
        type(value) is tuple
        and (bool(value) or not nonempty)
        and all(_canonical(item) for item in value)
        and len(value) == len(set(value))
    )


_KINDS = frozenset(
    {
        "content",
        "offer",
        "doctor",
        "commercial_fact",
        "external_kb",
        "external_doctor",
        "consultation",
        "clinic_contact",
    }
)


def _validated_inputs(
    request: object,
    response: object,
) -> tuple[TargetComposerRequest, TargetUnverifiedComposedResponse]:
    if type(request) is not TargetComposerRequest:
        _error("target_verifier_input_invalid", "request")
    if type(response) is not TargetUnverifiedComposedResponse:
        _error("target_verifier_input_invalid", "response")
    if (
        not _canonical(response.text)
        or type(response.verification_status) is not str
        or response.verification_status != "unverified"
    ):
        _error("target_verifier_input_invalid", "response")
    spec = request.spec
    if (
        type(spec) is not TargetResponseSpec
        or type(spec.response_mode) is not str
        or spec.response_mode not in {"answer", "medical_handoff"}
        or not _canonical_tuple(spec.allowed_topics, nonempty=True)
        or not _canonical_tuple(spec.forbidden_topics, nonempty=False)
        or not _canonical_tuple(spec.required_fact_ids, nonempty=False)
        or bool(set(spec.allowed_topics).intersection(spec.forbidden_topics))
    ):
        _error("target_verifier_input_invalid", "spec")
    if (
        response.spec is not spec
        or response.selected_followups is not request.selected_followups
        or response.selected_cta_key is not request.selected_cta_key
    ):
        _error("target_verifier_input_invalid", "identity")
    blocks = request.evidence_blocks
    if type(blocks) is not tuple:
        _error("target_verifier_input_invalid", "evidence")
    if not blocks and not is_fullcontext_service_optional_spec(spec):
        stage = spec.response_stage
        if not (
            is_scope_aware_price_stage(stage)
            and stage in {"stage_clarify", "data_gap"}
        ):
            _error("target_verifier_input_invalid", "evidence")
    if not blocks:
        return request, response
    refs: list[str] = []
    commercial: dict[str, int] = {}
    for index, block in enumerate(blocks):
        if type(block) is not TargetComposerEvidenceBlock:
            _error("target_verifier_input_invalid", "evidence")
        if (
            type(block.kind) is not str
            or block.kind not in _KINDS
            or not _canonical(block.ref)
            or not _canonical(block.text)
            or not _canonical_tuple(block.topics, nonempty=True)
            or not _canonical_tuple(block.fact_ids, nonempty=False)
            or type(block.must_preserve_exact) is not bool
        ):
            _error("target_verifier_input_invalid", "evidence")
        refs.append(block.ref)
        if block.kind == "commercial_fact":
            if (
                len(block.fact_ids) != 1
                or block.ref != f"fact:{block.fact_ids[0]}"
                or block.fact_ids[0] in commercial
            ):
                _error("target_verifier_input_invalid", "required_facts")
            commercial[block.fact_ids[0]] = index
    if len(refs) != len(set(refs)):
        _error("target_verifier_input_invalid", "evidence")
    if any(fact_id not in commercial for fact_id in spec.required_fact_ids):
        _error("target_verifier_input_invalid", "required_facts")
    return request, response


_LEXICAL_NAME = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?=[A-Za-z0-9-]*[A-Za-z])"
    r"(?=[A-Za-z0-9-]*\d)"
    r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*"
    r"(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_NUMBER = re.compile(
    r"(?<!\d)(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[.,]\d+)?(?!\d)"
)
_RANGE = re.compile(
    rf"(?P<first>{_NUMBER.pattern})\s*[-–—]\s*(?P<second>{_NUMBER.pattern})"
)
_MONEY_PREFIX = re.compile(r"(?:₽|RUB)\s*$", re.IGNORECASE)
_MONEY_SUFFIX = re.compile(
    r"^\s*(?:₽|RUB\b|руб(?:ль|ля|лей)?\b|руб\.|р\.)",
    re.IGNORECASE,
)
_PERCENT_SUFFIX = re.compile(r"^\s*(?:%|процент(?:а|ов)?\b)", re.IGNORECASE)
_DAY_SUFFIX = re.compile(
    r"^\s*(?:(?:день|дня|дней)\b|дн\.|-\s*дневн\w*)", re.IGNORECASE
)
_MONTH_SUFFIX = re.compile(
    r"^\s*(?:(?:месяц|месяца|месяцев)\b|мес\.|-\s*месячн\w*)",
    re.IGNORECASE,
)
_YEAR_SUFFIX = re.compile(
    r"^\s*(?:(?:год|года|лет)\b|г\.|-\s*летн\w*)",
    re.IGNORECASE,
)


def _number_value(raw: str) -> str:
    normalized = unicodedata.normalize("NFKC", raw)
    normalized = re.sub(r"[ \u00a0\u202f]", "", normalized).replace(",", ".")
    try:
        value = Decimal(normalized)
    except InvalidOperation as exc:  # pragma: no cover - regex guarantees decimal syntax
        _error("target_verifier_input_invalid", "evidence", exc)
    rendered = format(value.normalize(), "f")
    return "0" if rendered in {"-0", ""} else rendered


def _associated_kind(text: str, start: int, end: int) -> TargetNumericKind:
    before = text[max(0, start - 16) : start]
    after = text[end : end + 24]
    if _MONEY_PREFIX.search(before) or _MONEY_SUFFIX.search(after):
        return "money"
    if _PERCENT_SUFFIX.search(after):
        return "percent"
    if _DAY_SUFFIX.search(after):
        return "day"
    if _MONTH_SUFFIX.search(after):
        return "month"
    if _YEAR_SUFFIX.search(after):
        return "year"
    return "generic"


def _overlaps(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    return any(span[0] < other[1] and other[0] < span[1] for other in spans)


def _numeric_claims(text: str) -> tuple[TargetNumericClaim, ...]:
    normalized = unicodedata.normalize("NFKC", text)
    lexical_spans = [match.span() for match in _LEXICAL_NAME.finditer(normalized)]
    consumed: list[tuple[int, int]] = []
    ordered: list[tuple[int, TargetNumericClaim]] = []
    for match in _RANGE.finditer(normalized):
        if _overlaps(match.span(), lexical_spans):
            continue
        kind = _associated_kind(normalized, match.start(), match.end())
        first_span = match.span("first")
        second_span = match.span("second")
        consumed.extend((first_span, second_span))
        ordered.append(
            (
                first_span[0],
                TargetNumericClaim(kind=kind, value=_number_value(match.group("first"))),
            )
        )
        ordered.append(
            (
                second_span[0],
                TargetNumericClaim(kind=kind, value=_number_value(match.group("second"))),
            )
        )
    for match in _NUMBER.finditer(normalized):
        if _overlaps(match.span(), lexical_spans) or _overlaps(match.span(), consumed):
            continue
        ordered.append(
            (
                match.start(),
                TargetNumericClaim(
                    kind=_associated_kind(normalized, match.start(), match.end()),
                    value=_number_value(match.group()),
                ),
            )
        )
    ordered.sort(key=lambda item: item[0])
    return tuple(claim for _position, claim in ordered)


def _strict_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _structured_json(text: str) -> dict[str, object]:
    try:
        value = json.loads(text, object_pairs_hook=_strict_pairs)
    except (json.JSONDecodeError, ValueError) as exc:
        _error("target_verifier_input_invalid", "evidence", exc)
    if type(value) is not dict:
        _error("target_verifier_input_invalid", "evidence")
    return value


def _exact_keys(value: object, keys: tuple[str, ...]) -> bool:
    return type(value) is dict and tuple(value) == keys


def _amount(value: object) -> bool:
    return type(value) is int and value >= 0


def _text_list(value: object, *, unique: bool) -> bool:
    return (
        type(value) is list
        and all(_canonical(item) for item in value)
        and (not unique or len(value) == len(set(value)))
    )


def _offer_claims(block: TargetComposerEvidenceBlock) -> tuple[TargetNumericClaim, ...]:
    payload = _structured_json(block.text)
    if not _exact_keys(
        payload,
        (
            "offer_id",
            "service_id",
            "option_id",
            "brand_id",
            "price",
            "package",
            "payment_stages",
        ),
    ):
        _error("target_verifier_input_invalid", "evidence")
    if not _canonical(payload["offer_id"]) or not _canonical(payload["service_id"]):
        _error("target_verifier_input_invalid", "evidence")
    if any(
        value is not None and not _canonical(value)
        for value in (payload["option_id"], payload["brand_id"])
    ):
        _error("target_verifier_input_invalid", "evidence")

    price = payload["price"]
    if type(price) is not dict or type(price.get("mode")) is not str:
        _error("target_verifier_input_invalid", "evidence")
    mode = price["mode"]
    claims: list[TargetNumericClaim] = []
    if mode == "fixed":
        valid = _exact_keys(price, ("mode", "amount", "currency", "billing_unit"))
        amount_names = ("amount",)
    elif mode == "from":
        valid = _exact_keys(price, ("mode", "min_amount", "currency", "billing_unit"))
        amount_names = ("min_amount",)
    elif mode == "range":
        valid = _exact_keys(
            price,
            ("mode", "min_amount", "max_amount", "currency", "billing_unit"),
        )
        amount_names = ("min_amount", "max_amount")
    elif mode == "no_public_price":
        valid = _exact_keys(price, ("mode", "approved_text")) and _canonical(
            price.get("approved_text")
        )
        amount_names = ()
    else:
        valid = False
        amount_names = ()
    if not valid:
        _error("target_verifier_input_invalid", "evidence")
    if mode != "no_public_price" and (
        not all(_amount(price[name]) for name in amount_names)
        or not _canonical(price.get("currency"))
        or not _canonical(price.get("billing_unit"))
    ):
        _error("target_verifier_input_invalid", "evidence")
    if mode == "range" and price["min_amount"] > price["max_amount"]:
        _error("target_verifier_input_invalid", "evidence")
    claims.extend(
        TargetNumericClaim(kind="money", value=str(price[name])) for name in amount_names
    )
    if mode == "no_public_price":
        claims.extend(_numeric_claims(price["approved_text"]))

    package = payload["package"]
    if (
        not _exact_keys(package, ("label", "includes"))
        or not _canonical(package["label"])
        or not _text_list(package["includes"], unique=True)
    ):
        _error("target_verifier_input_invalid", "evidence")
    claims.extend(_numeric_claims(package["label"]))
    for item in package["includes"]:
        claims.extend(_numeric_claims(item))

    stages = payload["payment_stages"]
    if stages is not None:
        if type(stages) is not list or not stages:
            _error("target_verifier_input_invalid", "evidence")
        labels: list[str] = []
        for stage in stages:
            if (
                not _exact_keys(stage, ("label", "amount", "currency"))
                or not _canonical(stage["label"])
                or not _amount(stage["amount"])
                or not _canonical(stage["currency"])
            ):
                _error("target_verifier_input_invalid", "evidence")
            labels.append(stage["label"])
            claims.extend(_numeric_claims(stage["label"]))
            claims.append(TargetNumericClaim(kind="money", value=str(stage["amount"])))
        if len(labels) != len(set(labels)):
            _error("target_verifier_input_invalid", "evidence")
    return tuple(claims)


def _doctor_claims(block: TargetComposerEvidenceBlock) -> tuple[TargetNumericClaim, ...]:
    payload = _structured_json(block.text)
    if not _exact_keys(
        payload,
        ("doctor_id", "name", "position", "experience_years", "profile_text"),
    ) or not all(
        _canonical(payload[name]) for name in ("doctor_id", "name", "position", "profile_text")
    ):
        _error("target_verifier_input_invalid", "evidence")
    if not _amount(payload["experience_years"]):
        _error("target_verifier_input_invalid", "evidence")
    claims: list[TargetNumericClaim] = [
        TargetNumericClaim(kind="year", value=str(payload["experience_years"]))
    ]
    for name in ("name", "position", "profile_text"):
        claims.extend(_numeric_claims(payload[name]))
    return tuple(claims)


def _structured_commercial_whitelist(
    blocks: tuple[TargetComposerEvidenceBlock, ...],
) -> frozenset[TargetNumericClaim]:
    claims: list[TargetNumericClaim] = []
    for block in blocks:
        if block.kind == "offer":
            claims.extend(_offer_claims(block))
        elif block.kind == "commercial_fact":
            claims.extend(_numeric_claims(block.text))
        elif block.kind in {"doctor", "external_doctor"}:
            claims.extend(_doctor_claims(block))
    return frozenset(claims)


def _general_numeric_whitelist(
    blocks: tuple[TargetComposerEvidenceBlock, ...],
    corpus_text: str,
) -> frozenset[TargetNumericClaim]:
    claims: list[TargetNumericClaim] = []
    for block in blocks:
        if block.kind not in {"offer", "commercial_fact", "doctor", "external_doctor"}:
            claims.extend(_numeric_claims(block.text))
    claims.extend(_numeric_claims(corpus_text))
    return frozenset(claims)


def _claim_in_corpus(claim: TargetNumericClaim, corpus_text: str) -> bool:
    if claim.kind in {"money", "percent"}:
        return False
    return claim.value in corpus_text or claim.value.replace(".", ",") in corpus_text


def _evidence_whitelist(
    blocks: tuple[TargetComposerEvidenceBlock, ...],
) -> frozenset[TargetNumericClaim]:
    claims: list[TargetNumericClaim] = []
    for block in blocks:
        if block.kind == "offer":
            claims.extend(_offer_claims(block))
        elif block.kind in {"doctor", "external_doctor"}:
            claims.extend(_doctor_claims(block))
        else:
            claims.extend(_numeric_claims(block.text))
    return frozenset(claims)


def _compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False)


def _normalize_span_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", normalized).strip()


def _span_in_candidate(span: str, candidate_text: str) -> bool:
    normalized_span = _normalize_span_text(span)
    if not normalized_span:
        return False
    return normalized_span in _normalize_span_text(candidate_text)


def _validated_semantic_issue(raw: object, *, candidate_text: str) -> TargetSemanticIssue:
    if type(raw) is TargetSemanticIssue:
        issue = raw
    elif type(raw) is dict:
        kind = raw.get("kind")
        offending_span = raw.get("offending_span")
        if type(kind) is not str or kind not in _TARGET_SEMANTIC_ISSUE_KINDS:
            _error("target_verifier_semantic_output_invalid", raw)
        if not _canonical(offending_span):
            _error("target_verifier_semantic_output_invalid", raw)
        issue = TargetSemanticIssue(kind=kind, offending_span=offending_span)  # type: ignore[arg-type]
    else:
        _error("target_verifier_semantic_output_invalid", raw)
    if not _span_in_candidate(issue.offending_span, candidate_text):
        _error("target_verifier_semantic_output_invalid", issue.offending_span)
    return issue


def _validated_semantic_assessment(
    assessment: object,
    *,
    candidate_text: str,
) -> TargetSemanticAssessment:
    if type(assessment) is TargetSemanticAssessment:
        raw_issues = assessment.issues
    elif type(assessment) is dict:
        raw_issues = assessment.get("issues")
        if raw_issues is None:
            _error("target_verifier_semantic_output_invalid", assessment)
        if type(raw_issues) is not list:
            _error("target_verifier_semantic_output_invalid", assessment)
    else:
        _error("target_verifier_semantic_output_invalid", assessment)
    issues = tuple(
        _validated_semantic_issue(item, candidate_text=candidate_text) for item in raw_issues
    )
    return TargetSemanticAssessment(issues=issues)


def _blocking_issues(assessment: TargetSemanticAssessment) -> tuple[TargetSemanticIssue, ...]:
    return tuple(
        issue for issue in assessment.issues if issue.kind in _TARGET_SEMANTIC_BLOCKING_KINDS
    )


def _semantic_invocation(
    request: TargetComposerRequest,
    response: TargetUnverifiedComposedResponse,
    verifier_context: str,
) -> TargetSemanticVerifierInvocation:
    spec = request.spec
    spec_payload = {
        "response_mode": spec.response_mode,
        "allowed_topics": list(spec.allowed_topics),
        "forbidden_topics": list(spec.forbidden_topics),
        "required_fact_ids": list(spec.required_fact_ids),
        "allow_cta": spec.allow_cta,
        "allow_consultation_close": spec.allow_consultation_close,
    }
    evidence_payload = [
        {
            "kind": block.kind,
            "ref": block.ref,
            "topics": list(block.topics),
            "fact_ids": list(block.fact_ids),
            "text": block.text,
            "must_preserve_exact": block.must_preserve_exact,
        }
        for block in request.evidence_blocks
    ]
    return TargetSemanticVerifierInvocation(
        system_policy=TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY,
        cached_full_context=verifier_context,
        response_spec_json=_compact_json(spec_payload),
        primary_evidence_json=_compact_json(evidence_payload),
        candidate_text=response.text,
    )


def _document_block_from_context(context_text: str, content_ref: str) -> str | None:
    begin = f"---BEGIN DOC:{content_ref}---\n"
    end = f"\n---END DOC:{content_ref}---"
    start = context_text.find(begin)
    if start < 0:
        return None
    finish = context_text.find(end, start + len(begin))
    if finish < 0:
        return None
    return context_text[start : finish + len(end)]


def _structured_evidence_is_complete(request: TargetComposerRequest) -> bool:
    kinds = {block.kind for block in request.evidence_blocks}
    for component in request.spec.required_components:
        if component == "price" and "offer" not in kinds:
            return False
        if component == "doctors" and not kinds.intersection({"doctor", "external_doctor"}):
            return False
        if component == "content":
            return False
    required_facts = set(request.spec.required_fact_ids)
    observed_facts = {
        fact_id for block in request.evidence_blocks for fact_id in block.fact_ids
    }
    return required_facts.issubset(observed_facts)


def _verifier_context(
    request: TargetComposerRequest,
    cached_full_context: TargetCachedFullContext,
    *,
    used_content_refs: tuple[str, ...],
    exact_service_authority: bool,
) -> tuple[str, str]:
    """Return conservative model context and an anonymous observability mode.

    FullContext remains the fallback for every generic/incomplete request. A
    lightweight context is allowed only when package-owned MD refs or exact
    structured evidence deterministically cover the response specification.
    """

    full = cached_full_context.model_corpus_text
    try:
        if exact_service_authority and used_content_refs:
            blocks = tuple(
                _document_block_from_context(full, ref) for ref in used_content_refs
            )
            if all(blocks):
                return "\n".join(block for block in blocks if block), "exact_documents"
        if _structured_evidence_is_complete(request):
            return (
                "No additional MD context is required. "
                "The exact PRIMARY_EVIDENCE records are authoritative.",
                "exact_structured_evidence",
            )
    except Exception:  # noqa: BLE001 - optimization must never weaken verification
        pass
    return full, "fullcontext_fallback"


def _validate_cached_full_context(value: object) -> TargetCachedFullContext:
    if type(value) is not TargetCachedFullContext:
        _error("target_verifier_full_context_invalid", "full_context_type")
    if not _canonical(value.corpus_text):
        _error("target_verifier_full_context_invalid", "full_context_empty")
    return value


def _resolve_validated_source_identity(
    response: TargetUnverifiedComposedResponse,
    *,
    md_root: Path,
    package_primary: str | None,
    package_used: tuple[str, ...],
    exact_service_authority: bool,
) -> tuple[str | None, tuple[str, ...]]:
    if exact_service_authority and package_primary:
        validated_used = validate_used_content_refs(
            md_root,
            tuple(ref for ref in package_used if ref),
        )
        normalized_primary = validate_used_content_refs(md_root, (package_primary,))
        primary = normalized_primary[0] if normalized_primary else None
        if primary and primary not in validated_used:
            validated_used = (primary, *tuple(ref for ref in validated_used if ref != primary))
        return primary, validated_used

    if response.source_identity is not None:
        validated_used = validate_used_content_refs(
            md_root,
            response.source_identity.used_content_refs,
        )
        primary: str | None = None
        if response.source_identity.primary_content_ref:
            normalized_primary = validate_used_content_refs(
                md_root,
                (response.source_identity.primary_content_ref,),
            )
            primary = normalized_primary[0] if normalized_primary else None
        if primary is None and validated_used:
            primary = validated_used[0]
        if primary and primary not in validated_used:
            validated_used = (primary, *tuple(ref for ref in validated_used if ref != primary))
        return primary, validated_used

    candidates = tuple(
        ref
        for ref in (
            *(package_used or ()),
            *((package_primary,) if package_primary else ()),
        )
        if ref
    )
    validated_used = validate_used_content_refs(md_root, candidates)
    if package_primary:
        normalized_primary = validate_used_content_refs(md_root, (package_primary,))
        primary = normalized_primary[0] if normalized_primary else None
    elif validated_used:
        primary = validated_used[0]
    else:
        primary = None
    return primary, validated_used


def verify_target_composed_response(
    request: TargetComposerRequest,
    response: TargetUnverifiedComposedResponse,
    *,
    cached_full_context: TargetCachedFullContext,
    semantic_backend: TargetSemanticVerifierBackend,
    navigation_followups: tuple[TargetNavigationFollowup, ...] = (),
    md_root: Path | None = None,
    primary_content_ref: str | None = None,
    used_content_refs: tuple[str, ...] = (),
    exact_service_authority: bool = False,
    client_id: str | None = None,
) -> TargetVerifiedComposedResponse:
    """Verify one adjacent S37 response without modifying or repairing its text."""

    request, response = _validated_inputs(request, response)
    validated_context = _validate_cached_full_context(cached_full_context)

    turn_timing.stage_start("verifier_deterministic")
    try:
        structured_whitelist = _structured_commercial_whitelist(request.evidence_blocks)
        general_whitelist = _general_numeric_whitelist(
            request.evidence_blocks,
            validated_context.corpus_text,
        )
        for claim in _numeric_claims(response.text):
            if claim.kind == "money":
                if claim not in structured_whitelist:
                    _error("target_verifier_numeric_ungrounded", (claim.kind, claim.value))
            elif (
                claim not in structured_whitelist
                and claim not in general_whitelist
                and not _claim_in_corpus(claim, validated_context.corpus_text)
            ):
                _error("target_verifier_numeric_ungrounded", (claim.kind, claim.value))
        for block in request.evidence_blocks:
            if block.kind != "commercial_fact" or not block.must_preserve_exact:
                continue
            if block.fact_ids and block.fact_ids[0] in request.spec.required_fact_ids:
                if block.text not in response.text:
                    _error("target_verifier_strict_fact_missing", block.fact_ids[0])
        has_clinic_contact = any(block.kind == "clinic_contact" for block in request.evidence_blocks)
        if has_clinic_contact:
            from core.target_contact_authority import (
                branch_by_id,
                canonical_contact_scalar,
                load_clinic_contact_facts,
                normalize_contact_scalar,
                parse_contact_evidence_ref,
            )

            contact_blocks = [
                block for block in request.evidence_blocks if block.kind == "clinic_contact"
            ]
            normalized_answer = normalize_contact_scalar(response.text)
            facts = load_clinic_contact_facts(client_id or "demo")
            for block in contact_blocks:
                field, branch_id = parse_contact_evidence_ref(block.ref)
                if field is None:
                    _error("target_verifier_clinic_contact_missing", block.ref)
                if branch_id is not None:
                    if branch_by_id(facts, branch_id) is None:
                        _error("target_verifier_clinic_contact_missing", block.ref)
                    if normalize_contact_scalar(block.text) not in normalized_answer:
                        _error("target_verifier_clinic_contact_missing", block.ref)
                    continue
                canonical = canonical_contact_scalar(
                    field,
                    client_id=client_id or "demo",
                    branch_id=None,
                )
                if not canonical:
                    _error("target_verifier_clinic_contact_missing", block.ref)
                if normalize_contact_scalar(canonical) not in normalized_answer:
                    _error("target_verifier_clinic_contact_missing", block.ref)
    except Exception:
        turn_timing.stage_end("verifier_deterministic", status="blocked")
        turn_timing.stage_skipped("verifier_semantic", reason="deterministic_block")
        raise
    turn_timing.stage_end("verifier_deterministic", status="completed")

    verifier_context, verifier_context_mode = _verifier_context(
        request,
        validated_context,
        used_content_refs=used_content_refs,
        exact_service_authority=exact_service_authority,
    )
    turn_timing.set_flag("verifier_context_mode", verifier_context_mode)
    turn_timing.set_flag("verifier_context_chars", len(verifier_context))

    turn_timing.stage_start("verifier_semantic")
    try:
        try:
            assess = getattr(semantic_backend, "assess")
        except Exception:
            _error("target_verifier_backend_invalid", "semantic_assess")
        if not callable(assess):
            _error("target_verifier_backend_invalid", "semantic_assess")
        invocation = _semantic_invocation(request, response, verifier_context)
        try:
            assessment = assess(invocation)
        except Exception as exc:
            _error("target_verifier_backend_failed", type(exc).__name__, exc)
        validated_assessment = _validated_semantic_assessment(
            assessment,
            candidate_text=response.text,
        )
        blocking = _blocking_issues(validated_assessment)
        if blocking:
            _error(
                "target_verifier_semantic_rejected",
                tuple((issue.kind, issue.offending_span) for issue in blocking),
            )
    except Exception:
        turn_timing.stage_end("verifier_semantic", status="blocked")
        raise
    turn_timing.stage_end("verifier_semantic", status="completed")

    validated_primary: str | None = None
    validated_used: tuple[str, ...] = ()
    if md_root is not None:
        validated_primary, validated_used = _resolve_validated_source_identity(
            response,
            md_root=md_root,
            package_primary=primary_content_ref,
            package_used=used_content_refs,
            exact_service_authority=exact_service_authority,
        )
    return TargetVerifiedComposedResponse(
        text=response.text,
        spec=response.spec,
        selected_followups=response.selected_followups,
        selected_cta_key=response.selected_cta_key,
        navigation_followups=navigation_followups,
        primary_content_ref=validated_primary,
        used_content_refs=validated_used,
    )
