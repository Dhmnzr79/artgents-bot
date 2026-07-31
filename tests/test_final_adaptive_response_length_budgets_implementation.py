"""Implementation tests for FINAL_ADAPTIVE_RESPONSE_LENGTH_BUDGETS / PERF-5 (Phase 2).

Covers the 30-scenario owner acceptance list: profile selection (all 7 profiles, the
owner's exact simple_faq decision, ambiguity -> standard_information), explicit typed
delivery into Composer (no ContextVar/global), the outline directive, non-mutation of
required facts/numbers/no_public_price/CTA/source identity, fail-open semantics
(over-budget never blocks/retries/reroutes), observability with no PII, and structural
non-invocation on the contacts/service-availability bypass paths. Fakes/recording
backends only -- the centralized `tests/conftest.py` provider-transport guard is
active for every test in this file; nothing here reaches a real network/provider call.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from contracts.target_cached_full_context import TargetCachedFullContext
from contracts.target_response_length_profile import (
    RESPONSE_LENGTH_SOFT_BUDGETS,
    response_length_soft_max,
)
from contracts.target_response_spec import TargetResponseSpec
from core.target_composer_executor import (
    TARGET_COMPOSER_SYSTEM_POLICY,
    TargetComposerInvocation,
    TargetComposerTone,
    execute_target_composer,
)
from core.target_composer_output import composer_test_json
from core.target_composer_request import (
    TargetComposerEvidenceBlock,
    TargetComposerRequest,
)
from core.target_response_followup_materializer import TargetContentFollowup
from core.target_response_followup_policy import TargetResponseFollowupSelection
from core.target_response_policy import (
    broad_family_price_directive_overlay,
    select_target_response_length_profile,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


class RecordingBackend:
    def __init__(self, answer: str = "Короткий ответ.") -> None:
        self.answer = answer
        self.invocations: list[TargetComposerInvocation] = []

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.invocations.append(invocation)
        return composer_test_json(self.answer, primary_content_ref="service_one.md")


def _cached_context() -> TargetCachedFullContext:
    text = (
        "---BEGIN DOC:service_one.md---\n"
        "---\n"
        "id: service_one\n"
        "title: Service\n"
        "---\n\n"
        "# Service\n"
        "Corpus background.\n"
        "---END DOC:service_one.md---"
    )
    return TargetCachedFullContext(
        corpus_text=text,
        document_count=1,
        document_paths=("service_one.md",),
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _content_spec(**updates: object) -> TargetResponseSpec:
    """A content-only (non-price-stage) answer spec -- the shape simple_faq/
    standard_information/marketing_concern selection actually operates on."""
    payload: dict[str, object] = {
        "response_mode": "answer",
        "service_id": "service_one",
        "tone_key": "commercial_warm",
        "allowed_topics": ("implantation",),
        "forbidden_topics": ("diagnosis",),
        "required_fact_ids": ("fact_one",),
        "required_components": ("content",),
        "followup_source": "content",
        "allow_marketing_facts": True,
        "allow_consultation_close": False,
        "allow_cta": True,
    }
    payload.update(updates)
    return TargetResponseSpec.model_validate(payload)


def _clarify_spec() -> TargetResponseSpec:
    return TargetResponseSpec.model_validate(
        {
            "response_mode": "clarify",
            "tone_key": "commercial_warm",
            "allowed_topics": ("implantation",),
            "forbidden_topics": ("diagnosis",),
            "required_components": (),
        }
    )


def _price_stage_spec(stage: str, **updates: object) -> TargetResponseSpec:
    """A scope-aware price-stage spec -- required_components must be exactly
    ("price",) and followup_source/marketing/CTA are stage-gated (see
    contracts/target_response_spec.py's _consistent_scope_and_payload)."""
    payload: dict[str, object] = {
        "response_mode": "answer",
        "service_id": "service_one" if stage in {"concrete_service_price", "scoped_family_price"} else None,
        "tone_key": "commercial_warm",
        "allowed_topics": ("implantation",),
        "forbidden_topics": ("diagnosis",),
        "required_fact_ids": (),
        "required_components": ("price",),
        "followup_source": "price" if stage == "concrete_service_price" else None,
        "allow_marketing_facts": False,
        "allow_consultation_close": False,
        "allow_cta": False,
        "response_stage": stage,
        "scope_price_topic": None if stage == "concrete_service_price" else "implantation",
    }
    payload.update(updates)
    return TargetResponseSpec.model_validate(payload)


_FACT_TEXT = "Гарантия на имплант 5 лет, цена 42000 рублей."


def _request(**updates: object) -> TargetComposerRequest:
    content = TargetComposerEvidenceBlock(
        kind="content",
        ref="content:service_one.md",
        topics=("implantation",),
        fact_ids=(),
        text="Описание услуги.",
        must_preserve_exact=False,
    )
    fact = TargetComposerEvidenceBlock(
        kind="commercial_fact",
        ref="fact:fact_one",
        topics=("implantation",),
        fact_ids=("fact_one",),
        text=_FACT_TEXT,
        must_preserve_exact=True,
    )
    followup = TargetContentFollowup(
        id="details",
        label="Подробнее",
        ref="service_one.md#details",
        source_content_ref="service_one.md",
    )
    values: dict[str, object] = {
        "user_message": "Расскажите об услуге",
        "spec": _content_spec(),
        "evidence_blocks": (content, fact),
        "selected_followups": TargetResponseFollowupSelection(
            source="content",
            content=(followup,),
            price=(),
        ),
        "selected_cta_key": "plan",
    }
    values.update(updates)
    return TargetComposerRequest(**values)  # type: ignore[arg-type]


def _tone() -> TargetComposerTone:
    return TargetComposerTone(
        key="commercial_warm",
        instruction="Отвечай доброжелательно и без давления.",
    )


# ---- 1-8: profile selection ---------------------------------------------------------


def test_1_all_seven_profiles_reachable() -> None:
    assert select_target_response_length_profile(_clarify_spec()) == "clarification_concise"
    assert (
        select_target_response_length_profile(_price_stage_spec("broad_family_price"))
        == "broad_price_overview"
    )
    assert select_target_response_length_profile(_price_stage_spec("scoped_family_price")) == "scoped_price"
    assert select_target_response_length_profile(_price_stage_spec("concrete_service_price")) == "scoped_price"
    assert (
        select_target_response_length_profile(
            _price_stage_spec("concrete_service_price"),
            aspects=("comparison",),
        )
        == "comparison_or_complex"
    )
    assert (
        select_target_response_length_profile(
            _content_spec(allow_marketing_facts=False),
            marketing_scenarios=("pain_fear",),
        )
        == "marketing_concern"
    )
    assert (
        select_target_response_length_profile(
            _content_spec(allow_marketing_facts=False, required_fact_ids=()),
            aspects=("overview",),
            aspects_valid=True,
        )
        == "simple_faq"
    )
    assert (
        select_target_response_length_profile(
            _content_spec(required_components=("content", "doctors"), allow_marketing_facts=False)
        )
        == "standard_information"
    )
    assert set(RESPONSE_LENGTH_SOFT_BUDGETS.keys()) == {
        "clarification_concise",
        "simple_faq",
        "standard_information",
        "marketing_concern",
        "broad_price_overview",
        "scoped_price",
        "comparison_or_complex",
    }


def test_2_simple_faq_matches_owner_decision_exactly() -> None:
    """simple_faq only for: no price stage/aspect, no comparison, no marketing_scenarios,
    no clarification, <=1 required fact, single (content-only) component, AND a genuinely
    proven single valid aspect (the PERF-5 correction's own explicit requirement)."""
    base = _content_spec(allow_marketing_facts=False, required_fact_ids=())
    assert (
        select_target_response_length_profile(base, aspects=("overview",), aspects_valid=True)
        == "simple_faq"
    )

    # any one owner-listed axis present -> must NOT be simple_faq
    assert (
        select_target_response_length_profile(
            base, aspects=("comparison",), aspects_valid=True
        )
        != "simple_faq"
    )
    assert (
        select_target_response_length_profile(
            base, aspects=("overview",), aspects_valid=True, marketing_scenarios=("time",)
        )
        != "simple_faq"
    )
    assert select_target_response_length_profile(_clarify_spec()) != "simple_faq"
    assert (
        select_target_response_length_profile(
            _content_spec(allow_marketing_facts=False, required_fact_ids=("f1", "f2")),
            aspects=("overview",),
            aspects_valid=True,
        )
        != "simple_faq"
    )
    assert (
        select_target_response_length_profile(
            _content_spec(required_components=("content", "doctors"), allow_marketing_facts=False),
            aspects=("overview",),
            aspects_valid=True,
        )
        != "simple_faq"
    )
    assert (
        select_target_response_length_profile(
            _content_spec(allow_marketing_facts=True, required_fact_ids=()),
            aspects=("overview",),
            aspects_valid=True,
        )
        != "simple_faq"
    )
    assert (
        select_target_response_length_profile(_price_stage_spec("concrete_service_price"))
        != "simple_faq"
    )
    # the correction's own new gate: no aspect, multiple aspects, or an invalid aspect
    # signal must never be read as "simple_faq" even when every other axis is clean
    assert select_target_response_length_profile(base) != "simple_faq"
    assert (
        select_target_response_length_profile(base, aspects=("overview", "pain"), aspects_valid=True)
        != "simple_faq"
    )
    assert (
        select_target_response_length_profile(base, aspects=("overview",), aspects_valid=False)
        != "simple_faq"
    )


def test_3_ambiguous_case_falls_back_to_standard_information() -> None:
    assert (
        select_target_response_length_profile(
            _content_spec(required_components=("content", "doctors"), allow_marketing_facts=False)
        )
        == "standard_information"
    )
    assert (
        select_target_response_length_profile(
            _content_spec(allow_marketing_facts=False, required_fact_ids=("f1", "f2"))
        )
        == "standard_information"
    )


def test_4_broad_price_overview() -> None:
    spec = _price_stage_spec("broad_family_price")
    assert select_target_response_length_profile(spec) == "broad_price_overview"


def test_5_scoped_price() -> None:
    spec = _price_stage_spec("scoped_family_price")
    assert select_target_response_length_profile(spec) == "scoped_price"
    spec2 = _price_stage_spec("concrete_service_price")
    assert select_target_response_length_profile(spec2) == "scoped_price"


def test_6_comparison_wins_over_concrete_price() -> None:
    spec = _price_stage_spec("concrete_service_price")
    assert (
        select_target_response_length_profile(spec, aspects=("comparison",))
        == "comparison_or_complex"
    )
    # comparison also fires outside any price stage
    spec2 = _content_spec()
    assert (
        select_target_response_length_profile(spec2, aspects=("comparison",))
        == "comparison_or_complex"
    )


def test_7_marketing_concern() -> None:
    spec = _content_spec(allow_marketing_facts=False)
    assert (
        select_target_response_length_profile(spec, marketing_scenarios=("result_reliability",))
        == "marketing_concern"
    )


def test_8_clarification_concise() -> None:
    assert select_target_response_length_profile(_clarify_spec()) == "clarification_concise"
    assert (
        select_target_response_length_profile(_price_stage_spec("stage_clarify"))
        == "clarification_concise"
    )
    assert (
        select_target_response_length_profile(_content_spec(), needs_clarification=True)
        == "clarification_concise"
    )


# ---- 9-10: explicit typed delivery + outline directive -------------------------------


def test_9_profile_explicitly_reaches_composer_messages() -> None:
    request = _request(response_length_profile="simple_faq")
    backend = RecordingBackend()
    execute_target_composer(request, backend, tone=_tone(), cached_full_context=_cached_context())
    assert len(backend.invocations) == 1
    directives = json.loads(backend.invocations[0].response_directives_json)
    assert directives["response_length_profile"] == "simple_faq"
    assert directives["response_length_soft_max"] == response_length_soft_max("simple_faq")


def test_10_outline_directive_present_in_system_policy() -> None:
    lowered = TARGET_COMPOSER_SYSTEM_POLICY.lower()
    assert "response_length_profile" in lowered
    assert "response_length_soft_max" in lowered
    assert "direct answer" in lowered
    assert "2-4" in TARGET_COMPOSER_SYSTEM_POLICY
    assert "next step" in lowered
    assert "never omit" in lowered or "dropping required content is not" in lowered


# ---- 11-13: required content is never mutated ----------------------------------------


def test_11_required_exact_fact_not_removed() -> None:
    request = _request(
        response_length_profile="clarification_concise",
        user_message="Сколько стоит?",
    )
    backend = RecordingBackend(answer=f"Коротко: {_FACT_TEXT}")
    result = execute_target_composer(request, backend, tone=_tone(), cached_full_context=_cached_context())
    assert _FACT_TEXT in result.text


def test_12_numeric_facts_unchanged() -> None:
    request = _request(response_length_profile="scoped_price")
    long_answer = f"{_FACT_TEXT} " * 20
    backend = RecordingBackend(answer=long_answer)
    result = execute_target_composer(request, backend, tone=_tone(), cached_full_context=_cached_context())
    assert result.text == long_answer.strip()
    assert "42000" in result.text
    assert "5 лет" in result.text


def test_13_no_public_price_preserved_verbatim() -> None:
    approved_text = "Точная стоимость определяется на консультации после осмотра."
    fact = TargetComposerEvidenceBlock(
        kind="commercial_fact",
        ref="fact:price_gap",
        topics=("implantation",),
        fact_ids=("price_gap",),
        text=approved_text,
        must_preserve_exact=True,
    )
    request = _request(
        spec=_content_spec(required_fact_ids=("price_gap",)),
        evidence_blocks=(fact,),
        response_length_profile="clarification_concise",
    )
    backend = RecordingBackend(answer=approved_text)
    result = execute_target_composer(request, backend, tone=_tone(), cached_full_context=_cached_context())
    assert result.text == approved_text


# ---- 14-17: fail-open semantics -------------------------------------------------------


def test_14_over_budget_valid_answer_still_materializes() -> None:
    request = _request(response_length_profile="clarification_concise")  # soft_max=250
    long_answer = "Очень длинный ответ. " * 30  # far over 250 chars
    backend = RecordingBackend(answer=long_answer)
    result = execute_target_composer(request, backend, tone=_tone(), cached_full_context=_cached_context())
    assert result.text == long_answer.strip()
    assert len(result.text) > response_length_soft_max("clarification_concise")


def test_15_over_budget_does_not_retry() -> None:
    request = _request(response_length_profile="clarification_concise")
    backend = RecordingBackend(answer="Очень длинный ответ. " * 30)
    execute_target_composer(request, backend, tone=_tone(), cached_full_context=_cached_context())
    assert len(backend.invocations) == 1


def test_16_call_count_unchanged_regardless_of_budget() -> None:
    for profile in RESPONSE_LENGTH_SOFT_BUDGETS:
        request = _request(response_length_profile=profile)
        backend = RecordingBackend(answer="x" * 5000)
        execute_target_composer(request, backend, tone=_tone(), cached_full_context=_cached_context())
        assert len(backend.invocations) == 1, profile


def test_17_route_and_spec_untouched_by_profile_selection() -> None:
    spec = _price_stage_spec("concrete_service_price")
    before = spec.model_dump()
    select_target_response_length_profile(spec, aspects=("comparison",))
    assert spec.model_dump() == before


# ---- 18-20: provider cap / JSON contract / CTA-source-identity unaffected -------------


def test_18_provider_max_completion_tokens_cap_untouched() -> None:
    source = (_REPO_ROOT / "core" / "target_runtime_llm_backends.py").read_text(encoding="utf-8")
    assert "max_completion_tokens=1024" in source


def test_19_composer_json_contract_not_damaged() -> None:
    assert '{"answer":"<patient-facing text>"' in TARGET_COMPOSER_SYSTEM_POLICY
    request = _request(response_length_profile="standard_information")
    backend = RecordingBackend()
    execute_target_composer(request, backend, tone=_tone(), cached_full_context=_cached_context())
    directives = json.loads(backend.invocations[0].response_directives_json)
    # additive only: every pre-existing key from a request with no profile is still present
    request_no_profile = _request(response_length_profile=None)
    backend2 = RecordingBackend()
    execute_target_composer(request_no_profile, backend2, tone=_tone(), cached_full_context=_cached_context())
    directives_no_profile = json.loads(backend2.invocations[0].response_directives_json)
    assert set(directives_no_profile.keys()) <= set(directives.keys())
    assert set(directives.keys()) - set(directives_no_profile.keys()) == {
        "response_length_profile",
        "response_length_soft_max",
    }


def test_20_buttons_cta_source_identity_unaffected() -> None:
    request = _request(response_length_profile="marketing_concern", selected_cta_key="plan")
    backend = RecordingBackend()
    result = execute_target_composer(request, backend, tone=_tone(), cached_full_context=_cached_context())
    assert result.selected_cta_key == "plan"
    assert result.source_identity is not None
    assert result.source_identity.primary_content_ref == "service_one.md"


# ---- 21-22: structured capability bypass paths remain untouched ----------------------


def test_21_contacts_structured_path_skips_composer() -> None:
    source = (_REPO_ROOT / "core" / "target_runtime_turn.py").read_text(encoding="utf-8")
    assert 'structured_capability.kind == "clinic_contact"' in source
    # both clinic_contact and service_availability branches must stage_skip composer
    # before any materialize_target_composer_request/execute_target_composer call
    contact_branch = source.split('structured_capability.kind == "clinic_contact"')[1]
    contact_branch = contact_branch.split('structured_capability.kind == "service_availability"')[0]
    assert 'turn_timing.stage_skipped("composer"' in contact_branch
    assert "materialize_target_composer_request" not in contact_branch
    assert "execute_target_composer" not in contact_branch


def test_22_service_availability_structured_path_skips_composer() -> None:
    source = (_REPO_ROOT / "core" / "target_runtime_turn.py").read_text(encoding="utf-8")
    assert 'structured_capability.kind == "service_availability"' in source
    availability_branch = source.split('structured_capability.kind == "service_availability"')[1]
    availability_branch = availability_branch.split("boundary_requirement = resolve_target_medical_boundary_requirement")[0]
    assert 'turn_timing.stage_skipped("composer"' in availability_branch
    assert "materialize_target_composer_request" not in availability_branch
    assert "execute_target_composer" not in availability_branch


# ---- 23-24: generic FAQ / consultation-value non-bleed --------------------------------


def test_23_generic_micro_fact_gets_simple_faq() -> None:
    spec = _content_spec(
        required_fact_ids=(),
        allow_marketing_facts=False,
        allow_consultation_close=False,
    )
    assert (
        select_target_response_length_profile(spec, aspects=("overview",), aspects_valid=True)
        == "simple_faq"
    )


def test_24_consultation_value_does_not_bleed_via_length_profile() -> None:
    spec = _content_spec(
        required_fact_ids=(),
        allow_marketing_facts=False,
        allow_consultation_close=False,
    )
    select_target_response_length_profile(spec)
    assert spec.allow_consultation_close is False  # untouched (frozen model; structural guarantee)

    request = _request(spec=spec, response_length_profile="simple_faq")
    backend = RecordingBackend()
    execute_target_composer(request, backend, tone=_tone(), cached_full_context=_cached_context())
    directives = json.loads(backend.invocations[0].response_directives_json)
    assert directives["allow_consultation_close"] is False


# ---- 25: /ask vs /ask/stream parity (no transport-specific state) --------------------


def test_25_profile_selection_is_transport_agnostic_and_deterministic() -> None:
    spec = _price_stage_spec("scoped_family_price")
    first = select_target_response_length_profile(spec)
    second = select_target_response_length_profile(spec)
    assert first == second == "scoped_price"
    source = Path("core/target_response_policy.py").read_text(encoding="utf-8")
    assert "flask" not in source.lower()
    assert "request.ctx" not in source


# ---- 26: observability has no PII -----------------------------------------------------


def test_26_observability_event_has_no_pii(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.target_composer_executor as executor_module

    captured: list[dict] = []

    def _fake_emit_bot_event(logger, event_name, *, status=None, details=None, **overrides):
        captured.append({"event_name": event_name, "details": details})

    monkeypatch.setattr(executor_module, "emit_bot_event", _fake_emit_bot_event)

    request = _request(response_length_profile="standard_information", user_message="секретный вопрос пациента")
    backend = RecordingBackend(answer="Секретный ответ с личными данными пациента.")
    execute_target_composer(request, backend, tone=_tone(), cached_full_context=_cached_context())

    assert len(captured) == 1
    assert captured[0]["event_name"] == "response_length_profile_evaluated"
    details = captured[0]["details"]
    assert set(details.keys()) == {
        "response_length_profile",
        "response_length_soft_max",
        "answer_chars",
        "over_soft_budget",
        "required_content_override",
    }
    for value in details.values():
        assert not isinstance(value, str) or value in RESPONSE_LENGTH_SOFT_BUDGETS
    serialized = json.dumps(details, ensure_ascii=False)
    assert "секретный" not in serialized.lower()
    assert "личными" not in serialized.lower()


# ---- 27: missing profile -> standard (producer), and inert-skip (executor) -----------


def test_27_missing_or_ambiguous_signals_default_to_standard_information() -> None:
    ambiguous = _content_spec(required_components=("content", "doctors"), allow_marketing_facts=False)
    assert select_target_response_length_profile(ambiguous) == "standard_information"


def test_27b_executor_degrades_safely_when_no_profile_attached() -> None:
    """A request built without going through materialize_target_composer_request (and
    therefore never calling the producer) has response_length_profile=None. The executor
    must never crash and must simply omit the length directive -- exactly pre-PERF-5
    behavior -- rather than guessing a profile itself (guessing would be a second,
    uncoordinated producer, forbidden by the governance design)."""
    request = _request(response_length_profile=None)
    backend = RecordingBackend()
    result = execute_target_composer(request, backend, tone=_tone(), cached_full_context=_cached_context())
    assert result.response_length_profile is None
    directives = json.loads(backend.invocations[0].response_directives_json)
    assert "response_length_profile" not in directives
    assert "response_length_soft_max" not in directives


# ---- 28: existing broad-family compact directive coexists ----------------------------


def test_28_broad_family_compact_directive_coexists_with_length_profile() -> None:
    spec = _price_stage_spec("broad_family_price")
    profile = select_target_response_length_profile(spec)
    assert profile == "broad_price_overview"
    offer_block = TargetComposerEvidenceBlock(
        kind="offer",
        ref="offer:offer_one",
        topics=("implantation",),
        fact_ids=(),
        text='{"offer_id":"offer_one"}',
        must_preserve_exact=True,
    )
    request = _request(
        spec=spec,
        response_length_profile=profile,
        evidence_blocks=(offer_block,),
        selected_followups=TargetResponseFollowupSelection(source=None, content=(), price=()),
        selected_cta_key=None,
    )
    backend = RecordingBackend()
    execute_target_composer(request, backend, tone=_tone(), cached_full_context=_cached_context())
    directives = json.loads(backend.invocations[0].response_directives_json)
    overlay = broad_family_price_directive_overlay(spec.response_stage)
    for key, value in overlay.items():
        assert directives[key] == list(value) if isinstance(value, tuple) else directives[key] == value
    assert directives["response_length_profile"] == "broad_price_overview"
    assert directives["response_length_soft_max"] == response_length_soft_max("broad_price_overview")


# ---- 29: no hidden ContextVar/global propagation --------------------------------------


def test_29_no_contextvar_or_module_global_used_for_profile_propagation() -> None:
    for path in (
        "contracts/target_response_length_profile.py",
        "core/target_response_policy.py",
    ):
        source = (_REPO_ROOT / path).read_text(encoding="utf-8")
        assert "ContextVar(" not in source
        assert "import contextvars" not in source

    source = (_REPO_ROOT / "core" / "target_composer_request.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    length_profile_functions = {"_attach_response_length_profile"}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in length_profile_functions:
            # Only inspect the executable statements -- skip the docstring, which
            # legitimately mentions "ContextVar" in prose ("no ContextVar/global").
            statements = node.body[1:] if ast.get_docstring(node) else node.body
            for stmt in statements:
                stmt_source = ast.get_source_segment(source, stmt) or ""
                assert "ContextVar(" not in stmt_source
                assert not stmt_source.lstrip().startswith("global ")


# ---- 30: zero network/provider calls (structural + guard) ----------------------------


def test_30_no_provider_import_in_new_contract_or_producer() -> None:
    for path in (
        "contracts/target_response_length_profile.py",
        "core/target_response_policy.py",
    ):
        source = (_REPO_ROOT / path).read_text(encoding="utf-8")
        for forbidden in ("openai", "chat_completions_create", "llm.py", "import llm"):
            assert forbidden not in source


def test_30b_real_provider_transport_still_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sanity check that the centralized guard (tests/conftest.py) is active in this
    file's process -- attempting the real transport must raise, never silently pass."""
    import llm as llm_module

    class _LiveLikeBackend:
        def generate(self, invocation):
            llm_module.chat_client.chat.completions.create(
                model="does-not-matter",
                messages=[{"role": "user", "content": "x"}],
            )
            return {"answer": "unused", "source_identity": None}

    request = _request(response_length_profile="simple_faq")
    with pytest.raises(Exception):
        execute_target_composer(
            request, _LiveLikeBackend(), tone=_tone(), cached_full_context=_cached_context()
        )
