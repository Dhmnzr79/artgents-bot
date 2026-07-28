from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, fields
from datetime import date
from pathlib import Path

import pytest

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from contracts.service_consultation import (
    ServiceConsultationRefError,
    ServiceConsultationValue,
)
from core.service_data_context import ServiceDataContextError
from core.target_marketing_selector import TargetMarketingSelectionError
from core.target_response_evidence import (
    TargetResponseEvidencePackage,
    TargetResponseEvidencePackageError,
    build_target_response_evidence_package,
)


TODAY = date(2026, 7, 21)


def _fact(fact_id: str, service_id: str) -> dict[str, object]:
    return {
        "id": fact_id,
        "kind": "commercial",
        "text_fact": f"Exact {fact_id}.",
        "render_mode": "strict",
        "active": True,
        "allowed_service_ids": [service_id],
        "incompatible_with": [],
    }


def _offer(
    offer_id: str,
    service_id: str,
    *,
    amount: int,
    active: bool,
    fact_id: str,
) -> dict[str, object]:
    return {
        "offer_id": offer_id,
        "service_id": service_id,
        "active": active,
        "price": {
            "mode": "fixed",
            "amount": amount,
            "currency": "RUB",
            "billing_unit": "jaw",
        },
        "package": {"label": f"Package {offer_id}", "includes": ["Exact item"]},
        "fact_refs": [fact_id],
        "followups": [],
    }


def _bundle(
    *,
    limits: tuple[int, int, int] = (3, 2, 2),
    initial_refs: list[str] | None = None,
    scenarios: dict[str, list[str]] | None = None,
) -> ResponseSchemaBundle:
    max_marketing, max_amplifiers, max_scenarios = limits
    if initial_refs is None:
        initial_refs = []
    if scenarios is None:
        scenarios = {}
    return ResponseSchemaBundle.model_validate(
        {
            "services": {
                "service_one": {
                    "name": "Service One",
                    "aliases": [],
                    "family": "implantology",
                    "roles": ["protocol"],
                    "active": False,
                    "content_ref": "service_one.md",
                    "selection": {"mode": "direct"},
                    "options": [
                        {
                            "option_id": "option_one",
                            "name": "Option One",
                            "active": True,
                            "content_ref": "service_one__option_one.md",
                        }
                    ],
                },
                "service_two": {
                    "name": "Service Two",
                    "aliases": [],
                    "family": "therapy",
                    "roles": ["supporting"],
                    "active": True,
                    "content_ref": "service_two.md",
                    "selection": {"mode": "direct"},
                    "options": [],
                },
            },
            "brands": {"version": 1, "brands": {}},
            "offers": [
                _offer(
                    "offer_z",
                    "service_one",
                    amount=310_000,
                    active=False,
                    fact_id="service_fact",
                ),
                _offer(
                    "other_offer",
                    "service_two",
                    amount=20_000,
                    active=True,
                    fact_id="other_fact",
                ),
                _offer(
                    "offer_a",
                    "service_one",
                    amount=410_000,
                    active=True,
                    fact_id="initial_fact",
                ),
            ],
            "facts": {
                "service_fact": _fact("service_fact", "service_one"),
                "initial_fact": _fact("initial_fact", "service_one"),
                "other_fact": _fact("other_fact", "service_two"),
            },
            "strategy": {"version": 1, "default_max_options": 3, "rules": []},
            "marketing": {
                "version": 1,
                "limits": {
                    "max_marketing_facts_per_turn": max_marketing,
                    "max_amplifiers_per_turn": max_amplifiers,
                    "max_scenarios_per_turn": max_scenarios,
                },
                "initial_commercial_blocks": (
                    {"service": {"ordered_fact_refs": initial_refs}}
                    if initial_refs
                    else {}
                ),
                "scenario_rules": {
                    scenario: {
                        "ordered_amplifier_refs": refs,
                        "allowed_semantic_contexts": ["service"],
                    }
                    for scenario, refs in scenarios.items()
                },
                "cta_contexts": {"service": "plan", "default": "callback"},
            },
        }
    )


def _doctors() -> TargetDoctorCatalog:
    return TargetDoctorCatalog.model_validate(
        {
            "doctors": {
                "doctor_z": {
                    "name": "Doctor Z",
                    "position": "Implantologist",
                    "experience_years": 17,
                    "service_ids": ["service_one"],
                    "profile_ref": "kb:doctor_z.md#profile",
                },
                "doctor_other": {
                    "name": "Doctor Other",
                    "position": "Therapist",
                    "experience_years": 9,
                    "service_ids": ["service_two"],
                    "profile_ref": "kb:doctor_other.md#profile",
                },
                "doctor_a": {
                    "name": "Doctor A",
                    "position": "Implantologist",
                    "experience_years": 12,
                    "service_ids": ["service_two", "service_one"],
                    "profile_ref": "kb:doctor_a.md#profile",
                },
            }
        }
    )


def _index() -> ResponseSchemaExternalIndex:
    return ResponseSchemaExternalIndex(
        kb_refs=("kb:cost.md#one",),
        doctor_refs=("doctor:doctor_one", "doctor:doctor_z"),
    )


def _consultations() -> tuple[ServiceConsultationValue, ...]:
    return (
        ServiceConsultationValue(
            content_ref="service_one.md",
            value="Exact service consultation value.",
        ),
        ServiceConsultationValue(
            content_ref="service_one__option_one.md",
            value="Exact option consultation value.",
        ),
    )


def _build(
    bundle: ResponseSchemaBundle | None = None,
    consultations: object | None = None,
    **overrides: object,
) -> TargetResponseEvidencePackage:
    if bundle is None:
        bundle = _bundle()
    if consultations is None:
        consultations = _consultations()
    params: dict[str, object] = {
        "service_id": "service_one",
        "selected_content_ref": "service_one.md",
        "semantic_context": "service",
        "today": TODAY,
        "include_initial_block": False,
        "include_consultation_close": True,
    }
    params.update(overrides)
    return build_target_response_evidence_package(
        bundle,
        _doctors(),
        _index(),
        consultations,  # type: ignore[arg-type]
        **params,  # type: ignore[arg-type]
    )


def test_exact_shape_preserves_s10_order_flags_and_one_service_link() -> None:
    result = _build()

    assert [field.name for field in fields(TargetResponseEvidencePackage)] == [
        "service_context",
        "selected_content_ref",
        "marketing_selection",
        "commercial_facts",
        "external_source_refs",
        "consultation_close",
        "marketing_slots_used",
        "amplifier_slots_used",
    ]
    assert result.service_context.service_id == "service_one"
    assert result.service_context.service.active is False
    assert [offer.offer_id for offer in result.service_context.offers] == [
        "offer_z",
        "offer_a",
    ]
    assert [offer.active for offer in result.service_context.offers] == [False, True]
    assert [doctor.doctor_id for doctor in result.service_context.doctors] == [
        "doctor_z",
        "doctor_a",
    ]
    assert isinstance(result.commercial_facts, tuple)
    assert isinstance(result.external_source_refs, tuple)
    with pytest.raises(FrozenInstanceError):
        result.marketing_slots_used = 99  # type: ignore[misc]
    assert not hasattr(result, "__dict__")


@pytest.mark.parametrize(
    ("selected_ref", "expected_value"),
    [
        ("service_one.md", "Exact service consultation value."),
        ("service_one__option_one.md", "Exact option consultation value."),
    ],
)
def test_exact_service_or_option_consultation_uses_one_of_each_slot(
    selected_ref: str, expected_value: str
) -> None:
    result = _build(selected_content_ref=selected_ref)

    assert result.selected_content_ref == selected_ref
    assert result.consultation_close is not None
    assert result.consultation_close.content_ref == selected_ref
    assert result.consultation_close.value == expected_value
    assert result.marketing_slots_used == 1
    assert result.amplifier_slots_used == 1
    assert result.marketing_selection.selected_refs == ()
    assert result.marketing_selection.amplifier_refs == ()


def test_selected_refs_materialize_copied_facts_and_ordered_external_refs() -> None:
    bundle = _bundle(
        initial_refs=["fact:initial_fact"],
        scenarios={
            "cost": ["kb:cost.md#one"],
            "doctor_trust": ["doctor:doctor_z"],
        },
    )
    result = _build(
        bundle,
        include_initial_block=True,
        marketing_scenarios=["cost", "doctor_trust"],
    )

    assert result.marketing_selection.selected_refs == (
        "kb:cost.md#one",
        "doctor:doctor_z",
        "fact:initial_fact",
    )
    assert result.external_source_refs == (
        "kb:cost.md#one",
        "doctor:doctor_z",
    )
    assert [fact.id for fact in result.commercial_facts] == ["initial_fact"]
    assert result.commercial_facts[0] is not bundle.facts["initial_fact"]
    assert result.consultation_close is None
    assert result.marketing_slots_used == 3
    assert result.amplifier_slots_used == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"include_consultation_close": False},
        {"selected_content_ref": None},
        {"shown_consultation_value_refs": ["service_one.md"]},
    ],
)
def test_explicit_close_gates_suppress_without_replacement(
    overrides: dict[str, object]
) -> None:
    result = _build(**overrides)

    assert result.consultation_close is None
    assert result.marketing_slots_used == 0
    assert result.amplifier_slots_used == 0


def test_missing_exact_consultation_value_does_not_use_another_owned_value() -> None:
    result = _build(
        consultations=(
            ServiceConsultationValue(
                content_ref="service_one__option_one.md",
                value="Only the option value.",
            ),
        )
    )

    assert result.selected_content_ref == "service_one.md"
    assert result.consultation_close is None
    assert result.marketing_slots_used == 0
    assert result.amplifier_slots_used == 0


def test_full_marketing_slot_independently_suppresses_consultation_close() -> None:
    bundle = _bundle(
        limits=(1, 1, 1),
        initial_refs=["fact:initial_fact"],
    )
    result = _build(bundle, include_initial_block=True)

    assert result.marketing_selection.selected_refs == ("fact:initial_fact",)
    assert result.marketing_selection.amplifier_refs == ()
    assert result.consultation_close is None
    assert (result.marketing_slots_used, result.amplifier_slots_used) == (1, 0)


def test_full_amplifier_slot_independently_suppresses_consultation_close() -> None:
    bundle = _bundle(
        limits=(3, 1, 1),
        scenarios={"cost": ["kb:cost.md#one"]},
    )
    result = _build(bundle, marketing_scenarios=["cost"])

    assert result.marketing_selection.selected_refs == ("kb:cost.md#one",)
    assert result.marketing_selection.amplifier_refs == ("kb:cost.md#one",)
    assert result.consultation_close is None
    assert (result.marketing_slots_used, result.amplifier_slots_used) == (1, 1)


@pytest.mark.parametrize(
    "selected_ref",
    ["", " service_one.md", "service_one.md#chunk", 7],
)
def test_invalid_selected_content_ref_has_stable_error(selected_ref: object) -> None:
    with pytest.raises(TargetResponseEvidencePackageError) as exc_info:
        _build(selected_content_ref=selected_ref)

    error = exc_info.value
    assert error.code == "evidence_selected_content_ref_invalid"
    assert error.value == selected_ref
    assert str(error) == f"evidence_selected_content_ref_invalid: {selected_ref!r}"


@pytest.mark.parametrize("selected_ref", ["service_two.md", "missing.md"])
def test_valid_cross_service_or_unknown_content_ref_is_not_owned(
    selected_ref: str,
) -> None:
    with pytest.raises(TargetResponseEvidencePackageError) as exc_info:
        _build(selected_content_ref=selected_ref)

    assert exc_info.value.code == "evidence_selected_content_ref_not_owned"
    assert exc_info.value.value == selected_ref


@pytest.mark.parametrize(
    ("consultations", "expected_value"),
    [
        ("service_one.md", "service_one.md"),
        ({"content_ref": "service_one.md"}, {"content_ref": "service_one.md"}),
        ([object()], None),
    ],
)
def test_invalid_consultation_values_container_or_item_has_stable_error(
    consultations: object, expected_value: object
) -> None:
    with pytest.raises(TargetResponseEvidencePackageError) as exc_info:
        _build(consultations=consultations)

    assert exc_info.value.code == "evidence_consultation_values_invalid"
    if expected_value is None:
        assert exc_info.value.value is consultations[0]  # type: ignore[index]
    else:
        assert exc_info.value.value == expected_value


def test_duplicate_consultation_content_refs_fail_closed() -> None:
    duplicates = (
        ServiceConsultationValue(content_ref="service_one.md", value="One."),
        ServiceConsultationValue(content_ref="service_one.md", value="Two."),
    )
    with pytest.raises(TargetResponseEvidencePackageError) as exc_info:
        _build(consultations=duplicates)

    assert exc_info.value.code == "evidence_consultation_content_ref_duplicate"
    assert exc_info.value.value == ("service_one.md", "service_one.md")


def test_orphan_consultation_record_uses_existing_s18_error() -> None:
    records = (
        ServiceConsultationValue(content_ref="orphan.md", value="Orphan."),
    )
    with pytest.raises(ServiceConsultationRefError) as exc_info:
        _build(consultations=records)

    assert exc_info.value.orphan_content_refs == ("orphan.md",)


def test_invalid_consultation_flag_has_stable_error() -> None:
    with pytest.raises(TargetResponseEvidencePackageError) as exc_info:
        _build(include_consultation_close=1)

    assert exc_info.value.code == "evidence_include_consultation_close_invalid"
    assert exc_info.value.value == 1


@pytest.mark.parametrize(
    ("shown", "expected_value"),
    [
        ("service_one.md", "service_one.md"),
        (["bad#ref.md"], "bad#ref.md"),
    ],
)
def test_invalid_shown_consultation_refs_have_stable_error(
    shown: object, expected_value: object
) -> None:
    with pytest.raises(TargetResponseEvidencePackageError) as exc_info:
        _build(shown_consultation_value_refs=shown)

    assert exc_info.value.code == "evidence_shown_consultation_ref_invalid"
    assert exc_info.value.value == expected_value


def test_duplicate_shown_consultation_refs_fail_closed() -> None:
    shown = ["service_one.md", "service_one.md"]
    with pytest.raises(TargetResponseEvidencePackageError) as exc_info:
        _build(shown_consultation_value_refs=shown)

    assert exc_info.value.code == "evidence_shown_consultation_ref_duplicate"
    assert exc_info.value.value == tuple(shown)


def test_valid_stale_shown_ref_is_accepted_without_hidden_cleanup() -> None:
    stale_snapshot = ["removed_but_valid.md"]

    result = _build(shown_consultation_value_refs=stale_snapshot)

    assert result.consultation_close is not None
    assert result.consultation_close.content_ref == "service_one.md"
    assert stale_snapshot == ["removed_but_valid.md"]


def test_s10_and_s21_errors_precede_s22_consultation_validation() -> None:
    with pytest.raises(ServiceDataContextError) as service_exc:
        _build(
            consultations="invalid",
            service_id="missing",
            semantic_context="",
        )
    assert service_exc.value.code == "service_not_found"

    with pytest.raises(TargetMarketingSelectionError) as marketing_exc:
        _build(consultations="invalid", semantic_context="")
    assert marketing_exc.value.code == "marketing_semantic_context_invalid"


def test_results_are_stateless_and_deep_detached_without_mutating_snapshots() -> None:
    bundle = _bundle(initial_refs=["fact:initial_fact"])
    doctors = _doctors()
    consultations = list(_consultations())
    scenarios: list[str] = []
    shown_facts: list[str] = []
    shown_amplifiers: list[str] = []
    shown_consultations: list[str] = []
    bundle_before = bundle.model_dump()
    doctors_before = doctors.model_dump()

    first = build_target_response_evidence_package(
        bundle,
        doctors,
        _index(),
        consultations,
        service_id="service_one",
        selected_content_ref="service_one.md",
        semantic_context="service",
        today=TODAY,
        include_initial_block=True,
        include_consultation_close=True,
        marketing_scenarios=scenarios,
        shown_fact_ids=shown_facts,
        shown_amplifier_refs=shown_amplifiers,
        shown_consultation_value_refs=shown_consultations,
    )
    first.service_context.service.name = "Output only"
    first.service_context.offers[0].package.label = "Output only"
    first.commercial_facts[0].text_fact = "Output only"

    second = build_target_response_evidence_package(
        bundle,
        doctors,
        _index(),
        consultations,
        service_id="service_one",
        selected_content_ref="service_one.md",
        semantic_context="service",
        today=TODAY,
        include_initial_block=True,
        include_consultation_close=True,
        marketing_scenarios=scenarios,
        shown_fact_ids=shown_facts,
        shown_amplifier_refs=shown_amplifiers,
        shown_consultation_value_refs=shown_consultations,
    )

    assert second.service_context.service.name == "Service One"
    assert second.service_context.offers[0].package.label == "Package offer_z"
    assert second.commercial_facts[0].text_fact == "Exact initial_fact."
    assert second.consultation_close is not consultations[0]
    assert bundle.model_dump() == bundle_before
    assert doctors.model_dump() == doctors_before
    assert scenarios == shown_facts == shown_amplifiers == shown_consultations == []
    assert [record.content_ref for record in consultations] == [
        "service_one.md",
        "service_one__option_one.md",
    ]


def test_exact_signature_and_import_firewall() -> None:
    assert list(
        inspect.signature(build_target_response_evidence_package).parameters
    ) == [
        "bundle",
        "doctor_catalog",
        "external_index",
        "consultation_values",
        "service_id",
        "selected_content_ref",
        "semantic_context",
        "today",
        "include_initial_block",
        "include_consultation_close",
        "marketing_scenarios",
        "shown_fact_ids",
        "shown_amplifier_refs",
        "shown_consultation_value_refs",
        "turn_topic",
    ]
    source_path = Path("core/target_response_evidence.py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not any(
        module.startswith(
            (
                "app",
                "clients",
                "config",
                "handlers",
                "orchestration",
                "routes",
                "telegram",
            )
        )
        for module in imported_modules
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"skip", "skipif", "xfail"}
        for node in ast.walk(tree)
    )
