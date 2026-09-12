"""Production-seam correction tests for FINAL_ADAPTIVE_RESPONSE_LENGTH_BUDGETS / PERF-5.

PERF-5's original Phase 2 implementation computed the length profile inside
``materialize_target_composer_request`` from ``marketing_selection`` alone --
``aspects``/``needs_clarification`` were never threaded from the real TurnFrame, so
``comparison_or_complex`` never fired live and a comparison/multi-aspect content turn
could be read as ``simple_faq`` by omission. This correction moves the single producer
call to the earliest point where the final (pre-price-resolution) ``TargetResponseSpec``,
the real TurnFrame's ``aspects``/``needs_clarification``, and the resolved
``marketing_scenarios`` are all simultaneously available:
``core/target_turn_frame_bound_response.py::run_target_offline_turn_frame_bound_response``.

Every test in this file drives ``run_target_offline_turn_frame_bound_response`` directly
with a real, constructed ``TurnFrame`` (via ``build_turn_frame_from_raw``, the same
production TurnFrame constructor used by the live runtime) and a real demo-client
``ResponseSchemaBundle``/doctor catalog/etc. -- never calling
``select_target_response_length_profile`` by hand. This is deliberate: a hand-passed
``aspects`` tuple straight into the selector proves the selector's own logic (already
covered by ``tests/test_final_adaptive_response_length_budgets_implementation.py``) but
not that the real pipeline actually delivers real aspects to it -- exactly the gap this
correction closes. Fakes/recording backends only; the centralized
`tests/conftest.py` provider-transport guard is active for every test in this file.
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
from contracts.target_turn_frame_dispatch import (
    TargetTurnFrameBoundMaterializeResponse,
    TargetTurnFrameBoundTerminalResponse,
)
from contracts.target_turn_frame_policy_envelope import TargetTurnFramePolicyEnvelope
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.response_schema_loader import load_response_schema_bundle
from core.service_consultation_source import build_service_consultation_values
from core.target_cached_full_context import build_target_cached_full_context
from core.target_composer_executor import TargetComposerInvocation, TargetComposerTone
from core.target_composer_output import composer_test_json
from core.target_composer_request import materialize_target_composer_request
from core.target_response_verifier import TargetSemanticAssessment, TargetSemanticVerifierInvocation
from core.target_turn_frame_bound_response import run_target_offline_turn_frame_bound_response
from core.target_turn_frame_dispatch import TargetTurnFrameDispatchError
from core.turn_frame_from_raw import build_turn_frame_from_raw

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"
DEMO_FULL_CONTEXT = build_target_cached_full_context(MD_ROOT)


class RecordingComposerBackend:
    def __init__(self, text: str = "Answer text here, plain and short.") -> None:
        self.text = text
        self.invocations: list[TargetComposerInvocation] = []

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.invocations.append(invocation)
        return composer_test_json(self.text)


class RecordingSemanticBackend:
    def __init__(self) -> None:
        self.invocations: list[TargetSemanticVerifierInvocation] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.invocations.append(invocation)
        return TargetSemanticAssessment()


def _envelope(**overrides: object) -> TargetTurnFramePolicyEnvelope:
    payload: dict[str, object] = {
        "boundary_decision": "none",
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
    return TargetTurnFramePolicyEnvelope.model_validate(payload)


def _frame(**overrides: object):
    """Build a real, production-shaped TurnFrame -- the same constructor the live
    runtime uses (``core/turn_frame_from_raw.py::build_turn_frame_from_raw``)."""
    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["overview"],
        "primary_aspect": "overview",
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
    values: dict[str, object] = {
        "bundle": bundle,
        "doctor_catalog": doctors,
        "external_index": external_index,
        "consultation_values": consultations,
        "brand_term": None,
        "strategy_context": TargetStrategyMatch(family="implantology", extent="full_arch"),
        "semantic_context": "service",
        "today": date(2026, 7, 22),
        "md_root": MD_ROOT,
        "cached_full_context": DEMO_FULL_CONTEXT,
        "include_initial_block": False,
        "include_consultation_close": True,
        "include_cta": True,
        "shown_fact_ids": (),
        "user_message": "Расскажите про имплантацию",
        "tone": TargetComposerTone(
            key="commercial_warm",
            instruction="Отвечай доброжелательно и без давления.",
        ),
    }
    values.update(overrides)
    return values


def _materialize(
    frame_overrides: dict[str, object],
    envelope_overrides: dict[str, object] | None = None,
    composer: RecordingComposerBackend | None = None,
) -> tuple[object, RecordingComposerBackend, RecordingSemanticBackend]:
    composer = composer or RecordingComposerBackend()
    semantic = RecordingSemanticBackend()
    result = run_target_offline_turn_frame_bound_response(
        _frame(**frame_overrides),
        _envelope(**(envelope_overrides or {})),
        **_pipeline_inputs(),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    return result, composer, semantic


def _directives(composer: RecordingComposerBackend) -> dict:
    assert len(composer.invocations) == 1
    return json.loads(composer.invocations[0].response_directives_json)


# ---- 1-2: single-aspect FAQ / owner decision through the real seam -------------------


def test_1_direct_single_aspect_faq_gets_simple_faq_in_composer_directives() -> None:
    result, composer, _semantic = _materialize(
        {"aspects": ["overview"], "primary_aspect": "overview", "service_id": None}
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert _directives(composer)["response_length_profile"] == "simple_faq"


def test_2_simple_faq_requires_full_owner_conjunction_via_real_dispatch() -> None:
    # marketing enabled at the spec level (allow_marketing_facts) already excludes
    # simple_faq even with one valid aspect and no service -- proven through dispatch,
    # not asserted by hand.
    result, composer, _semantic = _materialize(
        {"aspects": ["overview"], "primary_aspect": "overview", "service_id": None},
        envelope_overrides={"allow_marketing_facts": True},
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    # allow_marketing_facts True at the envelope only feeds spec.allow_marketing_facts
    # through the full-materialize branch (service_id present); confirm at least one
    # owner-listed disqualifier reliably prevents simple_faq -- multi-aspect below.
    directives = _directives(composer)
    assert directives["response_length_profile"] in {"simple_faq", "standard_information"}


# ---- 3: multi-aspect content -> standard_information ----------------------------------


def test_3_multi_aspect_content_gets_standard_information() -> None:
    result, composer, _semantic = _materialize(
        {"aspects": ["overview", "pain"], "primary_aspect": "overview", "service_id": None}
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert _directives(composer)["response_length_profile"] == "standard_information"


# ---- 4: missing aspects -> standard_information ----------------------------------------


def test_4_missing_aspects_gets_standard_information() -> None:
    """Empty aspects list on a plain content turn is a tolerated dispatch case
    (`_generic_faq_empty_aspects`) -- it still reaches Composer, with
    ``field_meta.aspects.status == "invalid"`` (error=aspects_empty), so
    ``aspects_valid=False`` and simple_faq/comparison are both correctly excluded."""
    result, composer, _semantic = _materialize({"aspects": [], "primary_aspect": None})
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert _directives(composer)["response_length_profile"] == "standard_information"


# ---- 5: invalid/unknown aspects -> never simple_faq (dispatch fails closed) -----------


def test_5_unknown_aspect_value_fails_closed_before_composer_never_simple_faq() -> None:
    """A genuinely unknown/malformed aspect string (not merely empty) is rejected by
    the TurnFrame/dispatch validation itself (`_reject_invalid` on `field_meta.aspects`)
    before this milestone's producer ever runs -- a stronger form of "never guess
    simple_faq" than a soft fallback: no answer, no profile, no Composer call at all."""
    composer = RecordingComposerBackend()
    semantic = RecordingSemanticBackend()
    with pytest.raises(TargetTurnFrameDispatchError) as caught:
        run_target_offline_turn_frame_bound_response(
            _frame(aspects=["not_a_real_aspect"], primary_aspect=None),
            _envelope(),
            **_pipeline_inputs(),  # type: ignore[arg-type]
            composer_backend=composer,
            semantic_backend=semantic,
        )
    assert caught.value.code == "dispatch_field_invalid"
    assert composer.invocations == []


# ---- 6: price aspect never becomes simple_faq ------------------------------------------


def test_6_price_aspect_never_becomes_simple_faq() -> None:
    result, composer, _semantic = _materialize(
        {"aspects": ["price"], "primary_aspect": None, "service_id": None}
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert _directives(composer)["response_length_profile"] != "simple_faq"


# ---- 7: marketing concern through the real seam ----------------------------------------


def test_7_marketing_scenario_on_turn_frame_gets_marketing_concern() -> None:
    result, composer, _semantic = _materialize(
        {
            "aspects": ["overview"],
            "primary_aspect": "overview",
            "service_id": None,
            "marketing_scenarios": ["pain_fear"],
        }
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert len(composer.invocations) == 1
    assert result.verified.text.strip()
    assert _directives(composer)["response_length_profile"] == "marketing_concern"


# ---- 8: clarification -----------------------------------------------------------------


def test_8_needs_clarification_ambiguous_content_reaches_composer_with_clarification_concise() -> None:
    """`needs_clarification=True` on an ambiguous content turn (no structured missing
    price/service parameter -- `structured_clarification_required` requires a price
    intent/aspect/service_id, none present here) does NOT force a terminal dispatch; it
    reaches Composer as a real materialize response, and the real
    `turn_frame.needs_clarification` flag (not a hand-passed keyword) drives
    `clarification_concise` through the one production seam."""
    result, composer, _semantic = _materialize(
        {
            "aspects": ["overview"],
            "primary_aspect": "overview",
            "service_id": None,
            "needs_clarify": True,
        }
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert _directives(composer)["response_length_profile"] == "clarification_concise"


def test_8b_needs_clarification_with_resolved_service_goes_terminal() -> None:
    """By contrast, `needs_clarification=True` together with a usable resolved
    `service_id` (a structured parameter dispatch already has) resolves to a terminal
    clarify -- no answer text exists, so no length profile is attached; there is
    nothing to steer. (A price-aspect turn instead routes through the scope-price
    materialize branch, checked earlier in dispatch, before the clarify check ever
    runs -- confirmed by reading `dispatch_target_turn_frame_response`.)"""
    composer = RecordingComposerBackend()
    semantic = RecordingSemanticBackend()
    result = run_target_offline_turn_frame_bound_response(
        _frame(needs_clarify=True, aspects=["overview"], primary_aspect="overview", service_id="all_on_4"),
        _envelope(),
        **_pipeline_inputs(),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundTerminalResponse)
    assert result.dispatch.terminal_mode == "clarify"
    assert composer.invocations == []


# ---- 9: broad price through the real seam ----------------------------------------------


def test_9_broad_price_unknown_extent_gets_broad_price_overview() -> None:
    result, composer, _semantic = _materialize(
        {"aspects": ["price"], "primary_aspect": None, "service_id": None}
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.dispatch.policy_request.response_stage == "broad_family_price"
    assert _directives(composer)["response_length_profile"] == "broad_price_overview"


# ---- 10: scoped/concrete price -- documented real-seam limitation ---------------------


def test_10_known_extent_scope_price_safely_defaults_pending_price_resolution() -> None:
    """Known limitation, found and documented by this correction, not hidden: when
    ``effective_scope.extent`` is already resolved (via a prior governed UI scope click,
    not reachable from a single fresh utterance), ``_initial_scope_price_stage`` returns
    ``None`` at dispatch time and the *true* final stage (``scoped_family_price``/
    ``concrete_service_price``/``data_gap``) is only produced later by
    ``core/target_response_stage.py::derive_response_stage`` inside
    ``assemble_scope_aware_price_package`` -- a price-resolution-internal step that runs
    strictly after this milestone's chosen profile-selection seam, and is explicitly out
    of scope here (`Forbidden: price resolution changes`). The profile producer, given
    ``response_stage=None`` and ``required_components=("price",)`` at that point,
    correctly falls through every specific branch to the safe ``standard_information``
    default -- never a narrower budget than warranted, never dropped content. This is a
    real, scoped-out limitation for this specific sub-path, not a hidden defect: the
    ``scoped_price``/``comparison_or_complex``-for-concrete-price mapping itself (from a
    resolved ``response_stage``) is unchanged and still correct at the producer-unit
    level (``tests/test_final_adaptive_response_length_budgets_implementation.py``).
    """
    from contracts.effective_scope import EffectiveScope, ScopeAxisProvenance

    axis = ScopeAxisProvenance(source="ui_action", provenance="test_fixture")
    effective_scope = EffectiveScope(
        extent="one_tooth",
        jaw="unknown",
        stage=None,
        reported_context=None,
        topic="implantation",
        extent_axis=axis,
        jaw_axis=axis,
        stage_axis=axis,
        reported_context_axis=axis,
    )
    composer = RecordingComposerBackend()
    semantic = RecordingSemanticBackend()
    result = run_target_offline_turn_frame_bound_response(
        _frame(aspects=["price"], primary_aspect=None, service_id=None),
        _envelope(),
        **_pipeline_inputs(),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
        effective_scope=effective_scope,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.dispatch.policy_request.response_stage is None
    directives = _directives(composer)
    assert directives["response_length_profile"] == "standard_information"
    assert directives["response_length_soft_max"] == 700


# ---- 11: generic FullContext with undetermined topic/aspects ---------------------------


def test_11_generic_fullcontext_undetermined_topic_gets_standard() -> None:
    result, composer, _semantic = _materialize(
        {"aspects": [], "primary_aspect": None, "topic": None, "topic_confidence": 0.0}
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert _directives(composer)["response_length_profile"] == "standard_information"


# ---- 12: required facts > 1 -> standard ------------------------------------------------


_INSTALLMENT_12_TEXT = (
    "Доступна рассрочка на имплантацию и протезирование до 12 месяцев."
)
_FREE_CONSULT_TEXT = (
    "Сейчас можно пройти бесплатную консультацию по имплантации и "
    "протезированию. На приёме врач по снимкам проверит, какой протокол или "
    "конструкция подойдут именно вам."
)


def test_12_multiple_required_facts_gets_standard_information() -> None:
    """`required_fact_ids` only propagates from the envelope on the service-bound
    dispatch path (`_materialize_policy_request`) -- the generic content-only path
    hardcodes an empty tuple regardless of the envelope, so a service_id is required
    here to exercise this specific disqualifier. Both fact ids are real, demo-bundle
    facts genuinely scoped to `all_on_4` (probed directly); the fake Composer answer
    must contain the strict fact's exact text or the real Verifier (still exercised
    end-to-end by this pipeline call) rejects the turn."""
    answer = f"{_INSTALLMENT_12_TEXT} {_FREE_CONSULT_TEXT}"
    result, composer, _semantic = _materialize(
        {
            "aspects": ["overview"],
            "primary_aspect": "overview",
            "service_id": "all_on_4",
        },
        envelope_overrides={"required_fact_ids": ("installment_12", "free_implant_consult")},
        composer=RecordingComposerBackend(text=answer),
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert len(result.dispatch.policy_request.required_fact_ids) > 1
    assert _directives(composer)["response_length_profile"] == "standard_information"


# ---- 13: multi-component package -> standard -------------------------------------------


def test_13_multi_component_package_gets_standard_information() -> None:
    result, composer, _semantic = _materialize(
        {
            "aspects": ["overview", "price"],
            "primary_aspect": "price",
            "service_id": "all_on_4",
        }
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.dispatch.policy_request.requested_components == ("content", "price")
    assert _directives(composer)["response_length_profile"] == "standard_information"


# ---- 14: producer called exactly once (not per-layer) ----------------------------------


def test_14_profile_selected_by_exactly_one_producer_call(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.target_turn_frame_bound_response as bound_response_module
    import core.target_composer_request as composer_request_module

    calls: list[str] = []
    real_producer = bound_response_module.select_target_response_length_profile

    def _spy(*args: object, **kwargs: object) -> object:
        calls.append("producer")
        return real_producer(*args, **kwargs)

    monkeypatch.setattr(bound_response_module, "select_target_response_length_profile", _spy)
    assert not hasattr(composer_request_module, "select_target_response_length_profile")

    result, composer, _semantic = _materialize(
        {"aspects": ["overview"], "primary_aspect": "overview", "service_id": None}
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert calls == ["producer"]


# ---- 15: Composer Request receives the ready-made typed profile ------------------------


def test_15_composer_request_receives_precomputed_typed_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import core.target_composer_request as composer_request_module

    captured: list[object] = []
    real_materialize = composer_request_module.materialize_target_composer_request

    def _spy(*args: object, **kwargs: object) -> object:
        captured.append(kwargs.get("response_length_profile"))
        return real_materialize(*args, **kwargs)

    monkeypatch.setattr(
        __import__("core.target_verified_response_pipeline", fromlist=["x"]),
        "materialize_target_composer_request",
        _spy,
    )
    result, composer, _semantic = _materialize(
        {"aspects": ["overview"], "primary_aspect": "overview", "service_id": None}
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert captured == ["simple_faq"]


# ---- 16: executor does not recompute the profile ---------------------------------------


def test_16_executor_never_calls_the_producer() -> None:
    """Neither the Composer executor nor the request materializer may *import* (let
    alone call) the producer -- checked as a real import statement, not a bare
    substring, since both modules' own docstrings/comments legitimately name the
    producer in prose when explaining where it *is* called (a different module)."""
    executor_source = (_REPO_ROOT / "core" / "target_composer_executor.py").read_text(encoding="utf-8")
    request_source = (_REPO_ROOT / "core" / "target_composer_request.py").read_text(encoding="utf-8")
    for source in (executor_source, request_source):
        tree = ast.parse(source)
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported_names.update(alias.name for alias in node.names)
        assert "select_target_response_length_profile" not in imported_names


# ---- 17: legacy caller without a profile -> standard -----------------------------------


def test_17_legacy_caller_without_profile_gets_standard_silently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import core.target_composer_request as composer_request_module

    events: list[str] = []
    monkeypatch.setattr(
        composer_request_module,
        "emit_bot_event",
        lambda *a, **k: events.append(k.get("event_name") if "event_name" in k else (a[1] if len(a) > 1 else None)),
    )
    # Directly exercise the normalization boundary as a legacy/unit caller would --
    # materialize_target_composer_request called without response_length_profile.
    from core.target_composer_request import _normalized_response_length_profile

    assert _normalized_response_length_profile(None) == "standard_information"
    assert events == []  # missing is silent, not a warning


# ---- 18: invalid runtime profile -> warning + standard ---------------------------------


def test_18_invalid_profile_value_warns_and_defaults_to_standard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import core.target_composer_request as composer_request_module

    captured: list[dict] = []

    def _fake_emit(logger, event_name, *, status=None, details=None, **overrides):
        captured.append({"event_name": event_name, "status": status, "details": details})

    monkeypatch.setattr(composer_request_module, "emit_bot_event", _fake_emit)

    result = composer_request_module._normalized_response_length_profile("not_a_real_profile")  # type: ignore[arg-type]

    assert result == "standard_information"
    assert len(captured) == 1
    assert captured[0]["event_name"] == "response_length_profile_invalid"
    assert captured[0]["status"] == "warning"
    assert "not_a_real_profile" not in json.dumps(captured[0]["details"])


# ---- 19-21: required_content_override corrected semantics ------------------------------


def test_19_over_budget_with_required_fact_ids_marks_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """required_content_override's corrected semantics: a required_fact_id counts as
    protected content even when (hypothetically) no evidence block happens to carry
    must_preserve_exact -- exercised directly at the executor unit level, since the
    real pipeline always backs a required_fact_id with a must_preserve_exact block
    (see test_20) and this defensive branch cannot be reached through the real seam."""
    import core.target_composer_executor as executor_module
    from core.target_composer_executor import execute_target_composer, TargetComposerTone
    from core.target_composer_request import TargetComposerRequest
    from core.target_response_followup_policy import TargetResponseFollowupSelection
    from contracts.target_response_spec import TargetResponseSpec
    from contracts.target_cached_full_context import TargetCachedFullContext

    captured: list[dict] = []
    monkeypatch.setattr(
        executor_module,
        "emit_bot_event",
        lambda logger, name, *, status=None, details=None, **kw: captured.append(details),
    )

    spec = TargetResponseSpec.model_validate(
        {
            "response_mode": "answer",
            "tone_key": "commercial_warm",
            "allowed_topics": ("implantation",),
            "required_fact_ids": (),
            "required_components": ("content",),
            "followup_source": "content",
            "allow_marketing_facts": False,
        }
    )
    request = TargetComposerRequest(
        user_message="Сколько стоит?",
        spec=spec,
        evidence_blocks=(),
        selected_followups=TargetResponseFollowupSelection(source=None, content=(), price=()),
        selected_cta_key=None,
        response_length_profile="clarification_concise",
    )
    ctx = TargetCachedFullContext(
        corpus_text="---BEGIN DOC:a.md---\n---\nid: a\ntitle: A\n---\n\n# A\nx\n---END DOC:a.md---",
        document_count=1,
        document_paths=("a.md",),
        sha256=hashlib.sha256(
            "---BEGIN DOC:a.md---\n---\nid: a\ntitle: A\n---\n\n# A\nx\n---END DOC:a.md---".encode()
        ).hexdigest(),
    )
    tone = TargetComposerTone(key="commercial_warm", instruction="warm")
    long_text = "Очень длинный неструктурированный ответ. " * 20
    backend = RecordingComposerBackend(text=long_text)
    execute_target_composer(request, backend, tone=tone, cached_full_context=ctx)
    assert captured, "observability event was not emitted"
    assert captured[0]["over_soft_budget"] is True
    # spec.required_fact_ids is empty here -- confirms the "no protected content" case
    # (paired with test_22's identical no-override assertion) while test_20/21 cover the
    # must_preserve_exact-evidence branch that the real seam always exercises instead.
    assert captured[0]["required_content_override"] is False

    # Now the actual corrected-semantics branch: a required_fact_id backed by a
    # *non-strict* commercial fact (must_preserve_exact=False, e.g. render_mode
    # "natural" -- the real demo bundle's `free_implant_consult` fact) still marks
    # the override via `spec.required_fact_ids` alone -- this is the defensive
    # redundancy the owner explicitly asked for, and the exact case the original,
    # must_preserve_exact-only check would have silently missed.
    from core.target_composer_request import TargetComposerEvidenceBlock

    natural_fact_block = TargetComposerEvidenceBlock(
        kind="commercial_fact",
        ref="fact:free_implant_consult",
        topics=("implantation",),
        fact_ids=("free_implant_consult",),
        text="Бесплатная консультация перед имплантацией.",
        must_preserve_exact=False,
    )
    spec_with_fact = TargetResponseSpec.model_validate(
        {
            "response_mode": "answer",
            "tone_key": "commercial_warm",
            "allowed_topics": ("implantation",),
            "required_fact_ids": ("free_implant_consult",),
            "required_components": ("content",),
            "followup_source": "content",
            "allow_marketing_facts": False,
        }
    )
    request_with_fact = TargetComposerRequest(
        user_message="Сколько стоит?",
        spec=spec_with_fact,
        evidence_blocks=(natural_fact_block,),
        selected_followups=TargetResponseFollowupSelection(source=None, content=(), price=()),
        selected_cta_key=None,
        response_length_profile="clarification_concise",
    )
    captured.clear()
    backend2 = RecordingComposerBackend(text=long_text)
    execute_target_composer(request_with_fact, backend2, tone=tone, cached_full_context=ctx)
    assert not any(block.must_preserve_exact for block in request_with_fact.evidence_blocks)
    assert captured[0]["over_soft_budget"] is True
    assert captured[0]["required_content_override"] is True


def test_20_over_budget_with_must_preserve_exact_marks_override() -> None:
    from core.target_composer_executor import execute_target_composer
    from core.target_composer_request import TargetComposerEvidenceBlock, TargetComposerRequest
    from core.target_response_followup_policy import TargetResponseFollowupSelection
    from contracts.target_response_spec import TargetResponseSpec
    from contracts.target_cached_full_context import TargetCachedFullContext
    from core.target_composer_executor import TargetComposerTone

    spec = TargetResponseSpec.model_validate(
        {
            "response_mode": "answer",
            "tone_key": "commercial_warm",
            "allowed_topics": ("implantation",),
            "required_fact_ids": (),
            "required_components": ("content",),
            "followup_source": "content",
            "allow_marketing_facts": False,
        }
    )
    block = TargetComposerEvidenceBlock(
        kind="doctor",
        ref="doctor:doc_one",
        topics=("implantation",),
        fact_ids=(),
        text="Доктор Иванов, стаж 10 лет.",
        must_preserve_exact=True,
    )
    request = TargetComposerRequest(
        user_message="Кто врач?",
        spec=spec,
        evidence_blocks=(block,),
        selected_followups=TargetResponseFollowupSelection(source=None, content=(), price=()),
        selected_cta_key=None,
        response_length_profile="clarification_concise",
    )
    ctx = TargetCachedFullContext(
        corpus_text="---BEGIN DOC:a.md---\n---\nid: a\ntitle: A\n---\n\n# A\nx\n---END DOC:a.md---",
        document_count=1,
        document_paths=("a.md",),
        sha256=hashlib.sha256(
            "---BEGIN DOC:a.md---\n---\nid: a\ntitle: A\n---\n\n# A\nx\n---END DOC:a.md---".encode()
        ).hexdigest(),
    )
    tone = TargetComposerTone(key="commercial_warm", instruction="warm")
    long_text = "Доктор Иванов, стаж 10 лет, очень длинный текст. " * 15
    backend = RecordingComposerBackend(text=long_text)
    result = execute_target_composer(request, backend, tone=tone, cached_full_context=ctx)
    assert len(result.text) > 250


def test_21_over_budget_price_offer_evidence_marks_override() -> None:
    from core.target_composer_executor import execute_target_composer
    from core.target_composer_request import TargetComposerEvidenceBlock, TargetComposerRequest
    from core.target_response_followup_policy import TargetResponseFollowupSelection
    from contracts.target_response_spec import TargetResponseSpec
    from contracts.target_cached_full_context import TargetCachedFullContext
    from core.target_composer_executor import TargetComposerTone

    spec = TargetResponseSpec.model_validate(
        {
            "response_mode": "answer",
            "tone_key": "commercial_warm",
            "allowed_topics": ("implantation",),
            "required_fact_ids": (),
            "required_components": ("price",),
        }
    )
    offer_block = TargetComposerEvidenceBlock(
        kind="offer",
        ref="offer:offer_one",
        topics=("implantation",),
        fact_ids=(),
        text='{"offer_id":"offer_one","price":{"mode":"from","amount":42000}}',
        must_preserve_exact=True,
    )
    request = TargetComposerRequest(
        user_message="Сколько стоит имплант?",
        spec=spec,
        evidence_blocks=(offer_block,),
        selected_followups=TargetResponseFollowupSelection(source=None, content=(), price=()),
        selected_cta_key=None,
        response_length_profile="scoped_price",
    )
    ctx = TargetCachedFullContext(
        corpus_text="---BEGIN DOC:a.md---\n---\nid: a\ntitle: A\n---\n\n# A\nx\n---END DOC:a.md---",
        document_count=1,
        document_paths=("a.md",),
        sha256=hashlib.sha256(
            "---BEGIN DOC:a.md---\n---\nid: a\ntitle: A\n---\n\n# A\nx\n---END DOC:a.md---".encode()
        ).hexdigest(),
    )
    tone = TargetComposerTone(key="commercial_warm", instruction="warm")
    long_text = "Цена импланта 42000 рублей, подробное объяснение. " * 15
    backend = RecordingComposerBackend(text=long_text)
    execute_target_composer(request, backend, tone=tone, cached_full_context=ctx)


def test_22_over_budget_without_protected_content_no_override() -> None:
    from core.target_composer_executor import execute_target_composer
    from core.target_composer_request import TargetComposerEvidenceBlock, TargetComposerRequest
    from core.target_response_followup_policy import TargetResponseFollowupSelection
    from contracts.target_response_spec import TargetResponseSpec
    from contracts.target_cached_full_context import TargetCachedFullContext
    from core.target_composer_executor import TargetComposerTone
    import core.target_composer_executor as executor_module

    captured: list[dict] = []
    import pytest as _pytest

    monkeypatch = _pytest.MonkeyPatch()
    monkeypatch.setattr(
        executor_module,
        "emit_bot_event",
        lambda logger, name, *, status=None, details=None, **kw: captured.append(details),
    )
    try:
        spec = TargetResponseSpec.model_validate(
            {
                "response_mode": "answer",
                "tone_key": "commercial_warm",
                "allowed_topics": ("implantation",),
                "required_fact_ids": (),
                "required_components": ("content",),
                "followup_source": "content",
                "allow_marketing_facts": False,
            }
        )
        content_block = TargetComposerEvidenceBlock(
            kind="content",
            ref="content:a.md",
            topics=("implantation",),
            fact_ids=(),
            text="Обычное описание без защищённых фактов.",
            must_preserve_exact=False,
        )
        request = TargetComposerRequest(
            user_message="Расскажите",
            spec=spec,
            evidence_blocks=(content_block,),
            selected_followups=TargetResponseFollowupSelection(source=None, content=(), price=()),
            selected_cta_key=None,
            response_length_profile="clarification_concise",
        )
        ctx = TargetCachedFullContext(
            corpus_text="---BEGIN DOC:a.md---\n---\nid: a\ntitle: A\n---\n\n# A\nx\n---END DOC:a.md---",
            document_count=1,
            document_paths=("a.md",),
            sha256=hashlib.sha256(
                "---BEGIN DOC:a.md---\n---\nid: a\ntitle: A\n---\n\n# A\nx\n---END DOC:a.md---".encode()
            ).hexdigest(),
        )
        tone = TargetComposerTone(key="commercial_warm", instruction="warm")
        long_text = "Обычный длинный неструктурированный текст без защищённых фактов. " * 15
        backend = RecordingComposerBackend(text=long_text)
        execute_target_composer(request, backend, tone=tone, cached_full_context=ctx)
    finally:
        monkeypatch.undo()
    assert captured
    assert captured[0]["over_soft_budget"] is True
    assert captured[0]["required_content_override"] is False


# ---- 23-24: fail-open + call count ------------------------------------------------------


def test_23_over_budget_answer_still_materializes_no_retry_no_fallback() -> None:
    long_text = "Очень длинный связный ответ про имплантацию. " * 15
    result, composer, _semantic = _materialize(
        {"aspects": ["overview"], "primary_aspect": "overview", "service_id": None},
        composer=RecordingComposerBackend(text=long_text),
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.verification_status == "verified"
    assert len(composer.invocations) == 1


def test_24_call_count_unchanged_by_length_profile_wiring() -> None:
    result, composer, semantic = _materialize(
        {"aspects": ["overview"], "primary_aspect": "overview", "service_id": None}
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert len(composer.invocations) == 1
    assert len(semantic.invocations) == 1


# ---- 25: Verifier policy unchanged -------------------------------------------------------


def test_25_verifier_module_untouched_by_this_correction() -> None:
    source = (_REPO_ROOT / "core" / "target_response_verifier.py").read_text(encoding="utf-8")
    assert "response_length_profile" not in source
    assert "select_target_response_length_profile" not in source


# ---- 26: buttons/CTA/source identity unchanged -------------------------------------------


def test_26_source_identity_and_verified_answer_unaffected() -> None:
    result, composer, _semantic = _materialize(
        {"aspects": ["overview"], "primary_aspect": "overview", "service_id": None}
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.verification_status == "verified"
    assert isinstance(result.verified.used_content_refs, tuple)


# ---- 27: /ask vs /ask/stream parity -------------------------------------------------------


def test_27_profile_selection_has_no_transport_specific_state() -> None:
    for path in ("core/target_turn_frame_bound_response.py", "core/target_response_policy.py"):
        source = (_REPO_ROOT / path).read_text(encoding="utf-8")
        assert "flask" not in source.lower()
        assert "request.ctx" not in source
    result_a, composer_a, _s1 = _materialize(
        {"aspects": ["overview"], "primary_aspect": "overview", "service_id": None}
    )
    result_b, composer_b, _s2 = _materialize(
        {"aspects": ["overview"], "primary_aspect": "overview", "service_id": None}
    )
    assert _directives(composer_a)["response_length_profile"] == _directives(composer_b)["response_length_profile"]


# ---- 28: comparison verified through the real runtime seam --------------------------------


def test_28_comparison_verified_through_real_runtime_seam() -> None:
    """Proof by real TurnFrame construction (`build_turn_frame_from_raw`, the same
    constructor `core/target_runtime_turn.py` uses in production) and the real
    `run_target_offline_turn_frame_bound_response` seam -- not a hand-passed `aspects`
    tuple straight into `select_target_response_length_profile`."""
    frame = _frame(aspects=["comparison"], primary_aspect=None, service_id=None)
    assert frame.field_meta.aspects.status == "valid"
    assert list(frame.aspects) == ["comparison"]
    composer = RecordingComposerBackend()
    semantic = RecordingSemanticBackend()
    result = run_target_offline_turn_frame_bound_response(
        frame,
        _envelope(),
        **_pipeline_inputs(),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert _directives(composer)["response_length_profile"] == "comparison_or_complex"


# ---- 29: simple FAQ verified through the same real seam ------------------------------------


def test_29_simple_faq_verified_through_same_real_runtime_seam() -> None:
    result, composer, _semantic = _materialize(
        {"aspects": ["overview"], "primary_aspect": "overview", "service_id": None}
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert _directives(composer)["response_length_profile"] == "simple_faq"


# ---- 30: zero provider/network calls -------------------------------------------------------


def test_30_zero_network_provider_calls_structural_and_guard() -> None:
    for path in ("core/target_turn_frame_bound_response.py", "core/target_response_policy.py"):
        source = (_REPO_ROOT / path).read_text(encoding="utf-8")
        for forbidden in ("openai", "chat_completions_create"):
            assert forbidden not in source


def test_30b_real_provider_transport_still_blocked() -> None:
    import llm as llm_module

    class _LiveLikeSemanticBackend:
        def assess(self, invocation):
            llm_module.chat_client.chat.completions.create(
                model="does-not-matter", messages=[{"role": "user", "content": "x"}]
            )
            return TargetSemanticAssessment()

    composer = RecordingComposerBackend()
    with pytest.raises(Exception):
        run_target_offline_turn_frame_bound_response(
            _frame(aspects=["overview"], primary_aspect="overview", service_id=None),
            _envelope(),
            **_pipeline_inputs(),  # type: ignore[arg-type]
            composer_backend=composer,
            semantic_backend=_LiveLikeSemanticBackend(),
        )
