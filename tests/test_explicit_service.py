"""Unit tests for catalog-based explicit service detection."""
from __future__ import annotations

import pytest

from core.explicit_service import (
    VOLUME_SCOPE_MARKER,
    explicit_service_mentioned,
    explicit_service_mentioned_bool,
)


@pytest.fixture(autouse=True)
def _clear_catalog_cache():
    from core.explicit_service import _load_catalog

    _load_catalog.cache_clear()
    yield
    _load_catalog.cache_clear()


@pytest.mark.parametrize(
    "q,expected",
    [
        ("болит зуб, сколько лечение?", "teeth_treatment"),
        ("шатается зуб, сколько удаление?", "tooth_extraction"),
        ("сколько стоит all-on-4", "all_on_4"),
        ("сколько стоит имплантация", VOLUME_SCOPE_MARKER),
        ("сколько стоит удалить?", "tooth_extraction"),
        ("сколько стоит лечение кариеса", "caries"),
        ("сколько стоит поставить коронку", "zirconia_crowns"),
        ("сколько стоит на всю челюсть", VOLUME_SCOPE_MARKER),
    ],
)
def test_explicit_service_mentioned_positive(q: str, expected: str):
    assert explicit_service_mentioned(q, "demo") == expected
    assert explicit_service_mentioned_bool(q, "demo") is True


@pytest.mark.parametrize(
    "q",
    [
        "шатается зуб, сколько стоит?",
        "болит зуб, сколько стоит?",
        "сколько",
        "сколько стоит?",
        "зуб",
        "а сколько?",
    ],
)
def test_explicit_service_mentioned_negative(q: str):
    assert explicit_service_mentioned(q, "demo") is None
    assert explicit_service_mentioned_bool(q, "demo") is False


def test_explicit_service_mentioned_no_symptom_alias_bridge():
    """After catalog cleanup, symptom phrases must not map to treatment services."""
    assert explicit_service_mentioned("болит зуб, сколько стоит?", "demo") is None
    assert explicit_service_mentioned("шатается зуб, сколько стоит?", "demo") is None
