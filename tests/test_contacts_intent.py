"""Deterministic contacts detection — canonical phrasings must not leak to composer."""
from __future__ import annotations

import pytest

from policy import contacts_intent


@pytest.mark.parametrize(
    "q",
    [
        "А где вы находитесь?",
        "Где вы находитесь",
        "где находится клиника",
        "адрес клиники",
        "как проехать",
        "где ваша клиника",
    ],
)
def test_contacts_intent_matches_canonical_phrasings(q: str) -> None:
    assert contacts_intent(q) is True


@pytest.mark.parametrize(
    "q",
    [
        "сколько стоит имплант",
        "больно ли ставить имплант",
        "какая гарантия на импланты",
    ],
)
def test_contacts_intent_no_false_positives(q: str) -> None:
    assert contacts_intent(q) is False
