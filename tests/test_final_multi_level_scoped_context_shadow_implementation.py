"""Phase 2 implementation acceptance tests for FINAL_MULTI_LEVEL_SCOPED_CONTEXT_SHADOW / PERF-6.

Exercises the real demo client pack (read-only) through the real
``run_target_offline_policy_bound_verified_response_pipeline`` with fake/recording Composer and
Verifier backends (the same pattern as
``tests/test_demo_target_policy_bound_verified_response_pipeline.py``) -- no live/provider/network
calls anywhere. Proves the shadow hook (§16 of TASK.md's PERF-6 Phase 2 completion record) is
fully inert with respect to the real answer: identical call counts, identical Composer/Verifier
invocation content, identical output, and a Verifier-blocked turn raises the exact same exception
it always did.
"""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from contracts.doctor_schema_refs import (
    DoctorCatalogExternalIndex,
    build_doctor_source_refs,
    validate_doctor_catalog_external_refs,
)
from contracts.response_schema import TargetStrategyMatch
from contracts.response_schema_refs import (
    ResponseSchemaExternalIndex,
    validate_response_schema_external_refs,
)
from contracts.service_consultation import validate_service_consultation_refs
from contracts.target_response_policy import TargetResponsePolicyRequest
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.response_schema_loader import load_response_schema_bundle
from core.service_consultation_source import build_service_consultation_values
from core.target_cached_full_context import build_target_cached_full_context
from core.target_composer_executor import TargetComposerInvocation, TargetComposerTone
from core.target_composer_output import composer_test_json
from core.target_policy_bound_verified_response_pipeline import (
    run_target_offline_policy_bound_verified_response_pipeline,
)
from core.target_response_verifier import (
    TargetResponseVerificationError,
    TargetSemanticAssessment,
    TargetSemanticIssue,
    TargetSemanticVerifierInvocation,
)

DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"
DEMO_FULL_CONTEXT = build_target_cached_full_context(MD_ROOT)
VALID_TEXT = (
    "All-on-4 в клинике стоит от 318 000 рублей за одну челюсть. "
    "Кузнецов Дмитрий Андреевич — врач со стажем 19 лет. "
    "Можно пройти бесплатную консультацию: врач посмотрит снимки и поможет "
    "подобрать подходящий протокол."
)


class RecordingComposerBackend:
    def __init__(self, text: str = VALID_TEXT) -> None:
        self.text = text
        self.invocations: list[TargetComposerInvocation] = []

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.invocations.append(invocation)
        return composer_test_json(self.text)


class RecordingSemanticBackend:
    def __init__(self, *, accepted: bool = True) -> None:
        self.accepted = accepted
        self.invocations: list[TargetSemanticVerifierInvocation] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.invocations.append(invocation)
        if self.accepted:
            return TargetSemanticAssessment()
        return TargetSemanticAssessment(
            issues=(
                TargetSemanticIssue(kind="unsupported_clinic_claim", offending_span="318 000"),
            )
        )


def _real_inputs() -> dict[str, object]:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")
    kb_refs = build_response_schema_kb_refs(MD_ROOT)
    doctor_index = DoctorCatalogExternalIndex(service_ids=tuple(bundle.services), kb_refs=kb_refs)
    assert validate_doctor_catalog_external_refs(doctors, doctor_index) is None
    external_index = ResponseSchemaExternalIndex(
        kb_refs=kb_refs,
        doctor_refs=build_doctor_source_refs(doctors),
    )
    assert validate_response_schema_external_refs(bundle, external_index) is None
    consultations = build_service_consultation_values(MD_ROOT)
    assert validate_service_consultation_refs(consultations, bundle.services) is None
    return {
        "policy_request": TargetResponsePolicyRequest.model_validate(
            {
                "response_mode": "answer",
                "service_id": "all_on_4",
                "tone_key": "commercial_warm",
                "allowed_topics": ("implantation", "doctors"),
                "forbidden_topics": ("diagnosis", "personal_eligibility"),
                "required_fact_ids": ("free_implant_consult",),
                "requested_components": ("content", "price", "doctors"),
                "primary_component": "content",
                "allow_marketing_facts": True,
                "allow_consultation_close": True,
                "allow_cta": True,
            }
        ),
        "bundle": bundle,
        "doctor_catalog": doctors,
        "external_index": external_index,
        "consultation_values": consultations,
        "brand_term": None,
        "strategy_context": TargetStrategyMatch(family="implantology", extent="full_arch"),
        "semantic_context": "service",
        "today": date(2026, 7, 31),
        "md_root": MD_ROOT,
        "cached_full_context": DEMO_FULL_CONTEXT,
        "include_initial_block": True,
        "include_consultation_close": True,
        "include_cta": True,
        "shown_fact_ids": ("installment_12", "implant_same_day_discount"),
        "user_message": "Расскажите про All-on-4, цену и врачей",
        "tone": TargetComposerTone(
            key="commercial_warm",
            instruction="Отвечай доброжелательно и без давления.",
        ),
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------------------------
# 32/33/45. Call-count parity -- exactly one Composer call, one Verifier call, zero extras
# --------------------------------------------------------------------------------------------


def test_32_33_45_call_counts_unchanged_with_shadow_active() -> None:
    inputs = _real_inputs()
    composer = RecordingComposerBackend()
    semantic = RecordingSemanticBackend()

    result = run_target_offline_policy_bound_verified_response_pipeline(
        **inputs,  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )

    assert len(composer.invocations) == 1
    assert len(semantic.invocations) == 1
    assert result.verification_status == "verified"


# --------------------------------------------------------------------------------------------
# 53/54/55. Real cached FullContext / Composer invocation / Verifier invocation unchanged
# --------------------------------------------------------------------------------------------


def test_53_54_55_composer_carries_compact_corpus_and_verifier_exact_documents() -> None:
    inputs = _real_inputs()
    composer = RecordingComposerBackend()
    semantic = RecordingSemanticBackend()

    run_target_offline_policy_bound_verified_response_pipeline(
        **inputs,  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )

    assert composer.invocations[0].cached_full_context == DEMO_FULL_CONTEXT.model_corpus_text
    verifier_context = semantic.invocations[0].cached_full_context
    assert "---BEGIN DOC:implantation__service__all_on_4.md---" in verifier_context
    assert "---END DOC:implantation__service__all_on_4.md---" in verifier_context
    assert "---BEGIN DOC:clinic__info__advantages.md---" not in verifier_context
    assert len(verifier_context) < len(DEMO_FULL_CONTEXT.model_corpus_text)
    assert composer.invocations[0].primary_evidence_json == semantic.invocations[0].primary_evidence_json


# --------------------------------------------------------------------------------------------
# 34/35/36/37. Output/buttons/CTA/source-identity unchanged; PERF-5 profile untouched
# --------------------------------------------------------------------------------------------


def test_34_35_36_37_output_buttons_cta_source_identity_and_length_profile_unchanged() -> None:
    inputs = _real_inputs()
    composer = RecordingComposerBackend()
    semantic = RecordingSemanticBackend()

    result = run_target_offline_policy_bound_verified_response_pipeline(
        **inputs,  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )

    assert result.text == VALID_TEXT
    assert result.spec.service_id == "all_on_4"
    assert result.selected_cta_key == "plan"
    assert result.selected_followups.source == "content"
    assert result.primary_content_ref is not None
    directives = json.loads(composer.invocations[0].response_directives_json)
    assert "response_length_profile" not in directives or directives.get(
        "response_length_profile"
    ) in (None, "standard_information")


# --------------------------------------------------------------------------------------------
# 29/30/31. Verifier block preserves the exact same exception/route; shadow never blocks/retries
# --------------------------------------------------------------------------------------------


def test_29_30_31_verifier_block_raises_exact_same_typed_error() -> None:
    inputs = _real_inputs()
    composer = RecordingComposerBackend()
    semantic = RecordingSemanticBackend(accepted=False)

    with pytest.raises(TargetResponseVerificationError) as caught:
        run_target_offline_policy_bound_verified_response_pipeline(
            **inputs,  # type: ignore[arg-type]
            composer_backend=composer,
            semantic_backend=semantic,
        )

    assert caught.value.code == "target_verifier_semantic_rejected"
    # Composer still called exactly once; no retry, no widened re-call.
    assert len(composer.invocations) == 1
    assert len(semantic.invocations) == 1


# --------------------------------------------------------------------------------------------
# demo client pack + product source files untouched by this test run (read-only proof)
# --------------------------------------------------------------------------------------------


def test_demo_pack_untouched_by_a_full_pipeline_run() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}
    inputs = _real_inputs()
    run_target_offline_policy_bound_verified_response_pipeline(
        **inputs,  # type: ignore[arg-type]
        composer_backend=RecordingComposerBackend(),
        semantic_backend=RecordingSemanticBackend(),
    )
    assert {path: _sha256(path) for path in paths} == before


# --------------------------------------------------------------------------------------------
# 52. Decision is never stored in a global/ContextVar/session -- static proof over the new code
# --------------------------------------------------------------------------------------------


def _module_source(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "path",
    [
        "core/target_context_scope_resolver.py",
        "core/target_context_scope_shadow.py",
        "core/target_policy_bound_verified_response_pipeline.py",
    ],
)
def test_52_no_contextvar_global_or_session_state_introduced(path: str) -> None:
    source = _module_source(path)
    tree = ast.parse(source)
    assert "ContextVar(" not in source
    for node in ast.walk(tree):
        assert not isinstance(node, ast.Global), path
        assert not isinstance(node, ast.Nonlocal), path


def test_shadow_decision_variable_is_local_not_returned_from_public_pipeline() -> None:
    """The public pipeline entry point's return type is unchanged (still exactly
    ``TargetVerifiedComposedResponse`` / the selection tuple) -- the shadow decision is never
    threaded into the return value, session, or any shared state."""

    import inspect

    from core.target_policy_bound_verified_response_pipeline import (
        run_target_offline_policy_bound_verified_response_pipeline_with_selection,
    )

    sig = inspect.signature(run_target_offline_policy_bound_verified_response_pipeline_with_selection)
    assert "TargetVerifiedComposedResponse" in str(sig.return_annotation)
    assert "TargetContextScopeDecision" not in str(sig.return_annotation)


# --------------------------------------------------------------------------------------------
# 38/39. Structured contacts/service-availability short-circuit paths never reach the resolver
# --------------------------------------------------------------------------------------------


def test_38_39_structured_capability_modules_do_not_import_the_resolver() -> None:
    """Structured contact / service-availability answers short-circuit in
    core/target_runtime_turn.py *before* the policy-bound pipeline is ever called (materialized by
    materialize_structured_contact_turn_response / materialize_structured_service_availability_
    turn_response) -- neither of those modules has any reason to import the scope resolver, and
    this test keeps that true."""

    import core.target_structured_answer as contact_mod
    import core.target_structured_service_availability as availability_mod

    for mod in (contact_mod, availability_mod):
        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "target_context_scope_resolver" not in source
        assert "target_context_scope_shadow" not in source
