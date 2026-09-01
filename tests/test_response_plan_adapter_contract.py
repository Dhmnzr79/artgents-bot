from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts.response_plan import RouteModePair, SessionKey
from contracts.response_plan_adapter import (
    ADAPTER_ERROR_CODES,
    ResponsePlanAdapterComposerRouteAuthority,
    ResponsePlanAdapterConditionAuthority,
    ResponsePlanAdapterDeterministicRouteAuthority,
    ResponsePlanAdapterError,
    ResponsePlanAdapterMaterialAuthority,
    ResponsePlanAdapterSessionState,
    ResponsePlanAdapterTerminalAuthority,
    adapt_composer_json_to_decision,
    assert_not_legacy_composer_output,
    coerce_material_bound_package,
    material_bound_package_invalid_reason,
)
from tests.test_response_plan_composer_contract import (
    _composer_decision_authority_from_plan,
    _composer_result_from_adapted,
    _composer_plan,
    _json,
)


def test_adapter_error_codes_closed_set() -> None:
    assert len(ADAPTER_ERROR_CODES) == 19
    with pytest.raises(ResponsePlanAdapterError) as exc:
        raise ResponsePlanAdapterError("adapter_client_mismatch")
    assert exc.value.code == "adapter_client_mismatch"


def test_adapter_error_rejects_unknown_code() -> None:
    with pytest.raises(ValueError, match="adapter_error_code_invalid"):
        ResponsePlanAdapterError("not_a_real_code")  # type: ignore[arg-type]


def _valid_structural_bound_package():
    from contracts.target_response_spec import TargetResponseSpec
    from core.target_offline_response_assembly import TargetOfflineResponseMaterials
    from core.target_marketing_selector import TargetMarketingSelection
    from core.target_response_followup_policy import TargetResponseFollowupSelection
    from core.target_response_materialization_plan import build_target_response_materialization_plan

    spec = TargetResponseSpec(
        response_mode="answer",
        service_id="all_on_4",
        tone_key="commercial_warm",
        allowed_topics=("implantation",),
        required_components=("content",),
    )
    materials = TargetOfflineResponseMaterials(
        service_id="all_on_4",
        service=None,
        selected_brand_id=None,
        brand=None,
        matched_rule_id=None,
        max_options=3,
        offers=(),
        doctors=(),
        selected_content_ref="content.md",
        marketing_selection=TargetMarketingSelection(
            applied_scenarios=(),
            selected_refs=(),
            amplifier_refs=(),
            cta_key="book_consultation",
        ),
        commercial_facts=(),
        external_source_refs=(),
        consultation_close=None,
        marketing_slots_used=0,
        amplifier_slots_used=0,
    )
    plan = build_target_response_materialization_plan(
        materials,
        required_components=spec.required_components,
    )
    return coerce_material_bound_package(
        type(
            "BoundPackageFixture",
            (),
            {
                "spec": spec,
                "package": type(
                    "PackageFixture",
                    (),
                    {
                        "materials": materials,
                        "plan": plan,
                        "selected_followups": TargetResponseFollowupSelection(
                            source=None,
                            content=(),
                            price=(),
                        ),
                        "navigation_followups": (),
                    },
                )(),
                "selected_cta_key": "book_consultation",
            },
        )()
    )


def test_material_authority_rejects_plain_object() -> None:
    with pytest.raises(ValidationError, match="bound_package_shape_invalid"):
        ResponsePlanAdapterMaterialAuthority(
            source_client_id="demo",
            bound_package=object(),
        )


def test_material_authority_is_frozen_and_extra_forbid() -> None:
    authority = ResponsePlanAdapterMaterialAuthority(
        source_client_id="demo",
        bound_package=_valid_structural_bound_package(),
    )
    with pytest.raises(ValidationError):
        authority.source_client_id = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ResponsePlanAdapterMaterialAuthority(source_client_id="demo", bound_package=_valid_structural_bound_package(), extra=True)  # type: ignore[call-arg]


def test_material_bound_package_rejects_missing_spec() -> None:
    package = type("PackageFixture", (), {"materials": object(), "plan": object(), "selected_followups": object(), "navigation_followups": ()})()
    invalid = type("BoundFixture", (), {"spec": None, "package": package, "selected_cta_key": None})()
    assert material_bound_package_invalid_reason(invalid) == "missing_spec"


def test_material_bound_package_rejects_missing_materials() -> None:
    package = type(
        "PackageFixture",
        (),
        {"materials": None, "plan": object(), "selected_followups": object(), "navigation_followups": ()},
    )()
    invalid = type("BoundFixture", (), {"spec": object(), "package": package, "selected_cta_key": None})()
    assert material_bound_package_invalid_reason(invalid) == "missing_materials"


def test_material_bound_package_rejects_missing_plan() -> None:
    package = type(
        "PackageFixture",
        (),
        {"materials": object(), "plan": None, "selected_followups": object(), "navigation_followups": ()},
    )()
    invalid = type("BoundFixture", (), {"spec": object(), "package": package, "selected_cta_key": None})()
    assert material_bound_package_invalid_reason(invalid) == "missing_plan"


def test_material_bound_package_rejects_missing_selected_followups() -> None:
    package = type(
        "PackageFixture",
        (),
        {"materials": object(), "plan": object(), "selected_followups": None, "navigation_followups": ()},
    )()
    invalid = type("BoundFixture", (), {"spec": object(), "package": package, "selected_cta_key": None})()
    assert material_bound_package_invalid_reason(invalid) == "missing_selected_followups"


def test_material_bound_package_rejects_invalid_selected_cta_key() -> None:
    package = type(
        "PackageFixture",
        (),
        {"materials": object(), "plan": object(), "selected_followups": object(), "navigation_followups": ()},
    )()
    invalid = type("BoundFixture", (), {"spec": object(), "package": package, "selected_cta_key": 1})()
    assert material_bound_package_invalid_reason(invalid) == "selected_cta_key_invalid_type"


def test_material_bound_package_accepts_valid_structural_package() -> None:
    bound = _valid_structural_bound_package()
    assert bound.spec is not None
    assert bound.package.materials is not None
    assert bound.package.plan is not None
    assert bound.package.selected_followups is not None


def test_build_pre_composer_plan_accepts_valid_material_package() -> None:
    from contracts.response_plan import CanonicalContactCandidate, SessionKey
    from contracts.response_plan_adapter import (
        ResponsePlanAdapterComposerRouteAuthority,
        ResponsePlanAdapterSources,
        ResponsePlanAdapterTerminalAuthority,
    )
    from core.response_plan_production_adapter import build_pre_composer_plan
    from core.turn_frame_from_raw import build_turn_frame_from_raw

    bound = _valid_structural_bound_package()
    terminal_authorities = (
        ResponsePlanAdapterTerminalAuthority(
            source_client_id="demo",
            route="ANSWER",
            mode="contacts",
            authority="contacts",
            display_text="Контакты demo",
            canonical_contact=CanonicalContactCandidate(source_client_id="demo", phone="+7 (495) 000-00-00"),
        ),
        ResponsePlanAdapterTerminalAuthority(
            source_client_id="demo",
            route="ADMIN",
            mode="standard",
            authority="governed_ui",
            display_text="ADMIN standard",
            canonical_contact=CanonicalContactCandidate(source_client_id="demo", phone="+7 (495) 000-00-00"),
        ),
        ResponsePlanAdapterTerminalAuthority(
            source_client_id="demo",
            route="ADMIN",
            mode="medical_terminal",
            authority="deterministic_policy_terminal",
            display_text="ADMIN medical",
            canonical_contact=CanonicalContactCandidate(source_client_id="demo", phone="+7 (495) 000-00-00"),
        ),
    )
    sources = ResponsePlanAdapterSources(
        session_key=SessionKey(client_id="demo", sid="s1"),
        context_strategy="full_context",
        turn_frame=build_turn_frame_from_raw(
            {
                "route": "content",
                "topic": "implantation",
                "topic_confidence": 0.9,
                "aspects": ["overview"],
                "primary_aspect": "overview",
                "service_id": "all_on_4",
            },
            allowed_topics=frozenset({"implantation"}),
            allowed_service_ids=frozenset({"all_on_4"}),
        ),
        material_authority=ResponsePlanAdapterMaterialAuthority(
            source_client_id="demo",
            bound_package=bound,
        ),
        allowed_topic_ids=("implantation",),
        route_authority=ResponsePlanAdapterComposerRouteAuthority(),
        terminal_authorities=terminal_authorities,
    )
    plan = build_pre_composer_plan(sources)
    assert plan.response_scope == "service"
    assert plan.selected_service_id == "all_on_4"


def test_session_state_model_is_frozen_and_extra_forbid() -> None:
    state = ResponsePlanAdapterSessionState(last_service_id="all_on_4")
    with pytest.raises(ValidationError):
        state.last_service_id = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ResponsePlanAdapterSessionState(last_service_id="all_on_4", unknown=True)  # type: ignore[call-arg]


def test_route_authority_rejects_invalid_pair() -> None:
    with pytest.raises(ValidationError):
        ResponsePlanAdapterDeterministicRouteAuthority(route="ANSWER", mode="medical_terminal")


def test_composer_route_authority_has_no_preselected_pair() -> None:
    authority = ResponsePlanAdapterComposerRouteAuthority()
    assert authority.kind == "composer_selected"
    assert not hasattr(authority, "route")
    assert not hasattr(authority, "mode")


def test_deterministic_route_authority_requires_pair() -> None:
    authority = ResponsePlanAdapterDeterministicRouteAuthority(route="ANSWER", mode="contacts")
    assert authority.kind == "deterministic_bypass"
    assert authority.route == "ANSWER"
    assert authority.mode == "contacts"


def test_terminal_authority_rejects_clarify() -> None:
    with pytest.raises(ValidationError):
        ResponsePlanAdapterTerminalAuthority(
            source_client_id="demo",
            route="CLARIFY",
            mode="standard",
            authority="governed_ui",
            display_text="text",
        )


def test_adapter_json_delegation_admin_invariants() -> None:
    from tests.test_response_plan_contract import composer_route_authority, price_single
    from contracts.response_plan import PreComposerPlan

    plan = PreComposerPlan(
        session_key=SessionKey(client_id="demo", sid="s1"),
        context_strategy="full_context",
        route_authority=composer_route_authority(),
        response_scope="clinic",
        price_plan=price_single(),
    )
    authority = _composer_decision_authority_from_plan(plan)
    result = adapt_composer_json_to_decision(
        _json(route="ADMIN", mode="standard", patient_text=None),
        authority,
    )
    assert result.decision.patient_text is None
    assert not hasattr(result, "composer_result")
    with pytest.raises(ResponsePlanAdapterError) as exc:
        adapt_composer_json_to_decision(
            _json(route="ADMIN", mode="standard", patient_text="nope"),
            authority,
        )
    assert exc.value.code == "adapter_composer_envelope_invalid"


def test_adapter_json_allows_contacts_mode() -> None:
    from tests.test_response_plan_contract import composer_route_authority, price_single
    from contracts.response_plan import PreComposerPlan

    plan = PreComposerPlan(
        session_key=SessionKey(client_id="demo", sid="s1"),
        context_strategy="full_context",
        route_authority=composer_route_authority(),
        response_scope="clinic",
        price_plan=price_single(),
    )
    authority = _composer_decision_authority_from_plan(plan)
    result = adapt_composer_json_to_decision(
        _json(route="ANSWER", mode="contacts", patient_text=None),
        authority,
    )
    assert result.decision.route == "ANSWER"
    assert result.decision.mode == "contacts"
    assert result.decision.patient_text is None


def test_legacy_unverified_composer_output_rejected() -> None:
    class TargetUnverifiedComposedResponse:
        pass

    legacy = TargetUnverifiedComposedResponse()
    with pytest.raises(ResponsePlanAdapterError) as exc:
        assert_not_legacy_composer_output(legacy)
    assert exc.value.code == "adapter_composer_contract_incompatible"


def test_legacy_verified_composer_output_rejected() -> None:
    class TargetVerifiedComposedResponse:
        pass

    legacy = TargetVerifiedComposedResponse()
    with pytest.raises(ResponsePlanAdapterError) as exc:
        assert_not_legacy_composer_output(legacy)
    assert exc.value.code == "adapter_composer_contract_incompatible"


def test_legacy_direct_fact_ids_envelope_rejected() -> None:
    with pytest.raises(ResponsePlanAdapterError) as exc:
        assert_not_legacy_composer_output({"direct_fact_ids": ["installment_12"], "text": "x"})
    assert exc.value.code == "adapter_composer_contract_incompatible"


def test_adapter_modules_have_no_forbidden_imports() -> None:
    repo = Path(__file__).resolve().parents[1]
    modules = (
        repo / "contracts" / "response_plan_adapter.py",
        repo / "core" / "response_plan_production_adapter.py",
    )
    forbidden = {"app", "session", "flask", "one_call_presentation_pass", "re"}
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert imported.isdisjoint(forbidden), module


def test_adapter_not_imported_by_production_runtime() -> None:
    repo = Path(__file__).resolve().parents[1]
    forbidden_snippets = (
        "response_plan_production_adapter",
        "response_plan_adapter",
    )
    runtime_roots = (repo / "app.py", repo / "core" / "sales_one_plus_turn.py")
    for path in runtime_roots:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        assert not any(snippet in text for snippet in forbidden_snippets), path


def test_adapter_json_maps_parser_error_without_masking(monkeypatch) -> None:
    from contracts.response_plan import PreComposerPlan
    from contracts.response_plan_composer import ComposerParserError
    from tests.test_response_plan_contract import composer_route_authority, price_single

    plan = PreComposerPlan(
        session_key=SessionKey(client_id="demo", sid="s1"),
        context_strategy="full_context",
        route_authority=composer_route_authority(),
        response_scope="clinic",
        price_plan=price_single(),
    )

    authority = _composer_decision_authority_from_plan(plan)

    def _boom(_raw: str):
        raise ComposerParserError("json_invalid", "boom")

    monkeypatch.setattr("contracts.response_plan_adapter.parse_response_plan_composer_json", _boom)
    with pytest.raises(ResponsePlanAdapterError) as exc:
        adapt_composer_json_to_decision("{}", authority)
    assert exc.value.code == "adapter_composer_envelope_invalid"


def test_adapter_json_maps_plan_aware_error_without_masking(monkeypatch) -> None:
    from contracts.response_plan import PreComposerPlan
    from contracts.response_plan_composer import ComposerAdapterError, ComposerDecision, ParsedComposerEnvelope
    from tests.test_response_plan_contract import composer_route_authority, price_single

    plan = PreComposerPlan(
        session_key=SessionKey(client_id="demo", sid="s1"),
        context_strategy="full_context",
        route_authority=composer_route_authority(),
        response_scope="clinic",
        price_plan=price_single(),
    )
    authority = _composer_decision_authority_from_plan(plan)
    parsed = ParsedComposerEnvelope(
        envelope=ComposerDecision(
            route="ANSWER",
            mode="standard",
            patient_text="x",
            service_reference_kind="none",
            topic_id=None,
            explicit_service_id=None,
            requested_aspect_ids=(),
            patient_situation=__import__(
                "contracts.response_plan_composer", fromlist=["ComposerPatientSituation"]
            ).ComposerPatientSituation(
                extent="unknown",
                jaw="unknown",
                stage="unknown",
                modifiers=(),
            ),
            requested_fact_ids=(),
            source_identity=None,
        ),
        warnings=(),
    )

    def _parse(_raw: str):
        return parsed

    def _adapt(_parsed, _authority):
        raise ComposerAdapterError("route_mode_not_allowed", "pair")

    monkeypatch.setattr("contracts.response_plan_adapter.parse_response_plan_composer_json", _parse)
    monkeypatch.setattr("contracts.response_plan_adapter.adapt_composer_envelope_to_decision", _adapt)
    with pytest.raises(ResponsePlanAdapterError) as exc:
        adapt_composer_json_to_decision("{}", authority)
    assert exc.value.code == "adapter_composer_route_mismatch"


def test_adapter_json_does_not_mask_unexpected_parser_runtime_error(monkeypatch) -> None:
    from contracts.response_plan import PreComposerPlan
    from tests.test_response_plan_contract import composer_route_authority, price_single

    plan = PreComposerPlan(
        session_key=SessionKey(client_id="demo", sid="s1"),
        context_strategy="full_context",
        route_authority=composer_route_authority(),
        response_scope="clinic",
        price_plan=price_single(),
    )

    authority = _composer_decision_authority_from_plan(plan)

    def _boom(_raw: str):
        raise RuntimeError("unexpected parser bug")

    monkeypatch.setattr("contracts.response_plan_adapter.parse_response_plan_composer_json", _boom)
    with pytest.raises(RuntimeError, match="unexpected parser bug"):
        adapt_composer_json_to_decision("{}", authority)


def test_adapter_json_does_not_mask_unexpected_adapter_runtime_error(monkeypatch) -> None:
    from contracts.response_plan import PreComposerPlan
    from contracts.response_plan_composer import ComposerDecision, ComposerPatientSituation, ParsedComposerEnvelope
    from tests.test_response_plan_contract import composer_route_authority, price_single

    plan = PreComposerPlan(
        session_key=SessionKey(client_id="demo", sid="s1"),
        context_strategy="full_context",
        route_authority=composer_route_authority(),
        response_scope="clinic",
        price_plan=price_single(),
    )
    authority = _composer_decision_authority_from_plan(plan)
    parsed = ParsedComposerEnvelope(
        envelope=ComposerDecision(
            route="ANSWER",
            mode="standard",
            patient_text="x",
            service_reference_kind="none",
            topic_id=None,
            explicit_service_id=None,
            requested_aspect_ids=(),
            patient_situation=ComposerPatientSituation(
                extent="unknown",
                jaw="unknown",
                stage="unknown",
                modifiers=(),
            ),
            requested_fact_ids=(),
            source_identity=None,
        ),
        warnings=(),
    )

    def _parse(_raw: str):
        return parsed

    def _boom(_parsed, _authority):
        raise RuntimeError("unexpected adapter bug")

    monkeypatch.setattr("contracts.response_plan_adapter.parse_response_plan_composer_json", _parse)
    monkeypatch.setattr("contracts.response_plan_adapter.adapt_composer_envelope_to_decision", _boom)
    with pytest.raises(RuntimeError, match="unexpected adapter bug"):
        adapt_composer_json_to_decision("{}", authority)


def test_production_modules_do_not_import_plan_derived_composer_bridge() -> None:
    repo = Path(__file__).resolve().parents[1]
    modules = (
        repo / "core" / "response_plan_production_adapter.py",
        repo / "contracts" / "response_plan_adapter.py",
    )
    forbidden = {
        "composer_decision_authority_from_pre_composer_plan",
        "build_composer_policy_sidecar_from_plan",
        "adapt_composer_json_to_plan",
        "adapt_parsed_composer_envelope_to_plan",
        "composer_decision_authority_from_plan",
    }
    for module in modules:
        text = module.read_text(encoding="utf-8")
        for symbol in forbidden:
            assert symbol not in text, (module, symbol)


def test_adapted_decision_has_no_composer_result_field() -> None:
    from contracts.response_plan import PreComposerPlan
    from contracts.response_plan_composer import adapt_composer_json_to_decision
    from tests.test_response_plan_contract import composer_route_authority, price_single

    plan = PreComposerPlan(
        session_key=SessionKey(client_id="demo", sid="s1"),
        context_strategy="full_context",
        route_authority=composer_route_authority(),
        response_scope="clinic",
        price_plan=price_single(),
    )
    adapted = adapt_composer_json_to_decision(_json(), _composer_decision_authority_from_plan(plan))
    assert not hasattr(adapted, "composer_result")
    assert adapted.decision.patient_text == "Ответ пациенту."


def test_unknown_topic_fail_open_preserves_patient_text() -> None:
    from contracts.response_plan import PreComposerPlan
    from contracts.response_plan_composer import adapt_composer_json_to_decision
    from tests.test_response_plan_contract import composer_route_authority, price_single

    plan = PreComposerPlan(
        session_key=SessionKey(client_id="demo", sid="s1"),
        context_strategy="full_context",
        route_authority=composer_route_authority(),
        response_scope="clinic",
        price_plan=price_single(),
    )
    patient_text = "Сохранить topic fail-open."
    adapted = adapt_composer_json_to_decision(
        _json(patient_text=patient_text, topic_id="unknown_topic"),
        _composer_decision_authority_from_plan(plan),
    )
    assert adapted.decision.patient_text == patient_text
    assert adapted.decision.topic_id is None
    assert any(item.code == "topic_id_not_allowed" for item in adapted.diagnostics)


def test_unknown_explicit_service_fail_open() -> None:
    from contracts.response_plan import PreComposerPlan
    from contracts.response_plan_composer import adapt_composer_json_to_decision
    from tests.test_response_plan_contract import composer_route_authority, price_single

    plan = PreComposerPlan(
        session_key=SessionKey(client_id="demo", sid="s1"),
        context_strategy="full_context",
        route_authority=composer_route_authority(),
        response_scope="topic",
        selected_topic_id="implantation",
        price_plan=price_single(),
    )
    adapted = adapt_composer_json_to_decision(
        _json(
            patient_text="Текст.",
            topic_id="implantation",
            service_reference_kind="explicit_current",
            explicit_service_id="missing_service",
        ),
        _composer_decision_authority_from_plan(plan),
    )
    assert adapted.decision.patient_text == "Текст."
    assert adapted.decision.topic_id == "implantation"
    assert adapted.decision.service_reference_kind == "none"
    assert adapted.decision.explicit_service_id is None
    assert any(item.code == "service_id_not_allowed" for item in adapted.diagnostics)


def test_stale_active_session_fail_open() -> None:
    from contracts.response_plan import PreComposerPlan
    from contracts.response_plan_composer import ComposerDecisionAuthority, adapt_composer_json_to_decision
    from contracts.response_plan import PricePlan
    from tests.test_response_plan_contract import composer_route_authority

    authority = _composer_decision_authority_from_plan(
        PreComposerPlan(
            session_key=SessionKey(client_id="demo", sid="s1"),
            context_strategy="full_context",
            route_authority=composer_route_authority(),
            response_scope="clinic",
            price_plan=PricePlan(kind="none"),
        )
    )
    authority = ComposerDecisionAuthority(
        source_client_id=authority.source_client_id,
        allowed_route_modes=authority.allowed_route_modes,
        allowed_topic_ids=authority.allowed_topic_ids,
        service_descriptors=authority.service_descriptors,
        active_session_service_id=None,
        context_strategy=authority.context_strategy,
        history_turn_count=authority.history_turn_count,
        allowed_aspect_ids=authority.allowed_aspect_ids,
        requestable_facts=authority.requestable_facts,
    )
    adapted = adapt_composer_json_to_decision(
        _json(patient_text="Продолжение.", service_reference_kind="active_session"),
        authority,
    )
    assert adapted.decision.service_reference_kind == "none"
    assert any(item.code == "active_session_service_unavailable" for item in adapted.diagnostics)


def test_mixed_known_unknown_requested_facts() -> None:
    from contracts.response_plan_composer import adapt_composer_json_to_decision
    from tests.test_response_plan_contract import fact

    plan = _composer_plan(commercial_facts=(fact("installment_12"),))
    adapted = adapt_composer_json_to_decision(
        _json(patient_text="Факты.", requested_fact_ids=["installment_12", "ghost_fact"]),
        _composer_decision_authority_from_plan(plan),
    )
    assert adapted.decision.requested_fact_ids == ("installment_12",)
    assert any(item.code == "requested_fact_unknown" and item.detail == "ghost_fact" for item in adapted.diagnostics)
