from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts import marketing_cta_refs
from contracts.marketing_cta_refs import (
    MarketingCtaIndex,
    MarketingCtaReferenceError,
    validate_marketing_cta_refs,
)
from contracts.response_schema import TargetMarketingPolicy


def _policy(*, cta_contexts: dict[str, str]) -> TargetMarketingPolicy:
    return TargetMarketingPolicy.model_validate(
        {
            "version": 1,
            "limits": {
                "max_marketing_facts_per_turn": 3,
                "max_amplifiers_per_turn": 2,
                "max_scenarios_per_turn": 2,
            },
            "cta_contexts": cta_contexts,
        }
    )


def test_complete_exact_index_validates_and_unused_keys_are_allowed() -> None:
    policy = _policy(
        cta_contexts={"service": "plan", "price": "price", "default": "callback"}
    )
    index = MarketingCtaIndex(
        cta_keys=("booking", "callback", "plan", "price", "unused")
    )

    assert validate_marketing_cta_refs(policy, index) is None


def test_all_missing_keys_are_one_typed_sorted_deduplicated_error() -> None:
    policy = _policy(
        cta_contexts={
            "service": "z_missing",
            "price": "a_missing",
            "doctors": "z_missing",
            "default": "callback",
        }
    )

    with pytest.raises(MarketingCtaReferenceError) as exc_info:
        validate_marketing_cta_refs(policy, MarketingCtaIndex(cta_keys=("callback",)))

    error = exc_info.value
    assert isinstance(error, ValueError)
    assert error.code == "marketing_cta_refs_missing"
    assert error.missing_cta_keys == ("a_missing", "z_missing")


def test_matching_is_exact_and_case_sensitive() -> None:
    policy = _policy(cta_contexts={"default": "Callback"})

    with pytest.raises(MarketingCtaReferenceError) as exc_info:
        validate_marketing_cta_refs(policy, MarketingCtaIndex(cta_keys=("callback",)))

    assert exc_info.value.missing_cta_keys == ("Callback",)


@pytest.mark.parametrize("value", [[], {"callback"}, "callback"])
def test_index_requires_exact_tuple_container(value: object) -> None:
    with pytest.raises(ValidationError) as exc_info:
        MarketingCtaIndex.model_validate({"cta_keys": value})

    assert "tuple_type" in str(exc_info.value)


@pytest.mark.parametrize(
    ("payload", "token"),
    [
        ({"extra": True}, "extra_forbidden"),
        ({"cta_keys": ("",)}, "string_must_not_be_blank"),
        ({"cta_keys": ("   ",)}, "string_must_not_be_blank"),
        (
            {"cta_keys": ("callback", "callback")},
            "marketing_cta_index_key_duplicate",
        ),
    ],
)
def test_index_rejects_extra_blank_and_duplicate_keys(
    payload: dict[str, object], token: str
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        MarketingCtaIndex.model_validate(payload)

    assert token in str(exc_info.value)


def test_index_is_strict_frozen_and_preserves_order_and_case() -> None:
    raw = ("Plan", "callback", "price")
    index = MarketingCtaIndex(cta_keys=raw)

    assert MarketingCtaIndex.model_config["strict"] is True
    assert MarketingCtaIndex.model_config["frozen"] is True
    assert MarketingCtaIndex.model_config["extra"] == "forbid"
    assert index.cta_keys == raw
    with pytest.raises(ValidationError) as exc_info:
        index.cta_keys = ()  # type: ignore[misc]
    assert "frozen_instance" in str(exc_info.value)


def test_validation_is_stateless_and_does_not_mutate_inputs() -> None:
    policy = _policy(cta_contexts={"service": "plan", "default": "callback"})
    complete = MarketingCtaIndex(cta_keys=("plan", "callback", "unused"))
    incomplete = MarketingCtaIndex(cta_keys=("callback",))
    policy_before = policy.model_dump()
    complete_before = complete.model_dump()

    assert validate_marketing_cta_refs(policy, complete) is None
    with pytest.raises(MarketingCtaReferenceError):
        validate_marketing_cta_refs(policy, incomplete)
    assert validate_marketing_cta_refs(policy, complete) is None
    assert policy.model_dump() == policy_before
    assert complete.model_dump() == complete_before


def test_source_has_only_contract_imports_and_no_io_runtime_or_session_calls() -> None:
    source_path = Path(marketing_cta_refs.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    identifiers = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

    assert imported_modules <= {
        "__future__",
        "pydantic",
        "contracts.response_schema",
    }
    assert not (
        {
            "open",
            "read_bytes",
            "read_text",
            "write_bytes",
            "write_text",
            "getenv",
        }
        & called_attributes
    )
    assert not (
        {
            "client_id",
            "DEFAULT_CLIENT_ID",
            "session",
            "patient_scope",
            "requests",
            "environ",
        }
        & identifiers
    )
