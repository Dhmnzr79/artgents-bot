from __future__ import annotations

import ast
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from contracts.target_response_spec import (
    TargetFollowupSource,
    TargetResponseComponent,
    TargetResponseMode,
    TargetResponseSpec,
)
from core.target_response_followup_policy import (
    TargetFollowupSource as CompatibleFollowupSource,
)
from core.target_response_materialization_plan import (
    TargetResponseComponent as CompatibleResponseComponent,
)


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "response_mode": "answer",
        "service_id": "all_on_4",
        "response_stage": None,
        "scope_price_topic": None,
        "tone_key": "commercial_warm",
        "allowed_topics": ("implantation",),
        "forbidden_topics": ("diagnosis",),
        "required_fact_ids": ("fact_a", "fact_b"),
        "required_components": ("content", "price", "doctors"),
        "followup_source": "content",
        "allow_marketing_facts": True,
        "allow_consultation_close": True,
        "allow_cta": True,
    }
    payload.update(overrides)
    return payload


def _invalid(reason: str, **overrides: object) -> None:
    with pytest.raises(ValidationError, match=reason):
        TargetResponseSpec.model_validate(_payload(**overrides))


def test_exact_fields_defaults_aliases_and_strict_frozen_config() -> None:
    assert list(TargetResponseSpec.model_fields) == [
        "response_mode",
        "service_id",
        "response_stage",
        "scope_price_topic",
        "tone_key",
        "allowed_topics",
        "forbidden_topics",
        "required_fact_ids",
        "required_components",
        "followup_source",
        "allow_marketing_facts",
        "allow_consultation_close",
        "allow_cta",
    ]
    assert TargetResponseSpec.model_fields["service_id"].default is None
    assert TargetResponseSpec.model_fields["response_stage"].default is None
    assert TargetResponseSpec.model_fields["scope_price_topic"].default is None
    assert TargetResponseSpec.model_fields["forbidden_topics"].default == ()
    assert TargetResponseSpec.model_fields["required_fact_ids"].default == ()
    assert TargetResponseSpec.model_fields["followup_source"].default is None
    for name in ("allow_marketing_facts", "allow_consultation_close", "allow_cta"):
        assert TargetResponseSpec.model_fields[name].default is False
    assert TargetResponseSpec.model_config["extra"] == "forbid"
    assert TargetResponseSpec.model_config["frozen"] is True
    assert TargetResponseSpec.model_config["strict"] is True
    assert get_args(TargetResponseMode) == (
        "answer",
        "clarify",
        "defer",
        "medical_handoff",
    )
    assert get_args(TargetResponseComponent) == ("content", "price", "doctors")
    assert get_args(TargetFollowupSource) == ("content", "price")

    spec = TargetResponseSpec.model_validate(_payload())
    with pytest.raises(ValidationError, match="frozen_instance"):
        spec.tone_key = "other"  # type: ignore[misc]


def test_valid_answer_preserves_authored_tuple_order() -> None:
    spec = TargetResponseSpec.model_validate(_payload())
    assert spec.allowed_topics == ("implantation",)
    assert spec.required_fact_ids == ("fact_a", "fact_b")
    assert spec.required_components == ("content", "price", "doctors")
    assert spec.followup_source == "content"
    assert spec.model_dump(mode="python") == _payload()


def test_valid_pure_and_sales_capable_medical_handoff() -> None:
    pure = TargetResponseSpec.model_validate(
        _payload(
            response_mode="medical_handoff",
            required_fact_ids=(),
            required_components=(),
            followup_source=None,
            allow_marketing_facts=False,
            allow_consultation_close=False,
            allow_cta=False,
        )
    )
    assert pure.response_mode == "medical_handoff"
    assert pure.required_components == ()

    sales = TargetResponseSpec.model_validate(
        _payload(
            response_mode="medical_handoff",
            required_components=("content", "price"),
            followup_source="price",
        )
    )
    assert sales.allow_marketing_facts is True
    assert sales.allow_consultation_close is True
    assert sales.allow_cta is True
    assert "diagnosis" in sales.forbidden_topics


@pytest.mark.parametrize("mode", ["clarify", "defer"])
def test_valid_terminal_specs_have_no_normal_payload(mode: str) -> None:
    spec = TargetResponseSpec.model_validate(
        _payload(
            response_mode=mode,
            service_id=None,
            allowed_topics=(),
            forbidden_topics=(),
            required_fact_ids=(),
            required_components=(),
            followup_source=None,
            allow_marketing_facts=False,
            allow_consultation_close=False,
            allow_cta=False,
        )
    )
    assert spec.response_mode == mode
    assert spec.required_components == ()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tone_key", ""),
        ("tone_key", " warm"),
        ("service_id", "service "),
        ("allowed_topics", ("",)),
        ("forbidden_topics", (" diagnosis",)),
        ("required_fact_ids", ("fact ",)),
    ],
)
def test_canonical_tokens_reject_blank_or_outer_whitespace(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        TargetResponseSpec.model_validate(_payload(**{field: value}))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("allowed_topics", ["implantation"]),
        ("forbidden_topics", ["diagnosis"]),
        ("required_fact_ids", ["fact_a"]),
        ("required_components", ["content"]),
        ("allow_cta", 1),
    ],
)
def test_strict_types_reject_coercion(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        TargetResponseSpec.model_validate(_payload(**{field: value}))

    with pytest.raises(ValidationError, match="extra_forbidden"):
        TargetResponseSpec.model_validate({**_payload(), "unexpected": True})


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("allowed_topics", ("implantation", "implantation"), "allowed_topic_duplicate"),
        ("forbidden_topics", ("diagnosis", "diagnosis"), "forbidden_topic_duplicate"),
        ("required_fact_ids", ("fact_a", "fact_a"), "required_fact_id_duplicate"),
        ("required_components", ("content", "content"), "required_component_duplicate"),
    ],
)
def test_tuple_duplicate_reason_tokens(
    field: str,
    value: object,
    reason: str,
) -> None:
    _invalid(reason, **{field: value})


def test_cross_field_reason_order_is_exact() -> None:
    _invalid(
        "response_topic_scope_overlap",
        allowed_topics=("implantation",),
        forbidden_topics=("implantation",),
        required_components=(),
    )
    _invalid("response_scope_empty", allowed_topics=(), required_components=())
    _invalid("response_components_empty", required_components=(), followup_source=None)
    _invalid(
        "terminal_response_payload_forbidden",
        response_mode="clarify",
        allowed_topics=(),
        forbidden_topics=(),
        required_fact_ids=(),
        required_components=(),
        followup_source="content",
        allow_marketing_facts=False,
        allow_consultation_close=False,
        allow_cta=False,
    )
    _invalid(
        "followup_source_component_missing",
        required_components=("doctors",),
        followup_source="content",
    )
    _invalid(
        "medical_forbidden_topics_empty",
        response_mode="medical_handoff",
        forbidden_topics=(),
        required_components=(),
        followup_source=None,
    )


def test_canonical_alias_compatibility_and_s31_direct_ownership() -> None:
    assert CompatibleResponseComponent is TargetResponseComponent
    assert CompatibleFollowupSource is TargetFollowupSource

    tree = ast.parse(
        Path("core/target_offline_response_package.py").read_text(encoding="utf-8")
    )
    imports = [
        (node.module, tuple(alias.name for alias in node.names))
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    ]
    assert (
        "contracts.target_response_spec",
        ("TargetFollowupSource",),
    ) in imports
    assert not any(
        module == "core.target_response_followup_policy"
        and "TargetFollowupSource" in names
        for module, names in imports
    )


def test_import_firewall_and_no_test_suppression() -> None:
    paths = [
        Path("contracts/target_response_spec.py"),
        Path("tests/test_target_response_spec.py"),
    ]
    trees = [ast.parse(path.read_text(encoding="utf-8")) for path in paths]
    imported_modules = {
        node.module
        for node in ast.walk(trees[0])
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(
        module.startswith(("app", "config", "core", "orchestration", "routes", "session"))
        for module in imported_modules
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"skip", "skipif", "xfail"}
        for tree in trees
        for node in ast.walk(tree)
    )
