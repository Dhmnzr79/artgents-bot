from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError
from datetime import date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from core.target_marketing_selector import (
    TargetMarketingSelection,
    TargetMarketingSelectionError,
    select_target_marketing,
)


TODAY = date(2026, 7, 21)


def _fact(
    fact_id: str,
    *,
    services: list[str] | None = None,
    active: bool = True,
    active_from: str | None = None,
    active_until: str | None = None,
    incompatible_with: list[str] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": fact_id,
        "kind": "proof",
        "text_fact": f"Exact {fact_id}.",
        "render_mode": "strict",
        "active": active,
        "allowed_service_ids": services or [],
        "incompatible_with": incompatible_with or [],
    }
    if active_from is not None:
        payload["active_from"] = active_from
    if active_until is not None:
        payload["active_until"] = active_until
    return payload


def _bundle(
    *,
    limits: tuple[int, int, int] = (3, 2, 2),
    initial: dict[str, list[str]] | None = None,
    scenarios: dict[str, tuple[list[str], list[str]]] | None = None,
) -> ResponseSchemaBundle:
    max_marketing, max_amplifiers, max_scenarios = limits
    facts = {
        "global": _fact("global"),
        "service": _fact("service", services=["service_one"]),
        "other": _fact("other", services=["service_two"]),
        "inactive": _fact("inactive", active=False),
        "future": _fact("future", active_from="2026-07-22"),
        "expired": _fact("expired", active_until="2026-07-20"),
        "starts_today": _fact("starts_today", active_from="2026-07-21"),
        "ends_today": _fact("ends_today", active_until="2026-07-21"),
        "conflict_a": _fact("conflict_a", incompatible_with=["conflict_b"]),
        "conflict_b": _fact("conflict_b"),
    }
    if initial is None:
        initial = {"service": ["fact:service", "fact:global", "fact:other"]}
    if scenarios is None:
        scenarios = {
            "cost": (["fact:service", "kb:cost.md#one"], ["service"]),
            "pain_fear": (["kb:pain.md#one", "kb:pain.md#two"], ["service"]),
            "doctor_trust": (
                [
                    "doctor:doctor_other",
                    "doctor:doctor_one",
                    "kb:doctors.md#overview",
                ],
                ["service", "doctors"],
            ),
        }
    return ResponseSchemaBundle.model_validate(
        {
            "services": {
                "service_one": {
                    "name": "Service One",
                    "family": "implantology",
                    "roles": ["protocol"],
                    "active": True,
                    "selection": {"mode": "context"},
                },
                "service_two": {
                    "name": "Service Two",
                    "family": "therapy",
                    "roles": ["protocol"],
                    "active": True,
                    "selection": {"mode": "context"},
                },
            },
            "brands": {"version": 1, "brands": {}},
            "offers": [],
            "facts": facts,
            "strategy": {"version": 1, "default_max_options": 3, "rules": []},
            "marketing": {
                "version": 1,
                "limits": {
                    "max_marketing_facts_per_turn": max_marketing,
                    "max_amplifiers_per_turn": max_amplifiers,
                    "max_scenarios_per_turn": max_scenarios,
                },
                "initial_commercial_blocks": {
                    context: {"ordered_fact_refs": refs}
                    for context, refs in initial.items()
                },
                "scenario_rules": {
                    scenario: {
                        "ordered_amplifier_refs": refs,
                        "allowed_semantic_contexts": contexts,
                    }
                    for scenario, (refs, contexts) in scenarios.items()
                },
                "cta_contexts": {
                    "service": "plan",
                    "doctors": "doctor",
                    "default": "callback",
                },
            },
        }
    )


def _doctors() -> TargetDoctorCatalog:
    return TargetDoctorCatalog.model_validate(
        {
            "doctors": {
                "doctor_one": {
                    "name": "Doctor One",
                    "position": "Implantologist",
                    "experience_years": 12,
                    "service_ids": ["service_one"],
                    "profile_ref": "kb:doctor_one.md#profile",
                },
                "doctor_other": {
                    "name": "Doctor Other",
                    "position": "Therapist",
                    "experience_years": 9,
                    "service_ids": ["service_two"],
                    "profile_ref": "kb:doctor_other.md#profile",
                },
            }
        }
    )


def _index(
    *,
    kb_refs: tuple[str, ...] = (
        "kb:cost.md#one",
        "kb:pain.md#one",
        "kb:pain.md#two",
        "kb:doctors.md#overview",
    ),
    doctor_refs: tuple[str, ...] = (
        "doctor:doctor_one",
        "doctor:doctor_other",
    ),
) -> ResponseSchemaExternalIndex:
    return ResponseSchemaExternalIndex(kb_refs=kb_refs, doctor_refs=doctor_refs)


def _select(
    bundle: ResponseSchemaBundle | None = None,
    **kwargs: object,
) -> TargetMarketingSelection:
    params: dict[str, object] = {
        "semantic_context": "service",
        "service_id": "service_one",
        "today": TODAY,
        "include_initial_block": True,
    }
    params.update(kwargs)
    return select_target_marketing(
        bundle or _bundle(),
        _doctors(),
        _index(),
        **params,
    )


def test_single_scenario_preserves_pool_order_caps_and_fills_initial() -> None:
    result = _select(marketing_scenarios=["cost"])

    assert result.applied_scenarios == ("cost",)
    assert result.amplifier_refs == ("fact:service", "kb:cost.md#one")
    assert result.selected_refs == (
        "fact:service",
        "kb:cost.md#one",
        "fact:global",
    )
    assert result.cta_key == "plan"


def test_two_scenarios_round_robin_skips_shared_ref_in_same_turn() -> None:
    bundle = _bundle(
        initial={},
        scenarios={
            "pain_fear": (
                ["kb:shared.md#one", "kb:pain.md#two"],
                ["service"],
            ),
            "cost": (
                ["kb:shared.md#one", "kb:cost.md#one"],
                ["service"],
            ),
        },
    )
    index = _index(
        kb_refs=("kb:shared.md#one", "kb:pain.md#two", "kb:cost.md#one")
    )

    result = select_target_marketing(
        bundle,
        _doctors(),
        index,
        semantic_context="service",
        service_id="service_one",
        today=TODAY,
        include_initial_block=False,
        marketing_scenarios=["pain_fear", "cost"],
    )

    assert result.applied_scenarios == ("pain_fear", "cost")
    assert result.selected_refs == result.amplifier_refs == (
        "kb:shared.md#one",
        "kb:cost.md#one",
    )


def test_ineligible_pool_does_not_block_other_scenario_from_remaining_slot() -> None:
    bundle = _bundle(
        initial={},
        scenarios={
            "doctor_trust": (["doctor:doctor_other"], ["service"]),
            "cost": (
                ["kb:cost.md#one", "kb:pain.md#one"],
                ["service"],
            ),
        },
    )

    result = _select(
        bundle,
        include_initial_block=False,
        marketing_scenarios=["doctor_trust", "cost"],
    )

    assert result.applied_scenarios == ("doctor_trust", "cost")
    assert result.amplifier_refs == ("kb:cost.md#one", "kb:pain.md#one")


def test_context_filtering_precedes_scenario_cap_and_empty_allowlist_denies() -> None:
    bundle = _bundle(
        limits=(3, 2, 1),
        scenarios={
            "pain_fear": (["kb:pain.md#one"], ["doctors"]),
            "time": (["kb:pain.md#two"], []),
            "cost": (["kb:cost.md#one"], ["service"]),
        },
    )

    result = _select(
        bundle,
        include_initial_block=False,
        marketing_scenarios=["pain_fear", "time", "cost"],
    )

    assert result.applied_scenarios == ("cost",)
    assert result.selected_refs == ("kb:cost.md#one",)


def test_applied_scenarios_keep_no_evidence_rules_but_zero_scenario_cap_is_empty() -> None:
    no_evidence = _select(
        _bundle(
            initial={},
            scenarios={"cost": (["kb:missing.md#one"], ["service"])},
        ),
        include_initial_block=False,
        marketing_scenarios=["cost"],
    )
    zero_cap = _select(
        _bundle(limits=(3, 2, 0)),
        include_initial_block=False,
        marketing_scenarios=["cost"],
    )

    assert no_evidence.applied_scenarios == ("cost",)
    assert no_evidence.selected_refs == ()
    assert zero_cap.applied_scenarios == ()
    assert zero_cap.selected_refs == ()


def test_fact_active_dates_and_service_eligibility_are_exact_and_inclusive() -> None:
    bundle = _bundle(
        initial={
            "service": [
                "fact:inactive",
                "fact:future",
                "fact:expired",
                "fact:other",
                "fact:starts_today",
                "fact:ends_today",
                "fact:global",
            ]
        },
        scenarios={},
    )

    result = _select(bundle)

    assert result.selected_refs == (
        "fact:starts_today",
        "fact:ends_today",
        "fact:global",
    )


def test_missing_external_refs_and_wrong_service_doctor_are_skipped() -> None:
    bundle = _bundle(
        initial={},
        scenarios={
            "doctor_trust": (
                [
                    "kb:missing.md#one",
                    "doctor:doctor_other",
                    "doctor:doctor_one",
                    "kb:doctors.md#overview",
                ],
                ["service"],
            )
        },
    )

    result = _select(
        bundle,
        include_initial_block=False,
        marketing_scenarios=["doctor_trust"],
    )

    assert result.selected_refs == (
        "doctor:doctor_one",
        "kb:doctors.md#overview",
    )


def test_doctor_missing_from_explicit_index_is_optional_skip() -> None:
    bundle = _bundle(
        initial={},
        scenarios={
            "doctor_trust": (
                ["doctor:doctor_one", "kb:doctors.md#overview"],
                ["service"],
            )
        },
    )

    result = select_target_marketing(
        bundle,
        _doctors(),
        _index(doctor_refs=()),
        semantic_context="service",
        service_id="service_one",
        today=TODAY,
        include_initial_block=False,
        marketing_scenarios=["doctor_trust"],
    )

    assert result.selected_refs == ("kb:doctors.md#overview",)


def test_doctor_present_in_index_but_absent_from_catalog_is_optional_skip() -> None:
    bundle = _bundle(
        initial={},
        scenarios={
            "doctor_trust": (
                ["doctor:doctor_one", "kb:doctors.md#overview"],
                ["service"],
            )
        },
    )

    result = select_target_marketing(
        bundle,
        TargetDoctorCatalog(doctors={}),
        _index(),
        semantic_context="service",
        service_id="service_one",
        today=TODAY,
        include_initial_block=False,
        marketing_scenarios=["doctor_trust"],
    )

    assert result.selected_refs == ("kb:doctors.md#overview",)


def test_doctors_without_service_are_allowed_only_in_exact_doctors_context() -> None:
    general = select_target_marketing(
        _bundle(),
        _doctors(),
        _index(),
        semantic_context="doctors",
        service_id=None,
        today=TODAY,
        include_initial_block=False,
        marketing_scenarios=["doctor_trust"],
    )
    no_service = select_target_marketing(
        _bundle(),
        _doctors(),
        _index(),
        semantic_context="service",
        service_id=None,
        today=TODAY,
        include_initial_block=False,
        marketing_scenarios=["doctor_trust"],
    )

    assert general.selected_refs == (
        "doctor:doctor_other",
        "doctor:doctor_one",
    )
    assert general.cta_key == "doctor"
    assert no_service.selected_refs == ("kb:doctors.md#overview",)


def test_shown_suppression_and_scenario_initial_dedup_are_exact() -> None:
    result = _select(
        marketing_scenarios=["cost"],
        shown_fact_ids=["service"],
        shown_amplifier_refs=["kb:cost.md#one"],
    )

    assert result.selected_refs == ("fact:global",)
    assert result.amplifier_refs == ()


@pytest.mark.parametrize(
    "ordered_refs",
    [
        ["fact:conflict_a", "fact:conflict_b"],
        ["fact:conflict_b", "fact:conflict_a"],
    ],
)
def test_bidirectional_incompatibility_keeps_first_authored_fact(
    ordered_refs: list[str],
) -> None:
    bundle = _bundle(initial={"service": ordered_refs}, scenarios={})

    result = _select(bundle)

    assert result.selected_refs == (ordered_refs[0],)


def test_zero_limits_keep_applied_scenario_metadata_and_cta_only() -> None:
    result = _select(
        _bundle(limits=(0, 0, 2)),
        marketing_scenarios=["cost"],
    )

    assert result.applied_scenarios == ("cost",)
    assert result.selected_refs == result.amplifier_refs == ()
    assert result.cta_key == "plan"


def test_partial_limits_count_each_ref_once_and_do_not_fill_from_other_context() -> None:
    bundle = _bundle(
        limits=(2, 1, 2),
        initial={"price": ["fact:global"], "service": ["fact:service"]},
    )

    result = _select(bundle, marketing_scenarios=["cost"])

    assert result.amplifier_refs == ("fact:service",)
    assert result.selected_refs == ("fact:service",)


def test_cta_uses_exact_context_then_default_without_consuming_slots() -> None:
    exact = _select(include_initial_block=False)
    fallback = _select(semantic_context="unknown", include_initial_block=False)

    assert exact.selected_refs == fallback.selected_refs == ()
    assert exact.cta_key == "plan"
    assert fallback.cta_key == "callback"


def test_neutral_path_does_not_rotate_initial_block() -> None:
    result = _select(include_initial_block=False, marketing_scenarios=[])

    assert result.applied_scenarios == ()
    assert result.selected_refs == result.amplifier_refs == ()


class _DateSubclass(date):
    pass


@pytest.mark.parametrize(
    ("overrides", "code", "expected_value"),
    [
        ({"semantic_context": "  "}, "marketing_semantic_context_invalid", "  "),
        ({"service_id": 1}, "marketing_service_id_invalid", 1),
        ({"service_id": "missing"}, "marketing_service_not_found", "missing"),
        ({"today": "2026-07-21"}, "marketing_today_invalid", "2026-07-21"),
        (
            {"today": datetime(2026, 7, 21)},
            "marketing_today_invalid",
            datetime(2026, 7, 21),
        ),
        (
            {"today": _DateSubclass(2026, 7, 21)},
            "marketing_today_invalid",
            _DateSubclass(2026, 7, 21),
        ),
        (
            {"include_initial_block": 1},
            "marketing_include_initial_block_invalid",
            1,
        ),
        ({"marketing_scenarios": "cost"}, "marketing_scenario_invalid", "cost"),
        ({"marketing_scenarios": ["bad"]}, "marketing_scenario_invalid", "bad"),
        (
            {"marketing_scenarios": ["cost", "cost"]},
            "marketing_scenario_duplicate",
            ("cost", "cost"),
        ),
        ({"shown_fact_ids": {"one"}}, "marketing_shown_fact_id_invalid", {"one"}),
        ({"shown_fact_ids": [""]}, "marketing_shown_fact_id_invalid", ""),
        (
            {"shown_fact_ids": ["one", "one"]},
            "marketing_shown_fact_id_duplicate",
            ("one", "one"),
        ),
        (
            {"shown_amplifier_refs": "kb:a.md#b"},
            "marketing_shown_amplifier_ref_invalid",
            "kb:a.md#b",
        ),
        (
            {"shown_amplifier_refs": ["broken"]},
            "marketing_shown_amplifier_ref_invalid",
            "broken",
        ),
        (
            {"shown_amplifier_refs": ["kb:a.md#b", "kb:a.md#b"]},
            "marketing_shown_amplifier_ref_duplicate",
            ("kb:a.md#b", "kb:a.md#b"),
        ),
    ],
)
def test_invalid_inputs_have_exact_error_code_and_value(
    overrides: dict[str, object], code: str, expected_value: object
) -> None:
    with pytest.raises(TargetMarketingSelectionError) as exc_info:
        _select(**overrides)

    assert exc_info.value.code == code
    assert exc_info.value.value == expected_value
    assert str(exc_info.value) == f"{code}: {expected_value!r}"


def test_invalid_input_validation_order_matches_public_signature_and_table() -> None:
    with pytest.raises(TargetMarketingSelectionError) as context_error:
        _select(
            semantic_context="",
            service_id="missing",
            today="bad",
            include_initial_block=1,
        )
    with pytest.raises(TargetMarketingSelectionError) as service_error:
        _select(
            service_id="missing",
            today="bad",
            include_initial_block=1,
        )
    with pytest.raises(TargetMarketingSelectionError) as date_error:
        _select(today="bad", include_initial_block=1)

    assert context_error.value.code == "marketing_semantic_context_invalid"
    assert service_error.value.code == "marketing_service_not_found"
    assert date_error.value.code == "marketing_today_invalid"


def test_missing_local_marketing_fact_is_bundle_validation_not_selector_case() -> None:
    payload = _bundle().model_dump()
    payload["facts"].pop("service")

    with pytest.raises(ValidationError) as exc_info:
        ResponseSchemaBundle.model_validate(payload)

    assert "bundle_marketing_fact_missing" in str(exc_info.value)


def test_result_is_frozen_slots_and_calls_are_stateless_without_mutation() -> None:
    bundle = _bundle()
    doctors = _doctors()
    index = _index()
    scenarios = ["cost"]
    shown_facts = ["unused_fact"]
    shown_amplifiers = ["kb:unused.md#one"]
    bundle_before = bundle.model_dump()
    doctors_before = doctors.model_dump()
    index_before = index.model_dump()
    scenarios_before = list(scenarios)
    shown_facts_before = list(shown_facts)
    shown_amplifiers_before = list(shown_amplifiers)

    first = select_target_marketing(
        bundle,
        doctors,
        index,
        semantic_context="service",
        service_id="service_one",
        today=TODAY,
        include_initial_block=True,
        marketing_scenarios=scenarios,
        shown_fact_ids=shown_facts,
        shown_amplifier_refs=shown_amplifiers,
    )
    second = select_target_marketing(
        bundle,
        doctors,
        index,
        semantic_context="service",
        service_id="service_one",
        today=TODAY,
        include_initial_block=True,
        marketing_scenarios=scenarios,
        shown_fact_ids=shown_facts,
        shown_amplifier_refs=shown_amplifiers,
    )

    assert first == second
    assert TargetMarketingSelection.__slots__ == (
        "applied_scenarios",
        "selected_refs",
        "amplifier_refs",
        "cta_key",
        "selection_mode",
    )
    with pytest.raises(FrozenInstanceError):
        first.cta_key = "changed"  # type: ignore[misc]
    assert bundle.model_dump() == bundle_before
    assert doctors.model_dump() == doctors_before
    assert index.model_dump() == index_before
    assert scenarios == scenarios_before
    assert shown_facts == shown_facts_before
    assert shown_amplifiers == shown_amplifiers_before


def test_public_signature_and_source_boundary_are_exact() -> None:
    signature = inspect.signature(select_target_marketing)
    assert tuple(signature.parameters) == (
        "bundle",
        "doctor_catalog",
        "external_index",
        "semantic_context",
        "service_id",
        "today",
        "include_initial_block",
        "marketing_scenarios",
        "shown_fact_ids",
        "shown_amplifier_refs",
        "turn_topic",
    )
    assert all(
        signature.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        for name in tuple(signature.parameters)[3:]
    )
    assert all(
        signature.parameters[name].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        for name in tuple(signature.parameters)[:3]
    )
    assert signature.parameters["marketing_scenarios"].default == ()
    assert signature.parameters["shown_fact_ids"].default == ()
    assert signature.parameters["shown_amplifier_refs"].default == ()
    assert signature.return_annotation == "TargetMarketingSelection"

    source_path = Path("core/target_marketing_selector.py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert imported <= {
        "__future__",
        "collections.abc",
        "dataclasses",
        "datetime",
        "typing",
        "contracts.doctor_schema",
        "contracts.response_schema",
        "contracts.response_schema_refs",
    }
    assert not (
        {
            "open",
            "read_bytes",
            "read_text",
            "write_bytes",
            "write_text",
            "getenv",
            "today",
        }
        & called_attributes
    )
