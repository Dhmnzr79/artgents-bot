from __future__ import annotations

import hashlib
import inspect
import json
import re
from dataclasses import MISSING, FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

from contracts.target_cached_full_context import TargetCachedFullContext
from contracts.target_response_spec import TargetResponseSpec
from core.target_composer_executor import TargetUnverifiedComposedResponse
from core.target_composer_request import (
    TargetComposerEvidenceBlock,
    TargetComposerRequest,
)
from core.target_response_followup_policy import TargetResponseFollowupSelection
from core.target_response_verifier import (
    TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY,
    TargetNumericClaim,
    TargetResponseVerificationError,
    TargetSemanticAssessment,
    TargetSemanticIssue,
    TargetSemanticVerifierInvocation,
    TargetVerifiedComposedResponse,
    verify_target_composed_response,
)


class RecordingBackend:
    def __init__(self, assessment: object | None = None) -> None:
        self.assessment = assessment or TargetSemanticAssessment()
        self.invocations: list[TargetSemanticVerifierInvocation] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.invocations.append(invocation)
        return self.assessment


class FailingBackend:
    def __init__(self) -> None:
        self.calls = 0

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.calls += 1
        raise RuntimeError("semantic provider detail")


def _cached_context(
    text: str = "corpus service_one offer 318000 19 doctor profile",
) -> TargetCachedFullContext:
    return TargetCachedFullContext(
        corpus_text=text,
        document_count=1,
        document_paths=("service_one.md",),
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _spec(**updates: object) -> TargetResponseSpec:
    payload: dict[str, object] = {
        "response_mode": "answer",
        "service_id": "service_one",
        "tone_key": "commercial_warm",
        "allowed_topics": ("implantation",),
        "forbidden_topics": ("diagnosis",),
        "required_fact_ids": ("strict_fact",),
        "required_components": ("content", "price", "doctors"),
        "followup_source": None,
        "allow_marketing_facts": True,
        "allow_consultation_close": True,
        "allow_cta": True,
    }
    payload.update(updates)
    return TargetResponseSpec.model_validate(payload)


def _offer_text(
    *,
    price: dict[str, object] | None = None,
    package_label: str = "Пакет 2 этапа",
    includes: list[str] | None = None,
    stages: list[dict[str, object]] | None = None,
) -> str:
    payload = {
        "offer_id": "offer_one",
        "service_id": "service_one",
        "option_id": None,
        "brand_id": None,
        "price": price
        or {
            "mode": "fixed",
            "amount": 100000,
            "currency": "RUB",
            "billing_unit": "jaw",
        },
        "package": {
            "label": package_label,
            "includes": ["До 3 визитов"] if includes is None else includes,
        },
        "payment_stages": (
            [
                {"label": "Этап 1", "amount": 60000, "currency": "RUB"},
                {"label": "Этап 2", "amount": 40000, "currency": "RUB"},
            ]
            if stages is None
            else stages
        ),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _doctor_text() -> str:
    return json.dumps(
        {
            "doctor_id": "doctor_one",
            "name": "Doctor 7",
            "position": "Implantologist 8",
            "experience_years": 15,
            "profile_text": "Врач ведёт практику более 20 лет.",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _block(
    kind: str,
    ref: str,
    text: str,
    *,
    fact_ids: tuple[str, ...] = (),
    preserve: bool,
) -> TargetComposerEvidenceBlock:
    return TargetComposerEvidenceBlock(
        kind=kind,  # type: ignore[arg-type]
        ref=ref,
        topics=("implantation",),
        fact_ids=fact_ids,
        text=text,
        must_preserve_exact=preserve,
    )


def _default_blocks() -> tuple[TargetComposerEvidenceBlock, ...]:
    return (
        _block(
            "content",
            "content:service_one.md",
            "All-on-4: срок 1–3 дня, показатель 13%.",
            preserve=False,
        ),
        _block("offer", "offer:offer_one", _offer_text(), preserve=True),
        _block("doctor", "doctor:doctor_one", _doctor_text(), preserve=True),
        _block(
            "commercial_fact",
            "fact:strict_fact",
            "Строгий факт 5 лет.",
            fact_ids=("strict_fact",),
            preserve=True,
        ),
        _block(
            "commercial_fact",
            "fact:natural_fact",
            "Свободный факт о консультации.",
            fact_ids=("natural_fact",),
            preserve=False,
        ),
    )


def _request(
    *,
    spec: TargetResponseSpec | None = None,
    blocks: tuple[TargetComposerEvidenceBlock, ...] | object | None = None,
) -> TargetComposerRequest:
    return TargetComposerRequest(
        user_message="Расскажите об услуге",
        spec=spec or _spec(),
        evidence_blocks=_default_blocks() if blocks is None else blocks,  # type: ignore[arg-type]
        selected_followups=TargetResponseFollowupSelection(
            source=None,
            content=(),
            price=(),
        ),
        selected_cta_key="plan",
    )


def _valid_text() -> str:
    return (
        "All-on-4 стоит 100 000 рублей. Оплата: 60 000 ₽ и 40 000 RUB. "
        "Срок 1–3 дня. Стаж врача 15 лет. Строгий факт 5 лет. "
        "Свободная консультация доступна."
    )


def _response(
    request: TargetComposerRequest,
    text: str | None = None,
) -> TargetUnverifiedComposedResponse:
    return TargetUnverifiedComposedResponse(
        text=text or _valid_text(),
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )


def _caught(callable_) -> TargetResponseVerificationError:
    with pytest.raises(TargetResponseVerificationError) as caught:
        callable_()
    return caught.value


def test_contract_shapes_signature_policy_and_exact_error_codes() -> None:
    assert [(field.name, field.default) for field in fields(TargetNumericClaim)] == [
        ("kind", MISSING),
        ("value", MISSING),
    ]
    assert [field.name for field in fields(TargetSemanticVerifierInvocation)] == [
        "system_policy",
        "cached_full_context",
        "response_spec_json",
        "primary_evidence_json",
        "candidate_text",
    ]
    assert [field.name for field in fields(TargetSemanticIssue)] == [
        "kind",
        "offending_span",
    ]
    assert [field.name for field in fields(TargetSemanticAssessment)] == ["issues"]
    assert [field.name for field in fields(TargetVerifiedComposedResponse)] == [
        "text",
        "spec",
        "selected_followups",
        "selected_cta_key",
        "verification_status",
    ]
    assert list(inspect.signature(verify_target_composed_response).parameters) == [
        "request",
        "response",
        "cached_full_context",
        "semantic_backend",
    ]
    source = Path("core/target_response_verifier.py").read_text(encoding="utf-8")
    assert set(re.findall(r'"(target_verifier_[a-z_]+)"', source)) == {
        "target_verifier_input_invalid",
        "target_verifier_numeric_ungrounded",
        "target_verifier_strict_fact_missing",
        "target_verifier_backend_invalid",
        "target_verifier_backend_failed",
        "target_verifier_semantic_output_invalid",
        "target_verifier_semantic_rejected",
        "target_verifier_full_context_invalid",
    }
    assert "CACHED_FULL_CONTEXT" in TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY
    assert "unsupported_clinic_claim" in TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY
    assert "Never rewrite" in TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY
    assert "minor_external_detail" in TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY
    assert "NOT AN ISSUE" in TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY
    assert "doctor will decide after examination" in TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY
    assert "Absence of grounding alone is not a block reason" in TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY


def test_success_calls_one_semantic_backend_and_preserves_exact_response() -> None:
    request = _request()
    response = _response(request)
    backend = RecordingBackend()

    result = verify_target_composed_response(
        request,
        response,
        cached_full_context=_cached_context(),
        semantic_backend=backend,
    )

    assert len(backend.invocations) == 1
    invocation = backend.invocations[0]
    assert invocation.system_policy is TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY
    assert invocation.candidate_text is response.text
    assert list(json.loads(invocation.response_spec_json)) == [
        "response_mode",
        "allowed_topics",
        "forbidden_topics",
        "required_fact_ids",
        "allow_cta",
        "allow_consultation_close",
    ]
    evidence = json.loads(invocation.primary_evidence_json)
    assert list(evidence[0]) == [
        "kind",
        "ref",
        "topics",
        "fact_ids",
        "text",
        "must_preserve_exact",
    ]
    combined = invocation.response_spec_json + invocation.primary_evidence_json
    assert '"plan"' not in combined
    assert "selected_followups" not in combined
    assert result.text is response.text
    assert result.spec is response.spec
    assert result.selected_followups is response.selected_followups
    assert result.selected_cta_key is response.selected_cta_key
    assert result.verification_status == "verified"
    with pytest.raises(FrozenInstanceError):
        result.text = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "rendered",
    [
        "100 000 ₽",
        "100000 руб",
        "100000 руб.",
        "100000 рубль",
        "100000 рубля",
        "100000 рублей",
        "100000 р.",
        "100000 RUB",
        "₽ 100000",
        "rub 100000",
    ],
)
def test_common_currency_prefix_postfix_forms_match_structured_money(rendered: str) -> None:
    request = _request()
    text = f"Цена — {rendered}. Строгий факт 5 лет."
    backend = RecordingBackend()
    result = verify_target_composed_response(
        request,
        _response(request, text),
        cached_full_context=_cached_context(),
        semantic_backend=backend,
    )
    assert result.verification_status == "verified"
    assert len(backend.invocations) == 1


def test_price_only_all_on_4_name_is_semantic_but_standalone_four_blocks() -> None:
    blocks = (_block("offer", "offer:offer_one", _offer_text(), preserve=True),)
    request = _request(
        spec=_spec(required_fact_ids=(), required_components=("price",)),
        blocks=blocks,
    )
    backend = RecordingBackend()
    accepted = verify_target_composed_response(
        request,
        _response(request, "All-on-4 стоит 100 000 рублей."),
        cached_full_context=_cached_context(),
        semantic_backend=backend,
    )
    assert accepted.verification_status == "verified"
    assert len(backend.invocations) == 1

    blocked_backend = RecordingBackend()
    error = _caught(
        lambda: verify_target_composed_response(
            request,
            _response(request, "Есть 4 варианта по 100 000 рублей."),
            cached_full_context=_cached_context(),
            semantic_backend=blocked_backend,
        )
    )
    assert (error.code, error.value, blocked_backend.invocations) == (
        "target_verifier_numeric_ungrounded",
        ("generic", "4"),
        [],
    )


@pytest.mark.parametrize(
    ("price", "candidate"),
    [
        (
            {
                "mode": "from",
                "min_amount": 90000,
                "currency": "RUB",
                "billing_unit": "jaw",
            },
            "Цена от 90 000 рублей.",
        ),
        (
            {
                "mode": "range",
                "min_amount": 90000,
                "max_amount": 120000,
                "currency": "RUB",
                "billing_unit": "jaw",
            },
            "Цена 90 000–120 000 рублей.",
        ),
        (
            {"mode": "no_public_price", "approved_text": "Цена после 2 этапов."},
            "Цена после 2 этапов.",
        ),
    ],
)
def test_all_price_modes_authorize_only_their_exact_numeric_sources(
    price: dict[str, object],
    candidate: str,
) -> None:
    offer = _offer_text(price=price, package_label="Пакет", includes=[])
    blocks = (_block("offer", "offer:offer_one", offer, preserve=True),)
    request = _request(
        spec=_spec(required_fact_ids=(), required_components=("price",)),
        blocks=blocks,
    )
    result = verify_target_composed_response(
        request,
        _response(request, candidate),
        cached_full_context=_cached_context(),
        semantic_backend=RecordingBackend(),
    )
    assert result.verification_status == "verified"


def test_package_stage_and_doctor_profile_text_contribute_without_ids() -> None:
    blocks = (
        _block("offer", "offer:offer_one", _offer_text(), preserve=True),
        _block("doctor", "doctor:doctor_one", _doctor_text(), preserve=True),
    )
    request = _request(
        spec=_spec(required_fact_ids=(), required_components=("price", "doctors")),
        blocks=blocks,
    )
    text = (
        "Пакет 2 этапа, до 3 визитов. Этап 1. "
        "Doctor 7, Implantologist 8, практикует более 20 лет."
    )
    result = verify_target_composed_response(
        request,
        _response(request, text),
        cached_full_context=_cached_context(),
        semantic_backend=RecordingBackend(),
    )
    assert result.verification_status == "verified"


def test_digit_ranges_percent_decimals_and_time_are_typed() -> None:
    request = _request()
    accepted = (
        "Срок 1–3 дня, показатель 13,0%. All-on-4. "
        "Строгий факт 5 лет."
    )
    result = verify_target_composed_response(
        request,
        _response(request, accepted),
        cached_full_context=_cached_context(),
        semantic_backend=RecordingBackend(),
    )
    assert result.verification_status == "verified"

    error = _caught(
        lambda: verify_target_composed_response(
            request,
            _response(request, "Срок 1–4 дня. Строгий факт 5 лет."),
            cached_full_context=_cached_context(),
            semantic_backend=RecordingBackend(),
        )
    )
    assert (error.code, error.value) == (
        "target_verifier_numeric_ungrounded",
        ("day", "4"),
    )


def test_number_words_are_delegated_to_mandatory_semantic_assessment() -> None:
    request = _request()
    backend = RecordingBackend(
        TargetSemanticAssessment(
            issues=(
                TargetSemanticIssue(
                    kind="unsupported_clinic_claim",
                    offending_span="сто тысяч рублей",
                ),
            )
        )
    )
    error = _caught(
        lambda: verify_target_composed_response(
            request,
            _response(request, "Цена — сто тысяч рублей. Строгий факт 5 лет."),
            cached_full_context=_cached_context(),
            semantic_backend=backend,
        )
    )
    assert len(backend.invocations) == 1
    assert (error.code, error.value) == (
        "target_verifier_semantic_rejected",
        (("unsupported_clinic_claim", "сто тысяч рублей"),),
    )


@pytest.mark.parametrize(
    ("mutator", "marker"),
    [
        (lambda request, response: (object(), response), "request"),
        (lambda request, response: (request, object()), "response"),
        (
            lambda request, response: (
                replace(
                    request,
                    spec=request.spec.model_copy(update={"allowed_topics": object()}),
                ),
                response,
            ),
            "spec",
        ),
        (
            lambda request, response: (
                request,
                replace(response, spec=request.spec.model_copy()),
            ),
            "identity",
        ),
        (
            lambda request, response: (replace(request, evidence_blocks=[]), response),
            "evidence",
        ),
    ],
)
def test_hostile_adjacent_inputs_fail_typed_before_backend(mutator, marker: str) -> None:
    request = _request()
    response = _response(request)
    candidate_request, candidate_response = mutator(request, response)
    backend = RecordingBackend()
    error = _caught(
        lambda: verify_target_composed_response(
            candidate_request,
            candidate_response,
            cached_full_context=_cached_context(),
            semantic_backend=backend,
        )
    )
    assert (error.code, error.value, backend.invocations) == (
        "target_verifier_input_invalid",
        marker,
        [],
    )


def test_malformed_structured_offer_invariants_fail_before_backend() -> None:
    invalid_prices = (
        {
            "mode": "range",
            "min_amount": 120000,
            "max_amount": 90000,
            "currency": "RUB",
            "billing_unit": "jaw",
        },
        {
            "mode": "fixed",
            "amount": True,
            "currency": "RUB",
            "billing_unit": "jaw",
        },
    )
    for price in invalid_prices:
        blocks = (
            _block(
                "offer",
                "offer:offer_one",
                _offer_text(price=price),
                preserve=True,
            ),
        )
        request = _request(
            spec=_spec(required_fact_ids=(), required_components=("price",)),
            blocks=blocks,
        )
        backend = RecordingBackend()
        error = _caught(
            lambda: verify_target_composed_response(
                request,
                _response(request, "Цена уточняется."),
                cached_full_context=_cached_context(),
            semantic_backend=backend,
            )
        )
        assert (error.code, error.value, backend.invocations) == (
            "target_verifier_input_invalid",
            "evidence",
            [],
        )

    duplicate_stages = [
        {"label": "Этап", "amount": 60000, "currency": "RUB"},
        {"label": "Этап", "amount": 40000, "currency": "RUB"},
    ]
    blocks = (
        _block(
            "offer",
            "offer:offer_one",
            _offer_text(stages=duplicate_stages),
            preserve=True,
        ),
    )
    request = _request(
        spec=_spec(required_fact_ids=(), required_components=("price",)),
        blocks=blocks,
    )
    error = _caught(
        lambda: verify_target_composed_response(
            request,
            _response(request, "Цена уточняется."),
            cached_full_context=_cached_context(),
            semantic_backend=RecordingBackend(),
        )
    )
    assert (error.code, error.value) == ("target_verifier_input_invalid", "evidence")


def test_numeric_and_strict_fact_fail_before_semantic_backend_without_repair() -> None:
    request = _request()
    numeric_backend = RecordingBackend()
    numeric = _caught(
        lambda: verify_target_composed_response(
            request,
            _response(request, "Цена 999 999 рублей. Строгий факт 5 лет."),
            cached_full_context=_cached_context(),
            semantic_backend=numeric_backend,
        )
    )
    assert (numeric.code, numeric.value, numeric_backend.invocations) == (
        "target_verifier_numeric_ungrounded",
        ("money", "999999"),
        [],
    )

    strict_backend = RecordingBackend()
    original = "Цена 100 000 рублей. Перефразированный факт 5 лет."
    strict = _caught(
        lambda: verify_target_composed_response(
            request,
            _response(request, original),
            cached_full_context=_cached_context(),
            semantic_backend=strict_backend,
        )
    )
    assert (strict.code, strict.value, strict_backend.invocations) == (
        "target_verifier_strict_fact_missing",
        "strict_fact",
        [],
    )
    assert original == "Цена 100 000 рублей. Перефразированный факт 5 лет."


def test_backend_failures_and_semantic_false_fields_are_fail_closed_once() -> None:
    request = _request()
    response = _response(request)
    invalid = _caught(
        lambda: verify_target_composed_response(
            request,
            response,
            cached_full_context=_cached_context(),
            semantic_backend=object(),  # type: ignore[arg-type]
        )
    )
    assert (invalid.code, invalid.value) == (
        "target_verifier_backend_invalid",
        "semantic_assess",
    )

    failing = FailingBackend()
    failed = _caught(
        lambda: verify_target_composed_response(
            request,
            response,
            cached_full_context=_cached_context(),
            semantic_backend=failing,
        )
    )
    assert (failed.code, failed.value, failing.calls) == (
        "target_verifier_backend_failed",
        "RuntimeError",
        1,
    )
    assert isinstance(failed.__cause__, RuntimeError)

    malformed_backend = RecordingBackend(object())
    malformed = _caught(
        lambda: verify_target_composed_response(
            request,
            response,
            cached_full_context=_cached_context(),
            semantic_backend=malformed_backend,
        )
    )
    assert malformed.code == "target_verifier_semantic_output_invalid"

    rejected_backend = RecordingBackend(
        TargetSemanticAssessment(
            issues=(
                TargetSemanticIssue(
                    kind="personal_medical_conclusion",
                    offending_span="Вам нельзя",
                ),
                TargetSemanticIssue(
                    kind="material_external_medical_claim",
                    offending_span="три месяца",
                ),
            )
        )
    )
    rejected = _caught(
        lambda: verify_target_composed_response(
            request,
            _response(
                request,
                "Вам нельзя имплантацию. Полное заживление занимает три месяца. "
                "Строгий факт 5 лет.",
            ),
            cached_full_context=_cached_context(),
            semantic_backend=rejected_backend,
        )
    )
    assert rejected.code == "target_verifier_semantic_rejected"
    assert rejected.value == (
        ("personal_medical_conclusion", "Вам нельзя"),
        ("material_external_medical_claim", "три месяца"),
    )
    assert len(rejected_backend.invocations) == 1


def test_content_only_spec_accepts_empty_evidence_blocks() -> None:
    spec = _spec(
        service_id=None,
        required_fact_ids=(),
        required_components=("content",),
        allow_marketing_facts=False,
        allow_cta=False,
    )
    request = TargetComposerRequest(
        user_message="Общий вопрос",
        spec=spec,
        evidence_blocks=(),
        selected_followups=TargetResponseFollowupSelection(
            source=None,
            content=(),
            price=(),
        ),
        selected_cta_key=None,
    )
    result = verify_target_composed_response(
        request,
        TargetUnverifiedComposedResponse(
            text="Общий ответ из материалов клиники без чисел.",
            spec=spec,
            selected_followups=request.selected_followups,
            selected_cta_key=None,
        ),
        cached_full_context=_cached_context("corpus general clinic answer"),
        semantic_backend=RecordingBackend(),
    )
    assert result.verification_status == "verified"


def test_content_only_money_claim_is_rejected_without_structured_evidence() -> None:
    spec = _spec(
        service_id=None,
        required_fact_ids=(),
        required_components=("content",),
        allow_marketing_facts=False,
        allow_cta=False,
    )
    request = TargetComposerRequest(
        user_message="Сколько стоит?",
        spec=spec,
        evidence_blocks=(),
        selected_followups=TargetResponseFollowupSelection(
            source=None,
            content=(),
            price=(),
        ),
        selected_cta_key=None,
    )
    error = _caught(
        lambda: verify_target_composed_response(
            request,
            TargetUnverifiedComposedResponse(
                text="Имплантация стоит 100 000 рублей.",
                spec=spec,
                selected_followups=request.selected_followups,
                selected_cta_key=None,
            ),
            cached_full_context=_cached_context("corpus without prices"),
            semantic_backend=RecordingBackend(),
        )
    )
    assert error.code == "target_verifier_numeric_ungrounded"
    assert error.value[0] == "money"


def test_medical_handoff_also_gets_one_mandatory_semantic_check() -> None:
    spec = _spec(response_mode="medical_handoff")
    request = _request(spec=spec)
    backend = RecordingBackend()
    result = verify_target_composed_response(
        request,
        _response(request),
        cached_full_context=_cached_context(),
        semantic_backend=backend,
    )
    assert result.verification_status == "verified"
    assert len(backend.invocations) == 1
    assert json.loads(backend.invocations[0].response_spec_json)[
        "response_mode"
    ] == "medical_handoff"
    assert "personal eligibility" in backend.invocations[0].system_policy


def test_import_firewall_excludes_legacy_provider_runtime_and_live_hooks() -> None:
    source = Path("core/target_response_verifier.py").read_text(encoding="utf-8")
    filtered_import_lines = "\n".join(
        line
        for line in source.splitlines()
        if line.startswith(("import ", "from "))
        and "target_cached_full_context" not in line
    ).lower()
    forbidden = (
        "numeric_fact_gate",
        "verifier_verdict",
        "openai",
        "anthropic",
        "requests",
        "httpx",
        "router",
        "session",
        "cache",
        "search",
    )
    assert all(token not in filtered_import_lines for token in forbidden)
    assert "pytest.skip" not in source
    assert "xfail" not in source


def test_minor_external_detail_is_warning_only_and_does_not_reject() -> None:
    request = _request()
    backend = RecordingBackend(
        TargetSemanticAssessment(
            issues=(
                TargetSemanticIssue(
                    kind="minor_external_detail",
                    offending_span="аутоиммунным заболеваниям",
                ),
            )
        )
    )
    result = verify_target_composed_response(
        request,
        _response(
            request,
            "Волчанка относится к аутоиммунным заболеваниям. Строгий факт 5 лет.",
        ),
        cached_full_context=_cached_context(),
        semantic_backend=backend,
    )
    assert result.verification_status == "verified"


def test_invalid_offending_span_fails_before_acceptance() -> None:
    request = _request()
    backend = RecordingBackend(
        TargetSemanticAssessment(
            issues=(
                TargetSemanticIssue(
                    kind="material_external_medical_claim",
                    offending_span="missing fragment",
                ),
            )
        )
    )
    error = _caught(
        lambda: verify_target_composed_response(
            request,
            _response(request),
            cached_full_context=_cached_context(),
            semantic_backend=backend,
        )
    )
    assert error.code == "target_verifier_semantic_output_invalid"


def test_empathy_and_consultation_wording_passes_with_empty_issues() -> None:
    request = _request(
        spec=_spec(
            service_id=None,
            required_fact_ids=(),
            required_components=("content",),
            allow_marketing_facts=False,
            allow_cta=False,
        ),
        blocks=(),
    )
    request = TargetComposerRequest(
        user_message="Больно ли?",
        spec=request.spec,
        evidence_blocks=(),
        selected_followups=TargetResponseFollowupSelection(
            source=None,
            content=(),
            price=(),
        ),
        selected_cta_key=None,
    )
    text = (
        "Понимаю ваш страх — это нормально. "
        "На консультации врач спокойно объяснит, как проходит обезболивание."
    )
    result = verify_target_composed_response(
        request,
        TargetUnverifiedComposedResponse(
            text=text,
            spec=request.spec,
            selected_followups=request.selected_followups,
            selected_cta_key=None,
        ),
        cached_full_context=_cached_context("corpus анестезия консультация"),
        semantic_backend=RecordingBackend(),
    )
    assert result.verification_status == "verified"
