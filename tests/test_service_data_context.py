from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, fields

import pytest

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle
from core import service_data_context
from core.service_data_context import (
    ServiceDataContext,
    ServiceDataContextError,
    ServiceDoctorContext,
    build_service_data_context,
)


def _service_payload(
    name: str,
    *,
    active: bool = True,
    content_ref: str | None,
    option_id: str | None = None,
) -> dict[str, object]:
    options: list[dict[str, object]] = []
    if option_id is not None:
        options.append({"option_id": option_id, "name": f"{name} option"})
    return {
        "name": name,
        "aliases": [],
        "family": "implantology",
        "roles": ["protocol"],
        "active": active,
        "content_ref": content_ref,
        "selection": {"mode": "direct"},
        "options": options,
    }


def _offer_payload(
    offer_id: str,
    service_id: str,
    *,
    amount: int,
    active: bool,
    fact_ref: str,
) -> dict[str, object]:
    return {
        "offer_id": offer_id,
        "service_id": service_id,
        "option_id": "full_arch",
        "brand_id": "brand_one",
        "active": active,
        "price": {
            "mode": "fixed",
            "amount": amount,
            "currency": "RUB",
            "billing_unit": "jaw",
        },
        "package": {
            "label": f"Package {offer_id}",
            "includes": ["implant placement", "temporary prosthesis"],
        },
        "fact_refs": [fact_ref],
        "followups": [
            {
                "id": f"{offer_id}_includes",
                "label": "Что входит",
                "action": "price_aspect",
            }
        ],
    }


def _fact_payload(fact_id: str, service_id: str) -> dict[str, object]:
    return {
        "id": fact_id,
        "kind": "commercial",
        "catalog_label": f"Catalog topic for {fact_id}",
        "text_fact": f"Exact fact {fact_id}",
        "render_mode": "strict",
        "active": True,
        "allowed_service_ids": [service_id],
        "incompatible_with": [],
    }


def _bundle() -> ResponseSchemaBundle:
    offers = [
        _offer_payload(
            "offer_z",
            "all_on_4",
            amount=318_000,
            active=False,
            fact_ref="fact_one",
        ),
        {
            **_offer_payload(
                "other_offer",
                "other_service",
                amount=90_000,
                active=True,
                fact_ref="other_fact",
            ),
            "option_id": "other_option",
        },
        _offer_payload(
            "offer_a",
            "all_on_4",
            amount=428_000,
            active=True,
            fact_ref="fact_two",
        ),
    ]
    return ResponseSchemaBundle.model_validate(
        {
            "services": {
                "all_on_4": _service_payload(
                    "All-on-4",
                    active=False,
                    content_ref="kb:implantation__service__all_on_4.md#korotko",
                    option_id="full_arch",
                ),
                "other_service": _service_payload(
                    "Other service",
                    content_ref="kb:other.md#korotko",
                    option_id="other_option",
                ),
                "clinic_only": _service_payload(
                    "Clinic-only service",
                    content_ref=None,
                ),
            },
            "brands": {
                "version": 1,
                "brands": {
                    "brand_one": {
                        "canonical_name": "Brand One",
                        "country": "Country One",
                        "aliases": [],
                    }
                },
            },
            "offers": offers,
            "facts": {
                "fact_one": _fact_payload("fact_one", "all_on_4"),
                "fact_two": _fact_payload("fact_two", "all_on_4"),
                "other_fact": _fact_payload("other_fact", "other_service"),
            },
            "strategy": {
                "version": 1,
                "default_max_options": 3,
                "rules": [],
            },
            "marketing": {
                "version": 1,
                "limits": {
                    "max_marketing_facts_per_turn": 0,
                    "max_amplifiers_per_turn": 0,
                    "max_scenarios_per_turn": 0,
                },
                "initial_commercial_blocks": {},
                "scenario_rules": {},
                "cta_contexts": {"default": "callback"},
            },
        }
    )


def _doctor_payload(
    name: str,
    experience_years: int,
    service_ids: list[str],
) -> dict[str, object]:
    return {
        "name": name,
        "position": "Хирург-имплантолог",
        "experience_years": experience_years,
        "service_ids": service_ids,
        "profile_ref": f"kb:{name.lower().replace(' ', '_')}.md#profile",
    }


def _doctor_catalog() -> TargetDoctorCatalog:
    return TargetDoctorCatalog.model_validate(
        {
            "doctors": {
                "doctor_z": _doctor_payload("Doctor Z", 17, ["all_on_4"]),
                "doctor_other": _doctor_payload(
                    "Doctor Other", 9, ["other_service"]
                ),
                "doctor_a": _doctor_payload(
                    "Doctor A", 12, ["other_service", "all_on_4"]
                ),
            }
        }
    )


def test_exact_service_joins_full_offers_and_doctors_with_experience() -> None:
    bundle = _bundle()
    catalog = _doctor_catalog()

    context = build_service_data_context(bundle, catalog, "all_on_4")

    assert context.service_id == "all_on_4"
    assert context.service.model_dump() == bundle.services["all_on_4"].model_dump()
    assert context.service.content_ref == (
        "kb:implantation__service__all_on_4.md#korotko"
    )
    expected_offers = [bundle.offers[0].model_dump(), bundle.offers[2].model_dump()]
    assert [offer.model_dump() for offer in context.offers] == expected_offers
    assert context.offers[0].option_id == "full_arch"
    assert context.offers[0].brand_id == "brand_one"
    assert context.offers[0].fact_refs == ["fact_one"]
    assert context.offers[0].followups[0].action == "price_aspect"
    assert context.offers[0].price.amount == 318_000
    assert context.offers[0].package.includes == [
        "implant placement",
        "temporary prosthesis",
    ]
    assert [doctor.doctor_id for doctor in context.doctors] == [
        "doctor_z",
        "doctor_a",
    ]
    assert context.doctors == (
        ServiceDoctorContext(
            doctor_id="doctor_z",
            name="Doctor Z",
            position="Хирург-имплантолог",
            experience_years=17,
            profile_ref="kb:doctor_z.md#profile",
        ),
        ServiceDoctorContext(
            doctor_id="doctor_a",
            name="Doctor A",
            position="Хирург-имплантолог",
            experience_years=12,
            profile_ref="kb:doctor_a.md#profile",
        ),
    )


def test_context_excludes_other_service_records_and_preserves_authored_flags() -> None:
    context = build_service_data_context(_bundle(), _doctor_catalog(), "all_on_4")

    assert [offer.offer_id for offer in context.offers] == ["offer_z", "offer_a"]
    assert [offer.active for offer in context.offers] == [False, True]
    assert context.service.active is False
    assert "doctor_other" not in {doctor.doctor_id for doctor in context.doctors}


def test_service_without_content_price_or_doctors_returns_empty_context() -> None:
    context = build_service_data_context(_bundle(), _doctor_catalog(), "clinic_only")

    assert context.service.content_ref is None
    assert context.offers == ()
    assert context.doctors == ()


@pytest.mark.parametrize("service_id", [None, 7, "", "   "])
def test_invalid_service_id_is_typed_and_preserves_original_value(
    service_id: object,
) -> None:
    with pytest.raises(ServiceDataContextError) as exc_info:
        build_service_data_context(  # type: ignore[arg-type]
            _bundle(), _doctor_catalog(), service_id
        )

    error = exc_info.value
    assert isinstance(error, ServiceDataContextError)
    assert isinstance(error, ValueError)
    assert error.code == "service_id_invalid"
    assert error.service_id == service_id


@pytest.mark.parametrize("service_id", ["missing", "ALL_ON_4", " all_on_4 "])
def test_unknown_exact_service_id_is_not_normalized(service_id: str) -> None:
    with pytest.raises(ServiceDataContextError) as exc_info:
        build_service_data_context(_bundle(), _doctor_catalog(), service_id)

    error = exc_info.value
    assert isinstance(error, ServiceDataContextError)
    assert isinstance(error, ValueError)
    assert error.code == "service_not_found"
    assert error.service_id == service_id


def test_dataclasses_have_exact_frozen_slotted_shape() -> None:
    context = build_service_data_context(_bundle(), _doctor_catalog(), "all_on_4")

    assert [field.name for field in fields(ServiceDoctorContext)] == [
        "doctor_id",
        "name",
        "position",
        "experience_years",
        "profile_ref",
    ]
    assert [field.name for field in fields(ServiceDataContext)] == [
        "service_id",
        "service",
        "offers",
        "doctors",
    ]
    assert ServiceDoctorContext.__dataclass_params__.frozen is True
    assert ServiceDataContext.__dataclass_params__.frozen is True
    assert ServiceDoctorContext.__slots__ == (
        "doctor_id",
        "name",
        "position",
        "experience_years",
        "profile_ref",
    )
    assert ServiceDataContext.__slots__ == (
        "service_id",
        "service",
        "offers",
        "doctors",
    )
    assert not hasattr(context, "__dict__")
    assert not hasattr(context.doctors[0], "__dict__")
    with pytest.raises(FrozenInstanceError):
        context.service_id = "other_service"  # type: ignore[misc]


def test_builder_does_not_mutate_or_alias_inputs() -> None:
    bundle = _bundle()
    catalog = _doctor_catalog()
    bundle_before = bundle.model_dump()
    catalog_before = catalog.model_dump()

    context = build_service_data_context(bundle, catalog, "all_on_4")

    assert context.service is not bundle.services["all_on_4"]
    assert context.offers[0] is not bundle.offers[0]
    assert context.offers[1] is not bundle.offers[2]
    context.service.name = "Changed only in output"
    context.offers[0].package.label = "Changed only in output"
    context.offers[0].price.amount = 1

    assert bundle.model_dump() == bundle_before
    assert catalog.model_dump() == catalog_before

    second = build_service_data_context(bundle, catalog, "all_on_4")
    assert second.service.name == "All-on-4"
    assert second.offers[0].package.label == "Package offer_z"
    assert second.offers[0].price.amount == 318_000


def test_module_is_pure_and_has_no_second_schema_or_product_dependencies() -> None:
    source = inspect.getsource(service_data_context)
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert imported_modules <= {
        "__future__",
        "contracts.doctor_schema",
        "contracts.response_schema",
        "dataclasses",
    }
    assert "model_validate" not in called_attributes
    assert called_attributes.isdisjoint(
        {
            "getenv",
            "mkdir",
            "open",
            "read_bytes",
            "read_text",
            "touch",
            "write_bytes",
            "write_text",
        }
    )
    assert "client_id" not in source
    assert "session" not in source.lower()
    assert "pricebook_loader" not in source
