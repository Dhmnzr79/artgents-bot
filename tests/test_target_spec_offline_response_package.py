from __future__ import annotations

import ast
import inspect
import re
from dataclasses import FrozenInstanceError, fields
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.target_spec_offline_response_package as spec_package_module
from contracts.target_response_spec import TargetResponseSpec
from core.target_spec_offline_response_package import (
    TargetSpecBoundOfflineResponsePackage,
    TargetSpecOfflineResponsePackageError,
    assemble_target_spec_offline_response_package,
)


def _spec(**overrides: object) -> TargetResponseSpec:
    payload: dict[str, object] = {
        "response_mode": "answer",
        "service_id": "service_one",
        "tone_key": "commercial_warm",
        "allowed_topics": ("implantation",),
        "forbidden_topics": ("diagnosis",),
        "required_fact_ids": (),
        "required_components": ("content",),
        "followup_source": "content",
        "allow_marketing_facts": False,
        "allow_consultation_close": False,
        "allow_cta": False,
    }
    payload.update(overrides)
    return TargetResponseSpec.model_validate(payload)


def _inputs(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "bundle": object(),
        "doctor_catalog": object(),
        "external_index": object(),
        "consultation_values": (object(),),
        "spec": _spec(),
        "brand_term": None,
        "strategy_context": object(),
        "semantic_context": "service",
        "today": date(2026, 7, 22),
        "md_root": Path("md"),
        "include_initial_block": False,
        "include_consultation_close": False,
        "include_cta": False,
        "marketing_scenarios": (),
        "shown_fact_ids": ("fact",),
        "shown_amplifier_refs": ("kb:a.md#b",),
        "shown_consultation_value_refs": ("a.md",),
    }
    payload.update(overrides)
    return payload


def _nested_package(**overrides: object) -> SimpleNamespace:
    payload: dict[str, object] = {
        "plan": SimpleNamespace(cta_key="consultation"),
        "response_stage": None,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_exact_shape_signature_defaults_and_four_error_codes() -> None:
    assert [field.name for field in fields(TargetSpecBoundOfflineResponsePackage)] == [
        "spec",
        "package",
        "selected_cta_key",
    ]
    assert TargetSpecBoundOfflineResponsePackage.__slots__ == (
        "spec",
        "package",
        "selected_cta_key",
    )
    signature = inspect.signature(assemble_target_spec_offline_response_package)
    assert list(signature.parameters) == [
        "bundle",
        "doctor_catalog",
        "external_index",
        "consultation_values",
        "spec",
        "brand_term",
        "strategy_context",
        "semantic_context",
        "today",
        "md_root",
        "include_initial_block",
        "include_consultation_close",
        "include_cta",
        "marketing_scenarios",
        "shown_fact_ids",
        "shown_amplifier_refs",
        "shown_consultation_value_refs",
        "turn_topic",
        "effective_scope",
        "client_id",
    ]
    for name in (
        "marketing_scenarios",
        "shown_fact_ids",
        "shown_amplifier_refs",
        "shown_consultation_value_refs",
    ):
        assert signature.parameters[name].default == ()
    source = Path("core/target_spec_offline_response_package.py").read_text(
        encoding="utf-8"
    )
    assert set(re.findall(r'"(spec_package_[a-z_]+)"', source)) == {
        "spec_package_spec_invalid",
        "spec_package_selection_invalid",
        "spec_package_not_materializable",
        "spec_package_permission_forbidden",
    }


def test_public_error_contract_and_spec_first_precedence() -> None:
    assert issubclass(TargetSpecOfflineResponsePackageError, ValueError)
    error = TargetSpecOfflineResponsePackageError("code", (1, 2))
    assert (error.code, error.value, str(error)) == ("code", (1, 2), "code: (1, 2)")

    value = object()
    with pytest.raises(TargetSpecOfflineResponsePackageError) as exc_info:
        assemble_target_spec_offline_response_package(
            **_inputs(spec=value, include_initial_block=1)  # type: ignore[arg-type]
        )
    assert exc_info.value.code == "spec_package_spec_invalid"
    assert exc_info.value.value is value


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("include_initial_block", 1),
        ("include_consultation_close", "yes"),
        ("include_cta", None),
    ],
)
def test_selection_flags_are_exact_and_ordered(field: str, value: object) -> None:
    with pytest.raises(TargetSpecOfflineResponsePackageError) as exc_info:
        assemble_target_spec_offline_response_package(
            **_inputs(**{field: value})  # type: ignore[arg-type]
        )
    assert exc_info.value.code == "spec_package_selection_invalid"
    assert exc_info.value.value == (field, value)


@pytest.mark.parametrize(
    "spec",
    [
        _spec(
            response_mode="clarify",
            service_id=None,
            allowed_topics=(),
            forbidden_topics=(),
            required_components=(),
            followup_source=None,
        ),
        _spec(
            response_mode="medical_handoff",
            required_components=(),
            followup_source=None,
        ),
        _spec(service_id=None, required_fact_ids=("fact",)),
    ],
)
def test_nonmaterializable_specs_fail_before_s31(
    monkeypatch: pytest.MonkeyPatch,
    spec: TargetResponseSpec,
) -> None:
    called = False

    def forbidden(*args: object, **kwargs: object) -> object:
        nonlocal called
        called = True
        return object()

    monkeypatch.setattr(
        spec_package_module,
        "assemble_target_offline_response_package",
        forbidden,
    )
    with pytest.raises(TargetSpecOfflineResponsePackageError) as exc_info:
        assemble_target_spec_offline_response_package(**_inputs(spec=spec))  # type: ignore[arg-type]
    assert exc_info.value.code == "spec_package_not_materializable"
    assert exc_info.value.value == (
        spec.response_mode,
        spec.service_id,
        spec.required_components,
    )
    assert called is False


def test_include_cta_clamps_to_spec_allow_cta(monkeypatch: pytest.MonkeyPatch) -> None:
    nested = _nested_package()
    monkeypatch.setattr(
        spec_package_module,
        "assemble_target_offline_response_package",
        lambda *a, **k: nested,
    )
    result = assemble_target_spec_offline_response_package(
        **_inputs(include_cta=True, spec=_spec(allow_cta=False))
    )
    assert result.selected_cta_key is None


@pytest.mark.parametrize(
    ("overrides", "permission"),
    [
        ({"include_initial_block": True}, "marketing_facts"),
        ({"marketing_scenarios": ("cost",)}, "marketing_facts"),
        ({"marketing_scenarios": []}, "marketing_facts"),
        ({"include_consultation_close": True}, "consultation_close"),
    ],
)
def test_selection_cannot_widen_spec_permission(
    overrides: dict[str, object],
    permission: str,
) -> None:
    with pytest.raises(TargetSpecOfflineResponsePackageError) as exc_info:
        assemble_target_spec_offline_response_package(
            **_inputs(**overrides)  # type: ignore[arg-type]
        )
    assert exc_info.value.code == "spec_package_permission_forbidden"
    assert exc_info.value.value == permission


def test_exact_s31_mapping_once_and_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    nested = _nested_package()

    def assembled(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        return nested

    monkeypatch.setattr(
        spec_package_module,
        "assemble_target_offline_response_package",
        assembled,
    )
    spec = _spec(
        service_id="all_on_4",
        required_components=("price", "doctors"),
        followup_source="price",
        allow_marketing_facts=True,
        allow_consultation_close=True,
        allow_cta=True,
    )
    inputs = _inputs(
        spec=spec,
        include_initial_block=True,
        include_consultation_close=True,
        include_cta=True,
        marketing_scenarios=("cost",),
    )
    result = assemble_target_spec_offline_response_package(**inputs)  # type: ignore[arg-type]
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (
        inputs["bundle"],
        inputs["doctor_catalog"],
        inputs["external_index"],
        inputs["consultation_values"],
    )
    assert kwargs["service_term"] == spec.service_id
    assert kwargs["required_components"] is spec.required_components
    assert kwargs["followup_source"] == spec.followup_source
    assert kwargs["include_initial_block"] is True
    assert kwargs["include_consultation_close"] is True
    assert "include_cta" not in kwargs
    for name in (
        "brand_term",
        "strategy_context",
        "semantic_context",
        "today",
        "md_root",
        "marketing_scenarios",
        "shown_fact_ids",
        "shown_amplifier_refs",
        "shown_consultation_value_refs",
    ):
        assert kwargs[name] is inputs[name]
    assert result.spec is spec
    assert result.package is nested
    assert result.selected_cta_key == "consultation"
    with pytest.raises(FrozenInstanceError):
        result.selected_cta_key = None  # type: ignore[misc]


def test_narrower_selection_returns_no_cta_and_preserves_downstream_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nested = _nested_package(plan=SimpleNamespace(cta_key="internal_candidate"))
    monkeypatch.setattr(
        spec_package_module,
        "assemble_target_offline_response_package",
        lambda *args, **kwargs: nested,
    )
    result = assemble_target_spec_offline_response_package(**_inputs())  # type: ignore[arg-type]
    assert result.selected_cta_key is None
    assert result.package.plan.cta_key == "internal_candidate"

    error = RuntimeError("downstream")

    def fail(*args: object, **kwargs: object) -> object:
        raise error

    monkeypatch.setattr(
        spec_package_module,
        "assemble_target_offline_response_package",
        fail,
    )
    with pytest.raises(RuntimeError) as exc_info:
        assemble_target_spec_offline_response_package(**_inputs())  # type: ignore[arg-type]
    assert exc_info.value is error


def test_import_firewall_and_no_test_suppression() -> None:
    paths = [
        Path("core/target_spec_offline_response_package.py"),
        Path("tests/test_target_spec_offline_response_package.py"),
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
