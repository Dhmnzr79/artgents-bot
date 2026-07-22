from __future__ import annotations

import ast
import inspect
import re
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from core.target_response_followup_materializer import (
    TargetContentFollowup,
    TargetPriceFollowup,
    TargetResponseFollowups,
)
from core.target_response_followup_policy import (
    TargetResponseFollowupPolicyError,
    TargetResponseFollowupSelection,
    select_target_response_followups,
)


def _content(item_id: str) -> TargetContentFollowup:
    return TargetContentFollowup(
        id=item_id,
        label=f"Content {item_id}",
        ref=f"service.md#{item_id}",
        source_content_ref="service.md",
    )


def _price(item_id: str) -> TargetPriceFollowup:
    return TargetPriceFollowup(
        id=item_id,
        label=f"Price {item_id}",
        ref=f"price:service/{item_id}",
        action="price_aspect",
        source_offer_ids=("offer_b", "offer_a"),
    )


def _followups(
    *,
    content: object | None = None,
    price: object | None = None,
) -> TargetResponseFollowups:
    return TargetResponseFollowups(
        content=(_content("second"), _content("first")) if content is None else content,
        price=(_price("stages"), _price("includes")) if price is None else price,
    )  # type: ignore[arg-type]


def test_public_shapes_signature_and_frozen_slots() -> None:
    assert [field.name for field in fields(TargetResponseFollowupSelection)] == [
        "source",
        "content",
        "price",
    ]
    assert TargetResponseFollowupSelection.__slots__ == ("source", "content", "price")
    result = select_target_response_followups(_followups(), source=None)
    with pytest.raises(FrozenInstanceError):
        result.source = "content"  # type: ignore[misc]

    signature = inspect.signature(select_target_response_followups)
    assert list(signature.parameters) == ["followups", "source"]
    assert signature.parameters["source"].kind is inspect.Parameter.KEYWORD_ONLY


def test_error_contract_and_exact_governed_codes() -> None:
    assert issubclass(TargetResponseFollowupPolicyError, ValueError)
    error = TargetResponseFollowupPolicyError("code", (1, 2))
    assert error.code == "code"
    assert error.value == (1, 2)
    assert str(error) == "code: (1, 2)"

    source = Path("core/target_response_followup_policy.py").read_text(encoding="utf-8")
    assert set(re.findall(r'"(followup_policy_[a-z_]+)"', source)) == {
        "followup_policy_candidates_invalid",
        "followup_policy_source_invalid",
    }


@pytest.mark.parametrize("value", [None, object(), {"content": ()}])
def test_invalid_outer_candidates_precede_invalid_source(value: object) -> None:
    with pytest.raises(TargetResponseFollowupPolicyError) as exc_info:
        select_target_response_followups(value, source="wrong")  # type: ignore[arg-type]
    assert exc_info.value.code == "followup_policy_candidates_invalid"
    assert exc_info.value.value is value
    assert str(exc_info.value) == f"followup_policy_candidates_invalid: {value!r}"


@pytest.mark.parametrize(
    "followups",
    [
        _followups(content=[]),
        _followups(content=(_price("wrong"),)),
        _followups(price=[]),
        _followups(price=(_content("wrong"),)),
    ],
)
def test_invalid_inner_candidates_fail_closed(followups: TargetResponseFollowups) -> None:
    with pytest.raises(TargetResponseFollowupPolicyError) as exc_info:
        select_target_response_followups(followups, source=None)
    assert exc_info.value.code == "followup_policy_candidates_invalid"
    assert exc_info.value.value is followups


@pytest.mark.parametrize("source", ["", "doctor", 1, False, object()])
def test_invalid_source_has_exact_payload(source: object) -> None:
    with pytest.raises(TargetResponseFollowupPolicyError) as exc_info:
        select_target_response_followups(_followups(), source=source)  # type: ignore[arg-type]
    assert exc_info.value.code == "followup_policy_source_invalid"
    assert exc_info.value.value is source
    assert str(exc_info.value) == f"followup_policy_source_invalid: {source!r}"


def test_content_preserves_exact_tuple_order_and_identity() -> None:
    followups = _followups()
    result = select_target_response_followups(followups, source="content")
    assert result.source == "content"
    assert result.content is followups.content
    assert [item.id for item in result.content] == ["second", "first"]
    assert result.price == ()


def test_price_preserves_exact_tuple_order_and_identity() -> None:
    followups = _followups()
    result = select_target_response_followups(followups, source="price")
    assert result.source == "price"
    assert result.price is followups.price
    assert [item.id for item in result.price] == ["stages", "includes"]
    assert result.content == ()


def test_none_selects_nothing_and_does_not_mutate_input() -> None:
    followups = _followups()
    before = (followups.content, followups.price)
    result = select_target_response_followups(followups, source=None)
    assert result == TargetResponseFollowupSelection(source=None, content=(), price=())
    assert (followups.content, followups.price) == before


@pytest.mark.parametrize(
    ("followups", "source"),
    [
        (_followups(content=()), "content"),
        (_followups(price=()), "price"),
    ],
)
def test_empty_requested_family_never_falls_back(
    followups: TargetResponseFollowups,
    source: str,
) -> None:
    result = select_target_response_followups(followups, source=source)  # type: ignore[arg-type]
    assert result == TargetResponseFollowupSelection(source=None, content=(), price=())


def test_import_firewall_and_no_test_suppression() -> None:
    paths = [
        Path("core/target_response_followup_policy.py"),
        Path("tests/test_target_response_followup_policy.py"),
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
