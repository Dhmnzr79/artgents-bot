from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from contracts.response_schema import (
    TargetBrand,
    TargetCommercialFact,
    TargetOffer,
    TargetService,
)
from contracts.service_consultation import ServiceConsultationValue
from core.service_data_context import ServiceDoctorContext
from core.target_marketing_selector import TargetMarketingSelection
from core.target_offline_response_assembly import TargetOfflineResponseMaterials
from core.target_response_materialization_plan import (
    TargetResponseMaterializationPlan,
    TargetResponseMaterializationPlanError,
    build_target_response_materialization_plan,
)


def _service(*, content_ref: str | None = "service_one.md") -> TargetService:
    return TargetService.model_validate(
        {
            "name": "Service One",
            "aliases": ["one"],
            "family": "implantology",
            "roles": ["protocol"],
            "active": True,
            "content_ref": content_ref,
            "selection": {"mode": "direct"},
            "options": [],
        }
    )


def _offer(offer_id: str, *, brand_id: str | None = None) -> TargetOffer:
    payload: dict[str, object] = {
        "offer_id": offer_id,
        "service_id": "service_one",
        "active": True,
        "price": {
            "mode": "fixed",
            "amount": 120_000,
            "currency": "RUB",
            "billing_unit": "jaw",
        },
        "package": {"label": "Exact package", "includes": ["Exact include"]},
        "payment_stages": [
            {"label": "Stage 1", "amount": 70_000, "currency": "RUB"},
            {"label": "Stage 2", "amount": 50_000, "currency": "RUB"},
        ],
        "fact_refs": ["fact_one"],
        "followups": [
            {"id": "stages", "label": "Stages", "action": "price_aspect"}
        ],
    }
    if brand_id is not None:
        payload["brand_id"] = brand_id
    return TargetOffer.model_validate(payload)


def _doctor(doctor_id: str) -> ServiceDoctorContext:
    return ServiceDoctorContext(
        doctor_id=doctor_id,
        name=f"Doctor {doctor_id}",
        position="Implantologist",
        experience_years=17,
        profile_ref=f"kb:{doctor_id}.md#profile",
    )


def _materials(
    *,
    content_ref: str | None = "service_one.md",
    offers: tuple[TargetOffer, ...] | None = None,
    doctors: tuple[ServiceDoctorContext, ...] | None = None,
    branded: bool = False,
    include_consultation: bool = True,
) -> TargetOfflineResponseMaterials:
    if offers is None:
        offers = (_offer("offer_b"), _offer("offer_a"))
    if doctors is None:
        doctors = (_doctor("doctor_z"), _doctor("doctor_a"))
    brand = (
        TargetBrand(canonical_name="Brand A", country="Aland", aliases=["a"])
        if branded
        else None
    )
    fact = TargetCommercialFact(
        id="fact_one",
        kind="commercial",
        text_fact="Exact marketing fact.",
        render_mode="strict",
        allowed_service_ids=["service_one"],
    )
    consultation = (
        ServiceConsultationValue(
            content_ref="service_one.md",
            value="Exact consultation value.",
        )
        if include_consultation
        else None
    )
    return TargetOfflineResponseMaterials(
        service_id="service_one",
        service=_service(content_ref=content_ref),
        selected_brand_id="brand_a" if branded else None,
        brand=brand,
        matched_rule_id="rule_one",
        max_options=3,
        offers=offers,
        doctors=doctors,
        selected_content_ref=content_ref,
        marketing_selection=TargetMarketingSelection(
            applied_scenarios=("cost",),
            selected_refs=("kb:cost.md#value", "fact:fact_one"),
            amplifier_refs=("kb:cost.md#value",),
            cta_key="plan",
        ),
        commercial_facts=(fact,),
        external_source_refs=("kb:cost.md#value",),
        consultation_close=consultation,
        marketing_slots_used=3,
        amplifier_slots_used=2,
    )


def _plan(
    materials: TargetOfflineResponseMaterials | None = None,
    components: object = ("content",),
) -> TargetResponseMaterializationPlan:
    return build_target_response_materialization_plan(
        materials or _materials(),
        required_components=components,  # type: ignore[arg-type]
    )


def test_exact_identity_only_shape_is_frozen_and_has_no_policy_mode() -> None:
    result = _plan()

    assert [field.name for field in fields(TargetResponseMaterializationPlan)] == [
        "service_id",
        "selected_brand_id",
        "required_components",
        "unfulfilled_components",
        "primary_content_ref",
        "offer_ids",
        "doctor_ids",
        "commercial_fact_ids",
        "external_source_refs",
        "consultation_content_ref",
        "cta_key",
    ]
    assert result.service_id == "service_one"
    assert not hasattr(result, "response_mode")
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        result.cta_key = "other"  # type: ignore[misc]


@pytest.mark.parametrize("materials", [None, object(), {"service_id": "service_one"}])
def test_invalid_materials_have_stable_error(materials: object) -> None:
    with pytest.raises(TargetResponseMaterializationPlanError) as exc_info:
        build_target_response_materialization_plan(
            materials,  # type: ignore[arg-type]
            required_components=("content",),
        )

    assert exc_info.value.code == "materialization_plan_materials_invalid"
    assert exc_info.value.value is materials
    assert str(exc_info.value) == f"materialization_plan_materials_invalid: {materials!r}"


@pytest.mark.parametrize(
    ("components", "expected_value"),
    [
        ("content", "content"),
        ({"content"}, {"content"}),
        (("Content",), "Content"),
        ((" content",), " content"),
        (("marketing",), "marketing"),
        ((1,), 1),
    ],
)
def test_invalid_component_container_or_item_has_stable_error(
    components: object,
    expected_value: object,
) -> None:
    with pytest.raises(TargetResponseMaterializationPlanError) as exc_info:
        _plan(components=components)

    assert exc_info.value.code == "materialization_plan_components_invalid"
    assert exc_info.value.value == expected_value
    assert str(exc_info.value) == (
        f"materialization_plan_components_invalid: {expected_value!r}"
    )


def test_empty_and_duplicate_components_have_stable_errors() -> None:
    with pytest.raises(TargetResponseMaterializationPlanError) as empty:
        _plan(components=())
    assert empty.value.code == "materialization_plan_components_empty"
    assert empty.value.value == ()

    copied = ("price", "content", "price")
    with pytest.raises(TargetResponseMaterializationPlanError) as duplicate:
        _plan(components=copied)
    assert duplicate.value.code == "materialization_plan_component_duplicate"
    assert duplicate.value.value == copied


def test_content_only_keeps_one_md_identity_without_price_or_doctors() -> None:
    result = _plan(components=("content",))

    assert result.required_components == ("content",)
    assert result.unfulfilled_components == ()
    assert result.primary_content_ref == "service_one.md"
    assert result.offer_ids == ()
    assert result.doctor_ids == ()


def test_price_only_preserves_projected_offer_order_and_brand_identity() -> None:
    materials = _materials(
        offers=(
            _offer("offer_brand_b", brand_id="brand_a"),
            _offer("offer_brand_a", brand_id="brand_a"),
        ),
        branded=True,
    )
    result = _plan(materials, ("price",))

    assert result.selected_brand_id == "brand_a"
    assert result.primary_content_ref is None
    assert result.offer_ids == ("offer_brand_b", "offer_brand_a")
    assert result.doctor_ids == ()


def test_doctors_only_preserves_authored_order_without_profile_payload() -> None:
    result = _plan(components=("doctors",))

    assert result.doctor_ids == ("doctor_z", "doctor_a")
    assert result.primary_content_ref is None
    assert result.offer_ids == ()


def test_composite_order_and_all_requested_identities_are_preserved() -> None:
    requested = ("doctors", "content", "price")
    result = _plan(components=requested)

    assert result.required_components == requested
    assert result.unfulfilled_components == ()
    assert result.primary_content_ref == "service_one.md"
    assert result.offer_ids == ("offer_b", "offer_a")
    assert result.doctor_ids == ("doctor_z", "doctor_a")


def test_missing_required_components_are_ordered_and_never_filled_by_fallback() -> None:
    materials = _materials(content_ref=None, offers=(), doctors=(), include_consultation=False)
    requested = ("doctors", "content", "price")
    result = _plan(materials, requested)

    assert result.required_components == requested
    assert result.unfulfilled_components == requested
    assert result.primary_content_ref is None
    assert result.offer_ids == ()
    assert result.doctor_ids == ()


def test_known_brand_without_offer_is_unfulfilled_and_unrequested_gaps_are_ignored() -> None:
    materials = _materials(offers=(), doctors=(), branded=True)
    price = _plan(materials, ("price",))
    content = _plan(materials, ("content",))

    assert price.selected_brand_id == "brand_a"
    assert price.offer_ids == ()
    assert price.unfulfilled_components == ("price",)
    assert content.unfulfilled_components == ()
    assert content.doctor_ids == ()


def test_selected_marketing_consultation_and_cta_identities_pass_without_reselection() -> None:
    result = _plan()

    assert result.commercial_fact_ids == ("fact_one",)
    assert result.external_source_refs == ("kb:cost.md#value",)
    assert result.consultation_content_ref == "service_one.md"
    assert result.cta_key == "plan"


def test_repeated_calls_are_stateless_and_do_not_mutate_s27_materials() -> None:
    materials = _materials()
    before = (
        materials.service.model_dump(),
        tuple(offer.model_dump() for offer in materials.offers),
        materials.marketing_selection,
    )

    first = _plan(materials, ("price", "doctors"))
    second = _plan(materials, ("price", "doctors"))

    assert first == second
    assert before == (
        materials.service.model_dump(),
        tuple(offer.model_dump() for offer in materials.offers),
        materials.marketing_selection,
    )


def test_exact_signature_four_error_codes_and_import_firewall() -> None:
    signature = inspect.signature(build_target_response_materialization_plan)
    assert list(signature.parameters) == ["materials", "required_components"]
    source_path = Path("core/target_response_materialization_plan.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    codes = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith("materialization_plan_")
    }
    assert codes == {
        "materialization_plan_materials_invalid",
        "materialization_plan_components_invalid",
        "materialization_plan_components_empty",
        "materialization_plan_component_duplicate",
    }
    assert not any(isinstance(node, ast.Try) for node in ast.walk(tree))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert imported_modules <= {
        "__future__",
        "collections.abc",
        "dataclasses",
        "typing",
        "core.target_offline_response_assembly",
    }
    field_names = {field.name for field in fields(TargetResponseMaterializationPlan)}
    assert not field_names & {
        "price",
        "package",
        "payment_stages",
        "followups",
        "doctor_profile",
        "fact_text",
        "consultation_value",
        "md_body",
    }
