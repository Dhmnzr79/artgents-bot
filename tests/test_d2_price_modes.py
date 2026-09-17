from __future__ import annotations

from datetime import date

import pytest

from contracts.response_plan_materialization import (
    MaterializationContractError,
    OfferConditionEvidence,
)
from core.response_plan_materialization import resolve_d2_envelope_response
from tests.test_d2_multi_request import _envelope, _sources
from tests.test_target_offer_projection import _bundle


@pytest.mark.parametrize(
    ("offer_id", "expected_mode", "expected_text"),
    [
        ("generic_fixed", "fixed", "120 000 ₽"),
        ("option_a_from", "from", "от 68 000 ₽"),
        ("option_c_range", "range", "80 000–110 000 ₽"),
        ("generic_no_public", "no_public_price", "Стоимость определяется после консультации."),
    ],
)
def test_d2_price_modes_are_frozen_without_model_prose(
    offer_id: str, expected_mode: str, expected_text: str
) -> None:
    bundle = _bundle(no_public_active=True)
    payload = bundle.model_dump()
    for offer in payload["offers"]:
        offer["active"] = offer["offer_id"] == offer_id
    narrowed = bundle.__class__.model_validate(payload)

    outcome = resolve_d2_envelope_response(
        _envelope(), _sources(narrowed), as_of=date(2026, 9, 18)
    )

    assert outcome.resolved.d2_price_block is not None
    row = outcome.resolved.d2_price_block.rows[0]
    assert row.mode == expected_mode
    assert expected_text in row.display_text
    assert expected_text in outcome.rendered_text
    if expected_mode == "fixed":
        assert row.amount == 120_000
        assert row.billing_unit == "jaw"
    elif expected_mode == "from":
        assert row.min_amount == 68_000
    elif expected_mode == "range":
        assert (row.min_amount, row.max_amount) == (80_000, 110_000)
    else:
        assert row.approved_text == expected_text


def test_unknown_conditions_do_not_publish_price() -> None:
    bundle = _bundle()
    sources = _sources(bundle).model_copy(
        update={
            "condition_evidence_by_offer": {
                "generic_fixed": OfferConditionEvidence(
                    source_client_id="demo",
                    offer_id="generic_fixed",
                    completeness="unknown",
                )
            }
        }
    )

    with pytest.raises(MaterializationContractError, match="d2_no_complete_price_candidates"):
        resolve_d2_envelope_response(_envelope(), sources, as_of=date(2026, 9, 18))
