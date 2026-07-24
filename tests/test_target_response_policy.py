from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts.target_response_policy import TargetResponsePolicyRequest
from core.target_response_policy import (
    TargetResponsePolicyBuildError,
    build_target_response_spec,
)


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "response_mode": "answer",
        "service_id": "all_on_4",
        "tone_key": "commercial_warm",
        "allowed_topics": ("implantation",),
        "forbidden_topics": ("diagnosis",),
        "required_fact_ids": ("fact_b", "fact_a"),
        "requested_components": ("content",),
        "primary_component": None,
        "allow_marketing_facts": True,
        "allow_consultation_close": True,
        "allow_cta": True,
    }
    payload.update(overrides)
    return payload


def _request(**overrides: object) -> TargetResponsePolicyRequest:
    return TargetResponsePolicyRequest.model_validate(_payload(**overrides))


def test_exact_request_shape_defaults_and_strict_frozen_config() -> None:
    assert list(TargetResponsePolicyRequest.model_fields) == [
        "response_mode",
        "service_id",
        "family_price_overview_topic",
        "tone_key",
        "allowed_topics",
        "forbidden_topics",
        "required_fact_ids",
        "requested_components",
        "primary_component",
        "allow_marketing_facts",
        "allow_consultation_close",
        "allow_cta",
    ]
    assert TargetResponsePolicyRequest.model_fields["service_id"].default is None
    assert TargetResponsePolicyRequest.model_fields["family_price_overview_topic"].default is None
    assert TargetResponsePolicyRequest.model_fields["forbidden_topics"].default == ()
    assert TargetResponsePolicyRequest.model_fields["required_fact_ids"].default == ()
    assert TargetResponsePolicyRequest.model_fields["primary_component"].default is None
    for name in ("allow_marketing_facts", "allow_consultation_close", "allow_cta"):
        assert TargetResponsePolicyRequest.model_fields[name].default is False
    assert TargetResponsePolicyRequest.model_config["extra"] == "forbid"
    assert TargetResponsePolicyRequest.model_config["frozen"] is True
    assert TargetResponsePolicyRequest.model_config["strict"] is True

    request = _request()
    with pytest.raises(ValidationError, match="frozen_instance"):
        request.primary_component = "content"  # type: ignore[misc]


def test_exact_builder_signature_error_contract_and_sole_code() -> None:
    assert list(inspect.signature(build_target_response_spec).parameters) == ["request"]
    assert issubclass(TargetResponsePolicyBuildError, ValueError)
    error = TargetResponsePolicyBuildError("code", (1, 2))
    assert error.code == "code"
    assert error.value == (1, 2)
    assert str(error) == "code: (1, 2)"

    source = Path("core/target_response_policy.py").read_text(encoding="utf-8")
    assert set(re.findall(r'"(response_policy_[a-z_]+)"', source)) == {
        "response_policy_request_invalid"
    }

    for value in (None, object(), {"response_mode": "answer"}):
        with pytest.raises(TargetResponsePolicyBuildError) as exc_info:
            build_target_response_spec(value)  # type: ignore[arg-type]
        assert exc_info.value.code == "response_policy_request_invalid"
        assert exc_info.value.value is value
        assert str(exc_info.value) == f"response_policy_request_invalid: {value!r}"


@pytest.mark.parametrize(
    ("components", "expected_source"),
    [
        (("content",), "content"),
        (("content", "doctors"), "content"),
        (("price",), "price"),
        (("price", "doctors"), "price"),
        (("doctors",), None),
    ],
)
def test_single_followup_family_is_derived_without_fallback(
    components: tuple[str, ...],
    expected_source: str | None,
) -> None:
    spec = build_target_response_spec(
        _request(requested_components=components, primary_component=None)
    )
    assert spec.required_components == components
    assert spec.followup_source == expected_source


@pytest.mark.parametrize(
    ("primary", "expected_source"),
    [("content", "content"), ("price", "price"), ("doctors", None)],
)
def test_composite_focus_selects_exact_primary_family(
    primary: str,
    expected_source: str | None,
) -> None:
    spec = build_target_response_spec(
        _request(
            requested_components=("doctors", "content", "price"),
            primary_component=primary,
        )
    )
    assert spec.required_components == ("doctors", "content", "price")
    assert spec.followup_source == expected_source


def test_nonterminal_missing_and_ambiguous_primary_fail_closed() -> None:
    with pytest.raises(ValidationError, match="policy_primary_component_missing"):
        _request(requested_components=("content",), primary_component="price")
    with pytest.raises(ValidationError, match="policy_followup_source_ambiguous"):
        _request(
            requested_components=("content", "price"),
            primary_component=None,
        )


def test_terminal_primary_has_request_precedence_and_is_never_dropped() -> None:
    with pytest.raises(ValidationError, match="terminal_primary_component_forbidden"):
        _request(
            response_mode="clarify",
            allowed_topics=(),
            forbidden_topics=(),
            required_fact_ids=("fact",),
            requested_components=("content", "price"),
            primary_component="content",
        )


@pytest.mark.parametrize("mode", ["clarify", "defer"])
def test_terminal_payload_is_rejected_by_s32_when_primary_is_none(mode: str) -> None:
    request = _request(
        response_mode=mode,
        allowed_topics=(),
        forbidden_topics=(),
        required_fact_ids=(),
        requested_components=("content", "price"),
        primary_component=None,
        allow_marketing_facts=False,
        allow_consultation_close=False,
        allow_cta=False,
    )
    with pytest.raises(ValidationError, match="terminal_response_payload_forbidden"):
        build_target_response_spec(request)


def test_valid_terminal_request_builds_payload_free_spec() -> None:
    request = _request(
        response_mode="clarify",
        service_id=None,
        allowed_topics=(),
        forbidden_topics=(),
        required_fact_ids=(),
        requested_components=(),
        primary_component=None,
        allow_marketing_facts=False,
        allow_consultation_close=False,
        allow_cta=False,
    )
    spec = build_target_response_spec(request)
    assert spec.response_mode == "clarify"
    assert spec.required_components == ()
    assert spec.followup_source is None


def test_medical_pure_and_sales_specs_preserve_canonical_boundary() -> None:
    pure = build_target_response_spec(
        _request(
            response_mode="medical_handoff",
            required_fact_ids=(),
            requested_components=(),
            primary_component=None,
            allow_marketing_facts=False,
            allow_consultation_close=False,
            allow_cta=False,
        )
    )
    assert pure.response_mode == "medical_handoff"
    assert pure.required_components == ()

    sales = build_target_response_spec(
        _request(
            response_mode="medical_handoff",
            requested_components=("content", "price"),
            primary_component="price",
        )
    )
    assert sales.response_mode == "medical_handoff"
    assert sales.followup_source == "price"
    assert sales.allow_marketing_facts is True
    assert sales.allow_consultation_close is True
    assert sales.allow_cta is True


def test_request_focus_precedes_combined_invalid_medical_scope() -> None:
    with pytest.raises(ValidationError, match="policy_followup_source_ambiguous"):
        _request(
            response_mode="medical_handoff",
            allowed_topics=(),
            forbidden_topics=(),
            requested_components=("content", "price"),
            primary_component=None,
        )

    request = _request(
        response_mode="medical_handoff",
        allowed_topics=("implantation",),
        forbidden_topics=(),
        requested_components=("content",),
        primary_component=None,
    )
    with pytest.raises(ValidationError, match="medical_forbidden_topics_empty"):
        build_target_response_spec(request)


def test_all_nonderived_fields_and_order_pass_unchanged() -> None:
    request = _request(
        allowed_topics=("implantation", "clinic"),
        forbidden_topics=("diagnosis", "eligibility"),
        required_fact_ids=("fact_z", "fact_a"),
        requested_components=("doctors", "content"),
        primary_component="content",
    )
    before = request.model_dump(mode="python")
    spec = build_target_response_spec(request)
    assert spec.service_id == request.service_id
    assert spec.tone_key == request.tone_key
    assert spec.allowed_topics == request.allowed_topics
    assert spec.forbidden_topics == request.forbidden_topics
    assert spec.required_fact_ids == request.required_fact_ids
    assert spec.required_components == request.requested_components
    assert request.model_dump(mode="python") == before


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("allowed_topics", ("implantation", "implantation"), "allowed_topic_duplicate"),
        ("required_fact_ids", ("fact", "fact"), "required_fact_id_duplicate"),
        ("requested_components", ("content", "content"), "required_component_duplicate"),
    ],
)
def test_canonical_s32_validation_reasons_propagate(
    field: str,
    value: object,
    reason: str,
) -> None:
    request = _request(**{field: value})
    with pytest.raises(ValidationError, match=reason):
        build_target_response_spec(request)


def test_strict_request_and_import_firewall() -> None:
    with pytest.raises(ValidationError):
        TargetResponsePolicyRequest.model_validate(
            _payload(requested_components=["content"])
        )
    with pytest.raises(ValidationError, match="extra_forbidden"):
        TargetResponsePolicyRequest.model_validate({**_payload(), "patient_scope": {}})

    paths = [
        Path("contracts/target_response_policy.py"),
        Path("core/target_response_policy.py"),
        Path("tests/test_target_response_policy.py"),
    ]
    trees = [ast.parse(path.read_text(encoding="utf-8")) for path in paths]
    imported_modules = {
        node.module
        for tree in trees[:2]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(
        module.startswith(
            ("app", "config", "orchestration", "routes", "session", "contracts.turn_frame")
        )
        for module in imported_modules
    )
    assert "patient_scope" not in "\n".join(
        path.read_text(encoding="utf-8") for path in paths[:2]
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"skip", "skipif", "xfail"}
        for tree in trees
        for node in ast.walk(tree)
    )
