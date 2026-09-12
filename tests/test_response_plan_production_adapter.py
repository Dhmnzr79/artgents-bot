from __future__ import annotations

import ast
import json
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from contracts.response_plan import (
    CanonicalContactCandidate,
    ComposerResult,
    RequiredOfferConditionBlock,
    SessionKey,
)
from contracts.response_plan_adapter import (
    ResponsePlanAdapterComposerRouteAuthority,
    ResponsePlanAdapterConditionAuthority,
    ResponsePlanAdapterDeterministicRouteAuthority,
    ResponsePlanAdapterError,
    ResponsePlanAdapterMaterialAuthority,
    ResponsePlanAdapterSessionState,
    ResponsePlanAdapterSources,
    ResponsePlanAdapterTerminalAuthority,
    ResponsePlanAdapterTextualCtaAuthority,
    ResponsePlanAdapterUiAuthority,
    ResponsePlanAdapterUiWidgetAuthority,
)
from contracts.response_plan_composer import adapt_composer_json_to_decision
from contracts.response_plan import DeterministicBypassRouteAuthority, ComposerSelectedRouteAuthority
from tests.test_response_plan_composer_contract import (
    _composer_decision_authority_from_plan,
    _composer_result_from_adapted,
)
from contracts.response_schema import TargetCommercialFact, TargetOffer
from contracts.target_response_spec import TargetResponseSpec
from core.response_plan_production_adapter import (
    billing_unit_phrase,
    build_pre_composer_plan,
    format_multi_price_display,
    format_single_price_display,
)
from core.response_plan_resolver import resolve_response_plan
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui
from core.target_marketing_selector import TargetMarketingSelection
from core.target_offline_response_assembly import TargetOfflineResponseMaterials
from core.target_response_followup_materializer import TargetContentFollowup, TargetPriceFollowup, TargetResponseFollowups
from core.target_response_followup_policy import TargetResponseFollowupSelection
from core.target_response_materialization_plan import (
    TargetResponseMaterializationPlan,
    build_target_response_materialization_plan,
)
from core.turn_frame_from_raw import build_turn_frame_from_raw


ALLOWED_TOPICS = frozenset({"implantation", "prosthetics", "clinic", "doctors"})
ALLOWED_SERVICES = frozenset({"all_on_4", "implantium"})
BILLING_UNITS = (
    "tooth",
    "implant",
    "tooth_package",
    "jaw",
    "both_jaws",
    "procedure",
    "unit",
    "course",
)
CLINIC_FLOW_CASES = (
    ("sterilization", {"topic": "sterilization"}),
    ("clinic_technology", {"topic": "unknown_clinic_theme"}),
    ("doctors_general", {"topic": "general_doctors_inquiry"}),
    ("installment", {"topic": "unknown"}),
    ("general_warranty", {"topic": None}),
    ("consultation_overview", {"topic": "unknown", "aspects": ["overview"], "primary_aspect": "overview"}),
    ("new_clinic_theme", {"topic": "brand_new_theme"}),
)


@dataclass(frozen=True, slots=True)
class _BoundPackageShim:
    spec: TargetResponseSpec
    package: _PackageShim
    selected_cta_key: str | None = None


@dataclass(frozen=True, slots=True)
class _PackageShim:
    materials: TargetOfflineResponseMaterials
    plan: TargetResponseMaterializationPlan
    selected_followups: TargetResponseFollowupSelection
    navigation_followups: tuple[object, ...] = ()


from tests.test_response_plan_composer_contract import _json as _composer_json_payload


def _composer_json(**overrides: object) -> str:
    return _composer_json_payload(**overrides)


def _turn_frame(**overrides: object):
    payload: dict[str, object] = {
        "route": "content",
        "topic": "implantation",
        "topic_confidence": 0.9,
        "aspects": ["overview"],
        "primary_aspect": "overview",
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=ALLOWED_TOPICS,
        allowed_service_ids=ALLOWED_SERVICES,
    )


def _fact(
    fact_id: str,
    *,
    text: str | None = None,
    service_ids: tuple[str, ...] = (),
    topics: tuple[str, ...] = (),
    kind: str = "commercial",
) -> TargetCommercialFact:
    return TargetCommercialFact.model_validate(
        {
            "id": fact_id,
            "kind": kind,
            "catalog_label": fact_id,
            "text_fact": text or f"Exact {fact_id}.",
            "render_mode": "strict",
            "active": True,
            "allowed_service_ids": list(service_ids),
            "allowed_topics": list(topics),
            "incompatible_with": [],
        }
    )


def _offer(
    offer_id: str,
    *,
    amount: int = 120_000,
    active: bool = True,
    label: str | None = None,
    price_mode: str = "fixed",
    billing_unit: str = "jaw",
    currency: str = "RUB",
) -> TargetOffer:
    if price_mode == "fixed":
        price = {
            "mode": "fixed",
            "amount": amount,
            "currency": currency,
            "billing_unit": billing_unit,
        }
    elif price_mode == "from":
        price = {
            "mode": "from",
            "min_amount": amount,
            "currency": currency,
            "billing_unit": billing_unit,
        }
    elif price_mode == "range":
        price = {
            "mode": "range",
            "min_amount": amount,
            "max_amount": amount + 10_000,
            "currency": currency,
            "billing_unit": billing_unit,
        }
    else:
        price = {"mode": "no_public_price", "approved_text": "По запросу"}
    return TargetOffer.model_validate(
        {
            "offer_id": offer_id,
            "service_id": "all_on_4",
            "active": active,
            "price": price,
            "package": {"label": label or f"Package {offer_id}", "includes": ["item"]},
            "fact_refs": [],
            "followups": [],
        }
    )


def _materials(
    *,
    offers: tuple[TargetOffer, ...] = (),
    facts: tuple[TargetCommercialFact, ...] = (),
    marketing: TargetMarketingSelection | None = None,
) -> TargetOfflineResponseMaterials:
    return TargetOfflineResponseMaterials(
        service_id="all_on_4",
        service=None,
        selected_brand_id=None,
        brand=None,
        matched_rule_id=None,
        max_options=3,
        offers=offers,
        doctors=(),
        selected_content_ref="content.md",
        marketing_selection=marketing
        or TargetMarketingSelection(
            applied_scenarios=(),
            selected_refs=(),
            amplifier_refs=(),
            cta_key="book_consultation",
        ),
        commercial_facts=facts,
        external_source_refs=(),
        consultation_close=None,
        marketing_slots_used=0,
        amplifier_slots_used=0,
    )


def _bound_package(
    *,
    spec: TargetResponseSpec,
    materials: TargetOfflineResponseMaterials,
    selected_cta_key: str | None = None,
    navigation: tuple[object, ...] = (),
    selected_followups: TargetResponseFollowupSelection | None = None,
) -> _BoundPackageShim:
    followups = selected_followups or TargetResponseFollowupSelection(source=None, content=(), price=())
    plan = build_target_response_materialization_plan(
        materials,
        required_components=spec.required_components,
    )
    package = _PackageShim(
        materials=materials,
        plan=plan,
        selected_followups=followups,
        navigation_followups=navigation,
    )
    return _BoundPackageShim(
        spec=spec,
        package=package,
        selected_cta_key=selected_cta_key,
    )


def _spec(**overrides: object) -> TargetResponseSpec:
    payload = {
        "response_mode": "answer",
        "service_id": "all_on_4",
        "tone_key": "commercial_warm",
        "allowed_topics": ("implantation",),
        "required_components": ("content",),
    }
    payload.update(overrides)
    return TargetResponseSpec(**payload)


def _material_authority(
    *,
    client_id: str = "demo",
    bound_package: object,
) -> ResponsePlanAdapterMaterialAuthority:
    return ResponsePlanAdapterMaterialAuthority(
        source_client_id=client_id,
        bound_package=bound_package,
    )


def _terminal_authorities() -> tuple[ResponsePlanAdapterTerminalAuthority, ...]:
    return (
        _contacts_terminal(),
        _admin_terminal("standard"),
        _admin_terminal("medical_terminal"),
    )


def _sources(**overrides: object) -> ResponsePlanAdapterSources:
    spec = _spec()
    materials = _materials(
        offers=(_offer("offer_a"),),
        facts=(
            _fact("installment_12", service_ids=("all_on_4",)),
            _fact("promo_spring"),
            _fact("amp_painless"),
            _fact("implant_warranty", service_ids=("all_on_4",), kind="warranty"),
            _fact("clinic_warranty", topics=("clinic",), kind="warranty"),
        ),
        marketing=TargetMarketingSelection(
            applied_scenarios=(),
            selected_refs=("fact:promo_spring",),
            amplifier_refs=("fact:amp_painless",),
            cta_key="book_consultation",
            service_value_ref="fact:service_value_implant",
        ),
    )
    materials = replace(
        materials,
        commercial_facts=(
            *materials.commercial_facts,
            _fact("service_value_implant", service_ids=("all_on_4",), text="Имплантация под ключ"),
        ),
    )
    bound = _bound_package(spec=spec, materials=materials, selected_cta_key="book_consultation")
    payload = {
        "session_key": SessionKey(client_id="demo", sid="s1"),
        "context_strategy": "full_context",
        "turn_frame": _turn_frame(service_id="all_on_4"),
        "material_authority": _material_authority(bound_package=bound),
        "allowed_topic_ids": tuple(sorted(ALLOWED_TOPICS)),
        "route_authority": ResponsePlanAdapterComposerRouteAuthority(),
        "terminal_authorities": _terminal_authorities(),
    }
    payload.update(overrides)
    return ResponsePlanAdapterSources(**payload)


def _terminal_base_sources(**overrides: object) -> ResponsePlanAdapterSources:
    payload = {
        "session_key": SessionKey(client_id="demo", sid="s1"),
        "context_strategy": "full_context",
        "turn_frame": _turn_frame(service_id=None, topic=None),
        "material_authority": None,
        "allowed_topic_ids": tuple(sorted(ALLOWED_TOPICS)),
        "route_authority": ResponsePlanAdapterDeterministicRouteAuthority(
            route="ANSWER",
            mode="contacts",
        ),
        "terminal_authorities": (_contacts_terminal(),),
    }
    payload.update(overrides)
    return ResponsePlanAdapterSources(**payload)


def _clinic_sources(**turn_overrides: object) -> ResponsePlanAdapterSources:
    spec = _spec(
        service_id=None,
        allowed_topics=("clinic", "implantation", "doctors"),
        required_components=("content",),
    )
    materials = _materials(
        facts=(
            _fact("installment_12"),
            _fact("clinic_warranty", topics=("clinic",), kind="warranty"),
            _fact("implant_warranty", service_ids=("all_on_4",), kind="warranty"),
        ),
    )
    bound = _bound_package(spec=spec, materials=materials)
    turn_payload = {"service_id": None}
    turn_payload.update(turn_overrides)
    return _sources(
        turn_frame=_turn_frame(**turn_payload),
        material_authority=_material_authority(bound_package=bound),
    )


def _run_flow(
    sources: ResponsePlanAdapterSources,
    *,
    raw_json: str | None = None,
) -> tuple[object, object, object, str, object]:
    plan = build_pre_composer_plan(sources)
    if isinstance(plan.route_authority, DeterministicBypassRouteAuthority):
        composer = None
    else:
        authority = _composer_decision_authority_from_plan(plan)
        if raw_json is not None:
            adapted = adapt_composer_json_to_decision(raw_json, authority)
        else:
            adapted = adapt_composer_json_to_decision(
                _composer_json(
                    requested_aspect_ids=["price"] if plan.price_plan.kind != "none" else [],
                ),
                authority,
            )
        composer = _composer_result_from_adapted(adapted)
    resolved = resolve_response_plan(plan, composer)
    text = render_response_text(resolved)
    ui = project_response_ui(resolved)
    return plan, composer, resolved, text, ui


def _admin_terminal(mode: str = "standard") -> ResponsePlanAdapterTerminalAuthority:
    return ResponsePlanAdapterTerminalAuthority(
        source_client_id="demo",
        route="ADMIN",
        mode=mode,
        authority="governed_ui" if mode == "standard" else "deterministic_policy_terminal",
        display_text=f"ADMIN {mode}",
        canonical_contact=CanonicalContactCandidate(source_client_id="demo", phone="+7 (495) 000-00-00"),
    )


def _contacts_terminal() -> ResponsePlanAdapterTerminalAuthority:
    return ResponsePlanAdapterTerminalAuthority(
        source_client_id="demo",
        route="ANSWER",
        mode="contacts",
        authority="contacts",
        display_text="Контакты demo",
        canonical_contact=CanonicalContactCandidate(source_client_id="demo", phone="+7 (495) 000-00-00"),
    )


def test_service_answer_scope_and_plan() -> None:
    plan = build_pre_composer_plan(_sources())
    assert plan.response_scope == "service"
    assert plan.selected_service_id == "all_on_4"
    assert plan.selected_topic_id is None


def test_topic_answer_without_service() -> None:
    spec = _spec(service_id=None, allowed_topics=("implantation",), required_components=("content",))
    materials = _materials()
    bound = _bound_package(spec=spec, materials=materials)
    plan = build_pre_composer_plan(
        _sources(
            turn_frame=_turn_frame(service_id=None, topic="implantation"),
            material_authority=_material_authority(bound_package=bound),
        )
    )
    assert plan.response_scope == "topic"
    assert plan.selected_topic_id == "implantation"
    assert plan.selected_service_id is None


def test_clinic_wide_answer_without_service() -> None:
    spec = _spec(service_id=None, allowed_topics=("clinic",), required_components=("content",))
    materials = _materials()
    bound = _bound_package(spec=spec, materials=materials)
    plan = build_pre_composer_plan(
        _sources(
            turn_frame=_turn_frame(service_id=None, topic=None),
            material_authority=_material_authority(bound_package=bound),
        )
    )
    assert plan.response_scope == "clinic"
    assert plan.selected_service_id is None
    assert plan.selected_topic_id is None


def test_unknown_topic_falls_back_to_clinic_scope() -> None:
    plan = build_pre_composer_plan(_clinic_sources(topic="sterilization"))
    assert plan.response_scope == "clinic"
    assert plan.selected_topic_id is None


def test_stale_session_service_does_not_become_selected_service() -> None:
    sources = _clinic_sources(topic=None).model_copy(
        update={"session_state": ResponsePlanAdapterSessionState(last_service_id="all_on_4")}
    )
    plan = build_pre_composer_plan(sources)
    assert plan.response_scope == "clinic"
    assert plan.selected_service_id is None
    assert plan.active_session_service_id == "all_on_4"


@pytest.mark.parametrize("case_name,turn_overrides", CLINIC_FLOW_CASES)
def test_clinic_general_questions_do_not_fail_adapter(case_name: str, turn_overrides: dict) -> None:
    sources = _clinic_sources(**turn_overrides)
    plan, _, resolved, text, _ = _run_flow(
        sources,
        raw_json=_composer_json(
            route="ANSWER",
            mode="standard",
            patient_text=f"Ответ на {case_name}",
            requested_fact_ids=["installment_12"] if case_name == "installment" else [],
        ),
    )
    assert plan.response_scope == "clinic"
    assert plan.selected_service_id is None
    assert plan.service_value_candidate is None
    assert resolved.patient_text == f"Ответ на {case_name}"
    assert text
    assert "implant_warranty" not in resolved.finalized_commercial_ids.requested_fact_ids
    if case_name == "installment":
        assert resolved.finalized_commercial_ids.requested_fact_ids == ("installment_12",)


def test_offers_on_non_price_turn_do_not_create_price_plan() -> None:
    plan = build_pre_composer_plan(_sources())
    assert plan.price_plan.kind == "none"


@pytest.mark.parametrize("billing_unit", BILLING_UNITS)
def test_single_price_display_contains_billing_unit(billing_unit: str) -> None:
    offer = _offer("offer_single", amount=318_000, label="All-on-4 Implantium", billing_unit=billing_unit)
    display = format_single_price_display(offer)
    assert "318 000 ₽" in display
    assert billing_unit_phrase(billing_unit) in display
    assert "All-on-4 Implantium" in display


def test_fixed_single_price_plan() -> None:
    spec = _spec(required_components=("price",))
    offer = _offer("offer_single", amount=318_000, label="All-on-4 Implantium", billing_unit="jaw")
    materials = _materials(offers=(offer,))
    bound = _bound_package(spec=spec, materials=materials)
    plan = build_pre_composer_plan(
        _sources(
            material_authority=_material_authority(bound_package=bound),
        )
    )
    assert plan.price_plan.kind == "single"
    assert plan.price_plan.single is not None
    assert plan.price_plan.single.display_text == format_single_price_display(offer)
    assert "за одну челюсть" in plan.price_plan.single.display_text


def test_deterministic_combined_multi_price_block() -> None:
    spec = _spec(required_components=("price",))
    offers = (_offer("offer_b", amount=150_000), _offer("offer_a", amount=100_000))
    materials = _materials(offers=offers)
    bound = _bound_package(spec=spec, materials=materials)
    plan = build_pre_composer_plan(
        _sources(material_authority=_material_authority(bound_package=bound))
    )
    assert plan.price_plan.kind == "multi"
    assert plan.price_plan.multi is not None
    assert plan.price_plan.multi.offer_ids == ("offer_b", "offer_a")
    assert plan.price_plan.multi.display_text == format_multi_price_display(offers)
    for offer in offers:
        assert format_single_price_display(offer) in plan.price_plan.multi.display_text


def test_mixed_billing_units_fail_closed() -> None:
    spec = _spec(required_components=("price",))
    materials = _materials(
        offers=(
            _offer("offer_a", billing_unit="jaw"),
            _offer("offer_b", billing_unit="tooth"),
        )
    )
    bound = _bound_package(spec=spec, materials=materials)
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(_sources(material_authority=_material_authority(bound_package=bound)))
    assert exc.value.code == "adapter_price_shape_unsupported"


def test_mixed_currencies_fail_closed() -> None:
    spec = _spec(required_components=("price",))
    materials = _materials(
        offers=(
            _offer("offer_a", currency="RUB"),
            _offer("offer_b", currency="EUR"),
        )
    )
    bound = _bound_package(spec=spec, materials=materials)
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(_sources(material_authority=_material_authority(bound_package=bound)))
    assert exc.value.code == "adapter_price_shape_unsupported"


def test_unknown_billing_unit_fail_closed() -> None:
    with pytest.raises(ResponsePlanAdapterError) as exc:
        billing_unit_phrase("invalid_unit")
    assert exc.value.code == "adapter_price_metadata_incomplete"


@pytest.mark.parametrize("price_mode", ["from", "range", "no_public_price"])
def test_unsupported_price_shapes_fail_closed(price_mode: str) -> None:
    spec = _spec(required_components=("price",))
    materials = _materials(offers=(_offer("offer_x", price_mode=price_mode),))
    bound = _bound_package(spec=spec, materials=materials)
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(_sources(material_authority=_material_authority(bound_package=bound)))
    assert exc.value.code == "adapter_price_shape_unsupported"


def test_missing_active_offers_fail_closed_for_price_intent() -> None:
    spec = _spec(required_components=("price",))
    materials = _materials(offers=(_offer("offer_x", active=False),))
    bound = _bound_package(spec=spec, materials=materials)
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(_sources(material_authority=_material_authority(bound_package=bound)))
    assert exc.value.code == "adapter_price_intent_without_offer"


def test_foreign_material_source_offers_fail_closed() -> None:
    bound = _bound_package(spec=_spec(), materials=_materials(offers=(_offer("offer_a"),)))
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(
            _sources(material_authority=_material_authority(client_id="other", bound_package=bound))
        )
    assert exc.value.code == "adapter_client_mismatch"


def test_foreign_material_source_facts_fail_closed() -> None:
    materials = _materials(facts=(_fact("promo_spring"),))
    bound = _bound_package(spec=_spec(), materials=materials)
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(
            _sources(material_authority=_material_authority(client_id="other", bound_package=bound))
        )
    assert exc.value.code == "adapter_client_mismatch"


def test_foreign_material_source_service_value_fail_closed() -> None:
    materials = _materials(
        facts=(_fact("service_value_implant", service_ids=("all_on_4",)),),
        marketing=TargetMarketingSelection(
            applied_scenarios=(),
            selected_refs=(),
            amplifier_refs=(),
            cta_key="",
            service_value_ref="fact:service_value_implant",
        ),
    )
    bound = _bound_package(spec=_spec(), materials=materials)
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(
            _sources(material_authority=_material_authority(client_id="other", bound_package=bound))
        )
    assert exc.value.code == "adapter_client_mismatch"


def test_foreign_material_source_followups_fail_closed() -> None:
    followups = TargetResponseFollowupSelection(
        source="content",
        content=(TargetContentFollowup(id="a", label="A", ref="ref:a", source_content_ref="content.md"),),
        price=(),
    )
    bound = _bound_package(spec=_spec(), materials=_materials(), selected_followups=followups)
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(
            _sources(material_authority=_material_authority(client_id="other", bound_package=bound))
        )
    assert exc.value.code == "adapter_client_mismatch"


def test_incoherent_required_components_fail_closed() -> None:
    spec = _spec(required_components=("content",))
    materials = _materials()
    bound = _bound_package(spec=spec, materials=materials)
    broken_plan = replace(
        bound.package.plan,
        required_components=("price",),
    )
    broken_package = replace(bound.package, plan=broken_plan)
    broken_bound = replace(bound, package=broken_package)
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(_sources(material_authority=_material_authority(bound_package=broken_bound)))
    assert exc.value.code == "adapter_package_source_incoherent"


def test_incoherent_offer_ids_fail_closed() -> None:
    spec = _spec()
    materials = _materials(offers=(_offer("offer_a"),))
    bound = _bound_package(spec=spec, materials=materials)
    broken_plan = replace(bound.package.plan, offer_ids=("other_offer",))
    broken_bound = replace(bound, package=replace(bound.package, plan=broken_plan))
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(_sources(material_authority=_material_authority(bound_package=broken_bound)))
    assert exc.value.code == "adapter_package_source_incoherent"


def test_incoherent_non_price_offer_ids_fail_closed() -> None:
    spec = _spec(required_components=("content",))
    materials = _materials(offers=(_offer("offer_a"),))
    bound = _bound_package(spec=spec, materials=materials)
    broken_plan = replace(bound.package.plan, offer_ids=("offer_a",))
    broken_bound = replace(bound, package=replace(bound.package, plan=broken_plan))
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(_sources(material_authority=_material_authority(bound_package=broken_bound)))
    assert exc.value.code == "adapter_package_source_incoherent"


def test_incoherent_commercial_fact_ids_fail_closed() -> None:
    spec = _spec()
    materials = _materials(facts=(_fact("promo_spring"),))
    bound = _bound_package(spec=spec, materials=materials)
    broken_plan = replace(bound.package.plan, commercial_fact_ids=("missing_fact",))
    broken_bound = replace(bound, package=replace(bound.package, plan=broken_plan))
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(_sources(material_authority=_material_authority(bound_package=broken_bound)))
    assert exc.value.code == "adapter_package_source_incoherent"


def test_incoherent_materials_snapshot_fail_closed() -> None:
    spec = _spec(required_components=("price",))
    materials = _materials(offers=(_offer("offer_a"),))
    bound = _bound_package(spec=spec, materials=materials)
    new_materials = _materials(offers=(_offer("offer_b"),))
    broken_bound = replace(bound, package=replace(bound.package, materials=new_materials))
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(_sources(material_authority=_material_authority(bound_package=broken_bound)))
    assert exc.value.code == "adapter_package_source_incoherent"


def test_conditions_only_from_typed_authority() -> None:
    spec = _spec(required_components=("price",))
    materials = _materials(offers=(_offer("offer_single"),))
    bound = _bound_package(spec=spec, materials=materials)
    authority = ResponsePlanAdapterConditionAuthority(
        source_client_id="demo",
        required_conditions=(
            RequiredOfferConditionBlock(
                source_client_id="demo",
                condition_id="per_jaw",
                display_text="Цена указана за челюсть",
            ),
        ),
    )
    plan = build_pre_composer_plan(
        _sources(
            material_authority=_material_authority(bound_package=bound),
            condition_authority=authority,
        )
    )
    assert plan.required_offer_conditions[0].condition_id == "per_jaw"


def test_promo_and_amplifier_role_mapping() -> None:
    plan = build_pre_composer_plan(_sources())
    promo = next(item for item in plan.commercial_facts if item.fact_id == "promo_spring")
    amp = next(item for item in plan.commercial_facts if item.fact_id == "amp_painless")
    assert promo.allowed_roles == ("requested_fact", "promo")
    assert amp.allowed_roles == ("requested_fact", "automatic_amplifier")
    assert promo.source_client_id == "demo"


def test_requested_fact_remains_model_owned_in_flow() -> None:
    _, _, resolved, _, _ = _run_flow(
        _sources(),
        raw_json=_composer_json(
            route="ANSWER",
            mode="standard",
            patient_text="Ответ",
            requested_fact_ids=["installment_12"],
        ),
    )
    assert resolved.finalized_commercial_ids.requested_fact_ids == ("installment_12",)


def test_automatic_warranty_role_is_explicit_only() -> None:
    plan = build_pre_composer_plan(_sources())
    warranty = next(item for item in plan.commercial_facts if item.fact_id == "implant_warranty")
    assert warranty.explicit_only is True
    assert warranty.allowed_roles == ("requested_fact",)


def test_service_value_exact_lookup() -> None:
    plan = build_pre_composer_plan(_sources())
    assert plan.service_value_candidate is not None
    assert plan.service_value_candidate.fact_id == "service_value_implant"
    assert plan.service_value_candidate.source_client_id == "demo"


def test_missing_service_value_source_fails_closed() -> None:
    materials = _materials(
        marketing=TargetMarketingSelection(
            applied_scenarios=(),
            selected_refs=(),
            amplifier_refs=(),
            cta_key="",
            service_value_ref="fact:missing_value",
        )
    )
    bound = _bound_package(spec=_spec(), materials=materials)
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(_sources(material_authority=_material_authority(bound_package=bound)))
    assert exc.value.code == "adapter_service_value_source_missing"


def test_cta_key_does_not_become_text_without_authority() -> None:
    plan = build_pre_composer_plan(_sources())
    assert plan.textual_cta_candidate is None


def test_quick_reply_dedup_preserves_first_owner() -> None:
    followups = TargetResponseFollowupSelection(
        source="content",
        content=(
            TargetContentFollowup(id="a", label="Label A", ref="ref:shared", source_content_ref="content.md"),
            TargetContentFollowup(id="b", label="Label B", ref="ref:shared", source_content_ref="content.md"),
        ),
        price=(),
    )
    bound = _bound_package(spec=_spec(), materials=_materials(), selected_followups=followups)
    plan = build_pre_composer_plan(_sources(material_authority=_material_authority(bound_package=bound)))
    assert len(plan.ui_candidates.quick_replies) == 1
    assert plan.ui_candidates.quick_replies[0].source_client_id == "demo"


@pytest.mark.parametrize(
    "override",
    [
        {"condition_authority": ResponsePlanAdapterConditionAuthority(source_client_id="other", required_conditions=())},
        {
            "terminal_authorities": (
                ResponsePlanAdapterTerminalAuthority(
                    source_client_id="other",
                    route="ADMIN",
                    mode="standard",
                    authority="governed_ui",
                    display_text="ADMIN",
                ),
                *_terminal_authorities()[1:],
            )
        },
        {"textual_cta_authority": ResponsePlanAdapterTextualCtaAuthority(source_client_id="other", text="CTA")},
        {
            "ui_authority": ResponsePlanAdapterUiAuthority(
                source_client_id="other",
                widget=ResponsePlanAdapterUiWidgetAuthority(source_client_id="other", widget_offer_id="offer_a"),
            )
        },
    ],
)
def test_client_mismatch_fail_closed(override: dict) -> None:
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(_sources(**override))
    assert exc.value.code == "adapter_client_mismatch"


def test_admin_without_terminal_fail_closed() -> None:
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(
            _terminal_base_sources(
                route_authority=ResponsePlanAdapterDeterministicRouteAuthority(
                    route="ADMIN",
                    mode="standard",
                ),
                terminal_authorities=(),
            )
        )
    assert exc.value.code == "adapter_terminal_authority_invalid"


def test_answer_standard_without_material_fail_closed() -> None:
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(_sources(material_authority=None))
    assert exc.value.code == "adapter_material_authority_required"


def test_terminal_with_material_forbidden() -> None:
    bound = _bound_package(spec=_spec(), materials=_materials())
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(
            _terminal_base_sources(
                material_authority=_material_authority(bound_package=bound),
            )
        )
    assert exc.value.code == "adapter_material_authority_forbidden"


def test_composer_path_requires_terminal_authorities() -> None:
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(_sources(terminal_authorities=()))
    assert exc.value.code == "adapter_terminal_authority_invalid"


@pytest.mark.parametrize(
    "route,mode,terminal_factory,needs_envelope",
    [
        ("ANSWER", "standard", None, True),
        ("ANSWER", "contacts", _contacts_terminal, False),
        ("ADMIN", "standard", lambda: _admin_terminal("standard"), False),
        ("ADMIN", "medical_terminal", lambda: _admin_terminal("medical_terminal"), False),
        ("CLARIFY", "standard", None, True),
    ],
)
def test_route_mode_end_to_end_matrix(
    route: str,
    mode: str,
    terminal_factory,
    needs_envelope: bool,
) -> None:
    terminal = terminal_factory() if terminal_factory else None
    if route == "ANSWER" and mode == "standard":
        sources = _sources()
    elif route == "CLARIFY":
        spec = _spec(service_id=None, allowed_topics=("clinic",), required_components=("content",))
        materials = _materials()
        bound = _bound_package(spec=spec, materials=materials)
        sources = _sources(
            turn_frame=_turn_frame(service_id=None, topic=None),
            material_authority=_material_authority(bound_package=bound),
        )
    else:
        sources = _terminal_base_sources(
            route_authority=ResponsePlanAdapterDeterministicRouteAuthority(route=route, mode=mode),
            terminal_authorities=(terminal,) if terminal else (),
        )
    plan = build_pre_composer_plan(sources)
    composer = None
    if needs_envelope:
        composer = _composer_result_from_adapted(
            adapt_composer_json_to_decision(
                _composer_json(route=route, mode=mode, patient_text="Текст"),
                _composer_decision_authority_from_plan(plan),
            )
        )
    resolved = resolve_response_plan(plan, composer)
    text = render_response_text(resolved)
    ui = project_response_ui(resolved)
    assert text
    assert ui is not None
    if route == "CLARIFY":
        assert resolved.session_delta.clarify_pending is True
    if route in {"ADMIN", "ANSWER"} and mode == "contacts":
        assert resolved.price_block is None
        assert resolved.finalized_commercial_ids.price_offer_ids == ()


def test_spec_turn_conflict() -> None:
    spec = _spec(service_id="implantium")
    bound = _bound_package(spec=spec, materials=_materials())
    with pytest.raises(ResponsePlanAdapterError) as exc:
        build_pre_composer_plan(
            _sources(
                turn_frame=_turn_frame(service_id="all_on_4"),
                material_authority=_material_authority(bound_package=bound),
            )
        )
    assert exc.value.code == "adapter_spec_turn_conflict"


def test_equal_input_equal_output() -> None:
    sources = _sources()
    assert build_pre_composer_plan(sources) == build_pre_composer_plan(sources)


def test_full_flow_price_answer() -> None:
    spec = _spec(required_components=("price",))
    offer = _offer("offer_single", amount=318_000, label="All-on-4 Implantium", billing_unit="jaw")
    materials = _materials(offers=(offer,))
    bound = _bound_package(spec=spec, materials=materials)
    _, _, resolved, text, _ = _run_flow(
        _sources(material_authority=_material_authority(bound_package=bound)),
        raw_json=_composer_json(
            route="ANSWER",
            mode="standard",
            patient_text="Цена ниже.",
            requested_aspect_ids=["price"],
        ),
    )
    assert resolved.price_block is not None
    assert "за одну челюсть" in text


def test_adapter_static_forbidden_patterns() -> None:
    repo = Path(__file__).resolve().parents[1]
    production = repo / "core" / "response_plan_production_adapter.py"
    text = production.read_text(encoding="utf-8")
    assert "direct_fact_ids" not in text
    assert "one_call_presentation_pass" not in text
    assert "import re" not in text
    assert "TargetUnverifiedComposedResponse" not in text


def test_production_adapter_has_no_regex_imports() -> None:
    module = Path(__file__).resolve().parents[1] / "core" / "response_plan_production_adapter.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "re" not in imported


def test_structural_package_non_price_with_offers() -> None:
    spec = _spec(required_components=("content",))
    materials = _materials(offers=(_offer("offer_a"), _offer("offer_b")))
    real_plan = build_target_response_materialization_plan(
        materials,
        required_components=("content",),
    )
    assert real_plan.offer_ids == ()
    bound = _bound_package(spec=spec, materials=materials)
    plan, _, resolved, text, _ = _run_flow(
        _sources(
            turn_frame=_turn_frame(service_id="all_on_4"),
            material_authority=_material_authority(bound_package=bound),
        )
    )
    assert plan.response_scope == "service"
    assert plan.price_plan.kind == "none"
    assert resolved.price_block is None
    assert text


def test_structural_package_price() -> None:
    spec = _spec(required_components=("price",))
    offer = _offer("offer_single", amount=318_000, label="All-on-4 Implantium", billing_unit="jaw")
    materials = _materials(offers=(offer,))
    real_plan = build_target_response_materialization_plan(
        materials,
        required_components=("price",),
    )
    assert real_plan.offer_ids == ("offer_single",)
    bound = _bound_package(spec=spec, materials=materials)
    plan, _, resolved, text, _ = _run_flow(
        _sources(
            material_authority=_material_authority(bound_package=bound),
        ),
        raw_json=_composer_json(
            route="ANSWER",
            mode="standard",
            patient_text="Цена.",
            requested_aspect_ids=["price"],
        ),
    )
    assert plan.price_plan.kind == "single"
    assert resolved.price_block is not None
    assert resolved.price_block.offer_ids == ("offer_single",)
    assert "за одну челюсть" in text


def test_structural_package_clinic_content_flow() -> None:
    spec = TargetResponseSpec(
        response_mode="answer",
        service_id=None,
        tone_key="commercial_warm",
        allowed_topics=("clinic",),
        required_components=("content",),
    )
    materials = replace(_materials(), service_id=None)
    bound = _bound_package(spec=spec, materials=materials)
    assert bound.package.materials.service_id is None
    assert bound.package.plan.offer_ids == ()
    plan, _, resolved, text, _ = _run_flow(
        _sources(
            turn_frame=_turn_frame(service_id=None, topic=None),
            material_authority=_material_authority(bound_package=bound),
        ),
        raw_json=_composer_json(
            route="ANSWER",
            mode="standard",
            patient_text="Общий ответ о клинике.",
        ),
    )
    assert plan.response_scope == "clinic"
    assert plan.selected_service_id is None
    assert plan.price_plan.kind == "none"
    assert resolved.patient_text == "Общий ответ о клинике."
    assert resolved.finalized_commercial_ids.price_offer_ids == ()
    assert text


def test_structural_package_clinic_doctors_flow() -> None:
    spec = TargetResponseSpec(
        response_mode="answer",
        service_id=None,
        tone_key="commercial_warm",
        allowed_topics=("doctors",),
        required_components=("doctors",),
    )
    materials = replace(_materials(), service_id=None)
    bound = _bound_package(spec=spec, materials=materials)
    assert bound.package.materials.service_id is None
    plan, _, resolved, text, _ = _run_flow(
        _sources(
            turn_frame=_turn_frame(service_id=None, topic="general_doctors_inquiry"),
            material_authority=_material_authority(bound_package=bound),
        ),
        raw_json=_composer_json(
            route="ANSWER",
            mode="standard",
            patient_text="Ответ о врачах.",
        ),
    )
    assert plan.response_scope == "clinic"
    assert plan.selected_service_id is None
    assert resolved.patient_text == "Ответ о врачах."
    assert text


def test_contacts_terminal_without_package_end_to_end() -> None:
    plan, composer, resolved, text, ui = _run_flow(_terminal_base_sources())
    assert composer is None
    assert isinstance(plan.route_authority, DeterministicBypassRouteAuthority)
    assert plan.price_plan.kind == "none"
    assert plan.commercial_facts == ()
    assert resolved.terminal_text == "Контакты demo"
    assert text == "Контакты demo"
    assert ui.contact is not None


def test_admin_terminal_without_package_end_to_end() -> None:
    plan, composer, resolved, text, _ = _run_flow(
        _terminal_base_sources(
            route_authority=ResponsePlanAdapterDeterministicRouteAuthority(
                route="ADMIN",
                mode="standard",
            ),
            terminal_authorities=(_admin_terminal("standard"),),
        )
    )
    assert composer is None
    assert isinstance(plan.route_authority, DeterministicBypassRouteAuthority)
    assert plan.commercial_facts == ()
    assert resolved.terminal_text == "ADMIN standard"
    assert resolved.finalized_commercial_ids.price_offer_ids == ()
    assert text == "ADMIN standard"


def test_clarify_without_package_end_to_end() -> None:
    spec = _spec(service_id=None, allowed_topics=("clinic",), required_components=("content",))
    materials = _materials()
    bound = _bound_package(spec=spec, materials=materials)
    plan, composer, resolved, text, _ = _run_flow(
        _sources(
            turn_frame=_turn_frame(service_id=None, topic=None),
            material_authority=_material_authority(bound_package=bound),
        ),
        raw_json=_composer_json(route="CLARIFY", mode="standard", patient_text="Уточните вопрос."),
    )
    assert composer is not None
    assert isinstance(plan.route_authority, ComposerSelectedRouteAuthority)
    assert plan.price_plan.kind == "none"
    assert resolved.route == "CLARIFY"
    assert resolved.session_delta.clarify_pending is True
    assert resolved.finalized_commercial_ids.price_offer_ids == ()
    assert resolved.finalized_commercial_ids.promo_fact_ids == ()
    assert text == "Уточните вопрос."


def test_navigation_followups_missing_attribute_returns_empty_tuple() -> None:
    from core.response_plan_production_adapter import _navigation_followups

    package_without_attr = type(
        "PackageWithoutNavigation",
        (),
        {"materials": object(), "plan": object(), "selected_followups": object()},
    )()
    bound = type("BoundWithoutNavigation", (), {"package": package_without_attr})()
    assert _navigation_followups(bound) == ()


def test_navigation_followups_preserves_existing_order() -> None:
    from core.response_plan_production_adapter import _navigation_followups
    from core.target_client_ui_nav import TargetNavigationFollowup

    nav_a = TargetNavigationFollowup(label="Nav A", ref="nav:a")
    nav_b = TargetNavigationFollowup(label="Nav B", ref="nav:b")
    package = _PackageShim(
        materials=object(),
        plan=object(),
        selected_followups=object(),
        navigation_followups=(nav_a, nav_b),
    )
    bound = _BoundPackageShim(spec=object(), package=package)
    assert _navigation_followups(bound) == (nav_a, nav_b)
