from __future__ import annotations

import pytest

from core.sales_one_plus_protocol import (
    SALES_ONE_PLUS_SYSTEM_POLICY,
    SalesOnePlusProtocolError,
    parse_sales_one_plus_output,
)


def test_line_protocol_answer_and_admin_body_rules() -> None:
    assert parse_sales_one_plus_output("\n@ANSWER\nГотовый ответ") == ("answer", "Готовый ответ")
    assert parse_sales_one_plus_output("@ADMIN\nmodel prose is ignored") == ("admin", None)
    assert parse_sales_one_plus_output("@ANSWER Да, у здания есть парковка") == (
        "answer",
        "Да, у здания есть парковка",
    )
    assert parse_sales_one_plus_output("@ADMIN inline ignored body") == ("admin", None)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "hello",
        "@ANSWER\n  ",
        "@ANSWERABLE",
        "@ANSWERABLE\nbody",
        3,
    ],
)
def test_line_protocol_rejects_malformed_output(raw: object) -> None:
    with pytest.raises(SalesOnePlusProtocolError):
        parse_sales_one_plus_output(raw)


def test_policy_keeps_sales_fears_but_hands_medical_dialogue_to_admin() -> None:
    assert "Future fears about pain, price, osseointegration, trust, or timing" in (
        SALES_ONE_PLUS_SYSTEM_POLICY
    )
    assert "SALES_CONTEXT.needs_admin_quote is true" in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "return @ANSWER without any price amount or calculation" in (
        SALES_ONE_PLUS_SYSTEM_POLICY
    )
    assert "@ADMIN is only for problematic or medical requests" in (
        SALES_ONE_PLUS_SYSTEM_POLICY
    )
    assert "CURRENT_STRICT_FACTS for the active service scope" in (
        SALES_ONE_PLUS_SYSTEM_POLICY
    )
    assert "Do not lift 13%, 15%, or other promos from the general corpus" in (
        SALES_ONE_PLUS_SYSTEM_POLICY
    )
    assert "deterministic code owns follow-ups, button slots, and CTA" in (
        SALES_ONE_PLUS_SYSTEM_POLICY
    )
    assert "Never calculate, multiply, sum, or interpolate prices" in (
        SALES_ONE_PLUS_SYSTEM_POLICY
    )
