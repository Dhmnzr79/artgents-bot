from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, fields
from datetime import date
from pathlib import Path

import pytest

import core.target_offline_response_package as package_module
from core.target_offline_response_assembly import TargetOfflineResponseAssemblyError
from core.target_offline_response_package import (
    TargetOfflineResponsePackage,
    assemble_target_offline_response_package,
)
from core.target_response_followup_materializer import (
    TargetResponseFollowupMaterializationError,
)
from core.target_response_followup_policy import TargetResponseFollowupPolicyError
from core.target_response_materialization_plan import (
    TargetResponseMaterializationPlanError,
)


def _inputs() -> dict[str, object]:
    return {
        "bundle": object(),
        "doctor_catalog": object(),
        "external_index": object(),
        "consultation_values": [object()],
        "service_term": "service",
        "brand_term": None,
        "strategy_context": object(),
        "semantic_context": "service",
        "today": date(2026, 7, 22),
        "include_initial_block": False,
        "include_consultation_close": True,
        "required_components": ["content", "price"],
        "followup_source": "content",
        "md_root": Path("md"),
        "marketing_scenarios": ["scenario"],
        "shown_fact_ids": ["fact"],
        "shown_amplifier_refs": ["amplifier"],
        "shown_consultation_value_refs": ["consultation"],
    }


def _patch_success(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
    results = tuple(object() for _ in range(4))

    def s27(*args: object, **kwargs: object) -> object:
        calls.append(("S27", args, kwargs))
        return results[0]

    def s28(*args: object, **kwargs: object) -> object:
        calls.append(("S28", args, kwargs))
        return results[1]

    def s29(*args: object, **kwargs: object) -> object:
        calls.append(("S29", args, kwargs))
        return results[2]

    def s30(*args: object, **kwargs: object) -> object:
        calls.append(("S30", args, kwargs))
        return results[3]

    monkeypatch.setattr(package_module, "assemble_target_offline_response_materials", s27)
    monkeypatch.setattr(package_module, "build_target_response_materialization_plan", s28)
    monkeypatch.setattr(package_module, "materialize_target_response_followups", s29)
    monkeypatch.setattr(package_module, "select_target_response_followups", s30)
    return calls, results


def test_exact_frozen_shape_signature_and_defaults() -> None:
    assert [field.name for field in fields(TargetOfflineResponsePackage)] == [
        "materials",
        "plan",
        "followup_candidates",
        "selected_followups",
    ]
    assert TargetOfflineResponsePackage.__slots__ == (
        "materials",
        "plan",
        "followup_candidates",
        "selected_followups",
    )
    signature = inspect.signature(assemble_target_offline_response_package)
    assert list(signature.parameters) == [
        "bundle",
        "doctor_catalog",
        "external_index",
        "consultation_values",
        "service_term",
        "brand_term",
        "strategy_context",
        "semantic_context",
        "today",
        "include_initial_block",
        "include_consultation_close",
        "required_components",
        "followup_source",
        "md_root",
        "marketing_scenarios",
        "shown_fact_ids",
        "shown_amplifier_refs",
        "shown_consultation_value_refs",
    ]
    for name in (
        "service_term",
        "brand_term",
        "strategy_context",
        "semantic_context",
        "today",
        "include_initial_block",
        "include_consultation_close",
        "required_components",
        "followup_source",
        "md_root",
    ):
        assert signature.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert signature.parameters[name].default is inspect.Parameter.empty
    for name in (
        "marketing_scenarios",
        "shown_fact_ids",
        "shown_amplifier_refs",
        "shown_consultation_value_refs",
    ):
        assert signature.parameters[name].default == ()


def test_exact_stage_order_forwarding_and_result_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, results = _patch_success(monkeypatch)
    inputs = _inputs()
    before = {key: list(value) for key, value in inputs.items() if isinstance(value, list)}
    result = assemble_target_offline_response_package(**inputs)  # type: ignore[arg-type]

    assert [call[0] for call in calls] == ["S27", "S28", "S29", "S30"]
    assert calls[0][1] == (
        inputs["bundle"],
        inputs["doctor_catalog"],
        inputs["external_index"],
        inputs["consultation_values"],
    )
    for name in (
        "service_term",
        "brand_term",
        "strategy_context",
        "semantic_context",
        "today",
        "include_initial_block",
        "include_consultation_close",
        "marketing_scenarios",
        "shown_fact_ids",
        "shown_amplifier_refs",
        "shown_consultation_value_refs",
    ):
        assert calls[0][2][name] is inputs[name]
    assert calls[1][1] == (results[0],)
    assert calls[1][2]["required_components"] is inputs["required_components"]
    assert calls[2][1] == (results[1], results[0])
    assert calls[2][2]["md_root"] is inputs["md_root"]
    assert calls[3][1] == (results[2],)
    assert calls[3][2]["source"] is inputs["followup_source"]
    assert result.materials is results[0]
    assert result.plan is results[1]
    assert result.followup_candidates is results[2]
    assert result.selected_followups is results[3]
    assert {key: value for key, value in before.items()} == {
        key: value for key, value in inputs.items() if isinstance(value, list)
    }
    with pytest.raises(FrozenInstanceError):
        result.materials = object()  # type: ignore[misc]


@pytest.mark.parametrize(
    ("stage", "error"),
    [
        ("S27", TargetOfflineResponseAssemblyError("offline_assembly_service_not_found", "x")),
        (
            "S28",
            TargetResponseMaterializationPlanError(
                "materialization_plan_components_invalid", "x"
            ),
        ),
        (
            "S29",
            TargetResponseFollowupMaterializationError(
                "followup_content_read_failed", "x"
            ),
        ),
        ("S30", TargetResponseFollowupPolicyError("followup_policy_source_invalid", "x")),
    ],
)
def test_stage_errors_propagate_as_same_object(
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    error: ValueError,
) -> None:
    calls, _results = _patch_success(monkeypatch)

    def fail(*args: object, **kwargs: object) -> object:
        calls.append((stage, args, kwargs))
        raise error

    names = {
        "S27": "assemble_target_offline_response_materials",
        "S28": "build_target_response_materialization_plan",
        "S29": "materialize_target_response_followups",
        "S30": "select_target_response_followups",
    }
    monkeypatch.setattr(package_module, names[stage], fail)
    with pytest.raises(type(error)) as exc_info:
        assemble_target_offline_response_package(**_inputs())  # type: ignore[arg-type]
    assert exc_info.value is error
    expected_index = ("S27", "S28", "S29", "S30").index(stage)
    assert len(calls) == expected_index + 1


def test_import_firewall_and_no_test_suppression() -> None:
    paths = [
        Path("core/target_offline_response_package.py"),
        Path("tests/test_target_offline_response_package.py"),
    ]
    trees = [ast.parse(path.read_text(encoding="utf-8")) for path in paths]
    imported_modules = {
        node.module
        for node in ast.walk(trees[0])
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(
        module.startswith(("app", "config", "orchestration", "routes", "session"))
        for module in imported_modules
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"skip", "skipif", "xfail"}
        for tree in trees
        for node in ast.walk(tree)
    )
