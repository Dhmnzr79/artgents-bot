"""Fail-closed target response verification boundary (S38, offline/unwired)."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal, NoReturn, Protocol, TypeAlias

from contracts.target_response_spec import TargetResponseSpec
from core.target_composer_executor import TargetUnverifiedComposedResponse
from core.target_composer_request import (
    TargetComposerEvidenceBlock,
    TargetComposerRequest,
)
from core.target_response_followup_policy import TargetResponseFollowupSelection


TargetNumericKind: TypeAlias = Literal[
    "money",
    "percent",
    "day",
    "month",
    "year",
    "generic",
]

TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY = """1. Assess whether every factual claim, including numbers written with digits or words and their units and context, is grounded in PRIMARY_EVIDENCE.
2. Assess whether the answer stays inside allowed topics and outside forbidden topics.
3. In medical_handoff, reject diagnosis, differential diagnosis, personal eligibility, or treatment choice. For an ordinary answer, medical_boundary_ok must still be true.
4. Assess every selected commercial fact, not only required_fact_ids: natural facts must be present without meaning change and strict facts must remain verbatim.
5. Return only the four-field structured assessment. Never rewrite, repair, shorten, or replace the candidate answer."""


@dataclass(frozen=True, slots=True)
class TargetNumericClaim:
    kind: TargetNumericKind
    value: str


@dataclass(frozen=True, slots=True)
class TargetSemanticVerifierInvocation:
    system_policy: str
    response_spec_json: str
    primary_evidence_json: str
    candidate_text: str


@dataclass(frozen=True, slots=True)
class TargetSemanticVerification:
    grounded_in_primary_evidence: bool
    topic_scope_ok: bool
    medical_boundary_ok: bool
    selected_facts_ok: bool


class TargetSemanticVerifierBackend(Protocol):
    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object: ...


@dataclass(frozen=True, slots=True)
class TargetVerifiedComposedResponse:
    text: str
    spec: TargetResponseSpec
    selected_followups: TargetResponseFollowupSelection
    selected_cta_key: str | None
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
    if type(blocks) is not tuple or not blocks:
        _error("target_verifier_input_invalid", "evidence")
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


def _semantic_invocation(
    request: TargetComposerRequest,
    response: TargetUnverifiedComposedResponse,
) -> TargetSemanticVerifierInvocation:
    spec = request.spec
    spec_payload = {
        "response_mode": spec.response_mode,
        "allowed_topics": list(spec.allowed_topics),
        "forbidden_topics": list(spec.forbidden_topics),
        "required_fact_ids": list(spec.required_fact_ids),
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
        response_spec_json=_compact_json(spec_payload),
        primary_evidence_json=_compact_json(evidence_payload),
        candidate_text=response.text,
    )


def verify_target_composed_response(
    request: TargetComposerRequest,
    response: TargetUnverifiedComposedResponse,
    *,
    semantic_backend: TargetSemanticVerifierBackend,
) -> TargetVerifiedComposedResponse:
    """Verify one adjacent S37 response without modifying or repairing its text."""

    request, response = _validated_inputs(request, response)
    whitelist = _evidence_whitelist(request.evidence_blocks)
    for claim in _numeric_claims(response.text):
        if claim not in whitelist:
            _error("target_verifier_numeric_ungrounded", (claim.kind, claim.value))
    for block in request.evidence_blocks:
        if (
            block.kind == "commercial_fact"
            and block.must_preserve_exact
            and block.text not in response.text
        ):
            _error("target_verifier_strict_fact_missing", block.fact_ids[0])
    try:
        assess = getattr(semantic_backend, "assess")
    except Exception:
        _error("target_verifier_backend_invalid", "semantic_assess")
    if not callable(assess):
        _error("target_verifier_backend_invalid", "semantic_assess")
    invocation = _semantic_invocation(request, response)
    try:
        assessment = assess(invocation)
    except Exception as exc:
        _error("target_verifier_backend_failed", type(exc).__name__, exc)
    if type(assessment) is not TargetSemanticVerification or not all(
        type(getattr(assessment, name)) is bool
        for name in (
            "grounded_in_primary_evidence",
            "topic_scope_ok",
            "medical_boundary_ok",
            "selected_facts_ok",
        )
    ):
        _error("target_verifier_semantic_output_invalid", assessment)
    failed = tuple(
        name
        for name in (
            "grounded_in_primary_evidence",
            "topic_scope_ok",
            "medical_boundary_ok",
            "selected_facts_ok",
        )
        if not getattr(assessment, name)
    )
    if failed:
        _error("target_verifier_semantic_rejected", failed)
    return TargetVerifiedComposedResponse(
        text=response.text,
        spec=response.spec,
        selected_followups=response.selected_followups,
        selected_cta_key=response.selected_cta_key,
    )
