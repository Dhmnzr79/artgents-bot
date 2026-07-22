from __future__ import annotations

import ast
import inspect
from datetime import date
from pathlib import Path

import pytest

import core.target_boundary_enforced_fullcontext_response as s46_module
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
from contracts.target_medical_boundary import (
    TargetMedicalBoundaryResult,
    TargetMedicalBoundaryTerminalEnforcement,
)
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.response_schema_loader import load_response_schema_bundle
from core.service_consultation_source import build_service_consultation_values
from core.target_boundary_enforced_fullcontext_response import (
    run_target_offline_boundary_enforced_fullcontext_response,
)
from core.target_cached_full_context import build_target_cached_full_context
from core.target_composer_executor import (
    TargetComposerInvocation,
    TargetComposerTone,
)
from core.target_response_verifier import (
    TargetSemanticVerification,
    TargetSemanticVerifierInvocation,
)
from core.target_turn_frame_dispatch import TargetTurnFrameDispatchError
from core.target_turn_frame_policy_envelope_enforcement import (
    TargetMedicalBoundaryEnforcementError,
    enforce_target_medical_boundary_on_envelope,
)
from core.turn_frame_from_raw import build_turn_frame_from_raw


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"
DEMO_FULL_CONTEXT = build_target_cached_full_context(MD_ROOT)

PRICE_TEXT = (
    "All-on-4 в клинике стоит от 318 000 рублей за одну челюсть. "
    "Можно пройти бесплатную консультацию."
)
PAIN_GROUNDED_TEXT = (
    "Страх боли при имплантации — нормальная реакция. "
    "Во время операции используется современная прицельная анестезия: "
    "она эффективно убирает боль. "
    "Максимальные ощущения — лёгкий дискомфорт, сопоставимый с лечением кариеса. "
    "На консультации заранее обсудят, какой вариант обезболивания подходит."
)
MISSING_TOPIC_TEXT = (
    "В материалах клиники нет информации по этой теме. "
    "На консультации врач ответит на ваш вопрос и подскажет, что актуально именно для вас."
)
EXTERNAL_MEDICAL_TEXT = (
    "В материалах клиники нет информации по этой теме. "
    "Системный красный волчанок — аутоиммунное заболевание соединительной ткани."
)


class RecordingComposerBackend:
    def __init__(self, text: str) -> None:
        self.text = text
        self.invocations: list[TargetComposerInvocation] = []

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.invocations.append(invocation)
        return self.text


class RecordingSemanticBackend:
    def __init__(self, assessment: TargetSemanticVerification | None = None) -> None:
        self.assessment = assessment or TargetSemanticVerification(
            general_grounding_ok=True,
            strict_commercial_grounding_ok=True,
            topic_scope_ok=True,
            medical_boundary_ok=True,
            selected_facts_ok=True,
        )
        self.invocations: list[TargetSemanticVerifierInvocation] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.invocations.append(invocation)
        return self.assessment


class RuleBasedSemanticBackend:
    def __init__(self, *, mode: str) -> None:
        self.mode = mode
        self.invocations: list[TargetSemanticVerifierInvocation] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.invocations.append(invocation)
        text = invocation.candidate_text.lower()
        if self.mode == "pain":
            corpus = invocation.cached_full_context.lower()
            grounded = "анестез" in text and "анестез" in corpus
            personal_promise = "вам не будет больно" in text
            return TargetSemanticVerification(
                general_grounding_ok=grounded,
                strict_commercial_grounding_ok=True,
                topic_scope_ok=True,
                medical_boundary_ok=not personal_promise,
                selected_facts_ok=True,
            )
        if self.mode == "missing_ok":
            no_external = "волчан" not in text and "аутоиммун" not in text
            mentions_gap = "материал" in text and "нет" in text
            return TargetSemanticVerification(
                general_grounding_ok=mentions_gap,
                strict_commercial_grounding_ok=True,
                topic_scope_ok=True,
                medical_boundary_ok=no_external,
                selected_facts_ok=True,
            )
        if self.mode == "missing_reject":
            return TargetSemanticVerification(
                general_grounding_ok=True,
                strict_commercial_grounding_ok=True,
                topic_scope_ok=True,
                medical_boundary_ok=False,
                selected_facts_ok=True,
            )
        raise AssertionError(f"unknown mode: {self.mode}")


def _boundary(
    *,
    decision: str,
    reason_code: str,
    source: str = "backend",
    confidence: float = 0.9,
) -> TargetMedicalBoundaryResult:
    return TargetMedicalBoundaryResult.model_validate(
        {
            "decision": decision,
            "confidence": confidence,
            "reason_code": reason_code,
            "source": source,
        }
    )


def _policy_kwargs(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "tone_key": "commercial_warm",
        "allowed_topics": ("implantation", "doctors"),
        "forbidden_topics": ("diagnosis", "personal_eligibility"),
        "required_fact_ids": (),
        "allow_marketing_facts": True,
        "allow_consultation_close": True,
        "allow_cta": True,
        "min_topic_confidence": 0.5,
        "min_service_confidence": 0.0,
        "min_intent_confidence": 0.0,
    }
    payload.update(overrides)
    return payload


def _frame(**overrides: object):
    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["pain"],
        "primary_aspect": None,
        "service_id": None,
        "topic": "implantation",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=frozenset({"implantation", "doctors"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )


def _pipeline_inputs(**overrides: object) -> dict[str, object]:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")
    kb_refs = build_response_schema_kb_refs(MD_ROOT)
    doctor_index = DoctorCatalogExternalIndex(
        service_ids=tuple(bundle.services),
        kb_refs=kb_refs,
    )
    assert validate_doctor_catalog_external_refs(doctors, doctor_index) is None
    external_index = ResponseSchemaExternalIndex(
        kb_refs=kb_refs,
        doctor_refs=build_doctor_source_refs(doctors),
    )
    assert validate_response_schema_external_refs(bundle, external_index) is None
    consultations = build_service_consultation_values(MD_ROOT)
    assert validate_service_consultation_refs(consultations, bundle.services) is None
    payload: dict[str, object] = {
        "bundle": bundle,
        "doctor_catalog": doctors,
        "external_index": external_index,
        "consultation_values": consultations,
        "brand_term": None,
        "strategy_context": TargetStrategyMatch(
            family="implantology",
            extent="full_arch",
        ),
        "semantic_context": "service",
        "today": date(2026, 7, 22),
        "md_root": MD_ROOT,
        "cached_full_context": DEMO_FULL_CONTEXT,
        "include_initial_block": False,
        "include_consultation_close": True,
        "include_cta": False,
        "user_message": "Больно ли ставить имплант?",
        "tone": TargetComposerTone(
            key="commercial_warm",
            instruction="Отвечай доброжелательно и без давления.",
        ),
    }
    payload.update(overrides)
    return payload


def test_public_signature_is_single_straight_line_entrypoint() -> None:
    params = list(
        inspect.signature(
            run_target_offline_boundary_enforced_fullcontext_response
        ).parameters
    )
    assert params[0:2] == ["turn_frame", "boundary"]
    assert "cached_full_context" in params
    assert "composer_backend" in params
    source = inspect.getsource(run_target_offline_boundary_enforced_fullcontext_response)
    tree = ast.parse(source)
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)
    relevant_calls = [
        node.func.id
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id
        in {
            "enforce_target_medical_boundary_on_envelope",
            "run_target_offline_turn_frame_bound_response",
        }
    ]
    assert relevant_calls == [
        "enforce_target_medical_boundary_on_envelope",
        "run_target_offline_turn_frame_bound_response",
    ]


def test_boundary_none_service_price_enforces_once_and_verifies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enforce_calls = 0
    s41_calls = 0
    real_enforce = enforce_target_medical_boundary_on_envelope
    real_s41 = s46_module.run_target_offline_turn_frame_bound_response

    def counting_enforce(*args: object, **kwargs: object) -> object:
        nonlocal enforce_calls
        enforce_calls += 1
        return real_enforce(*args, **kwargs)

    def counting_s41(*args: object, **kwargs: object) -> object:
        nonlocal s41_calls
        s41_calls += 1
        return real_s41(*args, **kwargs)

    monkeypatch.setattr(
        s46_module,
        "enforce_target_medical_boundary_on_envelope",
        counting_enforce,
    )
    monkeypatch.setattr(
        s46_module,
        "run_target_offline_turn_frame_bound_response",
        counting_s41,
    )
    composer = RecordingComposerBackend(PRICE_TEXT)
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs(
        turn_frame=_frame(
            service_id="all_on_4",
            aspects=["price"],
            primary_aspect="price",
        ),
        boundary=_boundary(decision="none", reason_code="boundary_none_confident"),
        user_message="Сколько стоит All-on-4?",
        composer_backend=composer,
        semantic_backend=semantic,
        include_cta=True,
    )
    result = run_target_offline_boundary_enforced_fullcontext_response(
        inputs["turn_frame"],  # type: ignore[arg-type]
        inputs["boundary"],  # type: ignore[arg-type]
        inputs["bundle"],  # type: ignore[arg-type]
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["external_index"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        **_policy_kwargs(),
        brand_term=inputs["brand_term"],  # type: ignore[arg-type]
        strategy_context=inputs["strategy_context"],  # type: ignore[arg-type]
        semantic_context=inputs["semantic_context"],  # type: ignore[arg-type]
        today=inputs["today"],  # type: ignore[arg-type]
        md_root=inputs["md_root"],  # type: ignore[arg-type]
        cached_full_context=inputs["cached_full_context"],  # type: ignore[arg-type]
        include_initial_block=inputs["include_initial_block"],  # type: ignore[arg-type]
        include_consultation_close=inputs["include_consultation_close"],  # type: ignore[arg-type]
        include_cta=True,
        user_message=inputs["user_message"],  # type: ignore[arg-type]
        tone=inputs["tone"],  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert enforce_calls == 1
    assert s41_calls == 1
    assert len(composer.invocations) == 1
    assert len(semantic.invocations) == 1
    assert result.verified.verification_status == "verified"


def test_confident_medical_handoff_pain_materializes_without_service_id() -> None:
    composer = RecordingComposerBackend(PAIN_GROUNDED_TEXT)
    semantic = RuleBasedSemanticBackend(mode="pain")
    inputs = _pipeline_inputs(
        turn_frame=_frame(),
        boundary=_boundary(
            decision="medical_handoff",
            reason_code="boundary_medical_handoff_confident",
        ),
        composer_backend=composer,
        semantic_backend=semantic,
    )
    result = run_target_offline_boundary_enforced_fullcontext_response(
        inputs["turn_frame"],  # type: ignore[arg-type]
        inputs["boundary"],  # type: ignore[arg-type]
        inputs["bundle"],  # type: ignore[arg-type]
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["external_index"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        **_policy_kwargs(),
        brand_term=inputs["brand_term"],  # type: ignore[arg-type]
        strategy_context=inputs["strategy_context"],  # type: ignore[arg-type]
        semantic_context=inputs["semantic_context"],  # type: ignore[arg-type]
        today=inputs["today"],  # type: ignore[arg-type]
        md_root=inputs["md_root"],  # type: ignore[arg-type]
        cached_full_context=inputs["cached_full_context"],  # type: ignore[arg-type]
        include_initial_block=inputs["include_initial_block"],  # type: ignore[arg-type]
        include_consultation_close=inputs["include_consultation_close"],  # type: ignore[arg-type]
        include_cta=inputs["include_cta"],  # type: ignore[arg-type]
        user_message=inputs["user_message"],  # type: ignore[arg-type]
        tone=inputs["tone"],  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.dispatch.policy_request.service_id is None
    assert result.dispatch.policy_request.response_mode == "medical_handoff"
    assert len(composer.invocations) == 1
    assert len(semantic.invocations) == 1
    assert result.verified.verification_status == "verified"


def test_confident_medical_handoff_missing_base_materializes_not_defer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    md_root = tmp_path / "md"
    md_root.mkdir()
    (md_root / "general.md").write_text(
        "---\ndoc_id: general\ntopic: implantation\n---\n\n## Общее\nКлиника проводит имплантацию.\n",
        encoding="utf-8",
    )
    cached = build_target_cached_full_context(md_root)
    composer = RecordingComposerBackend(MISSING_TOPIC_TEXT)
    semantic = RuleBasedSemanticBackend(mode="missing_ok")
    inputs = _pipeline_inputs(
        turn_frame=_frame(aspects=["overview"], route="content"),
        boundary=_boundary(
            decision="medical_handoff",
            reason_code="boundary_medical_handoff_confident",
        ),
        md_root=md_root,
        cached_full_context=cached,
        user_message="Можно ли делать имплантацию при системной красной волчанке?",
        composer_backend=composer,
        semantic_backend=semantic,
    )
    result = run_target_offline_boundary_enforced_fullcontext_response(
        inputs["turn_frame"],  # type: ignore[arg-type]
        inputs["boundary"],  # type: ignore[arg-type]
        inputs["bundle"],  # type: ignore[arg-type]
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["external_index"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        **_policy_kwargs(allow_marketing_facts=False),
        brand_term=inputs["brand_term"],  # type: ignore[arg-type]
        strategy_context=inputs["strategy_context"],  # type: ignore[arg-type]
        semantic_context=inputs["semantic_context"],  # type: ignore[arg-type]
        today=inputs["today"],  # type: ignore[arg-type]
        md_root=md_root,
        cached_full_context=cached,
        include_initial_block=inputs["include_initial_block"],  # type: ignore[arg-type]
        include_consultation_close=inputs["include_consultation_close"],  # type: ignore[arg-type]
        include_cta=inputs["include_cta"],  # type: ignore[arg-type]
        user_message=inputs["user_message"],  # type: ignore[arg-type]
        tone=inputs["tone"],  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.verification_status == "verified"

    reject_composer = RecordingComposerBackend(EXTERNAL_MEDICAL_TEXT)
    reject_semantic = RuleBasedSemanticBackend(mode="missing_reject")
    with pytest.raises(Exception) as caught:
        run_target_offline_boundary_enforced_fullcontext_response(
            inputs["turn_frame"],  # type: ignore[arg-type]
            inputs["boundary"],  # type: ignore[arg-type]
            inputs["bundle"],  # type: ignore[arg-type]
            inputs["doctor_catalog"],  # type: ignore[arg-type]
            inputs["external_index"],  # type: ignore[arg-type]
            inputs["consultation_values"],  # type: ignore[arg-type]
            **_policy_kwargs(allow_marketing_facts=False),
            brand_term=inputs["brand_term"],  # type: ignore[arg-type]
            strategy_context=inputs["strategy_context"],  # type: ignore[arg-type]
            semantic_context=inputs["semantic_context"],  # type: ignore[arg-type]
            today=inputs["today"],  # type: ignore[arg-type]
            md_root=md_root,
            cached_full_context=cached,
            include_initial_block=inputs["include_initial_block"],  # type: ignore[arg-type]
            include_consultation_close=inputs["include_consultation_close"],  # type: ignore[arg-type]
            include_cta=inputs["include_cta"],  # type: ignore[arg-type]
            user_message=inputs["user_message"],  # type: ignore[arg-type]
            tone=inputs["tone"],  # type: ignore[arg-type]
            composer_backend=reject_composer,
            semantic_backend=reject_semantic,
        )
    assert caught.value.__class__.__name__ == "TargetResponseVerificationError"


def test_uncertain_boundary_returns_terminal_without_s41_or_backends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s41_calls = 0

    def forbidden_s41(*args: object, **kwargs: object) -> object:
        nonlocal s41_calls
        s41_calls += 1
        raise AssertionError("S41 must not run for uncertain boundary")

    monkeypatch.setattr(
        s46_module,
        "run_target_offline_turn_frame_bound_response",
        forbidden_s41,
    )
    composer = RecordingComposerBackend(PAIN_GROUNDED_TEXT)
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs(
        turn_frame=_frame(),
        boundary=_boundary(
            decision="uncertain",
            reason_code="boundary_uncertain_low_confidence",
            source="fail_closed",
            confidence=0.0,
        ),
        composer_backend=composer,
        semantic_backend=semantic,
    )
    result = run_target_offline_boundary_enforced_fullcontext_response(
        inputs["turn_frame"],  # type: ignore[arg-type]
        inputs["boundary"],  # type: ignore[arg-type]
        inputs["bundle"],  # type: ignore[arg-type]
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["external_index"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        **_policy_kwargs(),
        brand_term=inputs["brand_term"],  # type: ignore[arg-type]
        strategy_context=inputs["strategy_context"],  # type: ignore[arg-type]
        semantic_context=inputs["semantic_context"],  # type: ignore[arg-type]
        today=inputs["today"],  # type: ignore[arg-type]
        md_root=inputs["md_root"],  # type: ignore[arg-type]
        cached_full_context=inputs["cached_full_context"],  # type: ignore[arg-type]
        include_initial_block=inputs["include_initial_block"],  # type: ignore[arg-type]
        include_consultation_close=inputs["include_consultation_close"],  # type: ignore[arg-type]
        include_cta=inputs["include_cta"],  # type: ignore[arg-type]
        user_message=inputs["user_message"],  # type: ignore[arg-type]
        tone=inputs["tone"],  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetMedicalBoundaryTerminalEnforcement)
    assert result.terminal_mode == "defer"
    assert s41_calls == 0
    assert composer.invocations == []
    assert semantic.invocations == []


def test_inconsistent_boundary_fails_closed_before_downstream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        s46_module,
        "run_target_offline_turn_frame_bound_response",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("S41 must not run for inconsistent boundary")
        ),
    )
    inconsistent = TargetMedicalBoundaryResult.model_construct(
        decision="none",
        confidence=0.9,
        reason_code="boundary_medical_handoff_confident",
        source="backend",
    )
    inputs = _pipeline_inputs(
        turn_frame=_frame(),
        boundary=inconsistent,
        composer_backend=RecordingComposerBackend(PAIN_GROUNDED_TEXT),
        semantic_backend=RecordingSemanticBackend(),
    )
    with pytest.raises(TargetMedicalBoundaryEnforcementError) as caught:
        run_target_offline_boundary_enforced_fullcontext_response(
            inputs["turn_frame"],  # type: ignore[arg-type]
            inputs["boundary"],  # type: ignore[arg-type]
            inputs["bundle"],  # type: ignore[arg-type]
            inputs["doctor_catalog"],  # type: ignore[arg-type]
            inputs["external_index"],  # type: ignore[arg-type]
            inputs["consultation_values"],  # type: ignore[arg-type]
            **_policy_kwargs(),
            brand_term=inputs["brand_term"],  # type: ignore[arg-type]
            strategy_context=inputs["strategy_context"],  # type: ignore[arg-type]
            semantic_context=inputs["semantic_context"],  # type: ignore[arg-type]
            today=inputs["today"],  # type: ignore[arg-type]
            md_root=inputs["md_root"],  # type: ignore[arg-type]
            cached_full_context=inputs["cached_full_context"],  # type: ignore[arg-type]
            include_initial_block=inputs["include_initial_block"],  # type: ignore[arg-type]
            include_consultation_close=inputs["include_consultation_close"],  # type: ignore[arg-type]
            include_cta=inputs["include_cta"],  # type: ignore[arg-type]
            user_message=inputs["user_message"],  # type: ignore[arg-type]
            tone=inputs["tone"],  # type: ignore[arg-type]
            composer_backend=inputs["composer_backend"],  # type: ignore[arg-type]
            semantic_backend=inputs["semantic_backend"],  # type: ignore[arg-type]
        )
    assert caught.value.code == "medical_boundary_result_inconsistent"


def test_topic_incompatibility_propagates_existing_s41_error() -> None:
    composer = RecordingComposerBackend(PAIN_GROUNDED_TEXT)
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs(
        turn_frame=_frame(topic="doctors", topic_confidence=0.95, aspects=["overview"]),
        boundary=_boundary(decision="none", reason_code="boundary_none_confident"),
        composer_backend=composer,
        semantic_backend=semantic,
    )
    with pytest.raises(TargetTurnFrameDispatchError) as caught:
        run_target_offline_boundary_enforced_fullcontext_response(
            inputs["turn_frame"],  # type: ignore[arg-type]
            inputs["boundary"],  # type: ignore[arg-type]
            inputs["bundle"],  # type: ignore[arg-type]
            inputs["doctor_catalog"],  # type: ignore[arg-type]
            inputs["external_index"],  # type: ignore[arg-type]
            inputs["consultation_values"],  # type: ignore[arg-type]
            **_policy_kwargs(allowed_topics=("implantation",)),
            brand_term=inputs["brand_term"],  # type: ignore[arg-type]
            strategy_context=inputs["strategy_context"],  # type: ignore[arg-type]
            semantic_context=inputs["semantic_context"],  # type: ignore[arg-type]
            today=inputs["today"],  # type: ignore[arg-type]
            md_root=inputs["md_root"],  # type: ignore[arg-type]
            cached_full_context=inputs["cached_full_context"],  # type: ignore[arg-type]
            include_initial_block=inputs["include_initial_block"],  # type: ignore[arg-type]
            include_consultation_close=inputs["include_consultation_close"],  # type: ignore[arg-type]
            include_cta=inputs["include_cta"],  # type: ignore[arg-type]
            user_message=inputs["user_message"],  # type: ignore[arg-type]
            tone=inputs["tone"],  # type: ignore[arg-type]
            composer_backend=composer,
            semantic_backend=semantic,
        )
    assert caught.value.code == "dispatch_topic_scope_incompatible"
    assert composer.invocations == []


def test_prebuilt_full_context_shared_without_rebuild_in_s46(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def fail_build(md_root: Path):
        calls.append(md_root)
        raise AssertionError("build_target_cached_full_context must not run inside S46")

    monkeypatch.setattr(
        "core.target_cached_full_context.build_target_cached_full_context",
        fail_build,
    )
    composer = RecordingComposerBackend(PAIN_GROUNDED_TEXT)
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs(
        turn_frame=_frame(),
        boundary=_boundary(
            decision="medical_handoff",
            reason_code="boundary_medical_handoff_confident",
        ),
        composer_backend=composer,
        semantic_backend=semantic,
    )
    run_target_offline_boundary_enforced_fullcontext_response(
        inputs["turn_frame"],  # type: ignore[arg-type]
        inputs["boundary"],  # type: ignore[arg-type]
        inputs["bundle"],  # type: ignore[arg-type]
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["external_index"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        **_policy_kwargs(),
        brand_term=inputs["brand_term"],  # type: ignore[arg-type]
        strategy_context=inputs["strategy_context"],  # type: ignore[arg-type]
        semantic_context=inputs["semantic_context"],  # type: ignore[arg-type]
        today=inputs["today"],  # type: ignore[arg-type]
        md_root=inputs["md_root"],  # type: ignore[arg-type]
        cached_full_context=inputs["cached_full_context"],  # type: ignore[arg-type]
        include_initial_block=inputs["include_initial_block"],  # type: ignore[arg-type]
        include_consultation_close=inputs["include_consultation_close"],  # type: ignore[arg-type]
        include_cta=inputs["include_cta"],  # type: ignore[arg-type]
        user_message=inputs["user_message"],  # type: ignore[arg-type]
        tone=inputs["tone"],  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert calls == []
    assert composer.invocations[0].cached_full_context == DEMO_FULL_CONTEXT.corpus_text
    assert semantic.invocations[0].cached_full_context == DEMO_FULL_CONTEXT.corpus_text
