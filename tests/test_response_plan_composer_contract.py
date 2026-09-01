from __future__ import annotations

import json
from copy import deepcopy
from typing import get_args

import pytest

from contracts.answer_plan import AspectKind
from contracts.response_plan import (
    CommercialFactCandidate,
    ComposerResult,
    ComposerSelectedRouteAuthority,
    DeterministicBypassRouteAuthority,
    PreComposerPlan,
    PricePlan,
    RouteModePair,
    SessionKey,
    all_allowed_route_mode_pairs,
)
from contracts.response_plan_composer import (
    COMPOSER_DECISION_DIAGNOSTIC_CODES,
    CORE_RESPONSE_FIELDS,
    ComposerDecision,
    ComposerDecisionAuthority,
    ComposerPatientSituation,
    FORBIDDEN_LEGACY_TOP_LEVEL_KEYS,
    PUBLISHED_COMPOSER_OUTPUT_SCHEMA_JSON,
    PUBLISHED_TARGET_KEYS,
    ComposerAdapterError,
    ComposerParserError,
    ComposerPolicySidecar,
    PricePolicyMulti,
    PricePolicyNone,
    PricePolicySingle,
    RequestableFactDescriptor,
    RoutePolicyEntry,
    ServiceDescriptor,
    adapt_composer_envelope_to_decision,
    future_prompt_composition_parts,
    is_valid_source_ref_basename,
    parse_response_plan_composer_json,
    published_target_schema_example,
    route_policy_entry,
)
from contracts.target_composer_source_identity import TargetComposerSourceIdentity
from core.response_plan_composer_contract import (
    COMPOSER_POLICY_SIDECAR_KIND,
    ComposerPolicySidecarError,
    build_composer_policy_sidecar,
    build_static_composer_instructions,
    serialize_composer_policy_sidecar,
)
from core.response_plan_resolver import resolve_response_plan
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui
from pydantic import ValidationError

from tests.test_response_plan_contract import (
    admin_terminal,
    composer_route_authority,
    contacts_terminal,
    default_terminal_candidates,
    deterministic_route_authority,
    fact,
    make_plan,
    price_multi,
    price_single,
    session,
)


def _default_patient_situation(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "extent": "unknown",
        "jaw": "unknown",
        "stage": "unknown",
        "modifiers": [],
    }
    payload.update(overrides)
    return payload


def _base_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "route": "ANSWER",
        "mode": "standard",
        "patient_text": "Ответ пациенту.",
        "service_reference_kind": "none",
        "topic_id": None,
        "explicit_service_id": None,
        "requested_aspect_ids": [],
        "patient_situation": _default_patient_situation(),
        "requested_fact_ids": [],
        "source_identity": None,
    }
    payload.update(overrides)
    return payload


def _json(**overrides: object) -> str:
    return json.dumps(_base_payload(**overrides), ensure_ascii=False)


def _composer_plan(**overrides: object) -> PreComposerPlan:
    payload = {
        "session_key": session(),
        "context_strategy": "full_context",
        "route_authority": composer_route_authority(),
        "response_scope": "clinic",
        "price_plan": price_single(),
    }
    payload.update(overrides)
    return PreComposerPlan(**payload)


def _service_descriptor(service_id: str) -> ServiceDescriptor:
    return ServiceDescriptor(
        service_id=service_id,
        label=f"Label {service_id}",
        aliases=(f"alias-{service_id}",),
        short_meaning=f"Meaning for {service_id}",
    )


def _price_policy_from_plan(plan: PreComposerPlan) -> PricePolicySingle | PricePolicyMulti | PricePolicyNone:
    price_plan = plan.price_plan
    if price_plan.kind == "none":
        return PricePolicyNone()
    if price_plan.kind == "single":
        single = price_plan.single
        assert single is not None
        return PricePolicySingle(display_text=single.display_text, offer_id=single.offer_id)
    multi = price_plan.multi
    assert multi is not None
    return PricePolicyMulti(display_text=multi.display_text, offer_ids=multi.offer_ids)


def _composer_decision_authority_from_plan(plan: PreComposerPlan) -> ComposerDecisionAuthority:
    """Test-only bridge: build independent authority from an isolated PreComposerPlan."""

    route_authority = plan.route_authority
    if isinstance(route_authority, DeterministicBypassRouteAuthority):
        return ComposerDecisionAuthority(
            allowed_route_modes=(route_authority.route_mode,),
            allowed_topic_ids=(),
            service_descriptors=(),
            bypass=True,
        )
    if not isinstance(route_authority, ComposerSelectedRouteAuthority):
        raise ComposerAdapterError("route_mode_not_allowed", type(route_authority).__name__)

    topic_ids: set[str] = set()
    service_ids: set[str] = set()
    if plan.selected_topic_id is not None:
        topic_ids.add(plan.selected_topic_id)
    if plan.selected_service_id is not None:
        service_ids.add(plan.selected_service_id)
    if plan.active_session_service_id is not None:
        service_ids.add(plan.active_session_service_id)
    for fact in plan.commercial_facts:
        topic_ids.update(fact.allowed_topic_ids)
        service_ids.update(fact.allowed_service_ids)

    requestable_facts: list[RequestableFactDescriptor] = []
    for fact in plan.commercial_facts:
        if "requested_fact" not in fact.allowed_roles:
            continue
        if fact.applicability == "topic_scoped":
            requestable_facts.append(
                RequestableFactDescriptor(
                    fact_id=fact.fact_id,
                    meaning=fact.display_text,
                    explicit_only=fact.explicit_only,
                    applicability=fact.applicability,
                    allowed_topic_ids=fact.allowed_topic_ids,
                    requires_implant_scope=fact.requires_implant_scope,
                )
            )
        elif fact.applicability == "service_scoped":
            requestable_facts.append(
                RequestableFactDescriptor(
                    fact_id=fact.fact_id,
                    meaning=fact.display_text,
                    explicit_only=fact.explicit_only,
                    applicability=fact.applicability,
                    allowed_service_ids=fact.allowed_service_ids,
                    requires_implant_scope=fact.requires_implant_scope,
                )
            )
        else:
            requestable_facts.append(
                RequestableFactDescriptor(
                    fact_id=fact.fact_id,
                    meaning=fact.display_text,
                    explicit_only=fact.explicit_only,
                    applicability=fact.applicability,
                    requires_implant_scope=fact.requires_implant_scope,
                )
            )

    return ComposerDecisionAuthority(
        allowed_route_modes=route_authority.allowed_route_modes,
        allowed_topic_ids=tuple(sorted(topic_ids)),
        service_descriptors=tuple(_service_descriptor(service_id) for service_id in sorted(service_ids)),
        bypass=False,
        active_session_service_id=plan.active_session_service_id,
        context_strategy=plan.context_strategy,
        history_turn_count=plan.history_turn_count,
        price_policy=_price_policy_from_plan(plan),
        allowed_aspect_ids=tuple(get_args(AspectKind)),
        requestable_facts=tuple(requestable_facts),
    )


def _test_build_composer_policy_sidecar_from_plan(plan: PreComposerPlan) -> ComposerPolicySidecar:
    return build_composer_policy_sidecar(_composer_decision_authority_from_plan(plan))


def _composer_result_from_adapted(adapted) -> ComposerResult:
    decision = adapted.decision
    return ComposerResult(
        route=decision.route,
        mode=decision.mode,
        patient_text=decision.patient_text,
        requested_fact_ids=decision.requested_fact_ids,
    )


def _authority_with_source_refs(
    authority: ComposerDecisionAuthority,
    *refs: str,
) -> ComposerDecisionAuthority:
    return ComposerDecisionAuthority(
        allowed_route_modes=authority.allowed_route_modes,
        allowed_topic_ids=authority.allowed_topic_ids,
        service_descriptors=authority.service_descriptors,
        allowed_source_refs=refs,
        active_session_service_id=authority.active_session_service_id,
        context_strategy=authority.context_strategy,
        history_turn_count=authority.history_turn_count,
        price_policy=authority.price_policy,
        allowed_aspect_ids=authority.allowed_aspect_ids,
        requestable_facts=authority.requestable_facts,
    )


def _adapted_source_identity_equal(adapted) -> None:
    decision_identity = adapted.decision.source_identity
    adapted_identity = adapted.source_identity
    if decision_identity is None:
        assert adapted_identity is None
        return
    assert adapted_identity is not None
    assert decision_identity.primary_content_ref == adapted_identity.primary_content_ref
    assert decision_identity.used_content_refs == adapted_identity.used_content_refs


def test_published_schema_has_exact_target_keys() -> None:
    example = published_target_schema_example()
    assert set(example.keys()) == PUBLISHED_TARGET_KEYS
    assert len(example.keys()) == len(PUBLISHED_TARGET_KEYS)


def test_core_fields_have_no_defaults_in_parser() -> None:
    for field in CORE_RESPONSE_FIELDS:
        payload = _base_payload()
        del payload[field]
        with pytest.raises(ComposerParserError) as exc:
            parse_response_plan_composer_json(json.dumps(payload, ensure_ascii=False))
        assert exc.value.code == "json_missing_core_field"
        assert exc.value.detail == field


def test_published_schema_requires_source_identity_key_but_missing_is_warning() -> None:
    payload = _base_payload()
    del payload["source_identity"]
    parsed = parse_response_plan_composer_json(json.dumps(payload, ensure_ascii=False))
    assert parsed.envelope.source_identity is None
    assert any(item.code == "source_identity_missing" for item in parsed.warnings)


def test_extra_top_level_field_forbidden() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(_json(extra_field=True))
    assert exc.value.code == "json_extra_field"


@pytest.mark.parametrize("legacy_key", sorted(FORBIDDEN_LEGACY_TOP_LEVEL_KEYS))
def test_legacy_top_level_fields_forbidden(legacy_key: str) -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(_json(**{legacy_key: "legacy"}))
    assert exc.value.code == "json_extra_field"


@pytest.mark.parametrize(
    "route,mode,patient_text,requested_fact_ids,source_identity",
    [
        ("ANSWER", "standard", "Текст.", [], None),
        ("ANSWER", "contacts", None, [], None),
        ("ADMIN", "standard", None, [], None),
        ("ADMIN", "medical_terminal", None, [], None),
        ("CLARIFY", "standard", "Уточните.", [], None),
    ],
)
def test_all_route_mode_shapes_accepted(
    route: str,
    mode: str,
    patient_text: str | None,
    requested_fact_ids: list[str],
    source_identity: object | None,
) -> None:
    parsed = parse_response_plan_composer_json(
        _json(
            route=route,
            mode=mode,
            patient_text=patient_text,
            requested_fact_ids=requested_fact_ids,
            source_identity=source_identity,
        )
    )
    assert parsed.envelope.route == route
    assert parsed.envelope.mode == mode


def _run_pipeline(plan: PreComposerPlan, raw_json: str):
    authority = _composer_decision_authority_from_plan(plan)
    parsed = parse_response_plan_composer_json(raw_json)
    adapted = adapt_composer_envelope_to_decision(parsed, authority)
    resolved = resolve_response_plan(plan, _composer_result_from_adapted(adapted))
    text = render_response_text(resolved)
    ui = project_response_ui(resolved)
    return parsed, adapted, resolved, text, ui


def _diag_codes(resolved) -> set[str]:
    return {item.code for item in resolved.diagnostics}


def test_policy_sidecar_is_policy_control_not_full_prompt() -> None:
    plan = _composer_plan()
    sidecar = _test_build_composer_policy_sidecar_from_plan(plan)
    assert sidecar.kind == COMPOSER_POLICY_SIDECAR_KIND
    instructions = build_static_composer_instructions()
    assert "policy/control sidecar is not the complete Composer input or prompt" in instructions
    assert "complete Composer input or prompt" not in instructions.replace(
        "policy/control sidecar is not the complete Composer input or prompt", ""
    )
    serialized = serialize_composer_policy_sidecar(sidecar)
    assert "current user message" not in serialized
    assert "corpus" not in serialized
    assert "session_id" not in serialized
    assert "client_id" not in serialized


def test_static_instructions_require_exact_target_key_json_output() -> None:
    instructions = build_static_composer_instructions()
    assert "exactly one JSON object" in instructions
    assert "Do not wrap JSON in Markdown or code fences" in instructions
    assert "Do not include any text before or after the JSON object" in instructions
    assert PUBLISHED_COMPOSER_OUTPUT_SCHEMA_JSON in instructions
    for key in PUBLISHED_TARGET_KEYS:
        assert key in instructions
    assert "requested_fact_ids may contain only fact_id values from model-visible requestable fact descriptors" in instructions
    assert "patient_text is natural model prose" in instructions
    assert "source_identity is model attestation only" in instructions


def test_future_prompt_composition_lists_five_parts() -> None:
    parts = future_prompt_composition_parts()
    assert len(parts) == 5
    instructions = build_static_composer_instructions()
    for part in parts:
        assert part in instructions


def test_sidecar_contains_context_strategy_not_source_identity_output() -> None:
    plan = _composer_plan(context_strategy="hybrid")
    sidecar = _test_build_composer_policy_sidecar_from_plan(plan)
    assert sidecar.context_strategy == "hybrid"
    serialized = serialize_composer_policy_sidecar(sidecar)
    assert "source_identity" not in serialized


def test_sidecar_requestable_facts_only_for_requested_fact_role() -> None:
    plan = _composer_plan(
        commercial_facts=(
            CommercialFactCandidate(
                fact_id="installment_12",
                display_text="Рассрочка 12 месяцев без переплаты.",
                explicit_only=False,
                allowed_roles=("requested_fact", "promo"),
                applicability="clinic_wide",
                source_client_id="demo",
            ),
            CommercialFactCandidate(
                fact_id="implant_warranty",
                display_text="Гарантия на импланты по договору.",
                explicit_only=True,
                allowed_roles=("requested_fact",),
                applicability="service_scoped",
                allowed_service_ids=("all_on_4",),
                source_client_id="demo",
                requires_implant_scope=True,
            ),
            CommercialFactCandidate(
                fact_id="promo_only",
                display_text="Промо факт.",
                explicit_only=False,
                allowed_roles=("promo",),
                applicability="clinic_wide",
                source_client_id="demo",
            ),
        )
    )
    sidecar = _test_build_composer_policy_sidecar_from_plan(plan)
    ids = {item.fact_id for item in sidecar.requestable_facts}
    assert ids == {"installment_12", "implant_warranty"}
    installment = next(item for item in sidecar.requestable_facts if item.fact_id == "installment_12")
    warranty = next(item for item in sidecar.requestable_facts if item.fact_id == "implant_warranty")
    assert "Рассрочка" in installment.meaning
    assert warranty.explicit_only is True
    assert warranty.requires_implant_scope is True
    serialized = serialize_composer_policy_sidecar(sidecar)
    assert "promo_only" not in serialized


def test_sidecar_excludes_terminal_contact_phone_and_display_text() -> None:
    plan = _composer_plan()
    sidecar = _test_build_composer_policy_sidecar_from_plan(plan)
    serialized = serialize_composer_policy_sidecar(sidecar)
    for terminal in default_terminal_candidates():
        assert terminal.display_text not in serialized
        if terminal.canonical_contact is not None:
            assert terminal.canonical_contact.phone not in serialized


def test_deterministic_bypass_sidecar_forbidden() -> None:
    plan = _composer_plan(route_authority=deterministic_route_authority())
    with pytest.raises(ComposerPolicySidecarError) as exc:
        _test_build_composer_policy_sidecar_from_plan(plan)
    assert exc.value.code == "composer_forbidden_for_bypass"


def test_equal_plan_yields_byte_identical_sidecar() -> None:
    plan = _composer_plan()
    first = serialize_composer_policy_sidecar(_test_build_composer_policy_sidecar_from_plan(plan))
    second = serialize_composer_policy_sidecar(_test_build_composer_policy_sidecar_from_plan(plan))
    assert first == second
    assert first.encode("utf-8") == second.encode("utf-8")


def test_public_sidecar_types_reject_invalid_direct_construction() -> None:
    with pytest.raises(ValidationError):
        PricePolicySingle(display_text="", offer_id="offer_a")
    with pytest.raises(ValidationError):
        PricePolicySingle(display_text="120 000 ₽", offer_id=" padded ")
    with pytest.raises(ValidationError):
        PricePolicyMulti(display_text="multi", offer_ids=("only_one",))
    with pytest.raises(ValidationError):
        PricePolicyMulti(display_text="multi", offer_ids=("a", "a"))
    with pytest.raises(ValidationError):
        RoutePolicyEntry(
            route="ANSWER",
            mode="medical_terminal",
            purpose="invalid",
            code_owned_visible_response=False,
        )
    with pytest.raises(ValidationError):
        RequestableFactDescriptor(
            fact_id="",
            meaning="meaning",
            explicit_only=False,
            applicability="clinic_wide",
        )
    with pytest.raises(ValidationError):
        ComposerPolicySidecar(
            kind="policy_control",
            allowed_route_modes=(),
            allowed_topic_ids=(),
            service_descriptors=(),
            context_strategy="full_context",
            history_turn_count=0,
            price_policy=PricePolicySingle(display_text="x", offer_id="y"),
            allowed_aspect_ids=("price",),
        )
    with pytest.raises(ValidationError, match="allowed_aspect_ids_empty"):
        ComposerPolicySidecar(
            kind="policy_control",
            allowed_route_modes=(
                route_policy_entry("ANSWER", "standard"),
            ),
            allowed_topic_ids=(),
            service_descriptors=(_service_descriptor("svc_a"),),
            context_strategy="full_context",
            history_turn_count=0,
            price_policy=PricePolicySingle(display_text="x", offer_id="y"),
            allowed_aspect_ids=(),
        )


def test_requestable_fact_descriptor_rejects_duplicate_service_ids() -> None:
    with pytest.raises(ValidationError, match="allowed_service_id_duplicate"):
        RequestableFactDescriptor(
            fact_id="fact_a",
            meaning="meaning",
            explicit_only=False,
            applicability="service_scoped",
            allowed_service_ids=("svc_a", "svc_a"),
        )


def test_requestable_fact_descriptor_rejects_duplicate_topic_ids() -> None:
    with pytest.raises(ValidationError, match="allowed_topic_id_duplicate"):
        RequestableFactDescriptor(
            fact_id="fact_a",
            meaning="meaning",
            explicit_only=False,
            applicability="topic_scoped",
            allowed_topic_ids=("topic_a", "topic_a"),
        )


def test_requestable_fact_descriptor_rejects_clinic_wide_with_scope_allowlists() -> None:
    with pytest.raises(ValidationError, match="clinic_wide_forbids_scope_allowlists"):
        RequestableFactDescriptor(
            fact_id="fact_a",
            meaning="meaning",
            explicit_only=False,
            applicability="clinic_wide",
            allowed_service_ids=("svc_a",),
        )


def test_requestable_fact_descriptor_rejects_clinic_wide_with_implant_scope() -> None:
    with pytest.raises(ValidationError, match="clinic_wide_forbids_implant_scope"):
        RequestableFactDescriptor(
            fact_id="fact_a",
            meaning="meaning",
            explicit_only=False,
            applicability="clinic_wide",
            requires_implant_scope=True,
        )


def test_requestable_fact_descriptor_rejects_topic_scoped_without_topics() -> None:
    with pytest.raises(ValidationError, match="topic_scoped_requires_topic_ids"):
        RequestableFactDescriptor(
            fact_id="fact_a",
            meaning="meaning",
            explicit_only=False,
            applicability="topic_scoped",
        )


def test_requestable_fact_descriptor_rejects_topic_scoped_with_service_ids() -> None:
    with pytest.raises(ValidationError, match="topic_scoped_forbids_service_ids"):
        RequestableFactDescriptor(
            fact_id="fact_a",
            meaning="meaning",
            explicit_only=False,
            applicability="topic_scoped",
            allowed_topic_ids=("clinic",),
            allowed_service_ids=("svc_a",),
        )


def test_requestable_fact_descriptor_rejects_service_scoped_without_services() -> None:
    with pytest.raises(ValidationError, match="service_scoped_requires_service_ids"):
        RequestableFactDescriptor(
            fact_id="fact_a",
            meaning="meaning",
            explicit_only=False,
            applicability="service_scoped",
        )


def test_requestable_fact_descriptor_rejects_service_scoped_with_topic_ids() -> None:
    with pytest.raises(ValidationError, match="service_scoped_forbids_topic_ids"):
        RequestableFactDescriptor(
            fact_id="fact_a",
            meaning="meaning",
            explicit_only=False,
            applicability="service_scoped",
            allowed_service_ids=("svc_a",),
            allowed_topic_ids=("clinic",),
        )


def test_route_policy_entry_rejects_incorrect_purpose() -> None:
    with pytest.raises(ValidationError, match="route_purpose_mismatch"):
        RoutePolicyEntry(
            route="ANSWER",
            mode="standard",
            purpose="complaint",
            code_owned_visible_response=False,
        )


def test_route_policy_entry_rejects_incorrect_code_owned_flag() -> None:
    with pytest.raises(ValidationError, match="code_owned_visible_response_mismatch"):
        RoutePolicyEntry(
            route="ANSWER",
            mode="standard",
            purpose="ordinary_useful_answer",
            code_owned_visible_response=True,
        )


def test_composer_policy_sidecar_rejects_bool_history_count() -> None:
    with pytest.raises(ValidationError):
        ComposerPolicySidecar(
            kind="policy_control",
            allowed_route_modes=(route_policy_entry("ANSWER", "standard"),),
            response_scope="clinic",
            context_strategy="full_context",
            history_turn_count=True,  # type: ignore[arg-type]
            price_policy=PricePolicySingle(display_text="x", offer_id="y"),
        )


def test_composer_policy_sidecar_rejects_string_history_count() -> None:
    with pytest.raises(ValidationError):
        ComposerPolicySidecar(
            kind="policy_control",
            allowed_route_modes=(route_policy_entry("ANSWER", "standard"),),
            response_scope="clinic",
            context_strategy="full_context",
            history_turn_count="1",  # type: ignore[arg-type]
            price_policy=PricePolicySingle(display_text="x", offer_id="y"),
        )


def test_composer_policy_sidecar_rejects_numeric_boolean_fields() -> None:
    with pytest.raises(ValidationError):
        RequestableFactDescriptor(
            fact_id="fact_a",
            meaning="meaning",
            explicit_only=1,  # type: ignore[arg-type]
            applicability="clinic_wide",
        )


def test_composer_policy_sidecar_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ComposerPolicySidecar(
            kind="policy_control",
            allowed_route_modes=(route_policy_entry("ANSWER", "standard"),),
            response_scope="clinic",
            context_strategy="full_context",
            history_turn_count=0,
            price_policy=PricePolicySingle(display_text="x", offer_id="y"),
            unexpected=True,  # type: ignore[call-arg]
        )


def test_composer_policy_sidecar_rejects_list_for_tuple_field() -> None:
    with pytest.raises(ValidationError):
        ComposerPolicySidecar(
            kind="policy_control",
            allowed_route_modes=[route_policy_entry("ANSWER", "standard")],  # type: ignore[list-item]
            response_scope="clinic",
            context_strategy="full_context",
            history_turn_count=0,
            price_policy=PricePolicySingle(display_text="x", offer_id="y"),
        )


@pytest.mark.parametrize(
    "ref,expected",
    [
        ("clinic__info__consultation.md", True),
        ("some_source.md", True),
        ("../secret.md", False),
        ("folder/file.md", False),
        ("folder\\file.md", False),
        ("file.txt", False),
        (" source.md", False),
        ("source.md ", False),
    ],
)
def test_source_ref_basename_validation_matrix(ref: str, expected: bool) -> None:
    assert is_valid_source_ref_basename(ref) is expected


def test_pipeline_clinic_answer_without_service() -> None:
    plan = _composer_plan(
        response_scope="clinic",
        selected_service_id=None,
        selected_topic_id=None,
        price_plan=PricePlan(kind="none"),
    )
    _, _, resolved, text, ui = _run_pipeline(plan, _json(patient_text="Общий ответ о клинике."))
    assert resolved.route == "ANSWER"
    assert resolved.mode == "standard"
    assert resolved.response_scope == "clinic"
    assert resolved.patient_text == "Общий ответ о клинике."
    assert resolved.price_block is None
    assert resolved.finalized_commercial_ids.price_offer_ids == ()
    assert "Общий ответ о клинике." in text
    assert ui is not None


def test_pipeline_requested_installment_finalized_once() -> None:
    plan = _composer_plan(
        commercial_facts=(
            fact("installment_12", text="Рассрочка 12 месяцев.", roles=("requested_fact", "promo")),
        )
    )
    _, _, resolved, text, _ = _run_pipeline(
        plan,
        _json(patient_text="Да, есть рассрочка.", requested_fact_ids=["installment_12"]),
    )
    assert resolved.finalized_commercial_ids.requested_fact_ids == ("installment_12",)
    assert len(resolved.requested_fact_blocks) == 1
    assert resolved.requested_fact_blocks[0].fact_id == "installment_12"
    assert "Рассрочка 12 месяцев." in text
    assert resolved.finalized_commercial_ids.requested_fact_ids.count("installment_12") == 1


def test_pipeline_explicit_implant_warranty_in_service_scope() -> None:
    plan = make_plan(
        response_scope="service",
        selected_service_id="implantium",
        commercial_facts=(
            fact(
                "implant_warranty",
                explicit_only=True,
                roles=("requested_fact",),
                applicability="service_scoped",
                allowed_service_ids=("implantium",),
                requires_implant_scope=True,
                text="Гарантия на импланты.",
            ),
        ),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
        required_offer_conditions=(),
    )
    _, _, resolved, text, _ = _run_pipeline(
        plan,
        _json(patient_text="Про гарантию.", requested_fact_ids=["implant_warranty"]),
    )
    assert resolved.finalized_commercial_ids.requested_fact_ids == ("implant_warranty",)
    assert "Гарантия на импланты." in text


def test_pipeline_unknown_requested_fact_preserves_patient_text() -> None:
    plan = _composer_plan()
    raw = _json(patient_text="Сохранить этот текст.", requested_fact_ids=["unknown_fact"])
    authority = _composer_decision_authority_from_plan(plan)
    adapted = adapt_composer_envelope_to_decision(parse_response_plan_composer_json(raw), authority)
    _, _, resolved, text, _ = _run_pipeline(plan, raw)
    assert resolved.patient_text == "Сохранить этот текст."
    assert any(item.code == "requested_fact_unknown" for item in adapted.diagnostics)
    assert resolved.finalized_commercial_ids.requested_fact_ids == ()
    assert "Сохранить этот текст." in text


def test_pipeline_inapplicable_requested_fact_suppressed() -> None:
    plan = _composer_plan(
        response_scope="clinic",
        selected_service_id=None,
        commercial_facts=(
            fact(
                "implant_warranty",
                explicit_only=True,
                roles=("requested_fact",),
                applicability="service_scoped",
                allowed_service_ids=("implantium",),
                requires_implant_scope=True,
            ),
        ),
    )
    _, _, resolved, _, _ = _run_pipeline(
        plan,
        _json(patient_text="Гарантия?", requested_fact_ids=["implant_warranty"]),
    )
    assert "requested_fact_inapplicable" in _diag_codes(resolved)
    assert resolved.finalized_commercial_ids.requested_fact_ids == ()
    assert resolved.requested_fact_blocks == ()


def test_pipeline_single_price_uses_canonical_single_owner() -> None:
    single = price_single()
    assert single.single is not None
    plan = _composer_plan(price_plan=single)
    _, _, resolved, text, _ = _run_pipeline(
        plan,
        _json(patient_text="Цена.", requested_aspect_ids=["price"]),
    )
    assert resolved.price_block is not None
    assert resolved.price_block.owner == "canonical_single"
    assert single.single.display_text in text


def test_pipeline_multi_price_uses_canonical_multi_owner() -> None:
    multi = price_multi()
    plan = _composer_plan(price_plan=multi, response_scope="clinic", selected_service_id=None)
    _, _, resolved, text, _ = _run_pipeline(
        plan,
        _json(patient_text="Варианты.", requested_aspect_ids=["price"]),
    )
    assert resolved.price_block is not None
    assert resolved.price_block.owner == "canonical_multi"
    assert multi.multi is not None
    assert multi.multi.display_text in text


def test_pipeline_no_offer_has_no_price_block() -> None:
    plan = _composer_plan(price_plan=PricePlan(kind="none"))
    _, _, resolved, _, _ = _run_pipeline(
        plan,
        _json(patient_text="Ответ.", requested_aspect_ids=["price"]),
    )
    assert resolved.price_block is None


def test_pipeline_contacts_terminal_code_owned_text_only() -> None:
    terminal = contacts_terminal()
    plan = _composer_plan()
    _, _, resolved, text, ui = _run_pipeline(
        plan,
        _json(route="ANSWER", mode="contacts", patient_text=None),
    )
    assert resolved.route == "ANSWER"
    assert resolved.mode == "contacts"
    assert resolved.terminal_text == terminal.display_text
    assert text == terminal.display_text
    assert resolved.finalized_commercial_ids.price_offer_ids == ()
    assert resolved.finalized_commercial_ids.requested_fact_ids == ()
    assert ui.contact is not None


def test_pipeline_admin_deterministic_terminal_without_commerce() -> None:
    terminal = admin_terminal()
    plan = _composer_plan()
    _, _, resolved, text, _ = _run_pipeline(
        plan,
        _json(route="ADMIN", mode="standard", patient_text=None),
    )
    assert resolved.route == "ADMIN"
    assert resolved.terminal_text == terminal.display_text
    assert text == terminal.display_text
    assert resolved.finalized_commercial_ids.promo_fact_ids == ()
    assert resolved.finalized_commercial_ids.amplifier_fact_ids == ()


def test_pipeline_clarify_sets_pending_without_commerce() -> None:
    plan = _composer_plan(response_scope="clinic", selected_service_id=None)
    _, _, resolved, text, _ = _run_pipeline(
        plan,
        _json(route="CLARIFY", mode="standard", patient_text="Уточните вопрос."),
    )
    assert resolved.route == "CLARIFY"
    assert resolved.session_delta.clarify_pending is True
    assert resolved.finalized_commercial_ids.price_offer_ids == ()
    assert text == "Уточните вопрос."


def test_pipeline_source_identity_isolated_from_resolver_and_render() -> None:
    plan = _composer_plan(price_plan=PricePlan(kind="none"))
    raw = _json(
        patient_text="Ответ.",
        source_identity={
            "primary_content_ref": "clinic__info__consultation.md",
            "used_content_refs": ["clinic__info__consultation.md"],
        },
    )
    parsed = parse_response_plan_composer_json(raw)
    adapted = adapt_composer_envelope_to_decision(
        parsed,
        _authority_with_source_refs(
            _composer_decision_authority_from_plan(plan),
            "clinic__info__consultation.md",
        ),
    )
    resolved_before = resolve_response_plan(plan, _composer_result_from_adapted(adapted))
    text_before = render_response_text(resolved_before)
    assert adapted.source_identity is not None
    assert adapted.source_identity.primary_content_ref == "clinic__info__consultation.md"
    _adapted_source_identity_equal(adapted)
    plan_no_identity = _composer_plan(price_plan=PricePlan(kind="none"))
    adapted_none = adapt_composer_envelope_to_decision(
        parse_response_plan_composer_json(_json(patient_text="Ответ.")),
        _composer_decision_authority_from_plan(plan_no_identity),
    )
    resolved_after = resolve_response_plan(plan_no_identity, _composer_result_from_adapted(adapted_none))
    text_after = render_response_text(resolved_after)
    assert text_before == text_after == "Ответ."
    assert resolved_before.patient_text == resolved_after.patient_text


def test_composer_contract_modules_have_no_provider_imports() -> None:
    import ast
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    modules = (
        repo / "contracts" / "response_plan_composer.py",
        repo / "core" / "response_plan_composer_contract.py",
    )
    forbidden = {"openai", "httpx", "requests", "aiohttp"}
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert imported.isdisjoint(forbidden), module


def test_valid_source_identity_preserved_in_adapted_output_not_resolver() -> None:
    plan = _composer_plan()
    raw = _json(
        patient_text="Ответ.",
        source_identity={
            "primary_content_ref": "clinic__info__consultation.md",
            "used_content_refs": ["clinic__info__consultation.md", "clinic__info__about.md"],
        },
    )
    parsed = parse_response_plan_composer_json(raw)
    adapted = adapt_composer_envelope_to_decision(
        parsed,
        _authority_with_source_refs(
            _composer_decision_authority_from_plan(plan),
            "clinic__info__consultation.md",
            "clinic__info__about.md",
        ),
    )
    assert isinstance(adapted.source_identity, TargetComposerSourceIdentity)
    assert adapted.source_identity.primary_content_ref == "clinic__info__consultation.md"
    _adapted_source_identity_equal(adapted)
    resolved = resolve_response_plan(plan, _composer_result_from_adapted(adapted))
    assert resolved.patient_text == "Ответ."


def test_adapter_rejects_route_outside_plan() -> None:
    plan = _composer_plan(
        route_authority=ComposerSelectedRouteAuthority(
            allowed_route_modes=(RouteModePair(route="CLARIFY", mode="standard"),),
            terminal_candidates=(),
        )
    )
    parsed = parse_response_plan_composer_json(_json(route="ANSWER", mode="standard", patient_text="x"))
    with pytest.raises(ComposerAdapterError) as exc:
        adapt_composer_envelope_to_decision(
            parsed,
            _composer_decision_authority_from_plan(plan),
        )
    assert exc.value.code == "route_mode_not_allowed"


def test_adapter_rejects_composer_for_bypass_plan() -> None:
    plan = _composer_plan(route_authority=deterministic_route_authority())
    parsed = parse_response_plan_composer_json(_json())
    with pytest.raises(ComposerAdapterError) as exc:
        adapt_composer_envelope_to_decision(
            parsed,
            _composer_decision_authority_from_plan(plan),
        )
    assert exc.value.code == "composer_forbidden_for_bypass"


def test_building_sidecar_does_not_mutate_plan() -> None:
    plan = _composer_plan()
    snapshot = plan.model_dump()
    _test_build_composer_policy_sidecar_from_plan(plan)
    assert plan.model_dump() == snapshot


def test_route_policy_entries_cover_allowed_pairs() -> None:
    plan = _composer_plan()
    sidecar = _test_build_composer_policy_sidecar_from_plan(plan)
    pairs = {(item.route, item.mode) for item in sidecar.allowed_route_modes}
    assert pairs == {(item.route, item.mode) for item in all_allowed_route_mode_pairs()}


def test_terminal_route_policy_marked_code_owned() -> None:
    plan = _composer_plan()
    sidecar = _test_build_composer_policy_sidecar_from_plan(plan)
    contacts = next(
        item for item in sidecar.allowed_route_modes if item.route == "ANSWER" and item.mode == "contacts"
    )
    assert contacts.code_owned_visible_response is True


def test_adapted_decision_has_no_composer_result() -> None:
    _, adapted, _, _, _ = _run_pipeline(plan := _composer_plan(), _json())
    assert not hasattr(adapted, "composer_result")
    assert adapted.decision.route == "ANSWER"


def test_topic_scoped_implant_warranty_descriptor_allowed() -> None:
    descriptor = RequestableFactDescriptor(
        fact_id="implant_warranty",
        meaning="Гарантия на импланты.",
        explicit_only=True,
        applicability="topic_scoped",
        allowed_topic_ids=("implantation",),
        requires_implant_scope=True,
    )
    assert descriptor.requires_implant_scope is True


def test_service_descriptor_rejects_blank_and_duplicate_aliases() -> None:
    with pytest.raises(ValidationError, match="string_must_not_be_blank"):
        ServiceDescriptor(service_id="", label="x", aliases=(), short_meaning="y")
    with pytest.raises(ValidationError, match="service_descriptor_alias_duplicate"):
        ServiceDescriptor(
            service_id="svc_a",
            label="Label",
            aliases=("a", "a"),
            short_meaning="Meaning",
        )


def test_terminal_normalization_matrix() -> None:
    authority = _composer_decision_authority_from_plan(_composer_plan())
    cases = (
        ("ANSWER", "contacts"),
        ("ADMIN", "standard"),
        ("ADMIN", "medical_terminal"),
    )
    for route, mode in cases:
        adapted = adapt_composer_envelope_to_decision(
            parse_response_plan_composer_json(
                _json(
                    route=route,
                    mode=mode,
                    patient_text=None,
                    topic_id="implantation",
                    service_reference_kind="explicit_current",
                    explicit_service_id="all_on_4",
                    requested_aspect_ids=["price"],
                )
            ),
            authority,
        )
        assert adapted.decision.service_reference_kind == "none"
        assert adapted.decision.topic_id is None
        assert adapted.decision.explicit_service_id is None
        assert adapted.decision.requested_aspect_ids == ()
        assert adapted.decision.requested_fact_ids == ()
        assert adapted.source_identity is None
        assert any(item.code == "terminal_fields_normalized" for item in adapted.diagnostics)


def test_source_refs_filtering_fail_open() -> None:
    authority = _authority_with_source_refs(
        _composer_decision_authority_from_plan(_composer_plan()),
        "allowed.md",
    )
    adapted = adapt_composer_envelope_to_decision(
        parse_response_plan_composer_json(
            _json(
                source_identity={
                    "primary_content_ref": "foreign.md",
                    "used_content_refs": ["foreign.md", "allowed.md"],
                }
            )
        ),
        authority,
    )
    assert adapted.source_identity is None
    assert adapted.decision.source_identity is None
    _adapted_source_identity_equal(adapted)
    assert [item.detail for item in adapted.diagnostics if item.code == "source_ref_not_allowed"] == ["foreign.md"]
    assert adapted.decision.patient_text == "Ответ пациенту."


def test_empty_source_allowlist_denies_model_reported_refs() -> None:
    authority = _composer_decision_authority_from_plan(_composer_plan())
    adapted = adapt_composer_envelope_to_decision(
        parse_response_plan_composer_json(
            _json(
                source_identity={
                    "primary_content_ref": "foreign.md",
                    "used_content_refs": ["foreign.md"],
                }
            )
        ),
        authority,
    )
    assert adapted.source_identity is None
    assert adapted.decision.source_identity is None
    assert [item.code for item in adapted.diagnostics] == ["source_ref_not_allowed"]
    _adapted_source_identity_equal(adapted)


def test_empty_source_allowlist_without_model_identity_has_no_diagnostics() -> None:
    authority = _composer_decision_authority_from_plan(_composer_plan())
    adapted = adapt_composer_envelope_to_decision(parse_response_plan_composer_json(_json()), authority)
    assert adapted.source_identity is None
    assert adapted.decision.source_identity is None
    assert adapted.diagnostics == ()


def test_allowed_primary_with_foreign_used_ref_filters_both_projections() -> None:
    authority = _authority_with_source_refs(
        _composer_decision_authority_from_plan(_composer_plan()),
        "allowed.md",
    )
    adapted = adapt_composer_envelope_to_decision(
        parse_response_plan_composer_json(
            _json(
                source_identity={
                    "primary_content_ref": "allowed.md",
                    "used_content_refs": ["allowed.md", "foreign.md"],
                }
            )
        ),
        authority,
    )
    assert adapted.source_identity is not None
    assert adapted.source_identity.primary_content_ref == "allowed.md"
    assert adapted.source_identity.used_content_refs == ("allowed.md",)
    assert adapted.decision.source_identity is not None
    assert adapted.decision.source_identity.primary_content_ref == "allowed.md"
    assert adapted.decision.source_identity.used_content_refs == ("allowed.md",)
    _adapted_source_identity_equal(adapted)
    assert [item.detail for item in adapted.diagnostics if item.code == "source_ref_not_allowed"] == ["foreign.md"]


def test_composer_decision_authority_rejects_duplicate_service_descriptor_id() -> None:
    base = _composer_decision_authority_from_plan(_composer_plan())
    duplicate = _service_descriptor("svc_a")
    with pytest.raises(ValueError, match="service_descriptor_id_duplicate"):
        ComposerDecisionAuthority(
            allowed_route_modes=base.allowed_route_modes,
            allowed_topic_ids=base.allowed_topic_ids,
            service_descriptors=(duplicate, duplicate),
            context_strategy=base.context_strategy,
            history_turn_count=base.history_turn_count,
            price_policy=base.price_policy,
            allowed_aspect_ids=base.allowed_aspect_ids,
        )


def test_composer_decision_authority_rejects_duplicate_source_ref() -> None:
    base = _composer_decision_authority_from_plan(_composer_plan())
    with pytest.raises(ValueError, match="allowed_source_ref_duplicate"):
        ComposerDecisionAuthority(
            allowed_route_modes=base.allowed_route_modes,
            allowed_topic_ids=base.allowed_topic_ids,
            service_descriptors=base.service_descriptors,
            allowed_source_refs=("allowed.md", "allowed.md"),
            context_strategy=base.context_strategy,
            history_turn_count=base.history_turn_count,
            price_policy=base.price_policy,
            allowed_aspect_ids=base.allowed_aspect_ids,
        )


@pytest.mark.parametrize(
    "refs,error",
    [
        (("",), "allowed_source_ref_blank"),
        ((" padded.md",), "allowed_source_ref_padded"),
        (("padded.md ",), "allowed_source_ref_padded"),
    ],
)
def test_composer_decision_authority_rejects_invalid_source_refs(refs: tuple[str, ...], error: str) -> None:
    base = _composer_decision_authority_from_plan(_composer_plan())
    with pytest.raises(ValueError, match=error):
        ComposerDecisionAuthority(
            allowed_route_modes=base.allowed_route_modes,
            allowed_topic_ids=base.allowed_topic_ids,
            service_descriptors=base.service_descriptors,
            allowed_source_refs=refs,
            context_strategy=base.context_strategy,
            history_turn_count=base.history_turn_count,
            price_policy=base.price_policy,
            allowed_aspect_ids=base.allowed_aspect_ids,
        )


@pytest.mark.parametrize(
    "active_session_service_id,error",
    [
        ("", "active_session_service_id_blank"),
        (" all_on_4", "active_session_service_id_padded"),
        ("all_on_4 ", "active_session_service_id_padded"),
    ],
)
def test_composer_decision_authority_rejects_invalid_active_session_service_id(
    active_session_service_id: str,
    error: str,
) -> None:
    base = _composer_decision_authority_from_plan(_composer_plan())
    with pytest.raises(ValueError, match=error):
        ComposerDecisionAuthority(
            allowed_route_modes=base.allowed_route_modes,
            allowed_topic_ids=base.allowed_topic_ids,
            service_descriptors=base.service_descriptors,
            active_session_service_id=active_session_service_id,
            context_strategy=base.context_strategy,
            history_turn_count=base.history_turn_count,
            price_policy=base.price_policy,
            allowed_aspect_ids=base.allowed_aspect_ids,
        )
